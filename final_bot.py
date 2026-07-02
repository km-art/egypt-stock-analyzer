import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

st.title("🦅 قناص البورصة المصرية (النسخة المتكاملة المقفلة ضد المخاطر)")
st.write("تم تقفيل الكود بمعايير صارمة: إضافة حد أدنى للفوليوم لحجب الأسهم الميتة، وفلاتر حماية من التضخم الحاد.")

# --- قاموس قيمة جراهام للأسهم (تحديث دوري) ---
GRAHAM_VALUES = {
    "أبو قير للأسمدة": 0.0,
    "أكرو مصر للشدات": 0.0,
    "أوراسكوم للاستثمار القابضة": 0.0,
    "أوراسكوم للتنمية مصر": 0.0,
    "أودن للاستثمارات المالية": 0.0,
    "إعمار مصر للتنمية": 0.0,
    "إي فاينانس للاستثمارات": 0.0,
    "إيديتا للصناعات الغذائية": 0.0,
    "ابن سينا فارما": 0.0,
    "الاسكندرية لأسمنت بورتلاند": 0.0,
    "الأسكندرية لتداول الحاويات": 0.0,
    "الأسكندرية للزيوت المعدنية - أموك": 0.0,
    "الاسماعيلية مصر للدواجن": 0.0,
    "البنك التجاري الدولي": 92.77,
    "التعمير والاستشارات الهندسية": 0.0,
    "الجوهرة - العز للسيراميك": 0.0,
    "الجيزة العامة للمقاولات": 0.0,
    "الشمس للإسكان والتعمير": 0.0,
    "الشرقية - إيسترن كومباني": 0.0,
    "الصعيد العامة للمقاولات": 0.0,
    "العبوات الطبية": 0.0,
    "العربية للأدوية": 0.0,
    "العز الدخيلة للصلب": 0.0,
    "القاهرة للإسكان والتعمير": 0.0,
    "القاهرة للدواجن": 0.0,
    "القلعة للاستشارات المالية": 0.0,
    "المطورون العرب القابضة": 0.0,
    "المصرية للاتصالات": 0.0,
    "المنصورة للدواجن": 0.0,
    "النيل للأدوية": 0.0,
    "الزيوت المستخلصة ومنتجاتها": 0.0,
    "السويدي إليكتريك": 38.27,
    "بالم هيلز للتعمير": 0.0,
    "بنك البركة مصر": 0.0,
    "بنك التعمير والإسكان": 0.0,
    "بنك فيصل الإسلامي - بالجنيه": 0.0,
    "بنك قناة السويس": 0.0,
    "بلتون المالية القابضة": 0.0,
    "جهينة للصناعات الغذائية": 0.0,
    "جي بي كورب": 0.0,
    "حديد عز": 0.0,
    "دومتي": 0.0,
    "راكتا لورق التعبئة": 0.0,
    "سيدي كرير للبتروكيماويات": 0.0,
    "شمال أفريقيا للاستثمار": 0.0,
    "صناع التغليف - يونيفرت": 0.0,
    "طاقة عربية": 0.0,
    "عبر المحيطات للمقاولات": 0.0,
    "غاز مصر": 0.0,
    "فاركو للأدوية": 0.0,
    "فوري للمدفوعات الإلكترونية": 0.0,
    "كيما - الصناعات الكيماوية": 0.0,
    "مدينة مصر للإسكان": 0.0,
    "مجموعة إيـفـإى جـي هيرميس": 0.0,
    "مجموعة طلعت مصطفى": 23.81,
    "مطاحن مصر الوسطى": 0.0,
    "مطاحن ومخابز شمال القاهرة": 0.0,
    "مصر الجديدة للإسكان": 0.0,
    "مصر لإنتاج الأسمدة - موبكو": 0.0,
    "مصر للألومنيوم": 0.0,
    "مصرف أبوظبي الإسلامي": 55.62
}

def get_graham_value(name):
    """جلب قيمة جراهام من القاموس"""
    val = GRAHAM_VALUES.get(name, None)
    return val if val != 0.0 else None  # تحويل الصفر إلى None ليظهر N/A

# القراءة التلقائية من Streamlit Secrets كخيار احتياطي
default_token = st.secrets.get("TELEGRAM_TOKEN", "")
default_chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")

