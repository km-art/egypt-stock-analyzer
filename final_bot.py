import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np

# إعدادات الصفحة
st.set_page_config(page_title="محلل البورصة المصرية الاحترافي 🇪🇬📈", layout="wide")

st.title("🦅 قناص البورصة المصرية (النسخة المتكاملة)")

# إعدادات التنبيهات
default_token = st.secrets.get("TELEGRAM_TOKEN", "")
default_chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_TOKEN = st.sidebar.text_input("أدخل Token البوت:", value=default_token, type="password")
TELEGRAM_CHAT_ID = st.sidebar.text_input("أدخل Chat ID الخاص بك:", value=default_chat_id)

def send_telegram_alert(message):
    token = TELEGRAM_TOKEN if TELEGRAM_TOKEN else default_token
    chat_id = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else default_chat_id
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload)

# قائمة الأسهم
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

def calculate_indicators(df):
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI_14'] = 100 - (100 / (1 + (gain / (loss + 0.00001))))
    return df

if st.button("تشغيل الفرز 🚀"):
    fresh, invest, trade = [], [], []
    all_data = yf.download(list(ALL_EGX_STOCKS.values()), period="60d", progress=False, group_by='ticker')
    
    for name, ticker in ALL_EGX_STOCKS.items():
        try:
            df = calculate_indicators(all_data[ticker].dropna())
            r, p, e9, e21 = float(df['RSI_14'].iloc[-1]), float(df['Close'].iloc[-1]), float(df['EMA9'].iloc[-1]), float(df['EMA21'].iloc[-1])
            score = round(e9 + r, 1) # مؤشر بسيط للترتيب
            entry = {"اسم الشركة": name, "السعر الحالي (ج.م)": round(p, 2), "النقاط": score}
            
            if df['EMA9'].iloc[-4] <= df['EMA21'].iloc[-4] and e9 > e21 and r < 52: fresh.append(entry)
            elif e9 > e21: invest.append(entry)
            else: trade.append(entry)
        except: continue

    # التقرير المرسل لتليجرام
    telegram_msg = "🦅 *تقرير قناص البورصة المصرية اللحظي* 🇪🇬\n\n"
    if fresh:
        telegram_msg += "🌟 *أسهم تأسيس المركز (قاع صاعد):*\n"
        for item in sorted(fresh, key=lambda x: x['النقاط'], reverse=True)[:5]:
            telegram_msg += f"- {item['اسم الشركة']} ({item['السعر الحالي (ج.م)']} ج.م) | النقاط: {item['النقاط']}\n"
        telegram_msg += "\n"
    if invest:
        telegram_msg += "📈 *أقوى أسهم الاتجاه الصاعد المستقر:*\n"
        for item in sorted(invest, key=lambda x: x['النقاط'], reverse=True)[:5]:
            telegram_msg += f"- {item['اسم الشركة']} | السعر: {item['السعر الحالي (ج.م)']} ج.م | النقاط: {item['النقاط']}\n"
        telegram_msg += "\n"
    if trade:
        telegram_msg += "⚡ *أقوى أسهم المضاربة اللحظية وعزم السيولة:*\n"
        for item in sorted(trade, key=lambda x: x['النقاط'], reverse=True)[:5]:
            telegram_msg += f"- {item['اسم الشركة']} | السعر: {item['السعر الحالي (ج.م)']} ج.م\n"
    
    send_telegram_alert(telegram_msg)
    st.success("تم إرسال التقرير لتليجرام بنجاح! 🦅")
