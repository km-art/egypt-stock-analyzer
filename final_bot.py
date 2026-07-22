import time
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import numpy as np

# إعدادات الصفحة والمظهر العام
st.set_page_config(page_title="المحلل المالي العالمي الاحترافي 🌍📈", layout="wide")

st.title("🦅 القناص المالي المتعدد الأسواق (EGX - US - UAE)")
st.write("النسخة المتكاملة: تدعم البورصة المصرية، الأسهم الأمريكية، والأسواق الإماراتية بمعايير حماية صارمة ضد التضخم.")

# إعدادات عامة قابلة للتعديل
BATCH_SIZE = 30       # عدد الأسهم في كل طلب تحميل لتفادي حظر Yahoo Finance
BATCH_DELAY = 1.5     # ثواني انتظار بين الدفعات
CROSS_LOOKBACK = 3    # عدد أيام الخلف لاكتشاف التقاطع الجديد

# القراءة التلقائية من Streamlit Secrets
try:
    default_token = st.secrets.get("TELEGRAM_TOKEN", "")
    default_chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
except Exception:
    default_token = ""
    default_chat_id = ""

# إعدادات التنبيهات في الشريط الجانبي
st.sidebar.header("⚙️ إعدادات إشعارات الموبايل (تليجرام)")
TELEGRAM_TOKEN = st.sidebar.text_input("أدخل Token البوت:", value=default_token, type="password")
TELEGRAM_CHAT_ID = st.sidebar.text_input("أدخل Chat ID الخاص بك:", value=default_chat_id)

st.sidebar.markdown("---")
st.sidebar.header("🌍 اختيار السوق المالي")
market_choice = st.sidebar.selectbox(
    "حدد السوق المطلوب تحليله:",
    ["البورصة المصرية (EGX) 🇪🇬", "الأسهم الأمريكية (US) 🇺🇸", "الأسهم الإماراتية (UAE) 🇦🇪"]
)

# تحديد القواميس والعملة بناءً على السوق المختار
if "المصرية" in market_choice:
    CURRENCY = "ج.م"
    DEFAULT_MIN_VOL = 50000
    ALL_STOCKS = {
        "A Capital Holding": "ACAP.CA", "AJWA For Food Industries": "AJWA.CA",
        "Abu Qir Fertilizers": "ABUK.CA", "Commercial International Bank": "COMI.CA",
        " Talaat Moustafa Group": "TMGH.CA", "Elsewedy Electric": "SWDY.CA",
        "Eastern Company": "EAST.CA", "Fawry": "FWRY.CA", "Ezz Steel": "ESRS.CA",
        "EFG Hermes": "HRHO.CA", "Palm Hills": "PHDC.CA", "SODIC": "OCDI.CA",
        "Madinet Masr": "MASR.CA", "Juhayna": "JUFO.CA", "Orascom Construction": "ORAS.CA",
        " Sidi Kerir Petrochemicals": "SKPC.CA", "Abou Donia / Domt": "DOMT.CA",
        "Misr Production Fertilisers (MOPCO)": "MFPC.CA", "Alexandria Containers": "ALCN.CA"
    }
    TICKER_SECTOR = {
        "COMI.CA": "بنوك", "TMGH.CA": "عقاري", "SWDY.CA": "تصنيع", "EAST.CA": "استهلاكي",
        "ABUK.CA": "تصنيع", "ALCN.CA": "تصنيع", "ORAS.CA": "تصنيع", "FWRY.CA": "تكنولوجيا",
        "PHDC.CA": "عقاري", "ESRS.CA": "تصنيع", "HRHO.CA": "مالي غير مصرفي", "JUFO.CA": "استهلاكي",
        "OCDI.CA": "عقاري", "MASR.CA": "عقاري", "SKPC.CA": "تصنيع", "DOMT.CA": "استهلاكي",
        "MFPC.CA": "تصنيع", "ACAP.CA": "مالي غير مصرفي", "AJWA.CA": "استهلاكي"
    }
