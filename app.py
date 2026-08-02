
import streamlit as st

# ==========================================
# 1. إعدادات الصفحة الأساسية (لازم تكون أول سطر)
# ==========================================
st.set_page_config(page_title="بورصي - التحليل اليومي", layout="wide", page_icon="📈")

# ==========================================
# 2. تنسيق CSS (عشان يبقى شبه الصورة)
# ==========================================
st.markdown("""
<style>
    /* تنسيق الخط العربي */
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Tajawal', sans-serif;
        text-align: right;
        direction: rtl;
    }
    
    /* تنسيق البطاقات الأربعة فوق */
    .card-container {
        display: flex;
        justify-content: space-between;
        gap: 20px;
        margin-bottom: 30px;
    }
    .card {
        background-color: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        flex: 1;
        text-align: center;
        border-top: 4px solid #f0f2f6;
    }
    .card-number {
        font-size: 32px;
        font-weight: bold;
        margin: 10px 0;
    }
    
    /* تنسيق صناديق التوصيات (الأسهم) */
    .box-buy { background-color: #4CAF50; color: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    .box-sell { background-color: #f44336; color: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    .box-hold { background-color: #FFC107; color: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    
    .stock-price { font-size: 24px; font-weight: bold; margin: 10px 0; }
    .stock-target { font-size: 14px; opacity: 0.9; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. شريط العنوان (Header)
# ==========================================
st.markdown("<h1 style='text-align: center; color: #2c3e50;'>📊 بورصي - التوصيات اليومية</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>آخر تحديث: اليوم 09:30 م</p>", unsafe_allow_html=True)
st.write("---")

# ==========================================
# 4. البطاقات العلوية (إحصائيات السوق)
# ==========================================
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("<div class='card'><h4>⏳ انتظار</h4><div class='card-number' style='color: #3498db;'>2</div></div>", unsafe_allow_html=True)
with col2:
    st.markdown("<div class='card'><h4>🔻 توصيات بيع</h4><div class='card-number' style='color: #e74c3c;'>1</div></div>", unsafe_allow_html=True)
with col3:
    st.markdown("<div class='card'><h4>🟡 توصيات شراء</h4><div class='card-number' style='color: #f1c40f;'>3</div></div>", unsafe_allow_html=True)
with col4:
    st.markdown("<div class='card'><h4>🟢 الأسهم الآمنة</h4><div class='card-number' style='color: #2ecc71;'>8</div></div>", unsafe_allow_html=True)

st.write("---")

# ==========================================
# 5. قسم التوصيات اليومية (الجزء السفلي)
# ==========================================
st.subheader("📉 التوصيات اليومية")

cols_recommendations = st.columns(3)

# --- السهم الأول: EFTE (انتظار - أصفر) ---
with cols_recommendations[0]:
    st.markdown("""
    <div class='box-hold'>
        <h3 style='margin:0;'>EFTE</h3>
        <small>انتظار</small>
        <div class='stock-price'>62.27 ج.م</div>
        <div class='stock-target'>🎯 الهدف: 64.17 ج.م</div>
        <div style='background: rgba(0,0,0,0.1); padding: 5px; border-radius: 5px; margin-top: 10px;'>
            وقف خسارة: 60.43 ج.م 🔴
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- السهم الثاني: TMG (شراء - أخضر) ---
with cols_recommendations[1]:
    st.markdown("""
    <div class='box-buy'>
        <h3 style='margin:0;'>TMG</h3>
        <small>شراء</small>
        <div class='stock-price'>45.21 ج.م</div>
        <div class='stock-target'>🎯 الهدف: 47.46 ج.م</div>
        <div style='background: rgba(255,255,255,0.2); padding: 5px; border-radius: 5px; margin-top: 10px;'>
            وقف خسارة: 43.39 ج.م 🔴
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- السهم الثالث: COMI (شراء - أخضر) ---
with cols_recommendations[2]:
    st.markdown("""
    <div class='box-buy'>
        <h3 style='margin:0;'>COMI</h3>
        <small>شراء قوي</small>
        <div class='stock-price'>85.48 ج.م</div>
        <div class='stock-target'>🎯 الهدف: 89.78 ج.م</div>
        <div style='background: rgba(255,255,255,0.2); padding: 5px; border-radius: 5px; margin-top: 10px;'>
            وقف خسارة: 82.08 ج.م 🔴
        </div>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 6. تذييل الصفحة
# ==========================================
st.write("---")
st.caption("⚠️ تنبيه: هذه التوصيات لغرض تعليمي وتجريبي فقط. يرجى مراجعة مستشار مالي قبل اتخاذ أي قرار استثماري.")
