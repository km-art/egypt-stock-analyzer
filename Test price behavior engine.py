"""
test_price_behavior_engine.py — PHASE 1.7A tests

⚠️ SYNTHETIC DATA RULE (قسم 15): كل بيانات الاختبارات هنا مصطنعة (Synthetic).
MECHANICAL VALIDATION ONLY - بتثبت إن الحسابات والمنطق صحيحين رياضياً بس،
مش دليل على أن المحرك بيكتشف القاع فعلياً في السوق المصري أو بيحقق عائد.

تشغيل: python test_price_behavior_engine.py
"""
import subprocess
import sys

import numpy as np
import pandas as pd

import eagle_core as ec
import price_behavior_engine as pbe

PASS = []
FAIL = []


def _check(name, condition, detail=""):
    if condition:
        PASS.append(name)
        print(f"✅ {name}")
    else:
        FAIL.append(name)
        print(f"❌ {name} — {detail}")


# ---------------------------------------------------------------------------
# مولّد بيانات OHLCV مصطنعة (MECHANICAL VALIDATION ONLY)
# ---------------------------------------------------------------------------
def make_df(closes, start_vol=1_000_000, vol_pattern=None, high_low_pad=0.01, seed=0):
    """
    يبني DataFrame OHLCV مصطنع من قائمة أسعار إغلاق، ويمرره على
    eagle_core.calculate_indicators (نفس مصدر المؤشرات المستخدم في الإنتاج).
    """
    n = len(closes)
    idx = pd.bdate_range("2023-01-02", periods=n)
    closes = np.array(closes, dtype=float)
    opens = np.concatenate([[closes[0]], closes[:-1]])
    highs = np.maximum(opens, closes) * (1 + high_low_pad)
    lows = np.minimum(opens, closes) * (1 - high_low_pad)
    if vol_pattern is None:
        rng = np.random.default_rng(seed)
        vols = start_vol * (1 + rng.normal(0, 0.05, n))
    else:
        vols = np.array(vol_pattern, dtype=float)
        if len(vols) != n:
            raise ValueError("vol_pattern length must match closes length")
    df = pd.DataFrame({"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": vols}, index=idx)
    return ec.calculate_indicators(df)


def steady_uptrend_df(n=300, start=100.0, daily_pct=0.15, noise=0.002, seed=1):
    rng = np.random.default_rng(seed)
    rets = daily_pct / 100 + rng.normal(0, noise, n)
    closes = start * np.cumprod(1 + rets)
    return make_df(closes.tolist(), seed=seed)


def steady_downtrend_df(n=300, start=100.0, daily_pct=-0.4, noise=0.003, accelerate=False, seed=2):
    rng = np.random.default_rng(seed)
    if accelerate:
        rets = np.linspace(daily_pct / 100 * 0.5, daily_pct / 100 * 2.0, n) + rng.normal(0, noise, n)
    else:
        rets = daily_pct / 100 + rng.normal(0, noise, n)
    closes = start * np.cumprod(1 + rets)
    return make_df(closes.tolist(), seed=seed)


def flat_low_volatility_df(n=300, start=100.0, noise=0.0015, seed=3):
    rng = np.random.default_rng(seed)
    rets = rng.normal(0, noise, n)
    closes = start * np.cumprod(1 + rets)
    return make_df(closes.tolist(), seed=seed)


def high_volatility_df(n=300, start=100.0, noise=0.05, seed=4):
    rng = np.random.default_rng(seed)
    rets = rng.normal(0, noise, n)
    closes = start * np.cumprod(1 + rets)
    return make_df(closes.tolist(), seed=seed)


def stabilizing_after_decline_df(n=300, start=100.0, seed=5):
    """
    Scenario B (حتمي - بدون عشوائية عشان اختبار غير هش): هبوط تدريجي واضح
    لأول 200 يوم، بعدها تذبذب صغير جداً حوالين نفس المستوى (سعر يتماسك) -
    بدون أي يوم يكسر أدنى نقطة وصلها في الهبوط (يعني مفيش قيعان جديدة فعلية).
    """
    decline_days = 200
    calm_days = n - decline_days
    decline_closes = start * (1 - 0.003) ** np.arange(decline_days)  # هبوط ثابت ~0.3%/يوم
    base_price = decline_closes[-1]
    # تذبذب صغير جداً (±0.3%) حوالين base_price - موجة جيبية خفيفة، دايماً فوق أدنى نقطة في الهبوط
    calm_wave = 0.003 * np.sin(np.linspace(0, 6 * np.pi, calm_days))
    calm_closes = base_price * (1 + calm_wave)
    closes = np.concatenate([decline_closes, calm_closes])
    return make_df(closes.tolist(), high_low_pad=0.003, seed=seed)


