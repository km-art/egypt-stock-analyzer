import time
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="قناص البورصة العالمية الاحترافي 🌍📈", layout="wide")

st.title("🦅 قناص البورصة العالمية (مصر - أمريكا - الإمارات)")
st.write("تم تقفيل الكود بمعايير صارمة: إضافة حد أدنى للفوليوم لحجب الأسهم الميتة، وفلاتر حماية من التضخم الحاد.")

# إعدادات عامة قابلة للتعديل
BATCH_SIZE = 30
BATCH_DELAY = 1.5
CROSS_LOOKBACK = 3

# القراءة التلقائية من Streamlit Secrets
try:
    default_token = st.secrets.get("TELEGRAM_TOKEN", "")
    default_chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
except Exception:
    default_token = ""
    default_chat_id = ""

# إعدادات التنبيهات في الشريط الجانبي
st.sidebar.header("⚙️ إعدادات إشعارات الموبايل (تليجرام)")
TELEGRAM_TOKEN = st.sidebar.text_input("أدخل Token البوت:", value=default_token, type="password")
TELEGRAM_CHAT_ID = st.sidebar.text_input("أدخل Chat ID الخاص بك:", value=default_chat_id)

def send_telegram_alert(message):
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

# ============================================================
# الأسهم المصرية (EGX)
# ============================================================
EGX_STOCKS = {
    "البنك التجاري الدولي": "COMI.CA",
    "مجموعة طلعت مصطفى": "TMGH.CA",
    "السويدي إليكتريك": "SWDY.CA",
    "المصرية للاتصالات": "ETEL.CA",
    "مصر للألومنيوم": "EGAL.CA",
    "مصر لإنتاج الأسمدة - موبكو": "MFPC.CA",
    "الشرقية - إيسترن كومباني": "EAST.CA",
    "أبو قير للأسمدة": "ABUK.CA",
    "أوراسكوم للاستثمار القابضة": "OIH.CA",
    "أوراسكوم للتنمية مصر": "ORHD.CA",
    "إي فاينانس للاستثمارات": "EFIH.CA",
    "إيديتا للصناعات الغذائية": "EFID.CA",
    "جهينة للصناعات الغذائية": "JUFO.CA",
    "فاركو للأدوية": "PHAR.CA",
    "فوري للمدفوعات الإلكترونية": "FWRY.CA",
    "مجموعة إيـفـإى جـي هيرميس": "HRHO.CA",
    "حديد عز": "ESRS.CA",
    "بالم هيلز للتعمير": "PHDC.CA",
    "مدينة مصر للإسكان": "MASR.CA",
    "مصر الجديدة للإسكان": "HELI.CA",
    "بنك التعمير والإسكان": "HDBK.CA",
    "بنك البركة مصر": "SAUD.CA",
    "بنك قناة السويس": "CANA.CA",
    "مصرف أبوظبي الإسلامي": "ADIB.CA",
    "القلعة للاستشارات المالية": "CCAP.CA",
    "بلتون المالية القابضة": "BTFH.CA",
    "راكتا لورق التعبئة": "RAKT.CA",
    "دومتي": "DOMT.CA",
    "غاز مصر": "EGAS.CA",
    "سيدي كرير للبتروكيماويات": "SKPC.CA",
    "كيما - الصناعات الكيماوية": "EGCH.CA",
    "العز الدخيلة للصلب": "IRAX.CA",
    "النيل للأدوية": "NIPH.CA",
    "ابن سينا فارما": "ISPH.CA",
    "إعمار مصر للتنمية": "EMFD.CA",
}

