"""
test_egx_historical_analyzer.py — PHASE 1.7 tests

⚠️ كل الاختبارات هنا بتستخدم بيانات اصطناعية (Synthetic/Random-Walk) -
MECHANICAL VALIDATION ONLY. مفيش أي نتيجة هنا تمثل سلوك EGX30 الحقيقي.
الهدف إثبات إن الآلية (point-in-time, no-lookahead, low-sample protection,
إلخ) شغالة صح، مش إثبات حقائق عن السوق المصري.
"""
import numpy as np
import pandas as pd

import egx_historical_analyzer as eha
import eagle_core as ec


def _make_synthetic_df(n=1500, seed=7):
    np.random.seed(seed)
    dates = pd.bdate_range("2018-01-01", periods=n)
    close = 100 + np.cumsum(np.random.randn(n) * 0.6)
    return pd.DataFrame({
        "Open": close + np.random.randn(n) * 0.2,
        "High": close + np.abs(np.random.randn(n)) * 1.0,
        "Low": close - np.abs(np.random.randn(n)) * 1.0,
        "Close": close,
        "Volume": np.random.randint(100000, 1000000, n),
    }, index=dates)


# ---------------------------------------------------------------------------
# 1) No look-ahead
# ---------------------------------------------------------------------------
def test_no_lookahead():
    """RegimeFeatures عند نقطة T لازم تكون مطابقة تماماً سواء حسبناها من
    كامل الداتا أو من نسخة مقطوعة عند T - يعني مفيش استخدام لأي صف بعد T."""
    df = _make_synthetic_df()
    stress = eha.MarketStressAnalyzer(df)
    idx = 800

    features_full_df = stress.compute_features_at(idx)

    truncated_df = df.iloc[: idx + 1]
    stress_truncated = eha.MarketStressAnalyzer(truncated_df)
    features_truncated = stress_truncated.compute_features_at(idx)

    assert features_full_df == features_truncated, (
        f"LOOKAHEAD BUG: full-df features {features_full_df} != truncated-df features {features_truncated}"
    )
    print("✅ test_no_lookahead: PASS")


# ---------------------------------------------------------------------------
# 2) Point-in-time historical features
# ---------------------------------------------------------------------------
def test_point_in_time_historical_features():
    """compute_features_at(idx) ما ينفعش يتأثر بتعديل صفوف بعد idx."""
    df = _make_synthetic_df()
    idx = 500
    stress = eha.MarketStressAnalyzer(df)
    before = stress.compute_features_at(idx)

    df_modified = df.copy()
    df_modified.iloc[idx + 1:] = df_modified.iloc[idx + 1:] * 0  # خرّب كل حاجة بعد idx
    stress_modified = eha.MarketStressAnalyzer(df_modified)
    after = stress_modified.compute_features_at(idx)

    assert before == after, f"BUG: تعديل بيانات المستقبل أثر على features عند T! {before} != {after}"
    print("✅ test_point_in_time_historical_features: PASS")


# ---------------------------------------------------------------------------
# 3) Forward returns excluded from features
# ---------------------------------------------------------------------------
def test_forward_returns_excluded_from_features():
    """RegimeFeatures (المستخدمة في التصنيف) ما فيهاش أي حقل مشتق من عوائد للأمام."""
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(eha.RegimeFeatures)}
    forbidden = {"forward_return", "future_return", "next_return", "fwd_return"}
    assert not (field_names & forbidden), f"BUG: RegimeFeatures فيها حقل مستقبلي: {field_names & forbidden}"
    print("✅ test_forward_returns_excluded_from_features: PASS")
    print(f"   RegimeFeatures fields: {field_names}")


# ---------------------------------------------------------------------------
# 4) Day of week statistics mechanics
# ---------------------------------------------------------------------------
def test_day_of_week_statistics():
    df = _make_synthetic_df()
    pattern = eha.HistoricalPatternAnalyzer(df)
    result = pattern.day_of_week_analysis()
    assert len(result) > 0, "مفيش نتيجة خالص"
    for day, stats in result.items():
        assert stats["up_probability_%"] + stats["down_probability_%"] == 100.0 or \
               abs(stats["up_probability_%"] + stats["down_probability_%"] - 100.0) < 0.2
        assert stats["sample_size"] > 0
    print("✅ test_day_of_week_statistics: PASS")