def bottom_trap_high_risk_df(n=300, start=100.0, seed=6):
    """
    Scenario A (حتمي): سعر مستقر لفترة طويلة (تأسيس تاريخ للمؤشرات)، ثم
    هبوط متسارع وحاد في آخر الفترة مع اتساع مدى التذبذب يوماً بعد يوم
    (ATR صاعد بوضوح)، وحجم تداول أعلى بكتير في أيام الهبوط تحديداً - عشان
    نضمن Falling Knife Risk = HIGH بشكل غير هش لأي seed.
    """
    stable_days = n - 60
    decline_days = n - stable_days  # 60 يوم هبوط متسارع
    stable_closes = np.full(stable_days, start)
    # هبوط تراكمي متسارع: كل يوم بيهبط أكتر من اللي قبله، مع ارتداد صغير
    # كل 5 أيام (يوم "صعود" بحجم أقل) عشان نضمن وجود عينة أيام صاعدة فعلية
    # تتقارن بيها أيام الهبوط ذات الحجم الأعلى (بدل هبوط أحادي الاتجاه 100%
    # يمنع أي مقارنة حجم صاعد/هابط أصلاً).
    daily_drop_pct = np.linspace(0.5, 3.0, decline_days) / 100.0
    decline_closes = [stable_closes[-1]]
    for i, d in enumerate(daily_drop_pct):
        step = (1 + 0.003) if (i + 1) % 5 == 0 else (1 - d)
        decline_closes.append(decline_closes[-1] * step)
    decline_closes = np.array(decline_closes[1:])
    closes = np.concatenate([stable_closes, decline_closes])

    n_total = len(closes)
    opens = np.concatenate([[closes[0]], closes[:-1]])
    # مدى التذبذب (High-Low) بيتسع تدريجياً خلال فترة الهبوط بس (ATR صاعد) -
    # بحد أقصى معقول (3.5%) عشان ميشوهش قياس المسافة من قاع 52 أسبوع
    pad = np.full(n_total, 0.004)
    pad[stable_days:] = np.linspace(0.008, 0.035, decline_days)
    highs = np.maximum(opens, closes) * (1 + pad)
    lows = np.minimum(opens, closes) * (1 - pad)

    down_mask = closes < opens
    vol_pattern = np.where(down_mask, 3_000_000, 500_000).astype(float)

    idx = pd.bdate_range("2023-01-02", periods=n_total)
    df = pd.DataFrame({"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": vol_pattern}, index=idx)
    return ec.calculate_indicators(df)


# ═══════════════════════════════════════════════════════════════════════
# 1) test_daily_return_calculation
# ═══════════════════════════════════════════════════════════════════════
def test_daily_return_calculation():
    closes = [100.0] * 25 + [110.0]  # +10% آخر يوم
    df = make_df(closes)
    result = pbe.compute_price_change_magnitude(df)
    _check("test_daily_return_calculation", result["daily_%"] is not None and abs(result["daily_%"] - 10.0) < 0.05,
           f"got {result['daily_%']}")


# ═══════════════════════════════════════════════════════════════════════
# 2) test_atr_normalized_move
# ═══════════════════════════════════════════════════════════════════════
def test_atr_normalized_move():
    df = flat_low_volatility_df(n=60, noise=0.002, seed=10)
    df.loc[df.index[-1], "Close"] = float(df["Close"].iloc[-2]) * 1.20  # حركة يوم واحد ضخمة (+20%)
    df = ec.calculate_indicators(df.drop(columns=[c for c in df.columns if c not in ["Open", "High", "Low", "Close", "Volume"]]))
    result = pbe.compute_price_change_magnitude(df)
    _check(
        "test_atr_normalized_move",
        result["return_to_atr_ratio"] is not None and result["return_to_atr_ratio"] > 2.0,
        f"got ratio={result['return_to_atr_ratio']} atr%={result['atr_%']}",
    )


