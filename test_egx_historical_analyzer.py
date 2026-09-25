"""
test_egx_historical_analyzer.py
=================================
اختبارات ميكانيكية (MECHANICAL VALIDATION ONLY) - قسم 28 من مواصفة Phase 1.7.

⚠️ البيانات هنا كلها Synthetic (مصطنعة رياضياً) - بتثبت إن الحسابات والمنطق
صحيحين تقنياً، **مش** إنهم بيمثلوا سلوك السوق المصري الحقيقي. النتائج دي
ممنوع تُعرض كـ "Historical Market Results" أو "Trading Performance" -
القسم 28 نص على كده صراحة.

للتحقق من البيانات الحقيقية (^CASE30 الفعلية من Yahoo)، لازم تشغيل
egx_historical_analyzer.load_benchmark_history() على بيئة متصلة بالإنترنت -
مش ممكن هنا.
"""

import numpy as np
import pandas as pd

import egx_historical_analyzer as eha


def make_synthetic_ohlcv(n_days=800, seed=42, with_crash=False):
    """
    يبني DataFrame بصيغة OHLCV زي اللي yfinance بيرجعها بالظبط، لكن بأرقام
    مصطنعة عشوائياً - مفيش أي ادعاء إنها بتمثل EGX30 الحقيقي.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2021-01-01", periods=n_days)
    returns = rng.normal(0.0003, 0.012, n_days)

    if with_crash:
        # نحقن هبوط متتالي مصطنع في نص السلسلة عشان نختبر consecutive_days
        # وregime classification فعلياً بيرصدوا الحالة دي صح
        crash_start = n_days // 2
        returns[crash_start:crash_start + 6] = [-0.03, -0.025, -0.02, -0.018, -0.015, -0.01]

    price = 100 * np.cumprod(1 + returns)
    df = pd.DataFrame({
        "Open": price * 0.998, "High": price * 1.005, "Low": price * 0.995,
        "Close": price, "Volume": rng.integers(1_000_000, 5_000_000, n_days),
    }, index=dates)
    return df


# ═══════════════════════════════════════════════════════════════════════
# 1) test_no_lookahead - أهم اختبار في المواصفة كلها
# ═══════════════════════════════════════════════════════════════════════
def test_no_lookahead():
    """
    بيتأكد إن classify_regime_at(T) بيديله نفس النتيجة بالظبط لو قصينا
    البيانات عند T+50 يوم أو سيبناها كاملة - يعني مفيش تسريب لبيانات
    مستقبلية داخل في الحساب.
    """
    df = make_synthetic_ohlcv(n_days=800, with_crash=True)
    features_full = eha.prepare_daily_features(df)

    as_of_index = 500
    result_full = eha.classify_regime_at(features_full, as_of_index)

    # نقص البيانات لحد as_of_index + 50 يوم بس، ونعيد نفس الحساب
    truncated_df = df.iloc[:as_of_index + 51]
    features_truncated = eha.prepare_daily_features(truncated_df)
    result_truncated = eha.classify_regime_at(features_truncated, as_of_index)

    assert result_full["regime"] == result_truncated["regime"], (
        f"❌ تسريب بيانات مستقبلية! النتيجة اختلفت لما قصينا البيانات: "
        f"{result_full['regime']} != {result_truncated['regime']}"
    )
    assert result_full["ret_20d_%"] == result_truncated["ret_20d_%"]
    print("✅ test_no_lookahead: نجح - نفس النتيجة سواء البيانات كاملة أو مقصوصة بعد T")


# ═══════════════════════════════════════════════════════════════════════
# 2) test_point_in_time_historical_features
# ═══════════════════════════════════════════════════════════════════════
def test_point_in_time_historical_features():
    """محرك التشابه لازم يرفض يستخدم أي يوم بعد as_of_index في الترشيح."""
    df = make_synthetic_ohlcv(n_days=800)
    features_df = eha.prepare_daily_features(df)
    fwd_df = eha.compute_forward_returns(features_df)

    as_of_index = 400
    result = eha.find_similar_historical_days(features_df, fwd_df, as_of_index)

    # لازم نتأكد يدوياً إن candidates متولدتش غير من range(20, as_of_index)
    # - بنعمل ده بفحص الكود مباشرة بدل ما نثق في النتيجة بس
    import inspect
    source = inspect.getsource(eha.find_similar_historical_days)
    assert "range(20, as_of_index)" in source, "❌ نطاق البحث في الكود اتغيّر - راجع الدالة"
    print("✅ test_point_in_time_historical_features: نجح - نطاق الترشيح محصور قبل as_of_index")


# ═══════════════════════════════════════════════════════════════════════
# 3) test_forward_returns_excluded_from_features
# ═══════════════════════════════════════════════════════════════════════
def test_forward_returns_excluded_from_features():
    """عمود fwd_return_*d مينفعش يظهر في features_df (بس في fwd_df المنفصل)."""
    df = make_synthetic_ohlcv(n_days=200)
    features_df = eha.prepare_daily_features(df)
    fwd_cols = [c for c in features_df.columns if c.startswith("fwd_return")]
    assert len(fwd_cols) == 0, f"❌ لقينا أعمدة forward return جوه features_df: {fwd_cols}"
    print("✅ test_forward_returns_excluded_from_features: نجح")


# ═══════════════════════════════════════════════════════════════════════
# 4) test_day_of_week_statistics
# ═══════════════════════════════════════════════════════════════════════
def test_day_of_week_statistics():
    df = make_synthetic_ohlcv(n_days=800)
    features_df = eha.prepare_daily_features(df)
    result = eha.analyze_day_of_week(features_df)

    assert set(result.keys()) == {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}
    for day, stats in result.items():
        if stats["status"] == "OK":
            total_prob = stats["up_probability_%"] + stats["down_probability_%"]
            assert 0 <= total_prob <= 100.1, f"❌ نسب {day} غير منطقية: {total_prob}"
    print("✅ test_day_of_week_statistics: نجح")


# ═══════════════════════════════════════════════════════════════════════
# 5) test_monthly_statistics
# ═══════════════════════════════════════════════════════════════════════
def test_monthly_statistics():
    df = make_synthetic_ohlcv(n_days=800)
    features_df = eha.prepare_daily_features(df)
    result = eha.analyze_monthly_seasonality(features_df)
    assert len(result) == 12
    for month, stats in result.items():
        if stats["status"] == "OK":
            assert stats["up_years"] + stats["down_years"] == stats["years_analyzed"]
    print("✅ test_monthly_statistics: نجح")


# ═══════════════════════════════════════════════════════════════════════
# 6) test_consecutive_down_days
# ═══════════════════════════════════════════════════════════════════════
def test_consecutive_down_days():
    """بعد سلسلة هبوط مصطنعة، لازم down_streak يوصل فعلاً لرقم منطقي."""
    df = make_synthetic_ohlcv(n_days=800, with_crash=True)
    features_df = eha.prepare_daily_features(df)
    fwd_df = eha.compute_forward_returns(features_df)

    max_streak_seen = features_df["down_streak"].max()
    assert max_streak_seen >= 3, f"❌ الهبوط المصطنع المفروض يولّد streak >=3، طلع {max_streak_seen}"

    result = eha.analyze_consecutive_days(fwd_df, max_streak=5)
    assert "down" in result and "up" in result
    print(f"✅ test_consecutive_down_days: نجح (أقصى streak هبوط اتسجل = {max_streak_seen})")


# ═══════════════════════════════════════════════════════════════════════
# 7) test_large_down_move_statistics
# ═══════════════════════════════════════════════════════════════════════
def test_large_down_move_statistics():
    df = make_synthetic_ohlcv(n_days=800, with_crash=True)
    features_df = eha.prepare_daily_features(df)
    fwd_df = eha.compute_forward_returns(features_df)
    result = eha.analyze_large_moves(fwd_df, thresholds=(1, 2))
    assert "down_moves" in result and "up_moves" in result
    # نتأكد إن الهبوط المصطنع (-3%, -2.5%...) فعلاً ظهر في bucket >=2%
    bucket = result["down_moves"].get("<=-2%", {})
    assert bucket.get("status") in ("OK", "LOW_SAMPLE")
    print("✅ test_large_down_move_statistics: نجح")


# ═══════════════════════════════════════════════════════════════════════
# 8) test_historical_similarity
# ═══════════════════════════════════════════════════════════════════════
def test_historical_similarity():
    df = make_synthetic_ohlcv(n_days=800)
    features_df = eha.prepare_daily_features(df)
    fwd_df = eha.compute_forward_returns(features_df)
    result = eha.find_similar_historical_days(features_df, fwd_df, as_of_index=700)
    assert result["status"] in ("OK", "LOW_SAMPLE", "UNAVAILABLE")
    if result["status"] == "OK":
        assert 0 <= result["similarity_%"] <= 100
    print("✅ test_historical_similarity: نجح")


# ═══════════════════════════════════════════════════════════════════════
# 9) test_low_sample_protection
# ═══════════════════════════════════════════════════════════════════════
def test_low_sample_protection():
    """عيّنة صغيرة جداً (30 يوم بس) لازم ترجع LOW_SAMPLE مش أرقام وهمية."""
    df = make_synthetic_ohlcv(n_days=30)
    features_df = eha.prepare_daily_features(df)
    result = eha.analyze_day_of_week(features_df)
    statuses = {stats["status"] for stats in result.values()}
    assert "LOW_SAMPLE" in statuses, "❌ عيّنة صغيرة كان المفروض تتعلّم عليها LOW_SAMPLE"
    print("✅ test_low_sample_protection: نجح")


# ═══════════════════════════════════════════════════════════════════════
# 10) test_missing_data_handling
# ═══════════════════════════════════════════════════════════════════════
def test_missing_data_handling():
    """لو yfinance مش متاح أو رجّع فاضي، لازم النتيجة UNAVAILABLE صراحة."""
    original_yf = eha.yf
    eha.yf = None
    try:
        result = eha.load_benchmark_history()
        assert result["status"] == eha.UNAVAILABLE
        assert result["sample_size"] == 0
    finally:
        eha.yf = original_yf
    print("✅ test_missing_data_handling: نجح")


# ═══════════════════════════════════════════════════════════════════════
# 11) test_historical_context_disabled_by_default
# ═══════════════════════════════════════════════════════════════════════
def test_historical_context_disabled_by_default():
    """historical_context_adjustment لازم يكون 0 دايماً في المرحلة دي."""
    import inspect
    source = inspect.getsource(eha.get_historical_context)
    assert "HISTORICAL_CONTEXT_ADJUSTMENT = 0" in source
    print("✅ test_historical_context_disabled_by_default: نجح")


# ═══════════════════════════════════════════════════════════════════════
# 12) test_historical_context_does_not_directly_trigger_buy
# ═══════════════════════════════════════════════════════════════════════
def test_historical_context_does_not_directly_trigger_buy():
    """
    بيتأكد إن مخرجات الموديول مفيهاش أي مفتاح اسمه "verdict" أو "decision"
    أو "buy"/"sell" - الموديول ده بيرجع سياق بس، مش قرار.
    """
    import inspect
    forbidden_keys = ["verdict", "decision", "buy_signal", "sell_signal"]
    source = inspect.getsource(eha)
    for key in forbidden_keys:
        assert f'"{key}"' not in source.lower() and f"'{key}'" not in source.lower(), (
            f"❌ لقينا مفتاح '{key}' جوه الموديول - المفروض الموديول ده معندوش قرارات"
        )
    print("✅ test_historical_context_does_not_directly_trigger_buy: نجح")


# ═══════════════════════════════════════════════════════════════════════
# 13 + 14) test_production_backtest_score_consistency /
#          test_same_timestamp_same_core_score
# ═══════════════════════════════════════════════════════════════════════
def test_production_backtest_score_consistency():
    """
    ⚠️ الاختبارين دول (13، 14) في المواصفة الأصلية بيفترضوا وجود
    eagle_core.py و backtest_engine.py منفصلين عن final_bot.py - والـ
    AUDIT أثبت إنهم مش موجودين. الموديول ده (egx_historical_analyzer)
    مستقل عن Eagle Score خالص ومفيهوش Eagle Score computation أصلاً،
    فمفيش حاجة "تتكرر" بين production وbacktest هنا تحديداً.

    الاختبار ده بيتأكد بس إن نفس الدالة (get_historical_context) بترجع
    نفس النتيجة بالظبط لما تتنادى مرتين بنفس المدخلات - أقرب حاجة ممكن
    نتحقق منها من غير eagle_core.py حقيقي.
    """
    df = make_synthetic_ohlcv(n_days=800)
    features_df = eha.prepare_daily_features(df)
    r1 = eha.classify_regime_at(features_df, 500)
    r2 = eha.classify_regime_at(features_df, 500)
    assert r1 == r2, "❌ نفس المدخلات ديها نتايج مختلفة - في randomness مش متوقع"
    print("✅ test_production_backtest_score_consistency: نجح (بمعنى determinism بس - "
          "مش eagle_core.py/backtest_engine.py لأنهم مش موجودين فعلياً)")


if __name__ == "__main__":
    tests = [
        test_no_lookahead,
        test_point_in_time_historical_features,
        test_forward_returns_excluded_from_features,
        test_day_of_week_statistics,
        test_monthly_statistics,
        test_consecutive_down_days,
        test_large_down_move_statistics,
        test_historical_similarity,
        test_low_sample_protection,
        test_missing_data_handling,
        test_historical_context_disabled_by_default,
        test_historical_context_does_not_directly_trigger_buy,
        test_production_backtest_score_consistency,
    ]

    passed, failed = 0, []
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            failed.append((test.__name__, str(e)))
            print(f"❌ {test.__name__}: فشل - {e}")
        except Exception as e:
            failed.append((test.__name__, f"خطأ غير متوقع: {e}"))
            print(f"💥 {test.__name__}: خطأ غير متوقع - {e}")

    print(f"\n{'='*60}")
    print(f"النتيجة: {passed}/{len(tests)} اختبار نجح")
    if failed:
        print(f"الفاشل: {[f[0] for f in failed]}")
    print(f"{'='*60}")
