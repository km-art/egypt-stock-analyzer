import time
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="المحلل المالي العالمي الاحترافي 🌍📈", layout="wide")

st.title("🦅 القناص المالي المتعدد الأسواق (EGX - US - UAE)")
st.write("النسخة المتكاملة: مع نظام تشخيص الأخطاء وحماية البيانات.")

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

st.sidebar.markdown("---")
st.sidebar.header("🌍 اختيار السوق المالي")
market_choice = st.sidebar.selectbox(
    "حدد السوق المطلوب تحليله:",
    ["البورصة المصرية (EGX) 🇪🇬", "الأسهم الأمريكية (US) 🇺🇸", "الأسهم الإماراتية (UAE) 🇦🇪"]
)

# تحديد القواميس والعملة بناءً على السوق المختار
if "المصرية" in market_choice:
    CURRENCY = "ج.م"
    DEFAULT_MIN_VOL = 50000
    ALL_STOCKS = {
        "Commercial International Bank": "COMI.CA", "Talaat Moustafa Group": "TMGH.CA",
        "Elsewedy Electric": "SWDY.CA", "Eastern Company": "EAST.CA", "Fawry": "FWRY.CA",
        "Ezz Steel": "ESRS.CA", "EFG Hermes": "HRHO.CA", "Abu Qir Fertilizers": "ABUK.CA",
        "Misr Production Fertilisers (MOPCO)": "MFPC.CA", "Sidi Kerir Petrochemicals": "SKPC.CA",
        "Palm Hills Developments": "PHDC.CA", "SODIC": "OCDI.CA", "Madinet Masr": "MASR.CA",
        "Juhayna Food Industries": "JUFO.CA", "Orascom Construction": "ORAS.CA",
        "Alexandria Containers": "ALCN.CA", "Arabian Food Industries (Domty)": "DOMT.CA"
    }
    TICKER_SECTOR = {
        "COMI.CA": "بنوك", "TMGH.CA": "عقاري", "SWDY.CA": "تصنيع", "EAST.CA": "استهلاكي",
        "ABUK.CA": "تصنيع", "ALCN.CA": "تصنيع", "ORAS.CA": "تصنيع", "FWRY.CA": "تكنولوجيا",
        "PHDC.CA": "عقاري", "ESRS.CA": "تصنيع", "HRHO.CA": "مالي غير مصرفي", "JUFO.CA": "استهلاكي",
        "OCDI.CA": "عقاري", "MASR.CA": "عقاري", "SKPC.CA": "تصنيع", "DOMT.CA": "استهلاكي",
        "MFPC.CA": "تصنيع"
    }
elif "الأمريكية" in market_choice:
    CURRENCY = "$"
    DEFAULT_MIN_VOL = 500000
    ALL_STOCKS = {
        "Apple Inc.": "AAPL", "Microsoft Corporation": "MSFT", "NVIDIA Corporation": "NVDA",
        "Amazon.com Inc.": "AMZN", "Alphabet Inc. (Google)": "GOOGL", "Meta Platforms": "META",
        "Tesla Inc.": "TSLA", "Berkshire Hathaway": "BRK-B", "JPMorgan Chase": "JPM",
        "Visa Inc.": "V", "Johnson & Johnson": "JNJ", "Exxon Mobil": "XOM",
        "Walmart Inc.": "WMT", "Mastercard": "MA", "Netflix Inc.": "NFLX",
        "Advanced Micro Devices (AMD)": "AMD", "Intel Corporation": "INTC", "Cisco Systems": "CSCO"
    }
    TICKER_SECTOR = {
        "AAPL": "تكنولوجيا", "MSFT": "تكنولوجيا", "NVDA": "تكنولوجيا", "AMZN": "استهلاكي",
        "GOOGL": "تكنولوجيا", "META": "تكنولوجيا", "TSLA": "تصنيع", "BRK-B": "مالي غير مصرفي",
        "JPM": "بنوك", "V": "مالي غير مصرفي", "JNJ": "رعاية صحية", "XOM": "طاقة",
        "WMT": "استهلاكي", "MA": "مالي غير مصرفي", "NFLX": "تكنولوجيا", "AMD": "تكنولوجيا",
        "INTC": "تكنولوجيا", "CSCO": "تكنولوجيا"
    }
else:  # الإماراتية
    CURRENCY = "د.إ"
    DEFAULT_MIN_VOL = 100000
    ALL_STOCKS = {
        "Emaar Properties (DFM)": "EMAAR.DU", "Emirates NBD (DFM)": "ENBD.DU",
        "Dubai Islamic Bank (DFM)": "DIB.DU", "First Abu Dhabi Bank (ADX)": "FAB.AD",
        "International Holding Company (ADX)": "IHC.AD", "Aldar Properties (ADX)": "ALDAR.AD"
    }
    TICKER_SECTOR = {
        "EMAAR.DU": "عقاري", "ENBD.DU": "بنوك", "DIB.DU": "بنوك",
        "FAB.AD": "بنوك", "IHC.AD": "استثمار متنوع", "ALDAR.AD": "عقاري"
    }

ALL_STOCKS = dict(sorted(ALL_STOCKS.items(), key=lambda kv: kv[1]))

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
        time.sleep(BATCH_DELAY)

    return all_frames, failed

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

tab1, tab2 = st.tabs(["🔍 فحص سهم تفصيلي + رسم بياني", "🏆 مسح وترتيب السوق الاحترافي"])

with tab2:
    st.subheader(f"📊 مسح وترتيب سوق {market_choice}")
    
    if "الإماراتية" in market_choice:
        st.warning("⚠️ تنبيه هام: منصة Yahoo Finance لا توفر تغطية مستقرة للأسهم الإماراتية (.DU / .AD). إذا لم تظهر نتائج، فهذا بسبب عدم توفر بيانات المصدر الخارجي.")

    if st.button("تشغيل المسح الشامل والترتيب اللحظي 🚀"):
        fresh_cross_results = []
        bottom_accumulation_results = []
        short_term_trading = []
        long_term_investment = []
        
        with st.spinner("جاري جلب البيانات من السوق..."):
            tickers_list = list(ALL_STOCKS.values())
            all_data, failed_tickers = fetch_batch_data(tuple(tickers_list), period="60d")

            for name, ticker in ALL_STOCKS.items():
                if ticker not in all_data:
                    continue
                try:
                    stock_df = all_data[ticker].dropna(how='all')
                    if stock_df.empty or len(stock_df) < 25:
                        continue
                        
                    stock_df = calculate_indicators(stock_df)
                    row = stock_df.iloc[-1]
                    p = float(row['Close'])
                    r = float(row['RSI_14'])
                    m = float(row['MFI_14'])
                    
                    data_entry = {
                        "اسم الشركة": name,
                        "الرمز": ticker,
                        f"السعر": round(p, 2),
                        "RSI": round(r, 1),
                        "MFI": round(m, 1)
                    }
                    long_term_investment.append(data_entry)
                except Exception:
                    continue
            
            st.success("تم الانتهاء من الفحص!")
            
            if long_term_investment:
                st.dataframe(pd.DataFrame(long_term_investment), use_container_width=True)
            else:
                st.error("❌ لم يتم استرجاع أي بيانات صالحة من الأسهم المحددة لهذا السوق عبر المصدر الخارجي.")
