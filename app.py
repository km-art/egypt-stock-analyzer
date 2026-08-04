import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# ==========================================
# 1. إعدادات الصفحة والتنسيق
# ==========================================
st.set_page_config(page_title="بورصي - التحليل المتكامل", layout="wide", page_icon="📈")

# تنسيق CSS ليكون مثل تصميم الصورة التي أرسلتها
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Tajawal', sans-serif;
        text-align: right;
        direction: rtl;
    }
    .card-number { font-size: 32px; font-weight: bold; margin: 10px 0; }
    .box-buy { background-color: #4CAF50; color: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    .box-sell { background-color: #f44336; color: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    .box-hold { background-color: #FFC107; color: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    .stock-price { font-size: 24px; font-weight: bold; margin: 10px 0; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. دوال التحليل الفني والمالي (مأخوذة من كودك المتقدم)
# ==========================================
def calculate_indicators(df):
    """حساب المؤشرات الفنية RSI, EMA, Bollinger Bands"""
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

def get_stock_analysis(ticker_symbol):
    """تجلب البيانات وتحلل السهم"""
    try:
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period="60d") # 60 يوم للتحليل
        if hist.empty:
            return None
        
        df = calculate_indicators(hist)
        last = df.iloc[-1]
        
        price = round(last['Close'], 2)
        rsi = round(last['RSI_14'], 1)
        ema9 = round(last['EMA9'], 2)
        ema21 = round(last['EMA21'], 2)
        volume = int(last['Volume'])
        vol_ma10 = int(df['Volume'].rolling(10).mean().iloc[-1])
        
        # حساب التوصية بناءً على الكود المتقدم
        recommendation = "🟡 انتظار"
        rec_color = "box-hold"
        target_price = round(price * 1.03, 2) # افتراضي
        stop_loss = round(price * 0.97, 2)   # افتراضي
        
        if rsi < 35:
            recommendation = "🛒 تجميع (منطقة رخيصة)"
            rec_color = "box-buy"
            target_price = round(price * 1.05, 2)
            stop_loss = round(price * 0.95, 2)
        elif rsi > 75 or price >= last['Upper_Band']:
            recommendation = "🔴 بيع/جني أرباح (تشبع شرائي)"
            rec_color = "box-sell"
            target_price = price
            stop_loss = price
        elif ema9 > ema21 and 40 < rsi < 65:
            recommendation = "🟢 شراء (اتجاه صاعد)"
            rec_color = "box-buy"
            target_price = round(price * 1.05, 2)
            stop_loss = round(price * 0.98, 2)
            
        return {
            "price": price, "rsi": rsi, "ema9": ema9, "ema21": ema21,
            "volume": volume, "vol_ma10": vol_ma10,
            "recommendation": recommendation, "rec_color": rec_color,
            "target": target_price, "stop": stop_loss
        }
    except Exception as e:
        return None

# ==========================================
# 3. عرض الواجهة (الـ Dashboard)
# ==========================================
st.title("📊 بورصي - التحليل اليومي")
st.caption(f"آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
st.write("---")

# قائمة الأسهم التي سنحللها (يمكنك التعديل عليها)
stocks_to_scan = ["COMI.CA", "TMGH.CA", "ESRS.CA", "SWDY.CA", "EGAL.CA"]

st.subheader("🏆 أفضل توصيات اليوم (بناءً على التحليل الفني)")
cols = st.columns(len(stocks_to_scan))

for i, ticker in enumerate(stocks_to_scan):
    data = get_stock_analysis(ticker)
    with cols[i]:
        if data:
            # عرض الصندوق حسب نوع التوصية
            st.markdown(f"""
            <div class='{data['rec_color']}'>
                <h3 style='margin:0;'>{ticker.replace('.CA', '')}</h3>
                <small>{data['recommendation']}</small>
                <div class='stock-price'>{data['price']} ج.م</div>
                <div>🎯 الهدف: {data['target']} ج.م</div>
                <div style='background: rgba(0,0,0,0.1); padding: 5px; border-radius: 5px; margin-top: 10px;'>
                    ⛔ وقف خسارة: {data['stop']} ج.م
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # عرض مؤشرات صغيرة تحت الصندوق
            st.caption(f"RSI: {data['rsi']} | فوليوم: {data['volume']:,}")
        else:
            st.error(f"تعذر جلب بيانات {ticker}")

st.write("---")
st.info("💡 التحليل يعتمد على مؤشرات القوة النسبية (RSI) والمتوسطات المتحركة (EMA). هذه أداة مساعدة وليست توصية استثمارية ملزمة.")
