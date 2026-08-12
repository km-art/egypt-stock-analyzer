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
    "JCI": "تصنيع", "JPM": "بنوك", "KVUE": "استهلاكي", "KDP": "استهلاكي",
    "KEY": "بنوك", "KEYS": "تكنولوجيا", "KMB": "استهلاكي", "KIM": "عقاري",
    "KMI": "تصنيع", "KKR": "بنوك", "KLAC": "تكنولوجيا", "KHC": "استهلاكي",
    "KR": "استهلاكي", "LHX": "تصنيع", "LH": "استهلاكي", "LRCX": "تكنولوجيا",
    "LVS": "استهلاكي", "LDOS": "تصنيع", "LEN": "استهلاكي", "LII": "تصنيع",
    "LLY": "استهلاكي", "LIN": "تصنيع", "LYV": "تكنولوجيا", "LMT": "تصنيع",
    "L": "مالي غير مصرفي", "LOW": "استهلاكي", "LULU": "استهلاكي", "LITE": "تكنولوجيا",
    "LYB": "تصنيع", "MTB": "بنوك", "MPC": "تصنيع", "MAR": "استهلاكي",
    "MRSH": "مالي غير مصرفي", "MLM": "تصنيع", "MAS": "تصنيع", "MA": "مالي غير مصرفي",
    "MKC": "استهلاكي", "MCD": "استهلاكي", "MCK": "استهلاكي", "MDT": "استهلاكي",
    "MRK": "استهلاكي", "META": "تكنولوجيا", "MET": "مالي غير مصرفي", "MTD": "استهلاكي",
    "MGM": "استهلاكي", "MCHP": "تكنولوجيا", "MU": "تكنولوجيا", "MSFT": "تكنولوجيا",
    "MAA": "عقاري", "MRNA": "استهلاكي", "TAP": "استهلاكي", "MDLZ": "استهلاكي",
    "MPWR": "تكنولوجيا", "MNST": "استهلاكي", "MCO": "مالي غير مصرفي", "MS": "بنوك",
    "MOS": "تصنيع", "MSI": "تكنولوجيا", "MSCI": "مالي غير مصرفي", "NDAQ": "مالي غير مصرفي",
    "NTAP": "تكنولوجيا", "NFLX": "تكنولوجيا", "NEM": "تصنيع", "NWSA": "تكنولوجيا",
    "NWS": "تكنولوجيا", "NEE": "تصنيع", "NKE": "استهلاكي", "NI": "تصنيع",
    "NDSN": "تصنيع", "NSC": "تصنيع", "NTRS": "بنوك", "NOC": "تصنيع",
    "NCLH": "استهلاكي", "NRG": "تصنيع", "NUE": "تصنيع", "NVDA": "تكنولوجيا",
    "NVR": "استهلاكي", "NXPI": "تكنولوجيا", "ORLY": "استهلاكي", "OXY": "تصنيع",
    "ODFL": "تصنيع", "OMC": "تكنولوجيا", "ON": "تكنولوجيا", "OKE": "تصنيع",
    "ORCL": "تكنولوجيا", "OTIS": "تصنيع", "PCAR": "تصنيع", "PKG": "تصنيع",
    "PLTR": "تكنولوجيا", "PANW": "تكنولوجيا", "PSKY": "تكنولوجيا", "PH": "تصنيع",
    "PAYX": "تصنيع", "PYPL": "مالي غير مصرفي", "PNR": "تصنيع", "PEP": "استهلاكي",
    "PFE": "استهلاكي", "PCG": "تصنيع", "PM": "استهلاكي", "PSX": "تصنيع",
    "PNW": "تصنيع", "PNC": "بنوك", "POOL": "استهلاكي", "PPG": "تصنيع",
    "PPL": "تصنيع", "PFG": "مالي غير مصرفي", "PG": "استهلاكي", "PGR": "مالي غير مصرفي",
    "PLD": "عقاري", "PRU": "مالي غير مصرفي", "PEG": "تصنيع", "PTC": "تكنولوجيا",
    "PSA": "عقاري", "PHM": "استهلاكي", "PWR": "تصنيع", "QCOM": "تكنولوجيا",
    "DGX": "استهلاكي", "RL": "استهلاكي", "RJF": "بنوك", "RTX": "تصنيع",
    "O": "عقاري", "REG": "عقاري", "REGN": "استهلاكي", "RF": "بنوك",
    "RSG": "تصنيع", "RMD": "استهلاكي", "RVTY": "استهلاكي", "HOOD": "بنوك",
    "ROK": "تصنيع", "ROL": "تصنيع", "ROP": "تكنولوجيا", "ROST": "استهلاكي",
    "RCL": "استهلاكي", "SPGI": "مالي غير مصرفي", "CRM": "تكنولوجيا", "SNDK": "تكنولوجيا",
    "SBAC": "عقاري", "SLB": "تصنيع", "STX": "تكنولوجيا", "SRE": "تصنيع",
    "NOW": "تكنولوجيا", "SHW": "تصنيع", "SPG": "عقاري", "SWKS": "تكنولوجيا",
    "SJM": "استهلاكي", "SW": "تصنيع", "SNA": "تصنيع", "SOLV": "استهلاكي",
    "SO": "تصنيع", "LUV": "تصنيع", "SWK": "تصنيع", "SBUX": "استهلاكي",
    "STT": "بنوك", "STLD": "تصنيع", "STE": "استهلاكي", "SYK": "استهلاكي",
    "SMCI": "تكنولوجيا", "SYF": "مالي غير مصرفي", "SNPS": "تكنولوجيا", "SYY": "استهلاكي",
    "TMUS": "تكنولوجيا", "TROW": "بنوك", "TTWO": "تكنولوجيا", "TPR": "استهلاكي",
    "TRGP": "تصنيع", "TGT": "استهلاكي", "TEL": "تكنولوجيا", "TDY": "تكنولوجيا",
    "TER": "تكنولوجيا", "TSLA": "استهلاكي", "TXN": "تكنولوجيا", "TPL": "تصنيع",
    "TXT": "تصنيع", "TMO": "استهلاكي", "TJX": "استهلاكي", "TKO": "تكنولوجيا",
    "TTD": "تكنولوجيا", "TSCO": "استهلاكي", "TT": "تصنيع", "TDG": "تصنيع",
    "TRV": "مالي غير مصرفي", "TRMB": "تكنولوجيا", "TFC": "بنوك", "TYL": "تكنولوجيا",
    "TSN": "استهلاكي", "USB": "بنوك", "UBER": "تصنيع", "UDR": "عقاري",
    "ULTA": "استهلاكي", "UNP": "تصنيع", "UAL": "تصنيع", "UPS": "تصنيع",
    "URI": "تصنيع", "UNH": "استهلاكي", "UHS": "استهلاكي", "VLO": "تصنيع",
    "VEEV": "استهلاكي", "VTR": "عقاري", "VLTO": "تصنيع", "VRSN": "تكنولوجيا",
    "VRSK": "تصنيع", "VZ": "تكنولوجيا", "VRTX": "استهلاكي", "VRT": "تصنيع",
    "VTRS": "استهلاكي", "VICI": "عقاري", "V": "مالي غير مصرفي", "VST": "تصنيع",
    "VMC": "تصنيع", "WRB": "مالي غير مصرفي", "GWW": "تصنيع", "WAB": "تصنيع",
    "WMT": "استهلاكي", "DIS": "تكنولوجيا", "WBD": "تكنولوجيا", "WM": "تصنيع",
    "WAT": "استهلاكي", "WEC": "تصنيع", "WFC": "بنوك", "WELL": "عقاري",
    "WST": "استهلاكي", "WDC": "تكنولوجيا", "WY": "عقاري", "WSM": "استهلاكي",
    "WMB": "تصنيع", "WTW": "مالي غير مصرفي", "WDAY": "تكنولوجيا", "WYNN": "استهلاكي",
    "XEL": "تصنيع", "XYL": "تصنيع", "YUM": "استهلاكي", "ZBRA": "تكنولوجيا",
    "ZBH": "استهلاكي", "ZTS": "استهلاكي",
}

