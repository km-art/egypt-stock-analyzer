import os
import time
import numpy as np
import pandas as pd

from data_providers import get_provider, TwelveDataLivePrice, TradingViewLivePrice

# ---------------------------------------------------------------------------
# 0) رموز بديلة (Ticker Overrides)
# ---------------------------------------------------------------------------
# اكتشفنا إن Yahoo Finance بيستخدم لبعض أسهم EGX رمز مبني على ISIN بدل الرمز
# المختصر المعتاد - مثلاً "حديد عز" رمزها المعتاد ESRS.CA بس Yahoo فعلياً
# محتاج EGS3C251C013-EGP.CA. الديكشنري ده بيخليك تربط الرمز المعتاد بالرمز
# الصح اللي Yahoo فعلاً بيفهمه، من غير ما تغيّر الرمز المعروض في النتائج.
#
# لإضافة رمز بديل جديد: عدّل هنا مباشرة، أو (أسهل) استخدم الواجهة في
# egx_screener_app.py اللي بتحفظ في ticker_overrides.csv تلقائياً.
BUILT_IN_TICKER_OVERRIDES = {
    "ESRS.CA": "EGS3C251C013-EGP.CA",  # حديد عز
}

_TICKER_OVERRIDES_CSV = "ticker_overrides.csv"


def load_ticker_overrides(csv_path: str = _TICKER_OVERRIDES_CSV) -> dict:
    """يدمج الرموز البديلة المدمجة في الكود + أي رموز أضافها المستخدم عبر الواجهة."""
    overrides = dict(BUILT_IN_TICKER_OVERRIDES)
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            overrides.update(dict(zip(df["original_ticker"], df["yahoo_symbol"])))
        except Exception as e:
            print(f"⚠️  تعذر تحميل {csv_path} ({e}).")
    return overrides


TICKER_OVERRIDES = load_ticker_overrides()


def resolve_symbol(ticker: str) -> str:
    """يرجع الرمز اللي فعلاً هيتبعت للمزود (Yahoo غالباً) - نفس الرمز الأصلي
    لو مفيش بديل مسجّل ليه."""
    return TICKER_OVERRIDES.get(ticker, ticker)


# ---------------------------------------------------------------------------
# 0ب) سعر يدوي (Manual Price Override) - أعلى أولوية في سلسلة مصادر السعر
# ---------------------------------------------------------------------------
# لو عندك سعر لحظي فعلي من تطبيق وسيطك أو أي مصدر تثق فيه، تقدر تدخله يدوياً
# لسهم بعينه - وهو هياخد أولوية فوق كل مصادر الأتمتة (Twelve Data,
# TradingView, Yahoo). مفيد لما تحتاج تتأكد من دقة سعر سهم معين قبل قرار.
_MANUAL_PRICES_CSV = "manual_prices.csv"


def load_manual_prices(csv_path: str = _MANUAL_PRICES_CSV) -> dict:
    """يرجع dict: ticker -> {"price": float, "updated_at": str}"""
    if not os.path.exists(csv_path):
        return {}
    try:
        df = pd.read_csv(csv_path)
        return {
            row["ticker"]: {"price": float(row["price"]), "updated_at": str(row["updated_at"])}
            for _, row in df.iterrows()
        }
    except Exception as e:
        print(f"⚠️  تعذر تحميل {csv_path} ({e}).")
        return {}


MANUAL_PRICES = load_manual_prices()