# ============================================================
# الأسهم الأمريكية (US) - الرموز الصحيحة
# ============================================================
US_STOCKS = {
    "Apple Inc.": "AAPL",
    "Microsoft Corporation": "MSFT",
    "Amazon.com Inc.": "AMZN",
    "Alphabet Inc. (Google)": "GOOGL",
    "Meta Platforms Inc.": "META",
    "Tesla Inc.": "TSLA",
    "NVIDIA Corporation": "NVDA",
    "Berkshire Hathaway": "BRK-B",
    "Johnson & Johnson": "JNJ",
    "Visa Inc.": "V",
    "Procter & Gamble": "PG",
    "JPMorgan Chase": "JPM",
    "UnitedHealth Group": "UNH",
    "Home Depot": "HD",
    "Walmart Inc.": "WMT",
    "Mastercard Inc.": "MA",
    "Coca-Cola Company": "KO",
    "PepsiCo Inc.": "PEP",
    "Cisco Systems": "CSCO",
    "Intel Corporation": "INTC",
    "IBM": "IBM",
    "Netflix Inc.": "NFLX",
    "PayPal Holdings": "PYPL",
    "Adobe Inc.": "ADBE",
    "Salesforce Inc.": "CRM",
    "Oracle Corporation": "ORCL",
    "Caterpillar Inc.": "CAT",
    "Boeing Company": "BA",
    "McDonald's Corporation": "MCD",
    "Disney (Walt) Co.": "DIS",
    "Nike Inc.": "NKE",
    "Starbucks Corporation": "SBUX",
    "Costco Wholesale": "COST",
    "Chevron Corporation": "CVX",
    "Exxon Mobil": "XOM",
    "Philip Morris": "PM",
    "Altria Group": "MO",
    "Abbott Laboratories": "ABT",
    "AbbVie Inc.": "ABBV",
    "Eli Lilly": "LLY",
    "Pfizer Inc.": "PFE",
    "Merck & Co.": "MRK",
    "Amgen Inc.": "AMGN",
    "Gilead Sciences": "GILD",
    "Biogen Inc.": "BIIB",
    "Moderna Inc.": "MRNA",
    "Broadcom Inc.": "AVGO",
    "Texas Instruments": "TXN",
    "Qualcomm Inc.": "QCOM",
    "Advanced Micro Devices": "AMD",
    "Micron Technology": "MU",
    "Applied Materials": "AMAT",
    "Lam Research": "LRCX",
    "ASML Holding": "ASML",
    "Taiwan Semiconductor": "TSM",
    "SAP SE": "SAP",
    "Accenture plc": "ACN",
    "Dell Technologies": "DELL",
    "HP Inc.": "HPQ",
    "CrowdStrike Holdings": "CRWD",
    "Palo Alto Networks": "PANW",
    "Fortinet Inc.": "FTNT",
    "ServiceNow Inc.": "NOW",
    "Uber Technologies": "UBER",
    "Airbnb Inc.": "ABNB",
    "Booking Holdings": "BKNG",
    "American Express": "AXP",
    "Goldman Sachs": "GS",
    "Morgan Stanley": "MS",
    "Bank of America": "BAC",
    "Wells Fargo": "WFC",
    "Citigroup Inc.": "C",
    "BlackRock Inc.": "BLK",
}

