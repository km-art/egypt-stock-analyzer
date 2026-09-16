"""
eagle_core.py — منطق التسجيل والقرار الصافي (Pure Logic) لأداة تحليل
البورصة المصرية - مستخرج من final_bot.py حرفياً بدون أي تعديل منطقي.

الهدف: نفس الكود اللي بيحسب Eagle Score/Data Confidence/Signal
Conflicts/Final Decision في التطبيق الحي (final_bot.py) هو نفسه بالحرف
اللي بيستخدمه Backtest Engine (backtest_engine.py) - عشان أي نتيجة
Calibration تبقى صادقة فعلاً على نفس المنطق المستخدم في الإنتاج، مش نسخة
موازية ممكن تنحرف عنه بمرور الوقت.

⚠️ قاعدة صيانة: أي تعديل مستقبلي على دوال التسجيل في final_bot.py **لازم
يتنقل هنا يدوياً بالمثل** لحد ما يتعمل ترحيل حقيقي بحيث final_bot.py
نفسه يستورد من الملف ده بدل تكرار الكود (موصى بيه، مش متنفذ لسه).

مفيش أي Streamlit، مفيش أي شبكة - ملف منطق حسابي صافي بس (pandas/numpy).
"""
import pandas as pd
import numpy as np

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

    # --- RVOL (الحجم النسبي) = فوليوم اليوم ÷ متوسط فوليوم 20 يوم ---
    # بيتربط باتجاه السعر لاحقاً في منطق الفلترة (فوليوم عالي مش إيجابي تلقائياً،
    # ده بيبقى تصريف لو حصل مع هبوط سعر مش صعود)
    df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()
    df['RVOL'] = df['Volume'] / (df['Vol_MA20'] + 0.00001)

    # --- ATR (متوسط المدى الحقيقي) - مقياس التقلب الفعلي للسهم ---
    prev_close = df['Close'].shift(1)
    true_range = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - prev_close).abs(),
        (df['Low'] - prev_close).abs(),
    ], axis=1).max(axis=1)
    df['ATR_14'] = true_range.rolling(window=14).mean()
    df['ATR_%'] = (df['ATR_14'] / df['Close']) * 100  # ATR كنسبة من السعر، عشان تقارن بين أسهم بأسعار مختلفة

    # --- ADX (قوة الاتجاه) + DI+ / DI- ---
    up_move = df['High'].diff()
    down_move = -df['Low'].diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)
    atr_for_di = true_range.rolling(window=14).mean() + 0.00001
    plus_di = 100 * (plus_dm.rolling(window=14).mean() / atr_for_di)
    minus_di = 100 * (minus_dm.rolling(window=14).mean() / atr_for_di)
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di + 0.00001))
    df['ADX_14'] = dx.rolling(window=14).mean()
    df['Plus_DI'] = plus_di
    df['Minus_DI'] = minus_di

    # --- قرب السهم من أعلى/أدنى سعر خلال آخر سنة (52 أسبوع تقريباً = 252 يوم تداول) ---
    lookback_52w = min(len(df), 252)
    df['High_52W'] = df['High'].rolling(window=lookback_52w, min_periods=1).max()
    df['Low_52W'] = df['Low'].rolling(window=lookback_52w, min_periods=1).min()
    df['Dist_From_52W_High_%'] = ((df['Close'] - df['High_52W']) / df['High_52W']) * 100  # سالب أو صفر
    df['Dist_From_52W_Low_%'] = ((df['Close'] - df['Low_52W']) / df['Low_52W']) * 100      # موجب أو صفر

    # --- التقلب اليومي (% متوسط حجم التذبذب اليومي خلال آخر 14 يوم) ---
    daily_return_pct = df['Close'].pct_change() * 100
    df['Daily_Volatility_%'] = daily_return_pct.rolling(window=14).std()

    # --- عدد أيام الصعود المتتالية (لحد آخر يوم) ---
    is_up_day = (df['Close'].diff() > 0).astype(int)
    # عداد يتصفر أول ما يوم هابط أو ثابت يحصل، وبيتراكم في أيام الصعود
    streak = is_up_day.copy()
    for idx in range(1, len(streak)):
        if is_up_day.iloc[idx] == 1:
            streak.iloc[idx] = streak.iloc[idx - 1] + 1
        else:
            streak.iloc[idx] = 0
    df['Consecutive_Up_Days'] = streak

    # --- Accumulation/Distribution Line (تجميع/تصريف) ---
    # Money Flow Multiplier: بيقيس فين قفل السهم داخل مدى اليوم (High-Low)
    high_low_range = (df['High'] - df['Low']).replace(0, 0.0001)
    money_flow_multiplier = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / high_low_range
    money_flow_volume = money_flow_multiplier * df['Volume']
    df['AD_Line'] = money_flow_volume.cumsum()
    # ميل خط A/D خلال آخر 10 أيام - بيوضح هل في تجميع هادي (يصعد) أو تصريف (يهبط)
    df['AD_Line_Slope_10d'] = df['AD_Line'].diff(10)

    return df



