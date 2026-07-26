import time
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np
import json

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="قناص الأسواق العالمية 💹", layout="wide")

st.title("🦅 قناص الأسواق العالمية (S&P 500 + البورصة المصرية + العملات المشفرة)")
st.write("تحليل فني ومالي متكامل لأكثر من 500 سهم أمريكي + 230 سهم مصري + عملات مشفرة")

# إعدادات عامة
BATCH_SIZE = 30
BATCH_DELAY = 1.5
CROSS_LOOKBACK = 3

# إعدادات التليجرام
try:
    default_token = st.secrets.get("TELEGRAM_TOKEN", "")
    default_chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
except Exception:
    default_token = ""
    default_chat_id = ""

st.sidebar.header("⚙️ إعدادات إشعارات الموبايل (تليجرام)")
TELEGRAM_TOKEN = st.sidebar.text_input("أدخل Token البوت:", value=default_token, type="password")
TELEGRAM_CHAT_ID = st.sidebar.text_input("أدخل Chat ID الخاص بك:", value=default_chat_id)

def send_telegram_alert(message):
    token = TELEGRAM_TOKEN if TELEGRAM_TOKEN else default_token
    chat_id = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else default_chat_id

    if not (token and chat_id):
        return False, "لم يتم إدخال Token أو Chat ID"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200 and resp.json().get("ok"):
            return True, "✅ تم الإرسال بنجاح"
        return False, f"❌ فشل الإرسال (كود {resp.status_code})"
    except Exception as e:
        return False, f"❌ خطأ: {e}"

# ============================================================
# جلب قائمة S&P 500 - طرق متعددة (بدون lxml)
# ============================================================

@st.cache_data(ttl=86400)
def get_sp500_tickers():
    """
    جلب قائمة S&P 500 باستخدام طرق متعددة
    """
    
    # المحاولة 1: استخدام JSON من مصدر موثوق
    try:
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
        df = pd.read_csv(url)
        if not df.empty:
            tickers = df['Symbol'].tolist()
            names = df['Name'].tolist()
            
            # تنظيف الرموز
            tickers = [t.replace('.', '-') for t in tickers]
            
            sp500_dict = {}
            for name, ticker in zip(names, tickers):
                if len(name) > 35:
                    name = name[:32] + "..."
                sp500_dict[f"{name} ({ticker})"] = ticker
            
            return sp500_dict
    except Exception as e:
        st.warning(f"المحاولة 1 فشلت: {e}")
    
    # المحاولة 2: استخدام Wikipedia مع BeautifulSoup (بدون lxml)
    try:
        import html5lib
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url, flavor='html5lib')
        sp500_table = tables[0]
        tickers = sp500_table['Symbol'].tolist()
        names = sp500_table['Security'].tolist()
        
        tickers = [t.replace('.', '-') for t in tickers]
        
        sp500_dict = {}
        for name, ticker in zip(names, tickers):
            if len(name) > 35:
                name = name[:32] + "..."
            sp500_dict[f"{name} ({ticker})"] = ticker
        
        return sp500_dict
    except Exception as e:
        st.warning(f"المحاولة 2 فشلت: {e}")
    
    # المحاولة 3: قائمة يدوية موسعة (احتياطية)
    st.warning("جاري استخدام القائمة الاحتياطية للأسهم الأمريكية...")
    return get_fallback_us_stocks()

