import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import numpy as np

# إعدادات الصفحة
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

st.title("🦅 قناص البورصة المصرية (النسخة المتكاملة)")

# إعدادات التنبيهات
st.sidebar.header("⚙️ إعدادات إشعارات تليجرام")
default_token = st.secrets.get("TELEGRAM_TOKEN", "")
default_chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_TOKEN = st.sidebar.text_input("Token البوت:", value=default_token, type="password")
TELEGRAM_CHAT_ID = st.sidebar.text_input("Chat ID:", value=default_chat_id)

def send_telegram_alert(message):
    token = TELEGRAM_TOKEN if TELEGRAM_TOKEN else default_token
    chat_id = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else default_chat_id
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload)
        except Exception as e:
            st.sidebar.error(f"فشل إرسال التنبيه: {e}")

# القائمة الكاملة للأسهم
ALL_EGX_STOCKS = {
    "السويدي إليكتريك": "SWDY.CA", "البنك التجاري الدولي": "COMI.CA", "مصرف أبوظبي الإسلامي": "ADIB.CA",
    "مجموعة طلعت مصطفى": "TMGH.CA", "بلتون المالية القابضة": "BTFH.CA", "فوري للمدفوعات الإلكترونية": "FWRY.CA",
    "إي فاينانس للاستثمارات": "EFIH.CA", "أبو قير للأسمدة": "ABUK.CA", "مصر لإنتاج الأسمدة - موبكو": "MFPC.CA",
    "سيدي كرير للبتروكيماويات": "SKPC.CA", "الأسكندرية لتداول الحاويات": "ALCN.CA", "المصرية للاتصالات": "ETEL.CA",
    "إعمار مصر للتنمية": "EMFD.CA", "مدينة مصر للإسكان": "MASR.CA", "مصر الجديدة للإسكان": "HELI.CA",
    "بالم هيلز للتعمير": "PHDC.CA", "أوراسكوم للتنمية مصر": "ORHD.CA", "مجموعة إيـفـإى جـي هيرميس": "HRHO.CA",
    "جي بي كورب": "GBCO.CA", "القلعة للاستشارات المالية": "CCAP.CA", "حديد عز": "ESRS.CA",
    "مصر للألومنيوم": "EGAL.CA", "الصعيد العامة للمقاولات": "UEGC.CA", "جهينة للصناعات الغذائية": "JUFO.CA",
    "إيديتا للصناعات الغذائية": "EFID.CA", "دومتي": "DOMT.CA", "الشرقية - إيسترن كومباني": "EAST.CA",
    "ابن سينا فارما": "ISPH.CA", "الأسكندرية للزيوت المعدنية - أموك": "AMOC.CA", "كيما": "EGCH.CA",
    "الاسماعيلية مصر للدواجن": "ISMA.CA", "القاهرة للدواجن": "POUL.CA", "المنصورة للدواجن": "MPCO.CA",
    "بنك البركة مصر": "SAUD.CA", "بنك فيصل الإسلامي": "FAIT.CA", "بنك التعمير والإسكان": "HDBK.CA"
}

def calculate_indicators(df):
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
    df['MFI_14'] = 100 - (100 / (1 + (pos_flow.rolling(window=14).sum() / (neg_flow.rolling(window=14).sum() + 0.00001))))
    df['Vol_MA10'] = df['Volume'].rolling(window=10).mean()
    return df

tab1, tab2 = st.tabs(["🔍 فحص سهم", "🏆 مسح السوق"])

with tab2:
    if st.button("تشغيل الفرز الاحترافي 🚀"):
        fresh_cross_results, bottom_accumulation_results = [], []
        short_term_trading, long_term_investment = [], []
        
        tickers_list = list(ALL_EGX_STOCKS.values())
        all_data = yf.download(tickers_list, period="60d", progress=False, group_by='ticker')
        
        for name, ticker in ALL_EGX_STOCKS.items():
            stock_df = all_data[ticker].dropna(how='all')
            if len(stock_df) < 25: continue
            stock_df = calculate_indicators(stock_df)
            row = stock_df.iloc[-1]
            prev_row = stock_df.iloc[-4]
            
            p, r, m, vol_today = float(row['Close']), float(row['RSI_14']), float(row['MFI_14']), float(row['Volume'])
            if vol_today < 50000: continue
            
            # التصنيف
            if (prev_row['EMA9'] <= prev_row['EMA21']) and (row['EMA9'] > row['EMA21']) and r < 52:
                fresh_cross_results.append({"اسم الشركة": name, "السعر الحالي (ج.م)": round(p, 2)})
            elif r < 35 and m < 35:
                bottom_accumulation_results.append({"اسم الشركة": name, "السعر الحالي (ج.م)": round(p, 2), "مؤشر الزخم RSI": round(r, 1)})
            elif row['EMA9'] > row['EMA21']:
                entry = {"اسم الشركة": name, "السعر الحالي (ج.م)": round(p, 2), "النقاط الفنية": 75}
                if vol_today > row['Vol_MA10'] * 1.15: short_term_trading.append(entry)
                else: long_term_investment.append(entry)

        # --- رسالة التليجرام ---
        msg = "🦅 *تقرير قناص البورصة المصرية اللحظي* 🇪🇬\n\n"
        if fresh_cross_results:
            msg += "🌟 *أسهم تأسيس المركز (قاع صاعد):*\n"
            for item in fresh_cross_results[:5]: msg += f"- {item['اسم الشركة']} ({item['السعر الحالي (ج.م)']} ج.م)\n"
            msg += "\n"
        if bottom_accumulation_results:
            msg += "📥 *رادار تصيد القيعان (تجميع الحيتان 🐋):*\n"
            for item in bottom_accumulation_results[:5]: msg += f"- {item['اسم الشركة']} | السعر: {item['السعر الحالي (ج.م)']} ج.م | RSI: {item['مؤشر الزخم RSI']}\n"
            msg += "\n"
        if long_term_investment:
            msg += "📈 *أقوى أسهم الاتجاه الصاعد المستقر:*\n"
            for item in long_term_investment[:5]: msg += f"- {item['اسم الشركة']} | السعر: {item['السعر الحالي (ج.م)']} ج.م\n"
            msg += "\n"
        if short_term_trading:
            msg += "⚡ *أقوى أسهم المضاربة اللحظية وعزم السيولة:*\n"
            for item in short_term_trading[:5]: msg += f"- {item['اسم الشركة']} | السعر: {item['السعر الحالي (ج.م)']} ج.م\n"
        
        send_telegram_alert(msg)
        
        # --- عرض البيانات في Streamlit ---
        st.success("تم إرسال التقرير للتليجرام، وإليك التفاصيل:")
        if fresh_cross_results:
            st.subheader("🌟 تأسيس المركز")
            st.dataframe(pd.DataFrame(fresh_cross_results), use_container_width=True)
        if bottom_accumulation_results:
            st.subheader("📥 رادار تصيد القيعان (الحيتان 🐋)")
            st.dataframe(pd.DataFrame(bottom_accumulation_results), use_container_width=True)
        if long_term_investment:
            st.subheader("📈 الاستثمار المستقر")
            st.dataframe(pd.DataFrame(long_term_investment), use_container_width=True)
        if short_term_trading:
            st.subheader("⚡ المضاربة اللحظية")
            st.dataframe(pd.DataFrame(short_term_trading), use_container_width=True)