def find_support_resistance(df, order: int = 5, max_lookback: int = 150):
    """
    محرك دعم/مقاومة بسيط: بيدوّر على "نقاط انعكاس" (Swing High/Low) في آخر
    max_lookback يوم - أي نقطة أعلى (أو أدنى) من الأيام اللي حواليها بمقدار
    `order` يوم من الجهتين. من كل النقط دي، بنرجع أقرب مقاومة فوق السعر
    الحالي وأقرب دعم تحته.

    يرجع (nearest_support, nearest_resistance) - أي منهم ممكن يرجع None
    لو مفيش بيانات كافية أو مفيش نقطة مناسبة.
    """
    sub = df.tail(max_lookback)
    highs = sub['High'].values
    lows = sub['Low'].values
    n = len(sub)
    if n < (order * 2 + 5):
        return None, None

    current_price = float(sub['Close'].iloc[-1])
    resistance_levels = []
    support_levels = []
    for i in range(order, n - order):
        window_h = highs[i - order:i + order + 1]
        if highs[i] == window_h.max():
            resistance_levels.append(float(highs[i]))
        window_l = lows[i - order:i + order + 1]
        if lows[i] == window_l.min():
            support_levels.append(float(lows[i]))

    resistances_above = [r for r in resistance_levels if r > current_price]
    supports_below = [s for s in support_levels if s < current_price]
    nearest_resistance = min(resistances_above) if resistances_above else None
    nearest_support = max(supports_below) if supports_below else None
    return nearest_support, nearest_resistance


# ---------------------------------------------------------------------------
# Eagle Score V2 - نظام النقاط الموحّد - EAGLE INVESTOR OS 2.0 Phase 1
# (Stock_Scanner_V4_Unified_Implementation_Spec، قسم 27)
# ---------------------------------------------------------------------------
# مبدأ أساسي من الوثيقة: ENGINE CAPABILITY ≠ DATA PROVIDER AVAILABILITY.
# News/Macro/Geopolitical/Early Move (اللي محتاج بيانات لحظية داخل
# الجلسة) مش موجودين هنا خالص لأننا معندناش مزود بيانات حقيقي ليهم -
# مش هنّدّعي إنهم شغالين. لو حد منهم اتضاف مستقبلاً، هيتحط كمكوّن جديد
# في الـdict ده بس، من غير أي تعديل في باقي المحرك.
EAGLE_WEIGHTS = {
    "trend": 15, "momentum": 10, "volume_rvol": 10, "fundamentals": 20,
    "valuation": 10, "relative_strength": 10, "market_depth": 15,
    "risk_reward": 10, "liquidity": 5, "market_regime": 10,
    "breadth": 5, "sector_strength": 5,
}
DISABLED_ENGINES_NO_PROVIDER = ["early_move", "news_impact", "macro", "geopolitical", "options_volatility"]



