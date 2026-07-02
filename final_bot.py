import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np
import math

# إعدادات الصفحة
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

# قاموس البيانات الأساسية (يجب عليك تحديث الأرقام هنا من تقارير الأسهم)
BASIC_FUNDAMENTALS = {
    "السويدي إليكتريك": {"BV": 15.5, "EPS": 4.2},
    "البنك التجاري الدولي": {"BV": 45.0, "EPS": 8.5},
    "مجموعة طلعت مصطفى": {"BV": 12.0, "EPS": 2.1},
    # أضف باقي الأسهم بنفس هذا التنسيق
}

def calculate_fair_value(name):
    """حساب القيمة العادلة بناءً على معادلتك: جذر(BV * EPS * 22.5)"""
    if name in BASIC_FUNDAMENTALS:
        data = BASIC_FUNDAMENTALS[name]
        return round(math.sqrt(data['BV'] * data['EPS'] * 22.5), 2)
    return None

st.title("🦅 قناص البورصة المصرية (النسخة المتكاملة + القيمة العادلة)")

# إعدادات التليجرام (كما هي)
default_token = st.secrets.get("TELEGRAM_TOKEN", "")
default_chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_TOKEN = st.sidebar.text_input("Token البوت:", value=default_token, type="password")
TELEGRAM_CHAT_ID = st.sidebar.text_input("Chat ID:", value=default_chat_id)

def send_telegram_alert(message):
    token = TELEGRAM_TOKEN if TELEGRAM_TOKEN else default_token
    chat_id = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else default_chat_id
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        try: requests.post(url, json=payload)
        except Exception as e: st.sidebar.error(f"فشل إرسال التنبيه: {e}")

# القائمة (كما هي)
ALL_EGX_STOCKS = {
    "السويدي إليكتريك": "SWDY.CA", "البنك التجاري الدولي": "COMI.CA", "مجموعة طلعت مصطفى": "TMGH.CA"
    # ... أكمل باقي الأسهم من كودك الأصلي
}

def calculate_indicators(df):
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(-1)
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    # ... باقي المؤشرات
    df['Vol_MA10'] = df['Volume'].rolling(window=10).mean()
    return df

# (باقي الكود كما هو حتى جزء الـ data_entry داخل المسح)

# التعديل هنا داخل loop الفرز في tab2:
# ----------------------------------------------------
# داخل حلقة الـ for الخاصة بالأسهم في الـ tab2:
                    
                   # هذه هي المسافات الصحيحة، تأكد من مطابقتها في ملفك
                    fair_val = calculate_fair_value(name)
                    
                    data_entry = {
                        "النقاط الفنية": round(momentum_score, 1),
                        "اسم الشركة": name,
                        "السعر الحالي": round(p, 2),
                        "القيمة العادلة": fair_val if fair_val else "غير متاحة",
                        "حالة السعر": "لقطة (أرخص)" if (fair_val and p < fair_val) else "مبالغ فيه/عادل",
                        "EMA9": round(ema9, 2),
                        "EMA21": round(ema21, 2)
                    }
                    results.append(data_entry)
# ----------------------------------------------------

# (باقي الكود يظل كما هو مع عرض الجداول)