# --- الإمارات: DFM + ADX (163 شركة) ---
UAE_STOCKS = {
    "Emirates NBD Bank PJSC": "EMIRATESNBD.AE", "Dubai Electricity and Water Authority": "DEWA.AE", "Emaar Properties PJSC": "EMAAR.AE",
    "Dubai Islamic Bank P.J.S.C.": "DIB.AE", "Emirates Integrated Telecommunications Company PJSC": "DU.AE", "Emaar Development PJSC": "EMAARDEV.AE",
    "Mashreqbank PSC": "MASQ.AE", "Salik Company P.J.S.C.": "SALIK.AE", "Talabat Holding plc": "TALABAT.AE",
    "Commercial Bank of Dubai PSC": "CBD.AE", "Air Arabia PJSC": "AIRARABIA.AE", "Parkin Company P.J.S.C.": "PARKIN.AE",
    "Emirates Central Cooling Systems Corporation": "EMPOWER.AE", "TECOM Group PJSC": "TECOM.AE", "Dubai Residential REIT": "DUBAIRESI.AE",
    "Dubai Investments PJSC": "DIC.AE", "Dubai Financial Market P.J.S.C.": "DFM.AE", "GFH Bank B.S.C.": "GFH.AE",
    "Gulf Navigation Holding PJSC": "GULFNAV.AE", "ALEC Holdings PJSC": "ALEC.AE", "National Central Cooling Company PJSC": "TABREED.AE",
    "Al Ansari Financial Services PJSC": "ALANSARI.AE", "National Industries Group Holding": "NIND.AE", "Al Salam Bank B.S.C.": "SALAM_BAH.AE",
    "Dubai Taxi Company P.J.S.C.": "DTC.AE", "Spinneys 1961 Holding plc": "SPINNEYS.AE", "Makhazen": "MKHZN.AE",
    "Ajman Bank PJSC": "AJMANBANK.AE", "Union Coop": "UNIONCOOP.AE", "Deyaar Development PJSC": "DEYAAR.AE",
    "Amanat Holdings PJSC": "AMANAT.AE", "Union Properties Public Joint Stock Company": "UPP.AE", "Taaleem Holdings PJSC": "TAALEEM.AE",
    "International Financial Advisors Holding": "IFA.AE", "Aramex PJSC": "ARMX.AE", "Dubai Refreshment (P.J.S.C.)": "DRC.AE",
    "Sukoon Insurance PJSC": "SUKOON.AE", "Amlak Finance PJSC": "AMLAK.AE", "Dubai Insurance Company (P.S.C.)": "DIN.AE",
    "National Cement Company": "NCC.AE", "National General Insurance Co. (P.J.S.C.)": "NGI.AE", "Al Ramz Corporation Investment and Development P.J.S.C.": "ALRAMZ.AE",
    "SHUAA Capital PSC": "SHUAA.AE", "Drake and Scull International P.J.S.C.": "DSI.AE", "Emirates Reem Investments Company P.J.S.C": "ERC.AE",
    "Emirates Investment Bank P.J.S.C.": "EIBANK.AE", "Islamic Arab Insurance Co. (Salama) PJSC": "SALAMA.AE", "BHM Capital Financial Services PSC": "BHMCAPITAL.AE",
    "Al-Mazaya Holding Company": "MAZAYA.AE", "National International Holding Company": "NIH.AE", "Ithmaar Holding B.S.C.": "ITHMR.AE",
    "United Foods Company (PSC)": "UFC.AE", "Dubai National Insurance & Reinsurance Co. (P.S.C.)": "DNIR.AE", "Sukoon Takaful PJSC": "SUKOONTAKAFL.AE",
    "Unikai Foods (P.J.S.C)": "UNIKAI.AE", "Al Firdous Holdings (P.J.S.C.)": "ALFIRDOUS.AE", "Watania International Holding PJSC": "WATANIA.AE",
    "Naeem Holding Company For Investments": "NAHO.AE", "Ekttitab Holding Company": "EKTTITAB.AE", "Dubai Islamic Insurance & Reinsurance Co. (Aman)": "AMAN.AE",
    "Al Salam Bank - Sudan": "ALSALAMSUDAN.AE", "International Holding Company PJSC": "IHC.AE", "ADNOC Gas PLC": "ADNOCGAS.AE",
    "Abu Dhabi National Energy Company PJSC": "TAQA.AE", "First Abu Dhabi Bank P.J.S.C.": "FAB.AE", "Emirates Telecommunications Group Company PJSC": "EAND.AE",
    "Abu Dhabi Commercial Bank PJSC": "ADCB.AE", "ADNOC Drilling Company P.J.S.C.": "ADNOCDRILL.AE", "Abu Dhabi Islamic Bank PJSC": "ADIB.AE",
    "Alpha Dhabi Holding PJSC": "ALPHADHABI.AE", "Borouge plc": "BOROUGE.AE", "Aldar Properties PJSC": "ALDAR.AE",
    "Modon Holding PSC": "MODON.AE", "Abu Dhabi National Oil Company for Distribution PJSC": "ADNOCDIST.AE", "ADNOC Logistics & Services plc": "ADNOCLS.AE",
    "Ooredoo Q.P.S.C.": "ORDS.AE", "MBME GROUP Private Joint Stock Company": "MBME.AE", "Two Point Zero Group P.J.S.C": "2POINTZERO.AE",
    "Fertiglobe plc": "FERTIGLB.AE", "Pure Health Holding PJSC": "PUREHEALTH.AE", "Abu Dhabi Ports Company PJSC": "ADPORTS.AE",
    "Presight AI Holding PLC": "PRESIGHT.AE", "The National Bank of Ras Al-Khaimah": "RAKBANK.AE", "NMDC Group PJSC": "NMDC.AE",
    "Americana Restaurants International PLC": "AMR.AE", "Agility Global PLC": "AGILITY.AE", "NMDC Energy - P.J.S.C.": "NMDCENR.AE",
    "National Bank of Fujairah PJSC": "NBF.AE", "Apex Investment PSC": "APEX.AE", "Lulu Retail Holdings PLC": "LULU.AE",
    "Sharjah Islamic Bank PJSC": "SIB.AE", "Space42 PLC": "SPACE42.AE", "EMSTEEL Building Materials PJSC": "EMSTEEL.AE",
    "Invest bank P.S.C.": "INB.AE", "Alef Education Holding plc": "ALEFEDT.AE", "Dana Gas PJSC": "DANA.AE",
    "National Bank of Umm Al-Qaiwain": "NBQ.AE", "Burjeel Holdings PLC": "BURJEEL.AE", "Abu Dhabi Aviation Co.": "ADAVIATION.AE",
    "Abu Dhabi National Hotels Company PJSC": "ADNH.AE", "United Arab Bank P.J.S.C.": "UAB.AE", "Abu Dhabi National Insurance Company PJSC": "ADNIC.AE",
    "Phoenix Group Plc": "PHX.AE", "Emirates Mobility Company P.J.S.C.": "EMOBILITY.AE", "Bank Of Sharjah P.J.S.C.": "BOS.AE",
    "Al Waha Capital PJSC": "WAHA.AE", "Investcorp Capital plc": "ICAP.AE", "Anan Investment Holding PJSC": "ANAN.AE",
    "National Corporation for Tourism and Hotels": "NCTH.AE", "RAK Properties PJSC": "RAKPROP.AE", "ESG Emirates Stallions Group PJSC": "ESG.AE",
    "Sagasse Investment Company Plc": "SAGA.AE", "Agthia Group PJSC": "AGTHIA.AE", "Abu Dhabi National Company for Building Materials PJSC": "BILDCO.AE",
    "Ghitha Holding P.J.S.C": "GHITHA.AE", "Gulf Investment House": "GIH.AE", "R.A.K. Ceramics P.J.S.C.": "RAKCEC.AE",
    "Al Seer Marine Supplies and Equipment Company PJSC": "ASM.AE", "MAIR Group - P.J.S.C.": "MAIR.AE", "E7 Group PJSC": "E7.AE",
    "Invictus Investment Company PLC": "INVICTUS.AE", "Abu Dhabi Ship Building PJSC": "ADSB.AE", "Gulf Medical Projects Company (PJSC)": "GMPC.AE",
    "Commercial Bank International P.J.S.C.": "CBI.AE", "ADNH Catering PLC": "ADNHC.AE", "Alpha Data PJSC": "ALPHADATA.AE",
    "Eshraq Investments PJSC": "ESHRAQ.AE", "Gulf Pharmaceutical Industries P.S.C.": "JULPHAR.AE", "Palms Sports PJSC": "PALMS.AE",
    "Emirates Insurance Company P.J.S.C.": "EIC.AE", "Sudatel Telecom Group Limited": "SUDATEL.AE", "Manazel PJSC": "MANAZEL.AE",
    "Easy Lease Motor Cycle Rental P.S.C.": "EASYLEASE.AE", "Al Dhafra Insurance Company P.S.C.": "DHAFRA.AE", "Sharjah Cement and Industrial Development Co.": "SCIDC.AE",
    "Al Wathba National Insurance Company PJSC": "AWNIC.AE", "Al Buhaira National Insurance Company P.S.C.": "ABNIC.AE", "Umm Al Qaiwain General Investments Company P.S.C.": "QIC.AE",
    "Finance House P.J.S.C.": "FH.AE", "Al Khaleej Investment P.J.S.C.": "KICO.AE", "Abu Dhabi National Takaful Company PSC": "TKFL.AE",
    "Al Ain Ahlia Insurance Company P.S.C.": "ALAIN.AE", "Ras Al Khaimah Co. for White Cement & Construction Materials": "RAKWCT.AE", "Response Plus Holding PJSC": "RPM.AE",
    "Fujairah Building Industries P.J.S.C.": "FBI.AE", "Gulf Cement Company P.S.C.": "GCEM.AE", "Foodco National Foodstuff PJSC": "FNF.AE",
    "Ras Al Khaimah National Insurance Company P.S.C.": "RAKNIC.AE", "Sawaeed Holding P.J.S.C.": "SAWAEED.AE", "Union Insurance Company P.J.S.C.": "UNION.AE",
    "HAYAH Insurance Company P.J.S.C.": "HAYAH.AE", "United Fidelity Insurance Company (P.S.C.)": "FIDELITYUNITED.AE", "Al Fujairah National Insurance Company P.J.S.C": "AFNIC.AE",
    "Hily Holding PJSC": "HH.AE", "Sharjah Insurance Company P.S.C.": "SICO.AE", "RAPCO Investment PJSC": "RAPCO.AE",
    "Oman & Emirates Investment Holding Company": "OEIHC.AE", "Insurance House - P J S C": "IH.AE", "ARAM Group Company P.J.S.C.": "ARAM.AE",
    "Fujairah Cement Industries PJSC": "FCI.AE", "The National Investor Pr. J.S.C.": "TNI.AE", "Methaq Takaful Insurance P.S.C.": "METHAQ.AE",
    "Al Khazna Insurance Company P.S.C.": "AKIC.AE",
}