# ============================================================
# الأسهم الإماراتية (UAE) - رموز Yahoo Finance الصحيحة
# ============================================================
UAE_STOCKS = {
    # البنوك الإماراتية
    "First Abu Dhabi Bank": "FAB.AD",
    "Abu Dhabi Commercial Bank": "ADCB.AD",
    "Abu Dhabi Islamic Bank": "ADIB.AD",
    "Emirates NBD Bank": "EMIRATES.AD",
    "Dubai Islamic Bank": "DIB.AD",
    "Sharjah Islamic Bank": "SIB.AD",
    "Ras Al Khaimah National Bank": "RAKBNK.AD",
    "National Bank of Umm Al Quwain": "NBQ.AD",
    "United Arab Bank": "UAB.AD",
    "Commercial Bank of Dubai": "CBD.AD",
    "Ajman Bank": "AJMANBANK.AD",
    "Emirates Islamic Bank": "EIB.AD",
    
    # العقارات والتطوير
    "Aldar Properties": "ALDAR.AD",
    "Emaar Properties": "EMAAR.AD",
    "DAMAC Properties": "DAMAC.AD",
    "RAK Properties": "RAKPROP.AD",
    "Deyaar Development": "DEYAAR.AD",
    "Union Properties": "UPP.AD",
    "Manazel Real Estate": "MANAZEL.AD",
    "Emaar Development": "EMAARDEV.AD",
    "Dubai Investments": "DINV.AD",
    
    # الطاقة والموارد
    "ADNOC Distribution": "ADNOCDIST.AD",
    "ADNOC Drilling": "ADNOCDRILL.AD",
    "ADNOC Gas": "ADNOCGAS.AD",
    "Dana Gas": "DANA.AD",
    "TAQA (Abu Dhabi National Energy)": "TAQA.AD",
    "Emirates District Cooling (Tabreed)": "TABREED.AD",
    "Gulf Navigation Holding": "GULFNAV.AD",
    
    # الاتصالات والتكنولوجيا
    "Etisalat (Emirates Telecom)": "ETISALAT.AD",
    "du (Emirates Integrated Telecom)": "DU.AD",
    "Sirocom": "SIRO.AD",
    "Salik Company": "SALIK.AD",
    
    # الصناعة والنقل
    "Abu Dhabi Ports Company": "ADPORTS.AD",
    "National Marine Dredging Company": "NMDC.AD",
    "Abu Dhabi Ship Building": "ADSB.AD",
    "Agility Public Warehousing": "AGILITY.AD",
    "Aramex International": "ARMX.AD",
    "Air Arabia": "AIRA.AD",
    "Gulf Cement Company": "GCC.AD",
    "National Cement Company": "NCC.AD",
    "Ras Al Khaimah Cement": "RAKC.AD",
    "Sharjah Cement": "SHARJAH.AD",
    "Arkan Building Materials": "ARKAN.AD",
    "Al Seer Marine": "ALSEER.AD",
    
    # الاستثمار والمالية
    "International Holdings Co. (IHC)": "IHC.AD",
    "Alpha Dhabi Holding": "ALPHADHABI.AD",
    "Q Holding": "QHOLDING.AD",
    "Waha Capital": "WAHA.AD",
    "Invest Bank": "INVESTB.AD",
    "Dubai Financial Market": "DFM.AD",
    "Abu Dhabi National Hotels": "ADNH.AD",
    "Bayan Investment": "BAYAN.AD",
    "Eshraq Investments": "ESHRAQ.AD",
    
    # الرعاية الصحية والأدوية
    "Burjeel Holdings": "BURJEEL.AD",
    "Gulf Medical Projects": "GMP.AD",
    "Response Plus Holding": "RPM.AD",
    
    # الغذاء والزراعة
    "Foodco Holding": "FOODCO.AD",
    "Fertiglobe": "FERTIGLB.AD",
    "Al Ain Holding": "AINHOLD.AD",
    
    # أخرى
    "Palms Sports": "PALMS.AD",
    "Phoenix Group": "PHOENIX.AD",
    "AMG International": "AMG.AD",
    "Borosil Glass": "BOROSIL.AD",
    "Abu Dhabi National Company for Building Materials": "BILDCO.AD",
    "Energy Holding": "ENERGY.AD",
    "Ghurair Group": "GHURAIR.AD",
}

# ============================================================
# دمج جميع الأسهم مع تصنيفات القطاعات
# ============================================================

# دمج الأسهم
ALL_STOCKS = {}
ALL_STOCKS.update(EGX_STOCKS)
ALL_STOCKS.update({f"{k} (US)": v for k, v in US_STOCKS.items()})
ALL_STOCKS.update({f"{k} (UAE)": v for k, v in UAE_STOCKS.items()})

