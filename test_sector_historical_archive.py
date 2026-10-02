"""
test_sector_historical_archive.py

⚠️ MECHANICAL VALIDATION ONLY: كل البيانات هنا Synthetic - الهدف إثبات إن
منطق بناء المؤشر القطاعي واكتشاف نوافذ الصعود/النزول صحيح رياضياً بس. مفيش
نتيجة هنا تدّعي إن القطاعات الحقيقية (طبي/عقاري/...) فعلاً بتتحرك بالنمط ده.

تشغيل: python test_sector_historical_archive.py
"""
import sys
import numpy as np
import pandas as pd

import sector_historical_archive as sha
import eagle_core as ec

FAILURES = []


def _check(name, condition, detail=""):
    if condition:
        print(f"✅ {name}: PASS")
    else:
        FAILURES.append(name)
        print(f"❌ {name}: FAIL {detail}")


def _make_ohlcv(closes, start="2022-01-01"):
    n = len(closes)
    idx = pd.bdate_range(start=start, periods=n)
    closes = np.array(closes, dtype=float)
    return pd.DataFrame({
        "Open": closes, "High": closes * 1.005, "Low": closes * 0.995,
        "Close": closes, "Volume": np.full(n, 1_000_000.0),
    }, index=idx)


def _engineered_sector_path(n=140, seed=0):
    """
    مسار سعري مصطنع: هبوط 25 جلسة → صعود قوي 30 جلسة (+40%) → هبوط تاني
    25 جلسة (-25%) → استقرار الباقي. عشان اختبار اكتشاف نافذة صعود ونافذة
    نزول واضحتين مع بعض.
    """
    rng = np.random.default_rng(seed)
    path = [100.0]
    # هبوط أولي
    for _ in range(25):
        path.append(path[-1] * (1 - 0.012 + rng.normal(0, 0.002)))
    # صعود قوي (+40% تقريباً)
    for _ in range(30):
        path.append(path[-1] * (1 + 0.011 + rng.normal(0, 0.002)))
    # نزول تاني (-25% تقريباً)
    for _ in range(25):
        path.append(path[-1] * (1 - 0.011 + rng.normal(0, 0.002)))
    # استقرار
    remaining = n - len(path)
    for _ in range(max(remaining, 0)):
        path.append(path[-1] * (1 + rng.normal(0, 0.002)))
    return path[:n]


def test_build_sector_index_basic():
    path1 = _engineered_sector_path(seed=1)
    path2 = [p * 1.02 for p in _engineered_sector_path(seed=2)]  # سهم تاني بمسار مشابه (نفس القطاع)
    frames = {"A": _make_ohlcv(path1), "B": _make_ohlcv(path2)}
    idx_df = sha.build_sector_index(frames)
    _check("test_build_sector_index_basic", idx_df is not None and len(idx_df) == len(path1),
           detail=f"len={len(idx_df) if idx_df is not None else None}")
    if idx_df is not None:
        _check("test_build_sector_index_normalized_to_100", abs(float(idx_df['Close'].iloc[0]) - 100.0) < 0.01,
               detail=str(idx_df['Close'].iloc[0]))


def test_build_sector_index_insufficient_members():
    frames = {"A": _make_ohlcv(_engineered_sector_path(seed=3))}  # سهم واحد بس - أقل من الحد الأدنى
    idx_df = sha.build_sector_index(frames)
    _check("test_build_sector_index_insufficient_members", idx_df is None, detail=str(idx_df))


def test_detect_rally_window_found():
    frames = {
        "A": _make_ohlcv(_engineered_sector_path(seed=10)),
        "B": _make_ohlcv([p * 0.98 for p in _engineered_sector_path(seed=11)]),
        "C": _make_ohlcv([p * 1.03 for p in _engineered_sector_path(seed=12)]),
    }
    result = sha.build_sector_archive(frames, sector_name="اختبار", market_label="اختبار")
    _check("test_detect_rally_window_found_available", result.get("available") is True, detail=str(result.get("reason")))
    if result.get("available"):
        up_windows = result["up_windows"]
        _check("test_detect_rally_window_found_nonempty", len(up_windows) >= 1, detail=str(up_windows))
        if up_windows:
            biggest = max(up_windows, key=lambda w: w["return_pct"])
            _check("test_detect_rally_window_return_positive", biggest["return_pct"] > 20,
                   detail=str(biggest["return_pct"]))
            _check("test_detect_rally_window_duration", biggest["duration_days"] >= 10,
                   detail=str(biggest["duration_days"]))


