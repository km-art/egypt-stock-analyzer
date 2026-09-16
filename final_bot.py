import os
import time
from datetime import datetime
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np

# ---------------------------------------------------------------------------
# Single Source of Truth: كل منطق Eagle Score/Data Confidence/Signal
# Conflict/Final Decision موجود في eagle_core.py بس - final_bot.py و
# backtest_engine.py بيستوردوا نفس الدوال بالظبط، صفر نسخ مكررة، عشان
# يستحيل يحصل Logic Drift بين الإنتاج والـBacktest.
# ---------------------------------------------------------------------------
from eagle_core import (
    calculate_indicators, find_support_resistance,
    EAGLE_WEIGHTS, DISABLED_ENGINES_NO_PROVIDER,
    market_regime_score_component, breadth_score_component,
    _score_trend, _score_momentum, _score_volume_rvol, _score_liquidity,
    _score_price_structure, _score_breakout, _score_relative_strength,
    _score_sector_strength, _score_accumulation_distribution,
    _score_risk_reward, _score_fundamentals, _score_valuation,
    _score_market_depth, compute_eagle_score, compute_opportunity_risk_confidence,
    determine_entry_quality, DATA_STATUS_WEIGHT, compute_data_confidence,
    detect_signal_conflicts, DECISION_THRESHOLDS, make_final_decision,
)

# ---------------------------------------------------------------------------
# جلسة yfinance مضادة للحظر (Yahoo بيحظر السيرفرات المشتركة زي Streamlit Cloud)
# ---------------------------------------------------------------------------
# الحل المعتمد حالياً من مجتمع yfinance: استخدام curl_cffi عشان يقلّد بصمة
# متصفح حقيقي (TLS/JA3 fingerprint) بدل مكتبة requests العادية اللي Yahoo
# بقى يعرفها ويحظرها بسهولة على الـ IPs المشتركة زي Streamlit Cloud.
@st.cache_resource
def get_yf_session():
    try:
        from curl_cffi import requests as cffi_requests
        return cffi_requests.Session(impersonate="chrome")
    except Exception:
        # لو curl_cffi مش متثبتة لأي سبب، استخدم requests عادية بدل ما يقع الكود
        return requests.Session()


YF_SESSION = get_yf_session()

# ---------------------------------------------------------------------------
# مصدر بيانات مصر (EGX): TradingView بدل Yahoo
# ---------------------------------------------------------------------------
# Yahoo Finance وقفت تحدّث بيانات بورصة مصر (لاحظنا آخر تحديث متجمد على تاريخ
# قديم لكل الأسهم المصرية). TradingView عندها بيانات محدّثة يومياً وبتغطية
# أقوى لـ EGX، فبنستخدم مكتبة tvDatafeed (غير رسمية، بتقرا نفس البيانات اللي
# موقع TradingView بيعرضها) عشان نجيب تاريخ أسعار كامل (Open/High/Low/Close/
# Volume) بديل عن Yahoo لسوق مصر بس. أمريكا والإمارات فاضلين على Yahoo زي ما
# هما لأن بياناتهم شغالة تمام.
#
# ملحوظة: المكتبة غير رسمية (بتحاكي طلبات الموقع الداخلية)، ممكن تتعطل لو
# TradingView غيّرت حاجة من غير سابق إنذار - لو حصل كده، هترجع النتيجة فاضية
# وهيظهر السهم في "الأسهم اللي اتخطاها" بدل ما الكود يقع.
@st.cache_resource
def get_tv_datafeed():
    try:
        from tvDatafeed import TvDatafeed
        return TvDatafeed()  # وضع "بدون تسجيل دخول" - شغال لمعظم أسهم EGX
    except Exception:
        return None


TV_DATAFEED = get_tv_datafeed()


def fetch_egx_history_tv(egx_ticker: str, n_bars: int = 150):
    """
    يجيب تاريخ أسعار سهم مصري من TradingView (مش Yahoo) ويرجعه بنفس صيغة
    yfinance المعتادة (أعمدة Open/High/Low/Close/Volume) عشان باقي الكود
    (calculate_indicators وغيرها) يشتغل من غير أي تعديل.
    يرجع DataFrame فاضي لو فشل (بدل ما يرمي Exception ويوقف المسح كله).
    """
    if TV_DATAFEED is None:
        return pd.DataFrame()
    try:
        from tvDatafeed import Interval
        bare_symbol = egx_ticker[:-3] if egx_ticker.endswith(".CA") else egx_ticker
        hist = TV_DATAFEED.get_hist(
            symbol=bare_symbol, exchange="EGX",
            interval=Interval.in_daily, n_bars=n_bars,
        )
        if hist is None or hist.empty:
            return pd.DataFrame()
        hist = hist.rename(columns={
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume",
        })
        return hist[["Open", "High", "Low", "Close", "Volume"]]
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Market Depth Engine (Level 2 / Order Book) - مرحلة 2 من خطة التطوير
# ---------------------------------------------------------------------------
# قرار هندسي مهم (زي ما الخطة نفسها بتنص): مش بنربط عمق السوق جوه
# calculate_indicators() - ده محرك مستقل تماماً، ولو مصدر البيانات فشل أو
# مفيش مفتاح API، الأداة تفضل شغالة عادي بالتحليل الفني بس (V1) من غير أي
# تعطل. عمق السوق هنا **عرض معلوماتي بس حالياً** ومش بيدخل في قرار
# الشراء/البيع أو في نظام النقاط - زي ما الخطة أوصت (خطوة 8-9: اختبار
# وbacktest الأول قبل الاعتماد عليه في القرار).
#
# المصدر: EGXAPI (egxapi.com) - لسه "Developer Preview"، لسه مش مثبتة
# الاستقرار. بنستخدم بس الـ endpoints الخاصة بقراءة البيانات (quotes/order
# book)، وممنوع مطلقاً استخدام أي endpoint بيبعت أو يعدّل أو يلغي أوامر
# تداول حقيقية - ده تطبيق تحليل وترشيح، مش أداة تنفيذ صفقات.
#
# لازم مفتاح API (EGXAPI_KEY) في Streamlit Secrets عشان يشتغل. من غيره،
# كل الدوال هنا بترجع None بهدوء والتطبيق يفضل شغال زي ما هو.
def get_egxapi_key():
    try:
        return st.secrets.get("EGXAPI_KEY", None)
    except Exception:
        return None


@st.cache_data(ttl=15, show_spinner=False)  # كاش قصير جداً (15 ثانية) لأن العمق بيتغير بسرعة
def fetch_order_book_egxapi(bare_symbol: str):
    """
    يجيب order book خام لسهم من EGXAPI (قراءة فقط - مفيش أي إمكانية تنفيذ
    أوامر من هنا). يرجع None لو مفيش مفتاح API أو المصدر فشل - بهدوء من
    غير ما يوقف باقي التطبيق.

    ملحوظة: شكل الاستجابة هنا افتراضي (bids/asks كـ [price, size]) بناءً
    على النمط الشائع لـ APIs زي دي - لسه محتاج اختبار فعلي بمفتاح حقيقي
    عشان نتأكد ونظبط أسماء الحقول لو مختلفة.
    """
    api_key = get_egxapi_key()
    if not api_key:
        return None
    try:
        resp = requests.get(
            f"https://api.egxapi.com/v2/marketdata/{bare_symbol}/orderbook",
            headers={"Authorization": f"Bearer {api_key}", "X-EGX-Env": "paper"},
            timeout=5,
        )
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None


def normalize_to_adapter_schema(raw_order_book: dict, symbol: str, source: str = "egxapi"):
    """
    MarketDataAdapter: بيحوّل استجابة أي مصدر (EGXAPI دلوقتي، وممكن ICE لاحقاً)
    لشكل موحّد واحد زي ما الخطة حددت بالظبط:
    symbol | timestamp | bids[] | asks[] | last_price | last_trade_size |
    market_phase | source | data_age

    الفايدة: باقي الكود (فحص الجودة، حساب المقاييس، العرض) بيتعامل مع
    الشكل الموحّد ده بس، فلو غيّرنا المصدر لـICE مستقبلاً، بس الدالة دي
    اللي هتتغيّر - مفيش حاجة تانية في الكود هتتأثر.
    """
    if not raw_order_book:
        return None
    try:
        raw_ts = raw_order_book.get("timestamp") or raw_order_book.get("ts")
        if raw_ts:
            ts = pd.to_datetime(raw_ts, utc=True, errors="coerce")
        else:
            ts = None
        data_age_sec = (pd.Timestamp.now("UTC") - ts).total_seconds() if ts is not None and pd.notna(ts) else None

        return {
            "symbol": symbol,
            "timestamp": ts,
            "bids": raw_order_book.get("bids", []),
            "asks": raw_order_book.get("asks", []),
            "last_price": raw_order_book.get("last_price"),
            "last_trade_size": raw_order_book.get("last_trade_size"),
            "market_phase": raw_order_book.get("market_phase", "unknown"),
            "source": source,
            "data_age_sec": data_age_sec,
        }
    except Exception:
        return None


def validate_order_book(adapted: dict, max_staleness_sec: float = 60.0, min_levels: int = 1):
    """
    فحوصات جودة البيانات زي ما الخطة نصّت (قسم 5) - قبل أي حساب:
    - timestamp موجود وحديث (مش قديم أكتر من max_staleness_sec)
    - الأسعار والكميات مش سالبة
    - مستويات Bid تنازلية وAsk تصاعدية
    - snapshot مش فاضي وفيه عدد مستويات كافي

    يرجع (is_valid: bool, reason: str) - reason بتتعرض للمستخدم عشان
    يبقى واضح ليه Market Depth مش شغالة دلوقتي، بدل ما يفضل غامض.
    """
    if not adapted:
        return False, "مفيش بيانات وصلت من المصدر"

    bids, asks = adapted.get("bids") or [], adapted.get("asks") or []
    if len(bids) < min_levels or len(asks) < min_levels:
        return False, "عدد مستويات Bid/Ask غير كافي (snapshot ناقص)"

    if adapted.get("data_age_sec") is not None and adapted["data_age_sec"] > max_staleness_sec:
        return False, f"البيانات قديمة (عمرها {adapted['data_age_sec']:.0f} ثانية) - Stale Data"

    try:
        bid_prices = [float(b[0]) for b in bids]
        ask_prices = [float(a[0]) for a in asks]
        bid_sizes = [float(b[1]) for b in bids]
        ask_sizes = [float(a[1]) for a in asks]
    except (ValueError, IndexError, TypeError):
        return False, "تنسيق أسعار/كميات غير صالح"

    if any(p < 0 for p in bid_prices + ask_prices) or any(s < 0 for s in bid_sizes + ask_sizes):
        return False, "قيم سالبة في الأسعار أو الكميات (بيانات غير سليمة)"

    if bid_prices != sorted(bid_prices, reverse=True):
        return False, "ترتيب مستويات Bid غير صحيح (المفروض تنازلي)"
    if ask_prices != sorted(ask_prices):
        return False, "ترتيب مستويات Ask غير صحيح (المفروض تصاعدي)"

    if bid_prices[0] >= ask_prices[0]:
        return False, "السوق متقاطع (Best Bid >= Best Ask) - بيانات غير منطقية"

    return True, "سليم"