# ═══════════════════════════════════════════════════════════════════════
# 3-4) price stability: low vs high volatility
# ═══════════════════════════════════════════════════════════════════════
def test_price_stability_with_low_volatility():
    df = flat_low_volatility_df(n=120, noise=0.001, seed=11)
    result = pbe.compute_price_stability(df)
    _check(
        "test_price_stability_with_low_volatility",
        result["price_stability_status"] in ("STABLE", "IMPROVING"),
        f"got {result['price_stability_status']} std={result['rolling_std_return_%']}",
    )


def test_price_stability_with_high_volatility():
    df = high_volatility_df(n=120, noise=0.06, seed=12)
    result = pbe.compute_price_stability(df)
    _check(
        "test_price_stability_with_high_volatility",
        result["price_stability_status"] == "HIGH_VOLATILITY",
        f"got {result['price_stability_status']} std={result['rolling_std_return_%']}",
    )


# ═══════════════════════════════════════════════════════════════════════
# 5-6) lower lows / lower highs detection
# ═══════════════════════════════════════════════════════════════════════
def test_lower_lows_detection():
    df = steady_downtrend_df(n=120, daily_pct=-0.6, noise=0.001, seed=13)
    result = pbe.compute_price_stability(df)
    _check("test_lower_lows_detection", result["lower_lows_count"] is not None and result["lower_lows_count"] > 10,
           f"got {result['lower_lows_count']}")

    trend = pbe.compute_trend_continuation_risk(df)
    _check("test_lower_lows_detection_trend_factor", trend["factors"].get("lower_lows_streak", 0) >= 3,
           f"streak={trend['factors'].get('lower_lows_streak')}")


def test_lower_highs_detection():
    df = steady_downtrend_df(n=120, daily_pct=-0.6, noise=0.001, seed=14)
    result = pbe.compute_price_stability(df)
    _check("test_lower_highs_detection", result["lower_highs_count"] is not None and result["lower_highs_count"] > 10,
           f"got {result['lower_highs_count']}")


# ═══════════════════════════════════════════════════════════════════════
# 7) consecutive down days
# ═══════════════════════════════════════════════════════════════════════
def test_consecutive_down_days():
    closes = [100 - i for i in range(10)]  # 10 أيام هابطة متتالية بالظبط
    df = make_df(closes)
    result = pbe.compute_price_change_magnitude(df)
    _check("test_consecutive_down_days", result["consecutive_down_days"] == 9,
           f"got {result['consecutive_down_days']} (متوقع 9 - أول يوم مفيش سابق ليه)")


# ═══════════════════════════════════════════════════════════════════════
# 8) high volume down day context
# ═══════════════════════════════════════════════════════════════════════
def test_high_volume_down_day_context():
    df = bottom_trap_high_risk_df(n=120, seed=15)
    trend = pbe.compute_trend_continuation_risk(df)
    _check("test_high_volume_down_day_context", trend["factors"].get("higher_volume_on_down_days") is True,
           f"got {trend['factors'].get('higher_volume_on_down_days')}")


# ═══════════════════════════════════════════════════════════════════════
# 9-10) RSI منخفض / قرب قاع 52 أسبوع لوحدهم مش كافيين لـBUY
# ═══════════════════════════════════════════════════════════════════════
def test_rsi_low_does_not_trigger_buy():
    df = bottom_trap_high_risk_df(n=280, seed=16)  # RSI هيبقى منخفض جداً هنا
    last_rsi = float(df["RSI_14"].iloc[-1])
    context = pbe.build_price_behavior_context(df)
    _check(
        "test_rsi_low_does_not_trigger_buy",
        last_rsi < 35
        and context["bottom_confirmation"]["confirmed_signal"] is False
        and context["bottom_trap"]["bottom_status"] not in ("CONFIRMED", "CONFIRMED_ONLY_AFTER_VALIDATION"),
        f"rsi={last_rsi} confirmed_signal={context['bottom_confirmation']['confirmed_signal']} "
        f"bottom_status={context['bottom_trap']['bottom_status']}",
    )