UAE_SECTOR = {
    "EMIRATESNBD.AE": "بنوك", "DEWA.AE": "تصنيع", "EMAAR.AE": "عقاري", "DIB.AE": "بنوك",
    "DU.AE": "تكنولوجيا", "EMAARDEV.AE": "عقاري", "MASQ.AE": "بنوك", "SALIK.AE": "تصنيع",
    "TALABAT.AE": "تكنولوجيا", "CBD.AE": "بنوك", "AIRARABIA.AE": "تصنيع", "PARKIN.AE": "تصنيع",
    "EMPOWER.AE": "تصنيع", "TECOM.AE": "عقاري", "DUBAIRESI.AE": "عقاري", "DIC.AE": "مالي غير مصرفي",
    "DFM.AE": "مالي غير مصرفي", "GFH.AE": "بنوك", "GULFNAV.AE": "تصنيع", "ALEC.AE": "تصنيع",
    "TABREED.AE": "تصنيع", "ALANSARI.AE": "مالي غير مصرفي", "NIND.AE": "تصنيع", "SALAM_BAH.AE": "بنوك",
    "DTC.AE": "تصنيع", "SPINNEYS.AE": "استهلاكي", "MKHZN.AE": "تصنيع", "AJMANBANK.AE": "بنوك",
    "UNIONCOOP.AE": "استهلاكي", "DEYAAR.AE": "عقاري", "AMANAT.AE": "مالي غير مصرفي", "UPP.AE": "عقاري",
    "TAALEEM.AE": "استهلاكي", "IFA.AE": "مالي غير مصرفي", "ARMX.AE": "تصنيع", "DRC.AE": "استهلاكي",
    "SUKOON.AE": "مالي غير مصرفي", "AMLAK.AE": "مالي غير مصرفي", "DIN.AE": "مالي غير مصرفي", "NCC.AE": "تصنيع",
    "NGI.AE": "مالي غير مصرفي", "ALRAMZ.AE": "مالي غير مصرفي", "SHUAA.AE": "مالي غير مصرفي", "DSI.AE": "تصنيع",
    "ERC.AE": "مالي غير مصرفي", "EIBANK.AE": "بنوك", "SALAMA.AE": "مالي غير مصرفي", "BHMCAPITAL.AE": "مالي غير مصرفي",
    "MAZAYA.AE": "عقاري", "NIH.AE": "مالي غير مصرفي", "ITHMR.AE": "مالي غير مصرفي", "UFC.AE": "استهلاكي",
    "DNIR.AE": "مالي غير مصرفي", "SUKOONTAKAFL.AE": "مالي غير مصرفي", "UNIKAI.AE": "استهلاكي", "ALFIRDOUS.AE": "عقاري",
    "WATANIA.AE": "مالي غير مصرفي", "NAHO.AE": "مالي غير مصرفي", "EKTTITAB.AE": "مالي غير مصرفي", "AMAN.AE": "مالي غير مصرفي",
    "ALSALAMSUDAN.AE": "بنوك", "IHC.AE": "مالي غير مصرفي", "ADNOCGAS.AE": "تصنيع", "TAQA.AE": "تصنيع",
    "FAB.AE": "بنوك", "EAND.AE": "تكنولوجيا", "ADCB.AE": "بنوك", "ADNOCDRILL.AE": "تصنيع",
    "ADIB.AE": "بنوك", "ALPHADHABI.AE": "مالي غير مصرفي", "BOROUGE.AE": "تصنيع", "ALDAR.AE": "عقاري",
    "MODON.AE": "عقاري", "ADNOCDIST.AE": "تصنيع", "ADNOCLS.AE": "تصنيع", "ORDS.AE": "تكنولوجيا",
    "MBME.AE": "استهلاكي", "2POINTZERO.AE": "مالي غير مصرفي", "FERTIGLB.AE": "تصنيع", "PUREHEALTH.AE": "استهلاكي",
    "ADPORTS.AE": "تصنيع", "PRESIGHT.AE": "تكنولوجيا", "RAKBANK.AE": "بنوك", "NMDC.AE": "تصنيع",
    "AMR.AE": "استهلاكي", "AGILITY.AE": "تصنيع", "NMDCENR.AE": "تصنيع", "NBF.AE": "بنوك",
    "APEX.AE": "مالي غير مصرفي", "LULU.AE": "استهلاكي", "SIB.AE": "بنوك", "SPACE42.AE": "تكنولوجيا",
    "EMSTEEL.AE": "تصنيع", "INB.AE": "بنوك", "ALEFEDT.AE": "استهلاكي", "DANA.AE": "تصنيع",
    "NBQ.AE": "بنوك", "BURJEEL.AE": "استهلاكي", "ADAVIATION.AE": "تصنيع", "ADNH.AE": "استهلاكي",
    "UAB.AE": "بنوك", "ADNIC.AE": "مالي غير مصرفي", "PHX.AE": "تصنيع", "EMOBILITY.AE": "تصنيع",
    "BOS.AE": "بنوك", "WAHA.AE": "مالي غير مصرفي", "ICAP.AE": "مالي غير مصرفي", "ANAN.AE": "مالي غير مصرفي",
    "NCTH.AE": "استهلاكي", "RAKPROP.AE": "عقاري", "ESG.AE": "تصنيع", "SAGA.AE": "مالي غير مصرفي",
    "AGTHIA.AE": "استهلاكي", "BILDCO.AE": "تصنيع", "GHITHA.AE": "استهلاكي", "GIH.AE": "مالي غير مصرفي",
    "RAKCEC.AE": "تصنيع", "ASM.AE": "تصنيع", "MAIR.AE": "استهلاكي", "E7.AE": "تكنولوجيا",
    "INVICTUS.AE": "مالي غير مصرفي", "ADSB.AE": "تصنيع", "GMPC.AE": "استهلاكي", "CBI.AE": "بنوك",
    "ADNHC.AE": "استهلاكي", "ALPHADATA.AE": "تكنولوجيا", "ESHRAQ.AE": "عقاري", "JULPHAR.AE": "استهلاكي",
    "PALMS.AE": "استهلاكي", "EIC.AE": "مالي غير مصرفي", "SUDATEL.AE": "تكنولوجيا", "MANAZEL.AE": "عقاري",
    "EASYLEASE.AE": "مالي غير مصرفي", "DHAFRA.AE": "مالي غير مصرفي", "SCIDC.AE": "تصنيع", "AWNIC.AE": "مالي غير مصرفي",
    "ABNIC.AE": "مالي غير مصرفي", "QIC.AE": "مالي غير مصرفي", "FH.AE": "مالي غير مصرفي", "KICO.AE": "مالي غير مصرفي",
    "TKFL.AE": "مالي غير مصرفي", "ALAIN.AE": "مالي غير مصرفي", "RAKWCT.AE": "تصنيع", "RPM.AE": "استهلاكي",
    "FBI.AE": "تصنيع", "GCEM.AE": "تصنيع", "FNF.AE": "استهلاكي", "RAKNIC.AE": "مالي غير مصرفي",
    "SAWAEED.AE": "مالي غير مصرفي", "UNION.AE": "مالي غير مصرفي", "HAYAH.AE": "مالي غير مصرفي", "FIDELITYUNITED.AE": "مالي غير مصرفي",
    "AFNIC.AE": "مالي غير مصرفي", "HH.AE": "مالي غير مصرفي", "SICO.AE": "مالي غير مصرفي", "RAPCO.AE": "مالي غير مصرفي",
    "OEIHC.AE": "مالي غير مصرفي", "IH.AE": "مالي غير مصرفي", "ARAM.AE": "تصنيع", "FCI.AE": "تصنيع",
    "TNI.AE": "مالي غير مصرفي", "METHAQ.AE": "مالي غير مصرفي", "AKIC.AE": "مالي غير مصرفي",
}

# سجل موحّد للأسواق - يستخدم في الواجهة لاختيار السوق وعرض العملة الصحيحة
MARKETS = {
    "egx": {"label": "🇪🇬 مصر (EGX)", "stocks": ALL_EGX_STOCKS, "sector_map": TICKER_SECTOR,
            "currency": "EGP", "currency_label": "جنيه مصري", "default_min_liquidity": 3_000_000},
    "us": {"label": "🇺🇸 أمريكا (S&P 500)", "stocks": US_STOCKS, "sector_map": US_SECTOR,
           "currency": "USD", "currency_label": "دولار أمريكي", "default_min_liquidity": 5_000_000},
    "uae": {"label": "🇦🇪 الإمارات (DFM + ADX)", "stocks": UAE_STOCKS, "sector_map": UAE_SECTOR,
            "currency": "AED", "currency_label": "درهم إماراتي", "default_min_liquidity": 1_000_000},
}

TICKER_TO_CURRENCY = {}
for _mk, _m in MARKETS.items():
    for _ticker in _m["stocks"].values():
        TICKER_TO_CURRENCY[_ticker] = _m["currency"]


def get_sector(ticker: str) -> str:
    """يدوّر على قطاع السهم في أي سوق من الأسواق التلاتة."""
    for m in MARKETS.values():
        if ticker in m["sector_map"]:
            return m["sector_map"][ticker]
    return "غير مصنف"


def get_currency(ticker: str) -> str:
    """يدوّر على عملة السهم حسب السوق اللي هو مدرج فيه (افتراضي EGP لو رمز يدوي غير معروف)."""
    return TICKER_TO_CURRENCY.get(ticker, "EGP")



# ---------------------------------------------------------------------------
# تصنيف EGX30 / EGX70 - مبني على بيانات investing.com (قد تتغيّر مع أي
# مراجعة نصف سنوية لمؤشرات EGX - آخر تحقق تم يدوياً، حدّثها لو لاحظت تغيير)
# ---------------------------------------------------------------------------
EGX30_TICKERS = {
    "ABUK.CA", "ADIB.CA", "AMOC.CA", "ARCC.CA", "BTFH.CA", "CCAP.CA", "COMI.CA", "EAST.CA",
    "EFID.CA", "EFIH.CA", "EGAL.CA", "EGCH.CA", "EMFD.CA", "ETEL.CA", "FWRY.CA", "GBCO.CA",
    "HELI.CA", "HRHO.CA", "ISPH.CA", "JUFO.CA", "MCQE.CA", "OIH.CA", "ORAS.CA", "ORHD.CA",
    "ORWE.CA", "PHDC.CA", "RAYA.CA", "RMDA.CA", "TMGH.CA", "VLMR.CA", "VLMRA.CA",
}

EGX70_TICKERS = {
    "ACTF.CA", "AFDI.CA", "AFMC.CA", "AIDC.CA", "ALCN.CA", "AMER.CA", "AMIA.CA", "ARAB.CA",
    "ASCM.CA", "ASPI.CA", "ATLC.CA", "ATQA.CA", "BIOC.CA", "CIEB.CA", "CNFN.CA", "COSG.CA",
    "CSAG.CA", "DAPH.CA", "DSCW.CA", "ECAP.CA", "EEII.CA", "EFIC.CA", "EGTS.CA", "EHDR.CA",
    "ENGC.CA", "ETRS.CA", "EXPA.CA", "GPIM.CA", "HDBK.CA", "IDRE.CA", "IFAP.CA", "ISMA.CA",
    "ISMQ.CA", "KABO.CA", "KRDI.CA", "LCSW.CA", "MASR.CA", "MCRO.CA", "MEPA.CA", "MFPC.CA",
    "MOED.CA", "MPCI.CA", "MPCO.CA", "MPRC.CA", "MTIE.CA", "NCCW.CA", "NIPH.CA", "OBRI.CA",
    "OCDI.CA", "PHAR.CA", "POUL.CA", "PRCL.CA", "RACC.CA", "SCEM.CA", "SDTI.CA", "SIPC.CA",
    "SKPC.CA", "SPHT.CA", "SVCE.CA", "SWDY.CA", "TALM.CA", "TANM.CA", "TAQA.CA", "UEGC.CA",
    "UNIP.CA", "VALU.CA", "ZEOT.CA", "ZMID.CA",
}


