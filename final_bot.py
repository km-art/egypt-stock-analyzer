import time
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="محلل الأسواق العالمي الاحترافي 🌍📈", layout="wide")

st.title("🦅 قناص الأسواق العالمية (النسخة المتكاملة المقفلة ضد المخاطر)")
st.write("تم تقفيل الكود بمعايير صارمة: إضافة حد أدنى للفوليوم لحجب الأسهم الميتة، وفلاتر حماية من التضخم الحاد.")
st.write("🇪🇬 البورصة المصرية | 🇺🇸 البورصة الأمريكية | ₿ العملات الرقمية")

# إعدادات عامة قابلة للتعديل
BATCH_SIZE = 30       # عدد الأسهم في كل طلب تحميل - تقسيم لدفعات لتفادي رفض Yahoo Finance للطلبات الضخمة
BATCH_DELAY = 1.5     # ثواني انتظار بين كل دفعة وأخرى
CROSS_LOOKBACK = 3    # كام يوم نرجع بيهم للخلف لاكتشاف "تقاطع جديد" (نفس القيمة تستخدم في التاب الأول والثاني)

# القراءة التلقائية من Streamlit Secrets كخيار احتياطي
try:
    default_token = st.secrets.get("TELEGRAM_TOKEN", "")
    default_chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
except Exception:
    default_token = ""
    default_chat_id = ""

# إعدادات التنبيهات في الشريط الجانبي
st.sidebar.header("⚙️ إعدادات إشعارات الموبايل (تليجرام)")
TELEGRAM_TOKEN = st.sidebar.text_input("أدخل Token البوت:", value=default_token, type="password")
TELEGRAM_CHAT_ID = st.sidebar.text_input("أدخل Chat ID الخاص بك:", value=default_token)

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

# ==================== قوائم الأسواق ====================