def test_near_52_week_low_does_not_trigger_buy():
    df = bottom_trap_high_risk_df(n=280, seed=17)
    dist_low = float(df["Dist_From_52W_Low_%"].iloc[-1])
    context = pbe.build_price_behavior_context(df)
    _check(
        "test_near_52_week_low_does_not_trigger_buy",
        dist_low <= 5 and context["bottom_trap"]["bottom_status"] != "CONFIRMED"
        and context["bottom_confirmation"]["confirmed_signal"] is False,
        f"dist_low_52w={dist_low} bottom_status={context['bottom_trap']['bottom_status']}",
    )


# ═══════════════════════════════════════════════════════════════════════
# 11-12) bottom trap high risk / possible base
# ═══════════════════════════════════════════════════════════════════════
def test_bottom_trap_high_risk_case():
    df = bottom_trap_high_risk_df(n=280, seed=18)
    context = pbe.build_price_behavior_context(df)
    _check(
        "test_bottom_trap_high_risk_case",
        context["bottom_trap"]["falling_knife_risk"] == "HIGH"
        and context["bottom_trap"]["bottom_status"] == "UNCONFIRMED",
        f"got falling_knife_risk={context['bottom_trap']['falling_knife_risk']} "
        f"bottom_status={context['bottom_trap']['bottom_status']}",
    )


def test_possible_base_case():
    df = stabilizing_after_decline_df(n=280, seed=19)
    context = pbe.build_price_behavior_context(df)
    _check(
        "test_possible_base_case",
        context["bottom_trap"]["bottom_status"] in ("POSSIBLE_BASE", "BASE_FORMING"),
        f"got bottom_status={context['bottom_trap']['bottom_status']} "
        f"stability={context['price_stability']['price_stability_status']} "
        f"trend_risk={context['trend_continuation_risk']['trend_continuation_risk']}",
    )


# ═══════════════════════════════════════════════════════════════════════
# 13) missing history returns UNKNOWN
# ═══════════════════════════════════════════════════════════════════════
def test_missing_history_returns_unknown():
    df = flat_low_volatility_df(n=10, seed=20)  # أقل بكتير من MIN_HISTORY_FOR_TREND
    context = pbe.build_price_behavior_context(df)
    _check(
        "test_missing_history_returns_unknown",
        context["trend_continuation_risk"]["trend_continuation_risk"] == pbe.UNKNOWN
        and context["bottom_trap"]["bottom_status"] == pbe.UNKNOWN
        and context["price_stability"]["price_stability_status"] == pbe.UNKNOWN,
        f"got {context['trend_continuation_risk']} / {context['bottom_trap']} / {context['price_stability']['price_stability_status']}",
    )


# ═══════════════════════════════════════════════════════════════════════
# 14) missing volume is not treated as zero
# ═══════════════════════════════════════════════════════════════════════
def test_missing_volume_is_not_zero():
    df = steady_downtrend_df(n=120, seed=21)
    df["Volume"] = np.nan  # فوليوم غائب تماماً
    df = ec.calculate_indicators(df[["Open", "High", "Low", "Close", "Volume"]])
    trend = pbe.compute_trend_continuation_risk(df)
    _check(
        "test_missing_volume_is_not_zero",
        trend["factors"].get("higher_volume_on_down_days") is None,
        f"got {trend['factors'].get('higher_volume_on_down_days')} (لازم يبقى None مش False)",
    )


# ═══════════════════════════════════════════════════════════════════════
# 15) historical/price-behavior adjustment disabled by default
# ═══════════════════════════════════════════════════════════════════════
def test_historical_adjustment_disabled_by_default():
    checks = [
        pbe.ENABLE_PRICE_BEHAVIOR_SCORE_ADJUSTMENT is False,
        pbe.price_behavior_adjustment == 0,
        pbe.bottom_trap_adjustment == 0,
        pbe.historical_price_behavior_adjustment == 0,
        pbe.apply_price_behavior_adjustment(72.5, {"price_behavior_adjustment": 999}) == 72.5,
    ]
    _check("test_historical_adjustment_disabled_by_default", all(checks), f"{checks}")