def test_detect_decline_window_found():
    frames = {
        "A": _make_ohlcv(_engineered_sector_path(seed=20)),
        "B": _make_ohlcv([p * 0.97 for p in _engineered_sector_path(seed=21)]),
    }
    result = sha.build_sector_archive(frames, sector_name="اختبار2", market_label="اختبار")
    if result.get("available"):
        down_windows = result["down_windows"]
        _check("test_detect_decline_window_found_nonempty", len(down_windows) >= 1, detail=str(down_windows))
        if down_windows:
            biggest = min(down_windows, key=lambda w: w["return_pct"])
            _check("test_detect_decline_window_return_negative", biggest["return_pct"] < -10,
                   detail=str(biggest["return_pct"]))


def test_ema_confirmation_present_for_strong_trend():
    frames = {
        "A": _make_ohlcv(_engineered_sector_path(seed=30)),
        "B": _make_ohlcv([p * 1.01 for p in _engineered_sector_path(seed=31)]),
    }
    result = sha.build_sector_archive(frames, sector_name="اختبار3", market_label="اختبار")
    if result.get("available") and result["up_windows"]:
        w = max(result["up_windows"], key=lambda x: x["return_pct"])
        _check(
            "test_ema_confirmation_present_for_strong_trend",
            w["ema_confirmation_ratio"] is not None and w["ema_confirmation_ratio"] > 0.5,
            detail=str(w),
        )
        _check(
            "test_strength_label_reflects_criteria",
            w["criteria_count"] >= 2 and "🟢" in w["strength"] or "🟡" in w["strength"],
            detail=w["strength"],
        )


def test_only_confirmed_filter():
    frames = {
        "A": _make_ohlcv(_engineered_sector_path(seed=40)),
        "B": _make_ohlcv([p * 1.02 for p in _engineered_sector_path(seed=41)]),
    }
    full = sha.build_sector_archive(frames, "اختبار4", "اختبار", only_confirmed=False)
    confirmed_only = sha.build_sector_archive(frames, "اختبار4", "اختبار", only_confirmed=True)
    if full.get("available") and confirmed_only.get("available"):
        _check(
            "test_only_confirmed_filter_subset",
            len(confirmed_only["up_windows"]) <= len(full["up_windows"]),
            detail=f"{len(confirmed_only['up_windows'])} vs {len(full['up_windows'])}",
        )
        _check(
            "test_only_confirmed_filter_all_criteria3",
            all(w["criteria_count"] == 3 for w in confirmed_only["up_windows"]),
            detail=str(confirmed_only["up_windows"]),
        )


def test_single_asset_archive_min_members_1():
    """كريبتو/معدن/عملة - أصل واحد بس، مفيش 'قطاع' حقيقي (min_members=1)."""
    path = _engineered_sector_path(n=400, seed=50)
    frames = {"BTC-USD": _make_ohlcv(path)}
    result = sha.build_sector_archive(frames, sector_name="كريبتو تجريبي", market_label="كريبتو", min_members=1)
    _check("test_single_asset_archive_min_members_1_available", result.get("available") is True, detail=str(result.get("reason")))
    if result.get("available"):
        _check("test_single_asset_archive_has_up_windows", len(result["up_windows"]) >= 1, detail=str(result["up_windows"]))


def test_single_asset_archive_rejects_without_min_members_override():
    path = _engineered_sector_path(n=400, seed=51)
    frames = {"BTC-USD": _make_ohlcv(path)}
    result = sha.build_sector_archive(frames, sector_name="كريبتو تجريبي2", market_label="كريبتو")  # الافتراضي min_members=2
    _check("test_single_asset_archive_rejects_without_override", result.get("available") is False, detail=str(result))


def _make_multi_year_ohlcv(years=6, seed=60, seasonal_bias_month=None, bias_strength=0.0015):
    """
    مسار سعري متعدد السنين - لو seasonal_bias_month محدد، بيضيف انحياز
    صعودي ثابت في هذا الشهر عبر كل السنين (عشان نختبر إن الموسمية فعلاً
    بتلتقط نمط حقيقي مُدخَل، مش بس ضوضاء عشوائية).
    """
    rng = np.random.default_rng(seed)
    n_days = years * 260
    idx = pd.bdate_range("2018-01-01", periods=n_days)
    path = [100.0]
    for d in idx[1:]:
        drift = bias_strength if (seasonal_bias_month is not None and d.month == seasonal_bias_month) else 0.0002
        path.append(path[-1] * (1 + drift + rng.normal(0, 0.01)))
    return pd.DataFrame({
        "Open": path, "High": np.array(path) * 1.005, "Low": np.array(path) * 0.995,
        "Close": path, "Volume": np.full(n_days, 1_000_000.0),
    }, index=idx)