def get_fallback_us_stocks():
    """
    قائمة احتياطية للأسهم الأمريكية في حال فشل الجلب
    """
    # أهم 100 سهم أمريكي (قائمة موسعة)
    fallback = {
        "Apple Inc. (AAPL)": "AAPL",
        "Microsoft (MSFT)": "MSFT",
        "Amazon (AMZN)": "AMZN",
        "Google (GOOGL)": "GOOGL",
        "Meta (META)": "META",
        "Tesla (TSLA)": "TSLA",
        "NVIDIA (NVDA)": "NVDA",
        "Berkshire (BRK-B)": "BRK-B",
        "Johnson & Johnson (JNJ)": "JNJ",
        "Visa (V)": "V",
        "Procter & Gamble (PG)": "PG",
        "JPMorgan Chase (JPM)": "JPM",
        "UnitedHealth (UNH)": "UNH",
        "Home Depot (HD)": "HD",
        "Walmart (WMT)": "WMT",
        "Mastercard (MA)": "MA",
        "Coca-Cola (KO)": "KO",
        "PepsiCo (PEP)": "PEP",
        "Cisco (CSCO)": "CSCO",
        "Intel (INTC)": "INTC",
        "IBM (IBM)": "IBM",
        "Netflix (NFLX)": "NFLX",
        "PayPal (PYPL)": "PYPL",
        "Adobe (ADBE)": "ADBE",
        "Salesforce (CRM)": "CRM",
        "Oracle (ORCL)": "ORCL",
        "Caterpillar (CAT)": "CAT",
        "Boeing (BA)": "BA",
        "McDonald's (MCD)": "MCD",
        "Disney (DIS)": "DIS",
        "Nike (NKE)": "NKE",
        "Starbucks (SBUX)": "SBUX",
        "Costco (COST)": "COST",
        "Chevron (CVX)": "CVX",
        "Exxon Mobil (XOM)": "XOM",
        "Philip Morris (PM)": "PM",
        "Altria (MO)": "MO",
        "Abbott Labs (ABT)": "ABT",
        "AbbVie (ABBV)": "ABBV",
        "Eli Lilly (LLY)": "LLY",
        "Pfizer (PFE)": "PFE",
        "Merck (MRK)": "MRK",
        "Amgen (AMGN)": "AMGN",
        "Gilead (GILD)": "GILD",
        "Moderna (MRNA)": "MRNA",
        "Broadcom (AVGO)": "AVGO",
        "Texas Instruments (TXN)": "TXN",
        "Qualcomm (QCOM)": "QCOM",
        "AMD (AMD)": "AMD",
        "Micron (MU)": "MU",
        "ASML (ASML)": "ASML",
        "Taiwan Semi (TSM)": "TSM",
        "SAP (SAP)": "SAP",
        "Accenture (ACN)": "ACN",
        "Dell (DELL)": "DELL",
        "HP (HPQ)": "HPQ",
        "Uber (UBER)": "UBER",
        "Airbnb (ABNB)": "ABNB",
        "Booking (BKNG)": "BKNG",
        "American Express (AXP)": "AXP",
        "Goldman Sachs (GS)": "GS",
        "Morgan Stanley (MS)": "MS",
        "Bank of America (BAC)": "BAC",
        "Wells Fargo (WFC)": "WFC",
        "Citigroup (C)": "C",
        "BlackRock (BLK)": "BLK",
        "S&P Global (SPGI)": "SPGI",
        "Moody's (MCO)": "MCO",
        "MSCI (MSCI)": "MSCI",
        "Fiserv (FISV)": "FISV",
        "Fidelity (FIS)": "FIS",
        "Charles Schwab (SCHW)": "SCHW",
        "T-Mobile (TMUS)": "TMUS",
        "Verizon (VZ)": "VZ",
        "AT&T (T)": "T",
        "Comcast (CMCSA)": "CMCSA",
        "Charter (CHTR)": "CHTR",
        "Linde (LIN)": "LIN",
        "Air Products (APD)": "APD",
        "Ecolab (ECL)": "ECL",
        "3M (MMM)": "MMM",
        "Honeywell (HON)": "HON",
        "GE (GE)": "GE",
        "United Rentals (URI)": "URI",
        "Autozone (AZO)": "AZO",
        "O'Reilly (ORLY)": "ORLY",
        "TJX (TJX)": "TJX",
        "Lowe's (LOW)": "LOW",
        "Target (TGT)": "TGT",
        "Dollar General (DG)": "DG",
        "Dollar Tree (DLTR)": "DLTR",
        "Ross Stores (ROST)": "ROST",
        "Sherwin-Williams (SHW)": "SHW",
        "Deere (DE)": "DE",
        "Cummins (CMI)": "CMI",
        "Parker-Hannifin (PH)": "PH",
        "Emerson (EMR)": "EMR",
        "Rockwell (ROK)": "ROK",
        "Illinois Tool (ITW)": "ITW",
        "Fortive (FTV)": "FTV",
        "Dover (DOV)": "DOV",
        "Snap-on (SNA)": "SNA",
        "Stanley Black (SWK)": "SWK",
        "Textron (TXT)": "TXT",
        "Lockheed Martin (LMT)": "LMT",
        "Northrop (NOC)": "NOC",
        "Raytheon (RTX)": "RTX",
        "General Dynamics (GD)": "GD",
        "L3Harris (LHX)": "LHX",
        "Huntington Ingalls (HII)": "HII",
        "Booz Allen (BAH)": "BAH",
        "Leidos (LDOS)": "LDOS",
        "Cintas (CTAS)": "CTAS",
        "Aon (AON)": "AON",
        "Marsh (MMC)": "MMC",
        "Willis Towers (WTW)": "WTW",
        "AFLAC (AFL)": "AFL",
        "Prudential (PRU)": "PRU",
        "MetLife (MET)": "MET",
        "Allstate (ALL)": "ALL",
        "Travelers (TRV)": "TRV",
        "Chubb (CB)": "CB",
        "Progressive (PGR)": "PGR",
        "M&T Bank (MTB)": "MTB",
        "PNC (PNC)": "PNC",
        "Truist (TFC)": "TFC",
        "US Bancorp (USB)": "USB",
        "KeyCorp (KEY)": "KEY",
        "Fifth Third (FITB)": "FITB",
        "Citizens (CFG)": "CFG",
        "Regions (RF)": "RF",
        "State Street (STT)": "STT",
        "Northern Trust (NTRS)": "NTRS",
        "Bank of NY Mellon (BK)": "BK",
        "Ameriprise (AMP)": "AMP",
        "Raymond James (RJF)": "RJF",
        "LPL Financial (LPLA)": "LPLA",
        "Cboe (CBOE)": "CBOE",
        "CME (CME)": "CME",
        "Intercontinental (ICE)": "ICE",
        "Nasdaq (NDAQ)": "NDAQ",
        "Garmin (GRMN)": "GRMN",
        "Corning (GLW)": "GLW",
        "Amphenol (APH)": "APH",
        "TE Connectivity (TEL)": "TEL",
        "Jabil (JBL)": "JBL",
        "Flex (FLEX)": "FLEX",
        "Celestica (CLS)": "CLS",
        "Sanmina (SANM)": "SANM",
        "Keysight (KEYS)": "KEYS",
        "Teledyne (TDY)": "TDY",
        "Molex (MOLX)": "MOLX",
        "Arrow (ARW)": "ARW",
        "Avnet (AVT)": "AVT",
        "CDW (CDW)": "CDW",
        "Genpact (G)": "G",
        "Cognizant (CTSH)": "CTSH",
        "DXC (DXC)": "DXC",
        "EPAM (EPAM)": "EPAM",
        "Globant (GLOB)": "GLOB",
    }
    return fallback

