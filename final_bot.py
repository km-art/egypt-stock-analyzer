import streamlit as st
import yfinance as yf
import pandas as pd
import math

# --- 1. الإعدادات والتعريفات ---
ALL_EGX_STOCKS = {"السويدي إليكتريك": "SWDY.CA", "البنك التجاري الدولي": "COMI.CA", "مجموعة طلعت مصطفى": "TMGH.CA", "مصرف أبوظبي الإسلامي": "ADIB.CA"}
BASIC_FUNDAMENTALS = {"السويدي إليكتريك": {"BV": 15.5, "EPS": 4.2}, "البنك التجاري الدولي": {"BV": 45.0, "EPS": 8.5}, "مجموعة طلعت مصطفى": {"BV": 12.0, "EPS": 2.1}, "مصرف أبوظبي الإسلامي": {"BV": 25.0, "EPS": 5.5}}

def calculate_fair_value(name):
    if name in BASIC_FUNDAMENTALS:
        data = BASIC_FUNDAMENTALS[name]
        return round(math.sqrt(data['BV'] * data['EPS'] * 22.5), 2)
    return None

def calculate_indicators(df):
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['RSI_14'] = 50 # مثال: يتم استبدالها بمعادلة الـ RSI الفعلية
    return df

# --- 2. واجهة المستخدم والفرز ---
if st.button("تشغيل المسح الشامل (4 أقسام) 🚀"):
    fresh_cross, accumulation, fast_trade, long_term = [], [], [], []
    all_data = yf.download(list(ALL_EGX_STOCKS.values()), period="60d", group_by='ticker')
    
    for name, ticker in ALL_EGX_STOCKS.items():
        try:
            df = all_data[ticker].dropna()
            df = calculate_indicators(df)
            row = df.iloc[-1]
            p, r = float(row['Close']), float(row['RSI_14'])
            fv = calculate_fair_value(name)
            
            # تجهيز بيانات السهم
            entry = {
                "الشركة": name, "السعر": p, "القيمة العادلة": fv if fv else "N/A",
                "الحالة": "لقطة (أرخص)" if (fv and p < fv) else "عادل/مبالغ"
            }
            
            # منطق الأربعة أقسام
            if r < 52: fresh_cross.append(entry)
            elif r < 35: accumulation.append(entry)
            elif p > row['EMA9']: fast_trade.append(entry)
            else: long_term.append(entry)
        except: continue

    # عرض الأقسام
    st.subheader("📊 1. أسهم إشارات جديدة"); st.table(pd.DataFrame(fresh_cross))
    st.subheader("💰 2. أسهم التجميع"); st.table(pd.DataFrame(accumulation))
    st.subheader("⚡ 3. التداول السريع"); st.table(pd.DataFrame(fast_trade))
    st.subheader("💎 4. الاستثمار طويل الأجل"); st.table(pd.DataFrame(long_term))