# ---------------------------------------------------------------------------
# 1) قائمة الأسهم: مكتوبة مباشرة هنا في الكود (223 سهم مدرج فعلياً في EGX)
#    بدل ما تتحمّل من ملف CSV خارجي - عشان الكود يشتغل بمفرده من غير ما
#    تحتاج ترفع ملف إضافي منفصل مع كل نشر. لو عايز تضيف/تشيل سهم، عدّل
#    القائمة دي مباشرة.
# ---------------------------------------------------------------------------
EGX_TICKERS = [
    "COMI.CA", "TMGH.CA", "SWDY.CA", "ETEL.CA", "EGAL.CA", "MFPC.CA", "QNBE.CA", "EAST.CA",
    "ABUK.CA", "ALCN.CA", "ORAS.CA", "EFIH.CA", "HDBK.CA", "FWRY.CA", "EMFD.CA", "SCTS.CA",
    "ADIB.CA", "PHDC.CA", "ORHD.CA", "GPPL.CA", "VLMR.CA", "VLMRA.CA", "EFID.CA", "HRHO.CA",
    "CANA.CA", "JUFO.CA", "BTFH.CA", "IRON.CA", "RAYA.CA", "FERC.CA", "EGCH.CA", "CIEB.CA",
    "FAIT.CA", "FAITA.CA", "GBCO.CA", "OCDI.CA", "HELI.CA", "VALU.CA", "EXPA.CA", "CLHO.CA",
    "EGTS.CA", "CCAP.CA", "ARCC.CA", "EFIC.CA", "SKPC.CA", "MCQE.CA", "TAQA.CA", "POUL.CA",
    "EGSA.CA", "MTIE.CA", "SCEM.CA", "SAUD.CA", "ORWE.CA", "CIRA.CA", "MASR.CA", "UBEE.CA",
    "PHAR.CA", "MBSC.CA", "MHOT.CA", "CICH.CA", "ISPH.CA", "EGBE.CA", "TALM.CA", "ATQA.CA",
    "MOIL.CA", "AMOC.CA", "BINV.CA", "RMDA.CA", "IFAP.CA", "BONY.CA", "CSAG.CA", "OLFI.CA",
    "SPHT.CA", "NIPH.CA", "ISMQ.CA", "MIPH.CA", "OIH.CA", "ACAP.CA", "SUGR.CA", "EGAS.CA",
    "DOMT.CA", "ELEC.CA", "MOIN.CA", "AMES.CA", "PRDC.CA", "MPRC.CA", "BIOC.CA", "ZMID.CA",
    "NAPR.CA", "AXPH.CA", "NINH.CA", "CNFN.CA", "GOUR.CA", "CPCI.CA", "SPIN.CA", "PHTV.CA",
    "ENGC.CA", "DSCW.CA", "MFSC.CA", "MPCI.CA", "SVCE.CA", "AMIA.CA", "GSSC.CA", "OCPH.CA",
    "GDWA.CA", "MICH.CA", "WCDF.CA", "SAIB.CA", "KABO.CA", "UEFM.CA", "UNIT.CA", "ACAMD.CA",
    "ACTF.CA", "ARAB.CA", "OFH.CA", "AJWA.CA", "AMER.CA", "KZPC.CA", "ACGC.CA", "ADCI.CA",
    "CFGH.CA", "ELSH.CA", "ASCM.CA", "AFMC.CA", "ISMA.CA", "SDTI.CA", "ELKA.CA", "LCSW.CA",
    "GGRN.CA", "INFI.CA", "PHGC.CA", "SNFC.CA", "NAHO.CA", "EDFM.CA", "ETRS.CA", "SMFR.CA",
    "ATLC.CA", "RACC.CA", "DAPH.CA", "EALR.CA", "ZEOT.CA", "ADPC.CA", "EHDR.CA", "IDRE.CA",
    "MENA.CA", "WKOL.CA", "MOSC.CA", "MPCO.CA", "ECAP.CA", "CEFM.CA", "SCFM.CA", "GPIM.CA",
    "MILS.CA", "OBRI.CA", "DEIN.CA", "CRST.CA", "AALR.CA", "CERA.CA", "NARE.CA", "PRCL.CA",
    "NDRL.CA", "ALRA.CA", "ODIN.CA", "NCCW.CA", "MAAL.CA", "MEPA.CA", "NHPS.CA", "ALUM.CA",
    "SEIGA.CA", "POCO.CA", "COSG.CA", "AIDC.CA", "UEGC.CA", "RTVC.CA", "SEIG.CA", "EBSC.CA",
    "PRMH.CA", "SIPC.CA", "GGCC.CA", "RREI.CA", "CAED.CA", "GTEX.CA", "APSW.CA", "AFDI.CA",
    "MEGM.CA", "ICLE.CA", "ARVA.CA", "ANFI.CA", "TANM.CA", "MCRO.CA", "MOED.CA", "DTPP.CA",
    "KRDI.CA", "GTWL.CA", "RAKT.CA", "SPMD.CA", "UNIP.CA", "RUBX.CA", "ROTO.CA", "KWIN.CA",
    "ASPI.CA", "ICID.CA", "AIHC.CA", "AREH.CA", "EEII.CA", "CCRS.CA", "EASB.CA", "GRCA.CA",
    "EPCO.CA", "ELWA.CA", "LUTS.CA", "ELNA.CA", "DGTZ.CA", "GIHD.CA", "DCCC.CA", "NEDA.CA",
    "TRTO.CA", "MMAT.CA", "EPPK.CA", "GMCI.CA", "EOSB.CA", "CPME.CA", "COPR.CA",
]