def get_egx_index(ticker: str) -> str:
    """
    يرجع "EGX30" لو السهم من أكبر/أنشط 30 سهم، "EGX70" لو من الشريحة التالية
    (أسهم متوسطة نشطة)، أو "خارج EGX30/70" لباقي الأسهم المصرية أو أي سهم
    من سوق تاني (أمريكا/الإمارات).
    """
    if ticker in EGX30_TICKERS:
        return "EGX30"
    if ticker in EGX70_TICKERS:
        return "EGX70"
    if ticker in ALL_EGX_STOCKS.values():
        return "خارج EGX30/70"
    return "غير منطبق (مش سهم مصري)"


def calculate_indicators(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(-1)
        
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI_14'] = 100 - (100 / (1 + (gain / (loss + 0.00001))))
    
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['STD20'] = df['Close'].rolling(window=20).std()
    df['Upper_Band'] = df['MA20'] + (2 * df['STD20'])
    df['Lower_Band'] = df['MA20'] - (2 * df['STD20'])
    
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    raw_money_flow = typical_price * df['Volume']
    typical_price_diff = typical_price.diff()
    pos_flow = pd.Series(np.where(typical_price_diff > 0, raw_money_flow, 0), index=df.index)
    neg_flow = pd.Series(np.where(typical_price_diff < 0, raw_money_flow, 0), index=df.index)
    
    pos_mf14 = pos_flow.rolling(window=14).sum()
    neg_mf14 = neg_flow.rolling(window=14).sum()
    df['MFI_14'] = 100 - (100 / (1 + (pos_mf14 / (neg_mf14 + 0.00001))))
    
    df['Vol_MA10'] = df['Volume'].rolling(window=10).mean()
    return df


@st.cache_data(ttl=600, show_spinner=False)
def fetch_fundamentals(ticker: str) -> dict:
    """
    يجلب أهم البيانات المالية الأساسية للسهم (P/E, ROE, هامش الربح...).
    Cache لمدة 10 دقايق لأن استدعاء .info أبطأ وأتقل بكتير من بيانات الأسعار،
    ومحتاج نقلل الطلبات المتكررة عليه قد الإمكان.
    """
    empty = {
        "pe_ratio": None, "pb_ratio": None, "roe_%": None,
        "profit_margin_%": None, "debt_to_equity": None,
        "dividend_yield_%": None, "revenue_growth_%": None,
        "eps": None, "book_value_per_share": None,
    }
    try:
        info = yf.Ticker(resolve_symbol(ticker), session=YF_SESSION).info
    except Exception:
        return empty

    # استجابة فاضية/مقتضبة = رفض مؤقت من المصدر (rate limit)، مش إن السهم
    # مالوش بيانات فعلاً - نتعامل معاها زي بيانات ناقصة عادية
    if not info or len(info) < 5:
        return empty

    def pct(x):
        return round(x * 100, 2) if isinstance(x, (int, float)) else None

    return {
        "pe_ratio": info.get("trailingPE"),
        "pb_ratio": info.get("priceToBook"),
        "roe_%": pct(info.get("returnOnEquity")),
        "profit_margin_%": pct(info.get("profitMargins")),
        "debt_to_equity": info.get("debtToEquity"),
        "dividend_yield_%": pct(info.get("dividendYield")),
        "revenue_growth_%": pct(info.get("revenueGrowth")),
        "eps": info.get("trailingEps"),
        "book_value_per_share": info.get("bookValue"),
    }


def compute_graham(eps, bvps, price):
    """
    يحسب "رقم جراهام" (Graham Number) - السعر العادل الأقصى حسب معايير
    المستثمر الدفاعي لبنجامين جراهام:

        رقم جراهام = √(22.5 × EPS × BVPS)

    الرقم 22.5 = 15 (أقصى P/E مقبول) × 1.5 (أقصى P/B مقبول). محتاجة EPS
    موجب وBVPS موجب عشان الصيغة تكون منطقية (شركة رابحة بقيمة دفترية موجبة).
    """
    if eps is None or bvps is None or eps <= 0 or bvps <= 0:
        return {"graham_number": None, "graham_upside_%": None, "undervalued_per_graham": None}

    graham_number = (22.5 * eps * bvps) ** 0.5
    upside_pct = round((graham_number / price - 1) * 100, 1) if price else None
    return {
        "graham_number": round(graham_number, 2),
        "graham_upside_%": upside_pct,
        "undervalued_per_graham": price < graham_number,
    }


def graham_from_fundamentals(fundamentals: dict, price: float) -> dict:
    """
    يحسب رقم جراهام من dict الأساسيات، مع اشتقاق EPS/BVPS من P/E و P/B
    كحل بديل لو Yahoo مارجعش القيمتين مباشرة (شائع جداً لأسهم EGX).
    بيرجع dict فيه graham_number/graham_upside_%/undervalued_per_graham
    بالإضافة لـ eps وbvps المستخدمين فعلياً وعلامة estimated لكل واحد.
    """
    eps = fundamentals.get("eps")
    bvps = fundamentals.get("book_value_per_share")
    eps_estimated = False
    bvps_estimated = False

    pe = fundamentals.get("pe_ratio")
    pb = fundamentals.get("pb_ratio")

    if eps is None and pe is not None and pe > 0:
        eps = price / pe
        eps_estimated = True
    if bvps is None and pb is not None and pb > 0:
        bvps = price / pb
        bvps_estimated = True

    result = compute_graham(eps=eps, bvps=bvps, price=price)
    result["eps"] = round(eps, 3) if eps is not None else None
    result["book_value_per_share"] = round(bvps, 3) if bvps is not None else None
    result["eps_estimated"] = eps_estimated
    result["bvps_estimated"] = bvps_estimated
    return result


# عتبات قرار التوصية - عدّلها هنا لو حابب تشدد أو تخفف الشروط
VERDICT_BUY_MIN_TECH = 65
VERDICT_BUY_MIN_FUND = 65
VERDICT_SELL_MAX_TECH = 35
VERDICT_SELL_MAX_FUND = 40


def compute_verdict(momentum_score, fund_score, include_fundamentals: bool,
                     fundamentals_fetched: bool = True) -> dict:
    """
    توصية "شراء / انتظار / بيع" مبنية على تحقق التحليل الفني والمالي **مع بعض**.

    - لو التحليل المالي مطلوب بس بياناته رجعت فاضية (Yahoo رافض/حاظر) -> انتظار
      مع سبب واضح، عشان محدش ياخد قرار على بيانات ناقصة.
    - شراء: النقاط الفنية والمالية **الاتنين** فوق العتبة.
    - بيع: الاتنين تحت العتبة.
    - غير كده: انتظار (إشارات متضاربة).

    لو include_fundamentals=False، القرار بيعتمد على الفني بس.
    """
    if momentum_score is None:
        return {"التوصية": "🟡 انتظار (بيانات غير كافية)", "ترتيب_التوصية": 1}

    if not include_fundamentals:
        if momentum_score >= VERDICT_BUY_MIN_TECH:
            return {"التوصية": "🟢 شراء (فني فقط)", "ترتيب_التوصية": 0}
        if momentum_score <= VERDICT_SELL_MAX_TECH:
            return {"التوصية": "🔴 بيع (فني فقط)", "ترتيب_التوصية": 2}
        return {"التوصية": "🟡 انتظار (فني فقط)", "ترتيب_التوصية": 1}

    if not fundamentals_fetched:
        return {"التوصية": "🟡 انتظار (بيانات مالية ناقصة)", "ترتيب_التوصية": 1}

    if momentum_score >= VERDICT_BUY_MIN_TECH and fund_score >= VERDICT_BUY_MIN_FUND:
        return {"التوصية": "🟢 شراء", "ترتيب_التوصية": 0}

    if momentum_score <= VERDICT_SELL_MAX_TECH and fund_score <= VERDICT_SELL_MAX_FUND:
        return {"التوصية": "🔴 بيع", "ترتيب_التوصية": 2}

    return {"التوصية": "🟡 انتظار (إشارات متضاربة)", "ترتيب_التوصية": 1}


def score_fundamentals(f: dict) -> int:
    """
    درجة مالية (0-100) تعكس الصحة المالية للشركة، بنفس منطق أداة EGX Screener.
    لو بند معين مش متاح، بيتم تجاهله بدل ما يأثر سلباً على الدرجة (عشان
    شركة بيانات ناقصة متتظلمش بدرجة واطية ظلماً).
    """
    score = 50

    pe = f.get("pe_ratio")
    if pe is not None and pe > 0:
        if pe < 12:
            score += 10
        elif pe > 25:
            score -= 10

    pm = f.get("profit_margin_%")
    if pm is not None:
        if pm > 15:
            score += 10
        elif pm < 0:
            score -= 15

    roe = f.get("roe_%")
    if roe is not None:
        if roe > 15:
            score += 10
        elif roe < 5:
            score -= 5

    dte = f.get("debt_to_equity")
    if dte is not None:
        if dte < 50:
            score += 5
        elif dte > 150:
            score -= 10

    dy = f.get("dividend_yield_%")
    if dy is not None and dy > 5:
        score += 5

    rg = f.get("revenue_growth_%")
    if rg is not None:
        if rg > 10:
            score += 10
        elif rg < 0:
            score -= 10

    return max(0, min(100, score))


@st.cache_data(ttl=300, show_spinner=False)
def fetch_single_stock(ticker: str, period: str = "100d"):
    """تحميل بيانات سهم واحد مع تخزين مؤقت (cache) لمدة 5 دقايق لتقليل الطلبات المكررة."""
    if ticker.endswith(".CA"):
        # مصر: TradingView بدل Yahoo (Yahoo متجمدة لأسهم مصر)
        try:
            n_bars = int(period.rstrip("d")) if period.rstrip("d").isdigit() else 150
        except Exception:
            n_bars = 150
        return fetch_egx_history_tv(ticker, n_bars=max(n_bars, 50))
    return yf.download(resolve_symbol(ticker), period=period, progress=False, group_by='ticker', session=YF_SESSION)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_batch_data(tickers_tuple: tuple, period: str = "60d"):
    """
    يحمّل بيانات مجموعة أسهم على دفعات (batches) بدل طلب واحد ضخم لكل الأسهم،
    عشان نتفادى رفض Yahoo Finance للطلب أو فشله جزئياً لما يكون العدد كبير (230+ سهم).

    بعد الدفعات، بيعمل "محاولة ثانية" لكل سهم فشل - بيحمّله لوحده مش جوه دفعة،
    لأن كتير من فشل الدفعات بيكون سببه سهم واحد بايظ بيبوّظ الدفعة كلها أو
    رفض مؤقت لحظي (rate limit)، مش لأن السهم نفسه مالوش بيانات فعلاً.

    يرجع (dict لكل سهم بياناته, list بالأسهم اللي فشلت حتى بعد إعادة المحاولة).
    """
    tickers = list(tickers_tuple)
    all_frames = {}
    failed = []

    # نفصل أسهم مصر (.CA) عن الباقي، لأن مصر بتتحمّل من TradingView مش Yahoo
    egx_tickers = [t for t in tickers if t.endswith(".CA")]
    other_tickers = [t for t in tickers if not t.endswith(".CA")]

    # --- مصر: TradingView، سهم سهم (المكتبة مش بتدعم تحميل دفعات) ---
    for t in egx_tickers:
        try:
            df_t = fetch_egx_history_tv(t, n_bars=150)
            if df_t is not None and not df_t.dropna(how='all').empty:
                all_frames[t] = df_t
            else:
                failed.append(t)
        except Exception:
            failed.append(t)
        time.sleep(0.2)  # فاصل بسيط بين الطلبات عشان مانضغطش على TradingView

    tickers = other_tickers

    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        resolved_batch = [resolve_symbol(t) for t in batch]
        try:
            # threads=False لأن جلسة curl_cffi المشتركة ممكن تحصل معاها مشاكل
            # لو استخدمناها من كذا thread في نفس الوقت
            data = yf.download(resolved_batch, period=period, progress=False, group_by='ticker', threads=False, session=YF_SESSION)
        except Exception:
            failed.extend(batch)
            continue

        for t in batch:
            try:
                rt = resolve_symbol(t)
                df_t = data[rt] if len(batch) > 1 else data
                if df_t is not None and not df_t.dropna(how='all').empty:
                    all_frames[t] = df_t  # نخزّن بالرمز الأصلي عشان باقي الكود يلاقيه
                else:
                    failed.append(t)
            except Exception:
                failed.append(t)

        # نستنى شوية بين الدفعات (إلا لو كانت الدفعة الأخيرة) عشان نقلل احتمال الرفض
        if i + BATCH_SIZE < len(tickers):
            time.sleep(BATCH_DELAY)

    # محاولة ثانية: نحمّل كل سهم فشل لوحده (مش جوه دفعة) - غالباً بتنقذ نسبة كبيرة منهم
    still_failed = []
    if failed:
        for t in failed:
            try:
                df_t = yf.download(resolve_symbol(t), period=period, progress=False, group_by='ticker', session=YF_SESSION)
                if df_t is not None and not df_t.dropna(how='all').empty:
                    all_frames[t] = df_t
                else:
                    still_failed.append(t)
            except Exception:
                still_failed.append(t)
            time.sleep(0.3)  # فاصل بسيط بين المحاولات الفردية
        failed = still_failed

    return all_frames, failed

_WATCHLIST_CSV = "watchlist.csv"


def load_watchlist() -> list[str]:
    if os.path.exists(_WATCHLIST_CSV):
        try:
            return pd.read_csv(_WATCHLIST_CSV)["ticker"].dropna().tolist()
        except Exception:
            return []
    return []


def save_watchlist(tickers: list[str]):
    pd.DataFrame({"ticker": tickers}).to_csv(_WATCHLIST_CSV, index=False)


st.sidebar.markdown("---")
watchlist = load_watchlist()
with st.sidebar.expander(f"⭐ المفضّلة ({len(watchlist)} سهم)"):
    if watchlist:
        st.write(", ".join(watchlist))
    wl_col1, wl_col2 = st.columns(2)
    with wl_col1:
        wl_add = st.text_input("أضف رمز (زي COMI.CA)", key="wl_add_fb")
        if st.button("➕ إضافة للمفضّلة", key="wl_add_btn_fb"):
            if wl_add and wl_add.strip() not in watchlist:
                watchlist.append(wl_add.strip())
                save_watchlist(watchlist)
                st.success(f"✅ اتضاف {wl_add.strip()}")
                st.rerun()
    with wl_col2:
        wl_remove = st.text_input("احذف رمز", key="wl_remove_fb")
        if st.button("🗑️ حذف من المفضّلة", key="wl_remove_btn_fb"):
            if wl_remove and wl_remove.strip() in watchlist:
                watchlist.remove(wl_remove.strip())
                save_watchlist(watchlist)
                st.success(f"🗑️ اتشال {wl_remove.strip()}")
                st.rerun()
    st.caption("💡 لاستخدام المفضّلة في المسح الشامل، انسخ الرموز فوق والصقها في قائمة الأسهم بتاب المسح.")

tab1, tab2, tab3 = st.tabs([
    "🔍 فحص سهم تفصيلي + رسم بياني", "🏆 مسح وترتيب السوق الاحترافي", "💼 محفظتي",
])

with tab1:
    st.subheader("اختر سهمك المفضل لتحليله ورسم بياناته بالتفصيل")
    market_choice_tab1 = st.radio(
        "اختر السوق", options=list(MARKETS.keys()),
        format_func=lambda k: MARKETS[k]["label"], horizontal=True, key="market_tab1",
    )
    stocks_dict_tab1 = MARKETS[market_choice_tab1]["stocks"]
    col_input1, col_input2 = st.columns([2, 1])
    with col_input1:
        selected_stock = st.selectbox("اختر من قائمة السوق المحددة:", list(stocks_dict_tab1.keys()))
        ticker_input = stocks_dict_tab1[selected_stock]
    with col_input2:
        manual_ticker = st.text_input("أو اكتب رمزاً مخصصاً يدوياً (أي سوق):", value="").strip().upper()
        if manual_ticker:
            ticker_input = manual_ticker

    if st.button("تحليل السهم ورسم المنحنى ⚡"):
        with st.spinner("جاري جلب البيانات..."):
            try:
                df = fetch_single_stock(ticker_input, period="100d")
                if not df.empty:
                    df = calculate_indicators(df)
                    last_row = df.iloc[-1]
                    prev_row = df.iloc[-CROSS_LOOKBACK]
                    
                    price_hist_close = float(last_row['Close'].squeeze())
                    price_info = get_display_price(ticker_input, price_hist_close)
                    price = price_info["price"]
                    st.session_state.setdefault("last_scan_prices", {})[ticker_input] = price
                    ema9 = float(last_row['EMA9'].squeeze())
                    ema21 = float(last_row['EMA21'].squeeze())
                    rsi = float(last_row['RSI_14'].squeeze())
                    mfi = float(last_row['MFI_14'].squeeze())
                    upper = float(last_row['Upper_Band'].squeeze())
                    lower = float(last_row['Lower_Band'].squeeze())
                    vol = float(last_row['Volume'].squeeze())
                    
                    is_new_cross = (prev_row['EMA9'] <= prev_row['EMA21']) and (ema9 > ema21)
                    
                    if is_new_cross and rsi < 52:
                        decision = "🚀 تأسيس مركز (بداية تقاطع ذهبي حقيقي من القاع)"
                        color = "#1abc9c"
                    elif rsi < 35 and mfi < 35:
                        decision = "🛒 تجميع في القاع (منطقة رخيصة جداً للمراقبة)"
                        color = "#3498db"
                    elif ema9 > ema21 and rsi < 70 and mfi < 80:
                        decision = "STRONG BUY ⚡ (اتجاه صاعد مستمر)"
                        color = "#2ecc71"
                    elif price >= upper or rsi >= 75 or mfi >= 85:
                        decision = "SELL / TAKE PROFIT 🚨 (تضخم مؤشرات حاد)"
                        color = "#e74c3c"
                    else:
                        decision = "HOLD ✋ (مراقبة)"
                        color = "#f39c12"
                    
                    st.markdown(f'<div style="background-color:{color}; padding:20px; border-radius:10px; text-align:center; margin-bottom:20px;"><h2 style="color:white; margin:0;">القرار الحالي لـ {ticker_input}: {decision}</h2></div>', unsafe_allow_html=True)
                    
                    c1, c2, c3, c4 = st.columns(4)
                    price_currency = get_currency(ticker_input)
                    c1.metric("السعر الحالي", f"{price:.2f} {price_currency}")
                    c2.metric("مؤشر الزخم RSI", f"{rsi:.1f}")
                    c3.metric("مؤشر السيولة MFI", f"{mfi:.1f}")
                    c4.metric("حجم تداول اليوم (فوليوم)", f"{vol:,.0f}")

                    # --- تصنيف السهم حسب نفس الأقسام الأربعة بتاعة المسح الشامل ---
                    # (نفس الشرط بالظبط المستخدم في "مسح وترتيب السوق الاحترافي"،
                    # عشان أي سهم تشوفه هنا يبقى نفس تصنيفه هناك بالظبط)
                    vol_ma10 = float(last_row['Vol_MA10'].squeeze())
                    if is_new_cross and rsi < 52:
                        section_label = "🚀 أولاً: أسهم لقطت 'إشارة تأسيس مركز جديدة اليوم'"
                        section_color = "#1abc9c"
                    elif rsi < 35 and mfi < 35:
                        section_label = "📥 ثانياً: رادار تصيد القيعان"
                        section_color = "#3498db"
                    elif ema9 > ema21:
                        if vol > (vol_ma10 * 1.15) and 50 <= rsi <= 78:
                            section_label = "⚡ ثالثاً: أسهم المضاربة اللحظية واليومية"
                            section_color = "#e67e22"
                        else:
                            section_label = "📈 رابعاً: أسهم الاستثمار والاتجاه الصاعد المستقر"
                            section_color = "#2ecc71"
                    else:
                        section_label = None

                    if section_label:
                        st.markdown(
                            f'<div style="background-color:{section_color}; padding:14px; '
                            f'border-radius:8px; text-align:center; margin-bottom:16px;">'
                            f'<span style="color:white; font-size:16px;">📍 لو عملت مسح شامل دلوقتي، '
                            f'السهم ده هيظهر في قسم: <b>{section_label}</b></span></div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.caption(
                            "📍 السهم ده حالياً **مش هيظهر في أي قسم من الأربعة** لو عملت مسح شامل "
                            "(المؤشرات الحالية مش مطابقة لشروط أي قسم)."
                        )

                    # سعر بيع مستهدف (تقني) = النطاق العلوي لبولينجر باندز - لو
                    # السعر فوقه فعلاً، السهم متشبع شرائياً ومفيش هامش صعود واضح
                    if upper > price:
                        target_sell_price = round(upper, 2)
                        target_sell_upside = round((target_sell_price / price - 1) * 100, 1)
                        st.info(
                            f"🎯 سعر بيع مستهدف (تقني): **{target_sell_price} {price_currency}** "
                            f"(+{target_sell_upside}% عن السعر الحالي) - النطاق العلوي لبولينجر باندز."
                        )
                    else:
                        st.warning(
                            "🎯 السعر الحالي **فوق** النطاق العلوي لبولينجر باندز فعلاً - "
                            "السهم متشبع شرائياً ومفيش هامش صعود فني واضح متبقي دلوقتي."
                        )

                    # وقف خسارة مقترح (تقني) = النطاق السفلي لبولينجر باندز
                    stop_loss_price = round(lower, 2)
                    stop_loss_downside = round((stop_loss_price / price - 1) * 100, 1)
                    if price < lower:
                        st.error(
                            f"🛑 السعر الحالي **كسر بالفعل** وقف الخسارة التقني "
                            f"({stop_loss_price} {price_currency}) - إشارة خطر، مش مجرد مستوى مستقبلي."
                        )
                    else:
                        st.info(
                            f"🛑 وقف خسارة مقترح (تقني): **{stop_loss_price} {price_currency}** "
                            f"({stop_loss_downside}% عن السعر الحالي) - النطاق السفلي لبولينجر باندز."
                        )

                    source_labels = {
                        "manual": "✍️ سعر يدوي (إنت أدخلته)",
                        "twelvedata": "🟢 Twelve Data (لحظي)",
                        "tradingview": "🟢 TradingView (لحظي، مصدر غير رسمي)",
                        "yahoo_fast_info": "🟡 Yahoo (شبه لحظي)",
                        "historical_close": "⚪ آخر إغلاق يومي (مش لحظي)",
                    }
                    st.caption(f"مصدر السعر: {source_labels.get(price_info['source'], price_info['source'])}")
                    if price_info.get("updated_at"):
                        st.caption(f"آخر تحديث يدوي: {price_info['updated_at']}")

                    # --- التحليل المالي الأساسي ---
                    fundamentals = fetch_fundamentals(ticker_input)
                    fund_score = score_fundamentals(fundamentals)

                    st.markdown("##### 💰 التحليل المالي الأساسي")
                    f1, f2, f3, f4 = st.columns(4)
                    pe_display = f"{fundamentals['pe_ratio']:.2f}" if fundamentals.get("pe_ratio") else "غير متاح"
                    roe_display = f"{fundamentals['roe_%']:.1f}%" if fundamentals.get("roe_%") is not None else "غير متاح"
                    pm_display = f"{fundamentals['profit_margin_%']:.1f}%" if fundamentals.get("profit_margin_%") is not None else "غير متاح"
                    f1.metric("مكرر الربحية P/E", pe_display)
                    f2.metric("العائد على حقوق الملكية ROE", roe_display)
                    f3.metric("هامش الربح", pm_display)
                    f4.metric("الدرجة المالية (من 100)", fund_score)

                    if not any(v is not None for v in fundamentals.values()):
                        st.caption(
                            "⚠️ البيانات المالية رجعت فاضية - على الأغلب Yahoo Finance رافض/حاظر "
                            "الطلبات المالية مؤقتاً (مشكلة معروفة مع yfinance). التحليل الفني فوق مش متأثر."
                        )

                    # --- قاعدة جراهام للسعر العادل ---
                    graham = graham_from_fundamentals(fundamentals, price)
                    st.markdown("##### 📐 قاعدة جراهام (المستثمر الدفاعي)")
                    g1, g2, g3 = st.columns(3)
                    graham_display = f"{graham['graham_number']:.2f} ج.م" if graham["graham_number"] else "غير متاح"
                    upside_display = f"{graham['graham_upside_%']:+.1f}%" if graham["graham_upside_%"] is not None else "—"
                    verdict_display = (
                        "✅ تحت السعر العادل" if graham["undervalued_per_graham"] is True
                        else "❌ فوق السعر العادل" if graham["undervalued_per_graham"] is False
                        else "غير متاح"
                    )
                    g1.metric("رقم جراهام (السعر العادل)", graham_display)
                    g2.metric("الفرق عن السعر الحالي", upside_display)
                    g3.metric("الحكم", verdict_display)

                    if graham["eps_estimated"] or graham["bvps_estimated"]:
                        st.caption(
                            "⚠️ EPS و/أو BVPS المستخدمين هنا **مُشتقين تقريبياً** من P/E و P/B "
                            "(Yahoo مارجعش القيم الفعلية مباشرة) - راجعهم يدوياً من investing.com "
                            "قبل أي قرار."
                        )

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].squeeze(), name='سعر الإغلاق', line=dict(color='#1f77b4', width=2)))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'].squeeze(), name='EMA 9', line=dict(color='#2ca02c', dash='dot')))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'].squeeze(), name='EMA 21', line=dict(color='#d62728', dash='dash')))
                    fig.update_layout(template="plotly_dark", height=450)
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"حدث خطأ: {e}")

