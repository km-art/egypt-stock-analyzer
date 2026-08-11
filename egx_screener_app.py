import os
from datetime import datetime
import pandas as pd
import streamlit as st

from egx_screener import (
    EGX_TICKERS, US_TICKERS, UAE_TICKERS, MARKETS, run_screener,
    VERDICT_BUY_MIN_SHORT, VERDICT_SELL_MAX_SHORT, VERDICT_SELL_MAX_LONG,
    TICKER_OVERRIDES, _TICKER_OVERRIDES_CSV,
    MANUAL_PRICES, _MANUAL_PRICES_CSV,
)

st.set_page_config(page_title="Multi-Market Stock Screener", layout="wide")

st.title("📈 محلل الأسهم متعدد الأسواق (مصر + أمريكا + الإمارات)")
st.caption(
    "تحليل فني + أساسي مبني على بيانات تاريخية. "
    "هذا ليس توصية استثمارية — استخدمه كأداة مساعدة فقط."
)

# ---------------------------------------------------------------------------
# الشريط الجانبي: اختيار السوق وإدارة الأسهم والإعدادات
# ---------------------------------------------------------------------------
_WATCHLIST_CSV = "watchlist.csv"


def load_watchlist() -> list[str]:
    if os.path.exists(_WATCHLIST_CSV):
        try:
            return pd.read_csv(_WATCHLIST_CSV)["ticker"].dropna().tolist()
        except Exception:
            return []
    return []


def save_watchlist(tickers: list[str]):
    pd.DataFrame({"ticker": tickers}).to_csv(_WATCHLIST_CSV, index=False)


st.sidebar.header("⭐ المفضّلة")
watchlist = load_watchlist()
with st.sidebar.expander(f"إدارة المفضّلة ({len(watchlist)} سهم)"):
    if watchlist:
        st.write(", ".join(watchlist))
    wl_col1, wl_col2 = st.columns(2)
    with wl_col1:
        wl_add = st.text_input("أضف رمز (زي COMI.CA)", key="wl_add")
        if st.button("➕ إضافة للمفضّلة"):
            if wl_add and wl_add.strip() not in watchlist:
                watchlist.append(wl_add.strip())
                save_watchlist(watchlist)
                st.success(f"✅ اتضاف {wl_add.strip()}")
                st.rerun()
    with wl_col2:
        wl_remove = st.text_input("احذف رمز", key="wl_remove")
        if st.button("🗑️ حذف من المفضّلة"):
            if wl_remove and wl_remove.strip() in watchlist:
                watchlist.remove(wl_remove.strip())
                save_watchlist(watchlist)
                st.success(f"🗑️ اتشال {wl_remove.strip()}")
                st.rerun()
    load_watchlist_clicked = st.button("📋 حمّل المفضّلة في صندوق التحليل تحت")

st.sidebar.header("🌍 اختيار السوق")

selected_markets = st.sidebar.multiselect(
    "اختار سوق واحد أو أكتر (فاضي = هتكتب/تلزق الأسهم يدوياً بنفسك تحت)",
    options=list(MARKETS.keys()),
    format_func=lambda k: f"{MARKETS[k]['label']} ({len(MARKETS[k]['tickers'])} سهم)",
    default=["egx"],
)

if len(selected_markets) > 1:
    st.sidebar.warning(
        "⚠️ اخترت أكتر من سوق مع بعض. لاحظ إن العملة مختلفة لكل سوق "
        "(جنيه/دولار/درهم)، فأي مقارنة مباشرة للأسعار أو قيمة التداول بين "
        "الأسواق دي مش دقيقة من غير تحويل عملة."
    )

st.sidebar.header("⚙️ الإعدادات وإدارة الأسهم")

# 1. إدارة ملف حفظ الأسهم لتجنب فتح محرر الأكواد
SAVED_TICKERS_FILE = "custom_tickers.txt"

if load_watchlist_clicked and watchlist:
    current_tickers_list = "\n".join(watchlist)
elif os.path.exists(SAVED_TICKERS_FILE):
    with open(SAVED_TICKERS_FILE, "r", encoding="utf-8") as f:
        current_tickers_list = f.read()