# إعدادات التنبيهات في الشريط الجانبي
st.sidebar.header("⚙️ إعدادات إشعارات الموبايل (تليجرام)")
TELEGRAM_TOKEN = st.sidebar.text_input("أدخل Token البوت:", value=default_token, type="password")
TELEGRAM_CHAT_ID = st.sidebar.text_input("أدخل Chat ID الخاص بك:", value=default_chat_id)

def send_telegram_alert(message):
    """دالة لإرسال رسالة فورية إلى هاتف المستخدم عبر تليجرام"""
    token = TELEGRAM_TOKEN if TELEGRAM_TOKEN else default_token
    chat_id = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else default_chat_id
    
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload)
        except Exception as e:
            st.sidebar.error(f"فشل إرسال التنبيه: {e}")

# القائمة الكاملة لرموز أسهم السوق المصري (EGX)
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
    
    df['Vol_MA10'] = df['Volume'].rolling(window=10).mean()
    return df

tab1, tab2 = st.tabs(["🔍 فحص سهم تفصيلي + رسم بياني", "🏆 مسح وترتيب السوق الاحترافي"])

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
                    vol = float(last_row['Volume'].squeeze())
                    
                    is_new_cross = (prev_row['EMA9'] <= prev_row['EMA21']) and (ema9 > ema21)
                    
                    if is_new_cross and rsi < 52:
                        decision = "🚀 تأسيس مركز (بداية تقاطع ذهبي حقيقي من القاع)"
                        color = "#1abc9c"
                    elif rsi < 35 and mfi < 35:
                        decision = "🛒 تجميع في القاع (منطقة رخيصة جداً للمراقبة)"
                        color = "#3498db"
                    elif ema9 > ema21 and rsi < 70 and mfi < 80:
                        decision = "STRONG BUY ⚡ (اتجاه صاعد مستمر)"
                        color = "#2ecc71"
                    elif price >= upper or rsi >= 75 or mfi >= 85:
                        decision = "SELL / TAKE PROFIT 🚨 (تضخم مؤشرات حاد)"
                        color = "#e74c3c"
                    else:
                        decision = "HOLD ✋ (مراقبة)"
                        color = "#f39c12"
                    
                    st.markdown(f'<div style="background-color:{color}; padding:20px; border-radius:10px; text-align:center; margin-bottom:20px;"><h2 style="color:white; margin:0;">القرار الحالي لـ {ticker_input}: {decision}</h2></div>', unsafe_allow_html=True)
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("السعر الحالي", f"{price:.2f} ج.م")
                    c2.metric("مؤشر الزخم RSI", f"{rsi:.1f}")
                    c3.metric("مؤشر السيولة MFI", f"{mfi:.1f}")
                    c4.metric("حجم تداول اليوم (فوليوم)", f"{vol:,.0f}")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].squeeze(), name='سعر الإغلاق', line=dict(color='#1f77b4', width=2)))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'].squeeze(), name='EMA 9', line=dict(color='#2ca02c', dash='dot')))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'].squeeze(), name='EMA 21', line=dict(color='#d62728', dash='dash')))
                    fig.update_layout(template="plotly_dark", height=450)
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"حدث خطأ: {e}")