_SECTORS_CSV_PATH = "egx_sectors.csv"
_US_STOCKS_CSV_PATH = "us_stocks.csv"
_UAE_STOCKS_CSV_PATH = "uae_stocks.csv"


def _load_tickers_csv(csv_path: str, ticker_col: str = "yahoo_ticker") -> list[str]:
    """تحميل عام لأي قائمة أسهم من CSV - بيرجع قائمة فاضية لو الملف مش موجود
    بدل ما يكسر التطبيق (السوق ده هيختفي من الاختيار وبس)."""
    try:
        df = pd.read_csv(csv_path)
        return df[ticker_col].dropna().unique().tolist()
    except Exception as e:
        print(f"⚠️  تعذر تحميل {csv_path} ({e}).")
        return []


def _load_sector_map_csv(csv_path: str, ticker_col: str = "yahoo_ticker",
                          sector_col: str = "sector") -> dict:
    """تحميل عام لخريطة (رمز -> قطاع) من أي ملف CSV فيه العمودين دول."""
    try:
        df = pd.read_csv(csv_path)
        return dict(zip(df[ticker_col], df[sector_col]))
    except Exception as e:
        print(f"⚠️  تعذر تحميل {csv_path} ({e}).")
        return {}


def load_egx_sectors(csv_path: str = _SECTORS_CSV_PATH) -> dict:
    """
    يحمّل تصنيف القطاعات من egx_sectors.csv ويرجعه كـ dict:
    ticker -> {"sector": ..., "is_major_exporter": ...}
    لو الملف مش موجود، بيرجع dict فاضي (النتيجة هتبقى "غير مصنف" لكل الأسهم).
    """
    try:
        df = pd.read_csv(csv_path)
        return {
            row["yahoo_ticker"]: {
                "sector": row["sector"],
                "is_major_exporter": bool(row["is_major_exporter"]),
            }
            for _, row in df.iterrows()
        }
    except Exception as e:
        print(f"⚠️  تعذر تحميل {csv_path} ({e}). هيتم اعتبار كل الأسهم 'غير مصنف'.")
        return {}


EGX_SECTORS = load_egx_sectors()

# ---------------------------------------------------------------------------
# 1ب) أسواق إضافية: أمريكا (S&P 500) والإمارات (DFM + ADX)
# ---------------------------------------------------------------------------
# على عكس EGX (اللي أسهمها مكتوبة مباشرة في الكود)، القوائم دي كبيرة جداً
# (502 + 163 سهم) فبتتحمّل من ملفات CSV مصاحبة (us_stocks.csv, uae_stocks.csv).
# لو الملفات دي مش موجودة، السوق المعني هيختفي من الاختيار بس EGX هيفضل شغال عادي.
US_TICKERS = _load_tickers_csv(_US_STOCKS_CSV_PATH)
US_SECTORS = _load_sector_map_csv(_US_STOCKS_CSV_PATH)

UAE_TICKERS = _load_tickers_csv(_UAE_STOCKS_CSV_PATH)
UAE_SECTORS = _load_sector_map_csv(_UAE_STOCKS_CSV_PATH)

# سجل موحّد للأسواق - يستخدم في الواجهة لبناء قائمة الاختيار وعرض العملة الصحيحة
MARKETS = {
    "egx": {"label": "🇪🇬 مصر (EGX)", "tickers": EGX_TICKERS,
            "currency": "EGP", "currency_label": "جنيه مصري", "default_min_liquidity": 3_000_000},
    "us": {"label": "🇺🇸 أمريكا (S&P 500)", "tickers": US_TICKERS,
           "currency": "USD", "currency_label": "دولار أمريكي", "default_min_liquidity": 5_000_000},
    "uae": {"label": "🇦🇪 الإمارات (DFM + ADX)", "tickers": UAE_TICKERS,
            "currency": "AED", "currency_label": "درهم إماراتي", "default_min_liquidity": 1_000_000},
}


