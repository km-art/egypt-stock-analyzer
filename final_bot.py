import time
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="قناص الأسواق العالمية 💹", layout="wide")

st.title("🦅 قناص الأسواق العالمية (S&P 500 + البورصة المصرية + العملات المشفرة)")
st.write("تحليل فني ومالي متكامل لأكثر من 500 سهم أمريكي + 230 سهم مصري + عملات مشفرة")

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

# إعدادات التنبيهات
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
# جلب قائمة S&P 500 تلقائياً من Wikipedia
# ============================================================
@st.cache_data(ttl=86400)  # تحديث مرة واحدة يومياً
def get_sp500_tickers():
    """
    جلب قائمة أسهم S&P 500 من Wikipedia
    """
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        sp500_table = tables[0]
        tickers = sp500_table['Symbol'].tolist()
        names = sp500_table['Security'].tolist()
        
        # تنظيف الرموز (بعضها يحتوي على نقاط)
        tickers = [t.replace('.', '-') for t in tickers]
        
        # إنشاء قاموس باسم الشركة + الرمز
        sp500_dict = {}
        for name, ticker in zip(names, tickers):
            # اختصار الأسماء الطويلة
            if len(name) > 30:
                name = name[:27] + "..."
            sp500_dict[f"{name} ({ticker})"] = ticker
        
        return sp500_dict
    except Exception as e:
        st.error(f"فشل جلب قائمة S&P 500: {e}")
        # قائمة احتياطية في حال فشل الجلب
        return {
            "Apple Inc. (AAPL)": "AAPL",
            "Microsoft (MSFT)": "MSFT",
            "Amazon (AMZN)": "AMZN",
            "Google (GOOGL)": "GOOGL",
            "Meta (META)": "META",
            "Tesla (TSLA)": "TSLA",
            "NVIDIA (NVDA)": "NVDA",
            "Berkshire (BRK-B)": "BRK-B",
        }