def market_regime_score_component(regime_info: dict):
    """
    تحويل حالة السوق لنقاط (10 من Eagle Score V2 Phase 1): في سوق صاعد أو
    عرضي هادي، الفرص الفردية أوثق - في سوق هابط أو شديد التقلب، حتى أقوى
    سهم محاط بمخاطرة أعلى فبنطفي النقاط شوية كتنبيه ضمني، مش عقاب على
    السهم نفسه.
    """
    if not regime_info:
        return None
    regime = regime_info["regime"]
    if "Bull" in regime: return 10.0
    if "Sideways" in regime: return 6.0
    if "Bear" in regime: return 2.0
    if "High Volatility" in regime: return 1.0
    return 5.0



def breadth_score_component(breadth_info: dict):
    """
    Breadth (5 نقاط - جديدة في Phase 1): نسبة الأسهم الصاعدة في نفس جلسة
    المسح. اتساع صاعد قوي بيدّي ثقة إضافية إن الحركة مش سهم واحد لوحده.
    يرجع None لو مفيش مسح اتعمل في الجلسة دي لسه (مش صفر - عشان مايتحسبش
    ضد السهم بالغلط).
    """
    if not breadth_info or breadth_info.get("score") is None:
        return None
    score = breadth_info["score"]
    if score >= 65: return 5.0
    if score >= 50: return 3.5
    if score >= 35: return 2.0
    return 0.5


# ---------------------------------------------------------------------------
# Global Market Engine + Gold/Silver Ratio - V3 (قسم 4 و7-14)
# ---------------------------------------------------------------------------
GLOBAL_ASSETS = {
    "fx": {
        "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
        "USD/CHF": "USDCHF=X", "USD/CNY": "USDCNY=X", "USD/TRY": "USDTRY=X",
        "USD/BRL": "USDBRL=X", "USD/EGP": "USDEGP=X",
    },
    "crypto": {
        "Bitcoin (BTC)": "BTC-USD", "Ethereum (ETH)": "ETH-USD",
        "Solana (SOL)": "SOL-USD", "BNB": "BNB-USD", "XRP": "XRP-USD",
    },
    "metals": {
        "الذهب (Gold)": "GC=F", "الفضة (Silver)": "SI=F",
        "البلاتين (Platinum)": "PL=F", "البلاديوم (Palladium)": "PA=F",
        "النحاس (Copper)": "HG=F",
    },
    "energy": {
        "خام WTI": "CL=F", "خام برنت (Brent)": "BZ=F", "الغاز الطبيعي": "NG=F",
    },
}



def _score_trend(e9, e21, adx_val, p, ema200_ok=None):
    """Trend (15 نقطة): تقاطع EMA9/21 + قوة الاتجاه ADX."""
    score = 0.0
    if e9 > e21:
        score += 8
    strength_bonus = min(adx_val / 40, 1.0) * 7  # ADX=40+ يدي أقصى بونص
    score += strength_bonus
    return round(min(score, 15), 1)



def _score_momentum(r, m, u, l, p):
    """Momentum (10 نقاط): نفس منطق momentum_score القديم بس مُعاد توزينه لـ10."""
    score = 0.0
    if 50 <= m <= 70: score += 3.5
    elif 35 <= m < 50: score += 1.5
    elif m > 85: score -= 3
    if 45 <= r <= 65: score += 3.5
    elif r > 78: score -= 4
    if u > l:
        score += ((u - p) / (u - l)) * 3
    return round(max(min(score, 10), -10), 1)



def _score_volume_rvol(rvol, price_up_today):
    """Volume/RVOL (10 نقاط): حجم نسبي مربوط باتجاه السعر."""
    if rvol >= 2.0:
        return 10.0 if price_up_today else -5.0
    if rvol >= 1.5:
        return 7.0 if price_up_today else -3.0
    if rvol >= 1.0:
        return 4.0 if price_up_today else 1.0
    return 1.0