def get_sector(ticker: str) -> str:
    """يدوّر على قطاع السهم في أي من الأسواق التلاتة، وبيرجع 'غير مصنف' لو مش لاقيه."""
    if ticker in EGX_SECTORS:
        return EGX_SECTORS[ticker].get("sector", "غير مصنف")
    if ticker in US_SECTORS:
        return US_SECTORS[ticker]
    if ticker in UAE_SECTORS:
        return UAE_SECTORS[ticker]
    return "غير مصنف"


def get_is_major_exporter(ticker: str) -> bool:
    """علم 'مُصدّر رئيسي' - متاح حالياً للأسهم المصرية بس (تصنيف يدوي مُعَد مسبقاً)."""
    if ticker in EGX_SECTORS:
        return EGX_SECTORS[ticker].get("is_major_exporter", False)
    return False


# ---------------------------------------------------------------------------
# تصنيف EGX30 / EGX70 - مبني على بيانات investing.com (قد تتغيّر مع أي
# مراجعة نصف سنوية لمؤشرات EGX - آخر تحقق تم يدوياً، حدّثها لو لاحظت تغيير)
# ---------------------------------------------------------------------------
EGX30_TICKERS = {
    "ABUK.CA", "ADIB.CA", "AMOC.CA", "ARCC.CA", "BTFH.CA", "CCAP.CA", "COMI.CA", "EAST.CA",
    "EFID.CA", "EFIH.CA", "EGAL.CA", "EGCH.CA", "EMFD.CA", "ETEL.CA", "FWRY.CA", "GBCO.CA",
    "HELI.CA", "HRHO.CA", "ISPH.CA", "JUFO.CA", "MCQE.CA", "OIH.CA", "ORAS.CA", "ORHD.CA",
    "ORWE.CA", "PHDC.CA", "RAYA.CA", "RMDA.CA", "TMGH.CA", "VLMR.CA", "VLMRA.CA",
}

EGX70_TICKERS = {
    "ACTF.CA", "AFDI.CA", "AFMC.CA", "AIDC.CA", "ALCN.CA", "AMER.CA", "AMIA.CA", "ARAB.CA",
    "ASCM.CA", "ASPI.CA", "ATLC.CA", "ATQA.CA", "BIOC.CA", "CIEB.CA", "CNFN.CA", "COSG.CA",
    "CSAG.CA", "DAPH.CA", "DSCW.CA", "ECAP.CA", "EEII.CA", "EFIC.CA", "EGTS.CA", "EHDR.CA",
    "ENGC.CA", "ETRS.CA", "EXPA.CA", "GPIM.CA", "HDBK.CA", "IDRE.CA", "IFAP.CA", "ISMA.CA",
    "ISMQ.CA", "KABO.CA", "KRDI.CA", "LCSW.CA", "MASR.CA", "MCRO.CA", "MEPA.CA", "MFPC.CA",
    "MOED.CA", "MPCI.CA", "MPCO.CA", "MPRC.CA", "MTIE.CA", "NCCW.CA", "NIPH.CA", "OBRI.CA",
    "OCDI.CA", "PHAR.CA", "POUL.CA", "PRCL.CA", "RACC.CA", "SCEM.CA", "SDTI.CA", "SIPC.CA",
    "SKPC.CA", "SPHT.CA", "SVCE.CA", "SWDY.CA", "TALM.CA", "TANM.CA", "TAQA.CA", "UEGC.CA",
    "UNIP.CA", "VALU.CA", "ZEOT.CA", "ZMID.CA",
}


def get_egx_index(ticker: str) -> str:
    """
    يرجع "EGX30" لو السهم من أكبر/أنشط 30 سهم، "EGX70" لو من الشريحة التالية
    (أسهم متوسطة نشطة)، أو "خارج EGX30/70" لباقي الأسهم المصرية أو أي سهم
    من سوق تاني (أمريكا/الإمارات).
    """
    if ticker in EGX30_TICKERS:
        return "EGX30"
    if ticker in EGX70_TICKERS:
        return "EGX70"
    if ticker in EGX_TICKERS:
        return "خارج EGX30/70"
    return "غير منطبق (مش سهم مصري)"


HISTORY_DAYS = 365 + 30

