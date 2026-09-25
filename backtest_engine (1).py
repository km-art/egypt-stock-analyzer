"""
backtest_engine.py — Phase 1.6: Historical Backtest & Eagle Score Calibration

الهدف الوحيد: إثبات بالأرقام (مش بالتخمين) هل ارتفاع Eagle Score فعلاً
بيترافق مع نتائج مستقبلية أحسن، وهل BUY CANDIDATE فعلاً أحسن إحصائياً من
WAIT/AVOID.

⚠️ الملف ده لازم "إنترنت" عشان يجيب بيانات تاريخية حقيقية (TradingView عن
طريق tvDatafeed لأسهم مصر، أو yfinance لأمريكا/الإمارات). بيئة Claude اللي
كتبت الكود ده فيها مقطوعة عن الإنترنت تماماً، فمقدرش أشغّله وأجيبلك أرقام
حقيقية من عندي - لازم يتشغّل من عندك (جهازك، أو أي بيئة عندها إنترنت).

طريقة التشغيل:
    pip install tvDatafeed yfinance pandas numpy --break-system-packages
    python backtest_engine.py

الالتزام الأهم في الملف ده (Point-in-Time Discipline):
عند محاكاة قرار في تاريخ T، الكود بياخد بس df[df.index <= T] ويحسب عليه -
مفيش أي عمود أو قيمة من بعد T بتدخل في القرار. العوائد المستقبلية
(Forward Returns) بتتحسب بعد كده من بيانات بعد T، لكن **بس عشان نقيس
النتيجة**، مش عشان تدخل في القرار نفسه.
"""
import warnings
import numpy as np
import pandas as pd

import eagle_core as ec
import price_behavior_engine as pbe

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# إعدادات قابلة للتعديل
# ---------------------------------------------------------------------------
FORWARD_HORIZONS_DAYS = {
    # ⚠️ GAP موثّق: الخطة طلبت آفاق لحظية (5m/15m/30m/1h/4h) - دي مش متاحة
    # لأن مصدر البيانات الوحيد المتاح (TradingView عبر tvDatafeed لمصر،
    # yfinance لأمريكا/الإمارات) شمعات يومية بس، مفيش بيانات داخل اليوم.
    # البديل الصادق: آفاق يومية (Forward Trading Days) بدل الآفاق اللحظية.
    "1D": 1, "3D": 3, "5D": 5, "10D": 10, "20D": 20,
}
SCORE_BUCKETS = [(0, 39), (40, 49), (50, 59), (60, 69), (70, 79), (80, 89), (90, 100)]
MIN_HISTORY_DAYS = 260  # أقل عدد أيام تاريخية قبل أي نقطة قرار عشان المؤشرات (52 أسبوع إلخ) تحسب صح
WALK_FORWARD_SPLIT = {"train": 0.5, "validation": 0.25, "out_of_sample": 0.25}


