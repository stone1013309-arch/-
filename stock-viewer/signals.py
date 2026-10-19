"""綜合判斷：每項指標給 -2 ~ +2 分（正數偏多、負數偏空），依權重加總後判斷多空情勢。

技術面：均線、成交量、KD、RSI、MACD、週線
籌碼面：三大法人、融資融券（僅台股）
基本面：本益比、殖利率、營收成長、EPS
另外用大盤情勢打折，並要求週線確認才給「強烈」結論。
"""
from dataclasses import dataclass

import pandas as pd

from indicators import add_all


@dataclass
class Signal:
    name: str
    score: int
    reason: str


TECH_NAMES = ["均線趨勢", "成交量", "KD", "RSI", "MACD"]
ALL_NAMES = TECH_NAMES + ["週線趨勢", "法人籌碼", "融資融券", "基本面"]

VERDICT_ADVICE = {
    "強烈偏多": "趨勢與動能一致向上，可順勢偏多操作，留意高檔過熱",
    "偏多": "多方略佔優勢，可等拉回不破支撐再考慮",
    "盤整中性": "多空訊號分歧，觀望為宜，等方向明確",
    "偏空": "空方略佔優勢，不宜貿然進場，持有者留意支撐",
    "強烈偏空": "趨勢與動能一致向下，避免接刀，等止跌訊號",
}


def _clamp(v: float) -> int:
    return int(max(-2, min(2, v)))


def crossed(fast: pd.Series, slow: pd.Series, days: int) -> int:
    """最近 days 天內 fast 是否穿越 slow：+1 向上（黃金交叉）、-1 向下（死亡交叉）、0 沒有。"""
    diff = (fast.iloc[-(days + 1):] - slow.iloc[-(days + 1):]).dropna()
    for prev, cur in zip(diff.iloc[::-1].iloc[1:], diff.iloc[::-1]):
        if prev <= 0 < cur:
            return 1
        if prev >= 0 > cur:
            return -1
    return 0


def enough_data(df: pd.DataFrame) -> bool:
    return len(df) >= 65 and not df[["MA60", "K", "RSI", "DIF"]].iloc[-1].isna().any()


# ---------- 技術面 ----------
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
    cross = crossed(df["MA5"], df["MA20"], 5)
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
    cross = crossed(df["K"], df["D"], 3)
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
    cross = crossed(df["DIF"], df["MACD"], 3)
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


def technical_signals(df: pd.DataFrame) -> list[Signal]:
    """df 需先經過 add_all()；資料不足時回傳空清單。"""
    if not enough_data(df):
        return []
    return [ma_signal(df), volume_signal(df), kd_signal(df), rsi_signal(df), macd_signal(df)]


def weekly_signal(hist: pd.DataFrame) -> Signal | None:
    """把日線轉成週線，看週均線方向與週 MACD。"""
    w = hist.resample("W-FRI").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    ).dropna()
    if len(w) < 30:
        return None
    last = add_all(w).iloc[-1]
    score, parts = 0, []
    if last["Close"] > last["MA5"] > last["MA20"]:
        score += 1
        parts.append("週均線多頭排列")
    elif last["Close"] < last["MA5"] < last["MA20"]:
        score -= 1
        parts.append("週均線空頭排列")
    else:
        parts.append("週均線糾結")
    if last["OSC"] > 0:
        score += 1
        parts.append("週 MACD 紅柱")
    else:
        score -= 1
        parts.append("週 MACD 綠柱")
    return Signal("週線趨勢", score, "、".join(parts) + ("，中期趨勢向上" if score > 0 else "，中期趨勢向下" if score < 0 else ""))


def tech_score_frame(full: pd.DataFrame) -> pd.DataFrame:
    """逐日計算五項技術指標分數（回測、歷史評分走勢用）。"""
    rows = {}
    for i in range(64, len(full)):
        sigs = technical_signals(full.iloc[: i + 1])
        if sigs:
            rows[full.index[i]] = [s.score for s in sigs]
    return pd.DataFrame.from_dict(rows, orient="index", columns=TECH_NAMES)


# ---------- 籌碼面（台股） ----------
def institutional_signal(inst: pd.DataFrame) -> Signal | None:
    if inst is None or inst.empty:
        return None
    dates = sorted(inst["date"].unique())[-5:]
    recent = inst[inst["date"].isin(dates)].copy()
    recent["net"] = (recent["buy"] - recent["sell"]) / 1000  # 股 → 張

    def group(name: str) -> str:
        if name.startswith("Foreign"):
            return "外資"
        return "投信" if name == "Investment_Trust" else "自營商"

    net = recent.groupby(recent["name"].map(group))["net"].sum()
    f, t, d = net.get("外資", 0.0), net.get("投信", 0.0), net.get("自營商", 0.0)
    total = f + t + d
    if f > 0 and t > 0:
        score, desc = 2, "外資、投信同步買超"
    elif f < 0 and t < 0:
        score, desc = -2, "外資、投信同步賣超"
    elif total > 0:
        score, desc = 1, "三大法人合計買超"
    elif total < 0:
        score, desc = -1, "三大法人合計賣超"
    else:
        score, desc = 0, "法人買賣持平"
    return Signal("法人籌碼", score, f"近 {len(dates)} 日{desc}（外資 {f:+,.0f}、投信 {t:+,.0f}、自營商 {d:+,.0f} 張）")


