"""
egx_historical_analyzer.py — PHASE 1.7: EGX Market Seasonality & Historical
Regime Analyzer

الهدف: طبقة "سياق تاريخي" (Historical Context) بحتة - بتجاوب على أسئلة
زي "هل ظروف السوق دلوقتي حصلت قبل كده؟ وحصل إيه بعدها؟" - **مش نظام
BUY/SELL مستقل**. النتيجة بتاعتها بتتحط جنب Eagle Score في Decision Card
كسياق إضافي بس، ومفيش تأثير مباشر على القرار النهائي حالياً
(historical_context_adjustment = 0 دايماً، زي ما القسم 19 من الخطة نص).

⚠️ الملف ده لوحده منطق حسابي صافي (pandas/numpy) - زي eagle_core.py -
مفيش أي Eagle Score logic اتكرر هنا؛ أي حاجة تخص Eagle Score بتتجاب من
eagle_core.py لو احتجناها.

⚠️ نفس قيد الشبكة من كل المراحل اللي فاتت: الكود ده يشتغل صح، لكن
بيانات EGX30 تاريخية حقيقية لازم إنترنت فعلي يجيبها (عن طريق
backtest_engine.fetch_full_history أو مباشرة من tvDatafeed) - البيئة اللي
اتكتب فيها الملف ده مقطوعة عن الإنترنت.
"""
import warnings
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuration - قابلة للتعديل، لكن مش لخدمة نتيجة معينة (قسم 24)
# ---------------------------------------------------------------------------
HISTORICAL_MIN_SAMPLE_SIZE = 30          # أقل عدد ملاحظات عشان الإحصائية تُعتبر ذات دلالة
HISTORICAL_MIN_YEARS = 3                 # أقل عدد سنين بيانات عشان "Seasonality" يُعتبر قابل للتفسير
HISTORICAL_SIMILARITY_MIN_MATCHES = 20   # أقل عدد حالات مشابهة تاريخياً عشان نعرض النتيجة
FORWARD_HORIZONS_DAYS = {"1D": 1, "3D": 3, "5D": 5, "10D": 10, "20D": 20}
LARGE_MOVE_THRESHOLDS = [-3, -2, -1, 1, 2, 3]  # % - أيام حركة كبيرة (قسم 9)
CONSECUTIVE_DAY_BUCKETS = [1, 2, 3, 4, 5]      # 5 يعني "5 فأكثر"

STATUS_LOW_SAMPLE = "LOW_SAMPLE"
STATUS_LOW_COVERAGE = "LOW_COVERAGE"
STATUS_UNRELIABLE = "UNRELIABLE"
STATUS_OK = "OK"
STATUS_UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# أدوات مساعدة صافية (no look-ahead by construction: كل دالة هنا بتاخد
# DataFrame وبترجع إحصائية عن المحتوى المُمرَّر ليها بالظبط - القيد
# الحقيقي "متاح لحد T بس" هو مسؤولية الـcaller (زي ما هو في backtest_engine.py)
# ---------------------------------------------------------------------------
def _daily_returns(df: pd.DataFrame) -> pd.Series:
    return df["Close"].pct_change().dropna() * 100


def _sample_status(n: int, min_n: int = HISTORICAL_MIN_SAMPLE_SIZE) -> str:
    return STATUS_OK if n >= min_n else STATUS_LOW_SAMPLE


@dataclass
class StatSummary:
    """ملخص إحصائي موحّد - كل نتيجة في الموديول ده بترجع الشكل ده."""
    sample_size: int
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    std_error: Optional[float] = None
    status: str = STATUS_UNKNOWN
    date_range: Optional[str] = None

    def to_dict(self):
        return {
            "sample_size": self.sample_size, "mean": self.mean, "median": self.median,
            "std": self.std, "std_error": self.std_error, "status": self.status,
            "date_range": self.date_range,
        }


