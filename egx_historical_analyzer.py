"""
egx_historical_analyzer.py
===========================
PHASE 1.7 — EGX MARKET SEASONALITY & HISTORICAL REGIME ANALYZER

طبقة تحليل إحصائي تاريخي منفصلة تماماً عن Eagle Score - بتجاوب على سؤال
"إيه اللي حصل تاريخياً لما السوق كان شبه دلوقتي؟" - من غير ما تأثر على قرار
الشراء/البيع النهائي (Historical Adjustment = 0 دايماً في المرحلة دي).

═══════════════════════════════════════════════════════════════════════════
حالة معمارية مهمة (Architecture Status) - اقرأها قبل الاستخدام
═══════════════════════════════════════════════════════════════════════════
الموديول ده اتبنى كـ "Single Source of Truth" مستقل بذاته. لاحظنا وقت الـ
AUDIT إن final_bot.py الحالي **معندوش** eagle_core.py ولا backtest_engine.py
منفصلين - كل حاجة (بما فيها Eagle Score) جوه ملف واحد. الموديول ده اتصمم
عشان يُستورد من أي حد (final_bot.py أو backtest مستقبلي) من غير ما يفترض
وجود ملفات مش موجودة فعلياً. دمجه الفعلي مع Eagle Score (لو حبيت) محتاج
قرار تاني منفصل - الموديول ده مستقل وميغيّرش أي سلوك حالي.

حالة البيانات (Data Status):
- المصدر: Yahoo Finance، رمز ^CASE30 (مؤشر EGX30) عبر yfinance
- الفترة الفعلية المتاحة: **غير معروفة وقت كتابة الكود ده** - بيئة التطوير
  هنا من غير إنترنت. الكود بيجيب أي فترة Yahoo يرجّعها فعلياً ويعرضها
  بصراحة (date_range الحقيقي)، ومينفعش يدّعي "10 سنين" أو أي رقم قبل
  التشغيل الفعلي.
- لو التشغيل فشل أو البيانات ناقصة عن الحد الأدنى: كل النتائج المعتمدة
  عليها بترجع "UNAVAILABLE" صراحة، مش أصفار أو أرقام مصطنعة.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None

BENCHMARK_TICKER = "^CASE30"

# عتبات حماية العيّنة الصغيرة - قابلة للتعديل، بس مش لازم تتغيّر عشان تخدم
# نتيجة معينة
HISTORICAL_MIN_SAMPLE_SIZE = 30
HISTORICAL_MIN_YEARS = 1
HISTORICAL_SIMILARITY_MIN_MATCHES = 15

UNAVAILABLE = "UNAVAILABLE"
LOW_SAMPLE = "LOW_SAMPLE"


# ═══════════════════════════════════════════════════════════════════════
# 1) جلب البيانات (Data Loading) - المصدر الحقيقي الوحيد للبيانات التاريخية
# ═══════════════════════════════════════════════════════════════════════
def load_benchmark_history(period: str = "max") -> dict:
    """
    يجيب بيانات ^CASE30 التاريخية الحقيقية من Yahoo Finance.

    بيرجع dict فيه:
        "status": "OK" أو "UNAVAILABLE"
        "data": DataFrame (فاضي لو UNAVAILABLE)
        "date_range": (أول تاريخ, آخر تاريخ) أو None
        "sample_size": عدد الأيام الفعلي
        "years_covered": تقريبي، مبني على عدد الأيام الفعلي

    محتاج إنترنت فعلي وقت التشغيل - في بيئة بدون إنترنت هيرجع UNAVAILABLE
    صراحة بدل ما يكسر أو يخترع بيانات.
    """
    if yf is None:
        return {"status": UNAVAILABLE, "data": pd.DataFrame(), "date_range": None,
                "sample_size": 0, "years_covered": 0, "error": "مكتبة yfinance غير مثبتة"}

    try:
        df = yf.download(BENCHMARK_TICKER, period=period, interval="1d",
                          progress=False, auto_adjust=True)
    except Exception as e:
        return {"status": UNAVAILABLE, "data": pd.DataFrame(), "date_range": None,
                "sample_size": 0, "years_covered": 0, "error": str(e)}

    if df is None or df.empty:
        return {"status": UNAVAILABLE, "data": pd.DataFrame(), "date_range": None,
                "sample_size": 0, "years_covered": 0, "error": "استجابة فاضية من Yahoo"}

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.dropna(subset=["Close"])
    sample_size = len(df)
    years_covered = round(sample_size / 252, 1)  # ~252 يوم تداول في السنة

    if sample_size < HISTORICAL_MIN_SAMPLE_SIZE:
        return {"status": UNAVAILABLE, "data": df, "date_range": None,
                "sample_size": sample_size, "years_covered": years_covered,
                "error": f"عيّنة أصغر من الحد الأدنى ({HISTORICAL_MIN_SAMPLE_SIZE} يوم)"}

    date_range = (df.index[0].strftime("%Y-%m-%d"), df.index[-1].strftime("%Y-%m-%d"))
    return {"status": "OK", "data": df, "date_range": date_range,
            "sample_size": sample_size, "years_covered": years_covered, "error": None}


# ═══════════════════════════════════════════════════════════════════════
# 2) تحضير الميزات اليومية (Point-in-Time Features)
# ═══════════════════════════════════════════════════════════════════════
def prepare_daily_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    يحسب daily_return وconsecutive up/down streak لكل يوم - كل قيمة في
    الصف بتاع يوم T بتعتمد بس على بيانات لغاية T (ولا يوم بعده)، عشان
    نضمن قاعدة point-in-time من الأول.
    """
    out = df.copy()
    out["daily_return_%"] = out["Close"].pct_change() * 100
    out["day_of_week"] = out.index.day_name()
    out["month"] = out.index.month_name()
    out["is_up_day"] = out["daily_return_%"] > 0
    out["is_down_day"] = out["daily_return_%"] < 0

    # streak: عدد أيام الهبوط/الصعود المتتالية لغاية اليوم ده (شامل)
    up_streak = np.zeros(len(out), dtype=int)
    down_streak = np.zeros(len(out), dtype=int)
    for i in range(1, len(out)):
        if out["is_up_day"].iloc[i]:
            up_streak[i] = up_streak[i - 1] + 1
        if out["is_down_day"].iloc[i]:
            down_streak[i] = down_streak[i - 1] + 1
    out["up_streak"] = up_streak
    out["down_streak"] = down_streak

    return out