with tab2:
    st.subheader("📊 الفرز والترتيب المتقدم لأسهم السوق")

    scan_source = st.radio(
        "امسح إيه؟", options=["سوق كامل", "المفضّلة بس"], horizontal=True, key="scan_source",
    )

    if scan_source == "المفضّلة بس":
        if not watchlist:
            st.warning("مفضّلتك فاضية - ضيف أسهم من قسم '⭐ المفضّلة' في الشريط الجانبي الأول.")
        scan_stocks = {t: t for t in watchlist}  # نستخدم الرمز نفسه كاسم لو مفيش اسم شركة مسجّل
        scan_sector_map = {t: get_sector(t) for t in watchlist}
        market_choice_scan = []  # مش محتاجين اختيار سوق في وضع المفضّلة
    else:
        market_choice_scan = st.multiselect(
            "🌍 اختر سوق واحد أو أكتر للمسح",
            options=list(MARKETS.keys()),
            format_func=lambda k: f"{MARKETS[k]['label']} ({len(MARKETS[k]['stocks'])} سهم)",
            default=["egx"],
        )
        if len(market_choice_scan) > 1:
            st.warning(
                "⚠️ اخترت أكتر من سوق مع بعض. العملة مختلفة لكل سوق (جنيه/دولار/درهم)، "
                "فمقارنة الأسعار وقيمة التداول بين الأسواق دي مش دقيقة من غير تحويل عملة."
            )

        # دمج قواميس الأسهم والقطاعات للأسواق المختارة
        scan_stocks = {}
        scan_sector_map = {}
        for mk in market_choice_scan:
            scan_stocks.update(MARKETS[mk]["stocks"])
            scan_sector_map.update(MARKETS[mk]["sector_map"])

    if len(market_choice_scan) == 1:
        default_liquidity_scan = MARKETS[market_choice_scan[0]]["default_min_liquidity"]
        currency_label_scan = MARKETS[market_choice_scan[0]]["currency_label"]
    else:
        default_liquidity_scan = 3_000_000
        currency_label_scan = "بالعملة المحلية لكل سهم (أسواق مختلطة)"

    include_fundamentals_scan = st.checkbox(
        "💰 تضمين التحليل المالي الأساسي + رقم جراهام (P/E, ROE, السعر العادل...) - "
        "أبطأ بكتير لأنه بيجيب بيانات إضافية لكل سهم",
        value=False,
    )

    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        available_sectors = sorted(set(scan_sector_map.values())) if scan_sector_map else []
        selected_sectors_scan = st.multiselect(
            "🏢 فلتر القطاع (اختر واحد أو أكتر - سيبه فاضي لعرض كل القطاعات)",
            options=available_sectors,
            default=[],
        )
    with fcol2:
        min_liquidity_scan = st.checkbox(
            f"💧 متوسط قيمة التداول اليومي (تقريبي) فوق {int(default_liquidity_scan):,} "
            f"{currency_label_scan} فقط",
            value=False,
        )
        min_liquidity_value_scan = st.number_input(
            "أو خصّص القيمة بنفسك", min_value=0, value=int(default_liquidity_scan), step=100_000,
        )
    with fcol3:
        selected_indices_scan = st.multiselect(
            "📊 فلتر عضوية EGX30/70 (لأسهم مصر بس - سيبه فاضي لعرض الكل)",
            options=["EGX30", "EGX70", "خارج EGX30/70"],
            default=[],
        )

    CATEGORY_OPTIONS = {
        "fresh": "🚀 أولاً: تأسيس مركز جديدة (قاع صاعد طازة)",
        "bottom": "📥 ثانياً: رادار تصيد القيعان",
        "short_term": "⚡ ثالثاً: مضاربة لحظية ويومية",
        "long_term": "📈 رابعاً: استثمار واتجاه صاعد مستقر",
    }
    selected_categories_scan = st.multiselect(
        "🗂️ عايز تشوف أي الأقسام بس؟ (سيبها فاضية أو اختار الكل لعرض الأربعة زي المعتاد)",
        options=list(CATEGORY_OPTIONS.keys()),
        format_func=lambda k: CATEGORY_OPTIONS[k],
        default=list(CATEGORY_OPTIONS.keys()),
    )

    if st.button("تشغيل الفرز والترتيب الاحترافي اللحظي 🚀"):
        fresh_cross_results = []
        bottom_accumulation_results = []
        short_term_trading = []
        long_term_investment = []
        
        progress_bar = st.progress(0)
        total_stocks = len(scan_stocks)
        
        with st.spinner(f"جاري مسح {len(scan_stocks)} سهم على دفعات ({BATCH_SIZE} سهم لكل دفعة) + إعادة محاولة الأسهم اللي تفشل..."):
            tickers_list = list(scan_stocks.values())
            all_data, failed_tickers = fetch_batch_data(tuple(tickers_list), period="60d")

            if failed_tickers:
                st.warning(
                    f"⚠️ تعذر تحميل بيانات {len(failed_tickers)} سهم من أصل {len(tickers_list)} "
                    "(ممكن يكون توقف تداولهم مؤقتاً أو رفض مؤقت من المصدر). "
                    "التفاصيل الكاملة هتلاقيها في آخر الصفحة تحت 'الأسهم اللي اتخطاها'."
                )

            skipped_count = 0
            skipped_names = []
            for idx, (name, ticker) in enumerate(scan_stocks.items()):
                progress_bar.progress((idx + 1) / total_stocks)
                if ticker not in all_data:
                    skipped_count += 1
                    skipped_names.append((name, ticker, "لم يتم تحميل بياناته من المصدر"))
                    continue
                try:
                    stock_df = all_data[ticker].dropna(how='all')
                    if stock_df.empty or len(stock_df) < 25:
                        skipped_count += 1
                        skipped_names.append((name, ticker, "بيانات تاريخية غير كافية (أقل من 25 يوم)"))
                        continue
                        
                    stock_df = calculate_indicators(stock_df)
                    row = stock_df.iloc[-1]
                    prev_row = stock_df.iloc[-CROSS_LOOKBACK]
                    
                    p = float(row['Close'])
                    e9 = float(row['EMA9'])
                    e21 = float(row['EMA21'])
                    r = float(row['RSI_14'])
                    m = float(row['MFI_14'])
                    u = float(row['Upper_Band'])
                    l = float(row['Lower_Band'])
                    vol_today = float(row['Volume'])
                    vol_ma10 = float(row['Vol_MA10'])
                    
                    if vol_today < 50000:
                        continue

                    # متوسط قيمة التداول اليومي (تقريبي) = السعر × متوسط فوليوم 10 أيام
                    # (تقريب عملي بدل حساب rolling كامل لـ Close*Volume - كافي للفلترة)
                    avg_trade_value = p * vol_ma10
                    if min_liquidity_scan and avg_trade_value < min_liquidity_value_scan:
                        continue

                    sector = scan_sector_map.get(ticker, "غير مصنف")
                    if selected_sectors_scan and sector not in selected_sectors_scan:
                        continue

                    if selected_indices_scan and get_egx_index(ticker) not in selected_indices_scan:
                        continue
                        
                    is_new_cross = (prev_row['EMA9'] <= prev_row['EMA21']) and (e9 > e21)
                    
                    momentum_score = 0
                    if e9 > e21: momentum_score += 40
                    if 50 <= m <= 70: momentum_score += 30
                    elif 35 <= m < 50: momentum_score += 15
                    elif m > 85: momentum_score -= 25
                    if 45 <= r <= 65: momentum_score += 20
                    elif r > 75: momentum_score -= 20
                    if u > l: momentum_score += ((u - p) / (u - l)) * 10
                    if vol_today > vol_ma10: momentum_score += 10
                    
                    if m > 85 or r > 78:
                        status = "🚨 تصريف / خروج (تضخم)"
                    elif momentum_score >= 70:
                        status = "⚡ STRONG BUY (شراء قوي)"
                    elif 50 <= momentum_score < 70:
                        status = "🟢 إيجابي (متوسط)"
                    else:
                        status = "🟡 HOLD (مراقبة)"
                    
                    currency = get_currency(ticker)

                    # سعر بيع مستهدف (تقني) = النطاق العلوي لبولينجر باندز - None
                    # لو السعر فوقه فعلاً (متشبع شرائياً، مفيش هامش صعود واضح)
                    if u > p:
                        target_sell_price = round(u, 2)
                        target_sell_upside = round((target_sell_price / p - 1) * 100, 1)
                    else:
                        target_sell_price = None
                        target_sell_upside = None

                    # وقف خسارة مقترح (تقني) = النطاق السفلي لبولينجر باندز
                    stop_loss_price = round(l, 2)
                    stop_loss_downside = round((stop_loss_price / p - 1) * 100, 1)
                    stop_loss_broken = p < l

                    data_entry = {
                        "النقاط الفنية والسيولة (من 100)": round(momentum_score, 1),
                        "اسم الشركة": name,
                        "الرمز البرمجي": ticker,
                        "القطاع": sector,
                        "مؤشر EGX30/70": get_egx_index(ticker),
                        "العملة": currency,
                        "السعر الحالي": round(p, 2),
                        "سعر بيع مستهدف (تقني)": target_sell_price,
                        "فرق السعر المستهدف %": target_sell_upside,
                        "وقف خسارة مقترح": stop_loss_price,
                        "فرق وقف الخسارة %": stop_loss_downside,
                        "وقف الخسارة مكسور؟": stop_loss_broken,
                        "مؤشر الزخم RSI": round(r, 1),
                        "مؤشر السيولة MFI": round(m, 1),
                        "فوليوم اليوم": f"{vol_today:,.0f}",
                        "متوسط فوليوم 10أيام": f"{vol_ma10:,.0f}",
                        "متوسط قيمة التداول (تقريبي)": f"{avg_trade_value:,.0f}",
                        "التقييم الفني": status
                    }

                    # التحليل المالي + جراهام بيتحسبوا مرة واحدة هنا وبيتطبقوا على
                    # الأربع فئات كلها (مش بس فئة الاستثمار المستقر) - عشان تقدر
                    # تشوف الجانب المالي حتى لأسهم المضاربة السريعة أو القيعان
                    fund_score_for_verdict = None
                    fundamentals_fetched = True
                    if include_fundamentals_scan:
                        fundamentals = fetch_fundamentals(ticker)
                        fund_score = score_fundamentals(fundamentals)
                        fund_score_for_verdict = fund_score
                        fundamentals_fetched = any(v is not None for v in fundamentals.values())
                        combined_score = round(0.6 * momentum_score + 0.4 * fund_score, 1)
                        data_entry["الدرجة المالية (من 100)"] = fund_score
                        data_entry["مكرر الربحية P/E"] = (
                            round(fundamentals["pe_ratio"], 2) if fundamentals.get("pe_ratio") else None
                        )
                        data_entry["الدرجة الشاملة (فني+مالي)"] = combined_score

                        graham = graham_from_fundamentals(fundamentals, p)
                        data_entry["رقم جراهام"] = graham["graham_number"]
                        data_entry["فرق جراهام %"] = graham["graham_upside_%"]
                        data_entry["تحت السعر العادل؟"] = graham["undervalued_per_graham"]

                    verdict = compute_verdict(
                        momentum_score, fund_score_for_verdict,
                        include_fundamentals=include_fundamentals_scan,
                        fundamentals_fetched=fundamentals_fetched,
                    )
                    data_entry.update(verdict)
                    
                    if is_new_cross and r < 52:
                        data_entry["التقييم الفني"] = "✨ تأسيس مركز (قاع صاعد طازة)"
                        if "fresh" in selected_categories_scan:
                            fresh_cross_results.append(data_entry)

                    elif r < 35 and m < 35:
                        data_entry["التقييم الفني"] = "🛒 قاع تجميع (فرصة مراقبة صامتة)"
                        if "bottom" in selected_categories_scan:
                            bottom_accumulation_results.append(data_entry)

                    elif e9 > e21:
                        if vol_today > (vol_ma10 * 1.15) and 50 <= r <= 78:
                            data_entry["التقييم الفني"] = f"{status} [مضاربة لحظية]"
                            if "short_term" in selected_categories_scan:
                                short_term_trading.append(data_entry)
                        else:
                            data_entry["التقييم الفني"] = f"{status} [استثمار مستقر]"
                            if "long_term" in selected_categories_scan:
                                long_term_investment.append(data_entry)
                except Exception as e:
                    skipped_count += 1
                    skipped_names.append((name, ticker, f"خطأ أثناء التحليل: {e}"))
                    continue
            
            if skipped_count:
                st.info(f"ℹ️ تم تخطي {skipped_count} سهم أثناء التحليل (بيانات ناقصة أو تعذر حساب المؤشرات).")
                with st.expander(f"📋 عرض تفاصيل الـ {skipped_count} سهم اللي اتخطاها"):
                    for name, ticker, reason in skipped_names:
                        st.write(f"- **{name}** ({ticker}) — {reason}")

            st.success("تم التحديث النهائي والإغلاق الهندسي للرادار بنجاح! 🦅")
            
            # --- آلية الإرسال المعدلة لـ 5 فرص ---
            telegram_msg = "🦅 *تقرير قناص البورصة المصرية اللحظي* 🇪🇬\n\n"
            
            if fresh_cross_results:
                telegram_msg += "🌟 *أسهم تأسيس المركز (قاع صاعد):*\n"
                for item in fresh_cross_results[:5]: # تم التعديل لـ 5
                    telegram_msg += f"- {item['اسم الشركة']} ({item['السعر الحالي']} {item.get('العملة', 'EGP')})\n"
                telegram_msg += "\n"
                
            if long_term_investment:
                # ترتيب واختيار أعلى 5 أسهم استثمار
                _lt_df = pd.DataFrame(long_term_investment)
                _sort_col = "الدرجة الشاملة (فني+مالي)" if "الدرجة الشاملة (فني+مالي)" in _lt_df.columns else "النقاط الفنية والسيولة (من 100)"
                top_inv = _lt_df.sort_values(by=_sort_col, ascending=False).head(5) # تم التعديل لـ 5
                telegram_msg += "📈 *أقوى أسهم الاتجاه الصاعد المستقر:*\n"
                for _, row_inv in top_inv.iterrows():
                    telegram_msg += f"- {row_inv['اسم الشركة']} | السعر: {row_inv['السعر الحالي']} {row_inv.get('العملة', 'EGP')} | النقاط: {row_inv['النقاط الفنية والسيولة (من 100)']}\n"
                telegram_msg += "\n"
                
            if short_term_trading:
                # ترتيب واختيار أعلى 5 أسهم مضاربة
                top_trade = pd.DataFrame(short_term_trading).sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False).head(5) # تم التعديل لـ 5
                telegram_msg += "⚡ *أقوى أسهم المضاربة اللحظية وعزم السيولة:*\n"
                for _, row_tr in top_trade.iterrows():
                    telegram_msg += f"- {row_tr['اسم الشركة']} | السعر: {row_tr['السعر الحالي']} {row_tr.get('العملة', 'EGP')}\n"
            
            # إرسال الرسالة الكاملة والملخصة مرة واحدة فقط
            tg_success, tg_status_msg = send_telegram_alert(telegram_msg)
            if TELEGRAM_TOKEN or default_token or TELEGRAM_CHAT_ID or default_chat_id:
                # منعرضش حاجة لو المستخدم أصلاً مالوش إعدادات تليجرام متسجلة
                if tg_success:
                    st.sidebar.success(tg_status_msg)
                else:
                    st.sidebar.error(tg_status_msg)
            
            # عرض الجداول على الشاشة
            if "fresh" in selected_categories_scan:
                st.markdown("### 🚀 أولاً: أسهم لقطت 'إشارة تأسيس مركز جديدة اليوم' (آمنة وصارمة، RSI < 52)")
                if fresh_cross_results:
                    st.dataframe(pd.DataFrame(fresh_cross_results).sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False), use_container_width=True)
                else:
                    st.info("لا توجد أسهم لقطت تقاطع ذهبي هادئ اليوم واستوفت شروط الفوليوم الحقيقي.")
                st.write("---")

            if "bottom" in selected_categories_scan:
                st.markdown("### 📥 ثانياً: رادار تصيد القيعان (أسهم رخيصة جداً في مناطق تجميع الحيتان 🐋)")
                if bottom_accumulation_results:
                    st.dataframe(pd.DataFrame(bottom_accumulation_results).sort_values(by="مؤشر الزخم RSI", ascending=True), use_container_width=True)
                else:
                    st.info("لا توجد أسهم حالياً في قيعان التشبع البيعي الحاد تحت 35 تنطبق عليها شروط الفوليوم الأمان.")
                st.write("---")

            if "short_term" in selected_categories_scan:
                st.markdown("### ⚡ ثالثاً: أسهم المضاربة اللحظية واليومية (سيولة ضخمة وعزم سريع محمي من التضخم)")
                if short_term_trading:
                    st.dataframe(pd.DataFrame(short_term_trading).sort_values(by="فوليوم اليوم", ascending=False), use_container_width=True)
                else:
                    st.info("لا توجد أسهم مستوفية لشروط الحركات المضاربية النشطة والآمنة حالياً.")
                st.write("---")

            if "long_term" in selected_categories_scan:
                st.markdown("### 📈 رابعاً: أسهم الاستثمار والاتجاه الصاعد المستقر (طويل الأجل وآمن)")
                if long_term_investment:
                    lt_df = pd.DataFrame(long_term_investment)
                    sort_col = "الدرجة الشاملة (فني+مالي)" if "الدرجة الشاملة (فني+مالي)" in lt_df.columns else "النقاط الفنية والسيولة (من 100)"
                    st.dataframe(lt_df.sort_values(by=sort_col, ascending=False), use_container_width=True)
                    if include_fundamentals_scan:
                        st.caption(
                            "💡 مرتبة حسب 'الدرجة الشاملة' = 60% فني + 40% مالي. "
                            "لو عمود مكرر الربحية P/E فاضي لسهم معين، يبقى Yahoo مارجعش بيانات مالية له."
                        )

            # --- الملخص الشامل: التوصية النهائية (فني + مالي مع بعض) عبر كل الفئات ---
            st.markdown("---")
            st.markdown("### 🎯 خامساً: التوصية النهائية (فني + مالي مع بعض) - كل الأسهم")
            st.caption(
                f"🟢 شراء = النقاط الفنية والمالية الاتنين فوق {VERDICT_BUY_MIN_TECH}. "
                f"🔴 بيع = الاتنين تحت {VERDICT_SELL_MAX_TECH}/{VERDICT_SELL_MAX_FUND}. "
                "🟡 انتظار = إشارات متضاربة أو بيانات ناقصة. هذا ليس توصية استثمارية."
            )
            all_results = (fresh_cross_results + bottom_accumulation_results
                            + short_term_trading + long_term_investment)
            if all_results:
                st.session_state["last_scan_prices"] = {
                    r["الرمز البرمجي"]: r["السعر الحالي"] for r in all_results
                }
                all_df = pd.DataFrame(all_results)
                if "ترتيب_التوصية" in all_df.columns:
                    verdict_cols = [c for c in [
                        "اسم الشركة", "الرمز البرمجي", "القطاع", "العملة", "السعر الحالي",
                        "التوصية", "النقاط الفنية والسيولة (من 100)", "الدرجة المالية (من 100)",
                    ] if c in all_df.columns]
                    sort_cols = [c for c in ["ترتيب_التوصية", "النقاط الفنية والسيولة (من 100)"]
                                 if c in all_df.columns]
                    st.dataframe(
                        all_df.sort_values(by=sort_cols, ascending=[True] + [False] * (len(sort_cols) - 1))[verdict_cols],
                        use_container_width=True,
                    )
                    vcounts = all_df["التوصية"].value_counts()
                    vc1, vc2, vc3 = st.columns(3)
                    vc1.metric("🟢 شراء", int(sum(v for k, v in vcounts.items() if "شراء" in k)))
                    vc2.metric("🟡 انتظار", int(sum(v for k, v in vcounts.items() if "انتظار" in k)))
                    vc3.metric("🔴 بيع", int(sum(v for k, v in vcounts.items() if "بيع" in k)))
            else:
                st.info("مفيش أسهم عدّت الفلاتر عشان نوريك توصية ليها.")


