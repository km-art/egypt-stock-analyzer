"""
sector_historical_archive.py — أرشيف تاريخي لنوافذ صعود/نزول القطاعات
(مصر + أمريكا + الإمارات - كل الأسواق الموجودة في final_bot.py)

الفكرة: بدل تحليل سهم لوحده، نبني مؤشر قطاعي مجمّع (equal-weighted) من كل
أسهم القطاع (مثلاً "طبي" = كل المستشفيات وشركات الأدوية)، ونمسح تاريخه
بالكامل لنحدد: "من تاريخ X لتاريخ Y، القطاع كله صعد/نزل Z%" - أرشيف نوافذ
صعود ونزول قطاعية، مش سهم واحد شاذ.

⚠️ Single Source of Truth: بعد بناء المؤشر القطاعي، بيتغذّى على
eagle_core.calculate_indicators **بنفسه** - EMA9/21/ADX بتتحسب بنفس المنطق
المستخدم في باقي المشروع بالكامل، صفر إعادة حساب مؤشرات من الصفر.

⚠️ تعريف "بداية صعود/نزول القطاع" (بقرار صريح من المستخدم: دمج التلات
معايير مع بعض، مش معيار واحد بس):
    1. مدة كافية بين القاع والقمة (duration_days >= min_duration_days)
    2. نسبة تغيّر كافية (|return_pct| >= min_return_pct)
    3. تأكيد فني (EMA9 فوق/تحت EMA21 لأغلبية أيام النافذة)
نافذة تحقق التلات معايير = "🟢 مؤكدة بالكامل". نافذة تحقق بعضها بس = "🟡
جزئية" - بتُعرض بوضوح بدرجة الثقة، مش بتُخفى أو تُقدَّم كمؤكدة وهي مش كذلك.

⚠️ محتاج إنترنت فعلي وقت التشغيل (جلب سنين من الأسعار لكل سهم في القطاع).
الاختبارات هنا (test_sector_historical_archive.py) بيانات اصطناعية بس -
MECHANICAL VALIDATION ONLY، نفس مبدأ Phase 1.7A بالضبط.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import eagle_core as ec

DEFAULT_MIN_DURATION_DAYS = 10
DEFAULT_MIN_RETURN_PCT = 15.0
DEFAULT_EMA_CONFIRM_RATIO = 0.6   # نسبة أيام النافذة اللي لازم يكون فيها EMA9 فوق/تحت EMA21
SWING_WINDOW = 5                  # نافذة اكتشاف القمم/القيعان المحلية (يمين/شمال بالجلسات)
MIN_MEMBERS = 2
MIN_HISTORY_ROWS = 30


def build_sector_index(price_frames: dict, base: float = 100.0):
    """
    price_frames: dict {ticker: OHLCV DataFrame} - نفس الشكل اللي بترجعه
    fetch_batch_data في final_bot.py أو fetch_full_history في
    backtest_engine.py (Single Source of Truth - مفيش دالة جلب جديدة هنا).

    بيبني مؤشر Equal-Weighted (كل سهم بوزن متساوي) مُطبَّع على `base` في
    أول تاريخ مشترك بين كل الأسهم، ويرجّعه كـDataFrame OHLCV اصطناعي
    (Open=High=Low=Close=قيمة المؤشر، Volume=متوسط حجم الأعضاء) جاهز
    للتغذية على eagle_core.calculate_indicators مباشرة.

    يرجع None لو عدد الأسهم اللي عندها تاريخ كافي أقل من MIN_MEMBERS، أو
    التقاطع الزمني المشترك أقصر من MIN_HISTORY_ROWS جلسة.
    """
    closes, volumes = {}, {}
    for ticker, df in price_frames.items():
        if df is None or getattr(df, "empty", True):
            continue
        try:
            c = df["Close"].squeeze() if hasattr(df["Close"], "squeeze") else df["Close"]
            c = c.dropna()
        except Exception:
            continue
        if len(c) < MIN_HISTORY_ROWS:
            continue
        closes[ticker] = c
        if "Volume" in df.columns:
            try:
                v = df["Volume"].squeeze() if hasattr(df["Volume"], "squeeze") else df["Volume"]
                volumes[ticker] = v
            except Exception:
                pass

    if len(closes) < MIN_MEMBERS:
        return None

    close_df = pd.DataFrame(closes).sort_index()
    aligned = close_df.dropna(how="any")
    if len(aligned) < MIN_HISTORY_ROWS:
        # تقاطع كامل صغير جداً - نسمح بـforward-fill محدود (3 جلسات) بدل استبعاد القطاع بالكامل
        aligned = close_df.sort_index().ffill(limit=3).dropna(how="any")
    if len(aligned) < MIN_HISTORY_ROWS:
        return None

    normalized = aligned / aligned.iloc[0] * base
    sector_index = normalized.mean(axis=1)

    if volumes:
        vol_df = pd.DataFrame(volumes).reindex(aligned.index)
        avg_volume = vol_df.mean(axis=1, skipna=True).fillna(0.0)
    else:
        avg_volume = pd.Series(0.0, index=aligned.index)

    return pd.DataFrame({
        "Open": sector_index, "High": sector_index, "Low": sector_index,
        "Close": sector_index, "Volume": avg_volume,
    }, index=aligned.index)


def _find_swings(close: pd.Series, window: int = SWING_WINDOW):
    """
    قمم وقيعان محلية بسيطة (backward+forward window، بس بيستخدم للتحليل
    التاريخي كله دفعة واحدة بعد اكتمال البيانات - مش Point-in-Time مباشر
    مثل price_behavior_engine، لأن الهدف هنا أرشيف تاريخي بأثر رجعي مش
    قرار لحظي على سهم حي).
    """
    vals = close.values
    n = len(vals)
    troughs, peaks = [], []
    for i in range(window, n - window):
        segment = vals[i - window:i + window + 1]
        seg_min, seg_max = segment.min(), segment.max()
        if vals[i] == seg_min and seg_min != seg_max:
            troughs.append(i)
        if vals[i] == seg_max and seg_min != seg_max:
            peaks.append(i)
    return troughs, peaks


def detect_direction_windows(sector_df_with_indicators: pd.DataFrame, direction: str,
                              min_duration_days: int = DEFAULT_MIN_DURATION_DAYS,
                              min_return_pct: float = DEFAULT_MIN_RETURN_PCT,
                              ema_confirm_ratio: float = DEFAULT_EMA_CONFIRM_RATIO):
    """
    direction: "up" (نوافذ صعود: قاع → قمة) أو "down" (نوافذ نزول: قمة → قاع).
    يرجع list[dict] فيها start_date/end_date/duration_days/return_pct/
    ema_confirmation_ratio/criteria_met/strength لكل نافذة.
    """
    if direction not in ("up", "down"):
        raise ValueError("direction لازم تكون 'up' أو 'down'")

    df = sector_df_with_indicators
    close = df["Close"]
    troughs, peaks = _find_swings(close)
    starts, ends = (troughs, peaks) if direction == "up" else (peaks, troughs)

    windows = []
    for s_idx in starts:
        later_ends = [e for e in ends if e > s_idx]
        if not later_ends:
            continue
        e_idx = min(later_ends)  # أقرب نقطة نهاية بعد البداية (نافذة واحدة مش متراكبة)

        start_date, end_date = df.index[s_idx], df.index[e_idx]
        start_price, end_price = float(close.iloc[s_idx]), float(close.iloc[e_idx])
        duration_days = e_idx - s_idx
        return_pct = round((end_price / start_price - 1) * 100, 2)

        if direction == "up" and return_pct <= 0:
            continue
        if direction == "down" and return_pct >= 0:
            continue

        segment = df.iloc[s_idx:e_idx + 1]
        ema_confirm = None
        if "EMA9" in segment.columns and "EMA21" in segment.columns:
            valid = segment.dropna(subset=["EMA9", "EMA21"])
            if len(valid):
                ema_confirm = float((valid["EMA9"] > valid["EMA21"]).mean()) if direction == "up" \
                    else float((valid["EMA9"] < valid["EMA21"]).mean())

        criteria_met = []
        if duration_days >= min_duration_days:
            criteria_met.append("مدة كافية")
        if abs(return_pct) >= min_return_pct:
            criteria_met.append("نسبة تغيّر كافية")
        if ema_confirm is not None and ema_confirm >= ema_confirm_ratio:
            criteria_met.append("تأكيد فني (EMA9/21)")

        if len(criteria_met) == 3:
            strength = "🟢 مؤكدة بالكامل (كل المعايير التلاتة)"
        elif criteria_met:
            strength = "🟡 جزئية (بعض المعايير بس)"
        else:
            strength = "⚪ ضعيفة (مفيش معيار محقق)"

        windows.append({
            "start_date": start_date, "end_date": end_date,
            "duration_days": int(duration_days), "return_pct": return_pct,
            "ema_confirmation_ratio": round(ema_confirm, 2) if ema_confirm is not None else None,
            "criteria_met": criteria_met, "criteria_count": len(criteria_met),
            "strength": strength,
        })

    return sorted(windows, key=lambda w: w["start_date"])


def build_sector_archive(price_frames: dict, sector_name: str, market_label: str,
                          min_duration_days: int = DEFAULT_MIN_DURATION_DAYS,
                          min_return_pct: float = DEFAULT_MIN_RETURN_PCT,
                          only_confirmed: bool = False) -> dict:
    """
    نقطة الدخول الرئيسية: من price_frames (تاريخ كل أسهم القطاع، جاهز من
    عند final_bot.py/backtest_engine.py) لأرشيف كامل فيه كل نوافذ الصعود
    والنزول التاريخية لهذا القطاع.

    only_confirmed=True: يفلتر ويرجّع بس النوافذ "🟢 مؤكدة بالكامل" (التلات
    معايير مع بعض) - الافتراضي False بيرجع كل النوافذ (مؤكدة+جزئية) مع
    توضيح درجة الثقة لكل واحدة، عشان الشفافية.
    """
    sector_raw = build_sector_index(price_frames)
    if sector_raw is None:
        return {
            "available": False,
            "reason": (
                f"عدد الأسهم اللي عندها تاريخ كافي في قطاع '{sector_name}' أقل من "
                f"{MIN_MEMBERS}، أو التقاطع الزمني المشترك أقصر من {MIN_HISTORY_ROWS} جلسة."
            ),
        }

    sector_indexed = ec.calculate_indicators(sector_raw)

    up_windows = detect_direction_windows(sector_indexed, "up", min_duration_days, min_return_pct)
    down_windows = detect_direction_windows(sector_indexed, "down", min_duration_days, min_return_pct)

    if only_confirmed:
        up_windows = [w for w in up_windows if w["criteria_count"] == 3]
        down_windows = [w for w in down_windows if w["criteria_count"] == 3]

    for w in up_windows:
        w.update(sector=sector_name, market=market_label, direction="صعود")
    for w in down_windows:
        w.update(sector=sector_name, market=market_label, direction="نزول")

    return {
        "available": True, "sector": sector_name, "market": market_label,
        "member_count": len(price_frames),
        "index_start": sector_indexed.index[0], "index_end": sector_indexed.index[-1],
        "up_windows": up_windows, "down_windows": down_windows,
        "sector_index_df": sector_indexed,
    }