# ============================================================
# الأسهم المصرية
# ============================================================
EGX_STOCKS = {
    "البنك التجاري الدولي": "COMI.CA",
    "مجموعة طلعت مصطفى": "TMGH.CA",
    "السويدي إليكتريك": "SWDY.CA",
    "المصرية للاتصالات": "ETEL.CA",
    "مصر للألومنيوم": "EGAL.CA",
    "مصر لإنتاج الأسمدة": "MFPC.CA",
    "الشرقية - إيسترن": "EAST.CA",
    "أبو قير للأسمدة": "ABUK.CA",
    "أوراسكوم للاستثمار": "OIH.CA",
    "أوراسكوم للتنمية": "ORHD.CA",
    "إي فاينانس": "EFIH.CA",
    "إيديتا": "EFID.CA",
    "جهينة": "JUFO.CA",
    "فاركو": "PHAR.CA",
    "فوري": "FWRY.CA",
    "مجموعة هيرميس": "HRHO.CA",
    "حديد عز": "ESRS.CA",
    "بالم هيلز": "PHDC.CA",
    "مدينة مصر": "MASR.CA",
    "مصر الجديدة": "HELI.CA",
    "بنك التعمير والإسكان": "HDBK.CA",
    "بنك البركة": "SAUD.CA",
    "بنك قناة السويس": "CANA.CA",
    "مصرف أبوظبي الإسلامي": "ADIB.CA",
    "القلعة": "CCAP.CA",
    "بلتون": "BTFH.CA",
    "راكتا": "RAKT.CA",
    "دومتي": "DOMT.CA",
    "غاز مصر": "EGAS.CA",
    "سيدي كرير": "SKPC.CA",
    "كيما": "EGCH.CA",
    "العز الدخيلة": "IRAX.CA",
    "النيل للأدوية": "NIPH.CA",
    "ابن سينا": "ISPH.CA",
    "إعمار مصر": "EMFD.CA",
    "أبو قير": "ABUK.CA",
    "أكرو مصر": "ACRO.CA",
    "أودن": "ODIN.CA",
    "الأسكندرية لتداول الحاويات": "ALCN.CA",
    "الاسكندرية لأسمنت": "ALEX.CA",
    "التعمير والاستشارات": "DAPH.CA",
    "الجوهرة": "ECAP.CA",
    "الجيزة للمقاولات": "GGCC.CA",
    "الزيوت المستخلصة": "ZEOT.CA",
    "الشمس للإسكان": "ELSH.CA",
    "الصعيد للمقاولات": "UEGC.CA",
    "العبوات الطبية": "MEPA.CA",
    "العربية للأدوية": "ADCI.CA",
    "القاهرة للإسكان": "ELKA.CA",
    "القاهرة للدواجن": "POUL.CA",
    "المطورون العرب": "ARAB.CA",
    "المنصورة للدواجن": "MPCO.CA",
    "بنك فيصل الإسلامي": "FAIT.CA",
    "جي بي كورب": "GBCO.CA",
    "شمال أفريقيا": "NATI.CA",
    "صناع التغليف": "UNIP.CA",
    "طاقة عربية": "TAQA.CA",
    "عبر المحيطات": "GOCE.CA",
    "مطاحن مصر الوسطى": "CEFM.CA",
    "مطاحن شمال القاهرة": "MNSF.CA",
}