def margin_signal(margin: pd.DataFrame, close: pd.Series) -> Signal | None:
    if margin is None or margin.empty or len(close) < 6:
        return None
    m = margin.sort_values("date").tail(6)
    if len(m) < 2:
        return None
    now, then = m["MarginPurchaseTodayBalance"].iloc[-1], m["MarginPurchaseTodayBalance"].iloc[0]
    chg = (now - then) / then if then else 0.0
    price_chg = close.iloc[-1] / close.iloc[-6] - 1
    short = m["ShortSaleTodayBalance"].iloc[-1]
    short_ratio = short / now * 100 if now else 0.0
    if price_chg < 0 and chg > 0.02:
        score, desc = -2, "股價跌但融資增加，散戶接刀，籌碼凌亂"
    elif price_chg > 0 and chg > 0.10:
        score, desc = -1, "融資大增，散戶追高，籌碼過熱"
    elif price_chg > 0 and chg < 0:
        score, desc = 2, "股價漲但融資減少，籌碼往大戶集中"
    elif price_chg < 0 and chg < 0:
        score, desc = 0, "股價跌、融資同步減少，浮額清洗中"
    else:
        score, desc = 0, "融資變化不大"
    reason = f"{desc}（近 5 日融資 {chg:+.1%}、股價 {price_chg:+.1%}）"
    if short_ratio >= 30:
        score += 1
        reason += f"；券資比 {short_ratio:.0f}%，有軋空動能"
    return Signal("融資融券", _clamp(score), reason)


# ---------- 基本面 ----------
def fundamental_signal(f: dict | None, us: bool = False) -> Signal | None:
    if not f:
        return None
    score, parts = 0, []
    cheap, pricey = (15, 40) if us else (12, 30)
    per, eps, yld, growth = f.get("PER"), f.get("EPS"), f.get("殖利率"), f.get("營收年增")
    if eps is not None and eps <= 0:
        score -= 1
        parts.append(f"近四季 EPS {eps:.2f}，虧損")
    elif per:
        if per < cheap:
            score += 1
            parts.append(f"本益比 {per:.1f} 偏低")
        elif per > pricey:
            score -= 1
            parts.append(f"本益比 {per:.1f} 偏高")
        else:
            parts.append(f"本益比 {per:.1f} 合理")
    if yld is not None:
        if yld >= 5:
            score += 1
            parts.append(f"殖利率 {yld:.1f}% 高")
        else:
            parts.append(f"殖利率 {yld:.1f}%")
    if growth is not None:
        if growth >= 20:
            score += 1
            parts.append(f"營收年增 {growth:+.0f}%，成長強")
        elif growth <= -10:
            score -= 1
            parts.append(f"營收年增 {growth:+.0f}%，衰退")
        else:
            parts.append(f"營收年增 {growth:+.0f}%")
    if not parts:
        return None
    return Signal("基本面", _clamp(score), "、".join(parts))


# ---------- 綜合 ----------
def verdict_of(ratio: float) -> str:
    if ratio >= 0.5:
        return "強烈偏多"
    if ratio >= 0.2:
        return "偏多"
    if ratio > -0.2:
        return "盤整中性"
    if ratio > -0.5:
        return "偏空"
    return "強烈偏空"


def market_adjust(ratio, market_ratio):
    """大盤濾網：大盤偏空時個股偏多分數打五折，大盤偏多時偏空分數打五折。ratio 可為數字或 Series。"""
    if isinstance(ratio, pd.Series):
        m = market_ratio.reindex(ratio.index).ffill()
        damp = ((m <= -0.2) & (ratio > 0)) | ((m >= 0.2) & (ratio < 0))
        return ratio.where(~damp, ratio * 0.5)
    if market_ratio is None:
        return ratio
    if (market_ratio <= -0.2 and ratio > 0) or (market_ratio >= 0.2 and ratio < 0):
        return ratio * 0.5
    return ratio


def evaluate(signals: list[Signal], weights: dict | None = None, market_ratio: float | None = None) -> dict:
    """依權重加總。回傳 index（多空指數，-100 ~ +100）、verdict、advice、notes 等。"""
    weights = weights or {}
    used = [s for s in signals if weights.get(s.name, 1.0) > 0]
    max_score = sum(2 * weights.get(s.name, 1.0) for s in used)
    if not used or not any(s.name in TECH_NAMES for s in used):
        return {"index": None, "ratio": None, "verdict": "資料不足", "advice": "上市未滿約 3 個月，無法完整判斷",
                "notes": [], "signals": signals}
    raw = sum(weights.get(s.name, 1.0) * s.score for s in used) / max_score
    ratio = market_adjust(raw, market_ratio)
    notes = []
    if ratio != raw:
        notes.append(f"大盤{'偏空' if market_ratio < 0 else '偏多'}，個股{'偏多' if raw > 0 else '偏空'}分數打五折")
    verdict = verdict_of(ratio)
    weekly = next((s for s in used if s.name == "週線趨勢"), None)
    if weekly is not None:
        if verdict == "強烈偏多" and weekly.score <= 0:
            verdict = "偏多"
            notes.append("週線未同步向上，「強烈偏多」降為「偏多」")
        elif verdict == "強烈偏空" and weekly.score >= 0:
            verdict = "偏空"
            notes.append("週線未同步向下，「強烈偏空」降為「偏空」")
    return {"index": round(ratio * 100), "ratio": ratio, "verdict": verdict, "advice": VERDICT_ADVICE[verdict],
            "notes": notes, "signals": signals}


def market_ratio_of(hist: pd.DataFrame) -> float | None:
    """大盤本身的多空比例（技術面＋週線，等權重）。"""
    if hist is None or hist.empty:
        return None
    full = add_all(hist)
    sigs = technical_signals(full)
    weekly = weekly_signal(hist)
    if weekly:
        sigs.append(weekly)
    return evaluate(sigs)["ratio"]