# تصنيف القطاعات للأسهم المصرية
EGYPT_SECTOR = {
    "COMI.CA": "بنوك", "TMGH.CA": "عقاري", "SWDY.CA": "تصنيع", "ETEL.CA": "تكنولوجيا",
    "EGAL.CA": "تصنيع", "MFPC.CA": "تصنيع", "EAST.CA": "استهلاكي", "ABUK.CA": "تصنيع",
    "OIH.CA": "مالي", "ORHD.CA": "عقاري", "EFIH.CA": "تكنولوجيا", "EFID.CA": "استهلاكي",
    "JUFO.CA": "استهلاكي", "PHAR.CA": "صحي", "FWRY.CA": "تكنولوجيا", "HRHO.CA": "مالي",
    "ESRS.CA": "تصنيع", "PHDC.CA": "عقاري", "MASR.CA": "عقاري", "HELI.CA": "عقاري",
    "HDBK.CA": "بنوك", "SAUD.CA": "بنوك", "CANA.CA": "بنوك", "ADIB.CA": "بنوك",
    "CCAP.CA": "مالي", "BTFH.CA": "مالي", "RAKT.CA": "تصنيع", "DOMT.CA": "استهلاكي",
    "EGAS.CA": "طاقة", "SKPC.CA": "تصنيع", "EGCH.CA": "تصنيع", "IRAX.CA": "تصنيع",
    "NIPH.CA": "صحي", "ISPH.CA": "صحي", "EMFD.CA": "عقاري",
}

# تصنيف القطاعات للأسهم الأمريكية
US_SECTOR = {
    "AAPL": "تكنولوجيا", "MSFT": "تكنولوجيا", "AMZN": "استهلاكي", "GOOGL": "تكنولوجيا",
    "META": "تكنولوجيا", "TSLA": "استهلاكي", "NVDA": "تكنولوجيا", "BRK-B": "مالي",
    "JNJ": "صحي", "V": "مالي", "PG": "استهلاكي", "JPM": "مالي",
    "UNH": "صحي", "HD": "استهلاكي", "WMT": "استهلاكي", "MA": "مالي",
    "KO": "استهلاكي", "PEP": "استهلاكي", "CSCO": "تكنولوجيا", "INTC": "تكنولوجيا",
    "IBM": "تكنولوجيا", "NFLX": "تكنولوجيا", "PYPL": "مالي", "ADBE": "تكنولوجيا",
    "CRM": "تكنولوجيا", "ORCL": "تكنولوجيا", "CAT": "صناعي", "BA": "صناعي",
    "MCD": "استهلاكي", "DIS": "تكنولوجيا", "NKE": "استهلاكي", "SBUX": "استهلاكي",
    "COST": "استهلاكي", "CVX": "طاقة", "XOM": "طاقة", "PM": "استهلاكي",
    "MO": "استهلاكي", "ABT": "صحي", "ABBV": "صحي", "LLY": "صحي",
    "PFE": "صحي", "MRK": "صحي", "AMGN": "صحي", "GILD": "صحي",
    "BIIB": "صحي", "MRNA": "صحي", "AVGO": "تكنولوجيا", "TXN": "تكنولوجيا",
    "QCOM": "تكنولوجيا", "AMD": "تكنولوجيا", "MU": "تكنولوجيا", "AMAT": "تكنولوجيا",
    "LRCX": "تكنولوجيا", "ASML": "تكنولوجيا", "TSM": "تكنولوجيا", "SAP": "تكنولوجيا",
    "ACN": "تكنولوجيا", "DELL": "تكنولوجيا", "HPQ": "تكنولوجيا", "CRWD": "تكنولوجيا",
    "PANW": "تكنولوجيا", "FTNT": "تكنولوجيا", "NOW": "تكنولوجيا", "UBER": "تكنولوجيا",
    "ABNB": "استهلاكي", "BKNG": "استهلاكي", "AXP": "مالي", "GS": "مالي",
    "MS": "مالي", "BAC": "مالي", "WFC": "مالي", "C": "مالي", "BLK": "مالي",
}

