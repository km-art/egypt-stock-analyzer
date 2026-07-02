import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

st.title("🦅 قناص البورصة المصرية (فصل التقاطعات الحديثة + تدفق السيولة)")
st.write("تم ترقية النظام ليفصل لك 'الفرص الطازة الحالية' في جدول مستقل علوي، مع الحفاظ على ترتيب السوق العام بناءً على سيولة الحيتان.")

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
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(-1)
        
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
    
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    raw_money_flow = typical_price * df['Volume']
    typical_price_diff = typical_price.diff()
    pos_flow = pd.Series(np.where(typical_price_diff > 0, raw_money_flow, 0), index=df.index)
    neg_flow = pd.Series(np.where(typical_price_diff < 0, raw_money_flow, 0), index=df.index)
    
    pos_mf14 = pos_flow.rolling(window=14).sum()
    neg_mf14 = neg_flow.rolling(window=14).sum()
    df['MFI_14'] = 100 - (100 / (1 + (pos_mf14 / (neg_mf14 + 0.00001))))
    return df

tab1, tab2 = st.tabs(["🔍 فحص سهم تفصيلي + رسم بياني", "🏆 مسح وترتيب السوق الاحترافي"])

# --- التبويب الأول ---
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
        with st.spinner("جاري جلب البيانات..."):
            try:
                df = yf.download(ticker_input, period="100d", progress=False, group_by='ticker')
                if not df.empty:
                    df = calculate_indicators(df)
                    last_row = df.iloc[-1]
                    prev_row = df.iloc[-3]
                    
                    price = float(last_row['Close'].squeeze())
                    ema9 = float(last_row['EMA9'].squeeze())
                    ema21 = float(last_row['EMA21'].squeeze())
                    rsi = float(last_row['RSI_14'].squeeze())
                    mfi = float(last_row['MFI_14'].squeeze())
                    upper = float(last_row['Upper_Band'].squeeze())
                    
                    is_new_cross = (prev_row['EMA9'] <= prev_row['EMA21']) and (ema9 > ema21)
                    
                    if is_new_cross and rsi < 60:
                        decision = "🚀 تأسيس مركز (بداية تقاطع ذهبي واعد جداً)"
                        color = "#1abc9c"
                    elif ema9 > ema21 and rsi < 70 and mfi < 80:
                        decision = "STRONG BUY ⚡ (اتجاه صاعد مستمر)"
                        color = "#2ecc71"
                    elif price >= upper or rsi >= 70 or mfi >= 80:
                        decision = "SELL / TAKE PROFIT 🚨"
                        color = "#e74c3c"
                    else:
                        decision = "HOLD ✋ (مراقبة)"
                        color = "#f39c12"
                    
                    st.markdown(f'<div style="background-color:{color}; padding:20px; border-radius:10px; text-align:center; margin-bottom:20px;"><h2 style="color:white; margin:0;">القرار الحالي لـ {ticker_input}: {decision}</h2></div>', unsafe_allow_html=True)
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("السعر الحالي", f"{price:.2f} ج.م")
                    c2.metric("مؤشر الزخم RSI", f"{rsi:.1f}")
                    c3.metric("مؤشر السيولة MFI", f"{mfi:.1f}")
                    c4.metric("نوع الإشارة", "تقاطع حديث النشوء ✨" if is_new_cross else "موجة مستمرة 🌊")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].squeeze(), name='سعر الإغلاق', line=dict(color='#1f77b4', width=2)))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'].squeeze(), name='EMA 9', line=dict(color='#2ca02c', dash='dot')))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'].squeeze(), name='EMA 21', line=dict(color='#d62728', dash='dash')))
                    fig.update_layout(template="plotly_dark", height=450)
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"حدث خطأ: {e}")