def _summarize(values: pd.Series, date_range: str = None) -> StatSummary:
    n = len(values.dropna())
    if n == 0:
        return StatSummary(sample_size=0, status=STATUS_LOW_SAMPLE, date_range=date_range)
    mean = float(values.mean())
    median = float(values.median())
    std = float(values.std()) if n > 1 else None
    se = float(std / np.sqrt(n)) if std is not None else None
    return StatSummary(
        sample_size=n, mean=round(mean, 4), median=round(median, 4),
        std=round(std, 4) if std is not None else None,
        std_error=round(se, 4) if se is not None else None,
        status=_sample_status(n), date_range=date_range,
    )


# ===========================================================================
# 5) DAILY MARKET PATTERN ANALYSIS
# ===========================================================================
class HistoricalPatternAnalyzer:
    """إحصائيات يومية عامة + تحليل يوم الأسبوع + الشهر (أقسام 5-7)."""

    def __init__(self, df: pd.DataFrame):
        """df لازم يكون فيه Open/High/Low/Close/Volume وindex تاريخ."""
        self.df = df

    def daily_pattern_summary(self) -> dict:
        returns = _daily_returns(self.df)
        if returns.empty:
            return {"status": STATUS_LOW_SAMPLE, "sample_size": 0}
        up = (returns > 0).sum()
        down = (returns < 0).sum()
        flat = (returns == 0).sum()
        n = len(returns)
        return {
            "sample_size": n,
            "date_range": f"{self.df.index.min().date()} → {self.df.index.max().date()}",
            "avg_daily_return_%": round(float(returns.mean()), 4),
            "median_daily_return_%": round(float(returns.median()), 4),
            "std_%": round(float(returns.std()), 4),
            "up_day_%": round(up / n * 100, 1),
            "down_day_%": round(down / n * 100, 1),
            "flat_day_%": round(flat / n * 100, 1),
            "max_gain_%": round(float(returns.max()), 2),
            "max_loss_%": round(float(returns.min()), 2),
            "avg_volume": round(float(self.df["Volume"].mean()), 0),
            "median_volume": round(float(self.df["Volume"].median()), 0),
            "status": _sample_status(n),
        }

    def day_of_week_analysis(self) -> dict:
        """قسم 6 - يوم الأسبوع. بيحلل بس الأيام الموجودة فعلياً في البيانات."""
        returns = _daily_returns(self.df)
        dow = self.df["Close"].pct_change().dropna().to_frame("ret")
        dow["ret"] *= 100
        dow["day_name"] = dow.index.day_name()
        out = {}
        for day in dow["day_name"].unique():
            sub = dow[dow["day_name"] == day]["ret"]
            n = len(sub)
            if n == 0:
                continue
            up = (sub > 0).sum()
            out[day] = {
                "sample_size": n,
                "up_probability_%": round(up / n * 100, 1),
                "down_probability_%": round((n - up) / n * 100, 1),
                "mean_return_%": round(float(sub.mean()), 4),
                "median_return_%": round(float(sub.median()), 4),
                "std_%": round(float(sub.std()), 4) if n > 1 else None,
                "max_gain_%": round(float(sub.max()), 2),
                "max_loss_%": round(float(sub.min()), 2),
                "status": _sample_status(n),
            }
        return out

    def monthly_seasonality_analysis(self) -> dict:
        """
        قسم 7 - بيرجع لكل شهر: الإحصائيات + year-by-year consistency
        (عدد السنين اللي كان فيها الشهر ده صاعد مقابل هابط) - عشان نفرّق
        بين "متوسط سلبي" و"نمط ثابت فعلاً عبر السنين" (زي التحذير الصريح
        من مثال سبتمبر في الخطة).
        """
        ret = self.df["Close"].pct_change().dropna().to_frame("ret")
        ret["ret"] *= 100
        ret["month"] = ret.index.month_name()
        ret["year"] = ret.index.year
        out = {}
        for month in ret["month"].unique():
            sub = ret[ret["month"] == month]
            n = len(sub)
            if n == 0:
                continue
            up = (sub["ret"] > 0).sum()
            # year-by-year: هل الشهر ده صعد أو هبط كمجموع في كل سنة
            yearly = sub.groupby("year")["ret"].sum()
            up_years = int((yearly > 0).sum())
            down_years = int((yearly <= 0).sum())
            n_years = len(yearly)
            consistency_pct = round(max(up_years, down_years) / n_years * 100, 1) if n_years > 0 else None
            out[month] = {
                "sample_size": n,
                "n_years": n_years,
                "up_probability_%": round(up / n * 100, 1),
                "mean_return_%": round(float(sub["ret"].mean()), 4),
                "median_return_%": round(float(sub["ret"].median()), 4),
                "volatility_%": round(float(sub["ret"].std()), 4) if n > 1 else None,
                "max_gain_%": round(float(sub["ret"].max()), 2),
                "max_loss_%": round(float(sub["ret"].min()), 2),
                "up_years": up_years, "down_years": down_years,
                "consistency_%": consistency_pct,
                "status": (
                    STATUS_LOW_SAMPLE if n_years < HISTORICAL_MIN_YEARS
                    else (STATUS_UNRELIABLE if consistency_pct is not None and consistency_pct < 65
                          else STATUS_OK)
                ),
            }
        return out


