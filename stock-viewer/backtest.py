"""回測：用過去每天的技術指標評分，統計判斷之後 N 天的實際漲跌。"""
import pandas as pd

from signals import TECH_NAMES, market_adjust, verdict_of

ORDER = ["強烈偏多", "偏多", "盤整中性", "偏空", "強烈偏空"]


def score_series(raw: pd.DataFrame, weights: dict, market_ratio: pd.Series | None = None) -> pd.Series:
    """把逐日的指標分數依權重換成多空比例（-1 ~ +1）。"""
    w = pd.Series({n: weights.get(n, 1.0) for n in TECH_NAMES})
    if w.sum() == 0:
        w[:] = 1.0
    ratio = (raw[TECH_NAMES] * w).sum(axis=1) / (2 * w.sum())
    if market_ratio is not None and not market_ratio.empty:
        ratio = market_adjust(ratio, market_ratio)
    return ratio


def run_backtest(close: pd.Series, ratio: pd.Series, horizons=(5, 20)) -> pd.DataFrame:
    """每種判斷出現的次數，以及之後 N 個交易日的上漲機率與平均報酬（%）。"""
    df = pd.DataFrame({"判斷": ratio.map(verdict_of)})
    for h in horizons:
        df[h] = (close.shift(-h) / close - 1).reindex(df.index) * 100

    def summarize(g: pd.DataFrame) -> dict:
        row = {"次數": len(g)}
        for h in horizons:
            r = g[h].dropna()
            row[f"{h}日上漲機率%"] = (r > 0).mean() * 100 if len(r) else None
            row[f"{h}日平均報酬%"] = r.mean() if len(r) else None
        return row

    rows = {v: summarize(df[df["判斷"] == v]) for v in ORDER}
    rows["所有交易日（對照）"] = summarize(df)
    return pd.DataFrame.from_dict(rows, orient="index")
