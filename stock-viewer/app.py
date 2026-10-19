"""看盤小程式：台股＋美股，自選股、K 線、均線、KD、RSI、MACD，並綜合所有指標判斷多空情勢。

執行方式：streamlit run app.py
"""
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

from indicators import add_all
from signals import analyze

# 台股習慣：紅漲綠跌
UP, DOWN = "#e5383b", "#2a9d4b"
WATCHLIST_FILE = Path(__file__).with_name("watchlist.json")
DEFAULT_WATCHLIST = ["2330", "2317", "2454", "0050", "AAPL", "NVDA"]
# 顯示月數；指標一律用較長的資料計算，避免短期間時均線、KD 還沒算出來
PERIODS = {"1 個月": 1, "3 個月": 3, "6 個月": 6, "1 年": 12, "2 年": 24, "5 年": 60}
VERDICT_COLORS = {"強烈偏多": UP, "偏多": "#f4845f", "盤整中性": "#8d99ae", "偏空": "#52b788", "強烈偏空": DOWN}


# ---------- 自選股存取 ----------
def load_watchlist() -> list[str]:
    try:
        return json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DEFAULT_WATCHLIST.copy()


def save_watchlist(items: list[str]) -> None:
    WATCHLIST_FILE.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")


# ---------- 抓資料 ----------
@st.cache_data(ttl=300, show_spinner=False)
def fetch_history(code: str, period: str) -> tuple[str, pd.DataFrame]:
    """回傳 (Yahoo 代號, 歷史資料)。純數字代號自動嘗試上市 .TW、上櫃 .TWO。"""
    code = code.strip().upper()
    candidates = [f"{code}.TW", f"{code}.TWO"] if code.isdigit() or code[:-1].isdigit() else [code]
    for symbol in candidates:
        df = yf.Ticker(symbol).history(period=period, auto_adjust=False)
        if not df.empty:
            df.index = df.index.tz_localize(None)
            return symbol, df
    return candidates[0], pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_name(symbol: str) -> str:
    try:
        info = yf.Ticker(symbol).info
        return info.get("longName") or info.get("shortName") or symbol
    except Exception:
        return symbol


def quote_row(code: str) -> dict:
    symbol, df = fetch_history(code, "2y")
    if len(df) < 2:
        return {"代號": code, "名稱": "查無資料", "收盤價": None, "漲跌": None, "漲跌幅%": None, "成交量": None,
                "綜合判斷": "-", "評分": None}
    result = analyze(add_all(df))
    last, prev = df.iloc[-1], df.iloc[-2]
    chg = last["Close"] - prev["Close"]
    return {
        "代號": code,
        "名稱": fetch_name(symbol),
        "收盤價": round(last["Close"], 2),
        "漲跌": round(chg, 2),
        "漲跌幅%": round(chg / prev["Close"] * 100, 2),
        "成交量": int(last["Volume"]),
        "綜合判斷": result["verdict"],
        "評分": result["score"] if result["signals"] else None,
    }


# ---------- 圖表 ----------
def build_chart(df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(
        rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02,
        row_heights=[0.44, 0.1, 0.15, 0.15, 0.16],
        subplot_titles=("", "成交量", "KD(9)", "RSI(14)", "MACD(12,26,9)"),
    )
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        increasing_line_color=UP, increasing_fillcolor=UP,
        decreasing_line_color=DOWN, decreasing_fillcolor=DOWN, name="K 線",
    ), row=1, col=1)
    for name, color in (("MA5", "#f4a261"), ("MA20", "#3a86ff"), ("MA60", "#9b5de5")):
        fig.add_trace(go.Scatter(x=df.index, y=df[name], name=name, line=dict(width=1.2, color=color)), row=1, col=1)

    vol_colors = [UP if c >= o else DOWN for o, c in zip(df["Open"], df["Close"])]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=vol_colors, name="成交量", showlegend=False), row=2, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["K"], name="K", line=dict(color="#f4a261")), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["D"], name="D", line=dict(color="#3a86ff")), row=3, col=1)
    for lvl in (20, 80):
        fig.add_hline(y=lvl, line_dash="dot", line_color="gray", row=3, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(color="#9b5de5")), row=4, col=1)
    for lvl in (30, 70):
        fig.add_hline(y=lvl, line_dash="dot", line_color="gray", row=4, col=1)

    osc_colors = [UP if v >= 0 else DOWN for v in df["OSC"].fillna(0)]
    fig.add_trace(go.Bar(x=df.index, y=df["OSC"], marker_color=osc_colors, name="OSC", showlegend=False), row=5, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["DIF"], name="DIF", line=dict(color="#f4a261", dash="dash")), row=5, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD", line=dict(color="#3a86ff", dash="dash")), row=5, col=1)

    fig.update_layout(
        height=1000, margin=dict(l=10, r=10, t=30, b=10), xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.04, x=0), hovermode="x unified",
    )
    # 隱藏週末，K 線才不會有空隙
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    return fig


# ---------- 頁面 ----------
st.set_page_config(page_title="看盤小程式", page_icon="📈", layout="wide")
st.title("📈 看盤小程式")