# ===========================================================================
# 8-9) CONSECUTIVE DAYS + LARGE MOVES + FORWARD RETURNS
# ===========================================================================
class ForwardReturnAnalyzer:
    """
    قسم 8-9-14: بعد سلاسل الهبوط/الصعود المتتالية، وبعد الحركات الكبيرة -
    عوائد للأمام (Forward Returns) - **دول الوحيدين المسموح يستخدموا بيانات
    بعد T** لأنهم مقياس نتيجة، مش مدخل قرار.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df

    def _forward_returns_from_index(self, idx: int, horizons=FORWARD_HORIZONS_DAYS):
        if idx >= len(self.df):
            return None
        entry = float(self.df["Close"].iloc[idx])
        out = {}
        for label, n in horizons.items():
            target = idx + n
            if target >= len(self.df):
                out[label] = None
                continue
            exit_price = float(self.df["Close"].iloc[target])
            out[label] = round((exit_price / entry - 1) * 100, 3)
        return out

    def consecutive_days_analysis(self, direction: str = "down") -> dict:
        """
        قسم 8. لكل عدد أيام متتالية (1-5+)، بيحسب forward returns لكل
        الحالات التاريخية اللي حصلت فيها السلسلة دي (Point-in-Time: كل
        حالة إشارتها في يوم T، والـforward من T للأمام بس).
        """
        close = self.df["Close"]
        is_move = (close.diff() < 0) if direction == "down" else (close.diff() > 0)
        streak = pd.Series(0, index=self.df.index)
        for i in range(1, len(is_move)):
            streak.iloc[i] = streak.iloc[i - 1] + 1 if is_move.iloc[i] else 0

        results = {}
        for bucket in CONSECUTIVE_DAY_BUCKETS:
            is_last_bucket = bucket == CONSECUTIVE_DAY_BUCKETS[-1]
            if is_last_bucket:
                signal_idxs = np.where(streak.values >= bucket)[0]
                label = f"{bucket}+"
            else:
                signal_idxs = np.where(streak.values == bucket)[0]
                label = str(bucket)

            all_forward = {h: [] for h in FORWARD_HORIZONS_DAYS}
            for idx in signal_idxs:
                fwd = self._forward_returns_from_index(idx)
                if fwd is None:
                    continue
                for h, v in fwd.items():
                    if v is not None:
                        all_forward[h].append(v)

            horizon_stats = {}
            for h, vals in all_forward.items():
                if not vals:
                    horizon_stats[h] = {"sample_size": 0, "status": STATUS_LOW_SAMPLE}
                    continue
                arr = np.array(vals)
                horizon_stats[h] = {
                    "sample_size": len(arr),
                    "win_rate_%": round((arr > 0).mean() * 100, 1),
                    "mean_%": round(float(arr.mean()), 3),
                    "median_%": round(float(np.median(arr)), 3),
                    "best_%": round(float(arr.max()), 2),
                    "worst_%": round(float(arr.min()), 2),
                    "status": _sample_status(len(arr)),
                }
            results[label] = {"n_occurrences": len(signal_idxs), "forward": horizon_stats}
        return results

    def large_move_analysis(self) -> dict:
        """قسم 9: بعد أيام EGX30 <= -1%/-2%/-3% أو >= +1%/+2%/+3%."""
        daily_ret = self.df["Close"].pct_change() * 100
        results = {}
        for threshold in LARGE_MOVE_THRESHOLDS:
            if threshold < 0:
                idxs = np.where(daily_ret.values <= threshold)[0]
                label = f"<= {threshold}%"
            else:
                idxs = np.where(daily_ret.values >= threshold)[0]
                label = f">= +{threshold}%"

            all_forward = {h: [] for h in FORWARD_HORIZONS_DAYS}
            for idx in idxs:
                fwd = self._forward_returns_from_index(idx)
                if fwd is None:
                    continue
                for h, v in fwd.items():
                    if v is not None:
                        all_forward[h].append(v)

            horizon_stats = {}
            for h, vals in all_forward.items():
                if not vals:
                    horizon_stats[h] = {"sample_size": 0, "status": STATUS_LOW_SAMPLE}
                    continue
                arr = np.array(vals)
                same_direction = (arr > 0) if threshold > 0 else (arr < 0)
                horizon_stats[h] = {
                    "sample_size": len(arr),
                    "continuation_probability_%": round(same_direction.mean() * 100, 1),
                    "reversal_probability_%": round((1 - same_direction.mean()) * 100, 1),
                    "mean_%": round(float(arr.mean()), 3),
                    "median_%": round(float(np.median(arr)), 3),
                    "status": _sample_status(len(arr)),
                }
            results[label] = {"n_occurrences": len(idxs), "forward": horizon_stats}
        return results


# ===========================================================================
# 10-11) MARKET STRESS + REGIME CLASSIFICATION (Point-in-Time)
# ===========================================================================
@dataclass
class RegimeFeatures:
    """كل الميزات المستخدمة لتصنيف الـRegime عند نقطة زمنية T - كلها لازم تُحسب من df[:T] بس."""
    trend_return_20d_pct: Optional[float] = None
    volatility_20d_pct: Optional[float] = None
    drawdown_from_high_pct: Optional[float] = None
    consecutive_down_days: int = 0
    volume_percentile: Optional[float] = None
    breadth: Optional[float] = None          # UNAVAILABLE لو مفيش بيانات breadth تاريخية
    sector_strength: Optional[float] = None  # UNAVAILABLE لو مفيش


class MarketStressAnalyzer:
    """
    قسم 10-11: بيحسب Market Stress Score تاريخي (داخلي بس - مش جزء من
    Eagle Score) وبيصنّف الـRegime عند كل نقطة زمنية بناءً على بيانات لحد
    تلك النقطة بس.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df

    def compute_features_at(self, idx: int) -> RegimeFeatures:
        """كل القيم هنا محسوبة من self.df.iloc[:idx+1] بس - مفيش أي وصول لبعد idx."""
        if idx < 20:
            return RegimeFeatures()
        window = self.df.iloc[: idx + 1]
        close = window["Close"]

        trend_20d = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) >= 21 else None
        daily_ret = close.pct_change().dropna()
        vol_20d = float(daily_ret.tail(20).std()) if len(daily_ret) >= 20 else None

        rolling_high = close.expanding().max()  # سليم Point-in-Time: أقصى قيمة لحد النقطة دي بس
        drawdown = float((close.iloc[-1] / rolling_high.iloc[-1] - 1) * 100)

        streak = 0
        for i in range(len(close) - 1, 0, -1):
            if close.iloc[i] < close.iloc[i - 1]:
                streak += 1
            else:
                break

        vol_window = window["Volume"]
        vol_percentile = float((vol_window <= vol_window.iloc[-1]).mean() * 100) if len(vol_window) > 1 else None

        return RegimeFeatures(
            trend_return_20d_pct=round(trend_20d, 2) if trend_20d is not None else None,
            volatility_20d_pct=round(vol_20d, 3) if vol_20d is not None else None,
            drawdown_from_high_pct=round(drawdown, 2),
            consecutive_down_days=streak,
            volume_percentile=round(vol_percentile, 1) if vol_percentile is not None else None,
            breadth=None,           # UNAVAILABLE - مفيش تاريخ Breadth محفوظ (قسم 2)
            sector_strength=None,   # UNAVAILABLE - نفس السبب
        )

    def classify_regime(self, features: RegimeFeatures) -> str:
        """
        RISK_ON / NEUTRAL / RISK_OFF / SEVERE_RISK_OFF - مبني بس على
        الميزات المتاحة (breadth/sector_strength بيتم تجاهلهم لو
        UNAVAILABLE، مش استبدالهم بصفر).
        """
        if features.trend_return_20d_pct is None:
            return STATUS_UNKNOWN

        score = 0
        if features.trend_return_20d_pct > 3:
            score += 2
        elif features.trend_return_20d_pct > 0:
            score += 1
        elif features.trend_return_20d_pct < -5:
            score -= 2
        elif features.trend_return_20d_pct < 0:
            score -= 1

        if features.drawdown_from_high_pct is not None:
            if features.drawdown_from_high_pct < -10:
                score -= 2
            elif features.drawdown_from_high_pct < -5:
                score -= 1

        if features.consecutive_down_days >= 4:
            score -= 1
        if features.volatility_20d_pct is not None and features.volatility_20d_pct > 2.0:
            score -= 1

        if score >= 2:
            return "RISK_ON"
        if score <= -4:
            return "SEVERE_RISK_OFF"
        if score <= -2:
            return "RISK_OFF"
        return "NEUTRAL"

    def stress_score(self, features: RegimeFeatures) -> Optional[float]:
        """
        Market Stress Score داخلي (0-100، أعلى=أشد ضغط) - قسم 10.
        ⚠️ مش جزء من Eagle Score - عرض معلوماتي بس لحد ما يتحقق منه.
        """
        if features.trend_return_20d_pct is None:
            return None
        components = []
        components.append(max(0, min(-features.trend_return_20d_pct * 5, 40)))
        if features.drawdown_from_high_pct is not None:
            components.append(max(0, min(-features.drawdown_from_high_pct * 2, 30)))
        components.append(min(features.consecutive_down_days * 5, 20))
        if features.volatility_20d_pct is not None:
            components.append(min(features.volatility_20d_pct * 5, 10))
        return round(sum(components), 1)


