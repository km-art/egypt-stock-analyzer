import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

st.title("🏆 نظام المسح الفني الاحترافي المرتب حسب مقياس الزخم والعزم")
st.write("تم تحديث خوارزمية الترتيب لتتوافق مع إستراتيجيات التداول المحترفة: المفاضلة هنا بناءً على قوة الاتجاه، ومساحة الصعود المتاحة، والمنطقة الذهبية لمؤشر RSI.")

# القائمة الكاملة لرموز أسهم السوق المصري (EGX) على Yahoo Finance
ALL_EGX_STOCKS = {
    "السويدي إليكتريك": "SWDY.CA", "البنك التجاري الدولي": "COMI.CA", "مصرف أبوظبي الإسلامي": "ADIB.CA",
    "مجموعة طلعت مصطفى": "TMGH.CA", "بلتون المالية القابضة": "BTFH.CA", "فوري للمدفوعات الإلكترونية": "FWRY.CA",
    "إي فاينانس للاستثمارات": "EFIH.CA", "أبو قير للأسمدة": "ABUK.CA", "مصر لإنتاج الأسمدة - موبكو": "MFPC.CA",
    "سيدي كرير للبتروكيماويات": "SKPC.CA", "الأسكندرية لتداول الحاويات": "ALCN.CA", "المصرية للاتصالات": "ETEL.CA",
    "إعمار مصر للتنمية": "EMFD.CA", "مدينة مصر للإسكان": "MASR.CA", "مصر الجديدة للإسكان": "HELI.CA",
    "بالم هيلز للتعمير": "PHDC.CA", "أوراسكوم للتنمية مصر": "ORHD.CA", "مجموعة إيـفـإى جـي هيرميس": "HRHO.CA",
    "جي بي كورب": "GBCO.CA", "القلعة للاستشارات المالية": "CCAP.CA", "حديد عز": "ESRS.CA",
    "مصر للألومنيوم": "EGAL.CA", "العز الدخيلة للصلب": "IRAX.CA", "الصعيد العامة للمقاولات": "UEGC.CA",
    "الجيزة العامة للمقاولات": "GGCC.CA", "المطورون العرب القابضة": "ARAB.CA", "أوراسكوم للاستثمار القابضة": "OIH.CA",
    "جهينة للصناعات الغذائية": "JUFO.CA", "إيديتا للصناعات الغذائية": "EFID.CA", "دومتي": "DOMT.CA",
    "الشرقية - إيسترن كومباني": "EAST.CA", "ابن سينا فارما": "ISPH.CA", "فاركو للأدوية": "PHAR.CA",
    "طاقة عربية": "TAQA.CA", "غاز مصر": "EGAS.CA", "الأسكندرية للزيوت المعدنية - أموك": "AMOC.CA",
    "كيما - الصناعات الكيماوية": "EGCH.CA", "القاهرة للإسكان والتعمير": "ELKA.CA", "شمال أفريقيا للاستثمار": "NATI.CA",
    "أودن للاستثمارات المالية": "ODIN.CA", "مطاحن ومخابز شمال القاهرة": "MNSF.CA", "مطاحن مصر الوسطى": "CEFM.CA",
    "الزيوت المستخلصة ومنتجاتها": "ZEOT.CA", "العبوات الطبية": "MEPA.CA", "العربية للأدوية": "ADCI.CA",
    "النيل للأدوية": "NIPH.CA", "أكرو مصر للشدات": "ACRO.CA", "الاسكندرية لأسمنت بورتلاند": "ALEX.CA",
    "الجوهرة - العز للسيراميك": "ECAP.CA", "صناع التغليف - يونيفرت": "UNIP.CA", "راكتا لورق التعبئة": "RAKT.CA",
    "الشمس للإسكان والتعمير": "ELSH.CA", "التعمير والاستشارات الهندسية": "DAPH.CA", "عبر المحيطات للمقاولات": "GOCE.CA",
    "الاسماعيلية مصر للدواجن": "ISMA.CA", "القاهرة للدواجن": "POUL.CA", "المنصورة للدواجن": "MPCO.CA",
    "بنك قناة السويس": "CANA.CA", "بنك البركة مصر": "SAUD.CA", "بنك فيصل الإسلامي - بالجنيه": "FAIT.CA", "بنك التعمير والإسكان": "HDBK.CA"
}

ALL_EGX_STOCKS = dict(sorted(ALL_EGX_STOCKS.items()))