def test_seasonality_detects_injected_monthly_bias():
    df = _make_multi_year_ohlcv(years=6, seed=70, seasonal_bias_month=7, bias_strength=0.0025)  # يوليو منحاز صعودياً بقوة
    indexed = ec.calculate_indicators(df)
    seasonality = sha.compute_seasonality(indexed)
    july_stats = seasonality.get("July", {})
    _check(
        "test_seasonality_detects_injected_monthly_bias",
        july_stats.get("status") == "OK" and july_stats.get("mean_daily_return_%", 0) > 0,
        detail=str(july_stats),
    )


def test_upcoming_months_outlook_structure():
    df = _make_multi_year_ohlcv(years=5, seed=71)
    indexed = ec.calculate_indicators(df)
    seasonality = sha.compute_seasonality(indexed)
    outlook = sha.upcoming_months_outlook(seasonality, as_of_date="2024-01-15", months_ahead=2)
    _check("test_upcoming_months_outlook_length", len(outlook) == 2, detail=str(outlook))
    if len(outlook) == 2:
        _check("test_upcoming_months_outlook_order", outlook[0]["month_number"] == 2 and outlook[1]["month_number"] == 3,
               detail=str([o["month_number"] for o in outlook]))
        _check("test_upcoming_months_outlook_has_arabic_name", outlook[0]["month_name_ar"] == "فبراير", detail=outlook[0]["month_name_ar"])


def test_rank_upcoming_outlook_sorted_descending():
    df_high = _make_multi_year_ohlcv(years=6, seed=80, seasonal_bias_month=3, bias_strength=0.003)
    df_low = _make_multi_year_ohlcv(years=6, seed=81, seasonal_bias_month=None)
    res_high = sha.build_sector_archive({"A": df_high, "B": df_high * 1.0}, "قطاع قوي", "اختبار")
    res_low = sha.build_sector_archive({"A": df_low, "B": df_low * 1.0}, "قطاع عادي", "اختبار")
    res_high["label"], res_high["category"] = "قطاع قوي", "اختبار"
    res_low["label"], res_low["category"] = "قطاع عادي", "اختبار"

    ranked = sha.rank_upcoming_outlook([res_high, res_low], as_of_date="2024-02-15", months_ahead=1)
    _check("test_rank_upcoming_outlook_nonempty", not ranked.empty, detail=str(ranked))
    if not ranked.empty:
        _check("test_rank_upcoming_outlook_sorted", list(ranked["win_rate_%"]) == sorted(ranked["win_rate_%"].fillna(-1), reverse=True),
               detail=str(ranked["win_rate_%"].tolist()))


def test_no_duplicate_indicator_logic():
    """نفس مبدأ اختبارات الهوية في المشروع - نتأكد إن الملف مش بيعرّف أي دالة من دوال eagle_core أو egx_historical_analyzer."""
    with open("sector_historical_archive.py", encoding="utf-8") as f:
        source = f.read()
    protected_names = [
        "def calculate_indicators", "def find_support_resistance",
        "def compute_eagle_score", "def make_final_decision",
        "def prepare_daily_features", "def analyze_monthly_seasonality",
    ]
    duplicates = [n for n in protected_names if n in source]
    _check("test_no_duplicate_indicator_logic", not duplicates, detail=str(duplicates))
    _check("test_uses_eagle_core_calculate_indicators", "ec.calculate_indicators(" in source)
    _check("test_uses_egx_historical_analyzer_seasonality", "eha.analyze_monthly_seasonality(" in source)


if __name__ == "__main__":
    tests = [
        test_build_sector_index_basic, test_build_sector_index_insufficient_members,
        test_detect_rally_window_found, test_detect_decline_window_found,
        test_ema_confirmation_present_for_strong_trend, test_only_confirmed_filter,
        test_single_asset_archive_min_members_1, test_single_asset_archive_rejects_without_min_members_override,
        test_seasonality_detects_injected_monthly_bias, test_upcoming_months_outlook_structure,
        test_rank_upcoming_outlook_sorted_descending,
        test_no_duplicate_indicator_logic,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            FAILURES.append(t.__name__)
            print(f"❌ {t.__name__}: EXCEPTION {e}")

    print(f"\n=== النتيجة: {'0 فاشل' if not FAILURES else str(len(FAILURES)) + ' فاشل: ' + str(FAILURES)} ===")
    sys.exit(1 if FAILURES else 0)