# تصنيف القطاعات للأسهم الإماراتية
UAE_SECTOR = {
    "FAB.AD": "بنوك", "ADCB.AD": "بنوك", "ADIB.AD": "بنوك", "EMIRATES.AD": "بنوك",
    "DIB.AD": "بنوك", "SIB.AD": "بنوك", "RAKBNK.AD": "بنوك", "NBQ.AD": "بنوك",
    "UAB.AD": "بنوك", "CBD.AD": "بنوك", "AJMANBANK.AD": "بنوك", "EIB.AD": "بنوك",
    "ALDAR.AD": "عقاري", "EMAAR.AD": "عقاري", "DAMAC.AD": "عقاري", "RAKPROP.AD": "عقاري",
    "DEYAAR.AD": "عقاري", "UPP.AD": "عقاري", "MANAZEL.AD": "عقاري", "EMAARDEV.AD": "عقاري",
    "DINV.AD": "مالي", "ADNOCDIST.AD": "طاقة", "ADNOCDRILL.AD": "طاقة", "ADNOCGAS.AD": "طاقة",
    "DANA.AD": "طاقة", "TAQA.AD": "طاقة", "TABREED.AD": "طاقة", "GULFNAV.AD": "صناعي",
    "ETISALAT.AD": "تكنولوجيا", "DU.AD": "تكنولوجيا", "SIRO.AD": "تكنولوجيا", "SALIK.AD": "صناعي",
    "ADPORTS.AD": "صناعي", "NMDC.AD": "صناعي", "ADSB.AD": "صناعي", "AGILITY.AD": "صناعي",
    "ARMX.AD": "صناعي", "AIRA.AD": "صناعي", "GCC.AD": "تصنيع", "NCC.AD": "تصنيع",
    "RAKC.AD": "تصنيع", "SHARJAH.AD": "تصنيع", "ARKAN.AD": "تصنيع", "ALSEER.AD": "صناعي",
    "IHC.AD": "مالي", "ALPHADHABI.AD": "مالي", "QHOLDING.AD": "مالي", "WAHA.AD": "مالي",
    "INVESTB.AD": "مالي", "DFM.AD": "مالي", "ADNH.AD": "استهلاكي", "BAYAN.AD": "مالي",
    "ESHRAQ.AD": "مالي", "BURJEEL.AD": "صحي", "GMP.AD": "صحي", "RPM.AD": "صحي",
    "FOODCO.AD": "استهلاكي", "FERTIGLB.AD": "تصنيع", "AINHOLD.AD": "مالي",
    "PALMS.AD": "استهلاكي", "PHOENIX.AD": "مالي", "AMG.AD": "مالي", "BOROSIL.AD": "تصنيع",
    "BILDCO.AD": "تصنيع", "ENERGY.AD": "طاقة", "GHURAIR.AD": "مالي",
}

# دمج التصنيفات
TICKER_SECTOR = {**EGYPT_SECTOR, **US_SECTOR, **UAE_SECTOR}

# نرتب حسب رمز السهم
ALL_STOCKS = dict(sorted(ALL_STOCKS.items(), key=lambda kv: kv[1]))

# ============================================================
# دوال التحليل الأساسية
# ============================================================

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
    empty = {
        "pe_ratio": None, "pb_ratio": None, "roe_%": None,
        "profit_margin_%": None, "debt_to_equity": None,
        "dividend_yield_%": None, "revenue_growth_%": None,
        "eps": None, "book_value_per_share": None,
    }
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        return empty

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

def score_fundamentals(f: dict) -> int:
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

# دوال تحميل البيانات
@st.cache_data(ttl=300, show_spinner=False)
def fetch_single_stock(ticker: str, period: str = "100d"):
    return yf.download(ticker, period=period, progress=False, group_by='ticker')

@st.cache_data(ttl=300, show_spinner=False)
def fetch_batch_data(tickers_tuple: tuple, period: str = "60d"):
    tickers = list(tickers_tuple)
    all_frames = {}
    failed = []

    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        try:
            data = yf.download(batch, period=period, progress=False, group_by='ticker', threads=True)
        except Exception:
            failed.extend(batch)
            continue

        for t in batch:
            try:
                df_t = data[t] if len(batch) > 1 else data
                if df_t is not None and not df_t.dropna(how='all').empty:
                    all_frames[t] = df_t
                else:
                    failed.append(t)
            except Exception:
                failed.append(t)

        if i + BATCH_SIZE < len(tickers):
            time.sleep(BATCH_DELAY)

    still_failed = []
    if failed:
        for t in failed:
            try:
                df_t = yf.download(t, period=period, progress=False, group_by='ticker')
                if df_t is not None and not df_t.dropna(how='all').empty:
                    all_frames[t] = df_t
                else:
                    still_failed.append(t)
            except Exception:
                still_failed.append(t)
            time.sleep(0.3)
        failed = still_failed

    return all_frames, failed

