import streamlit as st
import investpy
import pandas as pd
from datetime import datetime

# ==========================================
# 1. إعدادات الصفحة والتنسيق
# ==========================================
st.set_page_config(page_title="بورصي - التحليل المباشر", layout="wide", page_icon="📈")

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
# 2. دوال لجلب البيانات الحقيقية باستخدام investpy
# ==========================================
def get_egx_price(symbol):
    """ تجلب السعر الحقيقي للأسهم المصرية """
    try:
        # استخدام investpy لجلب السعر الحالي
        data = investpy.get_stock_historical_data(stock=symbol, country='egypt', from_date='01/01/2020', to_date=datetime.now().strftime('%d/%m/%Y'))
        if not data.empty:
            return round(data['Close'].iloc[-1], 2)
        return None
    except Exception as e:
        # طباعة الخطأ في السيرفر عشان نعرف السبب (اختياري)
        print(f"Error fetching {symbol}: {e}")
        return None

# ==========================================
# 3. جلب البيانات وتجهيزها
# ==========================================
stocks_to_show = ["EFTE", "TMG", "COMI"]
stock_data = {}

# نمر على كل سهم ونجيب سعره
for symbol in stocks_to_show:
    with st.spinner(f'جاري تحديث سعر {symbol}...'):
        price = get_egx_price(symbol)
        if price:
            stock_data[symbol] = price
        else:
            stock_data[symbol] = None

# ==========================================
# 4. عرض الواجهة
# ==========================================
st.markdown(f"<h1 style='text-align: center; color: #2c3e50;'>📊 بورصي - {datetime.now().strftime('%d/%m/%Y')}</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>مؤشر البورصة المصرية EGX30: يتم التحديث...</p>", unsafe_allow_html=True)
st.write("---")

# عرض الإحصائيات
col1, col2, col3, col4 = st.columns(4)
with col1: st.markdown(f"<div style='text-align:center;'><h4>⏳ انتظار</h4><div class='card-number' style='color: #3498db;'>2</div></div>", unsafe_allow_html=True)
with col2: st.markdown(f"<div style='text-align:center;'><h4>🔻 توصيات بيع</h4><div class='card-number' style='color: #e74c3c;'>1</div></div>", unsafe_allow_html=True)
with col3: st.markdown(f"<div style='text-align:center;'><h4>🟡 توصيات شراء</h4><div class='card-number' style='color: #f1c40f;'>3</div></div>", unsafe_allow_html=True)
with col4: st.markdown(f"<div style='text-align:center;'><h4>🟢 الأسهم الآمنة</h4><div class='card-number' style='color: #2ecc71;'>8</div></div>", unsafe_allow_html=True)

st.write("---")
st.subheader("📉 التوصيات اليومية (بيانات حقيقية)")

cols_recommendations = st.columns(3)

# --- EFTE ---
with cols_recommendations[0]:
    price = stock_data.get("EFTE")
    if price:
        st.markdown(f"""
        <div class='box-hold'>
            <h3 style='margin:0;'>EFTE</h3>
            <small>انتظار</small>
            <div class='stock-price'>{price} ج.م</div>
            <div class='stock-target'>🎯 الهدف: {round(price * 1.03, 2)} ج.م</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<div class='box-hold'><h3>EFTE</h3><small>انتظار</small><p>جاري التحميل...</p></div>", unsafe_allow_html=True)

# --- TMG ---
with cols_recommendations[1]:
    price = stock_data.get("TMG")
    if price:
        st.markdown(f"""
        <div class='box-buy'>
            <h3 style='margin:0;'>TMG</h3>
            <small>شراء</small>
            <div class='stock-price'>{price} ج.م</div>
            <div class='stock-target'>🎯 الهدف: {round(price * 1.05, 2)} ج.م</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<div class='box-buy'><h3>TMG</h3><small>شراء</small><p>جاري التحميل...</p></div>", unsafe_allow_html=True)

# --- COMI ---
with cols_recommendations[2]:
    price = stock_data.get("COMI")
    if price:
        st.markdown(f"""
        <div class='box-buy'>
            <h3 style='margin:0;'>COMI</h3>
            <small>شراء قوي</small>
            <div class='stock-price'>{price} ج.م</div>
            <div class='stock-target'>🎯 الهدف: {round(price * 1.05, 2)} ج.م</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<div class='box-buy'><h3>COMI</h3><small>شراء قوي</small><p>جاري التحميل...</p></div>", unsafe_allow_html=True)

st.write("---")
st.caption("⚠️ تنبيه: الأسعار الحقيقية يتم جلبها من بيانات السوق. التوصيات لغرض تعليمي فقط.")