# ============================================================
# الأسهم المصرية (EGX) - القائمة الكاملة
# ============================================================
EGX_STOCKS = {
    "A Capital Holding": "ACAP.CA",
    "Act Financial": "ACTF.CA",
    "AJWA For Food Industries": "AJWA.CA",
    "Al Ahly for Development": "AFDI.CA",
    "Al Tawfeek Leasing": "ATLC.CA",
    "AlKhair River": "KRDI.CA",
    "Alexandria Co. For Pharmaceuticals": "AXPH.CA",
    "Alexandria Flour Mills": "AFMC.CA",
    "Alexandria New Medical Center": "AMES.CA",
    "Alexandria Spinning": "SPIN.CA",
    "Amer Group Holding": "AMER.CA",
    "Arab Aluminum": "ALUM.CA",
    "Arab Co. for Asset Management": "ACAMD.CA",
    "Arab Company For Land Reclamation": "EALR.CA",
    "Arab Engineering Industries": "EEII.CA",
    "Arab Moltaqa Investments": "AMIA.CA",
    "Arab Real Estate Investment": "RREI.CA",
    "Arab Valves Company": "ARVA.CA",
    "Arabia Cotton Ginning": "ACGC.CA",
    "Arabia Investments Holding": "AIHC.CA",
    "Arabia for Investment": "AIDC.CA",
    "Arabian Cement Company": "ARCC.CA",
    "Aspire Capital Holding": "ASPI.CA",
    "Atlas for Investment": "ALRA.CA",
    "B Investments Holding": "BINV.CA",
    "Bonyan for Development": "BONY.CA",
    "CI Capital Holding": "CICH.CA",
    "CIRA Education": "CIRA.CA",
    "Cairo Educational Services": "CAED.CA",
    "Cairo Oil & Soap": "COSG.CA",
    "Canal Shipping Agencies": "CSAG.CA",
    "Catalyst Partners": "CPME.CA",
    "Cleopatra Hospitals Group": "CLHO.CA",
    "Concrete Fashion Group": "CFGH.CA",
    "Contact Financial Holding": "CNFN.CA",
    "Copper for Commercial Investment": "COPR.CA",
    "Creast Mark For Contracting": "CRST.CA",
    "Credit Agricole Egypt Bank": "CIEB.CA",
    "Damietta Container & Cargo": "DCCC.CA",
    "Delta Co. For Printing": "DTPP.CA",
    "Delta Insurance": "DEIN.CA",
    "Delta Sugar": "SUGR.CA",
    "Dice For Ready-Made Garments": "DSCW.CA",
    "Digitize for Investment": "DGTZ.CA",
    "East Delta Flour Mills": "EDFM.CA",
    "Egypt Free Shops": "MFSC.CA",
    "Egypt for Poultry": "EPCO.CA",
    "Egyptian Arabian Company": "EASB.CA",
    "Egyptian Financial and Industrial": "EFIC.CA",
    "Egyptian Gulf Bank": "EGBE.CA",
    "Egyptian Iron and Steel": "IRON.CA",
    "Egyptian Media Production City": "MPRC.CA",
    "Egyptian Modern Education": "MOED.CA",
    "Egyptian Resorts Company": "EGTS.CA",
    "Egyptian Satellite Company": "EGSA.CA",
    "Egyptian Transport": "ETRS.CA",
    "Egyptians for Housing": "EHDR.CA",
    "El Ahram Co. For Printing": "EPPK.CA",
    "El Kahera El Watania Investment": "KWIN.CA",
    "El Nasr Manufacturing": "ELNA.CA",
    "El Orouba Securities": "EOSB.CA",
    "El Shams Pyramids Hotels": "SPHT.CA",
    "El Wadi for Investment": "ELWA.CA",
    "El-Ebour Co. for Real Estate": "OBRI.CA",
    "El-Nasr Clothing & Textiles": "KABO.CA",
    "Electro Cable Egypt": "ELEC.CA",
    "Export Development Bank": "EXPA.CA",
    "Faisal Islamic Bank (EGP)": "FAITA.CA",
    "Ferchem Misr": "FERC.CA",
    "GMC Group": "GMCI.CA",
    "GPI for Urban Growth": "GPIM.CA",
    "GTEX for Investments": "GTEX.CA",
    "Gadwa for Industrial Development": "GDWA.CA",
    "General Co. For Silos": "GSSC.CA",
    "General Company For Land Reclamation": "AALR.CA",
    "General Company for Ceramic": "PRCL.CA",
    "Gharbia Islamic Housing": "GIHD.CA",
    "GlaxoSmithKline Egypt": "BIOC.CA",
    "Go Green For Agricultural Investment": "GGRN.CA",
    "Golden Pyramids Plaza": "GPPL.CA",
    "Golden Textiles": "GTWL.CA",
    "Gourmet Egypt": "GOUR.CA",
    "Grand Capital": "GRCA.CA",
    "Gulf Canadian Company": "CCRS.CA",
    "Industrial Engineering ICON": "ENGC.CA",
    "International Co. For Investment": "ICID.CA",
    "International Company for Agricultural": "IFAP.CA",
    "International Company for Leasing": "ICLE.CA",
    "Iron & Steel for Mines": "ISMQ.CA",
    "Ismailia Development": "IDRE.CA",
    "Ismailia National Co.": "INFI.CA",
    "Kafr El Zayat For Pesticides": "KZPC.CA",
    "Kahira Pharmaceuticals": "CPCI.CA",
    "Lecico Egypt": "LCSW.CA",
    "Lotus Agri Capital": "LUTS.CA",
    "MINAPHARM Pharmaceuticals": "MIPH.CA",
    "MM Group for Industry": "MTIE.CA",
    "Macro Group Pharmaceuticals": "MCRO.CA",
    "Maridive and Oil Services": "MOIL.CA",
    "Marsa Alam For Tourism": "MMAT.CA",
    "Marseille Almasreia": "MAAL.CA",
    "Memphis Pharmaceuticals": "MPCI.CA",
    "Mena for Touristic": "MENA.CA",
    "Middle & West Delta Flour": "WCDF.CA",
    "Middle East Glass": "MEGM.CA",
    "Misr Beni Suef Cement": "MBSC.CA",
    "Misr Cement (Qena)": "MCQE.CA",
    "Misr Chemical Industries": "MICH.CA",
    "Misr Hotels Company": "MHOT.CA",
    "Misr National Steel": "ATQA.CA",
    "Misr Oils & Soap": "MOSC.CA",
    "Mohandes Insurance": "MOIN.CA",
    "Naeem Holding Company": "NAHO.CA",
    "Naeem Real Estate": "NARE.CA",
    "Nasr Company for Civil Works": "NCCW.CA",
    "National Company for Housing": "NHPS.CA",
    "National Drilling Company": "NDRL.CA",
    "National Printing Company": "NAPR.CA",
    "North Cairo Flour Mills": "MILS.CA",
    "Northern Upper Egypt": "NEDA.CA",
    "Nozha International Hospital": "NINH.CA",
    "O B Financial Holding": "OFH.CA",
    "Obour Land for Food": "OLFI.CA",
    "October Pharma": "OCPH.CA",
    "Orascom Construction": "ORAS.CA",
    "Oriental Weavers": "ORWE.CA",
    "Osool ESB Securities": "EBSC.CA",
    "Pioneers Properties": "PRDC.CA",
    "Port Said Containers": "POCO.CA",
    "Premium Healthcare": "PHGC.CA",
    "Prime Holding": "PRMH.CA",
    "Pyramisa Hotels": "PHTV.CA",
    "Qatar National Bank Al Ahli": "QNBE.CA",
    "Raya Customer Experience": "RACC.CA",
    "Raya Holding": "RAYA.CA",
    "Real Estate Egyptian Consortium": "AREH.CA",
    "Remco Tourism": "RTVC.CA",
    "Rowad Tourism": "ROTO.CA",
    "Rubex International": "RUBX.CA",
    "SHARM DREAMS Co.": "SDTI.CA",
    "Sabaa International": "SIPC.CA",
    "Samad Misr EGYFERT": "SMFR.CA",
    "Saudi Egyptian Investment": "SEIG.CA",
    "Saudi Egyptian Investment A": "SEIGA.CA",
    "Sharkia National Company": "SNFC.CA",
    "Sinai Cement": "SCEM.CA",
    "SODIC": "OCDI.CA",
    "Société Arabe Internationale": "SAIB.CA",
    "South Cairo and Giza Flour": "SCFM.CA",
    "South Valley Cement": "SVCE.CA",
    "Speed Medical": "SPMD.CA",
    "Suez Canal Technology": "SCTS.CA",
    "Taaleem Management": "TALM.CA",
    "Tanmiya For Real Estate": "TANM.CA",
    "Tenth of Ramadan (Rameda)": "RMDA.CA",
    "The Arab Ceramic": "CERA.CA",
    "The Arab Dairy": "ADPC.CA",
    "The United Bank": "UBEE.CA",
    "Trans Oceans Tours": "TRTO.CA",
    "Tycoon Holding": "ANFI.CA",
    "Unirab Polvara": "APSW.CA",
    "United Co. for Housing": "UNIT.CA",
    "Upper Egypt Mills": "UEFM.CA",
    "Valmore Holding (EGP)": "VLMRA.CA",
    "Valmore Holding (USD)": "VLMR.CA",
    "Valu Consumer Finance": "VALU.CA",
    "Wadi Kom Ombo": "WKOL.CA",
    "Zahraa El Maadi": "ZMID.CA",
    "أبو قير للأسمدة": "ABUK.CA",
    "أكرو مصر للشدات": "ACRO.CA",
    "أودن للاستثمارات": "ODIN.CA",
    "أوراسكوم للاستثمار": "OIH.CA",
    "أوراسكوم للتنمية": "ORHD.CA",
    "إعمار مصر للتنمية": "EMFD.CA",
    "إي فاينانس": "EFIH.CA",
    "إيديتا": "EFID.CA",
    "ابن سينا فارما": "ISPH.CA",
    "الأسكندرية لتداول الحاويات": "ALCN.CA",
    "الأسكندرية للزيوت المعدنية": "AMOC.CA",
    "الاسكندرية لأسمنت": "ALEX.CA",
    "الاسماعيلية مصر للدواجن": "ISMA.CA",
    "البنك التجاري الدولي": "COMI.CA",
    "التعمير والاستشارات": "DAPH.CA",
    "الجوهرة - العز للسيراميك": "ECAP.CA",
    "الجيزة العامة للمقاولات": "GGCC.CA",
    "الزيوت المستخلصة": "ZEOT.CA",
    "السويدي إليكتريك": "SWDY.CA",
    "الشرقية - إيسترن": "EAST.CA",
    "الشمس للإسكان": "ELSH.CA",
    "الصعيد العامة للمقاولات": "UEGC.CA",
    "العبوات الطبية": "MEPA.CA",
    "العربية للأدوية": "ADCI.CA",
    "العز الدخيلة للصلب": "IRAX.CA",
    "القاهرة للإسكان": "ELKA.CA",
    "القاهرة للدواجن": "POUL.CA",
    "القلعة للاستشارات": "CCAP.CA",
    "المصرية للاتصالات": "ETEL.CA",
    "المطورون العرب": "ARAB.CA",
    "المنصورة للدواجن": "MPCO.CA",
    "النيل للأدوية": "NIPH.CA",
    "بالم هيلز": "PHDC.CA",
    "بلتون المالية": "BTFH.CA",
    "بنك البركة مصر": "SAUD.CA",
    "بنك التعمير والإسكان": "HDBK.CA",
    "بنك فيصل الإسلامي": "FAIT.CA",
    "بنك قناة السويس": "CANA.CA",
    "جهينة": "JUFO.CA",
    "جي بي كورب": "GBCO.CA",
    "حديد عز": "ESRS.CA",
    "دومتي": "DOMT.CA",
    "راكتا": "RAKT.CA",
    "سيدي كرير": "SKPC.CA",
    "شمال أفريقيا": "NATI.CA",
    "صناع التغليف": "UNIP.CA",
    "طاقة عربية": "TAQA.CA",
    "عبر المحيطات": "GOCE.CA",
    "غاز مصر": "EGAS.CA",
    "فاركو": "PHAR.CA",
    "فوري": "FWRY.CA",
    "كيما": "EGCH.CA",
    "مجموعة هيرميس": "HRHO.CA",
    "مجموعة طلعت مصطفى": "TMGH.CA",
    "مدينة مصر": "MASR.CA",
    "مصر الجديدة": "HELI.CA",
    "مصر لإنتاج الأسمدة": "MFPC.CA",
    "مصر للألومنيوم": "EGAL.CA",
    "مصرف أبوظبي الإسلامي": "ADIB.CA",
    "مطاحن مصر الوسطى": "CEFM.CA",
    "مطاحن شمال القاهرة": "MNSF.CA",
}

