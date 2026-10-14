import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stockpicker.data import DemoProvider, parse_rss
from stockpicker.fundamental import score_fundamental
from stockpicker.news import NewsItem, filter_previous_day, keyword_sentiment, score_news
from stockpicker.scoring import combine, rate, scan
from stockpicker.technical import rsi, score_technical

TZ = ZoneInfo("Asia/Taipei")


def _prices(rets):
    close = 100 * np.exp(np.cumsum(rets))
    n = len(close)
    return pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99,
                         "Close": close, "Volume": np.full(n, 1e6)},
                        index=pd.bdate_range("2025-01-01", periods=n))


def test_rsi_bounds():
    s = pd.Series(np.linspace(1, 100, 50))
    assert rsi(s).iloc[-1] == 100
    r = rsi(pd.Series(np.random.default_rng(0).normal(0, 1, 200).cumsum() + 100))
    assert r.dropna().between(0, 100).all()


def test_uptrend_scores_higher_than_downtrend():
    rng = np.random.default_rng(1)
    up = score_technical(_prices(rng.normal(0.003, 0.01, 150)))
    down = score_technical(_prices(rng.normal(-0.003, 0.01, 150)))
    assert up.score > down.score
    assert 0 <= down.score <= up.score <= 100


def test_short_history_is_neutral():
    assert score_technical(_prices(np.zeros(30))).score == 50


def test_fundamental_good_vs_bad():
    good = score_fundamental({"returnOnEquity": 0.28, "profitMargins": 0.3, "revenueGrowth": 0.3,
                              "earningsGrowth": 0.4, "trailingPE": 12, "debtToEquity": 20})
    bad = score_fundamental({"returnOnEquity": -0.05, "profitMargins": -0.1, "revenueGrowth": -0.2,
                             "earningsGrowth": -0.3, "trailingPE": -5, "debtToEquity": 300})
    assert good.score > 75 and bad.score < 25
    assert score_fundamental({}).score == 50
    assert score_fundamental({"trailingPE": float("nan")}).score == 50


def test_keyword_sentiment():
    assert keyword_sentiment("台積電營收創新高 法人看好") > 0
    assert keyword_sentiment("鴻海傳遭砍單 股價重挫") < 0
    assert keyword_sentiment("董事會通過預算") == 0
    assert keyword_sentiment("Nvidia beats estimates, shares surge") > 0


def test_previous_day_window_monday_includes_friday():
    monday = datetime(2026, 10, 12, 9, 0, tzinfo=TZ)
    items = [NewsItem("fri", datetime(2026, 10, 9, 15, 0, tzinfo=TZ)),
             NewsItem("thu", datetime(2026, 10, 8, 15, 0, tzinfo=TZ)),
             NewsItem("fri", datetime(2026, 10, 9, 16, 0, tzinfo=TZ))]  # 重複標題
    assert [n.title for n in filter_previous_day(items, monday)] == ["fri"]


def test_score_news_neutral_when_empty_and_directional():
    now = datetime(2026, 10, 14, 8, 0, tzinfo=TZ)
    assert score_news([], now=now).score == 50
    pos = [NewsItem(f"公司獲利優於預期 {i}", now - timedelta(hours=i + 1)) for i in range(3)]
    neg = [NewsItem(f"公司遭砍單 股價重挫 {i}", now - timedelta(hours=i + 1)) for i in range(3)]
    assert score_news(pos, now=now).score > 80
    assert score_news(neg, now=now).score < 20


def test_parse_rss():
    xml = """<rss><channel><item><title>台積電 法說會</title><link>http://x</link>
    <pubDate>Tue, 13 Oct 2026 02:00:00 GMT</pubDate><source>經濟日報</source></item>
    <item><title>bad</title></item></channel></rss>"""
    items = parse_rss(xml)
    assert len(items) == 1 and items[0].source == "經濟日報"
    assert items[0].published.hour == 10  # 轉為台北時間


def test_combine_and_rate():
    assert combine(100, 100, 100) == 100
    assert combine(80, 0, 0, {"technical": 1, "fundamental": 0, "news": 0}) == 80
    assert rate(80) == "建議買進" and rate(60) == "觀察" and rate(30) == "暫不建議"


def test_demo_scan_end_to_end():
    now = datetime(2026, 10, 14, 8, 0, tzinfo=TZ)
    wl = {"2330.TW": "台積電", "2317.TW": "鴻海", "AAPL": "Apple"}
    reports = scan(wl, DemoProvider(now), now=now)
    assert len(reports) == 3
    assert reports == sorted(reports, key=lambda r: r.total, reverse=True)
    assert all(0 <= r.total <= 100 for r in reports)


class _Broken(DemoProvider):
    def history(self, ticker):
        raise RuntimeError("network down")


def test_failed_history_never_recommended():
    r = scan({"X": "x"}, _Broken())[0]
    assert r.error and r.rating != "建議買進"