else:
    # القائمة الافتراضية = دمج كل الأسواق المختارة (لو محددتش سوق، هتبقى فاضية
    # وتكتب/تلزق الأسهم بنفسك - زي رمز عالمي لسهم مش موجود في قوائمنا الجاهزة)
    combined = []
    for key in selected_markets:
        combined.extend(MARKETS[key]["tickers"])
    current_tickers_list = "\n".join(combined)

# 2. عرض المربع النصي لتعديل الأسهم مباشرة من الواجهة (تقدر تضيف أي رمز يدوياً
#    هنا كمان - مثلاً سهم عالمي مش موجود في القوائم الجاهزة)
custom_tickers_text = st.sidebar.text_area(
    "رموز الأسهم (سطر لكل رمز - .CA لمصر / بدون لاحقة لأمريكا / .AE للإمارات)",
    value=current_tickers_list,
    height=250,
)

# 3. زر الحفظ التلقائي في ملف الإعدادات للاستغناء عن الـ VS Code
if st.sidebar.button("💾 حفظ القائمة الحالية كافتراضية"):
    with open(SAVED_TICKERS_FILE, "w", encoding="utf-8") as f:
        f.write(custom_tickers_text.strip())
    st.sidebar.success("✅ تم حفظ وتحديث القائمة بنجاح!")
    st.rerun()

# تجهيز الأسهم للتحليل
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

if provider_choice == "yahoo":
    st.sidebar.warning(
        "⚠️ بيانات Yahoo المالية (P/E، P/B، EPS...) لأسهم EGX أحياناً بتكون "
        "**قديمة أو غير دقيقة**، مش بس ناقصة. قبل ما تعتمد على رقم جراهام أو "
        "P/E لأي قرار، قارنه يدوياً بمصدر تاني زي investing.com أو الموقع "
        "الرسمي للشركة."
    )

provider_kwargs = {}
if provider_choice == "eodhd":
    api_key = st.sidebar.text_input("EODHD API Key", type="password")
    provider_kwargs = {"api_key": api_key} if api_key else {}
elif provider_choice == "csv":
    data_dir = st.sidebar.text_input("مسار مجلد البيانات", value="./egx_data")
    provider_kwargs = {"data_dir": data_dir}
    st.sidebar.caption(
        "💡 دي أدق طريقة فعلياً: تدخل EPS وBVPS يدوياً من investing.com أو "
        "التقرير المالي الرسمي لكل سهم تهتم بيه في fundamentals.csv."
    )

st.sidebar.markdown("---")
st.sidebar.subheader("🕐 سعر لحظي إضافي (اختياري)")
enable_td_live = st.sidebar.checkbox("فعّل Twelve Data لسعر أقرب للحظي", value=False)
td_live_price = None
if enable_td_live:
    st.sidebar.caption(
        "🇺🇸 **مجاني ولحظي فعلاً للأسهم الأمريكية** (باقة Basic المجانية). "
        "🇪🇬 **مصر محتاجة باقة Pro المدفوعة (99$/شهر على الأقل)**، وشكل رمز "
        "السهم عندهم مختلف عن ياهو - جرّب وتأكد بنفسك قبل ما تعتمد عليه. "
        "🇦🇪 الإمارات: التغطية غير مؤكدة."
    )
    td_api_key = st.sidebar.text_input("Twelve Data API Key", type="password")
    if td_api_key:
        from data_providers import TwelveDataLivePrice
        td_live_price = TwelveDataLivePrice(api_key=td_api_key)

enable_tv_live = st.sidebar.checkbox("فعّل TradingView لسعر أقرب للحظي (مجاني، مصدر غير رسمي)", value=False)
tv_live_price = None
if enable_tv_live:
    st.sidebar.caption(
        "🆓 **مجاني بالكامل ومن غير API key.** تغطيته لمصر أقوى بكتير من "
        "Yahoo عادةً. **لكن**: مكتبة `tradingview_ta` غير رسمية (unofficial) "
        "- ممكن تتعطل فجأة لو TradingView غيّرت الـ endpoints الداخلية "
        "بتاعتها، والاستخدام المكثف ممكن يخالف شروط استخدامهم."
    )
    try:
        from data_providers import TradingViewLivePrice
        tv_live_price = TradingViewLivePrice()
    except SystemExit as e:
        st.sidebar.error(str(e))
        tv_live_price = None

