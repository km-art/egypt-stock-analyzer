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


def test_no_duplicate_indicator_logic():
    """نفس مبدأ اختبارات الهوية في المشروع - نتأكد إن الملف مش بيعرّف أي دالة من دوال eagle_core."""
    with open("sector_historical_archive.py", encoding="utf-8") as f:
        source = f.read()
    protected_names = [
        "def calculate_indicators", "def find_support_resistance",
        "def compute_eagle_score", "def make_final_decision",
    ]
    duplicates = [n for n in protected_names if n in source]
    _check("test_no_duplicate_indicator_logic", not duplicates, detail=str(duplicates))
    _check("test_uses_eagle_core_calculate_indicators", "ec.calculate_indicators(" in source)


if __name__ == "__main__":
    tests = [
        test_build_sector_index_basic, test_build_sector_index_insufficient_members,
        test_detect_rally_window_found, test_detect_decline_window_found,
        test_ema_confirmation_present_for_strong_trend, test_only_confirmed_filter,
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