def _score_liquidity(avg_trade_value):
    """Liquidity (5 نقاط في Eagle Score 2.0): حسب متوسط قيمة التداول اليومي التقريبي."""
    if avg_trade_value >= 20_000_000: return 5.0
    if avg_trade_value >= 5_000_000: return 3.75
    if avg_trade_value >= 1_000_000: return 2.5
    if avg_trade_value >= 300_000: return 1.25
    return 0.0



def _score_price_structure(p, nearest_support, nearest_resistance, dist_low_52w, dist_high_52w):
    """Price Structure (10 نقاط): موقع السعر بين الدعم والمقاومة + موقعه من مدى 52 أسبوع."""
    score = 0.0
    if nearest_support is not None and nearest_resistance is not None and nearest_resistance > nearest_support:
        position_in_range = (p - nearest_support) / (nearest_resistance - nearest_support)
        # وسط النطاق (مش ملتصق بمقاومة ولا دعم) بيدي أعلى نقاط - مساحة تحرك في الاتجاهين
        score += 6 * (1 - abs(position_in_range - 0.5) * 2) if 0 <= position_in_range <= 1 else 2
    else:
        score += 3  # مفيش هيكل واضح - نقاط محايدة
    # قريب من قاع 52 أسبوع بمعقولية = فرصة، بعيد جداً عن القمة يعني مساحة صعود
    if dist_high_52w <= -15:
        score += 4  # مساحة صعود لسه موجودة
    elif dist_high_52w >= -3:
        score += 1  # قريب من القمة، مساحة صعود محدودة
    else:
        score += 2.5
    return round(min(score, 10), 1)



def _score_breakout(p, nearest_resistance, rvol, price_up_today):
    """Breakout (8 نقاط): اختراق مقاومة قريبة بحجم مؤيد."""
    if nearest_resistance is None:
        return 2.0
    dist_to_resistance_pct = (nearest_resistance - p) / p * 100
    if p > nearest_resistance and rvol >= 1.5 and price_up_today:
        return 8.0  # اختراق فعلي بحجم قوي
    if p > nearest_resistance:
        return 5.0  # اختراق بس بدون تأكيد حجم قوي
    if 0 < dist_to_resistance_pct <= 3:
        return 3.0  # قريب جداً من الاختراق
    return 1.0



def _score_relative_strength(stock_change_20d, egx30_change_20d):
    """Relative Strength (10 نقاط في Eagle Score 2.0): أداء السهم مقابل مؤشر EGX30 خلال 20 يوم."""
    if stock_change_20d is None or egx30_change_20d is None:
        return None  # مش N/A بصفر - علشان مايتحسبش ضد السهم بالغلط
    relative_pct = stock_change_20d - egx30_change_20d
    if relative_pct >= 15: return 10.0
    if relative_pct >= 5: return 7.5
    if relative_pct >= 0: return 5.0
    if relative_pct >= -10: return 2.5
    return 0.0



def _score_sector_strength(sector_avg_change, overall_avg_change):
    """Sector Strength (5 نقاط في Phase 1): متوسط أداء قطاع السهم مقابل متوسط أداء كل الأسهم الممسوحة."""
    if sector_avg_change is None or overall_avg_change is None:
        return None
    relative_pct = sector_avg_change - overall_avg_change
    if relative_pct >= 5: return 5.0
    if relative_pct >= 0: return 3.0
    if relative_pct >= -5: return 1.0
    return 0.0



