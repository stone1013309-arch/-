"""財報基本面評分（0~100）。

輸入為 yfinance `Ticker.info` 格式的 dict；缺漏的欄位不計分，
全部缺漏時回傳中性 50 分。
"""

from __future__ import annotations

from dataclasses import dataclass, field


def _lin(x: float, lo: float, hi: float) -> float:
    """把 x 線性映射到 0~100：x<=lo 為 0，x>=hi 為 100。"""
    if hi == lo:
        return 50.0
    return max(0.0, min(100.0, (x - lo) / (hi - lo) * 100))


def _get(info: dict, key: str):
    v = info.get(key)
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v == v else None  # 排除 NaN


@dataclass
class FundamentalResult:
    score: float
    reasons: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def score_fundamental(info: dict | None) -> FundamentalResult:
    info = info or {}
    parts: list[tuple[float, float]] = []  # (分數, 權重)
    reasons: list[str] = []
    metrics: dict = {}

    # 獲利能力：ROE
    roe = _get(info, "returnOnEquity")
    if roe is not None:
        metrics["ROE"] = roe * 100
        parts.append((_lin(roe, 0.0, 0.25), 1.5))
        if roe >= 0.15:
            reasons.append(f"ROE {roe*100:.1f}%，獲利能力佳")
        elif roe < 0.05:
            reasons.append(f"ROE 僅 {roe*100:.1f}%，獲利能力偏弱")

    # 淨利率
    pm = _get(info, "profitMargins")
    if pm is not None:
        metrics["淨利率%"] = pm * 100
        parts.append((_lin(pm, 0.0, 0.30), 1.0))
        if pm < 0:
            reasons.append("目前處於虧損")

    # 成長性：營收、盈餘年增
    rg = _get(info, "revenueGrowth")
    if rg is not None:
        metrics["營收年增%"] = rg * 100
        parts.append((_lin(rg, -0.10, 0.30), 1.5))
        if rg >= 0.15:
            reasons.append(f"營收年增 {rg*100:.1f}%，成長強勁")
        elif rg < 0:
            reasons.append(f"營收年減 {abs(rg)*100:.1f}%")
    eg = _get(info, "earningsGrowth")
    if eg is not None:
        metrics["盈餘年增%"] = eg * 100
        parts.append((_lin(eg, -0.20, 0.40), 1.0))

    # 估值：本益比（越低越好，但虧損/負值不給分）
    pe = _get(info, "trailingPE") or _get(info, "forwardPE")
    if pe is not None:
        metrics["本益比"] = pe
        if pe <= 0:
            parts.append((0.0, 1.0))
        else:
            parts.append((100 - _lin(pe, 10, 40), 1.0))
            if pe > 40:
                reasons.append(f"本益比 {pe:.1f} 偏高")
            elif pe < 12:
                reasons.append(f"本益比 {pe:.1f}，估值偏低")

    pb = _get(info, "priceToBook")
    if pb is not None and pb > 0:
        metrics["股價淨值比"] = pb
        parts.append((100 - _lin(pb, 1.0, 8.0), 0.5))

    # 財務體質：負債權益比（yfinance 以百分比表示，例：45.3 代表 0.453）
    de = _get(info, "debtToEquity")
    if de is not None:
        ratio = de / 100 if de > 5 else de
        metrics["負債權益比"] = ratio
        parts.append((100 - _lin(ratio, 0.3, 2.0), 1.0))
        if ratio > 2:
            reasons.append(f"負債權益比 {ratio:.2f} 偏高")

    cr = _get(info, "currentRatio")
    if cr is not None:
        metrics["流動比率"] = cr
        parts.append((_lin(cr, 0.8, 2.0), 0.5))

    # 殖利率（yfinance >= 0.2.54 以百分比表示，例：2.1 代表 2.1%）
    dy = _get(info, "dividendYield")
    if dy is not None:
        pct = dy
        metrics["殖利率%"] = pct
        parts.append((_lin(pct, 0.0, 6.0), 0.5))
        if pct >= 4:
            reasons.append(f"殖利率 {pct:.1f}%")

    if not parts:
        return FundamentalResult(50.0, ["查無財報資料，基本面以中性計"], metrics)

    total_w = sum(w for _, w in parts)
    score = sum(s * w for s, w in parts) / total_w
    # 資料越少，越往中性 50 收斂，避免單一指標主導
    coverage = min(total_w / 6.0, 1.0)
    score = 50 + (score - 50) * coverage
    return FundamentalResult(round(score, 1), reasons, metrics)
