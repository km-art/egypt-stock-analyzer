import time
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

st.title("🦅 قناص البورصة المصرية (النسخة المحدثة: معايير جراهام)")
st.write("تم دمج قاعدة جراهام (Intrinsic Value) وفلتر P/E < 15 للأسهم الرخيصة.")

# --- دوال مساعدة ---

def get_fundamentals(ticker_symbol):
    """جلب البيانات المالية لحساب معادلة جراهام"""
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        pe = info.get('trailingPE')
        eps = info.get('trailingEps')
        bvps = info.get('bookValue')
        return pe, eps, bvps
    except:
        return None, None, None

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

# إعدادات عامة
BATCH_SIZE = 30
BATCH_DELAY = 1.5
CROSS_LOOKBACK = 3

# القائمة (مختصرة للنسخ، استبدلها بالكاملة الخاصة بك)
ALL_EGX_STOCKS = {
    "Egyptian Resorts Company": "EGTS.CA", "Egyptians for Housing & Development Co.": "EHDR.CA",
    "Pioneers Properties": "PRDC.CA", "Beltone": "BTFH.CA", "Fawry": "FWRY.CA",
    "Abu Qir Fertilizers": "ABUK.CA", "Telecom Egypt": "ETEL.CA", "Commercial Intl Bank": "COMI.CA"
    # أضف باقي القائمة هنا كما في ملفك الأصلي...
}
ALL_EGX_STOCKS = dict(sorted(ALL_EGX_STOCKS.items(), key=lambda kv: kv[1]))

@st.cache_data(ttl=300, show_spinner=False)
def fetch_batch_data(tickers_tuple, period="60d"):
    all_frames = {}
    tickers = list(tickers_tuple)
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        data = yf.download(batch, period=period, progress=False, group_by='ticker')
        for t in batch:
            df_t = data[t] if len(batch) > 1 else data
            if df_t is not None and not df_t.dropna(how='all').empty:
                all_frames[t] = df_t
        time.sleep(BATCH_DELAY)
    return all_frames

# --- التطبيق ---
tab1, tab2 = st.tabs(["🔍 فحص سهم", "🏆 مسح السوق المتقدم"])

with tab2:
    st.subheader("⚙️ أدوات المسح الاحترافي")
    
    # خيار مسح جراهام الجديد
    if st.button("🚀 مسح الفرص الاستثمارية (قاعدة جراهام + P/E < 15)"):
        graham_results = []
        tickers_list = list(ALL_EGX_STOCKS.values())
        all_data = fetch_batch_data(tuple(tickers_list), period="60d")
        
        with st.spinner("جاري فحص البيانات المالية لكل سهم..."):
            for name, ticker in ALL_EGX_STOCKS.items():
                if ticker not in all_data: continue
                
                # جلب البيانات المالية
                pe, eps, bvps = get_fundamentals(ticker)
                
                # جلب السعر الحالي
                df = calculate_indicators(all_data[ticker].dropna(how='all'))
                price = float(df.iloc[-1]['Close'])
                
                if pe and eps and bvps:
                    graham_val = (22.5 * eps * bvps)**0.5
                    
                    # شرط جراهام: السعر الحالي < القيمة العادلة + شرط P/E < 15
                    if pe < 15 and price < graham_val:
                        graham_results.append({
                            "الشركة": name,
                            "السعر الحالي": round(price, 2),
                            "P/E": round(pe, 2),
                            "القيمة العادلة (جراهام)": round(graham_val, 2)
                        })
        
        if graham_results:
            st.success(f"تم العثور على {len(graham_results)} فرصة استثمارية مطابقة للمعايير:")
            st.dataframe(pd.DataFrame(graham_results))
        else:
            st.warning("لم يتم العثور على أسهم تطابق شروط جراهام و P/E في الوقت الحالي.")

    # المسح الفني (القديم)
    if st.button("📊 تشغيل المسح الفني اللحظي"):
        # (باقي كود المسح الفني الخاص بك...)
        st.info("تم تشغيل المسح الفني...")

with tab1:
    st.write("استخدم تبويب مسح السوق للفرص الاستثمارية.")