def compute_market_depth_metrics(adapted: dict, depth_levels: int = 10):
    """
    بيحوّل order book (بعد التطبيع والتحقق) لمقاييس موحدة:
    Bid/Ask Imbalance, Depth 5, Depth 10, Spread %.
    يرجع dict فاضي {} لو البيانات مش سليمة (بدل ما يرمي Exception).
    """
    if not adapted:
        return {}
    try:
        bids, asks = adapted["bids"], adapted["asks"]
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        mid_price = (best_bid + best_ask) / 2
        spread_pct = ((best_ask - best_bid) / mid_price) * 100 if mid_price > 0 else None

        def depth_sum(levels, n):
            return sum(float(lvl[1]) for lvl in levels[:n])

        bid_depth_5, ask_depth_5 = depth_sum(bids, 5), depth_sum(asks, 5)
        bid_depth_10, ask_depth_10 = depth_sum(bids, depth_levels), depth_sum(asks, depth_levels)

        total_depth_10 = bid_depth_10 + ask_depth_10
        imbalance_pct = ((bid_depth_10 - ask_depth_10) / total_depth_10) * 100 if total_depth_10 > 0 else None
        depth5_ratio = (bid_depth_5 / ask_depth_5) if ask_depth_5 > 0 else None
        depth10_ratio = (bid_depth_10 / ask_depth_10) if ask_depth_10 > 0 else None

        return {
            "symbol": adapted["symbol"], "source": adapted["source"],
            "data_age_sec": adapted.get("data_age_sec"),
            "market_phase": adapted.get("market_phase"),
            "last_price": adapted.get("last_price"),
            "best_bid": best_bid, "best_ask": best_ask, "mid_price": mid_price,
            "spread_%": round(spread_pct, 3) if spread_pct is not None else None,
            "bid_depth_5": bid_depth_5, "ask_depth_5": ask_depth_5,
            "bid_depth_10": bid_depth_10, "ask_depth_10": ask_depth_10,
            "depth5_ratio": round(depth5_ratio, 2) if depth5_ratio is not None else None,
            "depth10_ratio": round(depth10_ratio, 2) if depth10_ratio is not None else None,
            "imbalance_%": round(imbalance_pct, 1) if imbalance_pct is not None else None,
        }
    except Exception:
        return {}


def track_depth_momentum(symbol: str, imbalance_pct: float, max_history: int = 5):
    """
    Depth Momentum / Stability: بنسجل آخر كام قراءة لـ Imbalance لكل سهم في
    session_state (طول ما التطبيق مفتوح)، عشان نشوف الاتجاه بيتحسن ولا
    بيتراجع بمرور الوقت - زي ما الخطة نصّت: قراءة واحدة +34% أضعف من سلسلة
    متصاعدة +5% ثم +12% ثم +21% ثم +34%.

    ملحوظة: التتبع ده بيتصفر لما التطبيق يعمل reload كامل (مفيش تخزين
    دائم بين الجلسات) - ده كافي لمتابعة لحظية أثناء الاستخدام، مش بديل
    عن تسجيل تاريخي حقيقي لازم لـBacktest (قسم 12 في الخطة - لسه محتاج
    قرار تخزين منفصل قبل ما نبنيه).
    """
    if "depth_momentum_history" not in st.session_state:
        st.session_state["depth_momentum_history"] = {}
    history = st.session_state["depth_momentum_history"].setdefault(symbol, [])
    if imbalance_pct is not None:
        history.append(imbalance_pct)
        if len(history) > max_history:
            history.pop(0)

    if len(history) < 2:
        return {"trend": "غير كافي بعد", "stability": None, "history": history}

    diffs = [history[i] - history[i - 1] for i in range(1, len(history))]
    consistently_rising = all(d > 0 for d in diffs)
    consistently_falling = all(d < 0 for d in diffs)
    if consistently_rising:
        trend = "📈 عدم التوازن بيتصاعد باستمرار (إشارة أقوى من قراءة منفردة)"
    elif consistently_falling:
        trend = "📉 عدم التوازن بيتراجع باستمرار"
    else:
        trend = "↔️ متذبذب (مفيش اتجاه واضح)"

    stability = round(np.std(history), 1) if len(history) >= 2 else None
    return {"trend": trend, "stability": stability, "history": history}


def get_market_depth(bare_symbol: str):
    """
    نقطة الدخول الموحدة: بتجيب البيانات الخام، تطبّعها لشكل Adapter
    الموحّد، تتحقق من جودتها، وبعدين بس تحسب المقاييس. يرجع
    (metrics_dict أو None, reason_if_unavailable). لو الجودة فشلت، بيرجع
    None + السبب بدل ما يملأ قيم صفر بتخلي السهم يبان ضعيف بشكل مصطنع
    (زي ما الخطة أكدت في قسم 13).
    """
    raw = fetch_order_book_egxapi(bare_symbol)
    if raw is None:
        return None, "مفيش اتصال بمصدر عمق السوق (مفيش مفتاح أو المصدر مش راد)"

    adapted = normalize_to_adapter_schema(raw, symbol=bare_symbol)
    is_valid, reason = validate_order_book(adapted)
    if not is_valid:
        return None, f"البيانات مرفوضة بعد فحص الجودة: {reason}"

    metrics = compute_market_depth_metrics(adapted)
    if not metrics:
        return None, "فشل حساب مقاييس العمق من البيانات المتاحة"

    momentum = track_depth_momentum(bare_symbol, metrics.get("imbalance_%"))
    metrics["depth_momentum"] = momentum
    return metrics, "سليم"


# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

st.title("🦅 قناص البورصة المصرية (النسخة المتكاملة المقفلة ضد المخاطر)")
st.write("تم تقفيل الكود بمعايير صارمة: إضافة حد أدنى للفوليوم لحجب الأسهم الميتة، وفلاتر حماية من التضخم الحاد.")

# إعدادات عامة قابلة للتعديل
BATCH_SIZE = 30       # عدد الأسهم في كل طلب تحميل - تقسيم لدفعات لتفادي رفض Yahoo Finance للطلبات الضخمة
BATCH_DELAY = 1.5     # ثواني انتظار بين كل دفعة وأخرى
CROSS_LOOKBACK = 3    # كام يوم نرجع بيهم للخلف لاكتشاف "تقاطع جديد" (نفس القيمة تستخدم في التاب الأول والثاني)

# ---------------------------------------------------------------------------
# رموز بديلة (Ticker Overrides)
# ---------------------------------------------------------------------------
# بعض أسهم EGX عند Yahoo Finance ليها رمز مبني على ISIN بدل الرمز المختصر
# المعتاد - مثلاً "حديد عز" رمزها المعتاد ESRS.CA بس Yahoo فعلياً محتاج
# EGS3C251C013-EGP.CA. الديكشنري ده بيربط الرمز المعتاد بالرمز الصح اللي
# Yahoo بيفهمه، من غير ما نغيّر الرمز المعروض في النتائج.
BUILT_IN_TICKER_OVERRIDES = {
    "ESRS.CA": "EGS3C251C013-EGP.CA",  # حديد عز
}

_TICKER_OVERRIDES_CSV = "ticker_overrides.csv"


def load_ticker_overrides(csv_path: str = _TICKER_OVERRIDES_CSV) -> dict:
    """يدمج الرموز البديلة المدمجة في الكود + أي رموز أضافها المستخدم عبر الواجهة."""
    overrides = dict(BUILT_IN_TICKER_OVERRIDES)
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            overrides.update(dict(zip(df["original_ticker"], df["yahoo_symbol"])))
        except Exception as e:
            print(f"⚠️  تعذر تحميل {csv_path} ({e}).")
    return overrides


TICKER_OVERRIDES = load_ticker_overrides()


def resolve_symbol(ticker: str) -> str:
    """يرجع الرمز اللي فعلاً هيتبعت لـ Yahoo - نفس الرمز الأصلي لو مفيش بديل مسجّل."""
    return TICKER_OVERRIDES.get(ticker, ticker)


# ---------------------------------------------------------------------------
# سعر يدوي (Manual Price Override) - أعلى أولوية في سلسلة مصادر السعر
# ---------------------------------------------------------------------------
# لو عندك سعر لحظي فعلي من تطبيق وسيطك أو أي مصدر تثق فيه، تقدر تدخله يدوياً
# لسهم بعينه - وهو هياخد أولوية فوق كل مصادر الأتمتة (Twelve Data,
# TradingView, Yahoo). مفيد لما تحتاج تتأكد من دقة سعر سهم معين قبل قرار.
_MANUAL_PRICES_CSV = "manual_prices.csv"


def load_manual_prices(csv_path: str = _MANUAL_PRICES_CSV) -> dict:
    """يرجع dict: ticker -> {"price": float, "updated_at": str}"""
    if not os.path.exists(csv_path):
        return {}
    try:
        df = pd.read_csv(csv_path)
        return {
            row["ticker"]: {"price": float(row["price"]), "updated_at": str(row["updated_at"])}
            for _, row in df.iterrows()
        }
    except Exception as e:
        print(f"⚠️  تعذر تحميل {csv_path} ({e}).")
        return {}


MANUAL_PRICES = load_manual_prices()


# ---------------------------------------------------------------------------
# Twelve Data - مصدر منفصل ومخصص بس لسعر أقرب للحظي (اختياري، مش بديل ليفنانس)
# ---------------------------------------------------------------------------
class TwelveDataLivePrice:
    """
    مصدر سعر لحظي إضافي (اختياري) - منفصل تماماً عن yfinance، بيُستخدم بس
    لتحسين حقل السعر المعروض. التحليل الفني بيفضل معتمد بالكامل على yfinance.

    التغطية حسب باقة Twelve Data (twelvedata.com/pricing):
    - أمريكا (S&P 500): لحظي ومجاني بالكامل على باقة Basic.
    - مصر (EGX): محتاجة باقة Pro المدفوعة على الأقل (99$/شهر)، وشكل رمز
      السهم عندهم مختلف عن Yahoo أحياناً - تأكد بنفسك من الرمز الصح.
    - الإمارات: التغطية غير مؤكدة.
    """
    BASE_URL = "https://api.twelvedata.com"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("TWELVEDATA_API_KEY")

    def get_price(self, symbol: str) -> dict:
        if not self.api_key:
            return {"price": None, "is_live": False, "error": "مفيش API key"}
        try:
            resp = requests.get(
                f"{self.BASE_URL}/price",
                params={"symbol": symbol, "apikey": self.api_key},
                timeout=10,
            )
            data = resp.json()
            if "price" in data:
                return {"price": float(data["price"]), "is_live": True, "error": None}
            return {"price": None, "is_live": False, "error": data.get("message", "استجابة غير متوقعة")}
        except requests.exceptions.Timeout:
            return {"price": None, "is_live": False, "error": "Timeout"}
        except Exception as e:
            return {"price": None, "is_live": False, "error": str(e)}


