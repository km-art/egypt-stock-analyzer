import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="محلل الأسهم الذكي المطور 📈", layout="wide")

st.title("🚀 النظام المتكامل للفحص الفني وزحم السوق المصري")
st.write("مرحباً بك! يمكنك الآن فحص سهم معين بالتفصيل أو عمل مسح شامل للسوق.")

# قائمة أشهر الأسهم المصرية مسبقة التعريف لتسهيل الاختيار
EGYPTIAN_STOCKS = {
    "السويدي إليكتريك (SWDY)": "SWDY.CA",
    "البنك التجاري الدولي (COMI)": "COMI.CA",
    "الجيزة العامة للمقاولات (GGCC)": "GGCC.CA",
    "جهينة للصناعات الغذائية (JUFO)": "JUFO.CA",
    "طلعت مصطفى (TMGH)": "TMGH.CA",
    "فاركو للأدوية (PHAR)": "PHAR.CA",
    "سيدي كرير للبتروكيماويات (SKPC)": "SKPC.CA",
    "طاقة عربية (TAQA)": "TAQA.CA",
    "مصر للألومنيوم (EGAL)": "EGAL.CA",
    "إعمار مصر (EMFD)": "EMFD.CA"
}

# تقسيم التطبيق إلى تبويبين (Tabs) لترتيب الميزات
tab1, tab2 = st.tabs(["🔍 فحص سهم تفصيلي + رسم بياني", "📊 مسح جماعي للسوق فوري"])

