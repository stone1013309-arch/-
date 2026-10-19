"""綜合判斷：把均線、成交量、KD、RSI、MACD 各自評分，加總後判斷多空情勢。

每個指標給 -2 ~ +2 分（正數偏多、負數偏空），並附上判斷理由。
需要先用 indicators.add_all() 算好欄位，且資料至少約 60 個交易日。
"""
from dataclasses import dataclass

import pandas as pd


@dataclass
class Signal:
    name: str
    score: int
    reason: str


def _crossed(fast: pd.Series, slow: pd.Series, days: int) -> int:
    """最近 days 天內 fast 是否穿越 slow：+1 向上（黃金交叉）、-1 向下（死亡交叉）、0 沒有。"""
    diff = (fast - slow).dropna().iloc[-(days + 1):]
    for prev, cur in zip(diff.iloc[::-1].iloc[1:], diff.iloc[::-1]):
        if prev <= 0 < cur:
            return 1
        if prev >= 0 > cur:
            return -1
    return 0


def ma_signal(df: pd.DataFrame) -> Signal:
    last = df.iloc[-1]
    c, ma5, ma20, ma60 = last["Close"], last["MA5"], last["MA20"], last["MA60"]
    if c > ma5 > ma20 > ma60:
        score, reason = 2, "多頭排列（股價 > MA5 > MA20 > MA60），趨勢向上"
    elif c < ma5 < ma20 < ma60:
        score, reason = -2, "空頭排列（股價 < MA5 < MA20 < MA60），趨勢向下"
    elif c > ma20 and c > ma60:
        score, reason = 1, "股價站上月線與季線"
    elif c < ma20 and c < ma60:
        score, reason = -1, "股價跌破月線與季線"
    else:
        score, reason = 0, "股價在月線、季線之間，方向未明"
    cross = _crossed(df["MA5"], df["MA20"], 5)
    if cross == 1:
        reason += "；近 5 日 MA5 黃金交叉 MA20"
        score = min(score + 1, 2)
    elif cross == -1:
        reason += "；近 5 日 MA5 死亡交叉 MA20"
        score = max(score - 1, -2)
    return Signal("均線趨勢", score, reason)


def volume_signal(df: pd.DataFrame) -> Signal:
    last = df.iloc[-1]
    avg = df["Volume"].iloc[-21:-1].mean()
    ratio = last["Volume"] / avg if avg else 1
    up = last["Close"] >= df["Close"].iloc[-2]
    if ratio >= 1.5:
        if up:
            return Signal("成交量", 2, f"價漲量增（量為 20 日均量的 {ratio:.1f} 倍），買盤積極")
        return Signal("成交量", -2, f"價跌量增（量為 20 日均量的 {ratio:.1f} 倍），賣壓沉重")
    if ratio <= 0.6:
        if up:
            return Signal("成交量", 0, f"價漲量縮（量僅 20 日均量的 {ratio:.1f} 倍），追價力道不足")
        return Signal("成交量", 0, f"價跌量縮（量僅 20 日均量的 {ratio:.1f} 倍），賣壓減輕")
    return Signal("成交量", 1 if up else -1, f"量能正常（20 日均量的 {ratio:.1f} 倍），今日{'收漲' if up else '收跌'}")


def kd_signal(df: pd.DataFrame) -> Signal:
    k, d = df["K"].iloc[-1], df["D"].iloc[-1]
    cross = _crossed(df["K"], df["D"], 3)
    if cross == 1 and k < 30:
        return Signal("KD", 2, f"低檔黃金交叉（K={k:.0f}、D={d:.0f}），反彈訊號")
    if cross == -1 and k > 70:
        return Signal("KD", -2, f"高檔死亡交叉（K={k:.0f}、D={d:.0f}），回檔訊號")
    if cross == 1:
        return Signal("KD", 1, f"黃金交叉（K={k:.0f}、D={d:.0f}）")
    if cross == -1:
        return Signal("KD", -1, f"死亡交叉（K={k:.0f}、D={d:.0f}）")
    if k > 80:
        return Signal("KD", 0, f"高檔超買區（K={k:.0f}），強勢但留意過熱")
    if k < 20:
        return Signal("KD", 0, f"低檔超賣區（K={k:.0f}），弱勢但可能醞釀反彈")
    if k > d:
        return Signal("KD", 1, f"K 在 D 之上（K={k:.0f}、D={d:.0f}），短線偏多")
    return Signal("KD", -1, f"K 在 D 之下（K={k:.0f}、D={d:.0f}），短線偏空")