class TradingViewLivePrice:
    """
    مصدر سعر أقرب للحظي عبر مكتبة tradingview_ta - "unofficial API wrapper"
    (مش منتج معتمد رسمياً من TradingView، بيحاكي نفس الطلبات اللي المتصفح
    بيبعتها لما تفتح شارت على الموقع). التغطية لـ EGX أقوى بكتير من Yahoo
    عادةً، وده مجاني بالكامل من غير API key.

    مخاطر معروفة (اقرأها قبل الاعتماد عليها بكثافة):
    - مكتبة غير رسمية - ممكن تتعطل فجأة لو TradingView غيّرت الـ endpoints
      الداخلية بتاعتها من غير سابق إنذار.
    - الاستخدام المكثف (مسح مئات الأسهم بشكل متكرر) ممكن يخالف شروط استخدام
      TradingView.
    """

    def __init__(self):
        try:
            from tradingview_ta import TA_Handler, Interval
        except ImportError:
            raise SystemExit(
                "محتاج تركيب المكتبة الأول:\n"
                "pip install tradingview_ta --break-system-packages"
            )
        self._TA_Handler = TA_Handler
        self._interval = Interval.INTERVAL_1_DAY

    def _resolve_market(self, ticker: str) -> dict:
        """يحوّل رمز Yahoo (زي COMI.CA) لصيغة TradingView (screener/exchange/symbol)."""
        if ticker.endswith(".CA"):
            return {"screener": "egypt", "exchanges": ["EGX"], "symbol": ticker[:-3]}
        if ticker.endswith(".AE"):
            return {"screener": "uae", "exchanges": ["DFM", "ADX"], "symbol": ticker[:-3]}
        return {"screener": "america", "exchanges": ["NASDAQ", "NYSE"], "symbol": ticker}

    def get_price(self, ticker: str) -> dict:
        market = self._resolve_market(ticker)
        last_error = None
        for exch in market["exchanges"]:
            try:
                handler = self._TA_Handler(
                    symbol=market["symbol"], screener=market["screener"],
                    exchange=exch, interval=self._interval,
                )
                analysis = handler.get_analysis()
                price = analysis.indicators.get("close")
                if price:
                    return {"price": float(price), "is_live": True, "error": None}
            except Exception as e:
                last_error = f"{exch}: {e}"
                continue
        return {"price": None, "is_live": False, "error": last_error or "فشلت كل البورصات المجرَّبة"}


def get_live_price_yahoo(ticker: str) -> dict:
    """
    سعر أقرب للحظي (delayed quote) من yfinance عبر fast_info - أسرع وأخف من
    .info الكامل. مش لحظي 100% (تأخير Yahoo المعتاد)، وممكن يفشل لأسهم EGX
    الأقل تغطية. بيرجع لآخر إغلاق يومي تلقائياً لو فشل.
    """
    try:
        fast = yf.Ticker(resolve_symbol(ticker), session=YF_SESSION).fast_info
        price = fast.get("last_price") if hasattr(fast, "get") else getattr(fast, "last_price", None)
        if price is not None and price > 0:
            return {"price": float(price), "is_live": True}
    except Exception as e:
        print(f"⚠️  فشل جلب السعر شبه اللحظي لـ {ticker}: {type(e).__name__}: {e}")
    return {"price": None, "is_live": False}


# القراءة التلقائية من Streamlit Secrets كخيار احتياطي
try:
    default_token = st.secrets.get("TELEGRAM_TOKEN", "")
    default_chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
except Exception:
    # لو مفيش ملف secrets.toml أصلاً، منسيبش الأداة تقع - نكمل بقيم فاضية
    default_token = ""
    default_chat_id = ""

# إعدادات التنبيهات في الشريط الجانبي
st.sidebar.header("⚙️ إعدادات إشعارات الموبايل (تليجرام)")
TELEGRAM_TOKEN = st.sidebar.text_input("أدخل Token البوت:", value=default_token, type="password")
TELEGRAM_CHAT_ID = st.sidebar.text_input("أدخل Chat ID الخاص بك:", value=default_chat_id)

st.sidebar.markdown("---")
st.sidebar.subheader("🕐 سعر لحظي إضافي (اختياري)")
enable_td_live = st.sidebar.checkbox("فعّل Twelve Data لسعر أقرب للحظي", value=False)
td_live_price = None
if enable_td_live:
    st.sidebar.caption(
        "🇺🇸 مجاني ولحظي فعلاً للأسهم الأمريكية (باقة Basic). "
        "🇪🇬 مصر محتاجة باقة Pro المدفوعة (99$/شهر على الأقل)، وشكل رمز "
        "السهم عندهم مختلف عن Yahoo أحياناً."
    )
    td_api_key = st.sidebar.text_input("Twelve Data API Key", type="password", key="td_api_key")
    if td_api_key:
        td_live_price = TwelveDataLivePrice(api_key=td_api_key)

enable_tv_live = st.sidebar.checkbox("فعّل TradingView لسعر أقرب للحظي (مجاني، مصدر غير رسمي)", value=False)
tv_live_price = None
if enable_tv_live:
    st.sidebar.caption(
        "🆓 **مجاني بالكامل ومن غير API key.** تغطيته لمصر أقوى بكتير من "
        "Yahoo عادةً. **لكن**: مكتبة `tradingview_ta` غير رسمية (unofficial) "
        "- ممكن تتعطل فجأة لو TradingView غيّرت الـ endpoints الداخلية "
        "بتاعتها، والاستخدام المكثف ممكن يخالف شروط استخدامهم."
    )
    try:
        tv_live_price = TradingViewLivePrice()
    except SystemExit as e:
        st.sidebar.error(str(e))
        tv_live_price = None

st.sidebar.markdown("---")
with st.sidebar.expander(f"🔧 رموز بديلة للأسهم الفاشلة ({len(TICKER_OVERRIDES)} مسجّل)"):
    st.caption(
        "بعض أسهم EGX عند Yahoo Finance ليها رمز مبني على ISIN بدل الرمز "
        "المختصر المعتاد (مثال: ESRS.CA فعلياً محتاجة EGS3C251C013-EGP.CA). "
        "لو سهم بيفشل تحميله، دوّر عليه يدوياً على finance.yahoo.com واكتب "
        "الرمز الصح هنا."
    )
    if TICKER_OVERRIDES:
        st.dataframe(
            pd.DataFrame(list(TICKER_OVERRIDES.items()), columns=["الرمز الأصلي", "رمز Yahoo الصحيح"]),
            use_container_width=True, hide_index=True,
        )
    ov_col1, ov_col2 = st.columns(2)
    with ov_col1:
        ov_original = st.text_input("الرمز الأصلي (زي ESRS.CA)", key="ov_original_fb")
    with ov_col2:
        ov_yahoo = st.text_input("رمز Yahoo الصحيح", key="ov_yahoo_fb")
    if st.button("💾 حفظ الرمز البديل", key="save_override_fb"):
        if ov_original and ov_yahoo:
            existing = pd.read_csv(_TICKER_OVERRIDES_CSV) if os.path.exists(_TICKER_OVERRIDES_CSV) \
                else pd.DataFrame(columns=["original_ticker", "yahoo_symbol"])
            existing = existing[existing["original_ticker"] != ov_original.strip()]
            new_row = pd.DataFrame([{"original_ticker": ov_original.strip(), "yahoo_symbol": ov_yahoo.strip()}])
            pd.concat([existing, new_row], ignore_index=True).to_csv(_TICKER_OVERRIDES_CSV, index=False)
            st.success(f"✅ اتحفظ: {ov_original} → {ov_yahoo}. أعد تشغيل التحليل عشان يتفعّل.")
            st.rerun()
        else:
            st.warning("لازم تملأ الحقلين الاتنين.")

st.sidebar.markdown("---")
with st.sidebar.expander(f"✍️ سعر يدوي لسهم بعينه ({len(MANUAL_PRICES)} مسجّل)"):
    st.caption(
        "لو عندك سعر أدق من تطبيق وسيطك أو مصدر تثق فيه، دخّله هنا لسهم "
        "معين — هياخد **أعلى أولوية** فوق أي مصدر آلي (Twelve Data، "
        "TradingView، Yahoo) لحد ما تمسحه بنفسك."
    )
    if MANUAL_PRICES:
        mp_display = pd.DataFrame([
            {"الرمز": t, "السعر": v["price"], "آخر تحديث": v["updated_at"]}
            for t, v in MANUAL_PRICES.items()
        ])
        st.dataframe(mp_display, use_container_width=True, hide_index=True)

    mp_col1, mp_col2 = st.columns(2)
    with mp_col1:
        mp_ticker = st.text_input("رمز السهم (زي COMI.CA)", key="mp_ticker_fb")
    with mp_col2:
        mp_price = st.number_input("السعر", min_value=0.0, step=0.01, key="mp_price_fb")

    mp_save_col, mp_clear_col = st.columns(2)
    with mp_save_col:
        if st.button("💾 حفظ السعر اليدوي", key="save_manual_price_fb"):
            if mp_ticker and mp_price > 0:
                existing = pd.read_csv(_MANUAL_PRICES_CSV) if os.path.exists(_MANUAL_PRICES_CSV) \
                    else pd.DataFrame(columns=["ticker", "price", "updated_at"])
                existing = existing[existing["ticker"] != mp_ticker.strip()]
                new_row = pd.DataFrame([{
                    "ticker": mp_ticker.strip(),
                    "price": mp_price,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }])
                pd.concat([existing, new_row], ignore_index=True).to_csv(_MANUAL_PRICES_CSV, index=False)
                st.success(f"✅ اتحفظ سعر {mp_ticker} = {mp_price}")
                st.rerun()
            else:
                st.warning("لازم تدخل رمز السهم وسعر أكبر من صفر.")
    with mp_clear_col:
        if st.button("🗑️ مسح سعر يدوي", key="clear_manual_price_fb"):
            if mp_ticker and os.path.exists(_MANUAL_PRICES_CSV):
                existing = pd.read_csv(_MANUAL_PRICES_CSV)
                existing = existing[existing["ticker"] != mp_ticker.strip()]
                existing.to_csv(_MANUAL_PRICES_CSV, index=False)
                st.success(f"🗑️ اتمسح سعر {mp_ticker} اليدوي")
                st.rerun()
            else:
                st.warning("اكتب رمز السهم اللي عايز تمسح سعره اليدوي.")

