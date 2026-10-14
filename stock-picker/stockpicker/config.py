"""預設觀察清單與評分權重。"""

# 台股常見權值股（Yahoo Finance 代號需加 .TW / .TWO）
TW_WATCHLIST = {
    "2330.TW": "台積電",
    "2317.TW": "鴻海",
    "2454.TW": "聯發科",
    "2308.TW": "台達電",
    "2382.TW": "廣達",
    "2412.TW": "中華電",
    "2881.TW": "富邦金",
    "2882.TW": "國泰金",
    "2891.TW": "中信金",
    "2303.TW": "聯電",
    "3711.TW": "日月光投控",
    "2002.TW": "中鋼",
    "1301.TW": "台塑",
    "2603.TW": "長榮",
    "3008.TW": "大立光",
}

US_WATCHLIST = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "GOOGL": "Alphabet",
    "AMZN": "Amazon",
    "META": "Meta",
    "TSLA": "Tesla",
    "AVGO": "Broadcom",
    "JPM": "JPMorgan",
    "COST": "Costco",
}

WATCHLISTS = {"台股": TW_WATCHLIST, "美股": US_WATCHLIST}

# 三大面向權重（總和 1）
DEFAULT_WEIGHTS = {"technical": 0.40, "fundamental": 0.35, "news": 0.25}

# 綜合分數門檻
BUY_THRESHOLD = 68
WATCH_THRESHOLD = 55

TIMEZONE = "Asia/Taipei"