elif "الأمريكية" in market_choice:
    CURRENCY = "$"
    DEFAULT_MIN_VOL = 500000  # السيولة الأمريكية أضخم بكثير
    ALL_STOCKS = {
        "Apple Inc.": "AAPL", "Microsoft Corporation": "MSFT", "NVIDIA Corporation": "NVDA",
        "Amazon.com Inc.": "AMZN", "Alphabet Inc. (Google)": "GOOGL", "Meta Platforms": "META",
        "Tesla Inc.": "TSLA", "Berkshire Hathaway": "BRK-B", "JPMorgan Chase": "JPM",
        "Visa Inc.": "V", "Johnson & Johnson": "JNJ", "Exxon Mobil": "XOM",
        "Walmart Inc.": "WMT", "Mastercard": "MA", "Netflix Inc.": "NFLX",
        "Advanced Micro Devices (AMD)": "AMD", "Intel Corporation": "INTC", "Cisco Systems": "CSCO"
    }
    TICKER_SECTOR = {
        "AAPL": "تكنولوجيا", "MSFT": "تكنولوجيا", "NVDA": "تكنولوجيا", "AMZN": "استهلاكي",
        "GOOGL": "تكنولوجيا", "META": "تكنولوجيا", "TSLA": "تصنيع", "BRK-B": "مالي غير مصرفي",
        "JPM": "بنوك", "V": "مالي غير مصرفي", "JNJ": "رعاية صحية", "XOM": "طاقة",
        "WMT": "استهلاكي", "MA": "مالي غير مصرفي", "NFLX": "تكنولوجيا", "AMD": "تكنولوجيا",
        "INTC": "تكنولوجيا", "CSCO": "تكنولوجيا"
    }
else:  # الإماراتية
    CURRENCY = "د.إ"
    DEFAULT_MIN_VOL = 100000
    ALL_STOCKS = {
        "Emaar Properties (DFM)": "EMAAR.DU",
        "Emirates NBD (DFM)": "ENBD.DU",
        "Dubai Islamic Bank (DFM)": "DIB.DU",
        "Emaar Development (DFM)": "EMAARDEV.DU",
        "Aramex (DFM)": "ARMX.DU",
        "Dubai Investments (DFM)": "DIC.DU",
        "First Abu Dhabi Bank (ADX)": "FAB.AD",
        "International Holding Company (ADX)": "IHC.AD",
        "Multiply Group (ADX)": "MULTIPLY.AD",
        "Aldar Properties (ADX)": "ALDAR.AD",
        "Abu Dhabi Commercial Bank (ADX)": "ADCB.AD",
        "ADNOC Distribution (ADX)": "ADNOCDIST.AD"
    }
    TICKER_SECTOR = {
        "EMAAR.DU": "عقاري", "ENBD.DU": "بنوك", "DIB.DU": "بنوك", "EMAARDEV.DU": "عقاري",
        "ARMX.DU": "خدمات لوجستية", "DIC.DU": "استثمار", "FAB.AD": "بنوك",
        "IHC.AD": "استثمار متنوع", "MULTIPLY.AD": "استثمار متنوع", "ALDAR.AD": "عقاري",
        "ADCB.AD": "بنوك", "ADNOCDIST.AD": "طاقة"
    }

# ترتيب الأسهم حسب الرمز
ALL_STOCKS = dict(sorted(ALL_STOCKS.items(), key=lambda kv: kv[1]))

def send_telegram_alert(message):
    token = TELEGRAM_TOKEN if TELEGRAM_TOKEN else default_token
    chat_id = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else default_chat_id

    if not (token and chat_id):
        return False, "لم يتم إدخال Token أو Chat ID - تم تخطي الإرسال."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200 and resp.json().get("ok"):
            return True, "تم إرسال التنبيه على تليجرام بنجاح ✅"
        return False, f"فشل الإرسال (كود {resp.status_code})"
    except Exception as e:
        return False, f"خطأ في الاتصال: {e}"

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

@st.cache_data(ttl=600, show_spinner=False)
def fetch_fundamentals(ticker: str) -> dict:
    empty = {
        "pe_ratio": None, "pb_ratio": None, "roe_%": None,
        "profit_margin_%": None, "debt_to_equity": None,
        "dividend_yield_%": None, "revenue_growth_%": None,
        "eps": None, "book_value_per_share": None,
    }
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        return empty

    if not info or len(info) < 5:
        return empty

    def pct(x):
        return round(x * 100, 2) if isinstance(x, (int, float)) else None

    return {
        "pe_ratio": info.get("trailingPE"),
        "pb_ratio": info.get("priceToBook"),
        "roe_%": pct(info.get("returnOnEquity")),
        "profit_margin_%": pct(info.get("profitMargins")),
        "debt_to_equity": info.get("debtToEquity"),
        "dividend_yield_%": pct(info.get("dividendYield")),
        "revenue_growth_%": pct(info.get("revenueGrowth")),
        "eps": info.get("trailingEps"),
        "book_value_per_share": info.get("bookValue"),
    }