st.sidebar.header("💧 حد السيولة")
if len(selected_markets) == 1:
    _m = MARKETS[selected_markets[0]]
    default_liquidity = _m["default_min_liquidity"]
    currency_label = _m["currency_label"]
elif len(selected_markets) == 0:
    default_liquidity = 3_000_000
    currency_label = "بالعملة المحلية للسهم (غير محدد سوق)"
else:
    default_liquidity = 3_000_000
    currency_label = "بالعملة المحلية لكل سهم على حدة (أسواق مختلطة)"

min_avg_trade_value = st.sidebar.number_input(
    f"أقل متوسط قيمة تداول يومي مقبول ({currency_label})",
    min_value=0, value=int(default_liquidity), step=100_000,
)

st.sidebar.markdown("---")
with st.sidebar.expander(f"🔧 رموز بديلة للأسهم الفاشلة ({len(TICKER_OVERRIDES)} مسجّل)"):
    st.caption(
        "بعض أسهم EGX عند Yahoo Finance ليها رمز مبني على ISIN بدل الرمز "
        "المختصر المعتاد (مثال: ESRS.CA فعلياً محتاجة EGS3C251C013-EGP.CA "
        "عند Yahoo). لو سهم بيفشل تحميله، دوّر عليه يدوياً على "
        "finance.yahoo.com واكتب الرمز الصح هنا."
    )
    if TICKER_OVERRIDES:
        st.dataframe(
            pd.DataFrame(list(TICKER_OVERRIDES.items()), columns=["الرمز الأصلي", "رمز Yahoo الصحيح"]),
            use_container_width=True, hide_index=True,
        )
    ov_col1, ov_col2 = st.columns(2)
    with ov_col1:
        ov_original = st.text_input("الرمز الأصلي (زي ESRS.CA)", key="ov_original")
    with ov_col2:
        ov_yahoo = st.text_input("رمز Yahoo الصحيح", key="ov_yahoo")
    if st.button("💾 حفظ الرمز البديل"):
        if ov_original and ov_yahoo:
            existing = pd.read_csv(_TICKER_OVERRIDES_CSV) if os.path.exists(_TICKER_OVERRIDES_CSV) \
                else pd.DataFrame(columns=["original_ticker", "yahoo_symbol"])
            existing = existing[existing["original_ticker"] != ov_original.strip()]
            new_row = pd.DataFrame([{"original_ticker": ov_original.strip(), "yahoo_symbol": ov_yahoo.strip()}])
            pd.concat([existing, new_row], ignore_index=True).to_csv(_TICKER_OVERRIDES_CSV, index=False)
            st.success(f"✅ اتحفظ: {ov_original} → {ov_yahoo}. أعد تشغيل التحليل عشان يتفعّل.")
            st.rerun()
        else:
            st.warning("لازم تملأ الحقلين الاتنين.")