# ============================================================
# العملات المشفرة
# ============================================================
CRYPTO_STOCKS = {
    "Bitcoin (BTC)": "BTC-USD",
    "Ethereum (ETH)": "ETH-USD",
    "Solana (SOL)": "SOL-USD",
    "Ripple (XRP)": "XRP-USD",
    "Cardano (ADA)": "ADA-USD",
    "Dogecoin (DOGE)": "DOGE-USD",
    "BNB": "BNB-USD",
    "Chainlink (LINK)": "LINK-USD",
    "Polkadot (DOT)": "DOT-USD",
    "Polygon (MATIC)": "MATIC-USD",
    "Litecoin (LTC)": "LTC-USD",
    "Avalanche (AVAX)": "AVAX-USD",
    "Uniswap (UNI)": "UNI-USD",
    "Cosmos (ATOM)": "ATOM-USD",
    "Ethereum Classic (ETC)": "ETC-USD",
}

# ============================================================
# تحميل قائمة S&P 500
# ============================================================
with st.spinner("جاري تحميل قائمة S&P 500..."):
    SP500_STOCKS = get_sp500_tickers()

# ============================================================
# دمج جميع الأسواق
# ============================================================

ALL_STOCKS = {}
ALL_STOCKS.update(EGX_STOCKS)
ALL_STOCKS.update({f"{k} (US)": v for k, v in SP500_STOCKS.items()})
ALL_STOCKS.update({f"{k} (Crypto)": v for k, v in CRYPTO_STOCKS.items()})