def compute_graham(eps, bvps, price):
    if eps is None or bvps is None or eps <= 0 or bvps <= 0:
        return {"graham_number": None, "graham_upside_%": None, "undervalued_per_graham": None}

    graham_number = (22.5 * eps * bvps) ** 0.5
    upside_pct = round((graham_number / price - 1) * 100, 1) if price else None
    return {
        "graham_number": round(graham_number, 2),
        "graham_upside_%": upside_pct,
        "undervalued_per_graham": price < graham_number,
    }

def graham_from_fundamentals(fundamentals: dict, price: float) -> dict:
    eps = fundamentals.get("eps")
    bvps = fundamentals.get("book_value_per_share")
    eps_estimated = False
    bvps_estimated = False

    pe = fundamentals.get("pe_ratio")
    pb = fundamentals.get("pb_ratio")

    if eps is None and pe is not None and pe > 0:
        eps = price / pe
        eps_estimated = True
    if bvps is None and pb is not None and pb > 0:
        bvps = price / pb
        bvps_estimated = True

    result = compute_graham(eps=eps, bvps=bvps, price=price)
    result["eps"] = round(eps, 3) if eps is not None else None
    result["book_value_per_share"] = round(bvps, 3) if bvps is not None else None
    result["eps_estimated"] = eps_estimated
    result["bvps_estimated"] = bvps_estimated
    return result

def score_fundamentals(f: dict) -> int:
    score = 50
    pe = f.get("pe_ratio")
    if pe is not None and pe > 0:
        if pe < 15: score += 10
        elif pe > 30: score -= 10

    pm = f.get("profit_margin_%")
    if pm is not None:
        if pm > 15: score += 10
        elif pm < 0: score -= 15

    roe = f.get("roe_%")
    if roe is not None:
        if roe > 15: score += 10
        elif roe < 5: score -= 5

    return max(0, min(100, score))

@st.cache_data(ttl=300, show_spinner=False)
def fetch_single_stock(ticker: str, period: str = "100d"):
    return yf.download(ticker, period=period, progress=False, group_by='ticker')

@st.cache_data(ttl=300, show_spinner=False)
def fetch_batch_data(tickers_tuple: tuple, period: str = "60d"):
    tickers = list(tickers_tuple)
    all_frames = {}
    failed = []

    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        try:
            data = yf.download(batch, period=period, progress=False, group_by='ticker', threads=True)
        except Exception:
            failed.extend(batch)
            continue

        for t in batch:
            try:
                df_t = data[t] if len(batch) > 1 else data
                if df_t is not None and not df_t.dropna(how='all').empty:
                    all_frames[t] = df_t
                else:
                    failed.append(t)
            except Exception:
                failed.append(t)

        if i + BATCH_SIZE < len(tickers):
            time.sleep(BATCH_DELAY)

    still_failed = []
    if failed:
        for t in failed:
            try:
                df_t = yf.download(t, period=period, progress=False, group_by='ticker')
                if df_t is not None and not df_t.dropna(how='all').empty:
                    all_frames[t] = df_t
                else:
                    still_failed.append(t)
            except Exception:
                still_failed.append(t)
            time.sleep(0.3)
        failed = still_failed

    return all_frames, failed

tab1, tab2 = st.tabs(["🔍 فحص سهم تفصيلي + رسم بياني", "🏆 مسح وترتيب السوق الاحترافي"])

