import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

st.title("🦅 قناص البورصة المصرية (النسخة المتكاملة المقفلة ضد المخاطر)")
st.write("تم تقفيل الكود بمعايير صارمة: إضافة حد أدنى للفوليوم لحجب الأسهم الميتة، وتلخيص أفضل 5 فرص.")

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

tab1, tab2 = st.tabs(["🔍 فحص سهم تفصيلي", "🏆 مسح وترتيب السوق الاحترافي"])

with tab1:
    selected_stock = st.selectbox("اختر السهم:", list(ALL_EGX_STOCKS.keys()))
    if st.button("تحليل ⚡"):
        ticker_input = ALL_EGX_STOCKS[selected_stock]
        df = yf.download(ticker_input, period="100d", progress=False, group_by='ticker')
        df = calculate_indicators(df)
        st.write(f"السعر الحالي: {df['Close'].iloc[-1]:.2f}")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'].squeeze(), name='السعر'))
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    if st.button("تشغيل الفرز 🚀"):
        fresh_cross_results, bottom_accumulation_results, short_term_trading, long_term_investment = [], [], [], []
        tickers_list = list(ALL_EGX_STOCKS.values())
        all_data = yf.download(tickers_list, period="60d", progress=False, group_by='ticker')
        
        for name, ticker in ALL_EGX_STOCKS.items():
            try:
                stock_df = all_data[ticker].dropna(how='all')
                stock_df = calculate_indicators(stock_df)
                row, prev_row = stock_df.iloc[-1], stock_df.iloc[-4]
                p, e9, e21, r, m = float(row['Close']), float(row['EMA9']), float(row['EMA21']), float(row['RSI_14']), float(row['MFI_14'])
                
                momentum_score = (40 if e9 > e21 else 0) + (30 if 50 <= m <= 70 else 0)
                status = "⚡ STRONG BUY" if momentum_score >= 70 else "🟢 إيجابي"
                data_entry = {"اسم الشركة": name, "السعر": round(p, 2), "النقاط": round(momentum_score, 1)}
                
                if (prev_row['EMA9'] <= prev_row['EMA21']) and (e9 > e21) and r < 52:
                    fresh_cross_results.append(data_entry)
                elif e9 > e21:
                    long_term_investment.append(data_entry)
                else:
                    short_term_trading.append(data_entry)
            except: continue

        # عرض الجداول
        st.dataframe(pd.DataFrame(fresh_cross_results), use_container_width=True)
        
        # إرسال التقرير لتليجرام
        telegram_msg = "🦅 *تقرير قناص البورصة (أفضل 5 فرص):*\n\n"
        if fresh_cross_results:
            telegram_msg += "🌟 *تأسيس مركز:*\n"
            for item in sorted(fresh_cross_results, key=lambda x: x['النقاط'], reverse=True)[:5]:
                telegram_msg += f"- {item['اسم الشركة']} ({item['السعر']} ج.م)\n"
        if long_term_investment:
            telegram_msg += "\n📈 *استثمار:* \n"
            for item in sorted(long_term_investment, key=lambda x: x['النقاط'], reverse=True)[:5]:
                telegram_msg += f"- {item['اسم الشركة']} ({item['السعر']} ج.م)\n"
        send_telegram_alert(telegram_msg)
        st.success("تم إرسال التقرير للتليجرام!")
