"""
موسع لتحليل الأسواق العالمية والعملات الرقمية
=============================================
يضيف دعم للأسهم الأمريكية والعملات الرقمية إلى أداة تحليل البورصة المصرية
مع الحفاظ على نفس هيكل الكود ومنطق التحليل.
"""

import os
import pandas as pd
import streamlit as st

# استيراد المكونات الأساسية من الأداة الأصلية
from egx_screener import run_screener
from egx_screener_app import st as st_app

# ---------------------------------------------------------------------------
# 1) تحميل قوائم الأسهم من ملفات CSV
# ---------------------------------------------------------------------------
def load_market_list(csv_path: str) -> list:
    """تحميل قائمة الأسهم من ملف CSV"""
    try:
        df = pd.read_csv(csv_path)
        return df["symbol"].tolist()
    except Exception as e:
        print(f"⚠️  تعذر تحميل {csv_path} ({e})")
        return []

# مسارات ملفات القوائم
CRYPTO_TICKERS_FILE = "crypto_tickers.csv"
US_TICKERS_FILE = "us_tickers.csv"

# تحميل القوائم
CRYPTO_TICKERS = load_market_list(CRYPTO_TICKERS_FILE)
US_TICKERS = load_market_list(US_TICKERS_FILE)

# ---------------------------------------------------------------------------
# 2) دمج القوائم مع قائمة البورصة المصرية (بدون تعديل الكود الأصلي)
# ---------------------------------------------------------------------------
def get_all_tickers(markets: list = None) -> list:
    """
    إرجاع قائمة الأسهم حسب الأسواق المختارة.
    markets: قائمة بالأسواق المطلوبة ['egx', 'us', 'crypto']
    """
    if markets is None:
        markets = ['egx']
    
    all_tickers = []
    
    # استيراد EGX_TICKERS من الملف الأصلي
    from egx_screener import EGX_TICKERS
    
    if 'egx' in markets:
        all_tickers.extend(EGX_TICKERS)
    if 'us' in markets:
        all_tickers.extend(US_TICKERS)
    if 'crypto' in markets:
        all_tickers.extend(CRYPTO_TICKERS)
    
    return all_tickers

def get_market_name(ticker: str) -> str:
    """تحديد السوق بناءً على رمز السهم"""
    if ticker.endswith('.CA'):
        return '🇪🇬 البورصة المصرية'
    elif ticker in US_TICKERS:
        return '🇺🇸 الأسهم الأمريكية'
    elif ticker in CRYPTO_TICKERS:
        return '₿ العملات الرقمية'
    else:
        return 'غير معروف'

# ---------------------------------------------------------------------------
# 3) واجهة Streamlit الموسعة
# ---------------------------------------------------------------------------
def render_market_selector():
    """عرض خيارات اختيار الأسواق في الشريط الجانبي"""
    st.sidebar.subheader("🌍 الأسواق المتاحة")
    
    selected_markets = st.sidebar.multiselect(
        "اختر الأسواق للتحليل:",
        options=['egx', 'us', 'crypto'],
        format_func=lambda x: {
            'egx': '🇪🇬 البورصة المصرية',
            'us': '🇺🇸 الأسهم الأمريكية',
            'crypto': '₿ العملات الرقمية'
        }.get(x, x),
        default=['egx']
    )
    
    # عرض عدد الأسهم في كل سوق
    from egx_screener import EGX_TICKERS
    st.sidebar.caption(f"عدد أسهم البورصة المصرية: {len(EGX_TICKERS)}")
    st.sidebar.caption(f"عدد الأسهم الأمريكية: {len(US_TICKERS)}")
    st.sidebar.caption(f"عدد العملات الرقمية: {len(CRYPTO_TICKERS)}")
    
    return selected_markets

# ---------------------------------------------------------------------------
# 4) تعديل منطق التحليل لدعم الأسواق المختلفة
# ---------------------------------------------------------------------------
def run_multi_market_screener(tickers: list, include_fundamentals: bool = True, 
                               provider_name: str = "yahoo", provider_kwargs: dict = None):
    """
    تشغيل المحلل على قائمة أسهم من أسواق مختلفة
    """
    if provider_kwargs is None:
        provider_kwargs = {}
    
    # إضافة دعم للعملات الرقمية عبر Yahoo Finance
    # العملات الرقمية تحتاج معاملة خاصة لأنها تختلف عن الأسهم
    return run_screener(
        tickers=tickers,
        include_fundamentals=include_fundamentals,
        save_csv=False,
        verbose=False,
        provider_name=provider_name,
        provider_kwargs=provider_kwargs
    )

# ---------------------------------------------------------------------------
# 5) تحسين عرض البيانات حسب السوق
# ---------------------------------------------------------------------------
def add_market_column(df: pd.DataFrame) -> pd.DataFrame:
    """إضافة عمود السوق إلى DataFrame"""
    if df.empty:
        return df
    
    df['market'] = df['ticker'].apply(get_market_name)
    return df