# الحد الأدنى الافتراضي لمتوسط قيمة التداول اليومية (بالعملة المحلية للسهم) عشان
# يعتبر "سائل بما يكفي". القيمة دي افتراضية لمصر فقط - لو بتحلل سوق تاني، مرّر
# قيمة مختلفة عبر run_screener(min_avg_trade_value=...) لأن الأرقام مش قابلة
# للمقارنة مباشرة بين جنيه مصري ودولار ودرهم من غير تحويل عملة.
DEFAULT_MIN_AVG_TRADE_VALUE = 3_000_000
LIQUIDITY_LOOKBACK_DAYS = 20  # متوسط قيمة التداول محسوب على آخر كام يوم تداول


# ---------------------------------------------------------------------------
# 2) دوال حساب المؤشرات الفنية
# ---------------------------------------------------------------------------
def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def compute_bollinger(close: pd.Series, period: int = 20, num_std: float = 2.0):
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def score_fundamentals(f: dict) -> int:
    score = 50

    pe = f.get("pe_ratio")
    if pe is not None and pe > 0:
        if pe < 12:
            score += 10
        elif pe > 25:
            score -= 10

    pm = f.get("profit_margin_%")
    if pm is not None:
        if pm > 15:
            score += 10
        elif pm < 0:
            score -= 15

    roe = f.get("roe_%")
    if roe is not None:
        if roe > 15:
            score += 10
        elif roe < 5:
            score -= 5

    dte = f.get("debt_to_equity")
    if dte is not None:
        if dte < 50:
            score += 5
        elif dte > 150:
            score -= 10

    dy = f.get("dividend_yield_%")
    if dy is not None and dy > 0:
        if dy > 5:
            score += 5

    rg = f.get("revenue_growth_%")
    if rg is not None:
        if rg > 10:
            score += 10
        elif rg < 0:
            score -= 10

    return max(0, min(100, score))


def compute_graham(eps, bvps, price):
    """
    يحسب "رقم جراهام" (Graham Number) - السعر العادل الأقصى حسب معايير
    المستثمر الدفاعي لبنجامين جراهام:

        رقم جراهام = √(22.5 × EPS × BVPS)

    الرقم 22.5 = 15 (أقصى P/E مقبول) × 1.5 (أقصى P/B مقبول) - الصيغة دي
    بتفرض الحدين الأقصيين مع بعض في معادلة واحدة، فمحتاجة EPS موجب وBVPS موجب.
    """
    if eps is None or bvps is None or eps <= 0 or bvps <= 0:
        return {"graham_number": None, "graham_upside_%": None, "undervalued_per_graham": None}

    graham_number = (22.5 * eps * bvps) ** 0.5
    upside_pct = round((graham_number / price - 1) * 100, 1) if price else None
    return {
        "graham_number": round(graham_number, 2),
        "graham_upside_%": upside_pct,
        "undervalued_per_graham": price < graham_number,
    }


# عتبات قرار التوصية - عدّلها هنا لو حابب تشدد أو تخفف الشروط
VERDICT_BUY_MIN_SHORT = 65
VERDICT_BUY_MIN_LONG = 65
VERDICT_SELL_MAX_SHORT = 35
VERDICT_SELL_MAX_LONG = 40