def compute_forward_returns(df: pd.DataFrame, horizons=(1, 3, 5, 10, 20)) -> pd.DataFrame:
    """
    يحسب العائد المستقبلي (forward return) لكل يوم على أفق زمني معين.
    ده الاستثناء الوحيد المسموح فيه نستخدم بيانات "بعد" T - وبس عشان نقيس
    النتيجة اللي حصلت، مش عشان نستخدمه كـ feature في تحديد الحالة وقت T
    (فرق جوهري ومطلوب صراحة في الملف الأصلي - قسم 14).
    """
    out = df.copy()
    for h in horizons:
        out[f"fwd_return_{h}d_%"] = (out["Close"].shift(-h) / out["Close"] - 1) * 100
    return out


# ═══════════════════════════════════════════════════════════════════════
# 3) تحليل يوم الأسبوع (Day-of-Week Analysis)
# ═══════════════════════════════════════════════════════════════════════
def analyze_day_of_week(features_df: pd.DataFrame) -> dict:
    """قسم 6 من المواصفة - إحصائيات يوم الأسبوع، بس لو العيّنة كافية."""
    result = {}
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    for day in days:
        subset = features_df[features_df["day_of_week"] == day]["daily_return_%"].dropna()
        n = len(subset)
        if n < HISTORICAL_MIN_SAMPLE_SIZE:
            result[day] = {"status": LOW_SAMPLE, "sample_size": n}
            continue
        result[day] = {
            "status": "OK",
            "sample_size": n,
            "up_probability_%": round((subset > 0).mean() * 100, 1),
            "down_probability_%": round((subset < 0).mean() * 100, 1),
            "mean_return_%": round(subset.mean(), 3),
            "median_return_%": round(subset.median(), 3),
            "std_return_%": round(subset.std(), 3),
            "max_gain_%": round(subset.max(), 2),
            "max_loss_%": round(subset.min(), 2),
        }
    return result


