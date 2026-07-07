import time
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np

# إعدادات الصفحة
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

st.title("🦅 قناص البورصة المصرية (النسخة المرتبة عالمياً)")

# إعدادات عامة
BATCH_SIZE = 30       
BATCH_DELAY = 1.5     
CROSS_LOOKBACK = 3    

try:
    default_token = st.secrets.get("TELEGRAM_TOKEN", "")
    default_chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
except:
    default_token = ""
    default_chat_id = ""

st.sidebar.header("⚙️ إعدادات تليجرام")
TELEGRAM_TOKEN = st.sidebar.text_input("أدخل Token:", value=default_token, type="password")
TELEGRAM_CHAT_ID = st.sidebar.text_input("أدخل Chat ID:", value=default_chat_id)

def send_telegram_alert(message):
    token = TELEGRAM_TOKEN if TELEGRAM_TOKEN else default_token
    chat_id = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else default_chat_id
    if not (token and chat_id): return False, "Missing credentials"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200, "Success"
    except: return False, "Error"

# القائمة الكاملة للأسهم
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
    "مطاحن مصر الوسطى": "CEFM.CA", "مطاحن ومخابز شمال القاهرة": "MNSF.CA"
}

def calculate_indicators(df):
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(-1)
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

@st.cache_data(ttl=300, show_spinner=False)
def fetch_batch_data(tickers_tuple, period="60d"):
    tickers = list(tickers_tuple)
    all_frames = {}
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        try:
            data = yf.download(batch, period=period, progress=False, group_by='ticker', threads=True)
            for t in batch:
                try:
                    df_t = data[t] if len(batch) > 1 else data
                    if not df_t.dropna(how='all').empty: all_frames[t] = df_t
                except: continue
            time.sleep(BATCH_DELAY)
        except: continue
    return all_frames

tab1, tab2 = st.tabs(["🔍 تحليل سهم", "🏆 مسح السوق"])

with tab1:
    selected_stock = st.selectbox("اختر السهم:", list(ALL_EGX_STOCKS.keys()))
    ticker_input = ALL_EGX_STOCKS[selected_stock]
    if st.button("تحليل"):
        df = yf.download(ticker_input, period="100d", progress=False)
        if not df.empty:
            df = calculate_indicators(df)
            last = df.iloc[-1]
            st.metric("السعر الحالي", f"{float(last['Close']):.2f} ج.م")
            st.line_chart(df[['Close', 'EMA9', 'EMA21']])

with tab2:
    if st.button("تشغيل المسح والترتيب العام"):
        all_data = fetch_batch_data(tuple(ALL_EGX_STOCKS.values()))
        fresh_cross = []; long_term = []; short_term = []; bottom_catch = []
        
        for name, ticker in ALL_EGX_STOCKS.items():
            if ticker in all_data:
                df = calculate_indicators(all_data[ticker].dropna(how='all'))
                if len(df) < 25: continue
                last = df.iloc[-1]; prev = df.iloc[-CROSS_LOOKBACK]
                p, e9, e21, r, m = float(last['Close']), float(last['EMA9']), float(last['EMA21']), float(last['RSI_14']), float(last['MFI_14'])
                
                score = 0
                if e9 > e21: score += 40
                if 50 <= m <= 70: score += 30
                if 45 <= r <= 65: score += 20
                
                entry = {"اسم الشركة": name, "السعر الحالي (ج.م)": round(p, 2), "النقاط الفنية والسيولة (من 100)": score}
                
                if (prev['EMA9'] <= prev['EMA21']) and (e9 > e21): fresh_cross.append({**entry, "الفئة": "تأسيس"})
                elif r < 35 and m < 35: bottom_catch.append({"اسم الشركة": name, "السعر الحالي (ج.م)": round(p, 2), "RSI": round(r, 1)})
                elif e9 > e21:
                    if r > 50: short_term.append({**entry, "الفئة": "مضاربة"})
                    else: long_term.append({**entry, "الفئة": "استثمار"})

        # دمج وترتيب عام
        all_opps = fresh_cross + long_term + short_term
        df_all = pd.DataFrame(all_opps)
        
        if not df_all.empty:
            df_all = df_all.sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False)
            st.dataframe(df_all)
            
            # بناء الرسالة
            msg = "🦅 *تقرير القناص (الترتيب العام للأقوى):* \n\n"
            for _, row in df_all.head(20).iterrows():
                msg += f"- {row['اسم الشركة']} ({row['الفئة']}) | {row['السعر الحالي (ج.م)']} ج.م | النقاط: {row['النقاط الفنية والسيولة (من 100)']}\n"
            
            if bottom_catch:
                msg += "\n*🐋 رادار القيعان:*\n"
                for b in bottom_catch[:5]:
                    msg += f"- {b['اسم الشركة']} | {b['السعر الحالي (ج.م)']} ج.م | RSI: {b['RSI']}\n"
            
            send_telegram_alert(msg)
            st.success("تم الإرسال!")