st.sidebar.markdown("---")
with st.sidebar.expander(f"✍️ سعر يدوي لسهم بعينه ({len(MANUAL_PRICES)} مسجّل)"):
    st.caption(
        "لو عندك سعر أدق من تطبيق وسيطك أو مصدر تثق فيه، دخّله هنا لسهم "
        "معين — هياخد **أعلى أولوية** فوق أي مصدر آلي (Twelve Data، "
        "TradingView، Yahoo) لحد ما تمسحه بنفسك."
    )
    if MANUAL_PRICES:
        mp_display = pd.DataFrame([
            {"الرمز": t, "السعر": v["price"], "آخر تحديث": v["updated_at"]}
            for t, v in MANUAL_PRICES.items()
        ])
        st.dataframe(mp_display, use_container_width=True, hide_index=True)

    mp_col1, mp_col2 = st.columns(2)
    with mp_col1:
        mp_ticker = st.text_input("رمز السهم (زي COMI.CA)", key="mp_ticker")
    with mp_col2:
        mp_price = st.number_input("السعر", min_value=0.0, step=0.01, key="mp_price")

    mp_save_col, mp_clear_col = st.columns(2)
    with mp_save_col:
        if st.button("💾 حفظ السعر اليدوي"):
            if mp_ticker and mp_price > 0:
                existing = pd.read_csv(_MANUAL_PRICES_CSV) if os.path.exists(_MANUAL_PRICES_CSV) \
                    else pd.DataFrame(columns=["ticker", "price", "updated_at"])
                existing = existing[existing["ticker"] != mp_ticker.strip()]
                new_row = pd.DataFrame([{
                    "ticker": mp_ticker.strip(),
                    "price": mp_price,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }])
                pd.concat([existing, new_row], ignore_index=True).to_csv(_MANUAL_PRICES_CSV, index=False)
                st.success(f"✅ اتحفظ سعر {mp_ticker} = {mp_price}")
                st.rerun()
            else:
                st.warning("لازم تدخل رمز السهم وسعر أكبر من صفر.")
    with mp_clear_col:
        if st.button("🗑️ مسح سعر يدوي"):
            if mp_ticker and os.path.exists(_MANUAL_PRICES_CSV):
                existing = pd.read_csv(_MANUAL_PRICES_CSV)
                existing = existing[existing["ticker"] != mp_ticker.strip()]
                existing.to_csv(_MANUAL_PRICES_CSV, index=False)
                st.success(f"🗑️ اتمسح سعر {mp_ticker} اليدوي")
                st.rerun()
            else:
                st.warning("اكتب رمز السهم اللي عايز تمسح سعره اليدوي.")

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
                min_avg_trade_value=min_avg_trade_value,
                td_live_price=td_live_price,
                tv_live_price=tv_live_price,
            )
        except Exception as e:
            st.error(f"حصل خطأ أثناء التحليل: {e}")

df = st.session_state.df

if df.empty:
    st.info("اضغط 'شغّل التحليل الآن' من الشريط الجانبي للبدء.")
    st.stop()

if "fundamentals_fetched" in df.columns:
    fetched_ratio = df["fundamentals_fetched"].mean()
    if fetched_ratio < 0.2:
        st.error(
            "⚠️ البيانات المالية (P/E، P/B، EPS...) رجعت فاضية لمعظم/كل الأسهم. "
            "على الأغلب Yahoo Finance رافض/حاظر طلبات البيانات المالية من سيرفر "
            "Streamlit Cloud مؤقتاً (مشكلة معروفة ومتكررة مع yfinance من عناوين IP سحابية). "
            "جرب تاني بعد شوية، أو استخدم مصدر EODHD من الشريط الجانبي لو المشكلة استمرت. "
            "لاحظ إن التحليل الفني (RSI/MACD/المتوسطات) شغال بشكل طبيعي رغم كده."
        )
    elif fetched_ratio < 0.7:
        st.warning(
            f"ℹ️ البيانات المالية اتجابت لـ {fetched_ratio:.0%} من الأسهم بس. "
            "بعض الأسهم هتظهر بدرجة أساسية محايدة (50) ورقم جراهام None بسبب نقص البيانات."
        )

# ---------------------------------------------------------------------------
# فلاتر تفاعلية
# ---------------------------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    min_short = st.slider("أقل درجة للمدى القصير", 0, 100, 0)
with col2:
    min_long = st.slider("أقل درجة للمدى الطويل", 0, 100, 0)

filtered = df[(df["short_term_score"] >= min_short) & (df["long_term_score"] >= min_long)]

st.markdown("##### 🏢 فلتر القطاع والسيولة ومؤشر EGX30/70")
scol1, scol2, scol3 = st.columns(3)
with scol1:
    if "sector" in filtered.columns:
        available_sectors = sorted(filtered["sector"].dropna().unique().tolist())
        selected_sectors = st.multiselect("القطاع (اختر واحد أو أكتر - سيبه فاضي لعرض الكل)",
                                           options=available_sectors, default=[])
    else:
        selected_sectors = []