# ============================================================
# العملات المشفرة
# ============================================================
CRYPTO_STOCKS = {
    "Bitcoin (BTC)": "BTC-USD",
    "Ethereum (ETH)": "ETH-USD",
    "Tether (USDT)": "USDT-USD",
    "BNB (Binance Coin)": "BNB-USD",
    "Solana (SOL)": "SOL-USD",
    "Ripple (XRP)": "XRP-USD",
    "Cardano (ADA)": "ADA-USD",
    "Dogecoin (DOGE)": "DOGE-USD",
    "Toncoin (TON)": "TON-USD",
    "Chainlink (LINK)": "LINK-USD",
    "Polkadot (DOT)": "DOT-USD",
    "Polygon (MATIC)": "MATIC-USD",
    "Shiba Inu (SHIB)": "SHIB-USD",
    "Litecoin (LTC)": "LTC-USD",
    "Bitcoin Cash (BCH)": "BCH-USD",
    "Uniswap (UNI)": "UNI-USD",
    "Avalanche (AVAX)": "AVAX-USD",
    "Cosmos (ATOM)": "ATOM-USD",
    "Ethereum Classic (ETC)": "ETC-USD",
    "Stellar (XLM)": "XLM-USD",
    "Monero (XMR)": "XMR-USD",
    "Algorand (ALGO)": "ALGO-USD",
    "VeChain (VET)": "VET-USD",
    "Filecoin (FIL)": "FIL-USD",
    "Hedera (HBAR)": "HBAR-USD",
    "Aptos (APT)": "APT-USD",
    "Sui (SUI)": "SUI-USD",
    "Pepe (PEPE)": "PEPE-USD",
    "Mantle (MNT)": "MNT-USD",
    "Internet Computer (ICP)": "ICP-USD",
}