# ═══════════════════════════════════════════════════════════════════════
# 4) تحليل موسمي شهري (Monthly Seasonality)
# ═══════════════════════════════════════════════════════════════════════
def analyze_monthly_seasonality(features_df: pd.DataFrame) -> dict:
    """
    قسم 7 - بيحسب إحصائيات كل شهر + "year-by-year consistency" عشان
    نتجنب الادعاء إن "سبتمبر دايماً هابط" لمجرد إن المتوسط سالب.
    """
    result = {}
    months = ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]
    for month in months:
        subset = features_df[features_df["month"] == month]
        returns = subset["daily_return_%"].dropna()
        n = len(returns)
        if n < HISTORICAL_MIN_SAMPLE_SIZE:
            result[month] = {"status": LOW_SAMPLE, "sample_size": n}
            continue

        # نحسب عائد كل سنة لوحدها في الشهر ده، عشان نقيس consistency
        yearly_returns = subset.groupby(subset.index.year)["daily_return_%"].apply(
            lambda x: (1 + x / 100).prod() - 1
        )
        up_years = int((yearly_returns > 0).sum())
        down_years = int((yearly_returns <= 0).sum())

        result[month] = {
            "status": "OK",
            "sample_size": n,
            "mean_daily_return_%": round(returns.mean(), 3),
            "median_daily_return_%": round(returns.median(), 3),
            "std_%": round(returns.std(), 3),
            "max_gain_%": round(returns.max(), 2),
            "max_loss_%": round(returns.min(), 2),
            "up_years": up_years,
            "down_years": down_years,
            "years_analyzed": up_years + down_years,
            "consistency_note": (
                "عيّنة سنوات قليلة جداً - متعتمدش على consistency ده"
                if (up_years + down_years) < 5 else None
            ),
        }
    return result


# ═══════════════════════════════════════════════════════════════════════
# 5) تحليل الأيام المتتالية (Consecutive Up/Down Days)
# ═══════════════════════════════════════════════════════════════════════
def analyze_consecutive_days(fwd_df: pd.DataFrame, max_streak: int = 5,
                              horizons=(1, 3, 5, 10, 20)) -> dict:
    """قسم 8 - بيحسب إيه اللي بيحصل عادة بعد سلسلة أيام هبوط/صعود متتالية."""
    result = {"down": {}, "up": {}}

    for direction, streak_col in [("down", "down_streak"), ("up", "up_streak")]:
        for n_days in range(1, max_streak + 1):
            label = f"{n_days}" if n_days < max_streak else f"{n_days}+"
            if n_days < max_streak:
                mask = fwd_df[streak_col] == n_days
            else:
                mask = fwd_df[streak_col] >= n_days

            subset = fwd_df[mask]
            sample_size = len(subset)

            if sample_size < HISTORICAL_MIN_SAMPLE_SIZE:
                result[direction][label] = {"status": LOW_SAMPLE, "sample_size": sample_size}
                continue

            horizon_stats = {}
            for h in horizons:
                col = f"fwd_return_{h}d_%"
                fwd_returns = subset[col].dropna()
                if len(fwd_returns) < HISTORICAL_MIN_SAMPLE_SIZE:
                    horizon_stats[f"{h}D"] = {"status": LOW_SAMPLE, "sample_size": len(fwd_returns)}
                    continue
                horizon_stats[f"{h}D"] = {
                    "status": "OK",
                    "sample_size": len(fwd_returns),
                    "win_rate_%": round((fwd_returns > 0).mean() * 100, 1),
                    "mean_%": round(fwd_returns.mean(), 3),
                    "median_%": round(fwd_returns.median(), 3),
                    "best_%": round(fwd_returns.max(), 2),
                    "worst_%": round(fwd_returns.min(), 2),
                }

            result[direction][label] = {
                "status": "OK", "sample_size": sample_size, "horizons": horizon_stats,
            }

    return result


# ═══════════════════════════════════════════════════════════════════════
# 6) تحليل الحركات الكبيرة (Large Market Moves)
# ═══════════════════════════════════════════════════════════════════════
def analyze_large_moves(fwd_df: pd.DataFrame, thresholds=(1, 2, 3),
                         horizons=(1, 3, 5, 10, 20)) -> dict:
    """قسم 9 - إيه اللي بيحصل عادة بعد حركة سعرية قوية (هبوط أو صعود)."""
    result = {"down_moves": {}, "up_moves": {}}

    for pct in thresholds:
        down_mask = fwd_df["daily_return_%"] <= -pct
        up_mask = fwd_df["daily_return_%"] >= pct

        for label, mask, bucket in [(f"<=-{pct}%", down_mask, "down_moves"),
                                     (f">=+{pct}%", up_mask, "up_moves")]:
            subset = fwd_df[mask]
            sample_size = len(subset)
            if sample_size < HISTORICAL_MIN_SAMPLE_SIZE:
                result[bucket][label] = {"status": LOW_SAMPLE, "sample_size": sample_size}
                continue

            horizon_stats = {}
            for h in horizons:
                fwd_returns = subset[f"fwd_return_{h}d_%"].dropna()
                if len(fwd_returns) < HISTORICAL_MIN_SAMPLE_SIZE:
                    horizon_stats[f"{h}D"] = {"status": LOW_SAMPLE}
                    continue
                continuation = (fwd_returns < 0) if bucket == "down_moves" else (fwd_returns > 0)
                horizon_stats[f"{h}D"] = {
                    "status": "OK",
                    "sample_size": len(fwd_returns),
                    "continuation_probability_%": round(continuation.mean() * 100, 1),
                    "reversal_probability_%": round((~continuation).mean() * 100, 1),
                    "mean_%": round(fwd_returns.mean(), 3),
                    "median_%": round(fwd_returns.median(), 3),
                }
            result[bucket][label] = {"status": "OK", "sample_size": sample_size, "horizons": horizon_stats}

    return result