with scol2:
    liquidity_filter = st.checkbox(
        f"إخفاء الأسهم اللي متوسط تداولها أقل من الحد المدخل ({int(min_avg_trade_value):,})",
        value=False,
    )
with scol3:
    if "egx_index" in filtered.columns:
        available_indices = sorted(filtered["egx_index"].dropna().unique().tolist())
        selected_indices = st.multiselect(
            "عضوية EGX30/70 (لأسهم مصر بس - سيبه فاضي لعرض الكل)",
            options=available_indices, default=[],
        )
    else:
        selected_indices = []

if selected_sectors:
    filtered = filtered[filtered["sector"].isin(selected_sectors)]
if "meets_liquidity_min" in filtered.columns and liquidity_filter:
    filtered = filtered[filtered["meets_liquidity_min"] == True]
if selected_indices:
    filtered = filtered[filtered["egx_index"].isin(selected_indices)]

if "thin_float_risk" in filtered.columns:
    hide_thin_float = st.checkbox(
        "⚠️ إخفاء الأسهم اللي عليها تحذير 'تعويم رقيق' (سيولة ضعيفة + تقلب غير معتاد)",
        value=False,
    )
    if hide_thin_float:
        filtered = filtered[filtered["thin_float_risk"] != True]

st.markdown("##### 📐 فلاتر قاعدة جراهام (المستثمر الدفاعي)")
if provider_choice == "yahoo":
    st.caption(
        "⚠️ EPS وBVPS المستخدمين هنا جايين من Yahoo (أو مُشتقين من P/E و P/B "
        "بتوعه). لو عمود `eps_estimated` أو `bvps_estimated` بـ True لسهم معين، "
        "يبقى الرقم تقريبي وممكن يكون غير دقيق - راجعه يدوياً قبل أي قرار."
    )
gcol1, gcol2 = st.columns(2)
with gcol1:
    graham_pe_filter = st.checkbox("مكرر ربحية (P/E) أقل من 15 فقط", value=False)
with gcol2:
    graham_undervalued_filter = st.checkbox("سعره أقل من رقم جراهام (سعر عادل) فقط", value=False)

if "pe_below_15" in filtered.columns and graham_pe_filter:
    filtered = filtered[filtered["pe_below_15"] == True]
if "undervalued_per_graham" in filtered.columns and graham_undervalued_filter:
    filtered = filtered[filtered["undervalued_per_graham"] == True]

# ---------------------------------------------------------------------------
# عرض النتائج في تبويبات
# ---------------------------------------------------------------------------
if "price_is_live" in df.columns:
    live_ratio = df["price_is_live"].mean()
    if live_ratio > 0:
        st.caption(
            f"🕐 عمود `price_is_live`: True = سعر شبه لحظي (delayed quote حسب "
            f"سياسة المصدر، مش لحظي 100%)، False = آخر إغلاق يومي متاح. "
            f"حالياً {live_ratio:.0%} من الأسهم عندها سعر شبه لحظي."
        )
    else:
        st.caption(
            "🕐 كل الأسعار المعروضة هي **آخر إغلاق يومي** متاح (مش لحظية) - "
            "السعر شبه اللحظي مش متاح دلوقتي من المصدر المختار."
        )

tab0, tab1, tab2, tab3, tab4 = st.tabs([
    "🎯 التوصية", "📊 المدى القصير", "📈 المدى الطويل + المالي",
    "🗂 كل البيانات والمؤشرات", "💼 محفظتي",
])

