"""
طبقة مزوّدي البيانات (Data Providers) لـ EGX Stock Screener
=============================================================
الهدف: فصل مصدر البيانات عن منطق التحليل، عشان تقدر تبدّل المصدر
بسهولة من غير ما تلمس كود التحليل الفني/الأساسي.
"""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod

import pandas as pd
import requests


# ---------------------------------------------------------------------------
# الواجهة الأساسية (Abstract Base Class) - أي مزود جديد لازم يلتزم بيها
# ---------------------------------------------------------------------------
class DataProvider(ABC):
    name: str = "base"

    @abstractmethod
    def get_price_history(self, ticker: str, period_days: int = 365) -> pd.DataFrame:
        """
        يرجع DataFrame بأعمدة: Date (index), Open, High, Low, Close, Volume
        يجب أن يكون الـ index مرتب تصاعدياً بالتاريخ.
        """
        raise NotImplementedError

    @abstractmethod
    def get_fundamentals(self, ticker: str) -> dict:
        """
        يرجع dict بالمفاتيح:
        pe_ratio, pb_ratio, dividend_yield_%, profit_margin_%, roe_%,
        debt_to_equity, market_cap, revenue_growth_%
        أي قيمة غير متاحة توضع كـ None بدل ما تتسبب في خطأ.
        """
        raise NotImplementedError

    def get_live_price(self, ticker: str) -> dict:
        """
        اختياري (مش إجباري على كل مزود). يرجع dict فيه:
        {"price": float | None, "is_live": bool, "quote_time": str | None}

        الهدف: سعر أقرب للحظي (delayed quote) منفصل عن سلسلة الأسعار اليومية
        التاريخية المستخدمة في حساب المؤشرات الفنية. لو المزود مش بيدعمها،
        الافتراضي بيرجع is_live=False عشان الكود اللي بيستخدمها يعرف يرجع
        لآخر إغلاق يومي بدل ما يفشل.
        """
        return {"price": None, "is_live": False, "quote_time": None}

FUNDAMENTAL_KEYS = [
    "pe_ratio", "pb_ratio", "dividend_yield_%", "profit_margin_%",
    "roe_%", "debt_to_equity", "market_cap", "revenue_growth_%",
    "eps", "book_value_per_share",
]


def _empty_fundamentals() -> dict:
    return {k: None for k in FUNDAMENTAL_KEYS}


# ---------------------------------------------------------------------------
# 1) Yahoo Finance Provider (الافتراضي، مجاني)
# ---------------------------------------------------------------------------
class YahooProvider(DataProvider):
    name = "yahoo"

    def __init__(self):
        try:
            import yfinance as yf
        except ImportError:
            raise SystemExit(
                "المكتبة yfinance غير مثبتة:\n"
                "pip install yfinance --break-system-packages"
            )
        self._yf = yf

    def get_price_history(self, ticker: str, period_days: int = 365) -> pd.DataFrame:
        period = "2y" if period_days > 365 else "1y"
        df = self._yf.download(ticker, period=period, interval="1d",
                                progress=False, auto_adjust=True)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.rename(columns=str.title)
        return df[["Open", "High", "Low", "Close", "Volume"]]

    def get_live_price(self, ticker: str) -> dict:
        """
        بيحاول يجيب سعر أقرب للحظي عبر fast_info (أسرع وأخف من .info الكامل).
        مهم: ده "delayed quote" حسب سياسة Yahoo نفسها (عادة 15-20 دقيقة تأخير
        للبورصات الكبرى، وممكن يكون أكتر أو غير مدعوم أصلاً لبورصات زي EGX) -
        مش سعر لحظي مضمون 100%. لو مش متاح، بيرجع is_live=False وتفضل الأداة
        تستخدم آخر إغلاق يومي بدل ما تفشل.
        """
        try:
            fast = self._yf.Ticker(ticker).fast_info
            price = fast.get("last_price") if hasattr(fast, "get") else getattr(fast, "last_price", None)
            if price is not None and price > 0:
                return {"price": float(price), "is_live": True, "quote_time": None}
        except Exception as e:
            print(f"⚠️  Yahoo: فشل جلب السعر شبه اللحظي لـ {ticker}: {type(e).__name__}: {e}")
        return {"price": None, "is_live": False, "quote_time": None}

    def get_fundamentals(self, ticker: str) -> dict:
        out = _empty_fundamentals()
        try:
            info = self._yf.Ticker(ticker).info
        except Exception as e:
            print(f"⚠️  Yahoo: فشل استدعاء .info لـ {ticker}: {type(e).__name__}: {e}")
            return out

        # لو info رجعت فاضية أو شبه فاضية (مفتاح أو اتنين بس زي 'trailingPegRatio')
        # ده مؤشر قوي إن Yahoo رفض/حظر الطلب (شائع من عناوين IP سحابية)، مش إن
        # الشركة نفسها مالهاش بيانات
        if not info or len(info) < 5:
            print(f"⚠️  Yahoo: استجابة فارغة/مقتضبة لـ {ticker} - على الأغلب رفض مؤقت من المصدر (rate limit).")
            return out

        def pct(x):
            return round(x * 100, 2) if isinstance(x, (int, float)) else None

        out["pe_ratio"] = info.get("trailingPE")
        out["pb_ratio"] = info.get("priceToBook")
        out["eps"] = info.get("trailingEps")
        out["book_value_per_share"] = info.get("bookValue")
        out["dividend_yield_%"] = pct(info.get("dividendYield"))
        out["profit_margin_%"] = pct(info.get("profitMargins"))
        out["roe_%"] = pct(info.get("returnOnEquity"))
        out["debt_to_equity"] = info.get("debtToEquity")
        out["market_cap"] = info.get("marketCap")
        out["revenue_growth_%"] = pct(info.get("revenueGrowth"))
        return out


