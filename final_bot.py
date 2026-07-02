import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np
import math

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

st.title("🦅 قناص البورصة المصرية (النسخة المتكاملة المقفلة ضد المخاطر)")

# --- بيانات أساسية لحساب القيمة العادلة ---
BASIC_FUNDAMENTALS = {
    "السويدي إليكتريك": {"BV": 15.5, "EPS": 4.2}, "البنك التجاري الدولي": {"BV": 45.0, "EPS": 8.5},
    "مجموعة طلعت مصطفى": {"BV": 12.0, "EPS": 2.1}, "مصرف أبوظبي الإسلامي": {"BV": 25.0, "EPS": 5.5}
    # يمكنك إضافة باقي الأسهم بنفس هذا التنسيق
}

def calculate_fair_value(name):
    """حساب القيمة العادلة بناءً على معادلة: جذر(BV * EPS * 22.5)"""
    if name in BASIC_FUNDAMENTALS:
        data = BASIC_FUNDAMENTALS[name]
        return round(math.sqrt(data['BV'] * data['EPS'] * 22.5), 2)
    return None

# إعدادات التنبيهات
default_token = st.secrets.get("TELEGRAM_TOKEN", "")
default_chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
st.sidebar.header("⚙️ إعدادات إشعارات الموبايل")
TELEGRAM_TOKEN = st.sidebar.text_input("أدخل Token البوت:", value=default_token, type="password")
TELEGRAM_CHAT_ID = st.sidebar.text_input("أدخل Chat ID الخاص بك:", value=default_chat_id)

def send_telegram_alert(message):
    token = TELEGRAM_TOKEN if TELEGRAM_TOKEN else default_token
    chat_id = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else default_chat_id
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload)

# القائمة الكاملة لرموز أسهم السوق المصري
ALL_EGX_STOCKS = {
    "السويدي إليكتريك": "SWDY.CA", "البنك التجاري الدولي": "COMI.CA", "مصرف أبوظبي الإسلامي": "ADIB.CA",
    "مجموعة طلعت مصطفى": "TMGH.CA", "فوري للمدفوعات الإلكترونية": "FWRY.CA", "بالم هيلز للتعمير": "PHDC.CA"
    # تم تقليص القائمة للعرض، أضف باقي الأسهم هنا
}
ALL_EGX_STOCKS = dict(sorted(ALL_EGX_STOCKS.items()))

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
    return df

tab1, tab2 = st.tabs(["🔍 فحص سهم تفصيلي", "🏆 مسح وترتيب السوق الاحترافي"])

with tab2:
    if st.button("تشغيل الفرز والترتيب الاحترافي اللحظي 🚀"):
        fresh_cross_results, bottom_accumulation_results, short_term_trading, long_term_investment = [], [], [], []
        tickers_list = list(ALL_EGX_STOCKS.values())
        all_data = yf.download(tickers_list, period="60d", progress=False, group_by='ticker')
        
        for name, ticker in ALL_EGX_STOCKS.items():
            try:
                stock_df = all_data[ticker].dropna()
                stock_df = calculate_indicators(stock_df)
                row = stock_df.iloc[-1]
                p = float(row['Close'])
                
                # إضافة القيمة العادلة للنتائج
                fair_val = calculate_fair_value(name)
                
                data_entry = {
                    "اسم الشركة": name,
                    "السعر الحالي": round(p, 2),
                    "القيمة العادلة": fair_val if fair_val else "N/A",
                    "حالة السعر": "لقطة (أرخص)" if (fair_val and p < fair_val) else "مبالغ فيه/عادل",
                    "الرمز": ticker
                }
                
                # ... (باقي منطق التصنيف والفرز كما في الكود الأصلي)
                fresh_cross_results.append(data_entry) # مثال إلحاق
            except: continue
            
        st.dataframe(pd.DataFrame(fresh_cross_results))
