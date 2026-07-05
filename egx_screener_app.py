import pandas as pd
import streamlit as st

from egx_screener import EGX_TICKERS, run_screener

st.set_page_config(page_title="EGX Stock Screener", layout="wide")

st.title("📈 تحليل أسهم البورصة المصرية (EGX)")
st.caption(
    "تحليل فني + أساسي مبني على بيانات تاريخية. "
    "هذا ليس توصية استثمارية — استخدمه كأداة مساعدة فقط."
)

# ---------------------------------------------------------------------------
# الشريط الجانبي: اختيار الأسهم والإعدادات
# ---------------------------------------------------------------------------
st.sidebar.header("⚙️ الإعدادات")

custom_tickers_text = st.sidebar.text_area(
    "رموز الأسهم (سطر لكل رمز، بصيغة .CA)",
    value="\n".join(EGX_TICKERS),
    height=250,
)
tickers = [t.strip() for t in custom_tickers_text.splitlines() if t.strip()]

include_fundamentals = st.sidebar.checkbox("تضمين التحليل الأساسي (بيانات مالية)", value=True)

st.sidebar.markdown("---")
st.sidebar.subheader("🔌 مصدر البيانات")
provider_choice = st.sidebar.radio(
    "اختر مصدر البيانات",
    options=["yahoo", "eodhd", "csv"],
    format_func=lambda x: {
        "yahoo": "Yahoo Finance (مجاني)",
        "eodhd": "EODHD API (مدفوع، أدق)",
        "csv": "ملفات CSV محلية (بياناتك الخاصة)",
    }[x],
)

provider_kwargs = {}
if provider_choice == "eodhd":
    api_key = st.sidebar.text_input("EODHD API Key", type="password")
    provider_kwargs = {"api_key": api_key} if api_key else {}
elif provider_choice == "csv":
    data_dir = st.sidebar.text_input("مسار مجلد البيانات", value="./egx_data")
    provider_kwargs = {"data_dir": data_dir}

run_button = st.sidebar.button("🔄 شغّل التحليل الآن", type="primary")

if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()

if run_button:
    if provider_choice == "eodhd" and not provider_kwargs.get("api_key"):
        st.error("محتاج تدخل EODHD API Key الأول.")
        st.stop()
    with st.spinner(f"جاري تحليل {len(tickers)} سهم... قد يستغرق ذلك دقيقة أو أكثر"):
        try:
            st.session_state.df = run_screener(
                tickers=tickers,
                include_fundamentals=include_fundamentals,
                save_csv=False,
                verbose=False,
                provider_name=provider_choice,
                provider_kwargs=provider_kwargs,
            )
        except Exception as e:
            st.error(f"حصل خطأ أثناء التحليل: {e}")

df = st.session_state.df

if df.empty:
    st.info("اضغط 'شغّل التحليل الآن' من الشريط الجانبي للبدء.")
    st.stop()

# ---------------------------------------------------------------------------
# فلاتر تفاعلية
# ---------------------------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    min_short = st.slider("أقل درجة للمدى القصير", 0, 100, 0)
with col2:
    min_long = st.slider("أقل درجة للمدى الطويل", 0, 100, 0)

filtered = df[(df["short_term_score"] >= min_short) & (df["long_term_score"] >= min_long)]

# ---------------------------------------------------------------------------
# عرض النتائج في تبويبات
# ---------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📊 المدى القصير", "📈 المدى الطويل + المالي", "🗂 كل البيانات والمؤشرات"])

with tab1:
    st.subheader("أفضل الأسهم للمدى القصير")
    short_cols = ["ticker", "price", "rsi", "macd_hist", "above_sma20", "short_term_score"]
    st.dataframe(
        filtered.sort_values("short_term_score", ascending=False)[short_cols],
        use_container_width=True,
        hide_index=True,
    )
    st.bar_chart(
        filtered.sort_values("short_term_score", ascending=False)
        .set_index("ticker")["short_term_score"]
    )

with tab2:
    st.subheader("أفضل الأسهم للمدى الطويل (فني + مالي شامل)")
    long_cols = ["ticker", "price", "ret_1y_%", "volatility_%", "long_term_score"]
    if include_fundamentals:
        # إضافة المؤشرات الجديدة للجدول للمدى الطويل
        long_cols += ["pe_ratio", "pb_ratio", "dividend_yield_%", "profit_margin_%", "roe_%", "fundamental_score"]
    st.dataframe(
        filtered.sort_values("long_term_score", ascending=False)[long_cols],
        use_container_width=True,
        hide_index=True,
    )
    st.bar_chart(
        filtered.sort_values("long_term_score", ascending=False)
        .set_index("ticker")["long_term_score"]
    )

with tab3:
    st.subheader("كل البيانات والمؤشرات التفصيلية")
    st.dataframe(filtered, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ تحميل النتائج CSV",
        data=filtered.to_csv(index=False).encode("utf-8-sig"),
        file_name="egx_screener_results.csv",
        mime="text/csv",
    )

st.caption(
    "⚠️ إخلاء مسؤولية: هذا التطبيق أداة تحليلية تعليمية فقط، ولا يُعتبر استشارة مالية. الأداء التاريخي لا يضمن نتائج مستقبلية."
)