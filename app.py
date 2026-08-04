import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# ==========================================
# 1. إعدادات الصفحة والتنسيق
# ==========================================
st.set_page_config(page_title="بورصي - التحليل اليومي", layout="wide", page_icon="📈")

# تنسيق CSS (لون الخلفية والأزرار)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Tajawal', sans-serif;
        text-align: right;
        direction: rtl;
    }
    .card-number { font-size: 32px; font-weight: bold; margin: 10px 0; }
    .box-buy { background-color: #4CAF50; color: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    .box-sell { background-color: #f44336; color: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    .box-hold { background-color: #FFC107; color: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    .stock-price { font-size: 24px; font-weight: bold; margin: 10px 0; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. قائمة ضخمة بكل أسهم البورصة المصرية (EGX)
# ==========================================
ALL_EGX_STOCKS = [
    "ACAP.CA", "AJWA.CA", "ASCM.CA", "ACTF.CA", "AFDI.CA", "ATLC.CA", "KRDI.CA", "AXPH.CA",
    "AFMC.CA", "AMES.CA", "SPIN.CA", "AMER.CA", "ALUM.CA", "ACAMD.CA", "EALR.CA", "EEII.CA",
    "AMIA.CA", "RREI.CA", "ARVA.CA", "ACGC.CA", "AIHC.CA", "AIDC.CA", "ARCC.CA", "ASPI.CA",
    "ALRA.CA", "BINV.CA", "BONY.CA", "CICH.CA", "CIRA.CA", "CAED.CA", "COSG.CA", "CSAG.CA",
    "CPME.CA", "CLHO.CA", "CFGH.CA", "CNFN.CA", "COPR.CA", "CRST.CA", "CIEB.CA", "DCCC.CA",
    "DTPP.CA", "DEIN.CA", "SUGR.CA", "DSCW.CA", "DGTZ.CA", "EDFM.CA", "MFSC.CA", "EPCO.CA",
    "EASB.CA", "EFIC.CA", "EGBE.CA", "IRON.CA", "MPRC.CA", "MOED.CA", "EGTS.CA", "EGSA.CA",
    "ETRS.CA", "EHDR.CA", "EPPK.CA", "KWIN.CA", "ELNA.CA", "EOSB.CA", "SPHT.CA", "ELWA.CA",
    "OBRI.CA", "KABO.CA", "ELEC.CA", "EXPA.CA", "FAITA.CA", "FERC.CA", "GMCI.CA", "GPIM.CA",
    "GTEX.CA", "GDWA.CA", "GSSC.CA", "AALR.CA", "PRCL.CA", "GIHD.CA", "BIOC.CA", "GGRN.CA",
    "GPPL.CA", "GTWL.CA", "GOUR.CA", "GRCA.CA", "CCRS.CA", "ENGC.CA", "ICID.CA", "IFAP.CA",
    "ICLE.CA", "ISMQ.CA", "IDRE.CA", "INFI.CA", "KZPC.CA", "CPCI.CA", "LCSW.CA", "LUTS.CA",
    "MIPH.CA", "MTIE.CA", "MCRO.CA", "MOIL.CA", "MMAT.CA", "MAAL.CA", "MPCI.CA", "MENA.CA",
    "WCDF.CA", "MEGM.CA", "MBSC.CA", "MCQE.CA", "MICH.CA", "MHOT.CA", "ATQA.CA", "MOSC.CA",
    "MOIN.CA", "NAHO.CA", "NARE.CA", "NCCW.CA", "NHPS.CA", "NDRL.CA", "NAPR.CA", "MILS.CA",
    "NEDA.CA", "NINH.CA", "OFH.CA", "OLFI.CA", "OCPH.CA", "ORAS.CA", "ORWE.CA", "EBSC.CA",
    "PRDC.CA", "POCO.CA", "PHGC.CA", "PRMH.CA", "PHTV.CA", "QNBE.CA", "RACC.CA", "RAYA.CA",
    "AREH.CA", "RTVC.CA", "ROTO.CA", "RUBX.CA", "SDTI.CA", "SIPC.CA", "SMFR.CA", "SEIG.CA",
    "SEIGA.CA", "SNFC.CA", "SCEM.CA", "OCDI.CA", "SAIB.CA", "SCFM.CA", "SVCE.CA", "SPMD.CA",
    "SCTS.CA", "TALM.CA", "TANM.CA", "RMDA.CA", "CERA.CA", "ADPC.CA", "UBEE.CA", "TRTO.CA",
    "ANFI.CA", "APSW.CA", "UNIT.CA", "UEFM.CA", "VLMRA.CA", "VLMR.CA", "VALU.CA", "WKOL.CA",
    "ZMID.CA", "ABUK.CA", "ACRO.CA", "ODIN.CA", "OIH.CA", "ORHD.CA", "EMFD.CA", "EFIH.CA",
    "EFID.CA", "ISPH.CA", "ALCN.CA", "AMOC.CA", "ALEX.CA", "ISMA.CA", "COMI.CA", "DAPH.CA",
    "ECAP.CA", "GGCC.CA", "ZEOT.CA", "SWDY.CA", "EAST.CA", "ELSH.CA", "UEGC.CA", "MEPA.CA",
    "ADCI.CA", "IRAX.CA", "ELKA.CA", "POUL.CA", "CCAP.CA", "ETEL.CA", "ARAB.CA", "MPCO.CA",
    "NIPH.CA", "PHDC.CA", "BTFH.CA", "SAUD.CA", "HDBK.CA", "FAIT.CA", "CANA.CA", "JUFO.CA",
    "GBCO.CA", "ESRS.CA", "DOMT.CA", "RAKT.CA", "SKPC.CA", "NATI.CA", "UNIP.CA", "TAQA.CA",
    "GOCE.CA", "EGAS.CA", "PHAR.CA", "FWRY.CA", "EGCH.CA", "HRHO.CA", "TMGH.CA", "MASR.CA",
    "HELI.CA", "MFPC.CA", "EGAL.CA", "ADIB.CA", "CEFM.CA", "MNSF.CA"
]

# ==========================================
# 3. دوال التحليل الفني والمالي
# ==========================================
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
    return df

def get_stock_analysis(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period="60d")
        if hist.empty:
            return None
        
        df = calculate_indicators(hist)
        last = df.iloc[-1]
        
        price = round(last['Close'], 2)
        rsi = round(last['RSI_14'], 1)
        ema9 = round(last['EMA9'], 2)
        ema21 = round(last['EMA21'], 2)
        volume = int(last['Volume'])
        
        recommendation = "🟡 انتظار"
        rec_color = "box-hold"
        target_price = round(price * 1.03, 2)
        stop_loss = round(price * 0.97, 2)
        
        if rsi < 35:
            recommendation = "🛒 تجميع (منطقة رخيصة)"
            rec_color = "box-buy"
            target_price = round(price * 1.05, 2)
            stop_loss = round(price * 0.95, 2)
        elif rsi > 75 or price >= last['Upper_Band']:
            recommendation = "🔴 بيع/جني أرباح"
            rec_color = "box-sell"
            target_price = price
            stop_loss = price
        elif ema9 > ema21 and 40 < rsi < 65:
            recommendation = "🟢 شراء (اتجاه صاعد)"
            rec_color = "box-buy"
            target_price = round(price * 1.05, 2)
            stop_loss = round(price * 0.98, 2)
            
        return {
            "ticker": ticker_symbol.replace(".CA", ""),
            "price": price, "rsi": rsi,
            "recommendation": recommendation, "rec_color": rec_color,
            "target": target_price, "stop": stop_loss, "volume": volume
        }
    except:
        return None

# ==========================================
# 4. عرض الواجهة (قائمة ديناميكية)
# ==========================================
st.title("📊 بورصي - التحليل اليومي لجميع الأسهم")
st.caption(f"آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
st.write("---")

# شريط البحث (للبحث عن سهم معين)
search_query = st.text_input("🔍 ابحث عن سهم (مثل: COMI, TMGH, SWDY):", "").strip().upper()

# تحديد القائمة التي سنعرضها
if search_query:
    # إذا كتب المستخدم حرفاً، نبحث عن السهم
    display_stocks = [s for s in ALL_EGX_STOCKS if search_query in s]
    if not display_stocks:
        st.warning(f"لم يتم العثور على سهم باسم '{search_query}'")
        display_stocks = ALL_EGX_STOCKS[:5] # لو مفيش نتيجة، نعرض عشوائياً
else:
    # لو مفيش بحث، نعرض كل الأسهم (ولكن Streamlit قد يتأخر لو أكثر من 200 سهم)
    # هنا سنعرضهم بالكامل ولكن بشكل تدريجي
    display_stocks = ALL_EGX_STOCKS

st.subheader("🏆 نتائج المسح")
st.info("🔄 جاري تحميل بيانات الأسهم (كل صف يعرض 5 أسهم). قد يستغرق التحميل 30 ثانية لأول مرة.")

# نظام التقسيم: عرض 5 أسهم في كل صف تلقائياً
cols_per_row = 5
for i in range(0, len(display_stocks), cols_per_row):
    batch = display_stocks[i:i + cols_per_row]
    cols = st.columns(cols_per_row)
    
    for col, ticker in zip(cols, batch):
        with col:
            data = get_stock_analysis(ticker)
            if data:
                st.markdown(f"""
                <div class='{data['rec_color']}'>
                    <h3 style='margin:0;'>{data['ticker']}</h3>
                    <small>{data['recommendation']}</small>
                    <div class='stock-price'>{data['price']} ج.م</div>
                    <div>🎯 الهدف: {data['target']} ج.م</div>
                    <div style='background: rgba(0,0,0,0.1); padding: 5px; border-radius: 5px; margin-top: 10px;'>
                        ⛔ وقف خسارة: {data['stop']} ج.م
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.caption(f"RSI: {data['rsi']} | فوليوم: {data['volume']:,}")
            else:
                st.error(f"تعذر جلب بيانات {ticker.replace('.CA','')}")

st.write("---")
st.info("💡 التحليل يعتمد على مؤشرات القوة النسبية (RSI) والمتوسطات المتحركة (EMA). هذه أداة مساعدة وليست توصية استثمارية ملزمة.")