# تصنيف القطاعات
TICKER_SECTOR = {}

# القطاعات المصرية
egypt_sectors = {
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
TICKER_SECTOR.update(egypt_sectors)

# العملات المشفرة
for ticker in CRYPTO_STOCKS.values():
    TICKER_SECTOR[ticker] = "عملات مشفرة"

# الأسهم الأمريكية - سنضيف قطاعاتها عند المسح
# نضع قطاع افتراضي مؤقت
for ticker in SP500_STOCKS.values():
    TICKER_SECTOR[ticker] = "أمريكي"

# ترتيب القائمة
ALL_STOCKS = dict(sorted(ALL_STOCKS.items(), key=lambda kv: kv[1]))

# ============================================================
# دوال التحليل (نفس الكود السابق)
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
        "sector": None,
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
        "sector": info.get("sector"),
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

st.sidebar.markdown(f"### 📊 إحصائيات السوق")
st.sidebar.metric("🇺🇸 أسهم S&P 500", f"{len(SP500_STOCKS)} سهم")
st.sidebar.metric("🇪🇬 أسهم مصرية", f"{len(EGX_STOCKS)} سهم")
st.sidebar.metric("₿ عملات مشفرة", f"{len(CRYPTO_STOCKS)} عملة")
st.sidebar.metric("📈 إجمالي", f"{len(ALL_STOCKS)} أصل")

tab1, tab2 = st.tabs(["🔍 فحص سهم/عملة تفصيلي", "🏆 مسح وترتيب السوق"])

with tab1:
    st.subheader("اختر الأصل المالي لتحليله")
    
    market_option = st.radio(
        "اختر السوق:",
        ["🇪🇬 البورصة المصرية", "🇺🇸 S&P 500", "₿ العملات المشفرة"],
        horizontal=True
    )
    
    if market_option == "🇪🇬 البورصة المصرية":
        stock_list = EGX_STOCKS
        currency = "ج.م"
    elif market_option == "🇺🇸 S&P 500":
        stock_list = SP500_STOCKS
        currency = "$"
    else:
        stock_list = CRYPTO_STOCKS
        currency = "$"
    
    col_input1, col_input2 = st.columns([2, 1])
    with col_input1:
        selected_stock = st.selectbox("اختر من القائمة:", list(stock_list.keys()))
        ticker_input = stock_list[selected_stock]
    with col_input2:
        manual_ticker = st.text_input("أو اكتب رمزاً مخصصاً:", value="").strip().upper()
        if manual_ticker:
            ticker_input = manual_ticker

    if st.button("تحليل ورسم المنحنى ⚡"):
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
                        decision = "🚀 تأسيس مركز"
                        color = "#1abc9c"
                    elif rsi < 35 and mfi < 35:
                        decision = "🛒 تجميع في القاع"
                        color = "#3498db"
                    elif ema9 > ema21 and rsi < 70 and mfi < 80:
                        decision = "⚡ STRONG BUY"
                        color = "#2ecc71"
                    elif price >= upper or rsi >= 75 or mfi >= 85:
                        decision = "🔴 SELL"
                        color = "#e74c3c"
                    else:
                        decision = "✋ HOLD"
                        color = "#f39c12"
                    
                    st.markdown(f'<div style="background-color:{color}; padding:20px; border-radius:10px; text-align:center; margin-bottom:20px;"><h2 style="color:white; margin:0;">{decision}</h2></div>', unsafe_allow_html=True)
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("السعر", f"{price:.2f} {currency}")
                    c2.metric("RSI", f"{rsi:.1f}")
                    c3.metric("MFI", f"{mfi:.1f}")
                    c4.metric("الحجم", f"{vol:,.0f}")

                    if ticker_input not in CRYPTO_STOCKS.values():
                        fundamentals = fetch_fundamentals(ticker_input)
                        fund_score = score_fundamentals(fundamentals)

                        st.markdown("##### 💰 التحليل المالي")
                        f1, f2, f3, f4 = st.columns(4)
                        f1.metric("P/E", f"{fundamentals['pe_ratio']:.2f}" if fundamentals.get("pe_ratio") else "غير متاح")
                        f2.metric("ROE", f"{fundamentals['roe_%']:.1f}%" if fundamentals.get("roe_%") is not None else "غير متاح")
                        f3.metric("هامش الربح", f"{fundamentals['profit_margin_%']:.1f}%" if fundamentals.get("profit_margin_%") is not None else "غير متاح")
                        f4.metric("القطاع", fundamentals.get("sector", "غير متاح"))

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].squeeze(), name='السعر', line=dict(color='#1f77b4', width=2)))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'].squeeze(), name='EMA 9', line=dict(color='#2ca02c', dash='dot')))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'].squeeze(), name='EMA 21', line=dict(color='#d62728', dash='dash')))
                    fig.update_layout(template="plotly_dark", height=450)
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"حدث خطأ: {e}")