# --- التبويب الثاني ---
with tab2:
    st.subheader("📊 الفرز والترتيب المتقدم للسوق المصري")
    
    if st.button("تشغيل الفرز والترتيب الاحترافي اللحظي 🚀"):
        fresh_cross_results = []
        general_market_results = []
        progress_bar = st.progress(0)
        total_stocks = len(ALL_EGX_STOCKS)
        
        with st.spinner("جاري فحص التقاطعات ورصد تدفق سيولة الحيتان..."):
            tickers_list = list(ALL_EGX_STOCKS.values())
            all_data = yf.download(tickers_list, period="60d", progress=False, group_by='ticker')
            
            for idx, (name, ticker) in enumerate(ALL_EGX_STOCKS.items()):
                progress_bar.progress((idx + 1) / total_stocks)
                try:
                    stock_df = all_data[ticker].dropna(how='all') if len(tickers_list) > 1 else all_data
                    if stock_df.empty or len(stock_df) < 25:
                        continue
                        
                    stock_df = calculate_indicators(stock_df)
                    row = stock_df.iloc[-1]
                    prev_row = stock_df.iloc[-4]
                    
                    p = float(row['Close'])
                    e9 = float(row['EMA9'])
                    e21 = float(row['EMA21'])
                    r = float(row['RSI_14'])
                    m = float(row['MFI_14'])
                    u = float(row['Upper_Band'])
                    l = float(row['Lower_Band'])
                    
                    # شرط التقاطع الطازج لفرص التأسيس المبكر
                    is_new_cross = (prev_row['EMA9'] <= prev_row['EMA21']) and (e9 > e21)
                    
                    momentum_score = 0
                    if e9 > e21: 
                        momentum_score += 40
                    if 50 <= m <= 70: 
                        momentum_score += 30
                    elif 35 <= m < 50: 
                        momentum_score += 15
                    elif m > 85: 
                        momentum_score -= 25
                    if 45 <= r <= 65: 
                        momentum_score += 20
                    elif r > 75: 
                        momentum_score -= 20
                    if u > l: 
                        momentum_score += ((u - p) / (u - l)) * 10
                    
                    if m > 85 or r > 75:
                        status = "🔴 خروج فوري (تضخم حاد)"
                    elif momentum_score >= 70:
                        status = "🟢 شراء قوي (تجمع سيولة مستمر)"
                    elif 50 <= momentum_score < 70:
                        status = "🟢 شراء مضاربي (ركوب الموجة)"
                    else:
                        status = "🟡 HOLD (مراقبة)"
                    
                    data_entry = {
                        "النقاط الفنية والسيولة (من 100)": round(momentum_score, 1),
                        "اسم الشركة": name,
                        "الرمز البرمجي": ticker,
                        "السعر الحالي (ج.م)": round(p, 2),
                        "مؤشر الزخم RSI": round(r, 1),
                        "مؤشر السيولة MFI": round(m, 1),
                        "التقييم الفني المدمج": status
                    }
                    
                    # الفرز الذكي والتوزيع في جداول منفصلة
                    if is_new_cross and r < 63:
                        data_entry["التقييم الفني المدمج"] = "✨ تأسيس مركز (تقاطع ذهبي حديث)"
                        fresh_cross_results.append(data_entry)
                        send_telegram_alert(f"🌟 *قناص الفرص لقط تقاطع ذهبي طازة!* 🌟\nالسهم: {name} ({ticker})\nالسعر: {p:.2f} ج.م\nMFI: {m:.1f}\nالوضع: السهم بيبدأ موجة صعود جديدة حالا! فرصة تأسيس مثالية.")
                    else:
                        general_market_results.append(data_entry)
                except:
                    continue
            
            st.success("تم الانتهاء من المسح والفرز بنجاح! 🦅")
            
            # 1. عرض جدول فرص التأسيس الطازة أولاً في الأعلى
            st.markdown("### 🚀 أولاً: أسهم لقطت 'إشارة تأسيس مركز جديدة اليوم' (التقاطعات الطازة)")
            if fresh_cross_results:
                fresh_df = pd.DataFrame(fresh_cross_results).sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False)
                st.dataframe(fresh_df, use_container_width=True)
            else:
                st.info("لا توجد أسهم لقطت بداية تقاطع ذهبي جديد اليوم. تابع جدول فرز السوق العام بالأسفل.")
                
            st.write("---")
            
            # 2. عرض جدول فرز السوق العام تحت
            st.markdown("### 📊 ثانياً: جدول فرز وترتيب السوق العام (حسب قوة الزخم والسيولة المستمرة)")
            if general_market_results:
                general_df = pd.DataFrame(general_market_results).sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False)
                st.dataframe(general_df, use_container_width=True)