# ═══════════════════════════════════════════════════════════════════════
# 7) تصنيف النظام السوقي (Regime Classification) - Point-in-Time
# ═══════════════════════════════════════════════════════════════════════
def classify_regime_at(features_df: pd.DataFrame, as_of_index: int) -> dict:
    """
    قسم 11 - بيصنّف حالة السوق وقت يوم معين (T) بناءً على بيانات لغاية T
    بس (مفيش أي معلومة من بعد T بتدخل هنا - ده بالظبط شرط point-in-time).
    """
    if as_of_index < 20:
        return {"regime": UNAVAILABLE, "reason": "مش كفاية بيانات سابقة لحساب النظام (محتاج 20 يوم على الأقل)"}

    window = features_df.iloc[max(0, as_of_index - 20):as_of_index + 1]
    ret_20d = (window["Close"].iloc[-1] / window["Close"].iloc[0] - 1) * 100
    vol_20d = window["daily_return_%"].std() * np.sqrt(252)
    down_streak_now = int(features_df["down_streak"].iloc[as_of_index])

    # قواعد تصنيف بسيطة وشفافة (مش صندوق أسود) - قابلة للمراجعة والتعديل
    if ret_20d <= -8 or down_streak_now >= 5:
        regime = "SEVERE_RISK_OFF"
    elif ret_20d <= -3 or down_streak_now >= 3:
        regime = "RISK_OFF"
    elif ret_20d >= 5:
        regime = "RISK_ON"
    else:
        regime = "NEUTRAL"

    return {
        "regime": regime,
        "ret_20d_%": round(float(ret_20d), 2),
        "volatility_20d_annualized_%": round(float(vol_20d), 2) if not np.isnan(vol_20d) else None,
        "down_streak": down_streak_now,
    }


# ═══════════════════════════════════════════════════════════════════════
# 8) محرك التشابه (Regime Similarity Engine) - Point-in-Time
# ═══════════════════════════════════════════════════════════════════════
def find_similar_historical_days(features_df: pd.DataFrame, fwd_df: pd.DataFrame,
                                  as_of_index: int, top_n: int = 50,
                                  horizons=(1, 3, 5, 10, 20)) -> dict:
    """
    قسم 12-13 - بيدوّر على أيام تاريخية "شبه" اليوم المطلوب تحليله، باستخدام
    بس بيانات لغاية T (مفيش أي يوم بعد as_of_index يدخل في مجموعة الترشيح).

    معيار التشابه هنا: عائد 20 يوم + التقلب + streak الهبوط/الصعود -
    Euclidean distance بسيط على القيم دي بعد التطبيع (normalization).
    """
    if as_of_index < 20:
        return {"status": UNAVAILABLE, "reason": "مش كفاية بيانات سابقة"}

    current = classify_regime_at(features_df, as_of_index)
    if current["regime"] == UNAVAILABLE:
        return {"status": UNAVAILABLE, "reason": current["reason"]}

    current_vec = np.array([
        current["ret_20d_%"],
        current["volatility_20d_annualized_%"] or 0,
        current["down_streak"],
    ])

    # نبني متجه المقارنة لكل يوم تاريخي **قبل as_of_index بس** (نفس القاعدة)
    candidates = []
    for i in range(20, as_of_index):  # صراحة: range بيوقف قبل as_of_index
        hist = classify_regime_at(features_df, i)
        if hist["regime"] == UNAVAILABLE:
            continue
        vec = np.array([hist["ret_20d_%"], hist["volatility_20d_annualized_%"] or 0, hist["down_streak"]])
        distance = float(np.linalg.norm(current_vec - vec))
        candidates.append((i, distance))

    if len(candidates) < HISTORICAL_SIMILARITY_MIN_MATCHES:
        return {"status": LOW_SAMPLE, "matched_count": len(candidates),
                "minimum_required": HISTORICAL_SIMILARITY_MIN_MATCHES}

    candidates.sort(key=lambda x: x[1])
    top_matches = candidates[:top_n]
    match_indices = [idx for idx, _ in top_matches]

    # نحول المسافة لنسبة تشابه تقريبية (0-100%) للعرض بس - مش مقياس إحصائي رسمي
    max_dist = max(d for _, d in top_matches) or 1
    avg_similarity_pct = round((1 - (sum(d for _, d in top_matches) / len(top_matches)) / max_dist) * 100, 1)

    horizon_outcomes = {}
    for h in horizons:
        col = f"fwd_return_{h}d_%"
        fwd_values = fwd_df.iloc[match_indices][col].dropna()
        if len(fwd_values) < HISTORICAL_MIN_SAMPLE_SIZE // 2:
            horizon_outcomes[f"{h}D"] = {"status": LOW_SAMPLE, "sample_size": len(fwd_values)}
            continue
        horizon_outcomes[f"{h}D"] = {
            "status": "OK",
            "sample_size": len(fwd_values),
            "up_probability_%": round((fwd_values > 0).mean() * 100, 1),
            "mean_%": round(fwd_values.mean(), 3),
            "median_%": round(fwd_values.median(), 3),
        }

    return {
        "status": "OK",
        "current_regime": current,
        "matched_count": len(top_matches),
        "similarity_%": avg_similarity_pct,
        "forward_outcomes": horizon_outcomes,
    }


