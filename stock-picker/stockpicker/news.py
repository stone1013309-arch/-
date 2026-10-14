"""新聞面：篩選前一交易日以來的新聞並評估情緒（0~100）。

預設使用中英文關鍵字詞庫判斷；若設定 ANTHROPIC_API_KEY 且 use_llm=True，
改用 Claude 逐則判讀，失敗時自動退回關鍵字法。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .config import TIMEZONE


@dataclass
class NewsItem:
    title: str
    published: datetime  # 需含時區
    source: str = ""
    link: str = ""
    sentiment: float = 0.0  # -1 ~ 1


@dataclass
class NewsResult:
    score: float
    reasons: list[str] = field(default_factory=list)
    items: list[NewsItem] = field(default_factory=list)


POSITIVE = {
    # 中文
    "創新高": 2, "新高": 1.5, "大漲": 1.5, "漲停": 2, "上漲": 1, "看好": 1.5, "樂觀": 1,
    "成長": 1, "年增": 1, "優於預期": 2, "超乎預期": 2, "上修": 1.5, "調升": 1.5,
    "買進": 1.5, "加碼": 1.5, "獲利": 1, "營收創": 1.5, "接單": 1, "訂單": 1, "擴產": 1,
    "合作": 0.5, "受惠": 1.5, "利多": 2, "強勁": 1.5, "回購": 1, "配息": 0.5, "突破": 1,
    "轉盈": 2, "外資買超": 1.5, "投信買超": 1.5, "目標價上調": 2,
    # English
    "beat": 1.5, "beats": 1.5, "surge": 1.5, "soar": 1.5, "rally": 1, "record": 1,
    "upgrade": 1.5, "upgraded": 1.5, "raises": 1, "raised guidance": 2, "growth": 1,
    "strong": 1, "bullish": 1.5, "outperform": 1.5, "buy rating": 1.5, "buyback": 1,
    "profit jumps": 2, "partnership": 0.5, "all-time high": 2,
}

NEGATIVE = {
    "大跌": 1.5, "重挫": 2, "跌停": 2, "下跌": 1, "看壞": 1.5, "悲觀": 1, "衰退": 1.5,
    "年減": 1, "低於預期": 2, "不如預期": 2, "下修": 1.5, "調降": 1.5, "賣出": 1.5,
    "減碼": 1.5, "虧損": 1.5, "利空": 2, "疲弱": 1.5, "裁員": 1, "罰款": 1.5, "訴訟": 1,
    "調查": 1, "停工": 1.5, "斷鏈": 1.5, "砍單": 2, "外資賣超": 1.5, "投信賣超": 1.5,
    "目標價下調": 2, "警示": 1, "違約": 2, "制裁": 1.5,
    "miss": 1.5, "misses": 1.5, "plunge": 2, "slump": 1.5, "tumble": 1.5, "downgrade": 1.5,
    "downgraded": 1.5, "cuts guidance": 2, "lawsuit": 1, "probe": 1, "investigation": 1,
    "recall": 1, "layoffs": 1, "bearish": 1.5, "underperform": 1.5, "loss": 1, "fraud": 2,
    "sanction": 1.5, "warning": 1,
}


def keyword_sentiment(text: str) -> float:
    """回傳 -1~1。"""
    t = text.lower()
    pos = sum(w for k, w in POSITIVE.items() if k.lower() in t)
    neg = sum(w for k, w in NEGATIVE.items() if k.lower() in t)
    if pos == neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


def previous_session_start(now: datetime) -> datetime:
    """前一個工作日 00:00（週一會回推到週五）。不考慮國定假日。"""
    d = now.date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return datetime.combine(d, time.min, tzinfo=now.tzinfo)


def filter_previous_day(items: list[NewsItem], now: datetime | None = None) -> list[NewsItem]:
    now = now or datetime.now(ZoneInfo(TIMEZONE))
    start = previous_session_start(now)
    seen: set[str] = set()
    out = []
    for it in sorted(items, key=lambda x: x.published, reverse=True):
        key = it.title.strip().lower()
        if start <= it.published <= now and key not in seen:
            seen.add(key)
            out.append(it)
    return out


def llm_sentiment(titles: list[str], company: str) -> list[float] | None:
    """用 Claude 判讀每則標題對該公司股價的影響。沒有金鑰或失敗時回傳 None。"""
    if not titles or not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        from pydantic import BaseModel

        class Judgement(BaseModel):
            index: int
            sentiment: float  # -1 ~ 1

        class Judgements(BaseModel):
            items: list[Judgement]

        numbered = "\n".join(f"{i}. {t}" for i, t in enumerate(titles))
        client = anthropic.Anthropic()
        resp = client.messages.parse(
            model=os.environ.get("STOCKPICKER_CLAUDE_MODEL", "claude-opus-5-5"),
            max_tokens=4000,
            output_config={"effort": "low"},
            messages=[{
                "role": "user",
                "content": (
                    f"以下是關於「{company}」的新聞標題。請判斷每則對該公司短期股價的影響，"
                    "給出 -1（非常負面）到 1（非常正面）的分數，與該公司無關或中性給 0。\n\n"
                    + numbered
                ),
            }],
            output_format=Judgements,
        )
        if resp.stop_reason == "refusal" or resp.parsed_output is None:
            return None
        scores = [0.0] * len(titles)
        for j in resp.parsed_output.items:
            if 0 <= j.index < len(titles):
                scores[j.index] = max(-1.0, min(1.0, j.sentiment))
        return scores
    except Exception:  # 網路、金鑰、套件缺漏都退回關鍵字法
        return None


def score_news(items: list[NewsItem], company: str = "", use_llm: bool = False,
               now: datetime | None = None) -> NewsResult:
    recent = filter_previous_day(items, now)
    if not recent:
        return NewsResult(50.0, ["前一交易日無相關新聞，新聞面以中性計"], [])

    scores = llm_sentiment([n.title for n in recent], company) if use_llm else None
    method = "Claude" if scores else "關鍵字"
    if scores is None:
        scores = [keyword_sentiment(n.title) for n in recent]
    for n, s in zip(recent, scores):
        n.sentiment = s

    avg = sum(scores) / len(scores)
    # 新聞數越多信心越高（3 則以上視為充分）
    confidence = min(len(recent) / 3, 1.0)
    score = 50 + avg * 50 * confidence

    pos = sum(1 for s in scores if s > 0.2)
    neg = sum(1 for s in scores if s < -0.2)
    reasons = [f"前一交易日起共 {len(recent)} 則新聞（{method}判讀）：正面 {pos}、負面 {neg}"]
    best = max(recent, key=lambda n: n.sentiment)
    worst = min(recent, key=lambda n: n.sentiment)
    if best.sentiment > 0.2:
        reasons.append(f"利多：{best.title}")
    if worst.sentiment < -0.2:
        reasons.append(f"利空：{worst.title}")
    return NewsResult(round(score, 1), reasons, recent)