# ===========================================================================
# 12-13) REGIME SIMILARITY ENGINE (أهم إضافة في الخطة)
# ===========================================================================
class RegimeSimilarityAnalyzer:
    """
    قسم 12-13: بدل "إيه أداء سبتمبر؟"، بيدوّر على "إيه الأيام التاريخية
    اللي ظروفها شبه اليوم ده؟" باستخدام مسافة إقليدية على ميزات موحّدة
    (Z-score) - كل الميزات التاريخية بتتحسب Point-in-Time (compute_features_at
    مسؤولة عن كده).
    """

    def __init__(self, df: pd.DataFrame, stress_analyzer: MarketStressAnalyzer):
        self.df = df
        self.stress_analyzer = stress_analyzer

    def _feature_vector(self, f: RegimeFeatures):
        vals = [f.trend_return_20d_pct, f.volatility_20d_pct, f.drawdown_from_high_pct,
                f.consecutive_down_days, f.volume_percentile]
        if any(v is None for v in vals):
            return None
        return np.array(vals, dtype=float)

    def find_similar_days(self, target_idx: int, max_lookback_idx: int = None, top_n: int = 50):
        """
        ⚠️ Point-in-Time حرج (قسم 16): لو بنعمل Backtest عند تاريخ T
        (target_idx)، max_lookback_idx **لازم يكون target_idx نفسه أو أقل**
        - ممنوع نقارن بأيام بعد T.
        """
        if max_lookback_idx is None:
            max_lookback_idx = target_idx  # افتراضي آمن: مفيش نظرة للمستقبل خالص

        target_features = self.stress_analyzer.compute_features_at(target_idx)
        target_vec = self._feature_vector(target_features)
        if target_vec is None:
            return {"status": STATUS_UNKNOWN, "matches": [], "n_matches": 0}

        candidates = []
        vectors = []
        for idx in range(20, max_lookback_idx + 1):
            if idx == target_idx:
                continue
            f = self.stress_analyzer.compute_features_at(idx)
            vec = self._feature_vector(f)
            if vec is not None:
                candidates.append(idx)
                vectors.append(vec)

        if len(candidates) < HISTORICAL_SIMILARITY_MIN_MATCHES:
            return {"status": STATUS_LOW_SAMPLE, "matches": [], "n_matches": len(candidates)}

        vectors = np.array(vectors)
        means = vectors.mean(axis=0)
        stds = vectors.std(axis=0)
        stds[stds == 0] = 1.0
        z_vectors = (vectors - means) / stds
        z_target = (target_vec - means) / stds

        distances = np.linalg.norm(z_vectors - z_target, axis=1)
        order = np.argsort(distances)[:top_n]
        matched_idxs = [candidates[i] for i in order]
        matched_distances = distances[order]

        max_dist = distances.max() if len(distances) else 1.0
        similarity_pct = float(round((1 - (matched_distances.mean() / max_dist)) * 100, 1)) if max_dist > 0 else None

        return {
            "status": STATUS_OK, "matches": matched_idxs, "n_matches": len(matched_idxs),
            "similarity_%": similarity_pct, "target_features": target_features,
        }

    def forward_outcomes_after_similar_days(self, similar_result: dict, fwd_analyzer: "ForwardReturnAnalyzer"):
        """قسم 13: بعد الحالات المشابهة، عوائد للأمام (المرة الوحيدة اللي بنستخدم فيها بيانات بعد كل حالة تاريخية - لقياس النتيجة بس)."""
        if similar_result["status"] != STATUS_OK or not similar_result["matches"]:
            return {"status": similar_result["status"]}

        all_forward = {h: [] for h in FORWARD_HORIZONS_DAYS}
        for idx in similar_result["matches"]:
            fwd = fwd_analyzer._forward_returns_from_index(idx)
            if fwd is None:
                continue
            for h, v in fwd.items():
                if v is not None:
                    all_forward[h].append(v)

        out = {}
        for h, vals in all_forward.items():
            if len(vals) < HISTORICAL_SIMILARITY_MIN_MATCHES // 2:
                out[h] = {"sample_size": len(vals), "status": STATUS_LOW_SAMPLE}
                continue
            arr = np.array(vals)
            out[h] = {
                "sample_size": len(arr),
                "up_probability_%": round((arr > 0).mean() * 100, 1),
                "down_probability_%": round((arr <= 0).mean() * 100, 1),
                "mean_%": round(float(arr.mean()), 3),
                "status": STATUS_OK,
            }
        return {"status": STATUS_OK, "n_matches": similar_result["n_matches"], "forward": out}


