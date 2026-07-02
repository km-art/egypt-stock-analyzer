import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

st.title("🏆 نظام المسح الفني الاحترافي المطور (السعر + السيولة الذكية)")
st.write("تم دمج مؤشر السيولة الذكية (MFI) إلى جانب RSI والبولينجر والمتوسطات المتحركة لفرز السوق بناءً على حركة أموال الحيتان والتنبيه الفوري.")

# --- القراءة التلقائية الآمنة من Streamlit Secrets ---
default_token = st.secrets.get("TELEGRAM_TOKEN", "")
default_chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")

# إعدادات التنبيهات في الشريط الجانبي
st.sidebar.header("⚙️ إعدادات إشعارات الموبايل (تليجرام)")
TELEGRAM_TOKEN = st.sidebar.text_input("أدخل Token البوت:", value=default_token, type="password")
TELEGRAM_CHAT_ID = st.sidebar.text_input("أدخل Chat ID الخاص بك:", value=default_chat_id)

def send_telegram_alert(message):
    """دالة لإرسال رسالة فورية إلى هاتف المستخدم عبر تليجرام"""
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload)
        except Exception as e:
            st.sidebar.error(f"فشل إرسال التنبيه: {e}")

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

def calculate_indicators(df):
    """دالة موحدة لحساب كافة المؤشرات بما فيها MFI"""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(-1)
        
    # المتوسطات والـ RSI
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI_14'] = 100 - (100 / (1 + (gain / loss + 0.00001)))
    
    # البولينجر
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['STD20'] = df['Close'].rolling(window=20).std()
    df['Upper_Band'] = df['MA20'] + (2 * df['STD20'])
    df['Lower_Band'] = df['MA20'] - (2 * df['STD20'])
    
    # --- حساب مؤشر السيولة الذكية MFI (Money Flow Index) ---
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    raw_money_flow = typical_price * df['Volume']
    
    typical_price_diff = typical_price.diff()
    pos_flow = pd.Series(np.where(typical_price_diff > 0, raw_money_flow, 0), index=df.index)
    neg_flow = pd.Series(np.where(typical_price_diff < 0, raw_money_flow, 0), index=df.index)
    
    pos_mf14 = pos_flow.rolling(window=14).sum()
    neg_mf14 = neg_flow.rolling(window=14).sum()
    
    money_ratio = pos_mf14 / (neg_mf14 + 0.00001)
    df['MFI_14'] = 100 - (100 / (1 + money_ratio))
    return df

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
                    df = calculate_indicators(df)
                    
                    last_row = df.iloc[-1]
                    price = float(last_row['Close'].iloc[0]) if isinstance(last_row['Close'], pd.Series) else float(last_row['Close'])
                    ema9 = float(last_row['EMA9'].iloc[0]) if isinstance(last_row['EMA9'], pd.Series) else float(last_row['EMA9'])
                    ema21 = float(last_row['EMA21'].iloc[0]) if isinstance(last_row['EMA21'], pd.Series) else float(last_row['EMA21'])
                    rsi = float(last_row['RSI_14'].iloc[0]) if isinstance(last_row['RSI_14'], pd.Series) else float(last_row['RSI_14'])
                    mfi = float(last_row['MFI_14'].iloc[0]) if isinstance(last_row['MFI_14'], pd.Series) else float(last_row['MFI_14'])
                    upper = float(last_row['Upper_Band'].iloc[0]) if isinstance(last_row['Upper_Band'], pd.Series) else float(last_row['Upper_Band'])
                    
                    # شرط القرار المطور بالاعتماد على تدفق السيولة والسعر معاً
                    if ema9 > ema21 and rsi < 70 and mfi < 80:
                        decision = "STRONG BUY ⚡ (اتجاه صاعد وسيولة ممتازة)"
                        color = "#2ecc71"
                    elif price >= upper or rsi >= 70 or mfi >= 80:
                        decision = "SELL / TAKE PROFIT 🚨 (تضخم سعري أو سيولة ذروة)"
                        color = "#e74c3c"
                        alert_msg = f"⚠️ *تنبيه تضخم السيولة والسعر يدوياً*\nالسهم: {selected_stock} ({ticker_input})\nالسعر: {price:.2f} ج.م\nRSI: {rsi:.1f} | مؤشر السيولة MFI: {mfi:.1f}\nالسيولة في أعلى ذروتها التضخمية! ينصح بجني أرباح."
                        send_telegram_alert(alert_msg)
                    else:
                        decision = "HOLD ✋ (مراقبة)"
                        color = "#f39c12"
                    
                    st.markdown(f'<div style="background-color:{color}; padding:20px; border-radius:10px; text-align:center; margin-bottom:20px;"><h2 style="color:white; margin:0;">القرار الحالي لـ {ticker_input}: {decision}</h2></div>', unsafe_allow_html=True)
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("السعر الحالي", f"{price:.2f} ج.م")
                    c2.metric("مؤشر الزخم RSI", f"{rsi:.1f}")
                    c3.metric("مؤشر السيولة MFI", f"{mfi:.1f}")
                    c4.metric("حالة الاتجاه", "صاعد 🟢" if ema9 > ema21 else "هابط 🔴")
                    
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
    st.subheader("📊 ترتيب فرز المحترفين المطور: بناءً على نقاط الزخم ودخول السيولة الذكية")
    
    if st.button("تشغيل الفرز والترتيب الاحترافي اللحظي 🚀"):
        scan_results = []
        progress_bar = st.progress(0)
        total_stocks = len(ALL_EGX_STOCKS)
        
        with st.spinner("جاري مسح السوق وحساب تدفقات أموال الحيتان الحالية..."):
            tickers_list = list(ALL_EGX_STOCKS.values())
            all_data = yf.download(tickers_list, period="60d", progress=False, group_by='ticker')
            
            for idx, (name, ticker) in enumerate(ALL_EGX_STOCKS.items()):
                progress_bar.progress((idx + 1) / total_stocks)
                try:
                    if len(tickers_list) > 1:
                        stock_df = all_data[ticker].dropna(how='all')
                    else:
                        stock_df = all_data
                        
                    if stock_df.empty or len(stock_df) < 25:
                        continue
                        
                    stock_df = calculate_indicators(stock_df)
                    
                    row = stock_df.iloc[-1]
                    p = float(row['Close'])
                    e9 = float(row['EMA9'])
                    e21 = float(row['EMA21'])
                    r = float(row['RSI_14'])
                    m = float(row['MFI_14'])
                    u = float(row['Upper_Band'])
                    l = float(row['Lower_Band'])
                    
                    # --- خوارزمية التقييم الرقمي المطورة من 100 ---
                    momentum_score = 0
                    
                    # 1. الاتجاه الفني (وزن 35 نقطة)
                    if e9 > e21:
                        momentum_score += 35
                    
                    # 2. قوة السيولة الذكية MFI (وزن 35 نقطة)
                    if 50 <= m <= 70:
                        momentum_score += 35  # تجميع شرائي قوي وصحي
                    elif 35 <= m < 50:
                        momentum_score += 20  # تجميع هادئ
                    elif m > 85:
                        momentum_score -= 25  # خروج سيولة وتضخم مرعب
                        
                    # 3. القوة النسبية للسعر RSI (وزن 20 نقطة)
                    if 45 <= r <= 65:
                        momentum_score += 20
                    elif r > 75:
                        momentum_score -= 20
                        
                    # 4. مساحة الحركة داخل البولينجر (وزن 10 نقاط)
                    if u > l:
                        momentum_score += ((u - p) / (u - l)) * 10
                    
                    # الحالات والتنبيهات التلقائية المعتمدة على السيولة والسعر
                    if momentum_score >= 70:
                        status = "🟢 شراء قوي جداً (تجميع الحيتان)"
                    elif 50 <= momentum_score < 70:
                        status = "🟢 شراء مضاربي (تدفق سيولة)"
                    elif 30 <= momentum_score < 50:
                        status = "🟡 HOLD (مراقبة حركة السيولة)"
                    elif 10 <= momentum_score < 30:
                        status = "🔴 بيع وتخفيف (تصريف خفي)"
                        send_telegram_alert(f"🚨 *تنبيه تصريف وخروج سيولة* 🚨\nالسهم: {name} ({ticker})\nالسعر: {p:.2f} ج.م\nالسيولة MFI: {m:.1f}\nالوضع: الحيتان تبدأ بالتصريف والسيولة تخرج!")
                    else:
                        status = "🔴 خروج فوري (انفجار فقاعة التضخم)"
                        send_telegram_alert(f"🔥 *إشارة قمة تاريخية وخروج عاجل* 🔥\nالسهم: {name} ({ticker})\nالسعر: {p:.2f} ج.م\nMFI: {m:.1f} | RSI: {r:.1f}\nالوضع: تضخم شرائي متكامل وسقوط حتمي للسعر!")
                        
                    scan_results.append({
                        "النقاط الفنية والسيولة (من 100)": round(momentum_score, 1),
                        "اسم الشركة": name,
                        "الرمز البرمجي": ticker,
                        "السعر الحالي (ج.م)": round(p, 2),
                        "مؤشر الزخم RSI": round(r, 1),
                        "مؤشر السيولة MFI": round(m, 1),
                        "التقييم الفني المدمج": status
                    })
                except:
                    continue
            
            if scan_results:
                result_df = pd.DataFrame(scan_results)
                result_df = result_df.sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False)
                
                st.success("تم المسح الشامل وترتيب السوق بناءً على السعر والسيولة بنجاح! 🦅")
                st.dataframe(result_df, use_container_width=True)
