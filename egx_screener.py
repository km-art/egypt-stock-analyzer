import time
import numpy as np
import pandas as pd

from data_providers import get_provider

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

HISTORY_DAYS = 365 + 30

# الحد الأدنى لمتوسط قيمة التداول اليومية (بالجنيه المصري) عشان السهم يعتبر "سائل بما يكفي"
MIN_AVG_TRADE_VALUE_EGP = 3_000_000
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


# ---------------------------------------------------------------------------
# 3) تحميل البيانات وتحليل سهم واحد
# ---------------------------------------------------------------------------
def analyze_ticker(ticker: str, provider, include_fundamentals: bool = True) -> dict | None:
    try:
        df = provider.get_price_history(ticker, period_days=HISTORY_DAYS)
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

    last_price = float(close.iloc[-1])  # افتراضياً: آخر إغلاق يومي متاح من السلسلة التاريخية
    price_is_live = False

    # نحاول نجيب سعر أقرب للحظي (delayed quote) بدل الاكتفاء بآخر إغلاق يومي.
    # لو مش متاح (المزود مش بيدعمها أو فشل الطلب)، بنفضل مستخدمين آخر إغلاق
    # يومي عادي - مفيش تأثير سلبي، بس مفيش تحسين.
    live = provider.get_live_price(ticker)
    if live.get("is_live") and live.get("price"):
        last_price = float(live["price"])
        price_is_live = True

    last_rsi = float(rsi.iloc[-1])
    last_sma20 = float(sma20.iloc[-1])
    last_sma50 = float(sma50.iloc[-1])
    last_sma200 = float(sma200.iloc[-1]) if not pd.isna(sma200.iloc[-1]) else None
    last_hist = float(hist.iloc[-1])
    prev_hist = float(hist.iloc[-2])
    avg_vol20 = float(volume.rolling(20).mean().iloc[-1])
    last_vol = float(volume.iloc[-1])

    # متوسط قيمة التداول اليومية (جنيه) = السعر × الكمية، متوسط على آخر LIQUIDITY_LOOKBACK_DAYS يوم
    trade_value = close * volume
    avg_trade_value = float(trade_value.rolling(LIQUIDITY_LOOKBACK_DAYS).mean().iloc[-1])
    meets_liquidity_min = avg_trade_value >= MIN_AVG_TRADE_VALUE_EGP

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

    sector_info = EGX_SECTORS.get(ticker, {})

    result = {
        "ticker": ticker,
        "sector": sector_info.get("sector", "غير مصنف"),
        "is_major_exporter": sector_info.get("is_major_exporter", False),
        "price": round(last_price, 2),
        "price_is_live": price_is_live,
        "rsi": round(last_rsi, 1),
        "macd_hist": round(last_hist, 3),
        "above_sma20": last_price > last_sma20,
        "above_sma200": (last_sma200 is not None and last_price > last_sma200),
        "ret_3m_%": round(ret_3m, 1) if not np.isnan(ret_3m) else None,
        "ret_1y_%": round(ret_1y, 1),
        "volatility_%": round(volatility, 1),
        "avg_trade_value_egp": round(avg_trade_value, 0),
        "meets_liquidity_min": meets_liquidity_min,
        "short_term_score": short_score,
        "long_term_technical_score": long_score,
    }

    if include_fundamentals:
        fundamentals = provider.get_fundamentals(ticker)
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

    return result


def run_screener(tickers=None, include_fundamentals=True, save_csv=True, verbose=True,
                  provider=None, provider_name="yahoo", provider_kwargs=None):
    if provider is None:
        provider = get_provider(provider_name, **(provider_kwargs or {}))

    tickers = tickers or EGX_TICKERS
    results = []
    for t in tickers:
        if verbose:
            print(f"جاري تحليل {t} ...")
        r = analyze_ticker(t, provider, include_fundamentals=include_fundamentals)
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