# ---------------------------------------------------------------------------
# 6) واجهة التطبيق الرئيسية الموسعة
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="📊 محلل الأسواق العالمية والعملات الرقمية", layout="wide")
    
    st.title("🌍 محلل الأسواق العالمية والعملات الرقمية")
    st.caption(
        "تحليل فني + أساسي للبورصة المصرية، الأسهم الأمريكية، والعملات الرقمية. "
        "هذا ليس توصية استثمارية — استخدمه كأداة مساعدة فقط."
    )
    
    # ---------------------------------------------------------------------------
    # الشريط الجانبي: اختيار الأسواق والإعدادات
    # ---------------------------------------------------------------------------
    st.sidebar.header("⚙️ الإعدادات")
    
    # اختيار الأسواق
    selected_markets = render_market_selector()
    
    # الحصول على قائمة الأسهم المدمجة
    tickers = get_all_tickers(selected_markets)
    
    # عرض عدد الأسهم الإجمالي
    st.sidebar.info(f"📊 إجمالي الأسهم المختارة: {len(tickers)}")
    
    # إعدادات التحليل
    include_fundamentals = st.sidebar.checkbox("تضمين التحليل الأساسي", value=True)
    
    # مصدر البيانات
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔌 مصدر البيانات")
    
    # مصادر البيانات المدعومة
    provider_options = ["yahoo", "eodhd", "csv"]
    
    # إضافة دعم خاص للعملات الرقمية (باستخدام Yahoo فقط للعملات الرقمية)
    if 'crypto' in selected_markets and len(selected_markets) == 1:
        provider_choice = "yahoo"  # القوة لاستخدام Yahoo للعملات الرقمية
        st.sidebar.info("💡 العملات الرقمية تستخدم Yahoo Finance فقط")
        provider_choice_display = "yahoo"
    else:
        provider_choice = st.sidebar.radio(
            "اختر مصدر البيانات",
            options=provider_options,
            format_func=lambda x: {
                "yahoo": "Yahoo Finance (مجاني)",
                "eodhd": "EODHD API (مدفوع، أدق)",
                "csv": "ملفات CSV محلية",
            }[x],
            index=0
        )
        provider_choice_display = provider_choice
    
    provider_kwargs = {}
    if provider_choice_display == "eodhd":
        api_key = st.sidebar.text_input("EODHD API Key", type="password")
        provider_kwargs = {"api_key": api_key} if api_key else {}
    elif provider_choice_display == "csv":
        data_dir = st.sidebar.text_input("مسار مجلد البيانات", value="./market_data")
        provider_kwargs = {"data_dir": data_dir}
    
    run_button = st.sidebar.button("🔄 شغّل التحليل الآن", type="primary")
    
    # ---------------------------------------------------------------------------
    # تشغيل التحليل
    # ---------------------------------------------------------------------------
    if "df" not in st.session_state:
        st.session_state.df = pd.DataFrame()
    
    if run_button:
        if provider_choice_display == "eodhd" and not provider_kwargs.get("api_key"):
            st.error("محتاج تدخل EODHD API Key الأول.")
            st.stop()
        
        with st.spinner(f"جاري تحليل {len(tickers)} سهم... قد يستغرق ذلك دقيقة أو أكثر"):
            try:
                df = run_multi_market_screener(
                    tickers=tickers,
                    include_fundamentals=include_fundamentals,
                    provider_name=provider_choice_display,
                    provider_kwargs=provider_kwargs
                )
                
                # إضافة عمود السوق
                if not df.empty:
                    df = add_market_column(df)
                    # إعادة ترتيب الأعمدة لجعل السوق أولاً
                    cols = df.columns.tolist()
                    cols.insert(0, cols.pop(cols.index('market')))
                    df = df[cols]
                
                st.session_state.df = df
                
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
    
    # فلتر حسب السوق
    st.markdown("##### 🏢 فلتر السوق والقطاع")
    scol1, scol2 = st.columns(2)
    with scol1:
        if "market" in filtered.columns:
            available_markets = sorted(filtered["market"].dropna().unique().tolist())
            selected_markets_filter = st.multiselect(
                "السوق (اختر واحد أو أكتر - سيبه فاضي لعرض الكل)",
                options=available_markets,
                default=[]
            )
        else:
            selected_markets_filter = []
    with scol2:
        if "sector" in filtered.columns:
            available_sectors = sorted(filtered["sector"].dropna().unique().tolist())
            selected_sectors = st.multiselect(
                "القطاع",
                options=available_sectors,
                default=[]
            )
        else:
            selected_sectors = []
    
    if selected_markets_filter:
        filtered = filtered[filtered["market"].isin(selected_markets_filter)]
    if selected_sectors:
        filtered = filtered[filtered["sector"].isin(selected_sectors)]
    
    # ---------------------------------------------------------------------------
    # عرض النتائج
    # ---------------------------------------------------------------------------
    tab1, tab2, tab3 = st.tabs(["📊 المدى القصير", "📈 المدى الطويل", "🗂 كل البيانات"])
    
    with tab1:
        st.subheader("أفضل الأسهم للمدى القصير")
        short_cols = ["market", "ticker", "price", "rsi", "macd_hist", "above_sma20", "short_term_score"]
        short_cols = [c for c in short_cols if c in filtered.columns]
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
        st.subheader("أفضل الأسهم للمدى الطويل")
        long_cols = ["market", "ticker", "price", "ret_1y_%", "volatility_%", "long_term_score"]
        if include_fundamentals:
            long_cols += ["pe_ratio", "pb_ratio", "dividend_yield_%", "profit_margin_%", "roe_%"]
        long_cols = [c for c in long_cols if c in filtered.columns]
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
            file_name="global_markets_screener_results.csv",
            mime="text/csv",
        )
    
    st.caption(
        "⚠️ إخلاء مسؤولية: هذا التطبيق أداة تحليلية تعليمية فقط، ولا يُعتبر استشارة مالية. "
        "الأداء التاريخي لا يضمن نتائج مستقبلية. العملات الرقمية شديدة التقلب وتحمل مخاطر عالية."
    )

if __name__ == "__main__":
    main()
