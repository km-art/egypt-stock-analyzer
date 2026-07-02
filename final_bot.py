import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np
import math

# إعدادات الصفحة
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

# قاموس البيانات الأساسية
BASIC_FUNDAMENTALS = {
    "السويدي إليكتريك": {"BV": 15.5, "EPS": 4.2},
    "البنك التجاري الدولي": {"BV": 45.0, "EPS": 8.5},
    "مجموعة طلعت مصطفى": {"BV": 12.0, "EPS": 2.1},
}

def calculate_fair_value(name):
    """حساب القيمة العادلة"""
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

# --- الجزء الخاص بالمعالجة داخل الـ loop (استبدله بالكامل في ملفك) ---
# تأكد أن هذا الجزء داخل الـ tab2 وفي نفس مستوى الـ try:
                try:
                    stock_df = all_data[ticker].dropna(how='all') if len(tickers_list) > 1 else all_data
                    if stock_df.empty or len(stock_df) < 25: continue
                    
                    stock_df = calculate_indicators(stock_df)
                    row = stock_df.iloc[-1]
                    prev_row = stock_df.iloc[-4]
                    
                    p = float(row['Close'])
                    # ... (باقي تعريف المتغيرات الخاص بك)
                    
                    if float(row['Volume']) < 3000000: continue
                    
                    # هذا هو الجزء الذي يسبب الخطأ، تأكد من وجوده تماماً هكذا:
                    fair_val = calculate_fair_value(name)
                    
                    data_entry = {
                        "اسم الشركة": name,
                        "السعر الحالي": round(p, 2),
                        "القيمة العادلة": fair_val if fair_val else "غير متاحة",
                        "حالة السعر": "لقطة (أرخص)" if (fair_val and p < fair_val) else "مبالغ فيه/عادل",
                        "EMA9": round(float(row['EMA9']), 2),
                        "EMA21": round(float(row['EMA21']), 2)
                    }
                    results.append(data_entry)
                    
                except Exception as e:
                    continue
# -------------------------------------------------------------------