if "watchlist" not in st.session_state:
    st.session_state.watchlist = load_watchlist()

with st.sidebar:
    st.header("自選股")
    new_code = st.text_input("新增代號（例：2330、AAPL）")
    if st.button("加入", width="stretch") and new_code.strip():
        code = new_code.strip().upper()
        if code not in st.session_state.watchlist:
            st.session_state.watchlist.append(code)
            save_watchlist(st.session_state.watchlist)
            st.rerun()
    remove = st.multiselect("移除", st.session_state.watchlist)
    if remove and st.button("確定移除", width="stretch"):
        st.session_state.watchlist = [c for c in st.session_state.watchlist if c not in remove]
        save_watchlist(st.session_state.watchlist)
        st.rerun()
    st.divider()
    period_label = st.selectbox("K 線期間", list(PERIODS), index=3)
    if st.button("🔄 重新整理資料", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.caption("資料來源：Yahoo Finance（約延遲 15–20 分鐘），每 5 分鐘快取。")

# 自選股總覽
st.subheader("自選股總覽")
if st.session_state.watchlist:
    with st.spinner("抓取報價中…"):
        rows = [quote_row(c) for c in st.session_state.watchlist]
    table = pd.DataFrame(rows)

    def color_change(v):
        if pd.isna(v) or v == 0:
            return ""
        return f"color: {UP if v > 0 else DOWN}; font-weight: 600"

    def color_verdict(v):
        return f"color: {VERDICT_COLORS[v]}; font-weight: 600" if v in VERDICT_COLORS else ""

    st.dataframe(
        table.style.map(color_change, subset=["漲跌", "漲跌幅%", "評分"]).map(color_verdict, subset=["綜合判斷"]).format(
            {"收盤價": "{:,.2f}", "漲跌": "{:+,.2f}", "漲跌幅%": "{:+.2f}%", "成交量": "{:,.0f}", "評分": "{:+.0f}"}, na_rep="-"
        ),
        hide_index=True, width="stretch",
    )
else:
    st.info("左側輸入代號加入自選股。")

# 個股圖表與綜合判斷
st.subheader("個股走勢與情勢判斷")
options = st.session_state.watchlist or DEFAULT_WATCHLIST
selected = st.selectbox("選擇股票", options, label_visibility="collapsed")
months = PERIODS[period_label]
symbol, hist = fetch_history(selected, "5y" if months > 24 else "2y")

if hist.empty:
    st.error(f"抓不到「{selected}」的資料，請確認代號是否正確。")
else:
    full = add_all(hist)
    result = analyze(full)
    df = full[full.index > full.index[-1] - pd.DateOffset(months=months)]
    last, prev = full.iloc[-1], full.iloc[-2] if len(full) > 1 else full.iloc[-1]
    chg = last["Close"] - prev["Close"]
    st.markdown(f"**{fetch_name(symbol)}**（{symbol}）　資料日期：{full.index[-1]:%Y-%m-%d}")
    c1, c2, c3 = st.columns(3)
    # delta_color="inverse" 讓 Streamlit 顯示紅漲綠跌
    c1.metric("收盤價", f"{last['Close']:,.2f}", f"{chg:+,.2f} ({chg / prev['Close'] * 100:+.2f}%)", delta_color="inverse")
    c2.metric("最高 / 最低", f"{last['High']:,.2f} / {last['Low']:,.2f}")
    c3.metric("成交量", f"{last['Volume']:,.0f}")

    # 綜合判斷
    verdict_color = VERDICT_COLORS.get(result["verdict"], "#8d99ae")
    with st.container(border=True):
        left, right = st.columns([1, 2])
        with left:
            st.markdown(
                f"<div style='font-size:0.9rem;opacity:.7'>綜合判斷</div>"
                f"<div style='font-size:2.2rem;font-weight:700;color:{verdict_color}'>{result['verdict']}</div>",
                unsafe_allow_html=True,
            )
            if result["signals"]:
                st.markdown(f"評分 **{result['score']:+d}**（範圍 ±{result['max']}）")
                st.progress((result["score"] + result["max"]) / (2 * result["max"]))
                st.markdown(f"近 20 日支撐 **{result['support']:,.2f}**　壓力 **{result['resistance']:,.2f}**")
            st.caption(result["advice"])
        with right:
            for sig in result["signals"]:
                icon = "🔴" if sig.score > 0 else "🟢" if sig.score < 0 else "⚪"
                st.markdown(f"{icon} **{sig.name}**（{sig.score:+d}）：{sig.reason}")
    st.caption("⚠️ 判斷由技術指標自動計算，只反映過去的價格與成交量，不代表未來走勢，不構成投資建議。")

    st.plotly_chart(build_chart(df), width="stretch")

    with st.expander("查看原始資料"):
        cols = ["Open", "High", "Low", "Close", "Volume", "MA5", "MA20", "MA60", "K", "D", "RSI", "DIF", "MACD", "OSC"]
        st.dataframe(df[cols].iloc[::-1].round(2), width="stretch")