def _score_accumulation_distribution(ad_slope_10d, vol_ma10):
    """Accumulation/Distribution (5 نقاط): ميل خط A/D خلال آخر 10 أيام."""
    if ad_slope_10d is None or vol_ma10 in (None, 0):
        return 2.5  # محايد لو مفيش بيانات كافية
    # تطبيع الميل بالنسبة لحجم التداول عشان يبقى قابل للمقارنة بين الأسهم
    normalized_slope = ad_slope_10d / (vol_ma10 * 10)
    if normalized_slope > 0.3: return 5.0
    if normalized_slope > 0.1: return 3.5
    if normalized_slope > -0.1: return 2.5
    if normalized_slope > -0.3: return 1.0
    return 0.0



def _score_risk_reward(rr_ratio):
    """Risk/Reward (10 نقاط)."""
    if rr_ratio is None:
        return 2.0  # محايد منخفض - مفيش هدف/وقف واضح يتحسب عليهم
    if rr_ratio >= 3: return 10.0
    if rr_ratio >= 2: return 8.0
    if rr_ratio >= 1.5: return 6.0
    if rr_ratio >= 1: return 4.0
    return 1.0



def _score_fundamentals(fund_score):
    """Fundamentals (20 نقطة في Eagle Score 2.0 - وزن كبير عمداً بعد ما كان صغير جداً في V2)."""
    if fund_score is None:
        return None
    return round((fund_score / 100) * 20, 2)



def _score_valuation(graham_upside_pct):
    """
    Valuation (10 نقاط - جديدة في 2.0): مبنية على فرق قاعدة جراهام %
    (نفس الرقم المعروض فعلاً في عمود 'فرق جراهام %'). كل ما السهم أرخص من
    قيمته العادلة المحسوبة، كل ما النقاط أعلى.
    """
    if graham_upside_pct is None:
        return None
    if graham_upside_pct >= 30: return 10.0
    if graham_upside_pct >= 15: return 7.5
    if graham_upside_pct >= 0: return 5.0
    if graham_upside_pct >= -15: return 2.5
    return 0.0



def _score_market_depth(depth_metrics):
    """Market Depth (15 نقطة في Phase 1 - وزنها زاد عشان دي أولوية مؤكدة في الخطة) - لو متاحة وسليمة بس، وإلا None (مش صفر)."""
    if not depth_metrics:
        return None
    imb = depth_metrics.get("imbalance_%")
    spread = depth_metrics.get("spread_%")
    if imb is None:
        return None
    score = 7.5 + (imb / 100) * 7.5  # من صفر لـ15 حسب عدم التوازن (-100%..+100%)
    score = max(min(score, 15.0), 0.0)
    if spread is not None and spread > 1.0:  # Spread عالي = سيولة لحظية ضعيفة، بيقلل الثقة
        score *= 0.7
    return round(score, 1)



def compute_eagle_score(components: dict):
    """
    بيجمع كل المكونات مع بعض. أي مكوّن قيمته None (زي Market Depth لو مش
    متاح، أو Relative Strength لو فشل EGX30) **بيتشال من الحساب تماماً
    وبيتشال وزنه من المجموع الكلي**، فالنتيجة النهائية بتفضل من 100 لكل
    الأسهم المتاحة ليها نفس عدد المكونات - مفيش سهم بيتظلم لمجرد إن مصدر
    بيانات اختياري (زي Market Depth) مش شغال له.
    """
    total_score = 0.0
    total_possible = 0.0
    available_components = {}
    for key, weight in EAGLE_WEIGHTS.items():
        value = components.get(key)
        if value is None:
            continue
        total_score += value
        total_possible += weight
        available_components[key] = value

    if total_possible <= 0:
        return {"eagle_score": None, "components": available_components, "components_used": 0}

    eagle_score_100 = round((total_score / total_possible) * 100, 1)
    # تثبيت النطاق 0-100 صراحةً: بعض المكوّنات (Momentum، Volume/RVOL)
    # بترجع قيم سالبة كعقوبة، فمن غير الحد ده النتيجة النهائية كانت ممكن
    # تطلع بالسالب وهو شكل غير منطقي لدرجة من 100 - القيم الأصلية لكل
    # مكوّن (available_components) لسه محفوظة زي ما هي للشرح والتفسير.
    eagle_score_100 = max(min(eagle_score_100, 100.0), 0.0)
    return {
        "eagle_score": eagle_score_100,
        "components": available_components,
        "components_used": len(available_components),
        "components_total": len(EAGLE_WEIGHTS),
    }