with tab1:
    st.subheader(f"اختر سهماً من {market_choice} لتحليله الفني والمالي")
    col_input1, col_input2 = st.columns([2, 1])
    with col_input1:
        selected_stock = st.selectbox("اختر من القائمة:", list(ALL_STOCKS.keys()))
        ticker_input = ALL_STOCKS[selected_stock]
    with col_input2:
        manual_ticker = st.text_input("أو اكتب رمزاً مخصصاً يدوياً:", value="").strip().upper()
        if manual_ticker:
            ticker_input = manual_ticker

    if st.button("تحليل السهم ورسم المنحنى ⚡"):
        with st.spinner("جاري جلب البيانات..."):
            try:
                df = fetch_single_stock(ticker_input, period="100d")
                if not df.empty:
                    df = calculate_indicators(df)
                    last_row = df.iloc[-1]
                    prev_row = df.iloc[-CROSS_LOOKBACK]
                    
                    price = float(last_row['Close'].squeeze())
                    ema9 = float(last_row['EMA9'].squeeze())
                    ema21 = float(last_row['EMA21'].squeeze())
                    rsi = float(last_row['RSI_14'].squeeze())
                    mfi = float(last_row['MFI_14'].squeeze())
                    upper = float(last_row['Upper_Band'].squeeze())
                    vol = float(last_row['Volume'].squeeze())
                    
                    is_new_cross = (prev_row['EMA9'] <= prev_row['EMA21']) and (ema9 > ema21)
                    
                    if is_new_cross and rsi < 52:
                        decision = "🚀 تأسيس مركز (بداية تقاطع ذهبي حقيقي)"
                        color = "#1abc9c"
                    elif rsi < 35 and mfi < 35:
                        decision = "🛒 تجميع في القاع (منطقة رخيصة للمراقبة)"
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
                    c1.metric("السعر الحالي", f"{price:.2f} {CURRENCY}")
                    c2.metric("مؤشر الزخم RSI", f"{rsi:.1f}")
                    c3.metric("مؤشر السيولة MFI", f"{mfi:.1f}")
                    c4.metric("حجم تداول اليوم", f"{vol:,.0f}")

                    # التحليل المالي الأساسي
                    fundamentals = fetch_fundamentals(ticker_input)
                    fund_score = score_fundamentals(fundamentals)

                    st.markdown("##### 💰 التحليل المالي الأساسي")
                    f1, f2, f3, f4 = st.columns(4)
                    pe_display = f"{fundamentals['pe_ratio']:.2f}" if fundamentals.get("pe_ratio") else "غير متاح"
                    roe_display = f"{fundamentals['roe_%']:.1f}%" if fundamentals.get("roe_%") is not None else "غير متاح"
                    pm_display = f"{fundamentals['profit_margin_%']:.1f}%" if fundamentals.get("profit_margin_%") is not None else "غير متاح"
                    f1.metric("مكرر الربحية P/E", pe_display)
                    f2.metric("العائد على حقوق الملكية ROE", roe_display)
                    f3.metric("هامش الربح", pm_display)
                    f4.metric("الدرجة المالية (من 100)", fund_score)

                    # قاعدة جراهام
                    graham = graham_from_fundamentals(fundamentals, price)
                    st.markdown("##### 📐 قاعدة جراهام للسعر العادل")
                    g1, g2, g3 = st.columns(3)
                    graham_display = f"{graham['graham_number']:.2f} {CURRENCY}" if graham["graham_number"] else "غير متاح"
                    upside_display = f"{graham['graham_upside_%']:+.1f}%" if graham["graham_upside_%"] is not None else "—"
                    verdict_display = (
                        "✅ تحت السعر العادل" if graham["undervalued_per_graham"] is True
                        else "❌ فوق السعر العادل" if graham["undervalued_per_graham"] is False
                        else "غير متاح"
                    )
                    g1.metric("رقم جراهام (السعر العادل)", graham_display)
                    g2.metric("الفرق عن السعر الحالي", upside_display)
                    g3.metric("الحكم", verdict_display)

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].squeeze(), name='سعر الإغلاق', line=dict(color='#1f77b4', width=2)))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'].squeeze(), name='EMA 9', line=dict(color='#2ca02c', dash='dot')))
                    fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'].squeeze(), name='EMA 21', line=dict(color='#d62728', dash='dash')))
                    fig.update_layout(template="plotly_dark", height=450)
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"حدث خطأ: {e}")