def rsi_signal(df: pd.DataFrame) -> Signal:
    r = df["RSI"].iloc[-1]
    if r >= 80:
        return Signal("RSI", -1, f"RSI={r:.0f}，嚴重超買，追高風險大")
    if r >= 70:
        return Signal("RSI", 0, f"RSI={r:.0f}，進入超買區，強勢但過熱")
    if r >= 50:
        return Signal("RSI", 1, f"RSI={r:.0f}，多方佔優勢")
    if r >= 30:
        return Signal("RSI", -1, f"RSI={r:.0f}，空方佔優勢")
    if r >= 20:
        return Signal("RSI", 0, f"RSI={r:.0f}，進入超賣區，弱勢但跌深")
    return Signal("RSI", 1, f"RSI={r:.0f}，嚴重超賣，有反彈機會")


def macd_signal(df: pd.DataFrame) -> Signal:
    dif, osc = df["DIF"].iloc[-1], df["OSC"].iloc[-1]
    osc_up = osc > df["OSC"].iloc[-2]
    cross = _crossed(df["DIF"], df["MACD"], 3)
    if cross == 1:
        return Signal("MACD", 2 if dif < 0 else 1, "DIF 黃金交叉 MACD" + ("（零軸下，底部翻多）" if dif < 0 else ""))
    if cross == -1:
        return Signal("MACD", -2 if dif > 0 else -1, "DIF 死亡交叉 MACD" + ("（零軸上，高檔轉弱）" if dif > 0 else ""))
    if dif > 0 and osc > 0:
        return Signal("MACD", 2 if osc_up else 1, "零軸上紅柱" + ("放大，多頭動能增強" if osc_up else "縮小，多頭動能減弱"))
    if dif < 0 and osc < 0:
        return Signal("MACD", -2 if not osc_up else -1, "零軸下綠柱" + ("縮小，空頭動能減弱" if osc_up else "放大，空頭動能增強"))
    if osc > 0:
        return Signal("MACD", 1, "紅柱，動能轉強但 DIF 仍在零軸下")
    return Signal("MACD", -1, "綠柱，動能轉弱但 DIF 仍在零軸上")


VERDICTS = [  # (最低分, 結論, 建議方向)
    (5, "強烈偏多", "趨勢與動能一致向上，可順勢偏多操作，留意高檔過熱"),
    (2, "偏多", "多方略佔優勢，可等拉回不破支撐再考慮"),
    (-1, "盤整中性", "多空訊號分歧，觀望為宜，等方向明確"),
    (-4, "偏空", "空方略佔優勢，不宜貿然進場，持有者留意支撐"),
    (-99, "強烈偏空", "趨勢與動能一致向下，避免接刀，等止跌訊號"),
]


def analyze(df: pd.DataFrame) -> dict:
    """回傳 {'score', 'max', 'verdict', 'advice', 'signals', 'support', 'resistance'}；資料不足時 verdict 為 '資料不足'。"""
    if len(df) < 65 or df[["MA60", "K", "RSI", "DIF"]].iloc[-1].isna().any():
        return {"score": 0, "max": 0, "verdict": "資料不足", "advice": "上市未滿約 3 個月，無法完整判斷", "signals": [],
                "support": None, "resistance": None}
    signals = [ma_signal(df), volume_signal(df), kd_signal(df), rsi_signal(df), macd_signal(df)]
    score = sum(s.score for s in signals)
    verdict, advice = next((v, a) for lo, v, a in VERDICTS if score >= lo)
    recent = df.iloc[-20:]
    return {
        "score": score,
        "max": 2 * len(signals),
        "verdict": verdict,
        "advice": advice,
        "signals": signals,
        "support": recent["Low"].min(),
        "resistance": recent["High"].max(),
    }