with tab2:
    st.subheader("📊 الفرز والترتيب المتقدم لأسهم السوق")
    
    if st.button("تشغيل الفرز والترتيب الاحترافي اللحظي 🚀"):
        fresh_cross_results = []
        bottom_accumulation_results = []
        short_term_trading = []
        long_term_investment = []
        
        progress_bar = st.progress(0)
        total_stocks = len(ALL_EGX_STOCKS)
        
        with st.spinner("جاري مسح الأسهم ورصد الفرص الصارمة..."):
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
                    vol_today = float(row['Volume'])
                    vol_ma10 = float(row['Vol_MA10'])
                    
                    if vol_today < 50000:
                        continue
                        
                    is_new_cross = (prev_row['EMA9'] <= prev_row['EMA21']) and (e9 > e21)
                    
                    momentum_score = 0
                    if e9 > e21: momentum_score += 40
                    if 50 <= m <= 70: momentum_score += 30
                    elif 35 <= m < 50: momentum_score += 15
                    elif m > 85: momentum_score -= 25
                    if 45 <= r <= 65: momentum_score += 20
                    elif r > 75: momentum_score -= 20
                    if u > l: momentum_score += ((u - p) / (u - l)) * 10
                    if vol_today > vol_ma10: momentum_score += 10
                    
                    if m > 85 or r > 78:
                        status = "🚨 تصريف / خروج (تضخم)"
                    elif momentum_score >= 70:
                        status = "⚡ STRONG BUY (شراء قوي)"
                    elif 50 <= momentum_score < 70:
                        status = "🟢 إيجابي (متوسط)"
                    else:
                        status = "🟡 HOLD (مراقبة)"
                    
                    # --- التعديل هنا: استخدام مسميات جراهام ---
                    gv = get_graham_value(name)
                    price_status = "لقطة (تحت قيمة جراهام)" if (gv and p < gv) else "مبالغ فيه/عادل"
                    
                    data_entry = {
                        "النقاط الفنية والسيولة (من 100)": round(momentum_score, 1),
                        "اسم الشركة": name,
                        "الرمز البرمجي": ticker,
                        "قيمة جراهام": gv if gv else "N/A",
                        "تقييم جراهام للسعر": price_status,
                        "السعر الحالي (ج.م)": round(p, 2),
                        "مؤشر الزخم RSI": round(r, 1),
                        "مؤشر السيولة MFI": round(m, 1),
                        "فوليوم اليوم": f"{vol_today:,.0f}",
                        "متوسط فوليوم 10أيام": f"{vol_ma10:,.0f}",
                        "التقييم الفني": status
                    }
                    # -------------------------------------------------------------
                    
                    if is_new_cross and r < 52:
                        data_entry["التقييم الفني"] = "✨ تأسيس مركز (قاع صاعد طازة)"
                        fresh_cross_results.append(data_entry)
                    
                    elif r < 35 and m < 35:
                        data_entry["التقييم الفني"] = "🛒 قاع تجميع (فرصة مراقبة صامتة)"
                        bottom_accumulation_results.append(data_entry)
                    
                    elif e9 > e21:
                        if vol_today > (vol_ma10 * 1.15) and 50 <= r <= 78:
                            data_entry["التقييم الفني"] = f"{status} [مضاربة لحظية]"
                            short_term_trading.append(data_entry)
                        else:
                            data_entry["التقييم الفني"] = f"{status} [استثمار مستقر]"
                            long_term_investment.append(data_entry)
                except:
                    continue
            
            st.success("تم التحديث النهائي والإغلاق الهندسي للرادار بنجاح! 🦅")
            
            # --- آلية الإرسال المعدلة لـ 5 فرص ---
            telegram_msg = "🦅 *تقرير قناص البورصة المصرية اللحظي* 🇪🇬\n\n"
            
            if fresh_cross_results:
                telegram_msg += "🌟 *أسهم تأسيس المركز (قاع صاعد):*\n"
                for item in fresh_cross_results[:5]: 
                    telegram_msg += f"- {item['اسم الشركة']} ({item['السعر الحالي (ج.م)']} ج.م)\n"
                telegram_msg += "\n"
                
            if long_term_investment:
                top_inv = pd.DataFrame(long_term_investment).sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False).head(5) 
                telegram_msg += "📈 *أقوى أسهم الاتجاه الصاعد المستقر:*\n"
                for _, row_inv in top_inv.iterrows():
                    telegram_msg += f"- {row_inv['اسم الشركة']} | السعر: {row_inv['السعر الحالي (ج.م)']} ج.م | النقاط: {row_inv['النقاط الفنية والسيولة (من 100)']}\n"
                telegram_msg += "\n"
                
            if short_term_trading:
                top_trade = pd.DataFrame(short_term_trading).sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False).head(5) 
                telegram_msg += "⚡ *أقوى أسهم المضاربة اللحظية وعزم السيولة:*\n"
                for _, row_tr in top_trade.iterrows():
                    telegram_msg += f"- {row_tr['اسم الشركة']} | السعر: {row_tr['السعر الحالي (ج.م)']} ج.م\n"
            
            send_telegram_alert(telegram_msg)
            
            st.markdown("### 🚀 أولاً: أسهم لقطت 'إشارة تأسيس مركز جديدة اليوم' (آمنة وصارمة، RSI < 52)")
            if fresh_cross_results:
                st.dataframe(pd.DataFrame(fresh_cross_results).sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False), use_container_width=True)
            else:
                st.info("لا توجد أسهم لقطت تقاطع ذهبي هادئ اليوم واستوفت شروط الفوليوم الحقيقي.")
                
            st.write("---")
            
            st.markdown("### 📥 ثانياً: رادار تصيد القيعان (أسهم رخيصة جداً في مناطق تجميع الحيتان 🐋)")
            if bottom_accumulation_results:
                st.dataframe(pd.DataFrame(bottom_accumulation_results).sort_values(by="مؤشر الزخم RSI", ascending=True), use_container_width=True)
            else:
                st.info("لا توجد أسهم حالياً في قيعان التشبع البيعي الحاد تحت 35 تنطبق عليها شروط الفوليوم الأمان.")
                
            st.write("---")
            
            st.markdown("### ⚡ ثالثاً: أسهم المضاربة اللحظية واليومية (سيولة ضخمة وعزم سريع محمي من التضخم)")
            if short_term_trading:
                st.dataframe(pd.DataFrame(short_term_trading).sort_values(by="فوليوم اليوم", ascending=False), use_container_width=True)
            else:
                st.info("لا توجد أسهم مستوفية لشروط الحركات المضاربية النشطة والآمنة حالياً.")

            st.write("---")
            
            st.markdown("تم التعديل يا ريس! ✨

غيرت المسميات في الكود بالكامل لتصبح **"قيمة جراهام"** بدلاً من "القيمة العادلة" عشان تكون دقيقة واحترافية 100%. وكمان دمجت قائمة الشركات الكاملة اللي جهزناها عشان الكود يكون جاهز للعمل فوراً.

إليك الكود النهائي المحدث:

```python
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

st.title("🦅 قناص البورصة المصرية (النسخة المتكاملة المقفلة ضد المخاطر)")
st.write("تم تقفيل الكود بمعايير صارمة: إضافة حد أدنى للفوليوم لحجب الأسهم الميتة، وفلاتر حماية من التضخم الحاد.")

# --- قاموس قيمة جراهام للأسهم (تحديث دوري) ---
# يمكنك استبدال الأصفار بقيمة جراهام الحقيقية لكل شركة
GRAHAM_VALUES = {
    "أبو قير للأسمدة": 0.0,
    "أكرو مصر للشدات": 0.0,
    "أوراسكوم للاستثمار القابضة": 0.0,
    "أوراسكوم للتنمية مصر": 0.0,
    "أودن للاستثمارات المالية": 0.0,
    "إعمار مصر للتنمية": 0.0,
    "إي فاينانس للاستثمارات": 0.0,
    "إيديتا للصناعات الغذائية": 0.0,
    "ابن سينا فارما": 0.0,
    "الاسكندرية لأسمنت بورتلاند": 0.0,
    "الأسكندرية لتداول الحاويات": 0.0,
    "الأسكندرية للزيوت المعدنية - أموك": 0.0,
    "الاسماعيلية مصر للدواجن": 0.0,
    "البنك التجاري الدولي": 92.77,
    "التعمير والاستشارات الهندسية": 0.0,
    "الجوهرة - العز للسيراميك": 0.0,
    "الجيزة العامة للمقاولات": 0.0,
    "الشمس للإسكان والتعمير": 0.0,
    "الشرقية - إيسترن كومباني": 0.0,
    "الصعيد العامة للمقاولات": 0.0,
    "العبوات الطبية": 0.0,
    "العربية للأدوية": 0.0,
    "العز الدخيلة للصلب": 0.0,
    "القاهرة للإسكان والتعمير": 0.0,
    "القاهرة للدواجن": 0.0,
    "القلعة للاستشارات المالية": 0.0,
    "المطورون العرب القابضة": 0.0,
    "المصرية للاتصالات": 0.0,
    "المنصورة للدواجن": 0.0,
    "النيل للأدوية": 0.0,
    "الزيوت المستخلصة ومنتجاتها": 0.0,
    "السويدي إليكتريك": 38.27,
    "بالم هيلز للتعمير": 0.0,
    "بنك البركة مصر": 0.0,
    "بنك التعمير والإسكان": 0.0,
    "بنك فيصل الإسلامي - بالجنيه": 0.0,
    "بنك قناة السويس": 0.0,
    "بلتون المالية القابضة": 0.0,
    "جهينة للصناعات الغذائية": 0.0,
    "جي بي كورب": 0.0,
    "حديد عز": 0.0,
    "دومتي": 0.0,
    "راكتا لورق التعبئة": 0.0,
    "سيدي كرير للبتروكيماويات": 0.0,
    "شمال أفريقيا للاستثمار": 0.0,
    "صناع التغليف - يونيفرت": 0.0,
    "طاقة عربية": 0.0,
    "عبر المحيطات للمقاولات": 0.0,
    "غاز مصر": 0.0,
    "فاركو للأدوية": 0.0,
    "فوري للمدفوعات الإلكترونية": 0.0,
    "كيما - الصناعات الكيماوية": 0.0,
    "مدينة مصر للإسكان": 0.0,
    "مجموعة إيـفـإى جـي هيرميس": 0.0,
    "مجموعة طلعت مصطفى": 23.81,
    "مطاحن مصر الوسطى": 0.0,
    "مطاحن ومخابز شمال القاهرة": 0.0,
    "مصر الجديدة للإسكان": 0.0,
    "مصر لإنتاج الأسمدة - موبكو": 0.0,
    "مصر للألومنيوم": 0.0,
    "مصرف أبوظبي الإسلامي": 55.62
}

def get_graham_value(name):
    """جلب قيمة جراهام من القاموس"""
    val = GRAHAM_VALUES.get(name, 0.0)
    return val if val > 0.0 else None

# القراءة التلقائية من Streamlit Secrets كخيار احتياطي
default_token = st.secrets.get("TELEGRAM_TOKEN", "")
default_chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")

# إعدادات التنبيهات في الشريط الجانبي
st.sidebar.header("⚙️ إعدادات إشعارات الموبايل (تليجرام)")
TELEGRAM_TOKEN = st.sidebar.text_input("أدخل Token البوت:", value=default_token, type="password")
TELEGRAM_CHAT_ID = st.sidebar.text_input("أدخل Chat ID الخاص بك:", value=default_chat_id)

def send_telegram_alert(message):
    """دالة لإرسال رسالة فورية إلى هاتف المستخدم عبر تليجرام مباشرة من الخانات"""
    token = TELEGRAM_TOKEN if TELEGRAM_TOKEN else default_token
    chat_id = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else default_chat_id
    
    if token and chat_id:
        url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
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
    
    df['Vol_MA10'] = df['Volume'].rolling(window=10).mean()
    return df

tab1, tab2 = st.tabs(["🔍 فحص سهم تفصيلي + رسم بياني", "🏆 مسح وترتيب السوق الاحترافي"])

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
                    rsi = float(last_row['RSI_14'].squeezeتمام جداً، التسمية الدقيقة دايماً أفضل وأكثر احترافية وتليق بشغلك. 

تم تعديل المسميات في الكود بالكامل لتصبح **"قيمة جراهام"** (في الجداول والمتغيرات) بدلاً من "القيمة العادلة". إليك الكود الأساسي النهائي والمحدث:

```python
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

st.title("🦅 قناص البورصة المصرية (النسخة المتكاملة المقفلة ضد المخاطر)")
st.write("تم تقفيل الكود بمعايير صارمة: إضافة حد أدنى للفوليوم لحجب الأسهم الميتة، وفلاتر حماية من التضخم الحاد.")

# --- قاموس قيمة جراهام للأسهم (تحديث دوري) ---
GRAHAM_VALUES = {
    "أبو قير للأسمدة": 0.0,
    "أكرو مصر للشدات": 0.0,
    "أوراسكوم للاستثمار القابضة": 0.0,
    "أوراسكوم للتنمية مصر": 0.0,
    "أودن للاستثمارات المالية": 0.0,
    "إعمار مصر للتنمية": 0.0,
    "إي فاينانس للاستثمارات": 0.0,
    "إيديتا للصناعات الغذائية": 0.0,
    "ابن سينا فارما": 0.0,
    "الاسكندرية لأسمنت بورتلاند": 0.0,
    "الأسكندرية لتداول الحاويات": 0.0,
    "الأسكندرية للزيوت المعدنية - أموك": 0.0,
    "الاسماعيلية مصر للدواجن": 0.0,
    "البنك التجاري الدولي": 92.77,
    "التعمير والاستشارات الهندسية": 0.0,
    "الجوهرة - العز للسيراميك": 0.0,
    "الجيزة العامة للمقاولات": 0.0,
    "الشمس للإسكان والتعمير": 0.0,
    "الشرقية - إيسترن كومباني": 0.0,
    "الصعيد العامة للمقاولات": 0.0,
    "العبوات الطبية": 0.0,
    "العربية للأدوية": 0.0,
    "العز الدخيلة للصلب": 0.0,
    "القاهرة للإسكان والتعمير": 0.0,
    "القاهرة للدواجن": 0.0,
    "القلعة للاستشارات المالية": 0.0,
    "المطورون العرب القابضة": 0.0,
    "المصرية للاتصالات": 0.0,
    "المنصورة للدواجن": 0.0,
    "النيل للأدوية": 0.0,
    "الزيوت المستخلصة ومنتجاتها": 0.0,
    "السويدي إليكتريك": 38.27,
    "بالم هيلز للتعمير": 0.0,
    "بنك البركة مصر": 0.0,
    "بنك التعمير والإسكان": 0.0,
    "بنك فيصل الإسلامي - بالجنيه": 0.0,
    "بنك قناة السويس": 0.0,
    "بلتون المالية القابضة": 0.0,
    "جهينة للصناعات الغذائية": 0.0,
    "جي بي كورب": 0.0,
    "حديد عز": 0.0,
    "دومتي": 0.0,
    "راكتا لورق التعبئة": 0.0,
    "سيدي كرير للبتروكيماويات": 0.0,
    "شمال أفريقيا للاستثمار": 0.0,
    "صناع التغليف - يونيفرت": 0.0,
    "طاقة عربية": 0.0,
    "عبر المحيطات للمقاولات": 0.0,
    "غاز مصر": 0.0,
    "فاركو للأدوية": 0.0,
    "فوري للمدفوعات الإلكترونية": 0.0,
    "كيما - الصناعات الكيماوية": 0.0,
    "مدينة مصر للإسكان": 0.0,
    "مجموعة إيـفـإى جـي هيرميس": 0.0,
    "مجموعة طلعت مصطفى": 23.81,
    "مطاحن مصر الوسطى": 0.0,
    "مطاحن ومخابز شمال القاهرة": 0.0,
    "مصر الجديدة للإسكان": 0.0,
    "مصر لإنتاج الأسمدة - موبكو": 0.0,
    "مصر للألومنيوم": 0.0,
    "مصرف أبوظبي الإسلامي": 55.62
}

def get_graham_value(name):
    """جلب قيمة جراهام من القاموس"""
    return GRAHAM_VALUES.get(name, None)

# القراءة التلقائية من Streamlit Secrets كخيار احتياطي
default_token = st.secrets.get("TELEGRAM_TOKEN", "")
default_chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")

# إعدادات التنبيهات في الشريط الجانبي
st.sidebar.header("⚙️ إعدادات إشعارات الموبايل (تليجرام)")
TELEGRAM_TOKEN = st.sidebar.text_input("أدخل Token البوت:", value=default_token, type="password")
TELEGRAM_CHAT_ID = st.sidebar.text_input("أدخل Chat ID الخاص بك:", value=default_chat_id)

def send_telegram_alert(message):
    """دالة لإرسال رسالة فورية إلى هاتف المستخدم عبر تليجرام مباشرة من الخانات"""
    token = TELEGRAM_TOKEN if TELEGRAM_TOKEN else default_token
    chat_id = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else default_chat_id
    
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
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
    
    df['Vol_MA10'] = df['Volume'].rolling(window=10).mean()
    return df

tab1, tab2 = st.tabs(["🔍 فحص سهم تفصيلي + رسم بياني", "🏆 مسح وترتيب السوق الاحترافي"])

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
                    vol = float(last_row['Volume'].squeeze())
                    
                    is_new_cross = (prev_row['EMA9'] <= prev_row['EMA21']) and (ema9 > ema21)
                    
                    if is_new_cross and rsi < 52:
                        decision = "🚀 تأسيس مركز (بداية تقاطع ذهبي حقيقي من القاع)"
                        color = "#1abc9c"
                    elif rsi < 35 and mfi < 35:
                        decision = "🛒 تجميع في القاع (منطقة رخيصة جداً للمراقبة)"
                        color = "#3498db"
                    elif ema9 > ema21 and rsi < 70 and mfi < 80:
                        decision = "STRONG BUY ⚡ (اتجاه صاعد مستمر)"
                        color = "#2ecc71"
                    elif price >= upper or rsi >= 75 or mfi >= 85:
                        decision = "SELL / TAKE PROFIT 🚨 (تضخم مؤشرات حاد)"
                        color = "#e74c3c"
                    else:
                        decision = "HOLD ✋ (مراقبة)"
                        color = "#f39c12"
                    
                    st.markdown(f'<div style="background-color:{color}; padding:20px; border-radius:10px; text-align:center; margin-bottom:20px;"><h2 style="color:white; margin:0;">القرار الحالي لـ {ticker_input}: {decision}</h2></div>', unsafe_allow_html=True)
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("السعر الحالي", f"{price:.2f} ج.م")
                    c2.metric("مؤشر الزخم RSI", f"{rsi:.1f}")
                    c3.metric("مؤشر السيولة MFI", f"{mfi:.1f}")
                    c4.metric("حجم تداول اليوم (فوليوم)", f"{vol:,.0f}")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].squeeze(), name='سعر الإغلاق', line=dict(color='#1f77b4', width=2)))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'].squeeze(), name='EMA 9', line=dict(color='#2ca02c', dash='dot')))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'].squeeze(), name='EMA 21', line=dict(color='#d62728', dash='dash')))
                    fig.update_layout(template="plotly_dark", height=450)
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"حدث خطأ: {e}")