with tab0:
    st.subheader("التوصية النهائية (فني + مالي مع بعض)")
    st.caption(
        "🟢 شراء = الدرجة الفنية القصيرة والدرجة الطويلة (فني+مالي) **الاتنين** "
        f"فوق {VERDICT_BUY_MIN_SHORT} مع سيولة كافية. "
        f"🔴 بيع = الاتنين تحت {VERDICT_SELL_MAX_SHORT}/{VERDICT_SELL_MAX_LONG}. "
        "🟡 انتظار = إشارات متضاربة أو بيانات ناقصة. هذا ليس توصية استثمارية."
    )
    if "ترتيب_التوصية" in filtered.columns:
        verdict_cols = ["ticker", "sector", "price", "التوصية", "short_term_score", "long_term_score"]
        verdict_cols = [c for c in verdict_cols if c in filtered.columns]
        st.dataframe(
            filtered.sort_values(
                ["ترتيب_التوصية", "short_term_score", "long_term_score"],
                ascending=[True, False, False],
            )[verdict_cols],
            use_container_width=True,
            hide_index=True,
        )
        counts = filtered["التوصية"].value_counts()
        c1, c2, c3 = st.columns(3)
        c1.metric("🟢 شراء", int(sum(v for k, v in counts.items() if "شراء" in k)))
        c2.metric("🟡 انتظار", int(sum(v for k, v in counts.items() if "انتظار" in k)))
        c3.metric("🔴 بيع", int(sum(v for k, v in counts.items() if "بيع" in k)))
    else:
        st.info("عمود التوصية مش موجود في النتائج الحالية - شغّل التحليل تاني بالنسخة المحدّثة.")

with tab1:
    st.subheader("أفضل الأسهم للمدى القصير")
    st.caption(
        "💡 `target_sell_price` = سعر بيع مستهدف تقني (النطاق العلوي لبولينجر "
        "باندز). `stop_loss_price` = وقف خسارة مقترح (النطاق السفلي). لو "
        "`stop_loss_already_broken` = True، يبقى السعر كسر الدعم فعلاً - إشارة "
        "خطر، مش مجرد وقف خسارة مستقبلي."
    )
    short_cols = ["ticker", "egx_index", "price", "price_is_live", "price_source", "rsi", "macd_hist", "above_sma20",
                  "target_sell_price", "target_sell_upside_%", "stop_loss_price", "stop_loss_downside_%",
                  "stop_loss_already_broken", "short_term_score", "التوصية"]
    short_cols = [c for c in short_cols if c in filtered.columns]  # حماية لو عمود جديد لسه مش موجود في النسخة الشغالة
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
    st.caption(
        "💡 `relative_strength_1y_%` = عائد السهم ناقص عائد المؤشر المرجعي "
        "لنفس الفترة (موجب = بيتفوق على السوق فعلاً، مش مجرد راكب موجة صاعدة "
        "عامة). `volatility_percentile` = هل تقلب السهم دلوقتي أعلى من عادته "
        "هو نفسه تاريخياً (فوق 80 يستاهل حذر). `thin_float_risk` = تحذير "
        "سيولة ضعيفة + تقلب غير معتاد مع بعض - علامة على تعويم رقيق ممكن "
        "يحرّك السعر بعنف من غير سبب حقيقي (زي حالات BIOC ومطاحن الإسكندرية)."
    )
    long_cols = ["ticker", "egx_index", "price", "price_is_live", "ret_1y_%", "volatility_%",
                 "pct_from_52w_high", "pct_from_52w_low", "relative_strength_1y_%",
                 "volatility_percentile", "volume_trend_%", "thin_float_risk",
                 "long_term_score", "التوصية"]
    if include_fundamentals:
        # إضافة المؤشرات الجديدة للجدول للمدى الطويل
        long_cols += ["pe_ratio", "pb_ratio", "dividend_yield_%", "profit_margin_%", "roe_%",
                      "fundamental_score", "graham_number", "graham_upside_%", "undervalued_per_graham"]
    long_cols = [c for c in long_cols if c in filtered.columns]  # حماية لو عمود جديد لسه مش موجود في النسخة الشغالة
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

_PORTFOLIO_CSV = "portfolio.csv"


def load_portfolio() -> pd.DataFrame:
    if os.path.exists(_PORTFOLIO_CSV):
        try:
            return pd.read_csv(_PORTFOLIO_CSV)
        except Exception:
            pass
    return pd.DataFrame(columns=["ticker", "entry_price", "quantity"])


