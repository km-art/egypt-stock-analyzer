import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# ==========================================
# 1. إعدادات الصفحة والتنسيق
# ==========================================
st.set_page_config(page_title="بورصي - التحليل المتكامل", layout="wide", page_icon="🦅")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Tajawal', sans-serif;
        text-align: right;
        direction: rtl;
    }
    .card-number { font-size: 32px; font-weight: bold; margin: 10px 0; }
    .box-buy { background-color: #2ecc71; color: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    .box-sell { background-color: #e74c3c; color: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    .box-hold { background-color: #FFC107; color: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    .stock-price { font-size: 24px; font-weight: bold; margin: 10px 0; }
    /* تنسيق الجداول */
    .stDataFrame { font-size: 14px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. قائمة بكل أسهم البورصة المصرية (EGX)
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
# 3. دوال التحليل (مأخوذة من ملفك المتقدم)
# ==========================================
def calculate_indicators(df):
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI_14'] = 100 - (100 / (1 + (gain / (loss + 0.00001))))
    
    # مؤشر السيولة MFI
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    raw_money_flow = typical_price * df['Volume']
    typical_price_diff = typical_price.diff()
    pos_flow = pd.Series(np.where(typical_price_diff > 0, raw_money_flow, 0), index=df.index)
    neg_flow = pd.Series(np.where(typical_price_diff < 0, raw_money_flow, 0), index=df.index)
    pos_mf14 = pos_flow.rolling(window=14).sum()
    neg_mf14 = neg_flow.rolling(window=14).sum()
    df['MFI_14'] = 100 - (100 / (1 + (pos_mf14 / (neg_mf14 + 0.00001))))
    
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['STD20'] = df['Close'].rolling(window=20).std()
    df['Upper_Band'] = df['MA20'] + (2 * df['STD20'])
    df['Lower_Band'] = df['MA20'] - (2 * df['STD20'])
    
    df['Vol_MA10'] = df['Volume'].rolling(window=10).mean()
    return df

def get_analysis(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period="100d")
        if hist.empty or len(hist) < 25:
            return None
        
        df = calculate_indicators(hist)
        last = df.iloc[-1]
        prev = df.iloc[-3] # للمقارنة بالتقاطع
        
        price = round(last['Close'], 2)
        rsi = round(last['RSI_14'], 1)
        mfi = round(last['MFI_14'], 1)
        ema9 = round(last['EMA9'], 2)
        ema21 = round(last['EMA21'], 2)
        vol_today = int(last['Volume'])
        vol_ma10 = int(last['Vol_MA10'])
        
        # مؤشرات مهمة
        is_new_cross = (prev['EMA9'] <= prev['EMA21']) and (ema9 > ema21)
        avg_trade_value = price * vol_ma10
        
        # حساب النقاط الفنية
        momentum_score = 0
        if ema9 > ema21: momentum_score += 40
        if 50 <= mfi <= 70: momentum_score += 30
        elif 35 <= mfi < 50: momentum_score += 15
        elif mfi > 85: momentum_score -= 25
        if 45 <= rsi <= 65: momentum_score += 20
        elif rsi > 75: momentum_score -= 20
        if vol_today > vol_ma10: momentum_score += 10
        
        # تحديد الفئات الخمسة
        category = None
        priority = 0
        
        # 1. تأسيس مركز
        if is_new_cross and rsi < 52:
            category = "🚀 تأسيس مركز"
            priority = 100
        # 2. قاع تجميع
        elif rsi < 35 and mfi < 35:
            category = "🛒 قاع تجميع"
            priority = 95
        # 3. مضاربة
        elif ema9 > ema21 and vol_today > (vol_ma10 * 1.15) and 50 <= rsi <= 78:
            category = "⚡ مضاربة لحظية"
            priority = 85
        # 4. استثمار طويل
        elif ema9 > ema21:
            category = "📈 استثمار مستقر"
            priority = 70
        else:
            category = "🟡 مراقبة"
            priority = 0
            
        return {
            "اسم الشركة": ticker_symbol.replace(".CA", ""),
            "الرمز البرمجي": ticker_symbol,
            "السعر الحالي": price,
            "مؤشر الزخم RSI": rsi,
            "مؤشر السيولة MFI": mfi,
            "فوليوم اليوم": f"{vol_today:,}",
            "متوسط فوليوم 10أيام": f"{vol_ma10:,}",
            "متوسط قيمة التداول (تقريبي)": f"{avg_trade_value:,.0f}",
            "النقاط الفنية والسيولة (من 100)": momentum_score,
            "التقييم الفني": category,
            "الفئة": category,
            "القطاع": "غير مصنف", # يمكن إضافته لاحقاً
            "العملة": "EGP",
            "الأولوية": priority
        }
    except:
        return None

# ==========================================
# 4. محرك المسح والعرض
# ==========================================
st.title("🦅 قناص البورصة المصرية - النسخة المتكاملة")
st.caption(f"آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
st.write("---")

# زر التشغيل
if st.button("🚀 بدء مسح السوق بالكامل (تحليل 220 سهم)"):
    with st.spinner('جاري مسح السوق وتصنيف الأسهم... قد يستغرق هذا 40 ثانية'):
        progress_bar = st.progress(0)
        
        results = []
        for idx, ticker in enumerate(ALL_EGX_STOCKS):
            progress_bar.progress((idx + 1) / len(ALL_EGX_STOCKS))
            data = get_analysis(ticker)
            if data:
                results.append(data)
        
        progress_bar.empty()
        
        if results:
            df = pd.DataFrame(results)
            
            # تصنيف النتائج
            df_cross = df[df["التقييم الفني"] == "🚀 تأسيس مركز"].sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False)
            df_bottom = df[df["التقييم الفني"] == "🛒 قاع تجميع"].sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False)
            df_short = df[df["التقييم الفني"] == "⚡ مضاربة لحظية"].sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False)
            df_long = df[df["التقييم الفني"] == "📈 استثمار مستقر"].sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False)
            
            # عرض الأقسام الخمسة (كما طلبت بالضبط)
            st.markdown("### 🚀 أولاً: أسهم لقطت 'إشارة تأسيس مركز جديدة اليوم' (آمنة وصارمة، RSI < 52)")
            if not df_cross.empty:
                st.dataframe(df_cross, use_container_width=True, hide_index=True)
            else: st.info("لا توجد أسهم لقطت تقاطع ذهبي هادئ اليوم.")
            
            st.write("---")
            
            st.markdown("### 📥 ثانياً: رادار تصيد القيعان (أسهم رخيصة جداً في مناطق تجميع الحيتان 🐋)")
            if not df_bottom.empty:
                st.dataframe(df_bottom, use_container_width=True, hide_index=True)
            else: st.info("لا توجد أسهم حالياً في قيعان التشبع البيعي الحاد.")
            
            st.write("---")
            
            st.markdown("### ⚡ ثالثاً: أسهم المضاربة اللحظية واليومية (سيولة ضخمة وعزم سريع محمي من التضخم)")
            if not df_short.empty:
                st.dataframe(df_short, use_container_width=True, hide_index=True)
            else: st.info("لا توجد أسهم مستوفية لشروط الحركات المضاربية النشطة حالياً.")
            
            st.write("---")
            
            st.markdown("### 📈 رابعاً: أسهم الاستثمار والاتجاه الصاعد المستقر (طويل الأجل وآمن)")
            if not df_long.empty:
                st.dataframe(df_long, use_container_width=True, hide_index=True)
            else: st.info("لا توجد أسهم مستوفية لشروط الاستثمار المستقر حالياً.")
            
            st.write("---")
            
            # القسم الخامس: التوصية النهائية لجميع الأسهم
            st.markdown("### 🎯 خامساً: التوصية النهائية (فني + مالي مع بعض)")
            st.caption("مرتبة حسب النقاط الفنية + السيولة (من الأعلى للأدنى) لجميع الأسهم النشطة")
            if not df.empty:
                # حذف الأعمدة غير الضرورية للعرض النهائي
                display_cols = ["اسم الشركة", "الرمز البرمجي", "السعر الحالي", "التقييم الفني", "النقاط الفنية والسيولة (من 100)", "فوليوم اليوم"]
                st.dataframe(df.sort_values(by="النقاط الفنية والسيولة (من 100)", ascending=False)[display_cols], use_container_width=True, hide_index=True)
                
                # إحصائيات سريعة
                vc1, vc2, vc3, vc4 = st.columns(4)
                vc1.metric("🚀 تأسيس مراكز", len(df_cross))
                vc2.metric("🛒 قيعان تجميع", len(df_bottom))
                vc3.metric("⚡ مضاربة", len(df_short))
                vc4.metric("📈 استثمار", len(df_long))
            else:
                st.warning("لم يتم العثور على أي بيانات.")
        else:
            st.error("حدث خطأ أثناء جلب البيانات.")
else:
    st.info("👆 اضغط على زر 'بدء مسح السوق بالكامل' لبدء التحليل المتقدم.")

st.write("---")
st.caption("⚠️ تنبيه: هذه الأداة للتحليل الفني والمعرفي فقط. ليست توصية استثمارية ملزمة. يرجى مراجعة مستشار مالي قبل اتخاذ القرارات.")
