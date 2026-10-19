# 📈 看盤小程式

用瀏覽器看台股和美股：自選股報價、K 線、均線、KD、RSI、MACD。

## 怎麼開

1. 先安裝 [Python 3.10 以上版本](https://www.python.org/downloads/)（Windows 安裝時記得勾選「Add Python to PATH」）
2. Windows：雙擊 `run.bat`
   Mac / Linux：在終端機執行 `./run.sh`
3. 瀏覽器會自動打開 http://localhost:8501

## 功能

- **自選股總覽**：收盤價、漲跌、漲跌幅、成交量（紅漲綠跌）。在左側新增或移除股票，清單會存在 `watchlist.json`。
- **個股走勢**：K 線＋MA5／MA20／MA60、成交量，副圖可切換 KD、RSI、MACD。
- 期間可選 1 個月到 5 年。

## 代號怎麼打

| 市場 | 範例 |
|---|---|
| 台股上市／上櫃 | `2330`、`0050`（程式會自動判斷是上市 .TW 還是上櫃 .TWO） |
| 美股 | `AAPL`、`NVDA`、`TSLA` |
| 其他 | 直接輸入 Yahoo Finance 代號，例如 `^TWII`（加權指數）、`^GSPC`（S&P 500） |

資料來源是 Yahoo Finance，報價大約延遲 15–20 分鐘，僅供參考。