# ═══════════════════════════════════════════════════════════════════════
# 16) price behavior context never triggers BUY directly
# ═══════════════════════════════════════════════════════════════════════
def test_price_behavior_does_not_directly_trigger_buy():
    df = stabilizing_after_decline_df(n=280, seed=22)
    context = pbe.build_price_behavior_context(df)
    card = pbe.format_decision_card_addition(context)
    # الديسيجن كارد بتاع الفيتشر ده ممنوع يستخدم لغة توصية شراء مباشرة
    # ("🟢 BUY CANDIDATE" هي اللغة الوحيدة المعتمدة فعلياً في eagle_core.make_final_decision)
    _check(
        "test_price_behavior_does_not_directly_trigger_buy",
        context["bottom_confirmation"]["confirmed_signal"] is False
        and "BUY CANDIDATE" not in card["decision"]
        and "🟢" not in card["decision"]
        and context["enable_price_behavior_score_adjustment"] is False,
        f"{context['bottom_confirmation']} / decision={card['decision']}",
    )


# ═══════════════════════════════════════════════════════════════════════
# 17-18) Point-in-Time / No-Lookahead
# ═══════════════════════════════════════════════════════════════════════
def test_no_lookahead():
    """
    بناء سلسلة كاملة، ثم مقارنة السياق المحسوب على قطع مختلف الطول عند
    نفس نقطة T (T=150) - يجب أن تكون النتيجة متطابقة تماماً بغض النظر عن
    وجود بيانات بعد T من عدمه، لأن كل الحسابات backward-only.
    """
    full_closes = (steady_downtrend_df(n=250, seed=23)["Close"]).tolist()
    df_full = make_df(full_closes, seed=23)

    T = 150
    df_short_future = make_df(full_closes[: T + 1], seed=23)          # بيانات لحد T بالظبط، مفيش حاجة بعدها
    df_long_future_truncated_at_T = df_full.iloc[: T + 1]              # نفس المؤشرات لكن من دي فريم أطول قبل القطع

    ctx_short = pbe.build_price_behavior_context(df_short_future)
    ctx_long_truncated = pbe.build_price_behavior_context(df_long_future_truncated_at_T)

    same_stability = ctx_short["price_stability"]["price_stability_status"] == ctx_long_truncated["price_stability"]["price_stability_status"]
    same_trend = ctx_short["trend_continuation_risk"]["trend_continuation_risk"] == ctx_long_truncated["trend_continuation_risk"]["trend_continuation_risk"]
    same_bottom = ctx_short["bottom_trap"]["bottom_status"] == ctx_long_truncated["bottom_trap"]["bottom_status"]
    same_magnitude = ctx_short["price_change_magnitude"]["daily_%"] == ctx_long_truncated["price_change_magnitude"]["daily_%"]

    _check(
        "test_no_lookahead",
        same_stability and same_trend and same_bottom and same_magnitude,
        f"stability {ctx_short['price_stability']['price_stability_status']} vs {ctx_long_truncated['price_stability']['price_stability_status']} | "
        f"trend {ctx_short['trend_continuation_risk']['trend_continuation_risk']} vs {ctx_long_truncated['trend_continuation_risk']['trend_continuation_risk']} | "
        f"bottom {ctx_short['bottom_trap']['bottom_status']} vs {ctx_long_truncated['bottom_trap']['bottom_status']}",
    )


def test_point_in_time_bottom_trap_features():
    """نفس فكرة test_no_lookahead بس مركّز على BottomTrapDetector تحديداً + فحص ثابت: صفر shift(-N)/center=True في كود المحرك."""
    import inspect
    source = inspect.getsource(pbe)
    no_shift_negative = "shift(-" not in source
    no_center_true = "center=True" not in source and "center = True" not in source

    full_closes = (bottom_trap_high_risk_df(n=260, seed=24)["Close"]).tolist()
    df_full = make_df(full_closes, seed=24)
    T = 200
    df_upto_t = make_df(full_closes[: T + 1], seed=24)
    df_full_truncated = df_full.iloc[: T + 1]

    r1 = pbe.compute_bottom_trap_status(
        df_upto_t,
        pbe.compute_price_change_magnitude(df_upto_t),
        pbe.compute_price_stability(df_upto_t),
        pbe.compute_trend_continuation_risk(df_upto_t),
    )
    r2 = pbe.compute_bottom_trap_status(
        df_full_truncated,
        pbe.compute_price_change_magnitude(df_full_truncated),
        pbe.compute_price_stability(df_full_truncated),
        pbe.compute_trend_continuation_risk(df_full_truncated),
    )

    _check(
        "test_point_in_time_bottom_trap_features",
        no_shift_negative and no_center_true and r1["bottom_status"] == r2["bottom_status"]
        and r1["falling_knife_risk"] == r2["falling_knife_risk"],
        f"no_shift={no_shift_negative} no_center={no_center_true} r1={r1} r2={r2}",
    )