# القائمة الكاملة لرموز أسهم السوق المصري (EGX) على Yahoo Finance
EGX_STOCKS = {
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

# ==================== الأسهم الأمريكية ====================
US_STOCKS = {
    "Apple Inc.": "AAPL",
    "Microsoft Corp.": "MSFT",
    "NVIDIA Corp.": "NVDA",
    "Amazon.com Inc.": "AMZN",
    "Alphabet Inc. (GOOGL)": "GOOGL",
    "Alphabet Inc. (GOOG)": "GOOG",
    "Meta Platforms Inc.": "META",
    "Tesla Inc.": "TSLA",
    "Berkshire Hathaway B": "BRK-B",
    "JPMorgan Chase": "JPM",
    "Visa Inc.": "V",
    "UnitedHealth Group": "UNH",
    "Exxon Mobil": "XOM",
    "Johnson & Johnson": "JNJ",
    "Walmart Inc.": "WMT",
    "Procter & Gamble": "PG",
    "Mastercard Inc.": "MA",
    "Bank of America": "BAC",
    "Coca-Cola Co.": "KO",
    "PepsiCo Inc.": "PEP",
    "Netflix Inc.": "NFLX",
    "Adobe Inc.": "ADBE",
    "Salesforce Inc.": "CRM",
    "Intel Corp.": "INTC",
    "Advanced Micro Devices": "AMD",
    "Cisco Systems": "CSCO",
    "Oracle Corp.": "ORCL",
    "IBM": "IBM",
    "Qualcomm Inc.": "QCOM",
    "Texas Instruments": "TXN",
    "Broadcom Inc.": "AVGO",
    "Dell Technologies": "DELL",
    "HP Inc.": "HPQ",
    "Danaher Corp.": "DHR",
    "Thermo Fisher Scientific": "TMO",
    "Abbott Laboratories": "ABT",
    "Medtronic plc": "MDT",
    "Pfizer Inc.": "PFE",
    "Merck & Co.": "MRK",
    "Eli Lilly": "LLY",
    "AbbVie Inc.": "ABBV",
    "Bristol-Myers Squibb": "BMY",
    "Amgen Inc.": "AMGN",
    "Gilead Sciences": "GILD",
    "Regeneron Pharmaceuticals": "REGN",
    "Chevron Corp.": "CVX",
    "ConocoPhillips": "COP",
    "Schlumberger Ltd.": "SLB",
    "Home Depot Inc.": "HD",
    "Lowe's Companies": "LOW",
    "McDonald's Corp.": "MCD",
    "Starbucks Corp.": "SBUX",
    "Nike Inc.": "NKE",
    "Disney (Walt) Co.": "DIS",
    "Comcast Corp.": "CMCSA",
    "Verizon Communications": "VZ",
    "AT&T Inc.": "T",
    "T-Mobile US": "TMUS",
    "American Express": "AXP",
    "Goldman Sachs": "GS",
    "Morgan Stanley": "MS",
    "Citigroup Inc.": "C",
    "Wells Fargo": "WFC",
    "BlackRock Inc.": "BLK",
    "Charles Schwab": "SCHW",
    "S&P Global Inc.": "SPGI",
    "Moody's Corp.": "MCO",
    "Marsh & McLennan": "MMC",
    "Aon plc": "AON",
    "Lockheed Martin": "LMT",
    "Boeing Co.": "BA",
    "General Electric": "GE",
    "Honeywell International": "HON",
    "3M Company": "MMM",
    "Caterpillar Inc.": "CAT",
    "Deere & Co.": "DE",
    "FedEx Corp.": "FDX",
    "United Parcel Service": "UPS",
    "Union Pacific": "UNP",
    "Costco Wholesale": "COST",
    "Target Corp.": "TGT",
    "TJX Companies": "TJX",
    "Ross Stores": "ROST",
    "Lululemon Athletica": "LULU",
    "Booking Holdings": "BKNG",
    "Airbnb Inc.": "ABNB",
    "Uber Technologies": "UBER",
    "Lyft Inc.": "LYFT",
    "Palantir Technologies": "PLTR",
    "Snowflake Inc.": "SNOW",
    "Datadog Inc.": "DDOG",
    "CrowdStrike Holdings": "CRWD",
    "Palo Alto Networks": "PANW",
    "Fortinet Inc.": "FTNT",
    "Coupang Inc.": "CPNG",
    "Sea Ltd.": "SE",
    "Shopify Inc.": "SHOP",
    "MercadoLibre Inc.": "MELI",
    "Spotify Technology": "SPOT",
    "Block Inc.": "SQ",
    "PayPal Holdings": "PYPL",
    "Coinbase Global": "COIN",
    "Robinhood Markets": "HOOD",
    "SoFi Technologies": "SOFI",
    "Rivian Automotive": "RIVN",
    "Lucid Group": "LCID",
}

# ==================== العملات الرقمية ====================
CRYPTO_STOCKS = {
    "Bitcoin (BTC-USD)": "BTC-USD",
    "Ethereum (ETH-USD)": "ETH-USD",
    "Tether (USDT-USD)": "USDT-USD",
    "BNB (BNB-USD)": "BNB-USD",
    "Solana (SOL-USD)": "SOL-USD",
    "XRP (XRP-USD)": "XRP-USD",
    "Cardano (ADA-USD)": "ADA-USD",
    "Dogecoin (DOGE-USD)": "DOGE-USD",
    "Polkadot (DOT-USD)": "DOT-USD",
    "Polygon (MATIC-USD)": "MATIC-USD",
    "Chainlink (LINK-USD)": "LINK-USD",
    "Avalanche (AVAX-USD)": "AVAX-USD",
    "Uniswap (UNI-USD)": "UNI-USD",
    "Cosmos (ATOM-USD)": "ATOM-USD",
    "Ethereum Classic (ETC-USD)": "ETC-USD",
    "Litecoin (LTC-USD)": "LTC-USD",
    "Bitcoin Cash (BCH-USD)": "BCH-USD",
    "Stellar (XLM-USD)": "XLM-USD",
    "VeChain (VET-USD)": "VET-USD",
    "Internet Computer (ICP-USD)": "ICP-USD",
    "Filecoin (FIL-USD)": "FIL-USD",
    "Hedera (HBAR-USD)": "HBAR-USD",
    "Near Protocol (NEAR-USD)": "NEAR-USD",
    "Aptos (APT-USD)": "APT-USD",
    "Arbitrum (ARB-USD)": "ARB-USD",
    "Optimism (OP-USD)": "OP-USD",
    "Sui (SUI-USD)": "SUI-USD",
    "Sei (SEI-USD)": "SEI-USD",
    "Celestia (TIA-USD)": "TIA-USD",
    "Injective (INJ-USD)": "INJ-USD",
    "Mantle (MNT-USD)": "MNT-USD",
    "Stacks (STX-USD)": "STX-USD",
    "Maker (MKR-USD)": "MKR-USD",
    "Aave (AAVE-USD)": "AAVE-USD",
    "Curve (CRV-USD)": "CRV-USD",
    "Lido DAO (LDO-USD)": "LDO-USD",
    "Rocket Pool (RPL-USD)": "RPL-USD",
    "Frax (FRAX-USD)": "FRAX-USD",
    "PancakeSwap (CAKE-USD)": "CAKE-USD",
    "SushiSwap (SUSHI-USD)": "SUSHI-USD",
    "Gala (GALA-USD)": "GALA-USD",
    "Axie Infinity (AXS-USD)": "AXS-USD",
    "The Sandbox (SAND-USD)": "SAND-USD",
    "Decentraland (MANA-USD)": "MANA-USD",
    "ApeCoin (APE-USD)": "APE-USD",
    "Chiliz (CHZ-USD)": "CHZ-USD",
    "Pepe (PEPE-USD)": "PEPE-USD",
    "Bonk (BONK-USD)": "BONK-USD",
    "Floki Inu (FLOKI-USD)": "FLOKI-USD",
}

# دمج كل الأسواق في قائمة واحدة
ALL_MARKETS = {**EGX_STOCKS, **US_STOCKS, **CRYPTO_STOCKS}

# تصنيف القطاع لكل سهم (موسع للأسواق المختلفة)
def get_sector(ticker: str) -> str:
    """تحديد القطاع بناءً على الرمز أو السوق"""
    # العملات الرقمية
    if "-USD" in ticker:
        return "عملات رقمية"
    # الأسهم المصرية
    if ticker in TICKER_SECTOR_EGYPT:
        return TICKER_SECTOR_EGYPT[ticker]
    # الأسهم الأمريكية - تصنيف تقريبي حسب أول حرفين أو الكلمة
    if ticker in TICKER_SECTOR_US:
        return TICKER_SECTOR_US[ticker]
    # تصنيف تلقائي للأسهم الأمريكية حسب الرمز
    if ticker.isupper() and not ticker.endswith(".CA"):
        # تصنيفات تقريبية
        tech_tickers = {"AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META", "INTC", "AMD", "CSCO", "ORCL", "IBM", "QCOM", "TXN", "AVGO", "DELL", "HPQ", "PLTR", "SNOW", "DDOG", "CRWD", "PANW", "FTNT", "ADBE", "CRM"}
        fin_tickers = {"JPM", "BAC", "WFC", "C", "GS", "MS", "AXP", "BLK", "SCHW", "V", "MA", "PYPL", "SQ", "COIN", "HOOD"}
        health_tickers = {"UNH", "JNJ", "PFE", "MRK", "LLY", "ABBV", "BMY", "AMGN", "GILD", "REGN", "ABT", "TMO", "MDT", "DHR"}
        consumer_tickers = {"WMT", "PG", "KO", "PEP", "HD", "LOW", "MCD", "SBUX", "NKE", "DIS", "COST", "TGT", "TJX", "ROST", "LULU"}
        energy_tickers = {"XOM", "CVX", "COP", "SLB"}
        industrial_tickers = {"BA", "GE", "HON", "MMM", "CAT", "DE", "FDX", "UPS", "UNP", "LMT"}
        comm_tickers = {"CMCSA", "VZ", "T", "TMUS"}
        
        if ticker in tech_tickers:
            return "تكنولوجيا"
        elif ticker in fin_tickers:
            return "مالي"
        elif ticker in health_tickers:
            return "رعاية صحية"
        elif ticker in consumer_tickers:
            return "استهلاكي"
        elif ticker in energy_tickers:
            return "طاقة"
        elif ticker in industrial_tickers:
            return "صناعي"
        elif ticker in comm_tickers:
            return "اتصالات"
        else:
            return "غير مصنف"
    
    return "غير مصنف"

# تصنيفات الأسهم المصرية
TICKER_SECTOR_EGYPT = {
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

# تصنيفات الأسهم الأمريكية (تكميلية)
TICKER_SECTOR_US = {
    # Technology
    "AAPL": "تكنولوجيا", "MSFT": "تكنولوجيا", "NVDA": "تكنولوجيا", "AMZN": "تكنولوجيا",
    "GOOGL": "تكنولوجيا", "GOOG": "تكنولوجيا", "META": "تكنولوجيا", "INTC": "تكنولوجيا",
    "AMD": "تكنولوجيا", "CSCO": "تكنولوجيا", "ORCL": "تكنولوجيا", "IBM": "تكنولوجيا",
    "QCOM": "تكنولوجيا", "TXN": "تكنولوجيا", "AVGO": "تكنولوجيا", "DELL": "تكنولوجيا",
    "HPQ": "تكنولوجيا", "PLTR": "تكنولوجيا", "SNOW": "تكنولوجيا", "DDOG": "تكنولوجيا",
    "CRWD": "تكنولوجيا", "PANW": "تكنولوجيا", "FTNT": "تكنولوجيا", "ADBE": "تكنولوجيا",
    "CRM": "تكنولوجيا", "NFLX": "تكنولوجيا",
    # Financial
    "JPM": "مالي", "BAC": "مالي", "WFC": "مالي", "C": "مالي", "GS": "مالي",
    "MS": "مالي", "AXP": "مالي", "BLK": "مالي", "SCHW": "مالي", "V": "مالي",
    "MA": "مالي", "PYPL": "مالي", "SQ": "مالي", "COIN": "مالي", "HOOD": "مالي",
    "SPGI": "مالي", "MCO": "مالي", "MMC": "مالي", "AON": "مالي",
    # Healthcare
    "UNH": "رعاية صحية", "JNJ": "رعاية صحية", "PFE": "رعاية صحية", "MRK": "رعاية صحية",
    "LLY": "رعاية صحية", "ABBV": "رعاية صحية", "BMY": "رعاية صحية", "AMGN": "رعاية صحية",
    "GILD": "رعاية صحية", "REGN": "رعاية صحية", "ABT": "رعاية صحية", "TMO": "رعاية صحية",
    "MDT": "رعاية صحية", "DHR": "رعاية صحية",
    # Consumer
    "WMT": "استهلاكي", "PG": "استهلاكي", "KO": "استهلاكي", "PEP": "استهلاكي",
    "HD": "استهلاكي", "LOW": "استهلاكي", "MCD": "استهلاكي", "SBUX": "استهلاكي",
    "NKE": "استهلاكي", "DIS": "استهلاكي", "COST": "استهلاكي", "TGT": "استهلاكي",
    "TJX": "استهلاكي", "ROST": "استهلاكي", "LULU": "استهلاكي",
    "BKNG": "استهلاكي", "ABNB": "استهلاكي", "UBER": "استهلاكي", "LYFT": "استهلاكي",
    "CPNG": "استهلاكي", "SHOP": "استهلاكي", "MELI": "استهلاكي", "SE": "استهلاكي",
    "SPOT": "استهلاكي",
    # Energy
    "XOM": "طاقة", "CVX": "طاقة", "COP": "طاقة", "SLB": "طاقة",
    # Industrial
    "BA": "صناعي", "GE": "صناعي", "HON": "صناعي", "MMM": "صناعي",
    "CAT": "صناعي", "DE": "صناعي", "FDX": "صناعي", "UPS": "صناعي",
    "UNP": "صناعي", "LMT": "صناعي",
    # Communications
    "CMCSA": "اتصالات", "VZ": "اتصالات", "T": "اتصالات", "TMUS": "اتصالات",
    # Crypto/EV
    "RIVN": "صناعي", "LCID": "صناعي", "TSLA": "صناعي",
}

# ==================== الدوال الأساسية (نفسها بدون تعديل) ====================

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

# ==================== واجهة المستخدم ====================

# اختيار السوق
market_option = st.sidebar.selectbox(
    "🌍 اختيار السوق",
    options=["🇪🇬 البورصة المصرية", "🇺🇸 البورصة الأمريكية", "₿ العملات الرقمية", "🌐 جميع الأسواق"],
    index=0
)

# تحديد القائمة المناسبة
if market_option == "🇪🇬 البورصة المصرية":
    MARKET_STOCKS = EGX_STOCKS
    market_label = "البورصة المصرية"
elif market_option == "🇺🇸 البورصة الأمريكية":
    MARKET_STOCKS = US_STOCKS
    market_label = "البورصة الأمريكية"
elif market_option == "₿ العملات الرقمية":
    MARKET_STOCKS = CRYPTO_STOCKS
    market_label = "العملات الرقمية"
else:
    MARKET_STOCKS = ALL_MARKETS
    market_label = "جميع الأسواق"

# ترتيب القائمة حسب الرمز
MARKET_STOCKS = dict(sorted(MARKET_STOCKS.items(), key=lambda kv: kv[1]))

# ==================== TAB1: فحص سهم تفصيلي ====================

tab1, tab2 = st.tabs(["🔍 فحص سهم تفصيلي + رسم بياني", "🏆 مسح وترتيب السوق الاحترافي"])

with tab1:
    st.subheader(f"اختر سهمك المفضل لتحليله ورسم بياناته بالتفصيل - {market_label}")
    col_input1, col_input2 = st.columns([2, 1])
    with col_input1:
        selected_stock = st.selectbox("اختر من قائمة السوق:", list(MARKET_STOCKS.keys()))
        ticker_input = MARKET_STOCKS[selected_stock]
    with col_input2:
        manual_ticker = st.text_input("أو اكتب رمزاً مخصصاً يدوياً:", value="").strip().upper()
        if manual_ticker:
            ticker_input = manual_ticker

    if st.button("تحليل السهم ورسم المنحنى ⚡"):
        with st.spinner("جاري جلب البيانات..."):
            try:
                # للعملات الرقمية نستخدم فترة أطول شوية
                period = "100d"
                if "-USD" in ticker_input:
                    period = "120d"
                    
                df = fetch_single_stock(ticker_input, period=period)
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
                    c1.metric("السعر الحالي", f"{price:.2f} دولار" if "-USD" in ticker_input else f"{price:.2f} ج.م")
                    c2.metric("مؤشر الزخم RSI", f"{rsi:.1f}")
                    c3.metric("مؤشر السيولة MFI", f"{mfi:.1f}")
                    c4.metric("حجم تداول اليوم (فوليوم)", f"{vol:,.0f}")

                    # التحليل المالي الأساسي (للأسهم العادية فقط)
                    if not "-USD" in ticker_input:
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
                            st.caption("⚠️ البيانات المالية رجعت فاضية - على الأغلب Yahoo Finance رافض/حاظر الطلبات المالية مؤقتاً.")

                        # قاعدة جراهام
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
                            st.caption("⚠️ EPS و/أو BVPS المستخدمين هنا **مُشتقين تقريبياً** من P/E و P/B - راجعهم يدوياً قبل أي قرار.")
                    else:
                        st.info("💰 البيانات المالية غير متاحة للعملات الرقمية")

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].squeeze(), name='سعر الإغلاق', line=dict(color='#1f77b4', width=2)))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'].squeeze(), name='EMA 9', line=dict(color='#2ca02c', dash='dot')))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'].squeeze(), name='EMA 21', line=dict(color='#d62728', dash='dash')))
                    fig.update_layout(template="plotly_dark", height=450)
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"حدث خطأ: {e}")