# ═══════════════════════════════════════════════════════════════════════
# 9) الواجهة العليا - Historical Context (Historical Adjustment = 0 دايماً)
# ═══════════════════════════════════════════════════════════════════════
def get_historical_context(as_of_date: str | None = None) -> dict:
    """
    نقطة الدخول الرئيسية. بترجع Historical Context كامل لتاريخ معين (أو
    آخر يوم متاح لو as_of_date=None)، مع الالتزام الصارم بـ:

        historical_context_adjustment = 0   (دايماً، في المرحلة دي)

    يعني الناتج هنا معلومة سياقية بس (Historical Context)، مش عامل بيغيّر
    قرار الشراء/البيع النهائي - القسم 19 من المواصفة الأصلية بيمنع ده صراحة
    لحد ما يتعمل backtest مستقل يثبت فايدته.
    """
    HISTORICAL_CONTEXT_ADJUSTMENT = 0  # ثابت - ممنوع يتغيّر في المرحلة دي

    loaded = load_benchmark_history()
    if loaded["status"] == UNAVAILABLE:
        return {
            "status": UNAVAILABLE,
            "reason": loaded.get("error", "بيانات غير متاحة"),
            "historical_context_adjustment": HISTORICAL_CONTEXT_ADJUSTMENT,
        }

    if loaded["years_covered"] < HISTORICAL_MIN_YEARS:
        return {
            "status": UNAVAILABLE,
            "reason": f"البيانات المتاحة ({loaded['years_covered']} سنة) أقل من الحد الأدنى ({HISTORICAL_MIN_YEARS} سنة)",
            "sample_size": loaded["sample_size"],
            "date_range": loaded["date_range"],
            "historical_context_adjustment": HISTORICAL_CONTEXT_ADJUSTMENT,
        }

    features_df = prepare_daily_features(loaded["data"])
    fwd_df = compute_forward_returns(features_df)

    if as_of_date is not None:
        matching = features_df.index[features_df.index <= as_of_date]
        if len(matching) == 0:
            return {"status": UNAVAILABLE, "reason": f"مفيش بيانات لغاية {as_of_date} أو قبله"}
        as_of_index = features_df.index.get_loc(matching[-1])
    else:
        as_of_index = len(features_df) - 1

    return {
        "status": "OK",
        "data_source": "Yahoo Finance ^CASE30",
        "date_range": loaded["date_range"],
        "sample_size": loaded["sample_size"],
        "years_covered": loaded["years_covered"],
        "as_of_date": str(features_df.index[as_of_index].date()),
        "regime": classify_regime_at(features_df, as_of_index),
        "similarity": find_similar_historical_days(features_df, fwd_df, as_of_index),
        "day_of_week_stats": analyze_day_of_week(features_df),
        "monthly_seasonality": analyze_monthly_seasonality(features_df),
        "consecutive_days": analyze_consecutive_days(fwd_df),
        "large_moves": analyze_large_moves(fwd_df),
        # ثابت صراحة - راجع القسم 19 و20 من المواصفة الأصلية
        "historical_context_adjustment": HISTORICAL_CONTEXT_ADJUSTMENT,
        "note": (
            "الأرقام دي Historical Context بس - مش توصية شراء/بيع، ومتأثرش "
            "على Eagle Score النهائي (historical_context_adjustment = 0 دايماً "
            "في المرحلة دي لحد ما يتعمل backtest مستقل يثبت فائدتها)."
        ),
    }