def get_display_price(ticker: str, fallback_price: float) -> dict:
    """
    يحاول يجيب سعر أقرب للحظي بالأولوية: سعر يدوي (إنت أدخلته) -> Twelve
    Data -> TradingView -> Yahoo fast_info -> السعر الاحتياطي (آخر إغلاق
    يومي من البيانات المُحمّلة أصلاً).
    """
    manual_entry = MANUAL_PRICES.get(ticker)
    if manual_entry is not None:
        return {"price": manual_entry["price"], "source": "manual",
                "updated_at": manual_entry["updated_at"]}

    if td_live_price is not None:
        td_result = td_live_price.get_price(ticker)
        if td_result.get("is_live") and td_result.get("price"):
            return {"price": td_result["price"], "source": "twelvedata"}

    if tv_live_price is not None:
        tv_result = tv_live_price.get_price(ticker)
        if tv_result.get("is_live") and tv_result.get("price"):
            return {"price": tv_result["price"], "source": "tradingview"}

    live = get_live_price_yahoo(ticker)
    if live.get("is_live") and live.get("price"):
        return {"price": live["price"], "source": "yahoo_fast_info"}

    return {"price": fallback_price, "source": "historical_close"}


def send_telegram_alert(message):
    """
    يرسل رسالة عبر تليجرام ويرجع (نجح: bool, رسالة الحالة: str)
    بدل ما كان بيفشل بصمت لو الـ token أو الـ chat_id غلط.
    """
    token = TELEGRAM_TOKEN if TELEGRAM_TOKEN else default_token
    chat_id = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else default_chat_id

    if not (token and chat_id):
        return False, "لم يتم إدخال Token أو Chat ID - تم تخطي الإرسال."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200 and resp.json().get("ok"):
            return True, "تم إرسال التنبيه على تليجرام بنجاح ✅"
        return False, f"فشل الإرسال (كود {resp.status_code}): تأكد من صحة Token و Chat ID"
    except requests.exceptions.Timeout:
        return False, "انتهت مهلة الاتصال بتليجرام (Timeout) - جرب تاني."
    except requests.exceptions.RequestException as e:
        return False, f"خطأ في الاتصال بتليجرام: {e}"

# القائمة الكاملة لرموز أسهم السوق المصري (EGX) على Yahoo Finance
# تم تحديثها لتشمل كل الأسهم المدرجة في egx_all_listed_stocks.csv (230 سهم إجمالاً)
ALL_EGX_STOCKS = {
    "A Capital Holding": "ACAP.CA", "AJWA For Food Industries Co. Egypt": "AJWA.CA",
    "ASEC Company for Mining ASCOM": "ASCM.CA", "Act Financial": "ACTF.CA",
    "Al Ahly for Development & Investment": "AFDI.CA", "Al Tawfeek Leasing Company": "ATLC.CA",
    "AlKhair River for Development Agricultural Investment": "KRDI.CA", "Alexandria Co. For Pharmaceuticals & Chemical Industries": "AXPH.CA",
    "Alexandria Flour Mills": "AFMC.CA", "Alexandria New Medical Center": "AMES.CA",
    "Alexandria Spinning & Weaving Co.": "SPIN.CA", "Amer Group Holding Company": "AMER.CA",
    "Arab Aluminum Company": "ALUM.CA", "Arab Co. for Asset Management and Development": "ACAMD.CA",
    "Arab Company For Land Reclamation": "EALR.CA", "Arab Engineering Industries": "EEII.CA",
    "Arab Moltaqa Investments Company": "AMIA.CA", "Arab Real Estate Investment Co.": "RREI.CA",
    "Arab Valves Company": "ARVA.CA", "Arabia Cotton Ginning Company": "ACGC.CA",
    "Arabia Investments Holding": "AIHC.CA", "Arabia for Investment and Development": "AIDC.CA",
    "Arabian Cement Company": "ARCC.CA", "Aspire Capital Holding for Financial Investments": "ASPI.CA",
    "Atlas for Investment & Food Industries": "ALRA.CA", "B Investments Holding": "BINV.CA",
    "Bonyan for Development and Trade": "BONY.CA", "CI Capital Holding": "CICH.CA",
    "CIRA Education": "CIRA.CA", "Cairo Educational Services": "CAED.CA",
    "Cairo Oil & Soap Company": "COSG.CA", "Canal Shipping Agencies Company": "CSAG.CA",
    "Catalyst Partners": "CPME.CA", "Cleopatra Hospitals Group": "CLHO.CA",
    "Concrete Fashion Group": "CFGH.CA", "Contact Financial Holding": "CNFN.CA",
    "Copper for Commercial Investment & Real Estate Development": "COPR.CA", "Creast Mark For Contracting And Real Estate Development": "CRST.CA",
    "Credit Agricole Egypt Bank": "CIEB.CA", "Damietta Container & Cargo Handling Co.": "DCCC.CA",
    "Delta Co. For Printing & Packaging": "DTPP.CA", "Delta Insurance Company": "DEIN.CA",
    "Delta Sugar Company": "SUGR.CA", "Dice For Ready-Made Garments": "DSCW.CA",
    "Digitize for Investment And Technology": "DGTZ.CA", "East Delta Flour Mills": "EDFM.CA",
    "Egypt Free Shops Co.": "MFSC.CA", "Egypt for Poultry": "EPCO.CA",
    "Egyptian Arabian Company (Themar) for Securities Brokerage": "EASB.CA", "Egyptian Financial and Industrial SAE": "EFIC.CA",
    "Egyptian Gulf Bank": "EGBE.CA", "Egyptian Iron and Steel Company": "IRON.CA",
    "Egyptian Media Production City": "MPRC.CA", "Egyptian Modern Education Systems": "MOED.CA",
    "Egyptian Resorts Company": "EGTS.CA", "Egyptian Satellite Company Nilesat": "EGSA.CA",
    "Egyptian Transport and Commercial Services": "ETRS.CA", "Egyptians for Housing & Development Co.": "EHDR.CA",
    "El Ahram Co. For Printing And Packaging": "EPPK.CA", "El Kahera El Watania Investment": "KWIN.CA",
    "El Nasr Manufacturing Agricultural Crops": "ELNA.CA", "El Orouba Securities Brokerage": "EOSB.CA",
    "El Shams Pyramids Hotels & Touristic Projects": "SPHT.CA", "El Wadi for International and Investment Development": "ELWA.CA",
    "El-Ebour Co. for Real Estate Investment": "OBRI.CA", "El-Nasr Clothing & Textiles Co.": "KABO.CA",
    "Electro Cable Egypt": "ELEC.CA", "Export Development Bank of Egypt": "EXPA.CA",
    "Faisal Islamic Bank of Egypt (EGP line)": "FAITA.CA", "Ferchem Misr for Fertilizers and Chemicals": "FERC.CA",
    "GMC Group For Industrial Commercial & Financial Investments": "GMCI.CA", "GPI for Urban Growth": "GPIM.CA",
    "GTEX for Commercial and Industrial Investments": "GTEX.CA", "Gadwa for Industrial Development": "GDWA.CA",
    "General Co. For Silos & Storage": "GSSC.CA", "General Company For Land Reclamation Development & Reconstruction": "AALR.CA",
    "General Company for Ceramic and Porcelain Products": "PRCL.CA", "Gharbia Islamic Housing Development Company": "GIHD.CA",
    "GlaxoSmithKline Egypt": "BIOC.CA", "Go Green For Agricultural Investment And Development": "GGRN.CA",
    "Golden Pyramids Plaza": "GPPL.CA", "Golden Textiles & Clothes Wool": "GTWL.CA",
    "Gourmet Egypt.Com Foods": "GOUR.CA", "Grand Capital for Financial Investments": "GRCA.CA",
    "Gulf Canadian Company for Arab Real Estate Investment": "CCRS.CA", "Industrial Engineering Company ICON": "ENGC.CA",
    "International Co. For Investment & Development": "ICID.CA", "International Company for Agricultural Crops": "IFAP.CA",
    "International Company for Leasing": "ICLE.CA", "Iron & Steel for Mines & Quarries": "ISMQ.CA",
    "Ismailia Development and Real Estate Co": "IDRE.CA", "Ismailia National Co. for Food Industries": "INFI.CA",
    "Kafr El Zayat For Pesticides & Chemicals": "KZPC.CA", "Kahira Pharmaceuticals & Chemical Industries": "CPCI.CA",
    "Lecico Egypt": "LCSW.CA", "Lotus Agri Capital": "LUTS.CA",
    "MINAPHARM Pharmaceuticals": "MIPH.CA", "MM Group for Industry and International Trade": "MTIE.CA",
    "Macro Group Pharmaceuticals (Macro Capital)": "MCRO.CA", "Maridive and Oil Services": "MOIL.CA",
    "Marsa Alam For Tourism Development": "MMAT.CA", "Marseille Almasreia Alkhalegeya For Holding Investment": "MAAL.CA",
    "Memphis Pharmaceuticals & Chemical Industries": "MPCI.CA", "Mena for Touristic & Real Estate Investment": "MENA.CA",
    "Middle & West Delta Flour Mills": "WCDF.CA", "Middle East Glass Manufacturing Company": "MEGM.CA",
    "Misr Beni Suef Cement": "MBSC.CA", "Misr Cement (Qena)": "MCQE.CA",
    "Misr Chemical Industries Co.": "MICH.CA", "Misr Hotels Company": "MHOT.CA",
    "Misr National Steel - Ataqa": "ATQA.CA", "Misr Oils & Soap": "MOSC.CA",
    "Mohandes Insurance Company": "MOIN.CA", "Naeem Holding Company For Investments": "NAHO.CA",
    "Naeem Real Estate Holding Group": "NARE.CA", "Nasr Company for Civil Works": "NCCW.CA",
    "National Company for Housing Professional Syndicates": "NHPS.CA", "National Drilling Company": "NDRL.CA",
    "National Printing Company": "NAPR.CA", "North Cairo Flour Mills": "MILS.CA",
    "Northern Upper Egypt For Development & Agricultural Production": "NEDA.CA", "Nozha International Hospital": "NINH.CA",
    "O B Financial Holding": "OFH.CA", "Obour Land for Food Industries": "OLFI.CA",
    "October Pharma": "OCPH.CA", "Orascom Construction PLC": "ORAS.CA",
    "Oriental Weavers Carpets Company": "ORWE.CA", "Osool ESB Securities Brokerage": "EBSC.CA",
    "Pioneers Properties For Urban Development": "PRDC.CA", "Port Said Containers And Cargo Handling Co.": "POCO.CA",
    "Premium Healthcare Group": "PHGC.CA", "Prime Holding": "PRMH.CA",
    "Pyramisa Hotels & Resorts": "PHTV.CA", "Qatar National Bank Al Ahli": "QNBE.CA",
    "Raya Customer Experience": "RACC.CA", "Raya Holding for Financial Investments": "RAYA.CA",
    "Real Estate Egyptian Consortium": "AREH.CA", "Remco Tourism Villages Construction": "RTVC.CA",
    "Rowad Tourism Company": "ROTO.CA", "Rubex International for Plastic and Acrylic Manufacturing": "RUBX.CA",
    "SHARM DREAMS Co. for Touristic Investment": "SDTI.CA", "Sabaa International Pharmaceutical and Chemical Industry": "SIPC.CA",
    "Samad Misr EGYFERT": "SMFR.CA", "Saudi Egyptian Investment & Finance Co.": "SEIG.CA",
    "Saudi Egyptian Investment & Finance Co. (line A)": "SEIGA.CA", "Sharkia National Company for Food Security": "SNFC.CA",
    "Sinai Cement Co.": "SCEM.CA", "Sixth of October Development and Investment SODIC": "OCDI.CA",
    "Société Arabe Internationale de Banque": "SAIB.CA", "South Cairo and Giza Flour Mills and Bakeries": "SCFM.CA",
    "South Valley Cement Company": "SVCE.CA", "Speed Medical Co": "SPMD.CA",
    "Suez Canal Company for Technology Settling": "SCTS.CA", "Taaleem Management Services": "TALM.CA",
    "Tanmiya For Real Estate Investment": "TANM.CA", "Tenth of Ramadan Pharmaceutical (Rameda)": "RMDA.CA",
    "The Arab Ceramic Co.": "CERA.CA", "The Arab Dairy Products Co.": "ADPC.CA",
    "The United Bank": "UBEE.CA", "Trans Oceans Tours": "TRTO.CA",
    "Tycoon Holding Company For Financial Investments": "ANFI.CA", "Unirab Polvara Spinning & Weaving Co.": "APSW.CA",
    "United Co. for Housing & Development": "UNIT.CA", "Upper Egypt Mills Company": "UEFM.CA",
    "Valmore Holding (EGP line)": "VLMRA.CA", "Valmore Holding (USD line)": "VLMR.CA",
    "Valu Consumer Finance": "VALU.CA", "Wadi Kom Ombo For Land Reclamation Co.": "WKOL.CA",
    "Zahraa El Maadi Investment and Development": "ZMID.CA", "أبو قير للأسمدة": "ABUK.CA",
    "أكرو مصر للشدات": "ACRO.CA", "أودن للاستثمارات المالية": "ODIN.CA",
    "أوراسكوم للاستثمار القابضة": "OIH.CA", "أوراسكوم للتنمية مصر": "ORHD.CA",
    "إعمار مصر للتنمية": "EMFD.CA", "إي فاينانس للاستثمارات": "EFIH.CA",
    "إيديتا للصناعات الغذائية": "EFID.CA", "ابن سينا فارما": "ISPH.CA",
    "الأسكندرية لتداول الحاويات": "ALCN.CA", "الأسكندرية للزيوت المعدنية - أموك": "AMOC.CA",
    "الاسكندرية لأسمنت بورتلاند": "ALEX.CA", "الاسماعيلية مصر للدواجن": "ISMA.CA",
    "البنك التجاري الدولي": "COMI.CA", "التعمير والاستشارات الهندسية": "DAPH.CA",
    "الجوهرة - العز للسيراميك": "ECAP.CA", "الجيزة العامة للمقاولات": "GGCC.CA",
    "الزيوت المستخلصة ومنتجاتها": "ZEOT.CA", "السويدي إليكتريك": "SWDY.CA",
    "الشرقية - إيسترن كومباني": "EAST.CA", "الشمس للإسكان والتعمير": "ELSH.CA",
    "الصعيد العامة للمقاولات": "UEGC.CA", "العبوات الطبية": "MEPA.CA",
    "العربية للأدوية": "ADCI.CA", "العز الدخيلة للصلب": "IRAX.CA",
    "القاهرة للإسكان والتعمير": "ELKA.CA", "القاهرة للدواجن": "POUL.CA",
    "القلعة للاستشارات المالية": "CCAP.CA", "المصرية للاتصالات": "ETEL.CA",
    "المطورون العرب القابضة": "ARAB.CA", "المنصورة للدواجن": "MPCO.CA",
    "النيل للأدوية": "NIPH.CA", "بالم هيلز للتعمير": "PHDC.CA",
    "بلتون المالية القابضة": "BTFH.CA", "بنك البركة مصر": "SAUD.CA",
    "بنك التعمير والإسكان": "HDBK.CA", "بنك فيصل الإسلامي - بالجنيه": "FAIT.CA",
    "بنك قناة السويس": "CANA.CA", "جهينة للصناعات الغذائية": "JUFO.CA",
    "جي بي كورب": "GBCO.CA", "حديد عز": "ESRS.CA",
    "دومتي": "DOMT.CA", "راكتا لورق التعبئة": "RAKT.CA",
    "سيدي كرير للبتروكيماويات": "SKPC.CA", "شمال أفريقيا للاستثمار": "NATI.CA",
    "صناع التغليف - يونيفرت": "UNIP.CA", "طاقة عربية": "TAQA.CA",
    "عبر المحيطات للمقاولات": "GOCE.CA", "غاز مصر": "EGAS.CA",
    "فاركو للأدوية": "PHAR.CA", "فوري للمدفوعات الإلكترونية": "FWRY.CA",
    "كيما - الصناعات الكيماوية": "EGCH.CA", "مجموعة إيـفـإى جـي هيرميس": "HRHO.CA",
    "مجموعة طلعت مصطفى": "TMGH.CA", "مدينة مصر للإسكان": "MASR.CA",
    "مصر الجديدة للإسكان": "HELI.CA", "مصر لإنتاج الأسمدة - موبكو": "MFPC.CA",
    "مصر للألومنيوم": "EGAL.CA", "مصرف أبوظبي الإسلامي": "ADIB.CA",
    "مطاحن مصر الوسطى": "CEFM.CA", "مطاحن ومخابز شمال القاهرة": "MNSF.CA",
}

