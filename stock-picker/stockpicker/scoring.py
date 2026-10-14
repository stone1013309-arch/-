"""整合三大面向，產生每檔股票的綜合評分與建議。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from .config import BUY_THRESHOLD, DEFAULT_WEIGHTS, WATCH_THRESHOLD
from .fundamental import FundamentalResult, score_fundamental
from .news import NewsResult, score_news
from .technical import TechnicalResult, score_technical


@dataclass
class StockReport:
    ticker: str
    name: str
    total: float
    rating: str
    technical: TechnicalResult
    fundamental: FundamentalResult
    news: NewsResult
    history: pd.DataFrame | None = field(default=None, repr=False)
    error: str = ""


def rate(total: float) -> str:
    if total >= BUY_THRESHOLD:
        return "建議買進"
    if total >= WATCH_THRESHOLD:
        return "觀察"
    return "暫不建議"


def combine(tech: float, fund: float, news: float, weights: dict | None = None) -> float:
    w = weights or DEFAULT_WEIGHTS
    s = sum(w.values()) or 1.0
    return round((tech * w["technical"] + fund * w["fundamental"] + news * w["news"]) / s, 1)


def analyze(ticker: str, name: str, provider, weights: dict | None = None,
            use_llm: bool = False, now: datetime | None = None) -> StockReport:
    try:
        hist = provider.history(ticker)
    except Exception as e:  # 單一股票失敗不影響整體掃描
        hist = None
        err = f"股價取得失敗：{e}"
    else:
        err = "" if hist is not None and len(hist) else "查無股價資料"

    tech = score_technical(hist)
    fund = score_fundamental(provider.info(ticker))
    news = score_news(provider.news(ticker, name), company=name or ticker, use_llm=use_llm, now=now)
    total = combine(tech.score, fund.score, news.score, weights)
    if err:
        total = min(total, WATCH_THRESHOLD - 0.1)  # 沒有股價就不給買進建議
    return StockReport(ticker, name, total, rate(total), tech, fund, news, hist, err)


def scan(watchlist: dict[str, str], provider, weights: dict | None = None,
         use_llm: bool = False, now: datetime | None = None, workers: int = 6) -> list[StockReport]:
    with ThreadPoolExecutor(max_workers=workers) as ex:
        reports = list(ex.map(
            lambda kv: analyze(kv[0], kv[1], provider, weights, use_llm, now), watchlist.items()))
    return sorted(reports, key=lambda r: r.total, reverse=True)


def to_frame(reports: list[StockReport]) -> pd.DataFrame:
    rows = []
    for r in reports:
        m = r.technical.metrics
        rows.append({
            "代號": r.ticker,
            "名稱": r.name,
            "綜合分數": r.total,
            "建議": r.rating,
            "技術面": r.technical.score,
            "基本面": r.fundamental.score,
            "新聞面": r.news.score,
            "收盤價": round(m["close"], 2) if "close" in m else None,
            "漲跌%": round(m["change_pct"], 2) if "change_pct" in m else None,
            "RSI": round(m["rsi"], 1) if "rsi" in m else None,
            "新聞數": len(r.news.items),
        })
    return pd.DataFrame(rows)
