"""命令列每日選股。

用法：
    python cli.py                 # 掃描台股預設清單
    python cli.py --market 美股
    python cli.py --tickers 2330.TW 2454.TW AAPL
    python cli.py --demo          # 離線示範資料
    python cli.py --llm           # 用 Claude 判讀新聞（需 ANTHROPIC_API_KEY）
"""

from __future__ import annotations

import argparse
import sys

from stockpicker.config import WATCHLISTS
from stockpicker.scoring import scan, to_frame


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="根據前一日新聞、技術分析、財報找出值得關注的股票")
    p.add_argument("--market", choices=list(WATCHLISTS), default="台股")
    p.add_argument("--tickers", nargs="+", help="自訂代號（台股請加 .TW，例如 2330.TW）")
    p.add_argument("--top", type=int, default=10, help="顯示前幾名")
    p.add_argument("--demo", action="store_true", help="使用離線示範資料")
    p.add_argument("--llm", action="store_true", help="使用 Claude 判讀新聞情緒")
    p.add_argument("--csv", help="另存結果為 CSV")
    a = p.parse_args(argv)

    if a.demo:
        from stockpicker.data import DemoProvider
        provider = DemoProvider()
    else:
        from stockpicker.data import YahooProvider
        provider = YahooProvider()

    if a.tickers:
        names = {k: v for wl in WATCHLISTS.values() for k, v in wl.items()}
        watchlist = {t: names.get(t, t) for t in a.tickers}
    else:
        watchlist = WATCHLISTS[a.market]

    print(f"資料來源：{provider.name}，掃描 {len(watchlist)} 檔…\n")
    reports = scan(watchlist, provider, use_llm=a.llm)
    df = to_frame(reports)
    print(df.head(a.top).to_string(index=False))

    print("\n=== 前幾名理由 ===")
    for r in reports[: min(3, a.top)]:
        print(f"\n【{r.ticker} {r.name}】{r.total} 分 → {r.rating}")
        if r.error:
            print(f"  ! {r.error}")
        for reason in r.technical.reasons + r.fundamental.reasons + r.news.reasons:
            print(f"  - {reason}")

    if a.csv:
        df.to_csv(a.csv, index=False, encoding="utf-8-sig")
        print(f"\n已輸出 {a.csv}")
    print("\n※ 本工具僅供研究參考，不構成投資建議。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