with tab2:
    st.subheader(f"📊 مسح وترتيب سوق {market_choice}")
    include_fundamentals_scan = st.checkbox(
        "💰 تضمين التحليل المالي الأساسي + رقم جراهام (أبطأ نسبياً لأنه يطلب بيانات إضافية)",
        value=False,
    )

    fcol1, fcol2 = st.columns(2)
    with fcol1:
        available_sectors = sorted(set(TICKER_SECTOR.values()))
        selected_sectors_scan = st.multiselect(
            "🏢 فلتر القطاع (سيفه فارغ لعرض كل القطاعات)",
            options=available_sectors,
            default=[],
        )
    with fcol2:
        min_liquidity_scan = st.checkbox(
            f"💧 استبعاد الأسهم الضعيفة (فوليوم تفوق الحد الأدنى المناسب للسوق)",
            value=False,
        )

    if st.button("تشغيل المسح الشامل والترتيب اللحظي 🚀"):
        fresh_cross_results = []
        bottom_accumulation_results = []
        short_term_trading = []
        long_term_investment = []
        
        progress_bar = st.progress(0)
        total_stocks = len(ALL_STOCKS)
        
        with st.spinner(f"جاري مسح أسهم السوق المختار على دفعات..."):
            tickers_list = list(ALL_STOCKS.values())
            all_data, failed_tickers = fetch_batch_data(tuple(tickers_list), period="60d")

            skipped_count = 0
            for idx, (name, ticker) in enumerate(ALL_STOCKS.items()):
                progress_bar.progress((idx + 1) / total_stocks)
                if ticker not in all_data:
                    skipped_count += 1
                    continue
                try:
                    stock_df = all_data[ticker].dropna(how='all')
                    if stock_df.empty or len(stock_df) < 25:
                        skipped_count += 1
                        continue
                        
                    stock_df = calculate_indicators(stock_df)
                    row = stock_df.iloc[-1]
                    prev_row = stock_df.iloc[-CROSS_LOOKBACK]
                    
                    p = float(row['Close'])
                    e9 = float(row['EMA9'])
                    e21 = float(row['EMA21'])
                    r = float(row['RSI_14'])
                    m = float(row['MFI_14'])
                    u = float(row['Upper_Band'])
                    l = float(row['Lower_Band'])
                    vol_today = float(row['Volume'])
                    vol_ma10 = float(row['Vol_MA10'])
                    
                    if vol_today < 10000:
                        continue

                    avg_trade_value = p * vol_ma10
                    if min_liquidity_scan and avg_trade_value < (DEFAULT_MIN_VOL * p):
                        continue

                    sector = TICKER_SECTOR.get(ticker, "غير مصنف")
                    if selected_sectors_scan and sector not in selected_sectors_scan:
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
                    
                    data_entry = {
                        "النقاط الفنية (من 100)": round(momentum_score, 1),
                        "اسم الشركة": name,
                        "الرمز البرمجي": ticker,
                        "القطاع": sector,
                        f"السعر ({CURRENCY})": round(p, 2),
                        "مؤشر الزخم RSI": round(r, 1),
                        "مؤشر السيولة MFI": round(m, 1),
                        "فوليوم اليوم": f"{vol_today:,.0f}",
                        "التقييم الفني": status
                    }

                    if include_fundamentals_scan:
                        fundamentals = fetch_fundamentals(ticker)
                        fund_score = score_fundamentals(fundamentals)
                        combined_score = round(0.6 * momentum_score + 0.4 * fund_score, 1)
                        data_entry["الدرجة المالية"] = fund_score
                        data_entry["الدرجة الشاملة"] = combined_score
                        graham = graham_from_fundamentals(fundamentals, p)
                        data_entry["رقم جراهام"] = graham["graham_number"]
                        data_entry["فرق جراهام %"] = graham["graham_upside_%"]
                    
                    if is_new_cross and r < 52:
                        data_entry["التقييم الفني"] = "✨ تأسيس مركز (قاع صاعد)"
                        fresh_cross_results.append(data_entry)
                    elif r < 35 and m < 35:
                        data_entry["التقييم الفني"] = "🛒 قاع تجميع"
                        bottom_accumulation_results.append(data_entry)
                    elif e9 > e21:
                        if vol_today > (vol_ma10 * 1.15) and 50 <= r <= 78:
                            short_term_trading.append(data_entry)
                        else:
                       [cite: 1]    long_term_investment.append(data_entry)
                except Exception:
                    continue
            
            st.success("تم الانتهاء من فحص السوق بنجاح! 🦅")
            
            # عرض الجداول
            st.markdown("### 🚀 أولاً: أسهم إشارة تأسيس المركز (قاع صاعد طازة)")
            if fresh_cross_results:
                st.dataframe(pd.DataFrame(fresh_cross_results).sort_values(by="النقاط الفنية (من 100)", ascending=False), use_container_width=True)
            else:
                st.info("لا توجد أسهم حققت شروط التقاطع الذهبي الهادئ في هذا المسح.")
                
            st.markdown("### 📥 ثانياً: رادار تصيد القيعان (مناطق التجميع)")
            if bottom_accumulation_results:
                st.dataframe(pd.DataFrame(bottom_accumulation_results), use_container_width=True)
            else:
                st.info("لا توجد أسهم في مناطق التشبع البيعي الحاد حالياً.")
                
            st.markdown("### ⚡ ثالثاً: أسهم المضاربة اللحظية وعزم السيولة")
            if short_term_trading:
                st.dataframe(pd.DataFrame(short_term_trading), use_container_width=True)
            else:
                st.info("لا توجد أسهم مضاربة نشطة مستوفية للشروط.")

            st.markdown("### 📈 رابعاً: أسهم الاتجاه الصاعد المستقر")
            if long_term_investment:
                st.dataframe(pd.DataFrame(long_term_investment), use_container_width=True)