_PORTFOLIO_CSV = "portfolio.csv"


def load_portfolio() -> pd.DataFrame:
    if os.path.exists(_PORTFOLIO_CSV):
        try:
            return pd.read_csv(_PORTFOLIO_CSV)
        except Exception:
            pass
    return pd.DataFrame(columns=["ticker", "entry_price", "quantity"])


def save_portfolio(df_p: pd.DataFrame):
    df_p.to_csv(_PORTFOLIO_CSV, index=False)


with tab3:
    st.subheader("💼 محفظتي - تتبع الربح/الخسارة")
    st.caption(
        "سجّل الأسهم اللي فعلاً اشتريتها بسعر دخولك الحقيقي. الأداة هتقارنها "
        "بآخر سعر حلّلته لنفس السهم (سواء من الفحص التفصيلي أو المسح الشامل) "
        "في نفس الجلسة دي - لازم تحلل السهم مرة على الأقل الأول عشان نلاقي سعره."
    )

    portfolio_df = load_portfolio()

    pf_col1, pf_col2, pf_col3 = st.columns(3)
    with pf_col1:
        pf_ticker = st.text_input("رمز السهم", key="pf_ticker_fb")
    with pf_col2:
        pf_entry = st.number_input("سعر الدخول", min_value=0.0, step=0.01, key="pf_entry_fb")
    with pf_col3:
        pf_qty = st.number_input("الكمية (اختياري)", min_value=0.0, step=1.0, key="pf_qty_fb", value=0.0)

    pf_add_col, pf_remove_col = st.columns(2)
    with pf_add_col:
        if st.button("➕ إضافة/تحديث في المحفظة", key="pf_add_btn_fb"):
            if pf_ticker and pf_entry > 0:
                portfolio_df = portfolio_df[portfolio_df["ticker"] != pf_ticker.strip()]
                new_row = pd.DataFrame([{
                    "ticker": pf_ticker.strip(), "entry_price": pf_entry, "quantity": pf_qty,
                }])
                portfolio_df = pd.concat([portfolio_df, new_row], ignore_index=True)
                save_portfolio(portfolio_df)
                st.success(f"✅ اتحفظ {pf_ticker} بسعر دخول {pf_entry}")
                st.rerun()
            else:
                st.warning("لازم رمز السهم وسعر دخول أكبر من صفر.")
    with pf_remove_col:
        if st.button("🗑️ حذف من المحفظة", key="pf_remove_btn_fb"):
            if pf_ticker:
                portfolio_df = portfolio_df[portfolio_df["ticker"] != pf_ticker.strip()]
                save_portfolio(portfolio_df)
                st.success(f"🗑️ اتشال {pf_ticker} من المحفظة")
                st.rerun()

    if portfolio_df.empty:
        st.info("محفظتك فاضية - ضيف أول سهم من الفورم فوق.")
    else:
        price_lookup = st.session_state.get("last_scan_prices", {})
        rows = []
        for _, row in portfolio_df.iterrows():
            current_price = price_lookup.get(row["ticker"])
            entry = row["entry_price"]
            qty = row.get("quantity", 0) or 0
            if current_price is not None:
                pnl_pct = round((current_price / entry - 1) * 100, 2)
                pnl_value = round((current_price - entry) * qty, 2) if qty else None
            else:
                pnl_pct = None
                pnl_value = None
            rows.append({
                "الرمز": row["ticker"],
                "سعر الدخول": entry,
                "الكمية": qty if qty else "—",
                "السعر الحالي": current_price if current_price is not None else "حلّل السهم ده الأول",
                "الربح/الخسارة %": pnl_pct,
                "الربح/الخسارة (قيمة)": pnl_value,
            })

        pf_display = pd.DataFrame(rows)
        st.dataframe(pf_display, use_container_width=True, hide_index=True)

        total_value_rows = [r["الربح/الخسارة (قيمة)"] for r in rows if r["الربح/الخسارة (قيمة)"] is not None]
        if total_value_rows:
            st.metric("إجمالي الربح/الخسارة (للأسهم اللي معاها كمية)", f"{sum(total_value_rows):,.2f}")