tab1, tab2 = st.tabs(["🔍 فحص سهم تفصيلي + رسم بياني", "🏆 مسح وترتيب السوق الاحترافي"])

# --- التبويب الأول: فحص سهم تفصيلي ---
with tab1:
    st.subheader("اختر سهمك المفضل لتحليله ورسم بياناته بالتفصيل")
    col_input1, col_input2 = st.columns([2, 1])
    with col_input1:
        selected_stock = st.selectbox("اختر من قائمة السوق الكاملة:", list(ALL_EGX_STOCKS.keys()))
        ticker_input = ALL_EGX_STOCKS[selected_stock]
    with col_input2:
        manual_ticker = st.text_input("أو اكتب رمزاً مخصصاً يدوياً:", value="").strip().upper()
        if manual_ticker:
            ticker_input = manual_ticker

    if st.button("تحليل السهم ورسم المنحنى ⚡"):
        with st.spinner("جاري جلب البيانات وحساب المؤشرات الفنية..."):
            try:
                df = yf.download(ticker_input, period="100d", progress=False, group_by='ticker')
                if not df.empty:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(-1)
                    
                    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
                    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
                    delta = df['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    df['RSI_14'] = 100 - (100 / (1 + (gain / loss)))
                    df['MA20'] = df['Close'].rolling(window=20).mean()
                    df['STD20'] = df['Close'].rolling(window=20).std()
                    df['Upper_Band'] = df['MA20'] + (2 * df['STD20'])
                    
                    last_row = df.iloc[-1]
                    price = float(last_row['Close'].iloc[0]) if isinstance(last_row['Close'], pd.Series) else float(last_row['Close'])
                    ema9 = float(last_row['EMA9'].iloc[0]) if isinstance(last_row['EMA9'], pd.Series) else float(last_row['EMA9'])
                    ema21 = float(last_row['EMA21'].iloc[0]) if isinstance(last_row['EMA21'], pd.Series) else float(last_row['EMA21'])
                    rsi = float(last_row['RSI_14'].iloc[0]) if isinstance(last_row['RSI_14'], pd.Series) else float(last_row['RSI_14'])
                    upper = float(last_row['Upper_Band'].iloc[0]) if isinstance(last_row['Upper_Band'], pd.Series) else float(last_row['Upper_Band'])
                    
                    if ema9 > ema21 and rsi < 70 and price < upper:
                        decision = "STRONG BUY ⚡"
                        color = "#2ecc71"
                    elif price >= upper or rsi >= 70:
                        decision = "SELL / TAKE PROFIT 🚨"
                        color = "#e74c3c"
                    else:
                        decision = "HOLD ✋ (مراقبة)"
                        color = "#f39c12"
                    
                    st.markdown(f'<div style="background-color:{color}; padding:20px; border-radius:10px; text-align:center; margin-bottom:20px;"><h2 style="color:white; margin:0;">القرار الحالي لـ {ticker_input}: {decision}</h2></div>', unsafe_allow_html=True)
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("السعر الحالي", f"{price:.2f} ج.م")
                    c2.metric("مؤشر RSI_14", f"{rsi:.2f}")
                    c3.metric("EMA9", f"{ema9:.2f}")
                    c4.metric("EMA21", f"{ema21:.2f}")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].squeeze(), name='سعر الإغلاق', line=dict(color='#1f77b4', width=2)))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'].squeeze(), name='EMA 9', line=dict(color='#2ca02c', dash='dot')))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'].squeeze(), name='EMA 21', line=dict(color='#d62728', dash='dash')))
                    fig.update_layout(template="plotly_dark", height=450)
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"حدث خطأ: {e}")