# ==================== TAB2: مسح السوق ====================

with tab2:
    st.subheader(f"📊 الفرز والترتيب المتقدم لأسهم {market_label}")
    
    include_fundamentals_scan = st.checkbox(
        "💰 تضمين التحليل المالي الأساسي + رقم جراهام (P/E, ROE, السعر العادل...) - أبطأ بكتير",
        value=False,
    )

    fcol1, fcol2 = st.columns(2)
    with fcol1:
        available_sectors = sorted(set(get_sector(t) for t in MARKET_STOCKS.values()))
        selected_sectors_scan = st.multiselect(
            "🏢 فلتر القطاع (اختر واحد أو أكتر - سيبه فاضي لعرض كل القطاعات)",
            options=available_sectors,
            default=[],
        )
    with fcol2:
        min_liquidity_scan = st.checkbox(
            "💧 متوسط قيمة التداول اليومي (تقريبي) فوق 3 مليون فقط",
            value=False,
        )

    if st.button("تشغيل الفرز والترتيب الاحترافي اللحظي 🚀"):
        fresh_cross_results = []
        bottom_accumulation_results = []
        short_term_trading = []
        long_term_investment = []
        
        progress_bar = st.progress(0)
        total_stocks = len(MARKET_STOCKS)
        
        with st.spinner(f"جاري مسح {len(MARKET_STOCKS)} سهم على دفعات..."):
            tickers_list = list(MARKET_STOCKS.values())
            all_data, failed_tickers = fetch_batch_data(tuple(tickers_list), period="60d")

            if failed_tickers:
                st.warning(f"⚠️ تعذر تحميل بيانات {len(failed_tickers)} سهم من أصل {len(tickers_list)}")

            skipped_count = 0
            skipped_names = []
            for idx, (name, ticker) in enumerate(MARKET_STOCKS.items()):
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

                    sector = get_sector(ticker)
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
                    
                    # تحديد العملة
                    currency = "دولار" if "-USD" in ticker else "ج.م"
                    
                    data_entry = {
                        "النقاط الفنية والسيولة (من 100)": round(momentum_score, 1),
                        "اسم الشركة": name,
                        "الرمز البرمجي": ticker,
                        "القطاع": sector,
                        "السعر الحالي": f"{round(p, 2)} {currency}",
                        "مؤشر الزخم RSI": round(r, 1),
                        "مؤشر السيولة MFI": round(m, 1),
                        "فوليوم اليوم": f"{vol_today:,.0f}",
                        "متوسط فوليوم 10أيام": f"{vol_ma10:,.0f}",
                        "متوسط قيمة التداول (تقريبي)": f"{avg_trade_value:,.0f}",
                        "التقييم الفني": status
                    }

                    if include_fundamentals_scan and not "-USD" in ticker:
                        fundamentals = fetch_fundamentals(ticker)
                        fund_score = score_fundamentals(fundamentals)
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
                    
                    if is_new_cross and r < 52:
                        data_entry["التقييم الفني"] = "✨ تأسيس مركز (قاع صاعد طازة)"
                        fresh_cross_results.append(data_entry)
                    
                    elif r < 35 and m < 35:
                        data_entry["التقييم الفني"] = "🛒 قاع تجميع (فرصة مراقبة صامتة)"
                        bottom_accumulation_results.append(data_entry)
                    
                    elif e9 > e21:
                        if vol_today > (vol_ma10 * 1.15) and 50 <= r <= 78:
                            data_entry["التقييم الفني"] = f"{status} [مضاربة لحظية]"
                            short_term_trading.append(data_entry)
                        else:
                            data_entry["التقييم الفني"] = f"{status} [استثمار مستقر]"
                            long_term_investment.append(data_entry)
                except Exception as e:
                    skipped_count += 1
                    skipped_names.append((name, ticker, f"خطأ أثناء التحليل: {e}"))
                    continue
            
            if skipped_count:
                st.info(f"ℹ️ تم تخطي {skipped_count} سهم أثناء التحليل.")
                with st.expander(f"📋 عرض تفاصيل الـ {skipped_count} سهم اللي اتخطاها"):
                    for name, ticker, reason in skipped_names:
                        st.write(f"- **{name}** ({ticker}) — {reason}")

            st.success("تم التحديث النهائي والإغلاق الهندسي للرادار بنجاح! 🦅")
            
            # إرسال التقرير
            telegram_msg = f"🦅 *تقرير قناص {market_label} اللحظي* 🌍\n\n"
            
            if fresh_cross_results:
                telegram_msg += "🌟 *أسهم تأسيس المركز (قاع صاعد):*\n"
                for item in fresh_cross_results[:5]:
                    telegram_msg += f"- {item['اسم الشركة']} ({item['السعر الحالي']})\n"
                telegram_msg += "\n"
                
            if long_term_investment:
                _lt_df = pd.DataFrame(long_term_investment)
                _sort_col = "الدرجة الشاملة (فني+مالي)" if "الدرجة الشاملة (فني+مالي)" in _lt_df.columns else "النقاط الفنية والسيولة (من 100)"
                top_inv = _lt_df.sort_values(by=_sort_col, ascending=False).head(5)
                telegram_msg += "📈 *أقوى الأسهم في الاتجاه الصاعد المستقر:*\n"
                for _, row_inv in top_inv.iterrows():
                    telegram_msg += f"- {row_inv['اسم الشركة']} | السعر: {row_inv['السعر الحالي']} | النقاط: {row_inv['النقاط الفنية والسيولة (من 100)']}\n"
                telegram_msg += "\n"
                
            if short_term_trading:
                top_trade = pd.DataFrame(short_term_trading).sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False).head(5)
                telegram_msg += "⚡ *أقوى أسهم المضاربة اللحظية وعزم السيولة:*\n"
                for _, row_tr in top_trade.iterrows():
                    telegram_msg += f"- {row_tr['اسم الشركة']} | السعر: {row_tr['السعر الحالي']}\n"
            
            tg_success, tg_status_msg = send_telegram_alert(telegram_msg)
            if TELEGRAM_TOKEN or default_token or TELEGRAM_CHAT_ID or default_chat_id:
                if tg_success:
                    st.sidebar.success(tg_status_msg)
                else:
                    st.sidebar.error(tg_status_msg)
            
            # عرض الجداول
            st.markdown("### 🚀 أولاً: أسهم لقطت 'إشارة تأسيس مركز جديدة اليوم'")
            if fresh_cross_results:
                st.dataframe(pd.DataFrame(fresh_cross_results).sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False), use_container_width=True)
            else:
                st.info("لا توجد أسهم لقطت تقاطع ذهبي هادئ اليوم واستوفت شروط الفوليوم الحقيقي.")
                
            st.write("---")
            
            st.markdown("### 📥 ثانياً: رادار تصيد القيعان (أسهم رخيصة جداً في مناطق تجميع الحيتان 🐋)")
            if bottom_accumulation_results:
                st.dataframe(pd.DataFrame(bottom_accumulation_results).sort_values(by="مؤشر الزخم RSI", ascending=True), use_container_width=True)
            else:
                st.info("لا توجد أسهم حالياً في قيعان التشبع البيعي الحاد تحت 35 تنطبق عليها شروط الفوليوم الأمان.")
                
            st.write("---")
            
            st.markdown("### ⚡ ثالثاً: أسهم المضاربة اللحظية واليومية")
            if short_term_trading:
                st.dataframe(pd.DataFrame(short_term_trading).sort_values(by="فوليوم اليوم", ascending=False), use_container_width=True)
            else:
                st.info("لا توجد أسهم مستوفية لشروط الحركات المضاربية النشطة والآمنة حالياً.")

            st.write("---")
            
            st.markdown("### 📈 رابعاً: أسهم الاستثمار والاتجاه الصاعد المستقر")
            if long_term_investment:
                lt_df = pd.DataFrame(long_term_investment)
                sort_col = "الدرجة الشاملة (فني+مالي)" if "الدرجة الشاملة (فني+مالي)" in lt_df.columns else "النقاط الفنية والسيولة (من 100)"
                st.dataframe(lt_df.sort_values(by=sort_col, ascending=False), use_container_width=True)
                if include_fundamentals_scan:
                    st.caption("💡 مرتبة حسب 'الدرجة الشاملة' = 60% فني + 40% مالي.")
