import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import time

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="محلل البورصة المصرية الشامل 🇪🇬📈", layout="wide")

st.title("🚀 النظام المتكامل للمسح الفني الشامل لجميع أسهم السوق المصري")
st.write("مرحباً بك! يمكنك الآن عمل فحص فني وفلترة فورية لكامل أسهم البورصة المصرية المدرجة.")

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
    "ديفكو - الدلتا للتأمين": "DEFI.CA", "المهندس للتأمين": "MGIN.CA", "بنك قناة السويس": "CANA.CA",
    "بنك البركة مصر": "SAUD.CA", "بنك فيصل الإسلامي - بالجنيه": "FAIT.CA", "بنك التعمير والإسكان": "HDBK.CA",
    "الوطنية لإسكان النقابات": "NHGE.CA", "العربية لاستصلاح الأراضي": "EALR.CA", "العامة لاستصلاح الأراضي": "AALR.CA",
    "ريماس - سيراميك": "REMA.CA", "الاسماعيلية التطوير العقاري": "IDRE.CA", "مرسيليا المصرية الخليجية": "MAAL.CA"
}

# ترتيب الأسهم أبجدياً لسهولة البحث
ALL_EGX_STOCKS = dict(sorted(ALL_EGX_STOCKS.items()))

# تقسيم التطبيق إلى تبويبين
tab1, tab2 = st.tabs(["🔍 فحص سهم تفصيلي + رسم بياني", "📊 مسح كامل السوق المصري فوري 🇪🇬"])

# --- التبويب الأول: فحص سهم تفصيلي ---
with tab1:
    st.subheader("اختر سهمك المفضل لتحليله ورسم بياناته بالتفصيل")
    
    col_input1, col_input2 = st.columns([2, 1])
    with col_input1:
        selected_stock = st.selectbox("اختر من قائمة السوق الكاملة:", list(ALL_EGX_STOCKS.keys()))
        ticker_input = ALL_EGX_STOCKS[selected_stock]
    with col_input2:
        manual_ticker = st.text_input("أو اكتب رمزاً مخصصاً يدوياً (مثال: COMI.CA):", value="").strip().upper()
        if manual_ticker:
            ticker_input = manual_ticker

    if st.button("تحليل السهم ورسم المنحنى ⚡"):
        with st.spinner("جاري جلب البيانات وحساب المؤشرات الفنية..."):
            try:
                df = yf.download(ticker_input, period="100d", progress=False, group_by='ticker')
                
                if df.empty:
                    st.error("لم نتمكن من العثور على بيانات لهذا الرمز.")
                else:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.dropdown(0) if hasattr(df.columns, 'dropdown') else df.columns.get_level_values(-1)
                    
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
                    
                    st.markdown(
                        f'<div style="background-color:{color}; padding:20px; border-radius:10px; text-align:center; margin-bottom:20px;">'
                        f'<h2 style="color:white; margin:0;">القرار الفني الحالي لـ {ticker_input}: {decision}</h2>'
                        f'</div>', 
                        unsafe_allow_html=True
                    )
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("السعر الحالي", f"{price:.2f} ج.م")
                    c2.metric("مؤشر RSI_14", f"{rsi:.2f}")
                    c3.metric("EMA9 (السريع)", f"{ema9:.2f}")
                    c4.metric("EMA21 (البطيء)", f"{ema21:.2f}")
                    
                    st.markdown("### 📈 الرسم البياني وحركة المتوسطات الفنية")
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].squeeze(), name='سعر الإغلاق', line=dict(color='#1f77b4', width=2)))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'].squeeze(), name='EMA 9', line=dict(color='#2ca02c', dash='dot')))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'].squeeze(), name='EMA 21', line=dict(color='#d62728', dash='dash')))
                    
                    fig.update_layout(template="plotly_dark", xaxis_title="التاريخ", yaxis_title="السعر (ج.م)", height=500)
                    st.plotly_chart(fig, use_container_width=True)
                    
            except Exception as e:
                st.error(f"حدث خطأ أثناء تحليل البيانات: {e}")

# --- التبويب الثاني: مسح كامل السوق المصري فوري ---
with tab2:
    st.subheader("📊 فلترة ومسح شامل لـجـمـيـع أسهم البورصة المصرية")
    st.write("بضغطة واحدة، سيقوم النظام بفحص كامل الشركات المدرجة وتصنيفها في جدول متكامل وبسرعة عالية:")
    
    # فلترة سريعة للجدول النهائي لتسهيل المتابعة
    filter_choice = st.radio("عرض حسب الفئة الفنية:", ["كل الأسهم الشاملة", "إشارات الشراء فقط (🟢 STRONG BUY)", "إشارات البيع فقط (🔴 SELL)"], horizontal=True)

    if st.button("ابدأ الفحص الشامل لكامل السوق المصري 🚀"):
        scan_results = []
        progress_bar = st.progress(0)
        total_stocks = len(ALL_EGX_STOCKS)
        
        with st.spinner("جاري جلب البيانات من مقصورة البورصة وفلترة الإشارات..."):
            # جلب البيانات لجميع الأسهم دفعة واحدة لتوفير الوقت وسرعة الأداء
            tickers_list = list(ALL_EGX_STOCKS.values())
            all_data = yf.download(tickers_list, period="50d", progress=False, group_by='ticker')
            
            for idx, (name, ticker) in enumerate(ALL_EGX_STOCKS.items()):
                progress_bar.progress((idx + 1) / total_stocks)
                
                try:
                    # استخراج بيانات السهم المفرد من البيانات المجمعة
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
                    rs = gain / loss
                    stock_df['RSI_14'] = 100 - (100 / (1 + rs))
                    
                    stock_df['MA20'] = stock_df['Close'].rolling(window=20).mean()
                    stock_df['STD20'] = stock_df['Close'].rolling(window=20).std()
                    stock_df['Upper_Band'] = stock_df['MA20'] + (2 * stock_df['STD20'])
                    
                    row = stock_df.iloc[-1]
                    p = float(row['Close'])
                    e9 = float(row['EMA9'])
                    e21 = float(row['EMA21'])
                    r = float(row['RSI_14'])
                    u = float(row['Upper_Band'])
                    
                    if e9 > e21 and r < 70 and p < u:
                        status = "🟢 STRONG BUY"
                    elif p >= u or r >= 70:
                        status = "🔴 SELL"
                    else:
                        status = "🟡 HOLD"
                    
                    scan_results.append({
                        "اسم الشركة": name,
                        "الرمز البرمجي": ticker,
                        "السعر الحالي (ج.م)": round(p, 2),
                        "مؤشر RSI": round(r, 1),
                        "الحالة الفنية للسهم": status
                    })
                except:
                    continue
            
            if scan_results:
                result_df = pd.DataFrame(scan_results)
                
                # تطبيق الفلترة المختارة من المستخدم
                if filter_choice == "إشارات الشراء فقط (🟢 STRONG BUY)":
                    result_df = result_df[result_df["الحالة الفنية للسهم"] == "🟢 STRONG BUY"]
                elif filter_choice == "إشارات البيع فقط (🔴 SELL)":
                    result_df = result_df[result_df["الحالة الفنية للسهم"] == "🔴 SELL"]
                
                st.success(f"تم الانتهاء! إجمالي الشركات التي تم فحصها بنجاح: {len(result_df)} شركة.")
                st.dataframe(result_df, use_container_width=True)
            else:
                st.warning("نعتذر، لم يتم تحديث البيانات حالياً من السيرفر.")