with tab2:
    st.subheader("📊 الفرز والترتيب المتقدم لأسهم السوق")
    
    if st.button("تشغيل الفرز والترتيب الاحترافي اللحظي 🚀"):
        fresh_cross_results = []
        bottom_accumulation_results = []
        short_term_trading = []
        long_term_investment = []
        
        progress_bar = st.progress(0)
        total_stocks = len(ALL_EGX_STOCKS)
        
        with st.spinner("جاري مسح الأسهم ورصد الفرص الصارمة..."):
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
                    vol_today = float(row['Volume'])
                    vol_ma10 = float(row['Vol_MA10'])
                    
                    if vol_today < 50000:
                        continue
                        
                    is_new_cross = (prev_row['EMA9'] <= prev_row['EMA21']) and (e9 > e21)
                    
                    momentum_score = 0
                    if e9 > e21: momentum_score += 40
                    if 50 <= m <= 70: momentum_score += 30
                    elif 35 <= m < 50: momentum_score += 15
                    elif m > 85: momentum_score -= 25
                    if 45 <= r <= 65: momentum_score += 20
                    elif r > 75: momentum_score -= 20
                    if u > l: momentum_score += ((u - p) / (u - l)) * 10
                    if vol_today > vol_ma10: momentum_score += 10
                    
                    if m > 85 or r > 78:
                        status = "🚨 تصريف / خروج (تضخم)"
                    elif momentum_score >= 70:
                        status = "⚡ STRONG BUY (شراء قوي)"
                    elif 50 <= momentum_score < 70:
                        status = "🟢 إيجابي (متوسط)"
                    else:
                        status = "🟡 HOLD (مراقبة)"
                    
                    # --- حساب قيمة جراهام وحالة السعر ---
                    fv = get_graham_value(name)
                    price_status = "لقطة (أرخص)" if (fv and p < fv) else "مبالغ فيه/عادل"
                    
                    data_entry = {
                        "النقاط الفنية والسيولة (من 100)": round(momentum_score, 1),
                        "اسم الشركة": name,
                        "الرمز البرمجي": ticker,
                        "قيمة جراهام": fv if fv else "N/A",
                        "حالة السعر": price_status,
                        "السعر الحالي (ج.م)": round(p, 2),
                        "مؤشر الزخم RSI": round(r, 1),
                        "مؤشر السيولة MFI": round(m, 1),
                        "فوليوم اليوم": f"{vol_today:,.0f}",
                        "متوسط فوليوم 10أيام": f"{vol_ma10:,.0f}",
                        "التقييم الفني": status
                    }
                    
                    if is_new_cross and r < 52:
                        data_entry["التقييم الفني"] = "✨ تأسيس مركز (قاع صاعد طازة)"
                        fresh_cross_results.append(data_entry)
                    
                    elif r < 35 and m < 35:
                        data_entry["التقييم الفني"] = "🛒 قاع تجميع (فرصة مراقبة صامتة)"
                        bottom_accumulation_results.append(data_entry)
                    
                    elif e9 > e21:
                        if vol_today > (vol_ma10 * 1.15) and 50 <= r <= 78:
                            data_entry["التقييم الفني"] = f"{status} [مضاربة لحظية]"
                            short_term_trading.append(data_entry)
                        else:
                            data_entry["التقييم الفني"] = f"{status} [استثمار مستقر]"
                            long_term_investment.append(data_entry)
                except:
                    continue
            
            st.success("تم التحديث النهائي والإغلاق الهندسي للرادار بنجاح! 🦅")
            
            # --- آلية الإرسال المعدلة لـ 5 فرص ---
            telegram_msg = "🦅 *تقرير قناص البورصة المصرية اللحظي* 🇪🇬\n\n"
            
            if fresh_cross_results:
                telegram_msg += "🌟 *أسهم تأسيس المركز (قاع صاعد):*\n"
                for item in fresh_cross_results[:5]: 
                    telegram_msg += f"- {item['اسم الشركة']} ({item['السعر الحالي (ج.م)']} ج.م)\n"
                telegram_msg += "\n"
                
            if long_term_investment:
                top_inv = pd.DataFrame(long_term_investment).sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False).head(5) 
                telegram_msg += "📈 *أقوى أسهم الاتجاه الصاعد المستقر:*\n"
                for _, row_inv in top_inv.iterrows():
                    telegram_msg += f"- {row_inv['اسم الشركة']} | السعر: {row_inv['السعر الحالي (ج.م)']} ج.م | النقاط: {row_inv['النقاط الفنية والسيولة (من 100)']}\n"
                telegram_msg += "\n"
                
            if short_term_trading:
                top_trade = pd.DataFrame(short_term_trading).sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False).head(5) 
                telegram_msg += "⚡ *أقوى أسهم المضاربة اللحظية وعزم السيولة:*\n"
                for _, row_tr in top_trade.iterrows():
                    telegram_msg += f"- {row_tr['اسم الشركة']} | السعر: {row_tr['السعر الحالي (ج.م)']} ج.م\n"
            
            # إرسال الرسالة الكاملة والملخصة مرة واحدة فقط
            send_telegram_alert(telegram_msg)
            
            # عرض الجداول على الشاشة
            st.markdown("### 🚀 أولاً: أسهم لقطت 'إشارة تأسيس مركز جديدة اليوم' (آمنة وصارمة، RSI < 52)")
            if fresh_cross_results:
                st.dataframe(pd.DataFrame(fresh_cross_results).sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False), use_container_width=True)
            else:
                st.info("لا توجد أسهم لقطت تقاطع ذهبي هادئ اليوم واستوفت شروط الفوليوم الحقيقي.")
                
            st.write("---")
            
            st.markdown("### 📥 ثانياً: رادار تصيد القيعان (أسهم رخيصة جداً في مناطق تجميع الحيتان 🐋)")
            if bottom_accumulation_results:
                st.dataframe(pd.DataFrame(bottom_accumulation_results).sort_values(by="مؤشر الزخم RSI", ascending=True), use_container_width=True)
            else:
                st.info("لا توجد أسهم حالياً في قيعان التشبع البيعي الحاد تحت 35 تنطبق عليها شروط الفوليوم الأمان.")
                
            st.write("---")
            
            st.markdown("### ⚡ ثالثاً: أسهم المضاربة اللحظية واليومية (سيولة ضخمة وعزم سريع محمي منممتاز جداً! التسمية الدقيقة بتفرق كتير في التحليل المالي. 

تم تعديل المسميات في الكود بالكامل، عشان الجدول والبيانات تعرض **"قيمة جراهام"** بدل "القيمة العادلة".

تقدر تنسخ الكود النهائي ده وتستبدله عندك:

```python
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

st.title("🦅 قناص البورصة المصرية (النسخة المتكاملة المقفلة ضد المخاطر)")
st.write("تم تقفيل الكود بمعايير صارمة: إضافة حد أدنى للفوليوم لحجب الأسهم الميتة، وفلاتر حماية من التضخم الحاد.")

# --- قاموس قيمة جراهام للأسهم (تحديث دوري) ---
GRAHAM_VALUES = {
    "أبو قير للأسمدة": 0.0,
    "أكرو مصر للشدات": 0.0,
    "أوراسكوم للاستثمار القابضة": 0.0,
    "أوراسكوم للتنمية مصر": 0.0,
    "أودن للاستثمارات المالية": 0.0,
    "إعمار مصر للتنمية": 0.0,
    "إي فاينانس للاستثمارات": 0.0,
    "إيديتا للصناعات الغذائية": 0.0,
    "ابن سينا فارما": 0.0,
    "الاسكندرية لأسمنت بورتلاند": 0.0,
    "الأسكندرية لتداول الحاويات": 0.0,
    "الأسكندرية للزيوت المعدنية - أموك": 0.0,
    "الاسماعيلية مصر للدواجن": 0.0,
    "البنك التجاري الدولي": 92.77,
    "التعمير والاستشارات الهندسية": 0.0,
    "الجوهرة - العز للسيراميك": 0.0,
    "الجيزة العامة للمقاولات": 0.0,
    "الشمس للإسكان والتعمير": 0.0,
    "الشرقية - إيسترن كومباني": 0.0,
    "الصعيد العامة للمقاولات": 0.0,
    "العبوات