# ============================================================
# تحميل قائمة S&P 500
# ============================================================
with st.spinner("جاري تحميل قائمة S&P 500..."):
    SP500_STOCKS = get_sp500_tickers()

# ============================================================
# دمج جميع الأسواق
# ============================================================

# دمج جميع الأسهم في قاموس واحد
ALL_STOCKS = {}
ALL_STOCKS.update(EGX_STOCKS)
ALL_STOCKS.update({f"{k} (US)": v for k, v in SP500_STOCKS.items()})
ALL_STOCKS.update({f"{k} (Crypto)": v for k, v in CRYPTO_STOCKS.items()})

# تصنيف القطاعات (سيتم تحديثه تلقائياً للأسهم الأمريكية)
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

# الأسهم الأمريكية - سنستخدم دالة لجلب القطاع من yfinance عند الحاجة
# سيتم تحديثها ديناميكياً في المسح

# ترتيب القائمة
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
                        decision = "🚀 تأسيس مركز (تقاطع ذهبي)"
                        color = "#1abc9c"
                    elif rsi < 35 and mfi < 35:
                        decision = "🛒 تجميع في القاع"
                        color = "#3498db"
                    elif ema9 > ema21 and rsi < 70 and mfi < 80:
                        decision = "⚡ STRONG BUY"
                        color = "#2ecc71"
                    elif price >= upper or rsi >= 75 or mfi >= 85:
                        decision = "🔴 SELL / TAKE PROFIT"
                        color = "#e74c3c"
                    else:
                        decision = "✋ HOLD"
                        color = "#f39c12"
                    
                    st.markdown(f'<div style="background-color:{color}; padding:20px; border-radius:10px; text-align:center; margin-bottom:20px;"><h2 style="color:white; margin:0;">القرار: {decision}</h2></div>', unsafe_allow_html=True)
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("السعر", f"{price:.2f} {currency}")
                    c2.metric("RSI", f"{rsi:.1f}")
                    c3.metric("MFI", f"{mfi:.1f}")
                    c4.metric("الحجم", f"{vol:,.0f}")

                    # التحليل المالي (لغير العملات المشفرة)
                    if ticker_input not in CRYPTO_STOCKS.values():
                        fundamentals = fetch_fundamentals(ticker_input)
                        fund_score = score_fundamentals(fundamentals)

                        st.markdown("##### 💰 التحليل المالي الأساسي")
                        f1, f2, f3, f4 = st.columns(4)
                        pe_display = f"{fundamentals['pe_ratio']:.2f}" if fundamentals.get("pe_ratio") else "غير متاح"
                        roe_display = f"{fundamentals['roe_%']:.1f}%" if fundamentals.get("roe_%") is not None else "غير متاح"
                        pm_display = f"{fundamentals['profit_margin_%']:.1f}%" if fundamentals.get("profit_margin_%") is not None else "غير متاح"
                        sector_display = fundamentals.get("sector", "غير متاح")
                        f1.metric("P/E", pe_display)
                        f2.metric("ROE", roe_display)
                        f3.metric("هامش الربح", pm_display)
                        f4.metric("القطاع", sector_display)

                        # قاعدة جراهام
                        graham = graham_from_fundamentals(fundamentals, price)
                        st.markdown("##### 📐 قاعدة جراهام")
                        g1, g2, g3 = st.columns(3)
                        graham_display = f"{graham['graham_number']:.2f}" if graham["graham_number"] else "غير متاح"
                        upside_display = f"{graham['graham_upside_%']:+.1f}%" if graham["graham_upside_%"] is not None else "—"
                        verdict_display = "✅ تحت العادل" if graham["undervalued_per_graham"] is True else "❌ فوق العادل" if graham["undervalued_per_graham"] is False else "غير متاح"
                        g1.metric("السعر العادل", graham_display)
                        g2.metric("الفرق", upside_display)
                        g3.metric("الحكم", verdict_display)

                    # الرسم البياني
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
        "💰 تضمين التحليل المالي (للأسهم فقط - قد يبطئ العملية)",
        value=False,
    )

    fcol1, fcol2 = st.columns(2)
    with fcol1:
        # جلب القطاعات المتاحة
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
                status_text.text(f"جاري تحليل {idx+1}/{total_stocks}: {name}")
                
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
                    
                    # تعديل حدود الفوليوم حسب السوق
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

                        graham = graham_from_fundamentals(fundamentals, p)
                        data_entry["جراهام"] = graham["graham_number"]
                        data_entry["فرق %"] = graham["graham_upside_%"]
                    
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

            st.success(f"✅ تم مسح {total_stocks - skipped_count} أصل بنجاح!")

            # إرسال التقرير
            telegram_msg = f"🦅 *تقرير الأسواق* 🌍\n📊 *{scan_market}*\n📅 {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            
            if fresh_cross_results:
                telegram_msg += "🌟 *تأسيس مركز:*\n"
                for item in fresh_cross_results[:5]:
                    telegram_msg += f"- {item['الاسم']} ({item['السعر']})\n"
                telegram_msg += "\n"
                
            if long_term_investment:
                _lt_df = pd.DataFrame(long_term_investment)
                _sort_col = "شامل" if "شامل" in _lt_df.columns else "النقاط"
                top_inv = _lt_df.sort_values(by=_sort_col, ascending=False).head(5)
                telegram_msg += "📈 *أفضل استثمار:*\n"
                for _, row in top_inv.iterrows():
                    telegram_msg += f"- {row['الاسم']} | {row['السعر']} | نقاط: {row['النقاط']}\n"
                telegram_msg += "\n"
                
            if short_term_trading:
                top_trade = pd.DataFrame(short_term_trading).sort_values(by="النقاط", ascending=False).head(5)
                telegram_msg += "⚡ *أفضل مضاربة:*\n"
                for _, row in top_trade.iterrows():
                    telegram_msg += f"- {row['الاسم']} | {row['السعر']}\n"
            
            if bottom_accumulation_results:
                telegram_msg += "\n📥 *قيعان محتملة:*\n"
                for item in bottom_accumulation_results[:5]:
                    telegram_msg += f"- {item['الاسم']} | RSI: {item['RSI']}\n"
            
            tg_success, tg_status_msg = send_telegram_alert(telegram_msg)
            if TELEGRAM_TOKEN or default_token or TELEGRAM_CHAT_ID or default_chat_id:
                if tg_success:
                    st.sidebar.success(tg_status_msg)
                else:
                    st.sidebar.error(tg_status_msg)
            
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