with tab2:
    st.subheader("📊 مسح وترتيب الأسواق")
    
    st.warning(f"⚠️ سيتم مسح {len(ALL_STOCKS)} أصل مالي. قد يستغرق الأمر عدة دقائق.")

    scan_market = st.radio(
        "اختر السوق للمسح:",
        ["🇪🇬 البورصة المصرية", "🇺🇸 S&P 500", "₿ العملات المشفرة", "🌍 جميع الأسواق"],
        horizontal=True
    )

    include_fundamentals_scan = st.checkbox(
        "💰 تضمين التحليل المالي (للأسهم فقط)",
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
            "💧 متوسط التداول فوق 3 مليون",
            value=False,
        )

    if st.button("تشغيل المسح 🚀"):
        fresh_cross_results = []
        bottom_accumulation_results = []
        short_term_trading = []
        long_term_investment = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        if scan_market == "🇪🇬 البورصة المصرية":
            stocks_to_scan = EGX_STOCKS
        elif scan_market == "🇺🇸 S&P 500":
            stocks_to_scan = SP500_STOCKS
        elif scan_market == "₿ العملات المشفرة":
            stocks_to_scan = CRYPTO_STOCKS
        else:
            stocks_to_scan = {**EGX_STOCKS, **SP500_STOCKS, **CRYPTO_STOCKS}
        
        total_stocks = len(stocks_to_scan)
        
        with st.spinner(f"جاري مسح {total_stocks} أصل..."):
            tickers_list = list(stocks_to_scan.values())
            all_data, failed_tickers = fetch_batch_data(tuple(tickers_list), period="60d")

            if failed_tickers:
                st.warning(f"⚠️ تعذر تحميل {len(failed_tickers)} أصل")

            skipped_count = 0
            skipped_names = []
            
            for idx, (name, ticker) in enumerate(stocks_to_scan.items()):
                progress = (idx + 1) / total_stocks
                progress_bar.progress(progress)
                status_text.text(f"{idx+1}/{total_stocks}: {name}")
                
                if ticker not in all_data:
                    skipped_count += 1
                    skipped_names.append((name, ticker, "لم يتم التحميل"))
                    continue
                    
                try:
                    stock_df = all_data[ticker].dropna(how='all')
                    if stock_df.empty or len(stock_df) < 25:
                        skipped_count += 1
                        skipped_names.append((name, ticker, "بيانات غير كافية"))
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
                    
                    if ticker in CRYPTO_STOCKS.values():
                        if vol_today < 100000:
                            continue
                    else:
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
                        status = "🚨 تصريف"
                    elif momentum_score >= 70:
                        status = "⚡ STRONG BUY"
                    elif 50 <= momentum_score < 70:
                        status = "🟢 إيجابي"
                    else:
                        status = "🟡 HOLD"
                    
                    data_entry = {
                        "النقاط": round(momentum_score, 1),
                        "الاسم": name,
                        "الرمز": ticker,
                        "القطاع": sector,
                        "السعر": round(p, 2),
                        "RSI": round(r, 1),
                        "MFI": round(m, 1),
                        "الحجم": f"{vol_today:,.0f}",
                        "التقييم": status
                    }

                    if include_fundamentals_scan and ticker not in CRYPTO_STOCKS.values():
                        fundamentals = fetch_fundamentals(ticker)
                        fund_score = score_fundamentals(fundamentals)
                        combined_score = round(0.6 * momentum_score + 0.4 * fund_score, 1)
                        data_entry["مالي"] = fund_score
                        data_entry["P/E"] = round(fundamentals["pe_ratio"], 2) if fundamentals.get("pe_ratio") else None
                        data_entry["شامل"] = combined_score
                        
                        if fundamentals.get("sector"):
                            data_entry["القطاع"] = fundamentals.get("sector")
                    
                    if is_new_cross and r < 52:
                        data_entry["التقييم"] = "✨ تأسيس مركز"
                        fresh_cross_results.append(data_entry)
                    
                    elif r < 35 and m < 35:
                        data_entry["التقييم"] = "🛒 قاع تجميع"
                        bottom_accumulation_results.append(data_entry)
                    
                    elif e9 > e21:
                        if vol_today > (vol_ma10 * 1.15) and 50 <= r <= 78:
                            data_entry["التقييم"] = f"{status} [مضاربة]"
                            short_term_trading.append(data_entry)
                        else:
                            data_entry["التقييم"] = f"{status} [استثمار]"
                            long_term_investment.append(data_entry)
                            
                except Exception as e:
                    skipped_count += 1
                    skipped_names.append((name, ticker, f"خطأ: {e}"))
                    continue
            
            status_text.empty()
            progress_bar.empty()
            
            if skipped_count:
                st.info(f"ℹ️ تم تخطي {skipped_count} أصل")
                with st.expander("📋 تفاصيل المتخطاة (أول 50)"):
                    for name, ticker, reason in skipped_names[:50]:
                        st.write(f"- **{name}** ({ticker}) — {reason}")

            st.success(f"✅ تم مسح {total_stocks - skipped_count} أصل!")

            # عرض النتائج
            st.markdown("### 🚀 تأسيس مركز جديد")
            if fresh_cross_results:
                st.dataframe(pd.DataFrame(fresh_cross_results).sort_values(by="النقاط", ascending=False), use_container_width=True)
            else:
                st.info("لا توجد نتائج")
                
            st.write("---")
            
            st.markdown("### 📥 رادار القيعان")
            if bottom_accumulation_results:
                st.dataframe(pd.DataFrame(bottom_accumulation_results).sort_values(by="RSI", ascending=True), use_container_width=True)
            else:
                st.info("لا توجد نتائج")
                
            st.write("---")
            
            st.markdown("### ⚡ المضاربة اللحظية")
            if short_term_trading:
                st.dataframe(pd.DataFrame(short_term_trading).sort_values(by="الحجم", ascending=False), use_container_width=True)
            else:
                st.info("لا توجد نتائج")

            st.write("---")
            
            st.markdown("### 📈 الاستثمار المستقر")
            if long_term_investment:
                lt_df = pd.DataFrame(long_term_investment)
                sort_col = "شامل" if "شامل" in lt_df.columns else "النقاط"
                st.dataframe(lt_df.sort_values(by=sort_col, ascending=False), use_container_width=True)