# نرتب حسب رمز السهم (مش اسم الشركة) عشان الترتيب يبقى ثابت ومتسق
# سواء كان اسم الشركة عربي أو إنجليزي (خلاف كده بيطلع ترتيب غريب لخلط اللغتين)
ALL_EGX_STOCKS = dict(sorted(ALL_EGX_STOCKS.items(), key=lambda kv: kv[1]))

# تصنيف قطاعي لكل سهم (مكتوب مباشرة هنا زي قائمة الأسهم - بدون ملف خارجي).
# أي سهم مش موجود في القاموس ده (زي الأسهم المضافة يدوياً بعد آخر تحديث)
# هياخد تصنيف "غير مصنف" تلقائياً بدل ما يسبب خطأ.
TICKER_SECTOR = {
    "COMI.CA": "بنوك", "TMGH.CA": "عقاري", "SWDY.CA": "تصنيع", "ETEL.CA": "تكنولوجيا",
    "EGAL.CA": "تصنيع", "MFPC.CA": "تصنيع", "QNBE.CA": "بنوك", "EAST.CA": "استهلاكي",
    "ABUK.CA": "تصنيع", "ALCN.CA": "تصنيع", "ORAS.CA": "تصنيع", "EFIH.CA": "تكنولوجيا",
    "HDBK.CA": "بنوك", "FWRY.CA": "تكنولوجيا", "EMFD.CA": "عقاري", "SCTS.CA": "تكنولوجيا",
    "ADIB.CA": "بنوك", "PHDC.CA": "عقاري", "ORHD.CA": "عقاري", "GPPL.CA": "عقاري",
    "VLMR.CA": "مالي غير مصرفي", "VLMRA.CA": "مالي غير مصرفي", "EFID.CA": "استهلاكي", "HRHO.CA": "مالي غير مصرفي",
    "CANA.CA": "بنوك", "JUFO.CA": "استهلاكي", "BTFH.CA": "مالي غير مصرفي", "IRON.CA": "تصنيع",
    "RAYA.CA": "تكنولوجيا", "FERC.CA": "تصنيع", "EGCH.CA": "تصنيع", "CIEB.CA": "بنوك",
    "FAIT.CA": "بنوك", "FAITA.CA": "بنوك", "GBCO.CA": "تصنيع", "OCDI.CA": "عقاري",
    "HELI.CA": "عقاري", "VALU.CA": "مالي غير مصرفي", "EXPA.CA": "بنوك", "CLHO.CA": "استهلاكي",
    "EGTS.CA": "عقاري", "CCAP.CA": "مالي غير مصرفي", "ARCC.CA": "تصنيع", "EFIC.CA": "مالي غير مصرفي",
    "SKPC.CA": "تصنيع", "MCQE.CA": "تصنيع", "TAQA.CA": "تصنيع", "POUL.CA": "استهلاكي",
    "EGSA.CA": "تكنولوجيا", "MTIE.CA": "تكنولوجيا", "SCEM.CA": "تصنيع", "SAUD.CA": "بنوك",
    "ORWE.CA": "تصنيع", "CIRA.CA": "استهلاكي", "MASR.CA": "عقاري", "UBEE.CA": "بنوك",
    "PHAR.CA": "استهلاكي", "MBSC.CA": "تصنيع", "MHOT.CA": "استهلاكي", "CICH.CA": "مالي غير مصرفي",
    "ISPH.CA": "استهلاكي", "EGBE.CA": "بنوك", "TALM.CA": "استهلاكي", "ATQA.CA": "تصنيع",
    "MOIL.CA": "تصنيع", "AMOC.CA": "تصنيع", "BINV.CA": "عقاري", "RMDA.CA": "استهلاكي",
    "IFAP.CA": "استهلاكي", "BONY.CA": "عقاري", "CSAG.CA": "تصنيع", "OLFI.CA": "استهلاكي",
    "SPHT.CA": "استهلاكي", "NIPH.CA": "استهلاكي", "ISMQ.CA": "تصنيع", "MIPH.CA": "استهلاكي",
    "OIH.CA": "مالي غير مصرفي", "ACAP.CA": "مالي غير مصرفي", "SUGR.CA": "استهلاكي", "EGAS.CA": "تصنيع",
    "DOMT.CA": "استهلاكي", "ELEC.CA": "تصنيع", "MOIN.CA": "مالي غير مصرفي", "AMES.CA": "استهلاكي",
    "PRDC.CA": "عقاري", "MPRC.CA": "تكنولوجيا", "BIOC.CA": "استهلاكي", "ZMID.CA": "عقاري",
    "NAPR.CA": "تصنيع", "AXPH.CA": "استهلاكي", "NINH.CA": "استهلاكي", "CNFN.CA": "مالي غير مصرفي",
    "GOUR.CA": "استهلاكي", "CPCI.CA": "استهلاكي", "SPIN.CA": "تصنيع", "PHTV.CA": "عقاري",
    "ENGC.CA": "تصنيع", "DSCW.CA": "تصنيع", "MFSC.CA": "استهلاكي", "MPCI.CA": "استهلاكي",
    "SVCE.CA": "تصنيع", "AMIA.CA": "مالي غير مصرفي", "GSSC.CA": "تصنيع", "OCPH.CA": "استهلاكي",
    "GDWA.CA": "عقاري", "MICH.CA": "تصنيع", "WCDF.CA": "استهلاكي", "SAIB.CA": "بنوك",
    "KABO.CA": "تصنيع", "UEFM.CA": "استهلاكي", "UNIT.CA": "عقاري", "ACAMD.CA": "عقاري",
    "ACTF.CA": "مالي غير مصرفي", "ARAB.CA": "عقاري", "OFH.CA": "مالي غير مصرفي", "AJWA.CA": "استهلاكي",
    "AMER.CA": "عقاري", "KZPC.CA": "تصنيع", "ACGC.CA": "تصنيع", "ADCI.CA": "استهلاكي",
    "CFGH.CA": "تصنيع", "ELSH.CA": "عقاري", "ASCM.CA": "تصنيع", "AFMC.CA": "استهلاكي",
    "ISMA.CA": "استهلاكي", "SDTI.CA": "مالي غير مصرفي", "ELKA.CA": "عقاري", "LCSW.CA": "تصنيع",
    "GGRN.CA": "مالي غير مصرفي", "INFI.CA": "استهلاكي", "PHGC.CA": "استهلاكي", "SNFC.CA": "استهلاكي",
    "NAHO.CA": "مالي غير مصرفي", "EDFM.CA": "استهلاكي", "ETRS.CA": "تصنيع", "SMFR.CA": "تصنيع",
    "ATLC.CA": "مالي غير مصرفي", "RACC.CA": "مالي غير مصرفي", "DAPH.CA": "عقاري", "EALR.CA": "استهلاكي",
    "ZEOT.CA": "استهلاكي", "ADPC.CA": "استهلاكي", "EHDR.CA": "عقاري", "IDRE.CA": "عقاري",
    "MENA.CA": "عقاري", "WKOL.CA": "استهلاكي", "MOSC.CA": "استهلاكي", "MPCO.CA": "استهلاكي",
    "ECAP.CA": "تصنيع", "CEFM.CA": "استهلاكي", "SCFM.CA": "استهلاكي", "GPIM.CA": "عقاري",
    "MILS.CA": "استهلاكي", "OBRI.CA": "مالي غير مصرفي", "DEIN.CA": "مالي غير مصرفي", "CRST.CA": "عقاري",
    "AALR.CA": "عقاري", "CERA.CA": "تصنيع", "NARE.CA": "مالي غير مصرفي", "PRCL.CA": "تصنيع",
    "NDRL.CA": "تصنيع", "ALRA.CA": "مالي غير مصرفي", "ODIN.CA": "مالي غير مصرفي", "NCCW.CA": "تصنيع",
    "MAAL.CA": "مالي غير مصرفي", "MEPA.CA": "استهلاكي", "NHPS.CA": "عقاري", "ALUM.CA": "تصنيع",
    "SEIGA.CA": "مالي غير مصرفي", "POCO.CA": "تصنيع", "COSG.CA": "استهلاكي", "AIDC.CA": "مالي غير مصرفي",
    "UEGC.CA": "مالي غير مصرفي", "RTVC.CA": "استهلاكي", "SEIG.CA": "مالي غير مصرفي", "EBSC.CA": "مالي غير مصرفي",
    "PRMH.CA": "مالي غير مصرفي", "SIPC.CA": "استهلاكي", "GGCC.CA": "مالي غير مصرفي", "RREI.CA": "مالي غير مصرفي",
    "CAED.CA": "استهلاكي", "GTEX.CA": "مالي غير مصرفي", "APSW.CA": "تصنيع", "AFDI.CA": "مالي غير مصرفي",
    "MEGM.CA": "تصنيع", "ICLE.CA": "مالي غير مصرفي", "ARVA.CA": "تصنيع", "ANFI.CA": "مالي غير مصرفي",
    "TANM.CA": "مالي غير مصرفي", "MCRO.CA": "مالي غير مصرفي", "MOED.CA": "استهلاكي", "DTPP.CA": "تصنيع",
    "KRDI.CA": "مالي غير مصرفي", "GTWL.CA": "تصنيع", "RAKT.CA": "تصنيع", "SPMD.CA": "استهلاكي",
    "UNIP.CA": "تصنيع", "RUBX.CA": "تصنيع", "ROTO.CA": "استهلاكي", "KWIN.CA": "مالي غير مصرفي",
    "ASPI.CA": "مالي غير مصرفي", "ICID.CA": "مالي غير مصرفي", "AIHC.CA": "مالي غير مصرفي", "AREH.CA": "عقاري",
    "EEII.CA": "تصنيع", "CCRS.CA": "مالي غير مصرفي", "EASB.CA": "مالي غير مصرفي", "GRCA.CA": "مالي غير مصرفي",
    "EPCO.CA": "استهلاكي", "ELWA.CA": "مالي غير مصرفي", "LUTS.CA": "مالي غير مصرفي", "ELNA.CA": "استهلاكي",
    "DGTZ.CA": "تكنولوجيا", "GIHD.CA": "عقاري", "DCCC.CA": "تصنيع", "NEDA.CA": "عقاري",
    "TRTO.CA": "استهلاكي", "MMAT.CA": "عقاري", "EPPK.CA": "تصنيع", "GMCI.CA": "مالي غير مصرفي",
    "EOSB.CA": "مالي غير مصرفي", "CPME.CA": "مالي غير مصرفي", "COPR.CA": "مالي غير مصرفي",
}