def fetch_full_history(ticker: str, is_egx: bool):
    """
    يجيب تاريخ سعر كامل لسهم واحد. لازم إنترنت فعلي.
    - مصر: عن طريق tvDatafeed (نفس مصدر final_bot.py).
    - أمريكا/الإمارات: عن طريق yfinance.
    """
    if is_egx:
        try:
            from tvDatafeed import TvDatafeed, Interval
        except ImportError:
            raise RuntimeError("محتاج: pip install tvDatafeed")
        tv = TvDatafeed()
        bare = ticker[:-3] if ticker.endswith(".CA") else ticker
        hist = tv.get_hist(symbol=bare, exchange="EGX", interval=Interval.in_daily, n_bars=2500)
        if hist is None or hist.empty:
            return None
        hist = hist.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
        return hist[["Open", "High", "Low", "Close", "Volume"]]
    else:
        try:
            import yfinance as yf
        except ImportError:
            raise RuntimeError("محتاج: pip install yfinance")
        df = yf.download(ticker, period="10y", progress=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df[["Open", "High", "Low", "Close", "Volume"]]


def build_components_at_point(df_upto_t: pd.DataFrame, egx30_change_20d=None, sector_avg_change=None,
                               overall_avg_change=None, market_regime_info=None, breadth_info=None,
                               fund_score=None, graham_upside_pct=None):
    """
    بيحسب كل مكوّنات Eagle Score من غير أي بيانات بعد آخر يوم في
    df_upto_t. ده قلب الـPoint-in-Time Discipline: df_upto_t لازم يكون
    already مقطوع عند المتصل (caller) قبل ما يوصل هنا.
    """
    df = ec.calculate_indicators(df_upto_t.copy())
    if len(df) < 30:
        return None, None

    last = df.iloc[-1]
    prev = df.iloc[-2]
    p = float(last["Close"])
    e9, e21 = float(last["EMA9"]), float(last["EMA21"])
    adx_val = float(last["ADX_14"]) if pd.notna(last.get("ADX_14", np.nan)) else 0.0
    rsi = float(last["RSI_14"]) if pd.notna(last.get("RSI_14", np.nan)) else 50.0
    mfi = float(last["MFI_14"]) if pd.notna(last.get("MFI_14", np.nan)) else 50.0
    upper = float(last["Upper_Band"]) if pd.notna(last.get("Upper_Band", np.nan)) else p
    lower = float(last["Lower_Band"]) if pd.notna(last.get("Lower_Band", np.nan)) else p
    rvol = float(last["RVOL"]) if pd.notna(last.get("RVOL", np.nan)) else 1.0
    price_up_today = p > float(prev["Close"])
    vol_ma10 = float(last["Vol_MA10"]) if pd.notna(last.get("Vol_MA10", np.nan)) else 0.0
    avg_trade_value = float((df["Close"] * df["Volume"]).tail(10).mean())
    atr_14 = float(last["ATR_14"]) if pd.notna(last.get("ATR_14", np.nan)) else 0.0
    atr_pct = float(last["ATR_%"]) if pd.notna(last.get("ATR_%", np.nan)) else None

    nearest_support, nearest_resistance = ec.find_support_resistance(df)
    min_stop_distance = max(0.5 * atr_14, p * 0.01)
    support_distance = (p - nearest_support) if nearest_support is not None else 0
    if nearest_support is not None and min_stop_distance <= support_distance <= p * 0.08:
        stop_loss_price = nearest_support
    else:
        stop_loss_price = max(p - 1.5 * atr_14, p * 0.9)
    if nearest_resistance is not None:
        target_price = nearest_resistance
    elif upper > p:
        target_price = upper
    else:
        target_price = None
    risk_amount = p - stop_loss_price
    reward_amount = (target_price - p) if target_price else None
    rr_ratio = round(reward_amount / risk_amount, 2) if (risk_amount > 0 and reward_amount and reward_amount > 0) else None

    components = {
        "trend": ec._score_trend(e9, e21, adx_val, p),
        "momentum": ec._score_momentum(rsi, mfi, upper, lower, p),
        "volume_rvol": ec._score_volume_rvol(rvol, price_up_today),
        "liquidity": ec._score_liquidity(avg_trade_value),
        "risk_reward": ec._score_risk_reward(rr_ratio),
        "market_depth": None,  # GAP: لا يوجد Order Book تاريخي - UNAVAILABLE دايماً في الـBacktest
        "market_regime": ec.market_regime_score_component(market_regime_info),
        "breadth": ec.breadth_score_component(breadth_info),
        "fundamentals": ec._score_fundamentals(fund_score),
        "valuation": ec._score_valuation(graham_upside_pct),
        "relative_strength": ec._score_relative_strength(None, egx30_change_20d),  # يحتاج ربط فعلي بالتغيّر 20 يوم للسهم
        "sector_strength": ec._score_sector_strength(sector_avg_change, overall_avg_change),
    }
    # --- PHASE 1.7A: Price Behavior Context (قسم 16) ---------------------
    # Context بس، صفر تأثير على Eagle Score هنا: مفيش أي قيمة من
    # price_behavior_context بتدخل في components أو eagle_result فوق - بيتم
    # حفظه بس عشان تقسيم نتائج الـBacktest حسب Falling Knife Risk/Price
    # Stability/Trend Continuation Risk (مطلوب صراحة في قسم 16).
    price_behavior_context = pbe.build_price_behavior_context(df)

    extra = {
        "rvol": rvol, "avg_trade_value": avg_trade_value, "price_up_today": price_up_today,
        "rr_ratio": rr_ratio, "atr_pct": atr_pct, "price": p,
        "price_behavior": price_behavior_context,
    }
    return components, extra


def compute_forward_returns(full_df: pd.DataFrame, signal_date, horizons_days: dict):
    """
    عوائد للأمام بعد تاريخ الإشارة - دي الوحيدة المسموح تستخدم بيانات
    'بعد T'، لأنها مقياس النتيجة مش مدخل في القرار.
    """
    if signal_date not in full_df.index:
        return {}
    idx = full_df.index.get_loc(signal_date)
    entry_price = float(full_df["Close"].iloc[idx])
    results = {}
    for label, n_days in horizons_days.items():
        target_idx = idx + n_days
        if target_idx >= len(full_df):
            results[label] = None
            continue
        window = full_df.iloc[idx + 1: target_idx + 1]
        exit_price = float(full_df["Close"].iloc[target_idx])
        fwd_return_pct = (exit_price / entry_price - 1) * 100
        mfe_pct = ((window["High"].max() / entry_price) - 1) * 100 if not window.empty else None
        mae_pct = ((window["Low"].min() / entry_price) - 1) * 100 if not window.empty else None
        results[label] = {"return_%": fwd_return_pct, "mfe_%": mfe_pct, "mae_%": mae_pct}
    return results


def run_point_in_time_backtest(tickers: list, is_egx_map: dict, step_days: int = 5):
    """
    المحرك الرئيسي: لكل سهم، بيمشي يوم بيوم (بفاصل step_days لتقليل
    التكرار) من MIN_HISTORY_DAYS لحد قبل النهاية بعدد أيام = أطول أفق
    (عشان نقدر نقيس Forward Return)، وعند كل نقطة بيبني القرار من غير أي
    نظرة للمستقبل، وبعدين يقيس النتيجة الفعلية اللي حصلت بعدين.
    """
    max_horizon = max(FORWARD_HORIZONS_DAYS.values())
    all_signals = []

    for ticker in tickers:
        is_egx = is_egx_map.get(ticker, False)
        full_df = fetch_full_history(ticker, is_egx)
        if full_df is None or len(full_df) < MIN_HISTORY_DAYS + max_horizon + 10:
            print(f"[GAP] {ticker}: بيانات تاريخية غير كافية - اتشال من التحليل")
            continue

        for i in range(MIN_HISTORY_DAYS, len(full_df) - max_horizon, step_days):
            signal_date = full_df.index[i]
            df_upto_t = full_df.iloc[: i + 1]  # === القيد الأهم: بيانات لحد T بس ===

            components, extra = build_components_at_point(df_upto_t)
            if components is None:
                continue

            eagle_result = ec.compute_eagle_score(components)
            if eagle_result["eagle_score"] is None:
                continue

            data_statuses = {
                "technical": "LIVE", "market_depth": "UNAVAILABLE",
                "market_regime": "UNAVAILABLE", "breadth": "UNAVAILABLE",
                "fundamentals": "UNAVAILABLE", "relative_strength": "UNAVAILABLE",
                "sector_strength": "UNAVAILABLE",
                "early_move": "DISABLED_NO_PROVIDER", "news_impact": "DISABLED_NO_PROVIDER",
            }
            coverage = eagle_result["components_used"] / max(eagle_result["components_total"], 1)
            confidence_result = ec.compute_data_confidence(data_statuses, eagle_coverage_ratio=coverage)
            conflict_result = ec.detect_signal_conflicts(
                eagle_result["eagle_score"], None, extra["rvol"], extra["avg_trade_value"],
                None, confidence_result["confidence_pct"], extra["rr_ratio"], extra["price_up_today"], None,
            )
            final_decision = ec.make_final_decision(
                eagle_result["eagle_score"], conflict_result, confidence_result["confidence_pct"],
                None, extra["avg_trade_value"], extra["rr_ratio"],
            )

            forward = compute_forward_returns(full_df, signal_date, FORWARD_HORIZONS_DAYS)

            pb = extra.get("price_behavior", {})
            all_signals.append({
                "ticker": ticker, "date": signal_date, "eagle_score": eagle_result["eagle_score"],
                "components_used": eagle_result["components_used"],
                "data_confidence_pct": confidence_result["confidence_pct"],
                "final_decision": final_decision,
                "conflict_count": conflict_result["conflict_count"],
                "has_blocking_conflict": conflict_result["has_blocking_conflict"],
                "forward": forward,
                # PHASE 1.7A (قسم 16) - Context بس، مش داخل في eagle_result/final_decision فوق
                "falling_knife_risk": pb.get("bottom_trap", {}).get("falling_knife_risk"),
                "bottom_status": pb.get("bottom_trap", {}).get("bottom_status"),
                "price_stability_status": pb.get("price_stability", {}).get("price_stability_status"),
                "trend_continuation_risk": pb.get("trend_continuation_risk", {}).get("trend_continuation_risk"),
            })

    return pd.DataFrame(all_signals)


def bucket_score(score):
    for lo, hi in SCORE_BUCKETS:
        if lo <= score <= hi:
            return f"{lo}-{hi}"
    return "UNKNOWN"


def analyze_bucket_performance(signals_df: pd.DataFrame, horizon_label: str):
    """Win Rate / Avg Return / Median / Profit Factor / Expectancy لكل Score Bucket."""
    rows = []
    signals_df = signals_df.copy()
    signals_df["bucket"] = signals_df["eagle_score"].apply(bucket_score)
    signals_df[f"ret_{horizon_label}"] = signals_df["forward"].apply(
        lambda f: f.get(horizon_label, {}).get("return_%") if f.get(horizon_label) else None
    )
    for bucket_label, _ in [(f"{lo}-{hi}", None) for lo, hi in SCORE_BUCKETS]:
        sub = signals_df[(signals_df["bucket"] == bucket_label) & signals_df[f"ret_{horizon_label}"].notna()]
        if sub.empty:
            rows.append({"bucket": bucket_label, "n_signals": 0})
            continue
        returns = sub[f"ret_{horizon_label}"]
        wins = returns[returns > 0]
        losses = returns[returns <= 0]
        win_rate = round(len(wins) / len(returns) * 100, 1)
        avg_return = round(returns.mean(), 2)
        median_return = round(returns.median(), 2)
        gross_profit = wins.sum()
        gross_loss = abs(losses.sum())
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
        expectancy = round(returns.mean(), 2)
        rows.append({
            "bucket": bucket_label, "n_signals": len(returns), "win_rate_%": win_rate,
            "avg_return_%": avg_return, "median_return_%": median_return,
            "profit_factor": profit_factor, "expectancy_%": expectancy,
        })
    return pd.DataFrame(rows)


def analyze_decision_performance(signals_df: pd.DataFrame, horizon_label: str):
    """مقارنة BUY CANDIDATE / WAIT / AVOID / NO TRADE إحصائياً."""
    signals_df = signals_df.copy()
    signals_df[f"ret_{horizon_label}"] = signals_df["forward"].apply(
        lambda f: f.get(horizon_label, {}).get("return_%") if f.get(horizon_label) else None
    )
    signals_df["decision_simple"] = signals_df["final_decision"].apply(
        lambda d: "BUY CANDIDATE" if "BUY CANDIDATE" in d else ("WAIT" if "WAIT" in d else ("AVOID" if "AVOID" in d else "NO TRADE"))
    )
    rows = []
    for decision in ["BUY CANDIDATE", "WAIT", "AVOID", "NO TRADE"]:
        sub = signals_df[(signals_df["decision_simple"] == decision) & signals_df[f"ret_{horizon_label}"].notna()]
        if sub.empty:
            rows.append({"decision": decision, "n_signals": 0})
            continue
        returns = sub[f"ret_{horizon_label}"]
        rows.append({
            "decision": decision, "n_signals": len(returns),
            "win_rate_%": round((returns > 0).mean() * 100, 1),
            "avg_return_%": round(returns.mean(), 2),
            "median_return_%": round(returns.median(), 2),
        })
    return pd.DataFrame(rows)


def analyze_by_price_behavior_risk(signals_df: pd.DataFrame, horizon_label: str, segment_col: str):
    """
    قسم 16: تقسيم نتائج الـBacktest حسب Falling Knife Risk / Price
    Stability / Trend Continuation Risk. ده تحليل وصفي بعدي بس (post-hoc) -
    ملوش أي تأثير على القرار وقت T نفسه، وميغيرش Eagle Score.
    segment_col: "falling_knife_risk" أو "price_stability_status" أو
    "trend_continuation_risk" أو "bottom_status".
    """
    signals_df = signals_df.copy()
    signals_df[f"ret_{horizon_label}"] = signals_df["forward"].apply(
        lambda f: f.get(horizon_label, {}).get("return_%") if f.get(horizon_label) else None
    )
    rows = []
    for segment_value in sorted(signals_df[segment_col].dropna().unique().tolist()):
        sub = signals_df[(signals_df[segment_col] == segment_value) & signals_df[f"ret_{horizon_label}"].notna()]
        if sub.empty:
            rows.append({segment_col: segment_value, "n_signals": 0})
            continue
        returns = sub[f"ret_{horizon_label}"]
        rows.append({
            segment_col: segment_value, "n_signals": len(returns),
            "win_rate_%": round((returns > 0).mean() * 100, 1),
            "avg_return_%": round(returns.mean(), 2),
            "median_return_%": round(returns.median(), 2),
        })
    return pd.DataFrame(rows)


def walk_forward_split(signals_df: pd.DataFrame):
    """تقسيم زمني (مش عشوائي) - Train/Validation/Out-of-Sample."""
    signals_df = signals_df.sort_values("date")
    n = len(signals_df)
    n_train = int(n * WALK_FORWARD_SPLIT["train"])
    n_val = int(n * WALK_FORWARD_SPLIT["validation"])
    return {
        "train": signals_df.iloc[:n_train],
        "validation": signals_df.iloc[n_train:n_train + n_val],
        "out_of_sample": signals_df.iloc[n_train + n_val:],
    }


if __name__ == "__main__":
    # مثال استخدام - عدّل القائمة دي حسب الأسهم اللي عايز تختبرها
    EXAMPLE_TICKERS = ["COMI.CA", "HRHO.CA", "ETEL.CA", "TMGH.CA", "SWDY.CA"]
    IS_EGX = {t: True for t in EXAMPLE_TICKERS}

    print("بدء Point-in-Time Backtest... ده هياخد وقت (طلبات شبكة حقيقية).")
    signals = run_point_in_time_backtest(EXAMPLE_TICKERS, IS_EGX, step_days=5)

    if signals.empty:
        print("مفيش أي إشارات اتحسبت - تأكد من الاتصال بالإنترنت ومن صحة الرموز.")
    else:
        signals.to_csv("backtest_signals_raw.csv", index=False)
        print(f"تم توليد {len(signals)} إشارة. اتحفظت في backtest_signals_raw.csv")

        for horizon in ["1D", "5D", "10D", "20D"]:
            print(f"\n=== Score Bucket Performance ({horizon}) ===")
            print(analyze_bucket_performance(signals, horizon).to_string(index=False))

            print(f"\n=== Decision Performance ({horizon}) ===")
            print(analyze_decision_performance(signals, horizon).to_string(index=False))

            # PHASE 1.7A (قسم 16) - Context تحليلي بعدي بس
            print(f"\n=== Falling Knife Risk Segmentation ({horizon}) ===")
            print(analyze_by_price_behavior_risk(signals, horizon, "falling_knife_risk").to_string(index=False))
            print(f"\n=== Price Stability Segmentation ({horizon}) ===")
            print(analyze_by_price_behavior_risk(signals, horizon, "price_stability_status").to_string(index=False))
            print(f"\n=== Trend Continuation Risk Segmentation ({horizon}) ===")
            print(analyze_by_price_behavior_risk(signals, horizon, "trend_continuation_risk").to_string(index=False))

        splits = walk_forward_split(signals)
        print(f"\n=== Walk-Forward Split sizes ===")
        for name, part in splits.items():
            print(f"{name}: {len(part)} signals")