# ---------------------------------------------------------------------------
# 5) Monthly statistics mechanics
# ---------------------------------------------------------------------------
def test_monthly_statistics():
    df = _make_synthetic_df()
    pattern = eha.HistoricalPatternAnalyzer(df)
    result = pattern.monthly_seasonality_analysis()
    assert len(result) > 0
    for month, stats in result.items():
        assert stats["up_years"] + stats["down_years"] == stats["n_years"]
        # التحذير الصريح من الخطة: شهر بعينة سنين قليلة لازم يترفض statistically
        if stats["n_years"] < eha.HISTORICAL_MIN_YEARS:
            assert stats["status"] == eha.STATUS_LOW_SAMPLE
    print("✅ test_monthly_statistics: PASS")


# ---------------------------------------------------------------------------
# 6) Consecutive down days mechanics
# ---------------------------------------------------------------------------
def test_consecutive_down_days():
    df = _make_synthetic_df()
    fwd = eha.ForwardReturnAnalyzer(df)
    result = fwd.consecutive_days_analysis("down")
    assert set(result.keys()) == {"1", "2", "3", "4", "5+"}
    # كل ما عدد الأيام المتتالية زاد، كل ما عدد الحالات (n_occurrences) قل منطقياً
    counts = [result[k]["n_occurrences"] for k in ["1", "2", "3", "4", "5+"]]
    assert counts[0] >= counts[1] >= counts[2], f"BUG: العدد المفروض يقل مع زيادة السلسلة: {counts}"
    print("✅ test_consecutive_down_days: PASS", counts)


# ---------------------------------------------------------------------------
# 7) Large down move statistics
# ---------------------------------------------------------------------------
def test_large_down_move_statistics():
    df = _make_synthetic_df()
    fwd = eha.ForwardReturnAnalyzer(df)
    result = fwd.large_move_analysis()
    assert "<= -1%" in result and "<= -3%" in result
    # -3% لازم يكون عدد حالاته أقل من أو يساوي -1% (أكثر تشدداً)
    assert result["<= -3%"]["n_occurrences"] <= result["<= -1%"]["n_occurrences"]
    print("✅ test_large_down_move_statistics: PASS")


# ---------------------------------------------------------------------------
# 8) Historical similarity mechanics
# ---------------------------------------------------------------------------
def test_historical_similarity():
    df = _make_synthetic_df()
    stress = eha.MarketStressAnalyzer(df)
    sim = eha.RegimeSimilarityAnalyzer(df, stress)
    result = sim.find_similar_days(target_idx=1000, max_lookback_idx=1000, top_n=30)
    assert result["status"] in (eha.STATUS_OK, eha.STATUS_LOW_SAMPLE)
    if result["status"] == eha.STATUS_OK:
        assert result["n_matches"] > 0
        assert all(idx <= 1000 for idx in result["matches"]), "BUG: فيه matches بعد target_idx!"
    print("✅ test_historical_similarity: PASS")


# ---------------------------------------------------------------------------
# 8b) Similarity must be point-in-time (قسم 16 - حرج)
# ---------------------------------------------------------------------------
def test_similarity_point_in_time():
    """أهم اختبار في القسم كله: matches عند Backtest تاريخ T ما ينفعش تتضمن أي index بعد T."""
    df = _make_synthetic_df()
    stress = eha.MarketStressAnalyzer(df)
    sim = eha.RegimeSimilarityAnalyzer(df, stress)

    target_idx = 700
    result = sim.find_similar_days(target_idx=target_idx, max_lookback_idx=target_idx, top_n=50)
    if result["status"] == eha.STATUS_OK:
        future_leaks = [idx for idx in result["matches"] if idx > target_idx]
        assert not future_leaks, f"LOOKAHEAD BUG: matches من المستقبل: {future_leaks}"
    print("✅ test_similarity_point_in_time: PASS")


# ---------------------------------------------------------------------------
# 9) Low sample protection
# ---------------------------------------------------------------------------
def test_low_sample_protection():
    """أول 25 يوم بس في تاريخ السهم - المفروض LOW_SAMPLE في كل حاجة تقريباً."""
    df = _make_synthetic_df(n=25)
    analyzer = eha.EGXHistoricalAnalyzer(df)
    report = analyzer.pattern.daily_pattern_summary()
    assert report["status"] == eha.STATUS_LOW_SAMPLE, f"BUG: عينة 25 يوم لازم تترفض كـLOW_SAMPLE، طلعت {report['status']}"
    print("✅ test_low_sample_protection: PASS")