# --- التبويب الثاني: مسح وترتيب السوق الاحترافي ---
with tab2:
    st.subheader("📊 ترتيب فرز المحترفين: الأسهم المرتبة بناءً على نقاط الزخم الفني الأقوى")
    st.write("كلما زادت قيمة السهم الرقمية، كلما دل ذلك على اتجاه صاعد قوي ومساحة صعود واسعة آمنة بدون تضخم:")
    
    if st.button("تشغيل الفرز والترتيب الاحترافي اللحظي 🚀"):
        scan_results = []
        progress_bar = st.progress(0)
        total_stocks = len(ALL_EGX_STOCKS)
        
        with st.spinner("جاري فحص وحساب نقاط العزم والقوة الفنية لكل سهم..."):
            tickers_list = list(ALL_EGX_STOCKS.values())
            all_data = yf.download(tickers_list, period="50d", progress=False, group_by='ticker')
            
            for idx, (name, ticker) in enumerate(ALL_EGX_STOCKS.items()):
                progress_bar.progress((idx + 1) / total_stocks)
                try:
                    if len(tickers_list) > 1:
                        stock_df = all_data[ticker].dropna(how='all')
                    else:
                        stock_df = all_data
                        
                    if stock_df.empty or len(stock_df) < 25:
                        continue
                        
                    stock_df['EMA9'] = stock_df['Close'].ewm(span=9, adjust=False).mean()
                    stock_df['EMA21'] = stock_df['Close'].ewm(span=21, adjust=False).mean()
                    delta = stock_df['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    stock_df['RSI_14'] = 100 - (100 / (1 + (gain / loss)))
                    stock_df['MA20'] = stock_df['Close'].rolling(window=20).mean()
                    stock_df['STD20'] = stock_df['Close'].rolling(window=20).std()
                    stock_df['Upper_Band'] = stock_df['MA20'] + (2 * stock_df['STD20'])
                    stock_df['Lower_Band'] = stock_df['MA20'] - (2 * stock_df['STD20'])
                    
                    row = stock_df.iloc[-1]
                    p = float(row['Close'])
                    e9 = float(row['EMA9'])
                    e21 = float(row['EMA21'])
                    r = float(row['RSI_14'])
                    u = float(row['Upper_Band'])
                    l = float(row['Lower_Band'])
                    
                    # --- بناء سكور التداول الاحترافي (Momentum Score) ---
                    momentum_score = 0
                    
                    # 1. شرط الاتجاه (Trend): لو السريع فوق البطيء بياخد نقط دعم قوية
                    if e9 > e21:
                        momentum_score += 40
                        # إضافة نقاط إضافية بناء على قوة التباعد الإيجابي
                        momentum_score += min(((e9 - e21) / e21) * 100, 10)
                    
                    # 2. شرط الـ RSI الذهبي (بين 45 و 60 هي أفضل منطقة انطلاق)
                    if 45 <= r <= 60:
                        momentum_score += 30
                    elif 30 <= r < 45:
                        momentum_score += 15 # آمن ولكنه لسه مجمعش عزم كافي
                    elif 60 < r < 70:
                        momentum_score += 10 # العزم قوي بس دخل في ريسك التضخم
                    else:
                        momentum_score -= 20 # هبوط قوي أو تضخم خطر
                        
                    # 3. مساحة الصعود داخل البولينجر (النسبة المئوية لموقع السعر داخل القناة)
                    # لو السعر قريب من القاع وله مساحة صعود كبيرة للقمة ياخذ نقاط أعلى
                    if u > l:
                        position_in_band = (u - p) / (u - l)
                        momentum_score += position_in_band * 20
                    
                    # تحديد الحالة اللفظية بناء على السكور الإجمالي الشامل
                    if momentum_score >= 70:
                        status = "🟢 شراء قوي جداً (فرصة ذهبية)"
                    elif 50 <= momentum_score < 70:
                        status = "🟢 شراء مضاربي (عزم صاعد)"
                    elif 30 <= momentum_score < 50:
                        status = "🟡 HOLD (احتفاظ / حيادي)"
                    elif 10 <= momentum_score < 30:
                        status = "🔴 بيع / تخفيف كميات"
                    else:
                        status = "🔴 خروج فوري (قرب القمة/كسر اتجاه)"
                        
                    scan_results.append({
                        "النقاط الفنية (من 100)": round(momentum_score, 1),
                        "اسم الشركة": name,
                        "الرمز البرمجي": ticker,
                        "السعر الحالي (ج.م)": round(p, 2),
                        "مؤشر RSI": round(r, 1),
                        "التقييم الفني المدمج": status
                    })
                except:
                    continue
            
            if scan_results:
                result_df = pd.DataFrame(scan_results)
                # ترتيب الجدول تنازلياً من أعلى سكور (100) لأقل سكور لترى الفرص النادرة فوراً
                result_df = result_df.sort_values(by="النقاط الفنية (من 100)", ascending=False)
                
                st.success("تم الترتيب الفني الاحترافي بنجاح! الأسهم في الأعلى هي الأفضل توافقاً مع شروط الانفجار السعري الآمن.")
                st.dataframe(result_df, use_container_width=True)
