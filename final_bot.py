import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

st.title("🏆 نظام المسح الفني الاحترافي مع التنبيهات الفورية")
st.write("تم دمج نظام تنبيهات تليجرام الذكي لإرسال رسائل فورية لهاتفك عند وصول أي سهم لمستويات التضخم السعري أو جني الأرباح.")

# --- إعدادات التنبيهات (املا بياناتك هنا أو من الـ Sidebar) ---
st.sidebar.header("⚙️ إعدادات إشعارات الموبايل (تليجرام)")
TELEGRAM_TOKEN = st.sidebar.text_input("أدخل Token البوت:", value="", type="password")
TELEGRAM_CHAT_ID = st.sidebar.text_input("أدخل Chat ID الخاص بك:", value="")

def send_telegram_alert(message):
    """دالة لإرسال رسالة فورية إلى هاتف المستخدم عبر تليجرام"""
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload)
        except Exception as e:
            st.sidebar.error(f"فشل إرسال التنبيه: {e}")

# القائمة الكاملة لرموز أسهم السوق المصري (EGX)
ALL_EGX_STOCKS = {
    "السويدي إليكتريك": "SWDY.CA", "البنك التجاري الدولي": "COMI.CA", "مصرف أبوظبي الإسلامي": "ADIB.CA",
    "مجموعة طلعت مستطفى": "TMGH.CA", "بلتون المالية القابضة": "BTFH.CA", "فوري للمدفوعات الإلكترونية": "FWRY.CA",
    "إي فاينانس للاستثمارات": "EFIH.CA", "أبو قير للأسمدة": "ABUK.CA", "مصر لإنتاج الأسمدة - موبكو": "MFPC.CA",
    "سيدي كرير للبتروكيماويات": "SKPC.CA", "الأسكندرية لتداول الحاويات": "ALCN.CA", "المصرية للاتصالات": "ETEL.CA",
    "إعمار مصر للتنمية": "EMFD.CA", "مدينة مصر للإسكان": "MASR.CA", "مصر الجديدة للإسكان": "HELI.CA",
    "بالم هيلز للتعمير": "PHDC.CA", "أوراسكوم للتنمية مصر": "ORHD.CA", "مجموعة إيـفـإى جـي هيرميس": "HRHO.CA",
    "جي بي كورب": "GBCO.CA", "القلعة للاستشارات المالية": "CCAP.CA", "حديد عز": "ESRS.CA"
}

ALL_EGX_STOCKS = dict(sorted(ALL_EGX_STOCKS.items()))

tab1, tab2 = st.tabs(["🔍 فحص سهم تفصيلي + رسم بياني", "🏆 مسح وترتيب السوق الاحترافي"])

# --- التبويب الأول: فحص سهم تفصيلي ---
with tab1:
    st.subheader("اختر سهمك المفضل لتحليله ورسم بياناته بالتفصيل")
    selected_stock = st.selectbox("اختر من قائمة السوق الكاملة:", list(ALL_EGX_STOCKS.keys()))
    ticker_input = ALL_EGX_STOCKS[selected_stock]

    if st.button("تحليل السهم ورسم المنحنى ⚡"):
        with st.spinner("جاري جلب البيانات..."):
            try:
                df = yf.download(ticker_input, period="100d", progress=False)
                if not df.empty:
                    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(-1)
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
                    price = float(last_row['Close'])
                    rsi = float(last_row['RSI_14'])
                    upper = float(last_row['Upper_Band'])
                    
                    # تنبيه فوري إذا تم فحص السهم يدوياً وتبين تضخمه
                    if price >= upper or rsi >= 73:
                        alert_msg = f"⚠️ *تنبيه تضخم سعري يدوياً*\nالسهم: {selected_stock} ({ticker_input})\nالسعر الحالي: {price:.2f} ج.م\nمؤشر RSI: {rsi:.1f}\nالسهم ضرب في سقف البولينجر أو تضخم! ينصح بجني الأرباح."
                        send_telegram_alert(alert_msg)
                        st.error("🚨 إشارة بيع وتضخم! تم إرسال إشعار لهاتفك.")
                    else:
                        st.success("السهم في نطاق طبيعي أو تجميعي.")
            except Exception as e:
                st.error(f"حدث خطأ: {e}")

# --- التبويب الثاني: مسح وترتيب السوق الاحترافي ---
with tab2:
    st.subheader("📊 ترتيب فرز المحترفين + مسح الإشارات اللحظية")
    
    if st.button("تشغيل الفرز والترتيب الاحترافي اللحظي 🚀"):
        scan_results = []
        progress_bar = st.progress(0)
        total_stocks = len(ALL_EGX_STOCKS)
        
        tickers_list = list(ALL_EGX_STOCKS.values())
        all_data = yf.download(tickers_list, period="50d", progress=False, group_by='ticker')
        
        for idx, (name, ticker) in enumerate(ALL_EGX_STOCKS.items()):
            progress_bar.progress((idx + 1) / total_stocks)
            try:
                stock_df = all_data[ticker].dropna(how='all') if len(tickers_list) > 1 else all_data
                if stock_df.empty or len(stock_df) < 25: continue
                    
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
                p, e9, e21, r, u, l = float(row['Close']), float(row['EMA9']), float(row['EMA21']), float(row['RSI_14']), float(row['Upper_Band']), float(row['Lower_Band'])
                
                momentum_score = 0
                if e9 > e21: momentum_score += 40 + min(((e9 - e21) / e21) * 100, 10)
                if 45 <= r <= 60: momentum_score += 30
                elif 30 <= r < 45: momentum_score += 15
                elif 60 < r < 70: momentum_score += 10
                else: momentum_score -= 20
                    
                if u > l: momentum_score += ((u - p) / (u - l)) * 20
                
                # فرز الحالات وإطلاق التنبيه التلقائي
                if momentum_score >= 70:
                    status = "🟢 شراء قوي جداً (فرصة ذهبية)"
                elif 50 <= momentum_score < 70:
                    status = "🟢 شراء مضاربي (عزم صاعد)"
                elif 30 <= momentum_score < 50:
                    status = "🟡 HOLD (احتفاظ / حيادي)"
                elif 10 <= momentum_score < 30:
                    status = "🔴 بيع / تخفيف كميات"
                    # إرسال تنبيه في حالة التضخم وبدء البيع
                    send_telegram_alert(f"🚨 *تنبيه خروج وتخفيف* 🚨\nالسهم: {name} ({ticker})\nالسعر الحالي: {p:.2f} ج.م\nمؤشر RSI: {r:.1f}\nالوضع: بدأ السهم في التضخم السعري وفقدان العزم!")
                else:
                    status = "🔴 خروج فوري (قرب القمة/كسر اتجاه)"
                    send_telegram_alert(f"🔥 *إشارة خروج عاجلة وقصوى* 🔥\nالسهم: {name} ({ticker})\nالسعر الحالي: {p:.2f} ج.م\nمؤشر RSI: {r:.1f}\nالوضع: تضخم شرائي خطير جداً وجني أرباح حتمي!")
                    
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
            result_df = pd.DataFrame(scan_results).sort_values(by="النقاط الفنية (من 100)", ascending=False)
            st.success("تم الترتيب! تحقق من هاتف تليجرام إذا كانت هناك أسهم متضخمة.")
            st.dataframe(result_df, use_container_width=True)