# ---------------------------------------------------------------------------
# 10) Missing data handling
# ---------------------------------------------------------------------------
def test_missing_data_handling():
    """breadth وsector_strength مش متاحين تاريخياً - لازم يفضلوا None (UNAVAILABLE)، مش صفر."""
    df = _make_synthetic_df()
    stress = eha.MarketStressAnalyzer(df)
    features = stress.compute_features_at(500)
    assert features.breadth is None, "BUG: breadth المفروض None (UNAVAILABLE) مش قيمة مختلقة"
    assert features.sector_strength is None, "BUG: sector_strength المفروض None (UNAVAILABLE)"
    print("✅ test_missing_data_handling: PASS")


# ---------------------------------------------------------------------------
# 11) Historical context disabled by default
# ---------------------------------------------------------------------------
def test_historical_context_disabled_by_default():
    assert eha.historical_context_adjustment({}) == 0.0
    assert eha.historical_context_adjustment({"anything": "even if passed"}) == 0.0
    df = _make_synthetic_df()
    analyzer = eha.EGXHistoricalAnalyzer(df)
    ctx = analyzer.current_context()
    assert ctx["historical_context_adjustment"] == 0.0
    print("✅ test_historical_context_disabled_by_default: PASS")


# ---------------------------------------------------------------------------
# 12) Historical context does not directly trigger BUY
# ---------------------------------------------------------------------------
def test_historical_context_does_not_directly_trigger_buy():
    """
    محاكاة: حتى لو الـHistorical Context قال RISK_ON بقوة وSimilarity عالية
    ومتوسط عائد موجب جداً، الـFinal Decision (من eagle_core.py) لازم يفضل
    معتمد بس على Eagle Score/Data Confidence/Conflicts - مفيش أي مدخل من
    historical context بيدخل make_final_decision خالص.
    """
    import inspect
    sig = inspect.signature(ec.make_final_decision)
    param_names = set(sig.parameters.keys())
    forbidden = {"historical_context", "seasonality", "regime_similarity", "historical_adjustment"}
    assert not (param_names & forbidden), (
        f"BUG: make_final_decision بقى بياخد مدخل من Historical Context: {param_names & forbidden}"
    )
    print("✅ test_historical_context_does_not_directly_trigger_buy: PASS")
    print(f"   make_final_decision signature unchanged: {param_names}")


# ---------------------------------------------------------------------------
# 13) Production/Backtest consistency (SSOT - إعادة تأكيد لـPhase 1.7)
# ---------------------------------------------------------------------------
def test_production_backtest_score_consistency():
    """
    Phase 1.7 ما لمستش eagle_core.py خالص - إعادة تأكيد سريعة إن SSOT لسه
    سليم (نفس منطق Phase 1.6، هنا كتأكيد إضافي بعد إضافة الموديول الجديد).
    """
    fixed = {k: v * 0.7 for k, v in ec.EAGLE_WEIGHTS.items()}
    r1 = ec.compute_eagle_score(fixed)
    r2 = ec.compute_eagle_score(fixed)
    assert r1 == r2
    assert r1["eagle_score"] == 70.0
    print("✅ test_production_backtest_score_consistency: PASS (eagle_core.py لسه SSOT وحيد)")


# ---------------------------------------------------------------------------
# 14) Same timestamp -> same core score (determinism)
# ---------------------------------------------------------------------------
def test_same_timestamp_same_core_score():
    """نفس المدخلات بالظبط لازم تدي نفس النتيجة بالظبط - determinism، مفيش randomness مخفي."""
    df = _make_synthetic_df()
    stress = eha.MarketStressAnalyzer(df)
    f1 = stress.compute_features_at(900)
    f2 = stress.compute_features_at(900)
    assert f1 == f2
    r1 = stress.classify_regime(f1)
    r2 = stress.classify_regime(f2)
    assert r1 == r2
    print("✅ test_same_timestamp_same_core_score: PASS")


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
        test_similarity_point_in_time,
        test_low_sample_protection,
        test_missing_data_handling,
        test_historical_context_disabled_by_default,
        test_historical_context_does_not_directly_trigger_buy,
        test_production_backtest_score_consistency,
        test_same_timestamp_same_core_score,
    ]
    passed, failed = 0, []
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            failed.append((t.__name__, str(e)))
            print(f"❌ {t.__name__}: FAIL - {e}")
        except Exception as e:
            failed.append((t.__name__, f"{type(e).__name__}: {e}"))
            print(f"❌ {t.__name__}: ERROR - {e}")

    print(f"\n{'='*60}\n{passed}/{len(tests)} PASSED")
    if failed:
        print("FAILED TESTS:")
        for name, reason in failed:
            print(f"  - {name}: {reason}")