# --- التبويب الأول: فحص سهم تفصيلي ---
with tab1:
    st.subheader("اختر أو اكتب رمز السهم لتحليله ورسم بياناته")
    
    col_input1, col_input2 = st.columns([2, 1])
    with col_input1:
        selected_stock = st.selectbox("اختر من الأسهم الشائعة:", list(EGYPTIAN_STOCKS.keys()))
        ticker_input = EGYPTIAN_STOCKS[selected_stock]
    with col_input2:
        manual_ticker = st.text_input("أو اكتب رمز آخر يدوياً:", value="").strip().upper()
        if manual_ticker:
            ticker_input = manual_ticker

    if st.button("تحليل السهم ورسم المنحنى ⚡"):
        with st.spinner("جاري جلب البيانات وحساب المؤشرات الفنية..."):
            try:
                # استخدام جلب البيانات مع إلغاء تجميع العناوين المتعددة لضمان استقرار الجداول
                df = yf.download(ticker_input, period="100d", progress=False, group_by='ticker')
                
                if df.empty:
                    st.error("لم نتمكن من العثور على بيانات لهذا الرمز.")
                else:
                    # معالجة استواء الأعمدة لو كانت مجمعة تلو اسم السهم
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.dropdown(0) if hasattr(df.columns, 'dropdown') else df.columns.get_level_values(-1)
                    
                    # حساب المؤشرات
                    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
                    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
                    
                    delta = df['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    df['RSI_14'] = 100 - (100 / (1 + rs))
                    
                    df['MA20'] = df['Close'].rolling(window=20).mean()
                    df['STD20'] = df['Close'].rolling(window=20).std()
                    df['Upper_Band'] = df['MA20'] + (2 * df['STD20'])
                    df['Lower_Band'] = df['MA20'] - (2 * df['STD20'])
                    
                    last_row = df.iloc[-1]
                    
                    # استخراج القيم الفردية بدقة متناهية لمنع تداخل الجداول
                    price = float(last_row['Close'].iloc[0]) if isinstance(last_row['Close'], pd.Series) else float(last_row['Close'])
                    ema9 = float(last_row['EMA9'].iloc[0]) if isinstance(last_row['EMA9'], pd.Series) else float(last_row['EMA9'])
                    ema21 = float(last_row['EMA21'].iloc[0]) if isinstance(last_row['EMA21'], pd.Series) else float(last_row['EMA21'])
                    rsi = float(last_row['RSI_14'].iloc[0]) if isinstance(last_row['RSI_14'], pd.Series) else float(last_row['RSI_14'])
                    upper = float(last_row['Upper_Band'].iloc[0]) if isinstance(last_row['Upper_Band'], pd.Series) else float(last_row['Upper_Band'])
                    lower = float(last_row['Lower_Band'].iloc[0]) if isinstance(last_row['Lower_Band'], pd.Series) else float(last_row['Lower_Band'])
                    
                    # الخوارزمية الرقمية للقرار
                    if ema9 > ema21 and rsi < 70 and price < upper:
                        decision = "STRONG BUY ⚡"
                        color = "#2ecc71"
                    elif price >= upper or rsi >= 70:
                        decision = "SELL / TAKE PROFIT 🚨"
                        color = "#e74c3c"
                    else:
                        decision = "HOLD ✋ (مراقبة)"
                        color = "#f39c12"
                    
                    # عرض الكارت الملون للقرار
                    st.markdown(
                        f'<div style="background-color:{color}; padding:20px; border-radius:10px; text-align:center; margin-bottom:20px;">'
                        f'<h2 style="color:white; margin:0;">القرار الفني الحالي لـ {ticker_input}: {decision}</h2>'
                        f'</div>', 
                        unsafe_allow_html=True
                    )
                    
                    # عرض العدادات الرقمية
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("السعر الحالي", f"{price:.2f}")
                    c2.metric("مؤشر RSI_14", f"{rsi:.2f}")
                    c3.metric("EMA9 (السريع)", f"{ema9:.2f}")
                    c4.metric("EMA21 (البطيء)", f"{ema21:.2f}")
                    
                    # --- الرسم البياني التفاعلي ---
                    st.markdown("### 📈 الرسم البياني وحركة المتوسطات الفنية")
                    fig = go.Figure()
                    
                    # تجهيز سلاسل البيانات للرسم لضمان خلوها من العناوين الفرعية
                    y_close = df['Close'].squeeze()
                    y_ema9 = df['EMA9'].squeeze()
                    y_ema21 = df['EMA21'].squeeze()
                    
                    fig.add_trace(go.Scatter(x=df.index, y=y_close, name='سعر الإغلاق', line=dict(color='#1f77b4', width=2)))
                    fig.add_trace(go.Scatter(x=df.index, y=y_ema9, name='EMA 9 (سريع)', line=dict(color='#2ca02c', dash='dot')))
                    fig.add_trace(go.Scatter(x=df.index, y=y_ema21, name='EMA 21 (بطيء)', line=dict(color='#d62728', dash='dash')))
                    
                    fig.update_layout(title=f"تحليل حركة {ticker_input} ومتوسطاته الزخمية", template="plotly_dark", xaxis_title="التاريخ", yaxis_title="السعر (ج.م)", height=500)
                    st.plotly_chart(fig, use_container_width=True)
                    
            except Exception as e:
                st.error(f"حدث خطأ أثناء تحليل البيانات: {e}")

# --- التبويب الثاني: المسح الجماعي الفوري للمحفظة والسوق ---
with tab2:
    st.subheader("📊 فحص شامل وفلترة جماعية لأهم الأسهم في نفس اللحظة")
    st.write("اضغط على الزر أدناه ليقوم البوت بفحص كامل القائمة المحددة واستخراج الأسهم الذهبية للشراء اليوم:")
    
    if st.button("تشغيل المسح الشامل للسوق 🚀"):
        scan_results = []
        with st.spinner("جاري فحص وتصفية جميع الأسهم..."):
            for name, ticker in EGYPTIAN_STOCKS.items():
                try:
                    stock_df = yf.download(ticker, period="50d", progress=False, group_by='ticker')
                    if not stock_df.empty:
                        if isinstance(stock_df.columns, pd.MultiIndex):
                            stock_df.columns = stock_df.columns.dropdown(0) if hasattr(stock_df.columns, 'dropdown') else stock_df.columns.get_level_values(-1)
                        
                        stock_df['EMA9'] = stock_df['Close'].ewm(span=9, adjust=False).mean()
                        stock_df['EMA21'] = stock_df['Close'].ewm(span=21, adjust=False).mean()
                        
                        delta = stock_df['Close'].diff()
                        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                        rs = gain / loss
                        stock_df['RSI_14'] = 100 - (100 / (1 + rs))
                        
                        stock_df['MA20'] = stock_df['Close'].rolling(window=20).mean()
                        stock_df['STD20'] = stock_df['Close'].rolling(window=20).std()
                        stock_df['Upper_Band'] = stock_df['MA20'] + (2 * stock_df['STD20'])
                        
                        row = stock_df.iloc[-1]
                        p = float(row['Close'].iloc[0]) if isinstance(row['Close'], pd.Series) else float(row['Close'])
                        e9 = float(row['EMA9'].iloc[0]) if isinstance(row['EMA9'], pd.Series) else float(row['EMA9'])
                        e21 = float(row['EMA21'].iloc[0]) if isinstance(row['EMA21'], pd.Series) else float(row['EMA21'])
                        r = float(row['RSI_14'].iloc[0]) if isinstance(row['RSI_14'], pd.Series) else float(row['RSI_14'])
                        u = float(row['Upper_Band'].iloc[0]) if isinstance(row['Upper_Band'], pd.Series) else float(row['Upper_Band'])
                        
                        if e9 > e21 and r < 70 and p < u:
                            status = "🟢 STRONG BUY"
                        elif p >= u or r >= 70:
                            status = "🔴 SELL"
                        else:
                            status = "🟡 HOLD"
                        
                        scan_results.append({
                            "اسم السهم": name,
                            "الرمز": ticker,
                            "السعر الحالي": f"{p:.2f}",
                            "مؤشر RSI": f"{r:.1f}",
                            "حالة السهم الفنية": status
                        })
                except:
                    continue
            
            if scan_results:
                result_df = pd.DataFrame(scan_results)
                st.success("تم الانتهاء من فحص وتصفية السوق بنجاح!")
                st.dataframe(result_df, use_container_width=True)
            else:
                st.warning("لم نتمكن من جمع نتائج الفحص حالياً، برجاء المحاولة لاحقاً.")
