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
# 3. دوال التحليل المالي والفني
# ==========================================
@st.cache_data(ttl=300)
def get_fundamentals(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        return {"pe": info.get("trailingPE"), "roe": info.get("returnOnEquity")}
    except:
        return {"pe": None, "roe": None}

@st.cache_data(ttl=300)
def get_stock_analysis(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period="100d")
        if hist.empty or len(hist) < 25:
            return None
        
        fund = get_fundamentals(ticker_symbol)
        
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi = 100 - (100 / (1 + (gain / (loss + 0.00001))))
        rsi_val = round(rsi.iloc[-1], 1)
        
        ema9 = hist['Close'].ewm(span=9, adjust=False).mean()
        ema21 = hist['Close'].ewm(span=21, adjust=False).mean()
        ema9_val = ema9.iloc[-1]
        ema21_val = ema21.iloc[-1]
        price = round(hist['Close'].iloc[-1], 2)
        
        typical_price = (hist['High'] + hist['Low'] + hist['Close']) / 3
        raw_money_flow = typical_price * hist['Volume']
        typical_price_diff = typical_price.diff()
        pos_flow = pd.Series(np.where(typical_price_diff > 0, raw_money_flow, 0), index=hist.index)
        neg_flow = pd.Series(np.where(typical_price_diff < 0, raw_money_flow, 0), index=hist.index)
        mfi = 100 - (100 / (1 + (pos_flow.rolling(14).sum() / (neg_flow.rolling(14).sum() + 0.00001))))
        mfi_val = round(mfi.iloc[-1], 1)
        
        vol_today = int(hist['Volume'].iloc[-1])
        vol_ma10 = int(hist['Volume'].rolling(10).mean().iloc[-1])
        prev_ema9 = ema9.iloc[-3]
        prev_ema21 = ema21.iloc[-3]
        
        # النقاط الفنية
        momentum_score = 0
        if ema9_val > ema21_val: momentum_score += 40
        if 50 <= mfi_val <= 70: momentum_score += 30
        elif mfi_val > 85: momentum_score -= 25
        if 45 <= rsi_val <= 65: momentum_score += 20
        elif rsi_val > 75: momentum_score -= 20
        if vol_today > vol_ma10: momentum_score += 10
        
        priority = 0
        category = "🟡 مراقبة"
        rec_type = "hold"
        
        is_new_cross = (prev_ema9 <= prev_ema21) and (ema9_val > ema21_val)
        
        # تصنيف السهم وتحديد الأهداف (Targets)
        target = round(price * 1.03, 2)
        stop_loss = round(price * 0.97, 2)
        
        if is_new_cross and rsi_val < 52:
            category = "🚀 تأسيس مركز"
            rec_type = "buy"
            priority = 100
            target = round(price * 1.08, 2)
            stop_loss = round(price * 0.95, 2)
        elif rsi_val < 35 and mfi_val < 35:
            category = "🛒 قاع تجميع"
            rec_type = "buy"
            priority = 95
            target = round(price * 1.08, 2)
            stop_loss = round(price * 0.93, 2)
        elif ema9_val > ema21_val and vol_today > (vol_ma10 * 1.15) and 50 <= rsi_val <= 78:
            category = "⚡ مضاربة لحظية"
            rec_type = "buy"
            priority = 85
            target = round(price * 1.04, 2)
            stop_loss = round(price * 0.96, 2)
        elif ema9_val > ema21_val:
            category = "📈 استثمار مستقر"
            rec_type = "buy"
            priority = 70
            target = round(price * 1.06, 2)
            stop_loss = round(price * 0.96, 2)
        elif rsi_val > 75:
            category = "🔴 جني أرباح/بيع"
            rec_type = "sell"
            priority = 90
            target = round(price * 1.00, 2)
            stop_loss = round(price * 1.00, 2)
            
        return {
            "ticker": ticker_symbol.replace(".CA", ""),
            "price": price,
            "rsi": rsi_val,
            "mfi": mfi_val,
            "momentum_score": momentum_score,
            "category": category,
            "rec_type": rec_type,
            "priority": priority,
            "target": target,
            "stop_loss": stop_loss,
            "pe": fund["pe"],
            "roe": fund["roe"]
        }
    except:
        return None

# ==========================================
# 4. مسح السوق
# ==========================================
st.title("🦅 قناص البورصة المصرية - الهدف ووقف الخسارة")
st.caption(f"آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
st.write("---")

st.info("⏳ جاري مسح 220 سهماً لتحديد الأهداف...")
progress_bar = st.progress(0)
buy_signals = []
sell_signals = []
all_signals = []

for index, ticker in enumerate(ALL_EGX_STOCKS):
    progress_bar.progress((index + 1) / len(ALL_EGX_STOCKS))
    data = get_stock_analysis(ticker)
    if data:
        all_signals.append(data)
        if data['rec_type'] == "buy": buy_signals.append(data)
        elif data['rec_type'] == "sell": sell_signals.append(data)

progress_bar.empty()

# ==========================================
# 5. عرض الكروت الملونة (مع الهدف ووقف الخسارة)
# ==========================================
tab1, tab2 = st.tabs(["🟢 صفقات الشراء (الأهداف)", "🔴 صفقات البيع"])

with tab1:
    st.subheader(f"🟢 {len(buy_signals)} فرصة شراء متاحة")
    if buy_signals:
        sorted_buy = sorted(buy_signals, key=lambda x: x['priority'], reverse=True)
        for i in range(0, len(sorted_buy), 5):
            batch = sorted_buy[i:i+5]
            cols = st.columns(5)
            for col, data in zip(cols, batch):
                with col:
                    st.markdown(f"""
                    <div class='box-buy'>
                        <h3 style='margin:0;'>{data['ticker']}</h3>
                        <small>{data['category']}</small>
                        <div class='stock-price'>{data['price']} ج.م</div>
                        <div>🎯 الهدف: {data['target']} ج.م</div>
                        <div style='background: rgba(0,0,0,0.1); padding: 5px; border-radius: 5px; margin-top: 10px;'>
                            ⛔ وقف خسارة: {data['stop_loss']} ج.م
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    else: st.info("لا توجد فرص شراء حالياً.")

with tab2:
    st.subheader(f"🔴 {len(sell_signals)} فرصة بيع (جني أرباح)")
    if sell_signals:
        sorted_sell = sorted(sell_signals, key=lambda x: x['priority'], reverse=True)
        for i in range(0, len(sorted_sell), 5):
            batch = sorted_sell[i:i+5]
            cols = st.columns(5)
            for col, data in zip(cols, batch):
                with col:
                    st.markdown(f"""
                    <div class='box-sell'>
                        <h3 style='margin:0;'>{data['ticker']}</h3>
                        <small>{data['category']}</small>
                        <div class='stock-price'>{data['price']} ج.م</div>
                    </div>
                    """, unsafe_allow_html=True)
    else: st.info("لا توجد فرص بيع حالياً.")

st.write("---")

# ==========================================
# 6. الأقسام الخمسة (جداول البيانات مع P/E و ROE)
# ==========================================
st.title("📊 التحليل المتقدم: الجداول التفصيلية")
if all_signals:
    df_all = pd.DataFrame(all_signals)
    display_cols = ["ticker", "price", "rsi", "mfi", "momentum_score", "category", "pe", "roe"]
    
    st.markdown("### 🚀 أولاً: إشارة تأسيس مركز")
    df_cross = df_all[df_all['priority'] == 100]
    st.dataframe(df_cross[display_cols].sort_values(by="momentum_score", ascending=False), use_container_width=True, hide_index=True) if not df_cross.empty else st.info("لا توجد نتائج.")
    
    st.markdown("### 📥 ثانياً: رادار تصيد القيعان")
    df_bottom = df_all[df_all['priority'] == 95]
    st.dataframe(df_bottom[display_cols].sort_values(by="rsi", ascending=True), use_container_width=True, hide_index=True) if not df_bottom.empty else st.info("لا توجد نتائج.")
    
    st.markdown("### ⚡ ثالثاً: المضاربة اللحظية")
    df_short = df_all[df_all['priority'] == 85]
    st.dataframe(df_short[display_cols].sort_values(by="momentum_score", ascending=False), use_container_width=True, hide_index=True) if not df_short.empty else st.info("لا توجد نتائج.")
    
    st.markdown("### 📈 رابعاً: الاستثمار المستقر")
    df_long = df_all[df_all['priority'] == 70]
    st.dataframe(df_long[display_cols].sort_values(by="momentum_score", ascending=False), use_container_width=True, hide_index=True) if not df_long.empty else st.info("لا توجد نتائج.")
    
    st.markdown("### 🎯 خامساً: التوصية الشاملة")
    st.dataframe(df_all[display_cols + ["priority"]].sort_values(by="momentum_score", ascending=False), use_container_width=True, hide_index=True)

st.caption("⚠️ هذه أداة مساعدة وليست توصية استثمارية ملزمة.")