def compute_verdict(row: dict, include_fundamentals: bool) -> dict:
    """
    توصية "شراء / انتظار / بيع" مبنية على تحقق التحليل الفني والمالي **مع بعض**،
    مش أي واحد لوحده. القاعدة:

    - لو البيانات ناقصة (مفيش درجة فنية/طويلة، أو السيولة ضعيفة، أو التحليل
      المالي كان مطلوب لكن بياناته رجعت فاضية) -> "انتظار" مع سبب واضح،
      عشان محدش ياخد قرار على بيانات غير مكتملة.
    - شراء: الدرجة القصيرة والطويلة **الاتنين** فوق العتبة، والسيولة كافية.
    - بيع: الدرجة القصيرة والطويلة **الاتنين** تحت العتبة.
    - غير كده: انتظار (إشارات متضاربة - مثلاً فني كويس ومالي ضعيف، أو العكس).

    بيرجع dict فيه "التوصية" (نص) و"ترتيب_التوصية" (رقم للترتيب: 0=شراء
    أولاً، 1=انتظار، 2=بيع أخيراً) عشان تقدر ترتب بيه الجدول بسهولة.
    """
    short = row.get("short_term_score")
    long_ = row.get("long_term_score")
    liquid = row.get("meets_liquidity_min")
    fundamentals_fetched = row.get("fundamentals_fetched", True)

    if short is None or long_ is None:
        return {"التوصية": "🟡 انتظار (بيانات غير كافية)", "ترتيب_التوصية": 1}

    if liquid is False:
        return {"التوصية": "🟡 انتظار (سيولة ضعيفة)", "ترتيب_التوصية": 1}

    if include_fundamentals and not fundamentals_fetched:
        return {"التوصية": "🟡 انتظار (بيانات مالية ناقصة)", "ترتيب_التوصية": 1}

    if short >= VERDICT_BUY_MIN_SHORT and long_ >= VERDICT_BUY_MIN_LONG:
        return {"التوصية": "🟢 شراء", "ترتيب_التوصية": 0}

    if short <= VERDICT_SELL_MAX_SHORT and long_ <= VERDICT_SELL_MAX_LONG:
        return {"التوصية": "🔴 بيع", "ترتيب_التوصية": 2}

    return {"التوصية": "🟡 انتظار (إشارات متضاربة)", "ترتيب_التوصية": 1}