def compute_opportunity_risk_confidence(components: dict, eagle_result: dict, rr_ratio, atr_pct, depth_metrics):
    """
    EAGLE INVESTOR OS 2.0 (قسم 3): "لا نستخدم Score واحدًا فقط" - بنطلع
    3 مقاييس تانية لجانب Eagle Score نفسها:

    - Opportunity Score: قوة الفرصة (Trend+Momentum+Breakout لو موجودة+Valuation)
    - Risk Score: المخاطرة (عكسي - أعلى يعني مخاطرة أعلى) من التقلب (ATR)
      وRisk/Reward وجودة بيانات العمق
    - Confidence Score: مدى اكتمال البيانات اللي الـScore اتبني عليها
      (نفس فكرة قسم 18: Data Confidence بجانب كل إشارة)
    """
    comps = eagle_result.get("components", {})

    opportunity_parts = [comps.get(k) for k in ["trend", "momentum", "relative_strength", "valuation"] if comps.get(k) is not None]
    opportunity_score = round((sum(opportunity_parts) / max(len(opportunity_parts), 1)) * 10, 1) if opportunity_parts else None

    risk_penalty = 0.0
    risk_factors = 0
    if atr_pct is not None:
        risk_penalty += min(atr_pct / 8, 1.0) * 40  # تقلب عالي = مخاطرة أعلى
        risk_factors += 1
    if rr_ratio is not None:
        risk_penalty += max(0, (2 - rr_ratio)) * 15  # RR ضعيف = مخاطرة أعلى
        risk_factors += 1
    if depth_metrics is not None and depth_metrics.get("spread_%") is not None:
        risk_penalty += min(depth_metrics["spread_%"] / 2, 1.0) * 20
        risk_factors += 1
    risk_score = round(min(risk_penalty, 100), 1) if risk_factors > 0 else None

    confidence_score = round((eagle_result.get("components_used", 0) / max(eagle_result.get("components_total", 1), 1)) * 100, 1)

    return {"opportunity_score": opportunity_score, "risk_score": risk_score, "confidence_score": confidence_score}



def determine_entry_quality(eagle_score, dist_to_resistance_pct, rr_ratio, depth_metrics, spread_threshold=1.0):
    """
    Entry Quality (قسم 10 من الخطة): BUY NOW / BUY ON PULLBACK /
    WAIT FOR BREAKOUT / AVOID.
    """
    depth_confirms = depth_metrics is not None and (depth_metrics.get("imbalance_%") or 0) > 10
    spread_ok = depth_metrics is None or (depth_metrics.get("spread_%") or 0) <= spread_threshold

    if eagle_score is None:
        return "⚪ غير محدد (بيانات غير كافية)"
    if not spread_ok:
        return "🔴 AVOID (Spread مرتفع - سيولة لحظية ضعيفة)"
    if rr_ratio is not None and rr_ratio < 1:
        return "🔴 AVOID (Risk/Reward ضعيف)"
    if eagle_score >= 65 and dist_to_resistance_pct is not None and dist_to_resistance_pct > 5:
        if depth_confirms or depth_metrics is None:
            return "🟢 BUY NOW (قوة عالية + مفيش مقاومة قريبة)"
    if eagle_score >= 65 and dist_to_resistance_pct is not None and 0 < dist_to_resistance_pct <= 5:
        return "🟡 WAIT FOR BREAKOUT (قريب من مقاومة، محتاج اختراق مؤكد)"
    if eagle_score >= 55:
        return "🟡 BUY ON PULLBACK (السهم قوي بس السعر ممتد، استنى رجوع لدعم)"
    if eagle_score < 40:
        return "🔴 AVOID (قوة إجمالية ضعيفة)"
    return "⚪ WAIT (مفيش إشارة واضحة كفاية)"