# ===========================================================================
# Historical Context Confidence (قسم 23)
# ===========================================================================
def historical_context_confidence(sample_size: int, n_years: float, feature_availability_pct: float) -> str:
    """HIGH / MEDIUM / LOW / UNKNOWN - حسب حجم العينة، طول التاريخ، واكتمال الميزات."""
    if sample_size < HISTORICAL_MIN_SAMPLE_SIZE or n_years < HISTORICAL_MIN_YEARS:
        return "LOW"
    if feature_availability_pct < 60:
        return "LOW"
    if sample_size >= 100 and n_years >= HISTORICAL_MIN_YEARS * 2 and feature_availability_pct >= 90:
        return "HIGH"
    return "MEDIUM"


# ===========================================================================
# Interface جاهز لدمج مستقبلي - DISABLED_BY_DEFAULT (قسم 19-20)
# ===========================================================================
def historical_context_adjustment(historical_context: dict) -> float:
    """
    ⚠️ معطّلة عمداً - بترجع 0 دايماً في Phase 1.7. الغرض من الدالة إنها
    تبقى موجودة كـInterface واضح لدمج مستقبلي (قسم 20: Final Score = Base
    Eagle Score + Historical Context Adjustment + ...)، لكن من غير ما
    تأثر على أي قرار فعلي لحد ما يتعمل Backtest مستقل يثبت فايدتها.
    """
    return 0.0


