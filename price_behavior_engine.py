"""
price_behavior_engine.py — PHASE 1.7A: PRICE MAGNITUDE, PRICE STABILITY &
BOTTOM-TRAP DETECTOR (Eagle / EGX)

الهدف: منع اعتبار سهم فرصة شراء لمجرد قربه من قاعه أو انخفاض RSI. المحرك ده
يقيس شدة التغيّر السعري، ثبات السعر، خطر استمرار الاتجاه الهابط، واحتمال
الوقوع في Falling Knife / Bottom Trap - كل ده كـ Context إضافي في Decision
Card **فقط**، من غير أي تأثير مباشر على Eagle Score أو Final Decision في
هذه المرحلة (قسم 10 و11 من الـPrompt الأصلي).

⚠️ Single Source of Truth: المحرك ده ميحسبش ATR/ADX/RSI/MFI/RVOL/دعم
ومقاومة من الصفر - بيستخدم نفس الأعمدة اللي eagle_core.calculate_indicators()
و eagle_core.find_support_resistance() بيحسبوها، عشان ميبقاش فيه نسخة تانية
من نفس المنطق ممكن تنحرف عن الأصل بمرور الوقت (نفس مبدأ eagle_core.py نفسه).

⚠️ Point-in-Time Discipline (قسم 13): كل دالة هنا بتستخدم بس آخر صف/نافذة
تاريخية من الـDataFrame اللي بتستقبله - صفر إزاحة عكسية نحو المستقبل، صفر نافذة متمركزة (centered)، صفر
أي عمود بيعتمد على المستقبل. المسؤولية عن قطع الـDataFrame عند T نفسها
بتقع على المتصل (final_bot.py / backtest_engine.py)، تماماً زي
build_components_at_point في backtest_engine.py.

⚠️ Synthetic Data Rule (قسم 15): أي بيانات اصطناعية في اختبارات هذا الملف
هي MECHANICAL VALIDATION ONLY - إثبات إن الحسابات صحيحة رياضياً، مش دليل
على أن المحرك بيكتشف القاع فعلياً في السوق المصري أو بيحقق عائد.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

UNKNOWN = "UNKNOWN"
UNAVAILABLE = "UNAVAILABLE"

# ---------------------------------------------------------------------------
# قسم 11 - Future Eagle Integration Interface: معطّل افتراضياً بالكامل.
# ممنوع تغيير القيم دي في هذه المرحلة إلا بعد توثيق + اختبارات + Backtest
# مستقل يثبت الفايدة (نفس قاعدة historical_context_adjustment في
# egx_historical_analyzer.py).
# ---------------------------------------------------------------------------
ENABLE_PRICE_BEHAVIOR_SCORE_ADJUSTMENT = False
price_behavior_adjustment = 0
bottom_trap_adjustment = 0
historical_price_behavior_adjustment = 0

MIN_HISTORY_FOR_STABILITY = 25
MIN_HISTORY_FOR_TREND = 30


# ═══════════════════════════════════════════════════════════════════════
# قسم 5 - PRICE CHANGE MAGNITUDE ENGINE
# ═══════════════════════════════════════════════════════════════════════
def _pct_return(df: pd.DataFrame, n: int):
    """عائد % خلال آخر n جلسة، لحد آخر صف بس (point-in-time). None لو التاريخ ناقص."""
    if df is None or len(df) < n + 1:
        return None
    try:
        c_now = float(df["Close"].iloc[-1])
        c_then = float(df["Close"].iloc[-1 - n])
        if c_then == 0:
            return None
        return round((c_now / c_then - 1) * 100, 3)
    except Exception:
        return None


def _consecutive_down_days(df: pd.DataFrame) -> int:
    """عدد أيام الهبوط المتتالية لحد آخر يوم (backward-only، زي Consecutive_Up_Days في eagle_core)."""
    if df is None or len(df) < 2:
        return 0
    closes = df["Close"].values
    streak = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] < closes[i - 1]:
            streak += 1
        else:
            break
    return streak


def compute_price_change_magnitude(df: pd.DataFrame, large_move_window: int = 20,
                                     large_move_atr_multiple: float = 1.5) -> dict:
    """
    قسم 5. يتوقع df بعد تمريره على eagle_core.calculate_indicators (محتاج
    عمود Close وATR_%). كل الحسابات هنا تستخدم آخر صف/نافذة فقط.
    """
    empty = {
        "status": UNAVAILABLE, "daily_%": None, "3d_%": None, "5d_%": None,
        "10d_%": None, "20d_%": None, "atr_%": None, "return_to_atr_ratio": None,
        "large_down_moves_count": None, "new_lows_count": None,
        "consecutive_down_days": None, "avg_down_day_%": None, "avg_up_day_%": None,
        "downside_acceleration": UNKNOWN,
    }
    if df is None or len(df) < 2:
        return empty

    daily_pct = _pct_return(df, 1)
    r3, r5, r10, r20 = _pct_return(df, 3), _pct_return(df, 5), _pct_return(df, 10), _pct_return(df, 20)

    atr_pct = None
    if "ATR_%" in df.columns and pd.notna(df["ATR_%"].iloc[-1]):
        atr_pct = float(df["ATR_%"].iloc[-1])

    return_to_atr_ratio = None
    if daily_pct is not None and atr_pct not in (None, 0):
        return_to_atr_ratio = round(abs(daily_pct) / atr_pct, 2)

    window = df.tail(large_move_window)
    daily_returns_window = window["Close"].pct_change() * 100

    large_down_moves_count = None
    if "ATR_%" in window.columns and daily_returns_window.dropna().shape[0] >= 5 and window["ATR_%"].notna().any():
        atr_fill_mean = window["ATR_%"].mean()
        thresh = window["ATR_%"].fillna(atr_fill_mean) * large_move_atr_multiple
        large_down_moves_count = int(((-daily_returns_window) > thresh).sum())

    # عدد القيعان الجديدة: كل يوم في آخر large_move_window جلسة بيكسر أدنى
    # إغلاق سجّله السهم خلال reference_lookback جلسة **قبله** (مش داخل
    # النافذة الصغيرة نفسها فقط - ده كان بيدي إيجابيات كاذبة كتير في أي
    # سلسلة هادئة عادية بسبب طبيعة الـrandom walk). كل المقارنة backward-only.
    reference_lookback = max(large_move_window * 3, 60)
    closes_full = df["Close"]
    tail_start = max(len(closes_full) - large_move_window, reference_lookback)
    new_lows_count = 0
    for i in range(tail_start, len(closes_full)):
        current = closes_full.iloc[i]
        ref = closes_full.iloc[max(0, i - reference_lookback):i]
        if pd.notna(current) and ref.notna().sum() >= max(reference_lookback // 2, 5):
            if current < ref.min():
                new_lows_count += 1

    down_days = daily_returns_window[daily_returns_window < 0].dropna()
    up_days = daily_returns_window[daily_returns_window > 0].dropna()
    avg_down_day = round(float(down_days.mean()), 3) if len(down_days) else None
    avg_up_day = round(float(up_days.mean()), 3) if len(up_days) else None

    downside_acceleration = UNKNOWN
    if len(down_days) >= 4:
        half = len(down_days) // 2
        earlier = down_days.iloc[: len(down_days) - half]
        recent = down_days.iloc[len(down_days) - half:]
        if abs(recent.mean()) > abs(earlier.mean()) * 1.1:
            downside_acceleration = "ACCELERATING"
        elif abs(recent.mean()) < abs(earlier.mean()) * 0.9:
            downside_acceleration = "DECELERATING"
        else:
            downside_acceleration = "STABLE"

    return {
        "status": "OK",
        "daily_%": daily_pct, "3d_%": r3, "5d_%": r5, "10d_%": r10, "20d_%": r20,
        "atr_%": round(atr_pct, 3) if atr_pct is not None else None,
        "return_to_atr_ratio": return_to_atr_ratio,
        "large_down_moves_count": large_down_moves_count,
        "new_lows_count": new_lows_count,
        "consecutive_down_days": _consecutive_down_days(df),
        "avg_down_day_%": avg_down_day, "avg_up_day_%": avg_up_day,
        "downside_acceleration": downside_acceleration,
    }


# ═══════════════════════════════════════════════════════════════════════
# قسم 6 - PRICE STABILITY ENGINE (مستقل - لا يخلط سعر منخفض بسعر مستقر)
# ═══════════════════════════════════════════════════════════════════════
def compute_price_stability(df: pd.DataFrame, window: int = 20) -> dict:
    """
    price_stability_status معاني الأربعة حالات:
    - HIGH_VOLATILITY: تذبذب مرتفع حالياً.
    - LOW: تذبذب معتدل/غير مرتفع لكنه غير مستقر بثبات (لا تحسّن واضح).
    - IMPROVING: التذبذب يتقلص فعلياً (Volatility Contracting).
    - STABLE: تذبذب منخفض باستمرار.
    - UNKNOWN: بيانات غير كافية.
    """
    empty = {
        "price_stability_status": UNKNOWN, "price_stability_score": None,
        "rolling_std_return_%": None, "atr_pct_trend": UNKNOWN,
        "high_low_range_pct": None, "narrow_range_days": None,
        "lower_highs_count": None, "lower_lows_count": None,
        "positive_close_ratio_%": None, "volatility_contracting": UNKNOWN,
    }
    if df is None or len(df) < MIN_HISTORY_FOR_STABILITY:
        return empty

    win = df.tail(window)
    daily_returns = (win["Close"].pct_change() * 100).dropna()
    rolling_std = round(float(daily_returns.std()), 3) if len(daily_returns) >= 2 else None

    atr_pct_trend = UNKNOWN
    volatility_contracting = UNKNOWN
    if "ATR_%" in df.columns:
        atr_series = df["ATR_%"].dropna()
        if len(atr_series) >= window:
            tail_window = atr_series.tail(window)
            half = window // 2
            recent_half = tail_window.iloc[-half:]
            prior_half = tail_window.iloc[: window - half]
            if len(prior_half) and len(recent_half) and prior_half.mean() > 0:
                ratio = recent_half.mean() / prior_half.mean()
                if ratio < 0.9:
                    atr_pct_trend, volatility_contracting = "FALLING", True
                elif ratio > 1.1:
                    atr_pct_trend, volatility_contracting = "RISING", False
                else:
                    atr_pct_trend, volatility_contracting = "STABLE", False

    hl_range_pct = None
    if len(win) >= 1:
        hl_range_pct = round(float(((win["High"] - win["Low"]) / win["Close"]).mean() * 100), 3)

    narrow_range_days = int((((win["High"] - win["Low"]) / win["Close"] * 100) <= 3.0).sum())

    highs = win["High"].values
    lows = win["Low"].values
    lower_highs_count = int(sum(1 for i in range(1, len(highs)) if highs[i] < highs[i - 1]))
    lower_lows_count = int(sum(1 for i in range(1, len(lows)) if lows[i] < lows[i - 1]))

    total_days = len(daily_returns)
    positive_close_ratio = round((daily_returns > 0).sum() / total_days * 100, 1) if total_days else None

    # Score وصفي بس (0-100)، ليس إشارة BUY (قسم 6 صريح في هذا).
    score = 50.0
    if rolling_std is not None:
        score -= min(rolling_std, 10) * 3
    if volatility_contracting is True:
        score += 15
    elif volatility_contracting is False:
        score -= 10
    score = round(max(min(score, 100.0), 0.0), 1)

    if rolling_std is None:
        status = UNKNOWN
    elif rolling_std >= 4.0:
        status = "HIGH_VOLATILITY"
    elif volatility_contracting is True and rolling_std < 4.0:
        status = "IMPROVING"
    elif rolling_std < 2.0:
        status = "STABLE"
    else:
        status = "LOW"

    return {
        "price_stability_status": status, "price_stability_score": score,
        "rolling_std_return_%": rolling_std, "atr_pct_trend": atr_pct_trend,
        "high_low_range_pct": hl_range_pct, "narrow_range_days": narrow_range_days,
        "lower_highs_count": lower_highs_count, "lower_lows_count": lower_lows_count,
        "positive_close_ratio_%": positive_close_ratio,
        "volatility_contracting": volatility_contracting,
    }


# ═══════════════════════════════════════════════════════════════════════
# قسم 7 - TREND CONTINUATION RISK
# ⚠️ الابتعاد عن القاع السنوي (Dist_From_52W_Low_%) عمداً غير مستخدم هنا
# كعامل مخفّف للخطر - "الابتعاد عن القاع السنوي لا يلغي خطر الاتجاه الهابط".
# ═══════════════════════════════════════════════════════════════════════
def compute_trend_continuation_risk(df: pd.DataFrame, window: int = 20) -> dict:
    if df is None or len(df) < MIN_HISTORY_FOR_TREND:
        return {"trend_continuation_risk": UNKNOWN, "factors": {}, "reason": "insufficient_history"}

    win = df.tail(window)
    last = df.iloc[-1]

    lower_lows_streak = 0
    lows = win["Low"].values
    for i in range(len(lows) - 1, 0, -1):
        if lows[i] < lows[i - 1]:
            lower_lows_streak += 1
        else:
            break

    lower_highs_present = bool(len(win) > 1 and win["High"].iloc[-1] < win["High"].iloc[:-1].max())

    below_ema21 = None
    if "EMA21" in df.columns and pd.notna(last.get("EMA21", np.nan)):
        below_ema21 = bool(float(last["Close"]) < float(last["EMA21"]))

    adx_val = float(last["ADX_14"]) if "ADX_14" in df.columns and pd.notna(last.get("ADX_14", np.nan)) else None
    plus_di = float(last["Plus_DI"]) if "Plus_DI" in df.columns and pd.notna(last.get("Plus_DI", np.nan)) else None
    minus_di = float(last["Minus_DI"]) if "Minus_DI" in df.columns and pd.notna(last.get("Minus_DI", np.nan)) else None
    adx_confirms_downtrend = None
    if adx_val is not None and plus_di is not None and minus_di is not None:
        adx_confirms_downtrend = bool(adx_val >= 25 and minus_di > plus_di)

    atr_rising = None
    if "ATR_%" in df.columns:
        atr_series = df["ATR_%"].dropna()
        if len(atr_series) >= window:
            tail_window = atr_series.tail(window)
            half = window // 2
            recent_half = tail_window.iloc[-half:]
            prior_half = tail_window.iloc[: window - half]
            if len(prior_half) and len(recent_half) and prior_half.mean() > 0:
                atr_rising = bool(recent_half.mean() > prior_half.mean() * 1.1)

    ret = win["Close"].pct_change()
    vol = win["Volume"] if "Volume" in win.columns else pd.Series(dtype=float)
    down_vals = vol[ret < 0]
    up_vals = vol[ret > 0]
    down_day_vol = float(down_vals.mean()) if len(down_vals) and down_vals.notna().any() else None
    up_day_vol = float(up_vals.mean()) if len(up_vals) and up_vals.notna().any() else None
    higher_volume_on_down_days = None
    if down_day_vol is not None and up_day_vol is not None:
        higher_volume_on_down_days = bool(down_day_vol > up_day_vol * 1.1)

    # كسر دعم "مؤكّد بإغلاق" لا مجرد اختراق لحظي: إغلاق اليوم أقل من أدنى إغلاق سابق في النافذة
    confirmed_break = None
    if len(win) > 1:
        recent_min_close = win["Close"].iloc[:-1].min()
        confirmed_break = bool(float(last["Close"]) < recent_min_close)

    factors = {
        "lower_lows_streak": lower_lows_streak,
        "lower_highs_present": lower_highs_present,
        "below_ema21": below_ema21,
        "adx_confirms_downtrend": adx_confirms_downtrend,
        "atr_rising": atr_rising,
        "higher_volume_on_down_days": higher_volume_on_down_days,
        "confirmed_recent_support_break": confirmed_break,
    }

    boolean_factors = {k: v for k, v in factors.items() if isinstance(v, bool)}
    if not boolean_factors:
        risk = UNKNOWN
    else:
        true_count = sum(1 for v in boolean_factors.values() if v is True)
        # lower_lows_streak >= 3 يُحسب كعامل إضافي صريح (قسم 7: "وجود Lower Lows متتالية")
        if lower_lows_streak >= 3:
            true_count += 1
        if true_count >= 4:
            risk = "HIGH"
        elif true_count >= 2:
            risk = "MEDIUM"
        else:
            risk = "LOW"

    return {"trend_continuation_risk": risk, "factors": factors}


# ═══════════════════════════════════════════════════════════════════════
# قسم 8-9 - BOTTOM-TRAP / FALLING-KNIFE DETECTOR + BOTTOM CONFIRMATION LOGIC
# ═══════════════════════════════════════════════════════════════════════
class BottomTrapDetector:
    """
    لا يدّعي التنبؤ المؤكد - بيحدد خطر شراء سهم في أثناء استمرار الهبوط.
    كل مخرجاته وصفية/سياقية بس (قسم 10).
    """

    def __init__(self, window: int = 20):
        self.window = window

    def evaluate(self, df: pd.DataFrame, price_change_magnitude: dict,
                 price_stability: dict, trend_continuation_risk: dict) -> dict:
        if df is None or len(df) < MIN_HISTORY_FOR_TREND:
            return {
                "bottom_status": UNKNOWN, "falling_knife_risk": UNKNOWN,
                "reason": "insufficient_history",
            }

        last = df.iloc[-1]
        dist_low_52w = None
        if "Dist_From_52W_Low_%" in df.columns and pd.notna(last.get("Dist_From_52W_Low_%", np.nan)):
            dist_low_52w = float(last["Dist_From_52W_Low_%"])
        rsi = float(last["RSI_14"]) if "RSI_14" in df.columns and pd.notna(last.get("RSI_14", np.nan)) else None

        near_52w_low = bool(dist_low_52w is not None and dist_low_52w <= 5)
        rsi_low = bool(rsi is not None and rsi <= 35)  # وحده مش كافي أبداً (قسم 8)

        factors = trend_continuation_risk.get("factors", {}) or {}
        making_new_lows = bool((price_change_magnitude.get("new_lows_count") or 0) >= 2)
        high_down_volume = factors.get("higher_volume_on_down_days") is True
        atr_rising = factors.get("atr_rising") is True
        confirmed_break = factors.get("confirmed_recent_support_break") is True
        adx_bearish = factors.get("adx_confirms_downtrend") is True
        stability_status = price_stability.get("price_stability_status")

        win = df.tail(self.window)
        one_day_bounce, broke_recent_lower_high = False, False
        if len(win) >= 3:
            ret_today = float(win["Close"].iloc[-1] / win["Close"].iloc[-2] - 1)
            ret_yesterday = float(win["Close"].iloc[-2] / win["Close"].iloc[-3] - 1)
            one_day_bounce = ret_today > 0 and ret_yesterday <= 0
            prior_lower_high = win["High"].iloc[:-1].max()
            broke_recent_lower_high = bool(win["Close"].iloc[-1] > prior_lower_high)

        trend_risk = trend_continuation_risk.get("trend_continuation_risk")

        if trend_risk == UNKNOWN:
            falling_knife_risk = UNKNOWN
        else:
            fk_score = 0
            fk_score += 2 if (near_52w_low and making_new_lows) else 0
            fk_score += 1 if high_down_volume else 0
            fk_score += 1 if atr_rising else 0
            fk_score += 1 if confirmed_break else 0
            fk_score += 1 if adx_bearish else 0
            fk_score -= 1 if stability_status == "IMPROVING" else 0
            if fk_score >= 4:
                falling_knife_risk = "HIGH"
            elif fk_score >= 2:
                falling_knife_risk = "MEDIUM"
            else:
                falling_knife_risk = "LOW"

        # bottom_status: تحفّظ متعمد - "Confirmed" ممنوعة إلا بعد Backtest مستقل (قسم 9)
        historical_validation_status = UNKNOWN  # هذه المرحلة مبتعملش هذا الـBacktest المستقل بعد
        if trend_risk == UNKNOWN:
            bottom_status = UNKNOWN
        elif falling_knife_risk == "HIGH" or trend_risk == "HIGH":
            bottom_status = "UNCONFIRMED"
        elif (stability_status in ("IMPROVING", "STABLE") and not making_new_lows
              and trend_risk in ("LOW", "MEDIUM") and not confirmed_break):
            bottom_status = "POSSIBLE_BASE" if trend_risk == "MEDIUM" else "BASE_FORMING"
        elif broke_recent_lower_high and not confirmed_break and historical_validation_status == "VALIDATED":
            bottom_status = "CONFIRMED_ONLY_AFTER_VALIDATION"
        else:
            bottom_status = "UNCONFIRMED"

        return {
            "bottom_status": bottom_status,
            "falling_knife_risk": falling_knife_risk,
            "near_52w_low": near_52w_low,
            "rsi_low_alone_insufficient": rsi_low,
            "one_day_bounce_unconfirmed": bool(one_day_bounce and not broke_recent_lower_high),
            "broke_recent_lower_high": broke_recent_lower_high,
            "historical_validation_status": historical_validation_status,
        }


def compute_bottom_trap_status(df, price_change_magnitude, price_stability, trend_continuation_risk, window=20):
    """واجهة دالة مباشرة فوق BottomTrapDetector - عشان سهولة الاستخدام من غير instantiation يدوي."""
    return BottomTrapDetector(window=window).evaluate(df, price_change_magnitude, price_stability, trend_continuation_risk)


def compute_bottom_confirmation_logic(price_stability: dict, trend_continuation_risk: dict, bottom_trap: dict) -> dict:
    """
    قسم 9: شروط منفصلة صراحة. confirmed_signal دايماً False في هذه المرحلة -
    لسه معمول Backtest مستقل يثبت الفايدة (قسم 9 و16 و20).
    """
    near_bottom = bool(bottom_trap.get("near_52w_low"))
    stabilization = price_stability.get("price_stability_status") in ("IMPROVING", "STABLE")
    reversal_attempt = bool(bottom_trap.get("one_day_bounce_unconfirmed") or bottom_trap.get("broke_recent_lower_high"))
    trend_confirmation = bool(
        bottom_trap.get("broke_recent_lower_high")
        and trend_continuation_risk.get("trend_continuation_risk") in ("LOW", "MEDIUM")
    )
    confirmed_signal = False  # لا تُستخدم كلمة Confirmed بشكل مطلق - قسم 9

    return {
        "near_bottom": near_bottom, "stabilization": stabilization,
        "reversal_attempt": reversal_attempt, "trend_confirmation": trend_confirmation,
        "confirmed_signal": confirmed_signal,
        "confirmed_signal_note": "دايماً False في هذه المرحلة - لسه معمول Backtest مستقل يثبت الفايدة.",
    }


# ═══════════════════════════════════════════════════════════════════════
# قسم 10-12 - Decision Context Aggregator + Data Availability/Coverage
# ═══════════════════════════════════════════════════════════════════════
def build_price_behavior_context(df: pd.DataFrame, has_time_series: bool = True) -> dict:
    """
    نقطة الدخول الرئيسية لـPhase 1.7A. **لا تغيّر Eagle Score أو القرار
    النهائي مباشرة** - المخرجات هنا Context إضافي في Decision Card فقط.

    has_time_series: لو False (يعني عندنا Snapshot لحظي بس من غير سلسلة
    زمنية حقيقية)، بيرجع كل حاجة UNKNOWN صراحة (قسم 12: "لا تحسب stability
    التاريخية كما لو كانت متاحة").
    """
    if not has_time_series:
        magnitude = {"status": UNAVAILABLE}
        stability = {"price_stability_status": UNKNOWN}
        trend_risk = {"trend_continuation_risk": UNKNOWN, "factors": {}}
        bottom_trap = {"bottom_status": UNKNOWN, "falling_knife_risk": UNKNOWN}
        confirmation = compute_bottom_confirmation_logic(stability, trend_risk, bottom_trap)
        data_status = {k: UNAVAILABLE for k in
                        ["price_change_magnitude", "price_stability", "trend_continuation_risk", "bottom_trap"]}
        return {
            "price_change_magnitude": magnitude, "price_stability": stability,
            "trend_continuation_risk": trend_risk, "bottom_trap": bottom_trap,
            "bottom_confirmation": confirmation, "data_status": data_status,
            "coverage_ratio": 0.0,
            "evidence_limitations": ["لا توجد سلسلة زمنية حقيقية لهذا السهم (Snapshot فقط) - كل مخرجات Phase 1.7A غير متاحة."],
            "price_behavior_adjustment": price_behavior_adjustment,
            "bottom_trap_adjustment": bottom_trap_adjustment,
            "historical_price_behavior_adjustment": historical_price_behavior_adjustment,
            "enable_price_behavior_score_adjustment": ENABLE_PRICE_BEHAVIOR_SCORE_ADJUSTMENT,
        }

    magnitude = compute_price_change_magnitude(df)
    stability = compute_price_stability(df)
    trend_risk = compute_trend_continuation_risk(df)
    bottom_trap = compute_bottom_trap_status(df, magnitude, stability, trend_risk)
    confirmation = compute_bottom_confirmation_logic(stability, trend_risk, bottom_trap)

    data_status = {
        "price_change_magnitude": "LIVE" if magnitude.get("status") == "OK" else UNAVAILABLE,
        "price_stability": "LIVE" if stability.get("price_stability_status") != UNKNOWN else UNAVAILABLE,
        "trend_continuation_risk": "LIVE" if trend_risk.get("trend_continuation_risk") != UNKNOWN else UNAVAILABLE,
        "bottom_trap": "LIVE" if bottom_trap.get("bottom_status") != UNKNOWN else UNAVAILABLE,
    }
    scored = [v for v in data_status.values() if v != UNAVAILABLE]
    coverage_ratio = round(len(scored) / len(data_status), 2) if data_status else 0.0

    evidence_limitations = []
    if df is None or len(df) < MIN_HISTORY_FOR_TREND:
        evidence_limitations.append(f"تاريخ الأسعار المتاح أقل من الحد الأدنى ({MIN_HISTORY_FOR_TREND} جلسة) - النتائج غير مكتملة.")
    evidence_limitations.append(
        "هذه المخرجات Price Behavior Context بس - مش توصية شراء/بيع مستقلة، ومتأثرش على "
        "Eagle Score أو القرار النهائي (price_behavior_adjustment = 0 دايماً في هذه المرحلة)."
    )

    return {
        "price_change_magnitude": magnitude, "price_stability": stability,
        "trend_continuation_risk": trend_risk, "bottom_trap": bottom_trap,
        "bottom_confirmation": confirmation, "data_status": data_status,
        "coverage_ratio": coverage_ratio, "evidence_limitations": evidence_limitations,
        "price_behavior_adjustment": price_behavior_adjustment,
        "bottom_trap_adjustment": bottom_trap_adjustment,
        "historical_price_behavior_adjustment": historical_price_behavior_adjustment,
        "enable_price_behavior_score_adjustment": ENABLE_PRICE_BEHAVIOR_SCORE_ADJUSTMENT,
    }


def apply_price_behavior_adjustment(eagle_score, context: dict):
    """
    قسم 11: طبقة تكامل مستقبلية - **behavior-preserving بالكامل افتراضياً**.
    طالما ENABLE_PRICE_BEHAVIOR_SCORE_ADJUSTMENT=False (الحالة الحالية)، الدالة
    دي بترجع eagle_score كما هو تماماً من غير أي لمسة - محدش يقدر يفعّلها
    غلطاً من غير flag صريح + توثيق + اختبارات.
    """
    if not ENABLE_PRICE_BEHAVIOR_SCORE_ADJUSTMENT or eagle_score is None:
        return eagle_score
    total_adjustment = (
        context.get("price_behavior_adjustment", 0)
        + context.get("bottom_trap_adjustment", 0)
        + context.get("historical_price_behavior_adjustment", 0)
    )
    return max(min(eagle_score + total_adjustment, 100.0), 0.0)


# ═══════════════════════════════════════════════════════════════════════
# قسم 17 - Decision Card Additions (فصل Observed Facts / Computed Metrics /
# Interpretation / Decision)
# ═══════════════════════════════════════════════════════════════════════
def format_decision_card_addition(context: dict) -> dict:
    m = context.get("price_change_magnitude", {})
    s = context.get("price_stability", {})
    t = context.get("trend_continuation_risk", {})
    b = context.get("bottom_trap", {})
    cf = context.get("bottom_confirmation", {})

    return {
        "observed_facts": {
            "Daily Change %": m.get("daily_%"),
            "5D Change %": m.get("5d_%"),
            "ATR %": m.get("atr_%"),
            "Consecutive Down Days": m.get("consecutive_down_days"),
            "Lower Lows (window)": s.get("lower_lows_count"),
            "Lower Highs (window)": s.get("lower_highs_count"),
        },
        "computed_metrics": {
            "Volatility (rolling std %)": s.get("rolling_std_return_%"),
            "Stability Status": s.get("price_stability_status"),
            "Trend Continuation Risk": t.get("trend_continuation_risk"),
            "Falling Knife Risk": b.get("falling_knife_risk"),
            "Bottom Status": b.get("bottom_status"),
            "Volume-on-Down-Days Elevated": (t.get("factors", {}) or {}).get("higher_volume_on_down_days"),
            "Trend Confirmation": cf.get("trend_confirmation"),
            "Historical Validation Status": b.get("historical_validation_status", UNKNOWN),
        },
        "interpretation": context.get("evidence_limitations", []),
        "decision": (
            "هذه البطاقة Context تفسيري بس - القرار النهائي من Final Decision "
            "Engine الحالي فقط (eagle_core.make_final_decision)، لا BUY تلقائي من هنا (قسم 10)."
        ),
    }