# ---------------------------------------------------------------------------
# Data Confidence Engine + Signal Conflict Engine + Final Decision
# Stock_Scanner_V4_Unified_Implementation_Spec (أقسام 26-28، 51)
# ---------------------------------------------------------------------------
DATA_STATUS_WEIGHT = {"LIVE": 1.0, "DELAYED": 0.7, "STALE": 0.3, "SIMULATED": 0.0}
# UNAVAILABLE و DISABLED_NO_PROVIDER بيتشالوا من الحساب تماماً - مش بيتحسبوا صفر
# (ده نفس مبدأ Eagle Score: مكوّن مش متاح يتشال بوزنه، مش يتعاقب عليه السهم)



def compute_data_confidence(component_statuses: dict, eagle_coverage_ratio: float = None):
    """
    component_statuses: {اسم المكوّن: حالته} من
    LIVE/DELAYED/STALE/SIMULATED/UNAVAILABLE/DISABLED_NO_PROVIDER.
    يرجع نسبة ثقة 0-100% + تفاصيل كل مكوّن، عشان يظهر بوضوح في Decision Card.

    eagle_coverage_ratio (إصلاح Data Availability Bias، Phase 1 Audit
    التفصيلي): نسبة مكوّنات Eagle Score المتاحة فعلياً (زي "2 من 12").
    من غيره، سهم عنده بس 2 مؤشر متاحين والاتنين ممتازين كان بيطلع بثقة
    100% - نفس ثقة سهم عنده الـ12 مؤشر شغالين. التفاضل ده بيتحل بضرب
    الثقة في نسبة التغطية، فسهم بتغطية ناقصة بياخد عقوبة ثقة تلقائياً
    بدل ما الرقم يطلع مضلل.
    """
    scored = {k: v for k, v in component_statuses.items() if v not in ("UNAVAILABLE", "DISABLED_NO_PROVIDER")}
    if not scored:
        return {"confidence_pct": 0.0, "statuses": component_statuses}
    total = sum(DATA_STATUS_WEIGHT.get(s, 0.0) for s in scored.values())
    confidence_pct = (total / len(scored)) * 100
    if eagle_coverage_ratio is not None:
        confidence_pct *= eagle_coverage_ratio
    return {"confidence_pct": round(confidence_pct, 1), "statuses": component_statuses}



