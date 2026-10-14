"""資料來源。

- YahooProvider：yfinance 取得股價、財報指標、新聞，另加 Google News RSS（中文新聞）。
- DemoProvider：離線產生的模擬資料，用於展示與測試，**不代表真實行情**。
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .config import TIMEZONE
from .news import NewsItem

TZ = ZoneInfo(TIMEZONE)


class YahooProvider:
    name = "Yahoo Finance + Google News"

    def __init__(self):
        import yfinance as yf  # 延遲載入，示範模式不需要

        self._yf = yf

    def history(self, ticker: str) -> pd.DataFrame:
        df = self._yf.Ticker(ticker).history(period="1y", auto_adjust=True)
        return df[["Open", "High", "Low", "Close", "Volume"]].dropna()

    def info(self, ticker: str) -> dict:
        try:
            return self._yf.Ticker(ticker).info or {}
        except Exception:
            return {}

    def news(self, ticker: str, name: str) -> list[NewsItem]:
        items = self._yahoo_news(ticker)
        items += google_news(name or ticker, zh=ticker.endswith((".TW", ".TWO")))
        return items

    def _yahoo_news(self, ticker: str) -> list[NewsItem]:
        try:
            raw = self._yf.Ticker(ticker).news or []
        except Exception:
            return []
        out = []
        for r in raw:
            c = r.get("content", r)  # 新版 yfinance 包在 content 內
            title = c.get("title")
            if not title:
                continue
            if c.get("pubDate"):
                pub = datetime.fromisoformat(c["pubDate"].replace("Z", "+00:00"))
            elif r.get("providerPublishTime"):
                pub = datetime.fromtimestamp(r["providerPublishTime"], tz=timezone.utc)
            else:
                continue
            provider = c.get("provider") or {}
            source = provider.get("displayName", "") if isinstance(provider, dict) else str(provider)
            link = (c.get("canonicalUrl") or {}).get("url", "") if isinstance(c.get("canonicalUrl"), dict) else r.get("link", "")
            out.append(NewsItem(title, pub.astimezone(TZ), source or r.get("publisher", ""), link))
        return out


def google_news(query: str, zh: bool = True, timeout: float = 10) -> list[NewsItem]:
    import requests

    if zh:
        params = "hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    else:
        params = "hl=en-US&gl=US&ceid=US:en"
    url = f"https://news.google.com/rss/search?q={quote_plus(query + ' when:3d')}&{params}"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return parse_rss(resp.text)
    except Exception:
        return []


def parse_rss(xml_text: str) -> list[NewsItem]:
    out = []
    root = ET.fromstring(xml_text)
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        pub = item.findtext("pubDate")
        if not title or not pub:
            continue
        try:
            dt = parsedate_to_datetime(pub).astimezone(TZ)
        except (TypeError, ValueError):
            continue
        source = item.findtext("source") or ""
        out.append(NewsItem(title, dt, source, item.findtext("link") or ""))
    return out


# ---------------------------------------------------------------- 示範資料

_DEMO_HEADLINES_POS = [
    "{n} 營收創同期新高，法人看好後市",
    "{n} 獲外資調升目標價，評等買進",
    "{n} 接獲大單，擴產計畫加速",
    "{n} 第三季獲利優於預期",
]
_DEMO_HEADLINES_NEG = [
    "{n} 傳遭客戶砍單，股價重挫",
    "{n} 營收年減，表現不如預期",
    "{n} 遭外資調降評等至減碼",
]
_DEMO_HEADLINES_NEU = [
    "{n} 將於下週召開法說會",
    "{n} 董事會通過年度預算",
]


def _seed(ticker: str) -> int:
    return int(hashlib.md5(ticker.encode()).hexdigest()[:8], 16)


class DemoProvider:
    """依代號產生可重現的模擬資料。"""

    name = "示範資料（模擬，非真實行情）"

    def __init__(self, now: datetime | None = None):
        self.now = now or datetime.now(TZ)

    def history(self, ticker: str) -> pd.DataFrame:
        rng = np.random.default_rng(_seed(ticker))
        n = 250
        drift = rng.normal(0.0004, 0.0012)
        rets = rng.normal(drift, 0.018, n)
        close = 100 * np.exp(np.cumsum(rets))
        high = close * (1 + rng.uniform(0, 0.02, n))
        low = close * (1 - rng.uniform(0, 0.02, n))
        open_ = low + (high - low) * rng.uniform(0, 1, n)
        vol = rng.lognormal(15, 0.35, n)
        vol[-1] *= rng.uniform(0.6, 2.2)
        idx = pd.bdate_range(end=self.now.date() - timedelta(days=1), periods=n)
        return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol}, index=idx)

    def info(self, ticker: str) -> dict:
        rng = np.random.default_rng(_seed(ticker) + 1)
        return {
            "returnOnEquity": rng.uniform(-0.02, 0.32),
            "profitMargins": rng.uniform(-0.03, 0.35),
            "revenueGrowth": rng.uniform(-0.15, 0.40),
            "earningsGrowth": rng.uniform(-0.30, 0.50),
            "trailingPE": rng.uniform(7, 55),
            "priceToBook": rng.uniform(0.8, 9),
            "debtToEquity": rng.uniform(10, 220),
            "currentRatio": rng.uniform(0.7, 3),
            "dividendYield": rng.uniform(0, 6),
        }

    def news(self, ticker: str, name: str) -> list[NewsItem]:
        rng = np.random.default_rng(_seed(ticker) + 2)
        bias = rng.uniform(-1, 1)
        out = []
        for _ in range(int(rng.integers(0, 6))):
            r = rng.uniform(-1, 1) + bias * 0.6
            pool = _DEMO_HEADLINES_POS if r > 0.35 else _DEMO_HEADLINES_NEG if r < -0.35 else _DEMO_HEADLINES_NEU
            title = pool[int(rng.integers(len(pool)))].format(n=name or ticker)
            when = self.now - timedelta(hours=float(rng.uniform(1, 30)))
            out.append(NewsItem(title, when, "示範新聞"))
        return out
