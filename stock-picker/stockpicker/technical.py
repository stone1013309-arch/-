"""技術分析：指標計算與評分（0~100）。

輸入為含 Open/High/Low/Close/Volume 欄位、依日期排序的 DataFrame。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    # 完全沒有下跌時 RSI = 100
    return out.where(loss != 0, 100.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return line, sig, line - sig


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    c = out["Close"]
    out["MA5"] = sma(c, 5)
    out["MA20"] = sma(c, 20)
    out["MA60"] = sma(c, 60)
    out["RSI14"] = rsi(c, 14)
    out["MACD"], out["MACD_signal"], out["MACD_hist"] = macd(c)
    out["VOL_MA20"] = sma(out["Volume"], 20)
    std20 = c.rolling(20).std()
    out["BB_upper"] = out["MA20"] + 2 * std20
    out["BB_lower"] = out["MA20"] - 2 * std20
    return out


@dataclass
class TechnicalResult:
    score: float
    reasons: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def score_technical(df: pd.DataFrame) -> TechnicalResult:
    """四個子項各 25 分：趨勢、動能(RSI)、MACD、量能。"""
    if df is None or len(df) < 60:
        return TechnicalResult(50.0, ["歷史資料不足 60 日，技術面以中性計"], {})

    d = add_indicators(df)
    last, prev = d.iloc[-1], d.iloc[-2]
    reasons: list[str] = []

    # 1) 趨勢：價格與均線排列
    trend = 0.0
    if last.Close > last.MA20:
        trend += 8
    if last.MA20 > last.MA60:
        trend += 8
        reasons.append("MA20 在 MA60 之上，中期趨勢偏多")
    elif last.MA20 < last.MA60:
        reasons.append("MA20 在 MA60 之下，中期趨勢偏空")
    ma20_slope = (last.MA20 / d["MA20"].iloc[-6] - 1) if d["MA20"].iloc[-6] else 0
    if ma20_slope > 0:
        trend += 9 * min(ma20_slope / 0.02, 1.0)
    if last.Close > last.MA5 > last.MA20 > last.MA60:
        reasons.append("短中長期均線多頭排列")

    # 2) RSI：40~65 健康上漲區最佳，過熱扣分，超賣給予部分反彈分
    r = float(last.RSI14)
    if 45 <= r <= 65:
        mom = 25
    elif 65 < r <= 75:
        mom = 25 - (r - 65) * 1.5
    elif r > 75:
        mom = 8
        reasons.append(f"RSI {r:.0f} 過熱，留意追高風險")
    elif 30 <= r < 45:
        mom = 12 + (r - 30) * (13 / 15)
    else:
        mom = 12
        reasons.append(f"RSI {r:.0f} 超賣，可能有反彈但趨勢偏弱")

    # 3) MACD：柱狀體翻正 / 擴大
    m = 0.0
    if last.MACD_hist > 0:
        m += 12
        if last.MACD_hist > prev.MACD_hist:
            m += 6
    elif last.MACD_hist > prev.MACD_hist:
        m += 6  # 負值收斂
    recent = d["MACD_hist"].iloc[-5:]
    if (recent.iloc[0] <= 0) and (recent.iloc[-1] > 0):
        m += 7
        reasons.append("近 5 日 MACD 黃金交叉")
    elif (recent.iloc[0] >= 0) and (recent.iloc[-1] < 0):
        reasons.append("近 5 日 MACD 死亡交叉")
    m = min(m, 25)

    # 4) 量能：前一日放量上漲加分，放量下跌扣分
    vol_ratio = float(last.Volume / last.VOL_MA20) if last.VOL_MA20 else 1.0
    day_ret = float(last.Close / prev.Close - 1)
    if day_ret > 0 and vol_ratio >= 1.5:
        v = 25
        reasons.append(f"前一日帶量上漲（量為 20 日均量 {vol_ratio:.1f} 倍）")
    elif day_ret > 0:
        v = 17
    elif day_ret < 0 and vol_ratio >= 1.5:
        v = 3
        reasons.append(f"前一日爆量下跌（{vol_ratio:.1f} 倍均量）")
    else:
        v = 11

    score = float(np.clip(trend + mom + m + v, 0, 100))
    metrics = {
        "close": float(last.Close),
        "change_pct": day_ret * 100,
        "rsi": r,
        "ma20": float(last.MA20),
        "ma60": float(last.MA60),
        "macd_hist": float(last.MACD_hist),
        "volume_ratio": vol_ratio,
    }
    return TechnicalResult(round(score, 1), reasons, metrics)