def detect_signal_conflicts(eagle_score, market_regime_info, rvol, avg_trade_value,
                             depth_metrics, data_confidence_pct, rr_ratio, price_up_today,
                             breadth_info=None):
    """
    Signal Conflict Engine (قسم 26 - "يجب تنفيذه الآن" لأنه مش محتاج News
    API): بيدوّر على تضاربات بين الإشارات المختلفة. الهدف: مايبقاش القرار
    النهائي مبني على مؤشر واحد قوي وسط سياق يقول عكسه.
    """
    conflicts = []
    blocking = False

    if eagle_score is not None and eagle_score >= 65:
        if market_regime_info and "Bear" in market_regime_info["regime"]:
            conflicts.append("قوة فنية عالية، لكن السوق ككل في اتجاه هابط (Bear) - المخاطرة أعلى من المعتاد")
        if market_regime_info and "High Volatility" in market_regime_info["regime"]:
            conflicts.append("قوة فنية عالية، لكن السوق في وضع تقلب حاد - الإشارات الفردية أقل موثوقية دلوقتي")
        if avg_trade_value is not None and avg_trade_value < 300_000:
            conflicts.append("قوة فنية عالية، لكن السيولة ضعيفة جداً - صعوبة دخول/خروج بسعر عادل")
            blocking = True
        if depth_metrics is not None and (depth_metrics.get("spread_%") or 0) > 1.5:
            conflicts.append("قوة فنية عالية، لكن Spread مرتفع جداً - تكلفة تنفيذ عالية")
            blocking = True
        if breadth_info is not None and breadth_info.get("score") is not None and breadth_info["score"] < 35:
            conflicts.append("السهم منفرد قوي، لكن اتساع السوق ككل ضعيف (أغلبية الأسهم هابطة في نفس الجلسة) - تحقق قبل الاعتماد على قوة السهم لوحده")

    if data_confidence_pct is not None and data_confidence_pct < 50:
        conflicts.append(f"جودة/اكتمال البيانات منخفضة ({data_confidence_pct:.0f}%) - مينفعش نعتمد على إشارة شراء قوية")
        blocking = True

    if rr_ratio is not None and rr_ratio < 1 and eagle_score is not None and eagle_score >= 60:
        conflicts.append("قوة فنية عالية، لكن نسبة Risk/Reward ضعيفة - المخاطرة مش متناسبة مع الفرصة المحتملة")

    if rvol is not None and rvol >= 1.5 and not price_up_today:
        conflicts.append("حجم تداول مرتفع مع هبوط السعر - الشكل ده أقرب لتصريف مش تجميع")

    return {"conflicts": conflicts, "has_blocking_conflict": blocking, "conflict_count": len(conflicts)}


# Decision Thresholds - مركزية عشان يبقوا واضحين وقابلين للتدقيق (Phase 1
# Audit التفصيلي، قسم "Decision Thresholds") - مش سحرية متفرقة جوه الدوال
DECISION_THRESHOLDS = {
    "buy_min_eagle_score": 65,
    "buy_min_data_confidence": 70,
    "buy_min_rr_ratio": 1.5,
    "avoid_max_data_confidence": 40,
    "avoid_max_eagle_score": 35,
    "wait_max_data_confidence": 70,
    "min_liquidity_avg_trade_value": 300_000,
}



def make_final_decision(eagle_score, conflict_result, data_confidence_pct, market_regime_info,
                         avg_trade_value, rr_ratio):
    """
    منطق القرار النهائي (قسم 51 من الخطة): BUY CANDIDATE / WAIT / AVOID / NO TRADE.
    هنا القاعدة الأهم في كل الوثيقة: تضارب إشارات أو بيانات ضعيفة = WAIT
    أو AVOID، مش إجبار النظام على قرار BUY.
    """
    th = DECISION_THRESHOLDS
    if eagle_score is None or data_confidence_pct is None:
        return "⚪ NO TRADE (بيانات غير كافية لاتخاذ قرار)"

    high_vol_blackout = bool(market_regime_info and "High Volatility" in market_regime_info["regime"])
    weak_liquidity = avg_trade_value is not None and avg_trade_value < th["min_liquidity_avg_trade_value"]

    if conflict_result["has_blocking_conflict"] or data_confidence_pct < th["avoid_max_data_confidence"]:
        return "🔴 AVOID (تضارب إشارات خطير أو بيانات غير موثوقة)"

    if (eagle_score >= th["buy_min_eagle_score"] and data_confidence_pct >= th["buy_min_data_confidence"]
            and conflict_result["conflict_count"] == 0 and not high_vol_blackout and not weak_liquidity
            and (rr_ratio is None or rr_ratio >= th["buy_min_rr_ratio"])):
        return "🟢 BUY CANDIDATE"

    if eagle_score < th["avoid_max_eagle_score"]:
        return "🔴 AVOID (قوة إجمالية ضعيفة)"

    if (conflict_result["conflict_count"] > 0 or high_vol_blackout or weak_liquidity
            or data_confidence_pct < th["wait_max_data_confidence"]):
        return "🟡 WAIT"

    return "🟡 WAIT"


