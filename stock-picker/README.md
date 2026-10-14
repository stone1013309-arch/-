# 📈 每日選股 Stock Picker

每天根據 **前一交易日新聞**、**技術分析**、**公司財報** 三個面向替觀察清單中的股票評分（0~100），
排序後找出值得考慮買進的標的，並列出評分理由。

> ⚠️ 本工具僅供研究與學習，分數是規則式的參考指標，**不構成投資建議**。請自行判斷並控管風險。

## 快速開始

```bash
cd stock-picker
pip install -r requirements.txt

streamlit run app.py          # 網頁介面
python cli.py                 # 命令列：掃描台股預設清單
python cli.py --market 美股
python cli.py --tickers 2330.TW 2454.TW 6669.TW --csv today.csv
python cli.py --demo          # 沒有網路時用模擬資料試跑
```

台股代號要加 `.TW`（上市）或 `.TWO`（上櫃），例如 `2330.TW`。

## 評分方式

| 面向 | 預設權重 | 內容 |
|---|---|---|
| 技術面 | 40% | 均線排列與 MA20 斜率、RSI(14)、MACD 柱狀體與黃金/死亡交叉、前一日量價關係（各 25 分） |
| 基本面 | 35% | ROE、淨利率、營收/盈餘年增、本益比、股價淨值比、負債權益比、流動比率、殖利率；資料越少越往 50 收斂 |
| 新聞面 | 25% | 前一個工作日 00:00 到現在的新聞（週一會包含上週五），以中英文關鍵字判斷利多/利空；新聞少於 3 則時降低影響 |

綜合分數 ≥ 68 → **建議買進**、55~68 → **觀察**、< 55 → **暫不建議**。
門檻、權重與觀察清單都在 `stockpicker/config.py`，網頁介面也可以即時調整權重。

## 用 Claude 判讀新聞（選用）

關鍵字法很粗略，例如分不出「競爭對手大跌」對自己其實是利多。設定 API 金鑰後可改用 Claude 逐則判讀：

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python cli.py --llm           # 網頁介面勾選「用 Claude 判讀新聞情緒」
```

預設模型為 `claude-opus-5-5`，可用環境變數 `STOCKPICKER_CLAUDE_MODEL` 更換（例如較便宜的 `claude-haiku-5-5`）。呼叫失敗時會自動退回關鍵字法。

## 資料來源

- 股價、財報指標、英文新聞：[yfinance](https://github.com/ranaroussi/yfinance)（Yahoo Finance，非官方，偶爾會被限流）
- 中文新聞：Google News RSS

## 專案結構

```
stock-picker/
├── app.py                 # Streamlit 網頁介面
├── cli.py                 # 命令列
├── stockpicker/
│   ├── config.py          # 觀察清單、權重、門檻
│   ├── data.py            # 資料來源（Yahoo / Google News / 示範資料）
│   ├── technical.py       # 技術指標與評分
│   ├── fundamental.py     # 財報評分
│   ├── news.py            # 新聞篩選與情緒評分
│   └── scoring.py         # 綜合評分與排序
└── tests/                 # pytest
```

## 已知限制 / 可以再加強的方向

- 「前一交易日」只排除週末，未排除國定假日。
- 台股財報欄位在 Yahoo 上常有缺漏，可改接 [FinMind](https://finmindtrade.com/) 或公開資訊觀測站取得月營收、三大法人買賣超。
- 評分規則未經回測驗證，建議先用歷史資料回測後再調整權重與門檻。

執行測試：`python -m pytest tests`