# ---------------------------------------------------------------------------
# 2) EODHD Provider (مدفوع)
# ---------------------------------------------------------------------------
class EODHDProvider(DataProvider):
    name = "eodhd"
    BASE_URL = "https://eodhd.com/api"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("EODHD_API_KEY")
        if not self.api_key:
            raise ValueError(
                "لازم API key من eodhd.com. مرره مباشرة أو حطه في ومتغير البيئة EODHD_API_KEY"
            )

    def get_price_history(self, ticker: str, period_days: int = 365) -> pd.DataFrame:
        symbol = ticker.replace(".CA", ".EGX")
        url = f"{self.BASE_URL}/eod/{symbol}"
        params = {"api_token": self.api_key, "fmt": "json", "period": "d"}
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"⚠️  EODHD: فشل تحميل بيانات {ticker}: {e}")
            return pd.DataFrame()

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        df = df.rename(columns={
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume",
        })
        return df[["Open", "High", "Low", "Close", "Volume"]].tail(period_days)

    def get_fundamentals(self, ticker: str) -> dict:
        out = _empty_fundamentals()
        symbol = ticker.replace(".CA", ".EGX")
        url = f"{self.BASE_URL}/fundamentals/{symbol}"
        params = {"api_token": self.api_key, "fmt": "json"}
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"⚠️  EODHD: فشل تحميل البيانات المالية لـ {ticker}: {e}")
            return out

        highlights = data.get("Highlights", {}) or {}
        valuation = data.get("Valuation", {}) or {}

        out["pe_ratio"] = highlights.get("PERatio")
        out["pb_ratio"] = valuation.get("PriceBookMRQ")
        out["eps"] = highlights.get("EPS")
        out["book_value_per_share"] = highlights.get("BookValue")
        dy = highlights.get("DividendYield")
        out["dividend_yield_%"] = round(dy * 100, 2) if isinstance(dy, (int, float)) else None
        pm = highlights.get("ProfitMargin")
        out["profit_margin_%"] = round(pm * 100, 2) if isinstance(pm, (int, float)) else None
        roe = highlights.get("ReturnOnEquityTTM")
        out["roe_%"] = round(roe * 100, 2) if isinstance(roe, (int, float)) else None
        out["market_cap"] = highlights.get("MarketCapitalization")
        rg = highlights.get("QuarterlyRevenueGrowthYOY")
        out["revenue_growth_%"] = round(rg * 100, 2) if isinstance(rg, (int, float)) else None
        return out


# ---------------------------------------------------------------------------
# 3) Local CSV Provider
# ---------------------------------------------------------------------------
class CSVProvider(DataProvider):
    name = "csv"

    def __init__(self, data_dir: str = "./egx_data"):
        self.data_dir = data_dir
        self.prices_dir = os.path.join(data_dir, "prices")
        self.fundamentals_path = os.path.join(data_dir, "fundamentals.csv")
        self._fund_cache = None

    def get_price_history(self, ticker: str, period_days: int = 365) -> pd.DataFrame:
        path = os.path.join(self.prices_dir, f"{ticker}.csv")
        if not os.path.exists(path):
            print(f"⚠️  ملف الأسعار غير موجود: {path}")
            return pd.DataFrame()
        df = pd.read_csv(path, parse_dates=["Date"])
        df = df.set_index("Date").sort_index()
        return df.tail(period_days)

    def _load_fundamentals_table(self) -> pd.DataFrame:
        if self._fund_cache is None:
            if os.path.exists(self.fundamentals_path):
                self._fund_cache = pd.read_csv(self.fundamentals_path).set_index("ticker")
            else:
                self._fund_cache = pd.DataFrame()
        return self._fund_cache

    def get_fundamentals(self, ticker: str) -> dict:
        table = self._load_fundamentals_table()
        out = _empty_fundamentals()
        if ticker in table.index:
            row = table.loc[ticker]
            for k in FUNDAMENTAL_KEYS:
                if k in row:
                    out[k] = row[k] if pd.notna(row[k]) else None
        return out


def get_provider(name: str = "yahoo", **kwargs) -> DataProvider:
    name = name.lower()
    if name == "yahoo":
        return YahooProvider()
    if name == "eodhd":
        return EODHDProvider(**kwargs)
    if name == "csv":
        return CSVProvider(**kwargs)
    raise ValueError(f"مزود بيانات غير معروف: {name}.")