# ---------------------------------------------------------------------------
# 3) تحميل البيانات وتحليل سهم واحد
# ---------------------------------------------------------------------------
def analyze_ticker(ticker: str, provider, include_fundamentals: bool = True,
                    min_avg_trade_value: float = DEFAULT_MIN_AVG_TRADE_VALUE,
                    td_live_price=None, tv_live_price=None) -> dict | None:
    yahoo_symbol = resolve_symbol(ticker)  # ممكن يبقى مختلف عن ticker لو فيه رمز بديل مسجّل
    try:
        df = provider.get_price_history(yahoo_symbol, period_days=HISTORY_DAYS)
    except Exception as e:
        print(f"⚠️  فشل تحميل بيانات {ticker}: {e}")
        return None

    if df is None or df.empty or len(df) < 60:
        print(f"⚠️  بيانات غير كافية لـ {ticker}")
        return None

    close = df["Close"].squeeze()
    volume = df["Volume"].squeeze()

    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean() if len(close) >= 200 else pd.Series([np.nan] * len(close))
    rsi = compute_rsi(close)
    macd_line, signal_line, hist = compute_macd(close)
    upper_bb, mid_bb, lower_bb = compute_bollinger(close)

    last_price = float(close.iloc[-1])  # افتراضياً: آخر إغلاق يومي متاح من السلسلة التاريخية
    price_is_live = False
    price_source = "historical_close"

    # الأولوية 0: سعر أدخلته إنت يدوياً - أعلى أولوية من أي مصدر آلي، لأنك
    # إنت اللي تأكدت منه بنفسك
    manual_entry = MANUAL_PRICES.get(ticker)
    if manual_entry is not None:
        last_price = float(manual_entry["price"])
        price_is_live = True
        price_source = "manual"

    # الأولوية 1: Twelve Data (لو المستخدم مفعّلها بـ API key) - أدق مصدر لحظي
    # عندنا حالياً، خصوصاً للأسهم الأمريكية (مجاني ولحظي فعلاً على باقة Basic)
    if not price_is_live and td_live_price is not None:
        td_result = td_live_price.get_price(ticker)
        if td_result.get("is_live") and td_result.get("price"):
            last_price = float(td_result["price"])
            price_is_live = True
            price_source = "twelvedata"

    # الأولوية 2: TradingView (لو المستخدم مفعّلها) - مجاني، غير رسمي، وتغطيته
    # لمصر أقوى بكتير من Yahoo عادةً
    if not price_is_live and tv_live_price is not None:
        tv_result = tv_live_price.get_price(ticker)
        if tv_result.get("is_live") and tv_result.get("price"):
            last_price = float(tv_result["price"])
            price_is_live = True
            price_source = "tradingview"

    # الأولوية 3: fast_info من نفس مزود البيانات (Yahoo) - لو الاتنين اللي فوق
    # مش مفعّلين أو فشلوا لسبب ما
    if not price_is_live:
        live = provider.get_live_price(yahoo_symbol)
        if live.get("is_live") and live.get("price"):
            last_price = float(live["price"])
            price_is_live = True
            price_source = "yahoo_fast_info"

    last_rsi = float(rsi.iloc[-1])
    last_sma20 = float(sma20.iloc[-1])
    last_sma50 = float(sma50.iloc[-1])
    last_sma200 = float(sma200.iloc[-1]) if not pd.isna(sma200.iloc[-1]) else None
    last_hist = float(hist.iloc[-1])
    prev_hist = float(hist.iloc[-2])
    avg_vol20 = float(volume.rolling(20).mean().iloc[-1])
    last_vol = float(volume.iloc[-1])

    # سعر بيع مستهدف (تقني) = النطاق العلوي لبولينجر باندز - مقاومة فنية
    # طبيعية بناءً على تذبذب السعر خلال آخر 20 يوم. لو السعر الحالي فوقه
    # أصلاً، يبقى السهم متشبع شرائياً ومفيش "هامش صعود" تقني واضح متبقي.
    last_upper_bb = float(upper_bb.iloc[-1]) if not pd.isna(upper_bb.iloc[-1]) else None
    if last_upper_bb is not None and last_upper_bb > last_price:
        target_sell_price = round(last_upper_bb, 2)
        target_sell_upside_pct = round((target_sell_price / last_price - 1) * 100, 1)
    else:
        target_sell_price = None
        target_sell_upside_pct = None

    # وقف خسارة مقترح (تقني) = النطاق السفلي لبولينجر باندز - دعم فني طبيعي.
    # لو السعر الحالي تحته أصلاً، يبقى السهم كسر الدعم فعلاً (إشارة خطر أعلى
    # من كونه مجرد "وقف خسارة مستقبلي" - نعرضه برضو بس نوضح إنه مكسور).
    last_lower_bb = float(lower_bb.iloc[-1]) if not pd.isna(lower_bb.iloc[-1]) else None
    if last_lower_bb is not None:
        stop_loss_price = round(last_lower_bb, 2)
        stop_loss_downside_pct = round((stop_loss_price / last_price - 1) * 100, 1)
        stop_loss_already_broken = last_price < last_lower_bb
    else:
        stop_loss_price = None
        stop_loss_downside_pct = None
        stop_loss_already_broken = None

    # متوسط قيمة التداول اليومية (جنيه) = السعر × الكمية، متوسط على آخر LIQUIDITY_LOOKBACK_DAYS يوم
    trade_value = close * volume
    avg_trade_value = float(trade_value.rolling(LIQUIDITY_LOOKBACK_DAYS).mean().iloc[-1])
    meets_liquidity_min = avg_trade_value >= min_avg_trade_value

    ret_3m = (last_price / close.iloc[-63] - 1) * 100 if len(close) > 63 else np.nan
    ret_1y = (last_price / close.iloc[0] - 1) * 100

    daily_ret = close.pct_change().dropna()
    volatility = float(daily_ret.std() * np.sqrt(252) * 100)

    # نظام تقييم قصير المدى
    short_score = 50
    if last_rsi < 30:
        short_score += 20          
    elif last_rsi > 70:
        short_score -= 20          
    if last_hist > 0 and prev_hist <= 0:
        short_score += 15          
    elif last_hist < 0 and prev_hist >= 0:
        short_score -= 15          
    if last_price > last_sma20:
        short_score += 10
    else:
        short_score -= 10
    if last_vol > 1.5 * avg_vol20:
        short_score += 5           
    short_score = max(0, min(100, short_score))

    # نظام تقييم طويل المدى
    long_score = 50
    if last_sma200 is not None:
        if last_price > last_sma200:
            long_score += 15
        else:
            long_score -= 15
        if last_sma50 > last_sma200:
            long_score += 10        
        else:
            long_score -= 10
    if not np.isnan(ret_1y):
        if ret_1y > 15:
            long_score += 15
        elif ret_1y < -15:
            long_score -= 15
    if volatility < 25:
        long_score += 10            
    elif volatility > 45:
        long_score -= 10
    long_score = max(0, min(100, long_score))

    result = {
        "ticker": ticker,
        "sector": get_sector(ticker),
        "egx_index": get_egx_index(ticker),
        "is_major_exporter": get_is_major_exporter(ticker),
        "price": round(last_price, 2),
        "price_is_live": price_is_live,
        "price_source": price_source,
        "manual_price_updated_at": manual_entry["updated_at"] if manual_entry else None,
        "rsi": round(last_rsi, 1),
        "macd_hist": round(last_hist, 3),
        "above_sma20": last_price > last_sma20,
        "above_sma200": (last_sma200 is not None and last_price > last_sma200),
        "ret_3m_%": round(ret_3m, 1) if not np.isnan(ret_3m) else None,
        "ret_1y_%": round(ret_1y, 1),
        "volatility_%": round(volatility, 1),
        "avg_trade_value": round(avg_trade_value, 0),
        "meets_liquidity_min": meets_liquidity_min,
        "target_sell_price": target_sell_price,
        "target_sell_upside_%": target_sell_upside_pct,
        "stop_loss_price": stop_loss_price,
        "stop_loss_downside_%": stop_loss_downside_pct,
        "stop_loss_already_broken": stop_loss_already_broken,
        "short_term_score": short_score,
        "long_term_technical_score": long_score,
    }

    if include_fundamentals:
        fundamentals = provider.get_fundamentals(yahoo_symbol)
        fund_score = score_fundamentals(fundamentals)
        result.update(fundamentals)
        result["fundamental_score"] = fund_score
        result["long_term_score"] = round(0.5 * long_score + 0.5 * fund_score, 1)

        # لو كل قيم fundamentals رجعت None، يبقى المصدر رفض/حظر الطلب - مش إن
        # الشركة مالهاش بيانات فعلاً. نسجل ده صراحة عشان الواجهة تقدر تنبّهك.
        result["fundamentals_fetched"] = any(v is not None for v in fundamentals.values())

        # --- قاعدة جراهام للسعر العادل ---
        # Yahoo Finance غالباً مش بيرجع trailingEps/bookValue مباشرة لمعظم أسهم EGX.
        # كحل بديل، نشتقهم رياضياً من P/E وP/B (المتوفرين بشكل أوسع):
        #   EPS  = السعر ÷ P/E
        #   BVPS = السعر ÷ P/B
        eps = fundamentals.get("eps")
        bvps = fundamentals.get("book_value_per_share")
        eps_is_derived = False
        bvps_is_derived = False

        pe = fundamentals.get("pe_ratio")
        pb = fundamentals.get("pb_ratio")

        if eps is None and pe is not None and pe > 0:
            eps = last_price / pe
            eps_is_derived = True
        if bvps is None and pb is not None and pb > 0:
            bvps = last_price / pb
            bvps_is_derived = True

        # نحدّث النتيجة بالقيم الفعلية المستخدمة في الحساب (سواء جاية من Yahoo
        # مباشرة أو مُشتقة من P/E و P/B) - عشان تقدر تتأكد بنفسك من رقم جراهام
        result["eps"] = round(eps, 3) if eps is not None else None
        result["book_value_per_share"] = round(bvps, 3) if bvps is not None else None
        result["eps_estimated"] = eps_is_derived
        result["bvps_estimated"] = bvps_is_derived

        graham = compute_graham(eps=eps, bvps=bvps, price=last_price)
        result.update(graham)
        result["pe_below_15"] = (pe is not None and 0 < pe < 15)
    else:
        result["long_term_score"] = long_score

    result.update(compute_verdict(result, include_fundamentals))

    return result


def run_screener(tickers=None, include_fundamentals=True, save_csv=True, verbose=True,
                  provider=None, provider_name="yahoo", provider_kwargs=None,
                  min_avg_trade_value=DEFAULT_MIN_AVG_TRADE_VALUE, td_live_price=None, tv_live_price=None):
    if provider is None:
        provider = get_provider(provider_name, **(provider_kwargs or {}))

    tickers = tickers or EGX_TICKERS
    results = []
    for t in tickers:
        if verbose:
            print(f"جاري تحليل {t} ...")
        r = analyze_ticker(t, provider, include_fundamentals=include_fundamentals,
                            min_avg_trade_value=min_avg_trade_value,
                            td_live_price=td_live_price, tv_live_price=tv_live_price)
        if r:
            results.append(r)
        time.sleep(0.5)  

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    if save_csv:
        df.to_csv("egx_screener_results.csv", index=False, encoding="utf-8-sig")
    return df


if __name__ == "__main__":
    run_screener()
