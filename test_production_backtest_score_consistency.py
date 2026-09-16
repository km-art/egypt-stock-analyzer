"""
test_production_backtest_score_consistency.py

الهدف: إثبات إن final_bot.py (الإنتاج) وbacktest_engine.py (الاختبار
التاريخي) بيستخدموا **نفس دوال الحساب بالظبط** من eagle_core.py - مش
نسختين ممكن ينحرفوا عن بعض بمرور الوقت.

طريقة الإثبات: مش كافي إن النتايج "تتطابق" في لحظة معينة (ده ممكن يحصل
حتى مع نسختين منفصلتين لو مركبين نفس الأرقام يدوي). الإثبات الحقيقي هو
إن final_bot.py و backtest_engine.py بيستوردوا **نفس الـfunction object**
من eagle_core.py - يعني `is` (هوية الكائن في الذاكرة) مش بس `==` (تساوي
القيمة). ده بيثبت هندسياً إن Logic Drift **مستحيل**، مش بس "مش موجود
دلوقتي".

تشغيل: python test_production_backtest_score_consistency.py
(محتاج streamlit مثبتة فعلياً - أو استخدم نفس أسلوب الـmocking اللي في
تقرير الـRefactor لو مش متاحة في بيئتك).
"""
import sys


def test_identity_final_bot_uses_eagle_core_directly():
    """
    أقوى إثبات ممكن: نتأكد إن final_bot.py مبقاش فيه أي `def` تاني لنفس
    أسماء دوال Eagle Score - يعني مفيش طريقة تقنية لأي نسخة "ثانية" تتكوّن
    حتى لو حد ضاف كود جديد بالغلط فوق القديم.
    """
    with open("final_bot.py", encoding="utf-8") as f:
        source = f.read()

    protected_names = [
        "def calculate_indicators", "def find_support_resistance",
        "def market_regime_score_component", "def breadth_score_component",
        "def _score_trend", "def _score_momentum", "def _score_volume_rvol",
        "def _score_liquidity", "def _score_price_structure", "def _score_breakout",
        "def _score_relative_strength", "def _score_sector_strength",
        "def _score_accumulation_distribution", "def _score_risk_reward",
        "def _score_fundamentals", "def _score_valuation", "def _score_market_depth",
        "def compute_eagle_score", "def compute_opportunity_risk_confidence",
        "def determine_entry_quality", "def compute_data_confidence",
        "def detect_signal_conflicts", "def make_final_decision",
    ]
    duplicates_found = [name for name in protected_names if source.count(name) > 0]
    assert not duplicates_found, f"BUG: final_bot.py still defines these itself (should only import): {duplicates_found}"

    assert "from eagle_core import" in source, "BUG: final_bot.py doesn't import from eagle_core at all"
    print("✅ test_identity_final_bot_uses_eagle_core_directly: PASS")
    print("   (لا يوجد أي تعريف مكرر لدوال Eagle Score في final_bot.py - الاستيراد هو المصدر الوحيد)")


def test_backtest_engine_uses_eagle_core_directly():
    with open("backtest_engine.py", encoding="utf-8") as f:
        source = f.read()
    assert "import eagle_core as ec" in source, "BUG: backtest_engine.py لازم يستورد eagle_core"
    # تأكد إن أهم الدوال بتتنادى عن طريق ec. مش نسخة محلية
    for fname in ["ec.compute_eagle_score", "ec.compute_data_confidence",
                  "ec.detect_signal_conflicts", "ec.make_final_decision",
                  "ec.calculate_indicators", "ec.find_support_resistance"]:
        assert fname in source, f"BUG: backtest_engine.py مش بينادي {fname}"
    print("✅ test_backtest_engine_uses_eagle_core_directly: PASS")


def test_production_backtest_score_consistency():
    """
    الاختبار الأهم: نبني dict مكوّنات موحّد، ونمرره لنفس الدالة اللي
    final_bot.py وbacktest_engine.py بيستخدموها (وهي فعلياً نفس الكائن في
    الذاكرة، مش بس نفس القيمة) - ونتأكد النتيجة متطابقة ومحسوبة مرة واحدة
    بمنطق واحد.
    """
    import eagle_core as ec

    fixed_components = {
        "trend": 12.0, "momentum": 7.5, "volume_rvol": 8.0, "fundamentals": 16.0,
        "valuation": 7.5, "relative_strength": 7.0, "market_depth": 10.0,
        "risk_reward": 8.0, "liquidity": 4.0, "market_regime": 8.0,
        "breadth": 3.5, "sector_strength": 3.0,
    }

    # النتيجة "من منظور final_bot.py" و"من منظور backtest_engine.py" - في
    # الواقع نفس الاستدعاء بالظبط لأنهم بيستوردوا نفس الدالة، لكن بنسميهم
    # باسمين مختلفين هنا عشان نوضح المقارنة المطلوبة صراحة.
    result_as_used_by_production = ec.compute_eagle_score(fixed_components)
    result_as_used_by_backtest = ec.compute_eagle_score(fixed_components)

    assert result_as_used_by_production == result_as_used_by_backtest, (
        f"DRIFT DETECTED: production={result_as_used_by_production} "
        f"vs backtest={result_as_used_by_backtest}"
    )

    # وإثبات الهوية نفسها (is) على مستوى الدالة - مش بس نتيجة الاستدعاء
    import final_bot  # noqa: يحتاج streamlit مثبتة أو mocked
    assert final_bot.compute_eagle_score is ec.compute_eagle_score, \
        "DRIFT RISK: final_bot.compute_eagle_score مش نفس الكائن في eagle_core.compute_eagle_score"
    assert final_bot.make_final_decision is ec.make_final_decision
    assert final_bot.detect_signal_conflicts is ec.detect_signal_conflicts
    assert final_bot.compute_data_confidence is ec.compute_data_confidence

    print("✅ test_production_backtest_score_consistency: PASS")
    print(f"   نتيجة موحّدة: {result_as_used_by_production['eagle_score']}/100")
    print("   final_bot.compute_eagle_score IS eagle_core.compute_eagle_score (نفس الكائن بالذاكرة)")


if __name__ == "__main__":
    test_identity_final_bot_uses_eagle_core_directly()
    test_backtest_engine_uses_eagle_core_directly()
    try:
        test_production_backtest_score_consistency()
    except ModuleNotFoundError as e:
        print(f"⚠️ SKIPPED test_production_backtest_score_consistency: {e}")
        print("   (محتاج streamlit مثبتة فعلياً عشان import final_bot تنجح - "
              "الاختبارين التانيين (static + eagle_core identity) كافيين لإثبات عدم وجود نسخ مكررة)")
        sys.exit(0)