# ═══════════════════════════════════════════════════════════════════════
# فحص ثابت إضافي: مفيش منطق Eagle Score مكرر جوه price_behavior_engine.py
# (نفس فكرة test_identity_final_bot_uses_eagle_core_directly)
# ═══════════════════════════════════════════════════════════════════════
def test_no_duplicate_scoring_logic_in_price_behavior_engine():
    with open("price_behavior_engine.py", encoding="utf-8") as f:
        source = f.read()
    protected_names = [
        "def calculate_indicators", "def find_support_resistance",
        "def compute_eagle_score", "def make_final_decision",
        "def detect_signal_conflicts", "def compute_data_confidence",
    ]
    duplicates = [n for n in protected_names if source.count(n) > 0]
    _check("test_no_duplicate_scoring_logic_in_price_behavior_engine", not duplicates, f"duplicates={duplicates}")


# ═══════════════════════════════════════════════════════════════════════
# 19) production/backtest consistency (يعيد استخدام الاختبار الموجود فعلاً)
# ═══════════════════════════════════════════════════════════════════════
def test_production_backtest_score_consistency_reused():
    import test_production_backtest_score_consistency as tpbsc
    try:
        tpbsc.test_identity_final_bot_uses_eagle_core_directly()
        tpbsc.test_backtest_engine_uses_eagle_core_directly()
        try:
            tpbsc.test_production_backtest_score_consistency()
            _check("test_production_backtest_score_consistency_reused", True)
        except ModuleNotFoundError as e:
            print(f"⚠️ SKIPPED (جزء منه فقط - محتاج streamlit): {e}")
            PASS.append("test_production_backtest_score_consistency_reused (partial - static checks only)")
    except AssertionError as e:
        _check("test_production_backtest_score_consistency_reused", False, str(e))


# ═══════════════════════════════════════════════════════════════════════
# 20) Regression - تشغيل اختبارات المراحل السابقة
# ═══════════════════════════════════════════════════════════════════════
def run_all_previous_phase_regression_tests():
    """يشغّل test_egx_historical_analyzer__1_.py (قسم 20، بند 40) - فايل مستقل بالكامل، مفيهوش streamlit."""
    result = subprocess.run(
        [sys.executable, "test_egx_historical_analyzer__1_.py"],
        capture_output=True, text=True, cwd=".",
    )
    ok = result.returncode == 0
    _check("run_all_previous_phase_regression_tests (egx_historical_analyzer)", ok,
           result.stdout[-2000:] + result.stderr[-2000:] if not ok else "")
    if ok:
        print("   (تفاصيل egx_historical_analyzer regression مخفية للاختصار - PASS)")


if __name__ == "__main__":
    tests = [
        test_daily_return_calculation,
        test_atr_normalized_move,
        test_price_stability_with_low_volatility,
        test_price_stability_with_high_volatility,
        test_lower_lows_detection,
        test_lower_highs_detection,
        test_consecutive_down_days,
        test_high_volume_down_day_context,
        test_rsi_low_does_not_trigger_buy,
        test_near_52_week_low_does_not_trigger_buy,
        test_bottom_trap_high_risk_case,
        test_possible_base_case,
        test_missing_history_returns_unknown,
        test_missing_volume_is_not_zero,
        test_historical_adjustment_disabled_by_default,
        test_price_behavior_does_not_directly_trigger_buy,
        test_no_lookahead,
        test_point_in_time_bottom_trap_features,
        test_no_duplicate_scoring_logic_in_price_behavior_engine,
        test_production_backtest_score_consistency_reused,
        run_all_previous_phase_regression_tests,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            FAIL.append(t.__name__)
            print(f"❌ {t.__name__} — EXCEPTION: {e}")

    print(f"\n=== النتيجة: {len(PASS)} PASS / {len(FAIL)} FAIL (من إجمالي {len(tests)}) ===")
    if FAIL:
        print("فشلت:", FAIL)
        sys.exit(1)