class EGXHistoricalAnalyzer:
    """
    الواجهة الموحّدة (Facade) اللي بتجمع كل المحركات فوق - نقطة دخول واحدة
    لأي حد عايز يستخدم Phase 1.7 (final_bot.py أو backtest_engine.py).
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.pattern = HistoricalPatternAnalyzer(df)
        self.forward = ForwardReturnAnalyzer(df)
        self.stress = MarketStressAnalyzer(df)
        self.similarity = RegimeSimilarityAnalyzer(df, self.stress)

    def full_report(self) -> dict:
        n_years = (self.df.index.max() - self.df.index.min()).days / 365.25 if len(self.df) > 1 else 0
        return {
            "data_period": f"{self.df.index.min().date()} → {self.df.index.max().date()}" if len(self.df) else STATUS_UNKNOWN,
            "n_years": round(n_years, 1),
            "daily_pattern": self.pattern.daily_pattern_summary(),
            "day_of_week": self.pattern.day_of_week_analysis(),
            "monthly_seasonality": self.pattern.monthly_seasonality_analysis(),
            "consecutive_down_days": self.forward.consecutive_days_analysis("down"),
            "consecutive_up_days": self.forward.consecutive_days_analysis("up"),
            "large_moves": self.forward.large_move_analysis(),
        }

    def current_context(self, as_of_idx: int = None) -> dict:
        """
        Historical Context عند نقطة زمنية معينة (افتراضياً آخر يوم متاح).
        بيرجع Regime + Stress Score + أقرب حالات مشابهة + عوائدهم للأمام -
        كله Point-in-Time، وhistorical_context_adjustment = 0 دايماً.
        """
        idx = as_of_idx if as_of_idx is not None else len(self.df) - 1
        features = self.stress.compute_features_at(idx)
        regime = self.stress.classify_regime(features)
        stress = self.stress.stress_score(features)

        similar = self.similarity.find_similar_days(idx, max_lookback_idx=idx)
        outcomes = self.similarity.forward_outcomes_after_similar_days(similar, self.forward)

        feature_fields = [features.trend_return_20d_pct, features.volatility_20d_pct,
                           features.drawdown_from_high_pct, features.volume_percentile,
                           features.breadth, features.sector_strength]
        availability_pct = round(sum(v is not None for v in feature_fields) / len(feature_fields) * 100, 1)
        confidence = historical_context_confidence(
            similar.get("n_matches", 0), max((idx / 252), 0.1), availability_pct,
        )

        return {
            "as_of_date": str(self.df.index[idx].date()) if idx < len(self.df) else STATUS_UNKNOWN,
            "current_regime": regime,
            "market_stress_score": stress,
            "features": features.__dict__,
            "similarity": similar,
            "forward_outcomes_after_similar": outcomes,
            "historical_context_confidence": confidence,
            "historical_context_adjustment": historical_context_adjustment({}),  # دايماً 0.0
        }