# ============================================================
# الواجهة الرئيسية
# ============================================================

tab1, tab2 = st.tabs(["🔍 فحص سهم تفصيلي + رسم بياني", "🏆 مسح وترتيب السوق الاحترافي"])

with tab1:
    st.subheader("اختر سهمك المفضل لتحليله ورسم بياناته بالتفصيل")
    
    market_option = st.radio(
        "اختر السوق:",
        ["🇪🇬 البورصة المصرية (EGX)", "🇺🇸 البورصة الأمريكية (US)", "🇦🇪 البورصة الإماراتية (UAE)"],
        horizontal=True
    )
    
    if market_option == "🇪🇬 البورصة المصرية (EGX)":
        stock_list = EGX_STOCKS
    elif market_option == "🇺🇸 البورصة الأمريكية (US)":
        stock_list = US_STOCKS
    else:
        stock_list = UAE_STOCKS
    
    col_input1, col_input2 = st.columns([2, 1])
    with col_input1:
        selected_stock = st.selectbox("اختر من قائمة السوق:", list(stock_list.keys()))
        ticker_input = stock_list[selected_stock]
    with col_input2:
        manual_ticker = st.text_input("أو اكتب رمزاً مخصصاً يدوياً:", value="").strip().upper()
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
                    
                    price = float(last_row['Close'].squeeze())
                    ema9 = float(last_row['EMA9'].squeeze())
                    ema21 = float(last_row['EMA21'].squeeze())
                    rsi = float(last_row['RSI_14'].squeeze())
                    mfi = float(last_row['MFI_14'].squeeze())
                    upper = float(last_row['Upper_Band'].squeeze())
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
                    currency = "ج.م" if ticker_input.endswith(".CA") else "$"
                    c1.metric("السعر الحالي", f"{price:.2f} {currency}")
                    c2.metric("مؤشر الزخم RSI", f"{rsi:.1f}")
                    c3.metric("مؤشر السيولة MFI", f"{mfi:.1f}")
                    c4.metric("حجم تداول اليوم (فوليوم)", f"{vol:,.0f}")

                    # التحليل المالي
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

                    # قاعدة جراهام
                    graham = graham_from_fundamentals(fundamentals, price)
                    st.markdown("##### 📐 قاعدة جراهام (المستثمر الدفاعي)")
                    g1, g2, g3 = st.columns(3)
                    graham_display = f"{graham['graham_number']:.2f}" if graham["graham_number"] else "غير متاح"
                    upside_display = f"{graham['graham_upside_%']:+.1f}%" if graham["graham_upside_%"] is not None else "—"
                    verdict_display = (
                        "✅ تحت السعر العادل" if graham["undervalued_per_graham"] is True
                        else "❌ فوق السعر العادل" if graham["undervalued_per_graham"] is False
                        else "غير متاح"
                    )
                    g1.metric("رقم جراهام (السعر العادل)", graham_display)
                    g2.metric("الفرق عن السعر الحالي", upside_display)
                    g3.metric("الحكم", verdict_display)

                    # الرسم البياني
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

    scan_market = st.radio(
        "اختر السوق للمسح:",
        ["🇪🇬 البورصة المصرية (EGX)", "🇺🇸 البورصة الأمريكية (US)", "🇦🇪 البورصة الإماراتية (UAE)", "🌍 جميع الأسواق"],
        horizontal=True
    )

    include_fundamentals_scan = st.checkbox(
        "💰 تضمين التحليل المالي الأساسي + رقم جراهام",
        value=False,
    )

    fcol1, fcol2 = st.columns(2)
    with fcol1:
        available_sectors = sorted(set(TICKER_SECTOR.values()))
        selected_sectors_scan = st.multiselect(
            "🏢 فلتر القطاع",
            options=available_sectors,
            default=[],
        )
    with fcol2:
        min_liquidity_scan = st.checkbox(
            "💧 متوسط قيمة التداول اليومي فوق 3 مليون فقط",
            value=False,
        )

    if st.button("تشغيل الفرز والترتيب الاحترافي اللحظي 🚀"):
        fresh_cross_results = []
        bottom_accumulation_results = []
        short_term_trading = []
        long_term_investment = []
        
        progress_bar = st.progress(0)
        
        if scan_market == "🇪🇬 البورصة المصرية (EGX)":
            stocks_to_scan = EGX_STOCKS
        elif scan_market == "🇺🇸 البورصة الأمريكية (US)":
            stocks_to_scan = US_STOCKS
        elif scan_market == "🇦🇪 البورصة الإماراتية (UAE)":
            stocks_to_scan = UAE_STOCKS
        else:
            stocks_to_scan = {**EGX_STOCKS, **US_STOCKS, **UAE_STOCKS}
        
        total_stocks = len(stocks_to_scan)
        
        with st.spinner(f"جاري مسح {total_stocks} سهم على دفعات..."):
            tickers_list = list(stocks_to_scan.values())
            all_data, failed_tickers = fetch_batch_data(tuple(tickers_list), period="60d")

            if failed_tickers:
                st.warning(
                    f"⚠️ تعذر تحميل بيانات {len(failed_tickers)} سهم من أصل {len(tickers_list)}. "
                    "التفاصيل الكاملة هتلاقيها في آخر الصفحة."
                )

            skipped_count = 0
            skipped_names = []
            for idx, (name, ticker) in enumerate(stocks_to_scan.items()):
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

                    avg_trade_value = p * vol_ma10
                    if min_liquidity_scan and avg_trade_value < 3_000_000:
                        continue

                    sector = TICKER_SECTOR.get(ticker, "غير مصنف")
                    if selected_sectors_scan and sector not in selected_sectors_scan:
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
                    
                    data_entry = {
                        "النقاط الفنية والسيولة": round(momentum_score, 1),
                        "اسم الشركة": name,
                        "الرمز البرمجي": ticker,
                        "القطاع": sector,
                        "السعر الحالي": round(p, 2),
                        "RSI": round(r, 1),
                        "MFI": round(m, 1),
                        "فوليوم اليوم": f"{vol_today:,.0f}",
                        "متوسط فوليوم": f"{vol_ma10:,.0f}",
                        "التقييم الفني": status
                    }

                    if include_fundamentals_scan:
                        fundamentals = fetch_fundamentals(ticker)
                        fund_score = score_fundamentals(fundamentals)
                        combined_score = round(0.6 * momentum_score + 0.4 * fund_score, 1)
                        data_entry["الدرجة المالية"] = fund_score
                        data_entry["P/E"] = round(fundamentals["pe_ratio"], 2) if fundamentals.get("pe_ratio") else None
                        data_entry["الدرجة الشاملة"] = combined_score

                        graham = graham_from_fundamentals(fundamentals, p)
                        data_entry["رقم جراهام"] = graham["graham_number"]
                        data_entry["فرق جراهام %"] = graham["graham_upside_%"]
                        data_entry["تحت العادل؟"] = graham["undervalued_per_graham"]
                    
                    if is_new_cross and r < 52:
                        data_entry["التقييم الفني"] = "✨ تأسيس مركز (قاع صاعد)"
                        fresh_cross_results.append(data_entry)
                    
                    elif r < 35 and m < 35:
                        data_entry["التقييم الفني"] = "🛒 قاع تجميع"
                        bottom_accumulation_results.append(data_entry)
                    
                    elif e9 > e21:
                        if vol_today > (vol_ma10 * 1.15) and 50 <= r <= 78:
                            data_entry["التقييم الفني"] = f"{status} [مضاربة]"
                            short_term_trading.append(data_entry)
                        else:
                            data_entry["التقييم الفني"] = f"{status} [استثمار]"
                            long_term_investment.append(data_entry)
                except Exception as e:
                    skipped_count += 1
                    skipped_names.append((name, ticker, f"خطأ: {e}"))
                    continue
            
            if skipped_count:
                st.info(f"ℹ️ تم تخطي {skipped_count} سهم.")
                with st.expander(f"📋 تفاصيل الأسهم المتخطاة"):
                    for name, ticker, reason in skipped_names:
                        st.write(f"- **{name}** ({ticker}) — {reason}")

            st.success("✅ تم التحديث النهائي والإغلاق الهندسي للرادار بنجاح! 🦅")
            
            # إرسال التقرير
            telegram_msg = f"🦅 *تقرير قناص البورصة العالمية* 🌍\n"
            telegram_msg += f"📊 *السوق:* {scan_market}\n\n"
            
            if fresh_cross_results:
                telegram_msg += "🌟 *تأسيس مركز (قاع صاعد):*\n"
                for item in fresh_cross_results[:5]:
                    telegram_msg += f"- {item['اسم الشركة']} ({item['السعر الحالي']})\n"
                telegram_msg += "\n"
                
            if long_term_investment:
                _lt_df = pd.DataFrame(long_term_investment)
                _sort_col = "الدرجة الشاملة" if "الدرجة الشاملة" in _lt_df.columns else "النقاط الفنية والسيولة"
                top_inv = _lt_df.sort_values(by=_sort_col, ascending=False).head(5)
                telegram_msg += "📈 *أقوى أسهم الاستثمار:*\n"
                for _, row_inv in top_inv.iterrows():
                    telegram_msg += f"- {row_inv['اسم الشركة']} | {row_inv['السعر الحالي']} | {row_inv['النقاط الفنية والسيولة']}\n"
                telegram_msg += "\n"
                
            if short_term_trading:
                top_trade = pd.DataFrame(short_term_trading).sort_values(by="النقاط الفنية والسيولة", ascending=False).head(5)
                telegram_msg += "⚡ *أقوى أسهم المضاربة:*\n"
                for _, row_tr in top_trade.iterrows():
                    telegram_msg += f"- {row_tr['اسم الشركة']} | {row_tr['السعر الحالي']}\n"
            
            tg_success, tg_status_msg = send_telegram_alert(telegram_msg)
            if TELEGRAM_TOKEN or default_token or TELEGRAM_CHAT_ID or default_chat_id:
                if tg_success:
                    st.sidebar.success(tg_status_msg)
                else:
                    st.sidebar.error(tg_status_msg)
            
            # عرض الجداول
            st.markdown("### 🚀 تأسيس مركز جديد")
            if fresh_cross_results:
                st.dataframe(pd.DataFrame(fresh_cross_results).sort_values(by="النقاط الفنية والسيولة", ascending=False), use_container_width=True)
            else:
                st.info("لا توجد أسهم لقطت تقاطع ذهبي اليوم.")
                
            st.write("---")
            
            st.markdown("### 📥 رادار القيعان")
            if bottom_accumulation_results:
                st.dataframe(pd.DataFrame(bottom_accumulation_results).sort_values(by="RSI", ascending=True), use_container_width=True)
            else:
                st.info("لا توجد أسهم في قيعان التشبع البيعي.")
                
            st.write("---")
            
            st.markdown("### ⚡ أسهم المضاربة")
            if short_term_trading:
                st.dataframe(pd.DataFrame(short_term_trading).sort_values(by="فوليوم اليوم", ascending=False), use_container_width=True)
            else:
                st.info("لا توجد أسهم مستوفية لشروط المضاربة.")

            st.write("---")
            
            st.markdown("### 📈 أسهم الاستثمار المستقر")
            if long_term_investment:
                lt_df = pd.DataFrame(long_term_investment)
                sort_col = "الدرجة الشاملة" if "الدرجة الشاملة" in lt_df.columns else "النقاط الفنية والسيولة"
                st.dataframe(lt_df.sort_values(by=sort_col, ascending=False), use_container_width=True)