def save_portfolio(df_p: pd.DataFrame):
    df_p.to_csv(_PORTFOLIO_CSV, index=False)


with tab4:
    st.subheader("💼 محفظتي - تتبع الربح/الخسارة")
    st.caption(
        "سجّل الأسهم اللي فعلاً اشتريتها بسعر دخولك الحقيقي، وهنحسبلك الربح/"
        "الخسارة تلقائياً بالمقارنة مع آخر سعر متاح من نتائج التحليل فوق. "
        "لازم تكون شغّلت التحليل على نفس الأسهم دي الأول عشان نلاقي سعرها الحالي."
    )

    portfolio_df = load_portfolio()

    pf_col1, pf_col2, pf_col3 = st.columns(3)
    with pf_col1:
        pf_ticker = st.text_input("رمز السهم", key="pf_ticker")
    with pf_col2:
        pf_entry = st.number_input("سعر الدخول", min_value=0.0, step=0.01, key="pf_entry")
    with pf_col3:
        pf_qty = st.number_input("الكمية (اختياري)", min_value=0.0, step=1.0, key="pf_qty", value=0.0)

    pf_add_col, pf_remove_col = st.columns(2)
    with pf_add_col:
        if st.button("➕ إضافة/تحديث في المحفظة"):
            if pf_ticker and pf_entry > 0:
                portfolio_df = portfolio_df[portfolio_df["ticker"] != pf_ticker.strip()]
                new_row = pd.DataFrame([{
                    "ticker": pf_ticker.strip(), "entry_price": pf_entry, "quantity": pf_qty,
                }])
                portfolio_df = pd.concat([portfolio_df, new_row], ignore_index=True)
                save_portfolio(portfolio_df)
                st.success(f"✅ اتحفظ {pf_ticker} بسعر دخول {pf_entry}")
                st.rerun()
            else:
                st.warning("لازم رمز السهم وسعر دخول أكبر من صفر.")
    with pf_remove_col:
        if st.button("🗑️ حذف من المحفظة"):
            if pf_ticker:
                portfolio_df = portfolio_df[portfolio_df["ticker"] != pf_ticker.strip()]
                save_portfolio(portfolio_df)
                st.success(f"🗑️ اتشال {pf_ticker} من المحفظة")
                st.rerun()

    if portfolio_df.empty:
        st.info("محفظتك فاضية - ضيف أول سهم من الفورم فوق.")
    else:
        # نربط كل سهم في المحفظة بسعره الحالي من نتائج التحليل (لو موجود)
        price_lookup = df.set_index("ticker")["price"].to_dict() if not df.empty else {}
        rows = []
        for _, row in portfolio_df.iterrows():
            current_price = price_lookup.get(row["ticker"])
            entry = row["entry_price"]
            qty = row.get("quantity", 0) or 0
            if current_price is not None:
                pnl_pct = round((current_price / entry - 1) * 100, 2)
                pnl_value = round((current_price - entry) * qty, 2) if qty else None
            else:
                pnl_pct = None
                pnl_value = None
            rows.append({
                "الرمز": row["ticker"],
                "سعر الدخول": entry,
                "الكمية": qty if qty else "—",
                "السعر الحالي": current_price if current_price is not None else "شغّل التحليل عليه الأول",
                "الربح/الخسارة %": pnl_pct,
                "الربح/الخسارة (قيمة)": pnl_value,
            })

        pf_display = pd.DataFrame(rows)
        st.dataframe(pf_display, use_container_width=True, hide_index=True)

        total_value_rows = [r["الربح/الخسارة (قيمة)"] for r in rows if r["الربح/الخسارة (قيمة)"] is not None]
        if total_value_rows:
            st.metric("إجمالي الربح/الخسارة (للأسهم اللي معاها كمية)", f"{sum(total_value_rows):,.2f}")

st.caption(
    "⚠️ إخلاء مسؤولية: هذا التطبيق أداة تحليلية تعليمية فقط، ولا يُعتبر استشارة مالية. الأداء التاريخي لا يضمن نتائج مستقبلية."
)