# ---------------------------------------------------------------------------
# أسواق إضافية: أمريكا (S&P 500) والإمارات (DFM + ADX)
# نفس أسلوب مصر بالظبط: أسماء الشركات ورموزها وتصنيفها القطاعي مكتوبين
# مباشرة هنا في الكود - بدون أي ملف خارجي.
# ---------------------------------------------------------------------------

# --- أمريكا: S&P 500 (502 شركة) ---
US_STOCKS = {
    "3M": "MMM", "A. O. Smith": "AOS", "Abbott Laboratories": "ABT",
    "AbbVie": "ABBV", "Accenture": "ACN", "Adobe Inc.": "ADBE",
    "Advanced Micro Devices": "AMD", "AES Corporation": "AES", "Aflac": "AFL",
    "Agilent Technologies": "A", "Air Products": "APD", "Airbnb": "ABNB",
    "Akamai Technologies": "AKAM", "Albemarle Corporation": "ALB", "Alexandria Real Estate Equities": "ARE",
    "Align Technology": "ALGN", "Allegion": "ALLE", "Alliant Energy": "LNT",
    "Allstate": "ALL", "Alphabet Inc. (Class A)": "GOOGL", "Alphabet Inc. (Class C)": "GOOG",
    "Altria": "MO", "Amazon": "AMZN", "Amcor": "AMCR",
    "Ameren": "AEE", "American Electric Power": "AEP", "American Express": "AXP",
    "American International Group": "AIG", "American Tower": "AMT", "American Water Works": "AWK",
    "Ameriprise Financial": "AMP", "Ametek": "AME", "Amgen": "AMGN",
    "Amphenol": "APH", "Analog Devices": "ADI", "Aon plc": "AON",
    "APA Corporation": "APA", "Apollo Global Management": "APO", "Apple Inc.": "AAPL",
    "Applied Materials": "AMAT", "AppLovin": "APP", "Aptiv": "APTV",
    "Arch Capital Group": "ACGL", "Archer Daniels Midland": "ADM", "Ares Management": "ARES",
    "Arista Networks": "ANET", "Arthur J. Gallagher & Co.": "AJG", "Assurant": "AIZ",
    "AT&T": "T", "Atmos Energy": "ATO", "Autodesk": "ADSK",
    "Automatic Data Processing": "ADP", "AutoZone": "AZO", "AvalonBay Communities": "AVB",
    "Avery Dennison": "AVY", "Axon Enterprise": "AXON", "Baker Hughes": "BKR",
    "Ball Corporation": "BALL", "Bank of America": "BAC", "Baxter International": "BAX",
    "Becton Dickinson": "BDX", "Berkshire Hathaway": "BRK-B", "Best Buy": "BBY",
    "Bio-Techne": "TECH", "Biogen": "BIIB", "BlackRock": "BLK",
    "Blackstone Inc.": "BX", "Block, Inc.": "XYZ", "BNY Mellon": "BNY",
    "Boeing": "BA", "Booking Holdings": "BKNG", "Boston Scientific": "BSX",
    "Bristol Myers Squibb": "BMY", "Broadcom": "AVGO", "Broadridge Financial Solutions": "BR",
    "Brown & Brown": "BRO", "Brown-Forman": "BF-B", "Builders FirstSource": "BLDR",
    "Bunge Global": "BG", "BXP, Inc.": "BXP", "C.H. Robinson": "CHRW",
    "Cadence Design Systems": "CDNS", "Camden Property Trust": "CPT", "Campbell's Company (The)": "CPB",
    "Capital One": "COF", "Cardinal Health": "CAH", "Carnival Corporation": "CCL",
    "Carrier Global": "CARR", "Carvana": "CVNA", "Casey's": "CASY",
    "Caterpillar Inc.": "CAT", "Cboe Global Markets": "CBOE", "CBRE Group": "CBRE",
    "CDW Corporation": "CDW", "Cencora": "COR", "Centene Corporation": "CNC",
    "CenterPoint Energy": "CNP", "CF Industries": "CF", "Charles River Laboratories": "CRL",
    "Charles Schwab Corporation": "SCHW", "Charter Communications": "CHTR", "Chevron Corporation": "CVX",
    "Chipotle Mexican Grill": "CMG", "Chubb Limited": "CB", "Church & Dwight": "CHD",
    "Ciena": "CIEN", "Cigna": "CI", "Cincinnati Financial": "CINF",
    "Cintas": "CTAS", "Cisco": "CSCO", "Citigroup": "C",
    "Citizens Financial Group": "CFG", "Clorox": "CLX", "CME Group": "CME",
    "CMS Energy": "CMS", "Coca-Cola Company (The)": "KO", "Cognizant": "CTSH",
    "Coherent Corp.": "COHR", "Coinbase": "COIN", "Colgate-Palmolive": "CL",
    "Comcast": "CMCSA", "Comfort Systems USA": "FIX", "Conagra Brands": "CAG",
    "ConocoPhillips": "COP", "Consolidated Edison": "ED", "Constellation Brands": "STZ",
    "Constellation Energy": "CEG", "Cooper Companies (The)": "COO", "Copart": "CPRT",
    "Corning Inc.": "GLW", "Corpay": "CPAY", "Corteva": "CTVA",
    "CoStar Group": "CSGP", "Costco": "COST", "CRH plc": "CRH",
    "CrowdStrike": "CRWD", "Crown Castle": "CCI", "CSX Corporation": "CSX",
    "Cummins": "CMI", "CVS Health": "CVS", "Danaher Corporation": "DHR",
    "Darden Restaurants": "DRI", "Datadog": "DDOG", "DaVita": "DVA",
    "Deckers Brands": "DECK", "Deere & Company": "DE", "Dell Technologies": "DELL",
    "Delta Air Lines": "DAL", "Devon Energy": "DVN", "Dexcom": "DXCM",
    "Diamondback Energy": "FANG", "Digital Realty": "DLR", "Dollar General": "DG",
    "Dollar Tree": "DLTR", "Dominion Energy": "D", "Domino's": "DPZ",
    "DoorDash": "DASH", "Dover Corporation": "DOV", "Dow Inc.": "DOW",
    "D. R. Horton": "DHI", "DTE Energy": "DTE", "Duke Energy": "DUK",
    "DuPont": "DD", "Eaton Corporation": "ETN", "eBay Inc.": "EBAY",
    "EchoStar": "SATS", "Ecolab": "ECL", "Edison International": "EIX",
    "Edwards Lifesciences": "EW", "Electronic Arts": "EA", "Elevance Health": "ELV",
    "Emcor": "EME", "Emerson Electric": "EMR", "Entergy": "ETR",
    "EOG Resources": "EOG", "EPAM Systems": "EPAM", "EQT Corporation": "EQT",
    "Equifax": "EFX", "Equinix": "EQIX", "Equity Residential": "EQR",
    "Erie Indemnity": "ERIE", "Essex Property Trust": "ESS", "Estee Lauder Companies (The)": "EL",
    "Everest Group": "EG", "Evergy": "EVRG", "Eversource Energy": "ES",
    "Exelon": "EXC", "Expand Energy": "EXE", "Expedia Group": "EXPE",
    "Expeditors International": "EXPD", "Extra Space Storage": "EXR", "ExxonMobil": "XOM",
    "F5, Inc.": "FFIV", "FactSet": "FDS", "Fair Isaac": "FICO",
    "Fastenal": "FAST", "Federal Realty Investment Trust": "FRT", "FedEx": "FDX",
    "Fidelity National Information Services": "FIS", "Fifth Third Bancorp": "FITB", "First Solar": "FSLR",
    "FirstEnergy": "FE", "Fiserv": "FISV", "Ford Motor Company": "F",
    "Fortinet": "FTNT", "Fortive": "FTV", "Fox Corporation (Class A)": "FOXA",
    "Fox Corporation (Class B)": "FOX", "Franklin Resources": "BEN", "Freeport-McMoRan": "FCX",
    "Garmin": "GRMN", "Gartner": "IT", "GE Aerospace": "GE",
    "GE HealthCare": "GEHC", "GE Vernova": "GEV", "Gen Digital": "GEN",
    "Generac": "GNRC", "General Dynamics": "GD", "General Mills": "GIS",
    "General Motors": "GM", "Genuine Parts Company": "GPC", "Gilead Sciences": "GILD",
    "Global Payments": "GPN", "Globe Life": "GL", "GoDaddy": "GDDY",
    "Goldman Sachs": "GS", "Halliburton": "HAL", "Hartford (The)": "HIG",
    "Hasbro": "HAS", "HCA Healthcare": "HCA", "Healthpeak Properties": "DOC",
    "Henry Schein": "HSIC", "Hershey Company (The)": "HSY", "Hewlett Packard Enterprise": "HPE",
    "Hilton Worldwide": "HLT", "Home Depot (The)": "HD", "Honeywell": "HON",
    "Hormel Foods": "HRL", "Host Hotels & Resorts": "HST", "Howmet Aerospace": "HWM",
    "HP Inc.": "HPQ", "Hubbell Incorporated": "HUBB", "Humana": "HUM",
    "Huntington Bancshares": "HBAN", "Huntington Ingalls Industries": "HII", "IBM": "IBM",
    "IDEX Corporation": "IEX", "Idexx Laboratories": "IDXX", "Illinois Tool Works": "ITW",
    "Incyte": "INCY", "Ingersoll Rand": "IR", "Insulet Corporation": "PODD",
    "Intel": "INTC", "Interactive Brokers": "IBKR", "Intercontinental Exchange": "ICE",
    "International Flavors & Fragrances": "IFF", "International Paper": "IP", "Intuit": "INTU",
    "Intuitive Surgical": "ISRG", "Invesco": "IVZ", "Invitation Homes": "INVH",
    "IQVIA": "IQV", "Iron Mountain": "IRM", "J.B. Hunt": "JBHT",
    "Jabil": "JBL", "Jack Henry & Associates": "JKHY", "Jacobs Solutions": "J",
    "Johnson & Johnson": "JNJ", "Johnson Controls": "JCI", "JPMorgan Chase": "JPM",
    "Kenvue": "KVUE", "Keurig Dr Pepper": "KDP", "KeyCorp": "KEY",
    "Keysight Technologies": "KEYS", "Kimberly-Clark": "KMB", "Kimco Realty": "KIM",
    "Kinder Morgan": "KMI", "KKR & Co.": "KKR", "KLA Corporation": "KLAC",
    "Kraft Heinz": "KHC", "Kroger": "KR", "L3Harris": "LHX",
    "Labcorp": "LH", "Lam Research": "LRCX", "Las Vegas Sands": "LVS",
    "Leidos": "LDOS", "Lennar": "LEN", "Lennox International": "LII",
    "Lilly (Eli)": "LLY", "Linde plc": "LIN", "Live Nation Entertainment": "LYV",
    "Lockheed Martin": "LMT", "Loews Corporation": "L", "Lowe's": "LOW",
    "Lululemon Athletica": "LULU", "Lumentum": "LITE", "LyondellBasell": "LYB",
    "M&T Bank": "MTB", "Marathon Petroleum": "MPC", "Marriott International": "MAR",
    "Marsh McLennan": "MRSH", "Martin Marietta Materials": "MLM", "Masco": "MAS",
    "Mastercard": "MA", "McCormick & Company": "MKC", "McDonald's": "MCD",
    "McKesson Corporation": "MCK", "Medtronic": "MDT", "Merck & Co.": "MRK",
    "Meta Platforms": "META", "MetLife": "MET", "Mettler Toledo": "MTD",
    "MGM Resorts": "MGM", "Microchip Technology": "MCHP", "Micron Technology": "MU",
    "Microsoft": "MSFT", "Mid-America Apartment Communities": "MAA", "Moderna": "MRNA",
    "Molson Coors Beverage Company": "TAP", "Mondelez International": "MDLZ", "Monolithic Power Systems": "MPWR",
    "Monster Beverage": "MNST", "Moody's Corporation": "MCO", "Morgan Stanley": "MS",
    "Mosaic Company (The)": "MOS", "Motorola Solutions": "MSI", "MSCI Inc.": "MSCI",
    "Nasdaq, Inc.": "NDAQ", "NetApp": "NTAP", "Netflix": "NFLX",
    "Newmont": "NEM", "News Corp (Class A)": "NWSA", "News Corp (Class B)": "NWS",
    "NextEra Energy": "NEE", "Nike, Inc.": "NKE", "NiSource": "NI",
    "Nordson Corporation": "NDSN", "Norfolk Southern": "NSC", "Northern Trust": "NTRS",
    "Northrop Grumman": "NOC", "Norwegian Cruise Line Holdings": "NCLH", "NRG Energy": "NRG",
    "Nucor": "NUE", "Nvidia": "NVDA", "NVR, Inc.": "NVR",
    "NXP Semiconductors": "NXPI", "O'Reilly Automotive": "ORLY", "Occidental Petroleum": "OXY",
    "Old Dominion": "ODFL", "Omnicom Group": "OMC", "ON Semiconductor": "ON",
    "Oneok": "OKE", "Oracle Corporation": "ORCL", "Otis Worldwide": "OTIS",
    "Paccar": "PCAR", "Packaging Corporation of America": "PKG", "Palantir Technologies": "PLTR",
    "Palo Alto Networks": "PANW", "Paramount Skydance Corporation": "PSKY", "Parker Hannifin": "PH",
    "Paychex": "PAYX", "PayPal": "PYPL", "Pentair": "PNR",
    "PepsiCo": "PEP", "Pfizer": "PFE", "PG&E Corporation": "PCG",
    "Philip Morris International": "PM", "Phillips 66": "PSX", "Pinnacle West Capital": "PNW",
    "PNC Financial Services": "PNC", "Pool Corporation": "POOL", "PPG Industries": "PPG",
    "PPL Corporation": "PPL", "Principal Financial Group": "PFG", "Procter & Gamble": "PG",
    "Progressive Corporation": "PGR", "Prologis": "PLD", "Prudential Financial": "PRU",
    "Public Service Enterprise Group": "PEG", "PTC Inc.": "PTC", "Public Storage": "PSA",
    "PulteGroup": "PHM", "Quanta Services": "PWR", "Qualcomm": "QCOM",
    "Quest Diagnostics": "DGX", "Ralph Lauren Corporation": "RL", "Raymond James Financial": "RJF",
    "RTX Corporation": "RTX", "Realty Income": "O", "Regency Centers": "REG",
    "Regeneron Pharmaceuticals": "REGN", "Regions Financial Corporation": "RF", "Republic Services": "RSG",
    "ResMed": "RMD", "Revvity": "RVTY", "Robinhood Markets": "HOOD",
    "Rockwell Automation": "ROK", "Rollins, Inc.": "ROL", "Roper Technologies": "ROP",
    "Ross Stores": "ROST", "Royal Caribbean Group": "RCL", "S&P Global": "SPGI",
    "Salesforce": "CRM", "Sandisk": "SNDK", "SBA Communications": "SBAC",
    "Schlumberger": "SLB", "Seagate Technology": "STX", "Sempra": "SRE",
    "ServiceNow": "NOW", "Sherwin-Williams": "SHW", "Simon Property Group": "SPG",
    "Skyworks Solutions": "SWKS", "J.M. Smucker Company (The)": "SJM", "Smurfit Westrock": "SW",
    "Snap-on": "SNA", "Solventum": "SOLV", "Southern Company": "SO",
    "Southwest Airlines": "LUV", "Stanley Black & Decker": "SWK", "Starbucks": "SBUX",
    "State Street Corporation": "STT", "Steel Dynamics": "STLD", "Steris": "STE",
    "Stryker Corporation": "SYK", "Supermicro": "SMCI", "Synchrony Financial": "SYF",
    "Synopsys": "SNPS", "Sysco": "SYY", "T-Mobile US": "TMUS",
    "T. Rowe Price": "TROW", "Take-Two Interactive": "TTWO", "Tapestry, Inc.": "TPR",
    "Targa Resources": "TRGP", "Target Corporation": "TGT", "TE Connectivity": "TEL",
    "Teledyne Technologies": "TDY", "Teradyne": "TER", "Tesla, Inc.": "TSLA",
    "Texas Instruments": "TXN", "Texas Pacific Land Corporation": "TPL", "Textron": "TXT",
    "Thermo Fisher Scientific": "TMO", "TJX Companies": "TJX", "TKO Group Holdings": "TKO",
    "Trade Desk (The)": "TTD", "Tractor Supply": "TSCO", "Trane Technologies": "TT",
    "TransDigm Group": "TDG", "Travelers Companies (The)": "TRV", "Trimble Inc.": "TRMB",
    "Truist Financial": "TFC", "Tyler Technologies": "TYL", "Tyson Foods": "TSN",
    "U.S. Bancorp": "USB", "Uber": "UBER", "UDR, Inc.": "UDR",
    "Ulta Beauty": "ULTA", "Union Pacific Corporation": "UNP", "United Airlines Holdings": "UAL",
    "United Parcel Service": "UPS", "United Rentals": "URI", "UnitedHealth Group": "UNH",
    "Universal Health Services": "UHS", "Valero Energy": "VLO", "Veeva Systems": "VEEV",
    "Ventas": "VTR", "Veralto": "VLTO", "Verisign": "VRSN",
    "Verisk Analytics": "VRSK", "Verizon": "VZ", "Vertex Pharmaceuticals": "VRTX",
    "Vertiv": "VRT", "Viatris": "VTRS", "Vici Properties": "VICI",
    "Visa Inc.": "V", "Vistra Corp.": "VST", "Vulcan Materials Company": "VMC",
    "W. R. Berkley Corporation": "WRB", "W. W. Grainger": "GWW", "Wabtec": "WAB",
    "Walmart": "WMT", "Walt Disney Company (The)": "DIS", "Warner Bros. Discovery": "WBD",
    "Waste Management": "WM", "Waters Corporation": "WAT", "WEC Energy Group": "WEC",
    "Wells Fargo": "WFC", "Welltower": "WELL", "West Pharmaceutical Services": "WST",
    "Western Digital": "WDC", "Weyerhaeuser": "WY", "Williams-Sonoma, Inc.": "WSM",
    "Williams Companies": "WMB", "Willis Towers Watson": "WTW", "Workday, Inc.": "WDAY",
    "Wynn Resorts": "WYNN", "Xcel Energy": "XEL", "Xylem Inc.": "XYL",
    "Yum! Brands": "YUM", "Zebra Technologies": "ZBRA", "Zimmer Biomet": "ZBH",
    "Zoetis": "ZTS",
}

