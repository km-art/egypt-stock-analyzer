import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np
import math

# إعدادات الصفحة
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

# 1. التعريفات الأساسية في الأعلى
ALL_EGX_STOCKS = {
    "السويدي إليكتريك": "SWDY.CA", "البنك التجاري الدولي": "COMI.CA", 
    "مجموعة طلعت مصطفى": "TMGH.CA", "مصرف أبوظبي الإسلامي": "ADIB.CA"
}

BASIC_FUNDAMENTALS = {
    "السويدي إليكتريك": {"BV": 15.5, "EPS": 4.2},
    "البنك التجاري الدولي": {"BV": 45.0, "EPS": 8.5},
    "مجموعة طلعت مصطفى": {"BV": 12.0, "EPS": 2.1},
    "مصرف أبوظبي الإسلامي": {"BV": 25.0, "EPS": 5.5}
}

# 2. الدوال
def calculate_fair_value(name):
    if name in BASIC_FUNDAMENTALS:
        data = BASIC_FUNDAMENTALS[name]
        return round(math.sqrt(data['BV'] * data['EPS'] * 22.5), 2)
    return None

def calculate_indicators(df):
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(-1)
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['Vol_MA10'] = df['Volume'].rolling(window=10).mean()
    return df

st.title("🦅 قناص البورصة المصرية (النسخة المتكاملة والمصححة)")

# 3. قسم الفرز
if st.button("تشغيل الفرز والترتيب الاحترافي اللحظي 🚀"):
    results = []
    tickers_list = list(ALL_EGX_STOCKS.values())
    
    with st.spinner("جاري المسح..."):
        all_data = yf.download(tickers_list, period="60d", progress=False, group_by='ticker')
        
        for name, ticker in ALL_EGX_STOCKS.items():
            try:
                # التأكد من التعامل مع البيانات سواء سهم واحد أو أكثر
                stock_df = all_data[ticker] if len(tickers_list) > 1 else all_data
                stock_df = stock_df.dropna(how='all')
                
                if stock_df.empty or len(stock_df) < 25: continue
                
                stock_df = calculate_indicators(stock_df)
                row = stock_df.iloc[-1]
                p = float(row['Close'])
                
                if float(row['Volume']) < 50000: continue
                
                fair_val = calculate_fair_value(name)
                
                data_entry = {
                    "اسم الشركة": name,
                    "السعر الحالي": round(p, 2),
                    "القيمة العادلة": fair_val if fair_val else "غير متاحة",
                    "حالة السعر": "لقطة (أرخص)" if (fair_val and p < fair_val) else "مبالغ فيه/عادل"
                }
                results.append(data_entry)
            except Exception:
                continue
                
    if results:
        st.dataframe(pd.DataFrame(results), use_container_width=True)
    else:
        st.warning("لم يتم العثور على بيانات مطابقة للشروط.")
