import streamlit as st
import yfinance as yf
import pandas as pd

# إعدادات الصفحة المظهر العام
st.set_page_config(page_title="محلل الأسهم الذكي 📈", layout="centered")

st.title("📊 نظام الفحص الفني والزخم الفوري للأسهم")
st.write("أدخل رمز السهم (مثال: `COMI.CA` للسوق المصري، أو `SPY` للسوق الأمريكي) لتحليله فوراً:")

# صندوق إدخال اسم السهم
ticker = st.text_input("رمز السهم:", value="COMI.CA").strip().upper()

if st.button("بدء التحليل الفوري ⚡"):
    with st.spinner("جاري سحب البيانات اللحظية وحساب المؤشرات..."):
        try:
            # 1. جلب بيانات السهم (آخر 100 يوم لتغطية المتوسطات)
            stock = yf.Ticker(ticker)
            df = stock.history(period="100d")
            
            if df.empty:
                st.error("لم نتمكن من العثور على بيانات لهذا الرمز. تأكد من كتابته بشكل صحيح (مثال: COMI.CA).")
            else:
                # 2. حساب المؤشرات الفنية
                # المتوسطات المتحركة الأسية
                df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
                df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
                
                # مؤشر القوة النسبية RSI_14
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                df['RSI_14'] = 100 - (100 / (1 + rs))
                
                # حدود بولينجر Bollinger Bands
                df['MA20'] = df['Close'].rolling(window=20).mean()
                df['STD20'] = df['Close'].rolling(window=20).std()
                df['Upper_Band'] = df['MA20'] + (2 * df['STD20'])
                df['Lower_Band'] = df['MA20'] - (2 * df['STD20'])
                
                # جلب آخر قيم محدثة (اليومية)
                last_row = df.iloc[-1]
                price = last_row['Close']
                ema9 = last_row['EMA9']
                ema21 = last_row['EMA21']
                rsi = last_row['RSI_14']
                upper = last_row['Upper_Band']
                lower = last_row['Lower_Band']
                
                # 3. اتخاذ القرار بناءً على الخوارزمية
                if ema9 > ema21 and rsi < 70 and price < upper:
                    decision = "STRONG BUY ⚡"
                    color = "#2ecc71"  # أخضر
                elif price >= upper or rsi >= 70:
                    decision = "SELL / TAKE PROFIT 🚨"
                    color = "#e74c3c"  # أحمر
                else:
                    decision = "HOLD ✋ (مراقبة)"
                    color = "#f39c12"  # برتقالي
                
                # 4. عرض النتائج للمستخدم في الواجهة
                st.markdown("---")
                st.subheader(f"نتائج تحليل السهم: {ticker}")
                
                # عرض القرار في كارت ملون كبير
                st.markdown(
                    f'<div style="background-color:{color}; padding:20px; border-radius:10px; text-align:center;">'
                    f'<h2 style="color:white; margin:0;">القرار الحالي: {decision}</h2>'
                    f'</div>', 
                    unsafe_allow_html=True
                )
                
                # عرض الأرقام الفنية في أعمدة منظمة
                st.markdown("<br>", unsafe_allow_html=True)
                col1, col2, col3 = st.columns(3)
                col1.metric("السعر الحالي", f"{price:.2f}")
                col2.metric("مؤشر RSI_14", f"{rsi:.2f}")
                col3.metric("مساحة الـ Upper Band", f"{upper:.2f}")
                
                col4, col5 = st.columns(2)
                col4.metric("المتوسط السريع EMA9", f"{ema9:.2f}")
                col5.metric("المتوسط البطيء EMA21", f"{ema21:.2f}")
                
        except Exception as e:
            st.error(f"حدث خطأ أثناء جلب البيانات: {e}")