US_SECTOR = {
    "MMM": "تصنيع", "AOS": "تصنيع", "ABT": "استهلاكي", "ABBV": "استهلاكي",
    "ACN": "تكنولوجيا", "ADBE": "تكنولوجيا", "AMD": "تكنولوجيا", "AES": "تصنيع",
    "AFL": "مالي غير مصرفي", "A": "استهلاكي", "APD": "تصنيع", "ABNB": "استهلاكي",
    "AKAM": "تكنولوجيا", "ALB": "تصنيع", "ARE": "عقاري", "ALGN": "استهلاكي",
    "ALLE": "تصنيع", "LNT": "تصنيع", "ALL": "مالي غير مصرفي", "GOOGL": "تكنولوجيا",
    "GOOG": "تكنولوجيا", "MO": "استهلاكي", "AMZN": "استهلاكي", "AMCR": "تصنيع",
    "AEE": "تصنيع", "AEP": "تصنيع", "AXP": "مالي غير مصرفي", "AIG": "مالي غير مصرفي",
    "AMT": "عقاري", "AWK": "تصنيع", "AMP": "بنوك", "AME": "تصنيع",
    "AMGN": "استهلاكي", "APH": "تكنولوجيا", "ADI": "تكنولوجيا", "AON": "مالي غير مصرفي",
    "APA": "تصنيع", "APO": "بنوك", "AAPL": "تكنولوجيا", "AMAT": "تكنولوجيا",
    "APP": "تكنولوجيا", "APTV": "استهلاكي", "ACGL": "مالي غير مصرفي", "ADM": "استهلاكي",
    "ARES": "بنوك", "ANET": "تكنولوجيا", "AJG": "مالي غير مصرفي", "AIZ": "مالي غير مصرفي",
    "T": "تكنولوجيا", "ATO": "تصنيع", "ADSK": "تكنولوجيا", "ADP": "تصنيع",
    "AZO": "استهلاكي", "AVB": "عقاري", "AVY": "تصنيع", "AXON": "تصنيع",
    "BKR": "تصنيع", "BALL": "تصنيع", "BAC": "بنوك", "BAX": "استهلاكي",
    "BDX": "استهلاكي", "BRK-B": "مالي غير مصرفي", "BBY": "استهلاكي", "TECH": "استهلاكي",
    "BIIB": "استهلاكي", "BLK": "بنوك", "BX": "بنوك", "XYZ": "مالي غير مصرفي",
    "BNY": "بنوك", "BA": "تصنيع", "BKNG": "استهلاكي", "BSX": "استهلاكي",
    "BMY": "استهلاكي", "AVGO": "تكنولوجيا", "BR": "تصنيع", "BRO": "مالي غير مصرفي",
    "BF-B": "استهلاكي", "BLDR": "تصنيع", "BG": "استهلاكي", "BXP": "عقاري",
    "CHRW": "تصنيع", "CDNS": "تكنولوجيا", "CPT": "عقاري", "CPB": "استهلاكي",
    "COF": "مالي غير مصرفي", "CAH": "استهلاكي", "CCL": "استهلاكي", "CARR": "تصنيع",
    "CVNA": "استهلاكي", "CASY": "استهلاكي", "CAT": "تصنيع", "CBOE": "مالي غير مصرفي",
    "CBRE": "عقاري", "CDW": "تكنولوجيا", "COR": "استهلاكي", "CNC": "استهلاكي",
    "CNP": "تصنيع", "CF": "تصنيع", "CRL": "استهلاكي", "SCHW": "بنوك",
    "CHTR": "تكنولوجيا", "CVX": "تصنيع", "CMG": "استهلاكي", "CB": "مالي غير مصرفي",
    "CHD": "استهلاكي", "CIEN": "تكنولوجيا", "CI": "استهلاكي", "CINF": "مالي غير مصرفي",
    "CTAS": "تصنيع", "CSCO": "تكنولوجيا", "C": "بنوك", "CFG": "بنوك",
    "CLX": "استهلاكي", "CME": "مالي غير مصرفي", "CMS": "تصنيع", "KO": "استهلاكي",
    "CTSH": "تكنولوجيا", "COHR": "تكنولوجيا", "COIN": "مالي غير مصرفي", "CL": "استهلاكي",
    "CMCSA": "تكنولوجيا", "FIX": "تصنيع", "CAG": "استهلاكي", "COP": "تصنيع",
    "ED": "تصنيع", "STZ": "استهلاكي", "CEG": "تصنيع", "COO": "استهلاكي",
    "CPRT": "تصنيع", "GLW": "تكنولوجيا", "CPAY": "مالي غير مصرفي", "CTVA": "تصنيع",
    "CSGP": "عقاري", "COST": "استهلاكي", "CRH": "تصنيع", "CRWD": "تكنولوجيا",
    "CCI": "عقاري", "CSX": "تصنيع", "CMI": "تصنيع", "CVS": "استهلاكي",
    "DHR": "استهلاكي", "DRI": "استهلاكي", "DDOG": "تكنولوجيا", "DVA": "استهلاكي",
    "DECK": "استهلاكي", "DE": "تصنيع", "DELL": "تكنولوجيا", "DAL": "تصنيع",
    "DVN": "تصنيع", "DXCM": "استهلاكي", "FANG": "تصنيع", "DLR": "عقاري",
    "DG": "استهلاكي", "DLTR": "استهلاكي", "D": "تصنيع", "DPZ": "استهلاكي",
    "DASH": "استهلاكي", "DOV": "تصنيع", "DOW": "تصنيع", "DHI": "استهلاكي",
    "DTE": "تصنيع", "DUK": "تصنيع", "DD": "تصنيع", "ETN": "تصنيع",
    "EBAY": "استهلاكي", "SATS": "تكنولوجيا", "ECL": "تصنيع", "EIX": "تصنيع",
    "EW": "استهلاكي", "EA": "تكنولوجيا", "ELV": "استهلاكي", "EME": "تصنيع",
    "EMR": "تصنيع", "ETR": "تصنيع", "EOG": "تصنيع", "EPAM": "تكنولوجيا",
    "EQT": "تصنيع", "EFX": "تصنيع", "EQIX": "عقاري", "EQR": "عقاري",
    "ERIE": "مالي غير مصرفي", "ESS": "عقاري", "EL": "استهلاكي", "EG": "مالي غير مصرفي",
    "EVRG": "تصنيع", "ES": "تصنيع", "EXC": "تصنيع", "EXE": "تصنيع",
    "EXPE": "استهلاكي", "EXPD": "تصنيع", "EXR": "عقاري", "XOM": "تصنيع",
    "FFIV": "تكنولوجيا", "FDS": "مالي غير مصرفي", "FICO": "تكنولوجيا", "FAST": "تصنيع",
    "FRT": "عقاري", "FDX": "تصنيع", "FIS": "مالي غير مصرفي", "FITB": "بنوك",
    "FSLR": "تكنولوجيا", "FE": "تصنيع", "FISV": "مالي غير مصرفي", "F": "استهلاكي",
    "FTNT": "تكنولوجيا", "FTV": "تصنيع", "FOXA": "تكنولوجيا", "FOX": "تكنولوجيا",
    "BEN": "بنوك", "FCX": "تصنيع", "GRMN": "استهلاكي", "IT": "تكنولوجيا",
    "GE": "تصنيع", "GEHC": "استهلاكي", "GEV": "تصنيع", "GEN": "تكنولوجيا",
    "GNRC": "تصنيع", "GD": "تصنيع", "GIS": "استهلاكي", "GM": "استهلاكي",
    "GPC": "استهلاكي", "GILD": "استهلاكي", "GPN": "مالي غير مصرفي", "GL": "مالي غير مصرفي",
    "GDDY": "تكنولوجيا", "GS": "بنوك", "HAL": "تصنيع", "HIG": "مالي غير مصرفي",
    "HAS": "استهلاكي", "HCA": "استهلاكي", "DOC": "عقاري", "HSIC": "استهلاكي",
    "HSY": "استهلاكي", "HPE": "تكنولوجيا", "HLT": "استهلاكي", "HD": "استهلاكي",
    "HON": "تصنيع", "HRL": "استهلاكي", "HST": "عقاري", "HWM": "تصنيع",
    "HPQ": "تكنولوجيا", "HUBB": "تصنيع", "HUM": "استهلاكي", "HBAN": "بنوك",
    "HII": "تصنيع", "IBM": "تكنولوجيا", "IEX": "تصنيع", "IDXX": "استهلاكي",
    "ITW": "تصنيع", "INCY": "استهلاكي", "IR": "تصنيع", "PODD": "استهلاكي",
    "INTC": "تكنولوجيا", "IBKR": "بنوك", "ICE": "مالي غير مصرفي", "IFF": "تصنيع",
    "IP": "تصنيع", "INTU": "تكنولوجيا", "ISRG": "استهلاكي", "IVZ": "بنوك",
    "INVH": "عقاري", "IQV": "استهلاكي", "IRM": "عقاري", "JBHT": "تصنيع",
    "JBL": "تكنولوجيا", "JKHY": "مالي غير مصرفي", "J": "تصنيع", "JNJ": "استهلاكي",
    "JCI": "تصنيع", "JPM": "بنوك", "KVUE": "استهل
