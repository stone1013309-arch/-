"""看盤小程式：台股＋美股。技術面、籌碼面、基本面綜合判斷多空，附回測與選股掃描。

執行方式：streamlit run app.py
"""
import json
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from backtest import ORDER, run_backtest, score_series
from data import (download_many, fetch_history, fetch_institutional, fetch_margin, fetch_name,
                  fetch_tw_fundamentals, fetch_us_fundamentals, is_tw)
from indicators import add_all
from signals import (ALL_NAMES, crossed, evaluate, fundamental_signal, institutional_signal, margin_signal,
                     market_ratio_of, tech_score_frame, technical_signals, weekly_signal)
from tw50 import TW50

# 台股習慣：紅漲綠跌
UP, DOWN = "#e5383b", "#2a9d4b"
VERDICT_COLORS = {"強烈偏多": UP, "偏多": "#f4845f", "盤整中性": "#8d99ae", "偏空": "#52b788", "強烈偏空": DOWN}
WATCHLIST_FILE = Path(__file__).with_name("watchlist.json")
DEFAULT_WATCHLIST = ["2330", "2317", "2454", "0050", "AAPL", "NVDA"]
# 顯示月數；指標一律用較長的資料計算，避免短期間時均線、KD 還沒算出來
PERIODS = {"1 個月": 1, "3 個月": 3, "6 個月": 6, "1 年": 12, "2 年": 24, "5 年": 60}
MARKET_NAMES = {"^TWII": "加權指數", "^GSPC": "S&P 500"}


# ---------- 自選股存取 ----------
def load_watchlist() -> list[str]:
    try:
        return json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DEFAULT_WATCHLIST.copy()


def save_watchlist(items: list[str]) -> None:
    WATCHLIST_FILE.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")


# ---------- 分析 ----------
def market_index(symbol: str) -> str:
    return "^TWII" if is_tw(symbol) else "^GSPC"


@st.cache_data(ttl=300, show_spinner=False)
def market_ratio(index_symbol: str) -> float | None:
    _, hist = fetch_history(index_symbol, "2y")
    return market_ratio_of(hist)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_score_frame(symbol: str, period: str) -> pd.DataFrame:
    _, hist = fetch_history(symbol, period)
    return tech_score_frame(add_all(hist)) if not hist.empty else pd.DataFrame()


def _try(label: str, func, notes: list[str]):
    """抓籌碼、基本面時出錯不要讓整頁掛掉，記下原因就好。"""
    try:
        sig = func()
    except Exception as e:  # 網路、API 次數上限、格式變動等
        notes.append(f"{label}：資料抓取失敗（{type(e).__name__}），本次未納入")
        return None
    if sig is None:
        notes.append(f"{label}：無資料，未納入")
    return sig


def analyze_stock(code: str, weights: dict, token: str) -> dict | None:
    symbol, hist = fetch_history(code, "2y")
    if hist.empty:
        return None
    full = add_all(hist)
    signals = technical_signals(full)
    missing = []
    if signals:
        extra = [_try("週線趨勢", lambda: weekly_signal(hist), missing)]
        if is_tw(symbol):
            sid = symbol.split(".")[0]
            extra += [
                _try("法人籌碼", lambda: institutional_signal(fetch_institutional(sid, token)), missing),
                _try("融資融券", lambda: margin_signal(fetch_margin(sid, token), full["Close"]), missing),
                _try("基本面", lambda: fundamental_signal(fetch_tw_fundamentals(sid, token)), missing),
            ]
        else:
            missing.append("法人籌碼、融資融券：美股無此資料，未納入")
            extra.append(_try("基本面", lambda: fundamental_signal(fetch_us_fundamentals(symbol), us=True), missing))
        signals += [s for s in extra if s is not None]
    mkt = market_index(symbol)
    mr = market_ratio(mkt)
    recent = full.iloc[-20:]
    return {
        "symbol": symbol, "full": full, "result": evaluate(signals, weights, mr), "missing": missing,
        "market": mkt, "market_ratio": mr, "support": recent["Low"].min(), "resistance": recent["High"].max(),
    }


def run_scan(weights: dict) -> pd.DataFrame:
    """掃描台灣 50（技術面＋週線＋大盤濾網；籌碼、基本面要逐檔呼叫 API，掃描時不納入）。"""
    data = download_many(tuple(f"{c}.TW" for c in TW50), "2y")
    mr = market_ratio("^TWII")
    rows = []
    for symbol, hist in data.items():
        full = add_all(hist)
        sigs = technical_signals(full)
        if not sigs:
            continue
        wk = weekly_signal(hist)
        if wk:
            sigs.append(wk)
        res = evaluate(sigs, weights, mr)
        last, prev = full.iloc[-1], full.iloc[-2]
        code = symbol.split(".")[0]
        rows.append({
            "代號": code, "名稱": TW50[code], "收盤價": last["Close"],
            "漲跌幅%": (last["Close"] / prev["Close"] - 1) * 100,
            "量比": last["Volume"] / full["Volume"].iloc[-21:-1].mean(),
            "K": last["K"], "多空指數": res["index"], "綜合判斷": res["verdict"],
            "KD低檔金叉": crossed(full["K"], full["D"], 3) == 1 and last["K"] < 30,
        })
    return pd.DataFrame(rows)


# ---------- 表格樣式 ----------
def color_change(v):
    if v is None or pd.isna(v) or v == 0:
        return ""
    return f"color: {UP if v > 0 else DOWN}; font-weight: 600"


def color_verdict(v):
    return f"color: {VERDICT_COLORS[v]}; font-weight: 600" if v in VERDICT_COLORS else ""


def show_table(df: pd.DataFrame, fmt: dict, change_cols=(), verdict_cols=("綜合判斷",)):
    style = df.style.map(color_change, subset=[c for c in change_cols if c in df])
    style = style.map(color_verdict, subset=[c for c in verdict_cols if c in df])
    style = style.format({k: v for k, v in fmt.items() if k in df}, na_rep="-")
    st.dataframe(style, hide_index=True, width="stretch")


# ---------- 圖表 ----------
def build_chart(df: pd.DataFrame, support=None, resistance=None) -> go.Figure:
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
    if support is not None:
        fig.add_hline(y=support, line_dash="dash", line_color=DOWN, annotation_text="支撐", row=1, col=1)
        fig.add_hline(y=resistance, line_dash="dash", line_color=UP, annotation_text="壓力", row=1, col=1)

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


def build_history_chart(close: pd.Series, ratio: pd.Series) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.6, 0.4],
                        subplot_titles=("收盤價", "多空指數（> +20 偏多、< −20 偏空）"))
    fig.add_trace(go.Scatter(x=close.index, y=close, name="收盤價", line=dict(color="#3a86ff")), row=1, col=1)
    idx = ratio * 100
    fig.add_trace(go.Bar(x=idx.index, y=idx, marker_color=[UP if v >= 0 else DOWN for v in idx],
                         name="多空指數"), row=2, col=1)
    for lvl in (20, -20, 50, -50):
        fig.add_hline(y=lvl, line_dash="dot", line_color="gray", row=2, col=1)
    fig.update_layout(height=560, margin=dict(l=10, r=10, t=30, b=10), showlegend=False, hovermode="x unified")
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
    options = st.session_state.watchlist or DEFAULT_WATCHLIST
    selected = st.selectbox("分析股票", options)
    period_label = st.selectbox("K 線期間", list(PERIODS), index=3)
    with st.expander("⚖️ 指標權重"):
        st.caption("0 = 不納入，數字越大影響越大。")
        weights = {n: st.slider(n, 0.0, 3.0, 1.0, 0.5, key=f"w_{n}") for n in ALL_NAMES}
    with st.expander("🔑 FinMind Token（選填）"):
        token = st.text_input("Token", value=os.environ.get("FINMIND_TOKEN", ""), type="password",
                              label_visibility="collapsed")
        st.caption("不填也能用，但免費次數較少。到 finmindtrade.com 免費註冊即可取得。")
    if st.button("🔄 重新整理資料", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.caption("股價：Yahoo Finance（約延遲 15–20 分鐘）\n\n台股籌碼、基本面：FinMind")

tab_list, tab_stock, tab_bt, tab_scan = st.tabs(["📋 自選股總覽", "📊 個股分析", "🧪 回測", "🔍 選股掃描與排行"])

# 自選股總覽
with tab_list:
    if st.session_state.watchlist:
        rows = []
        with st.spinner("分析自選股中…"):
            for c in st.session_state.watchlist:
                a = analyze_stock(c, weights, token)
                if a is None:
                    rows.append({"代號": c, "名稱": "查無資料"})
                    continue
                full, res = a["full"], a["result"]
                last, prev = full.iloc[-1], full.iloc[-2]
                chg = last["Close"] - prev["Close"]
                rows.append({
                    "代號": c, "名稱": fetch_name(a["symbol"]), "收盤價": last["Close"], "漲跌": chg,
                    "漲跌幅%": chg / prev["Close"] * 100, "成交量": last["Volume"],
                    "多空指數": res["index"], "綜合判斷": res["verdict"],
                })
        show_table(pd.DataFrame(rows),
                   {"收盤價": "{:,.2f}", "漲跌": "{:+,.2f}", "漲跌幅%": "{:+.2f}%", "成交量": "{:,.0f}", "多空指數": "{:+.0f}"},
                   change_cols=("漲跌", "漲跌幅%", "多空指數"))
        st.caption("多空指數 −100～+100：+50 以上強烈偏多、+20 以上偏多、−20～+20 盤整、−20 以下偏空、−50 以下強烈偏空。")
    else:
        st.info("左側輸入代號加入自選股。")

# 個股分析
with tab_stock:
    a = analyze_stock(selected, weights, token)
    if a is None:
        st.error(f"抓不到「{selected}」的資料，請確認代號是否正確。")
    else:
        full, result = a["full"], a["result"]
        last, prev = full.iloc[-1], full.iloc[-2]
        chg = last["Close"] - prev["Close"]
        st.markdown(f"### {fetch_name(a['symbol'])}（{a['symbol']}）")
        st.caption(f"資料日期：{full.index[-1]:%Y-%m-%d}")
        c1, c2, c3 = st.columns(3)
        # delta_color="inverse" 讓 Streamlit 顯示紅漲綠跌
        c1.metric("收盤價", f"{last['Close']:,.2f}", f"{chg:+,.2f} ({chg / prev['Close'] * 100:+.2f}%)", delta_color="inverse")
        c2.metric("最高 / 最低", f"{last['High']:,.2f} / {last['Low']:,.2f}")
        c3.metric("成交量", f"{last['Volume']:,.0f}")

        color = VERDICT_COLORS.get(result["verdict"], "#8d99ae")
        with st.container(border=True):
            left, right = st.columns([1, 2])
            with left:
                st.markdown(
                    f"<div style='font-size:0.9rem;opacity:.7'>綜合判斷</div>"
                    f"<div style='font-size:2.2rem;font-weight:700;color:{color}'>{result['verdict']}</div>",
                    unsafe_allow_html=True,
                )
                if result["index"] is not None:
                    st.markdown(f"多空指數 **{result['index']:+d}**（−100～+100）")
                    st.progress((result["index"] + 100) / 200)
                    st.markdown(f"近 20 日支撐 **{a['support']:,.2f}**　壓力 **{a['resistance']:,.2f}**")
                st.caption(result["advice"])
                if a["market_ratio"] is not None:
                    st.caption(f"大盤（{MARKET_NAMES[a['market']]}）多空指數 {a['market_ratio'] * 100:+.0f}")
            with right:
                for sig in result["signals"]:
                    icon = "🔴" if sig.score > 0 else "🟢" if sig.score < 0 else "⚪"
                    w = weights.get(sig.name, 1.0)
                    wtxt = "，未計分" if w == 0 else f"，權重 {w:g}" if w != 1 else ""
                    st.markdown(f"{icon} **{sig.name}**（{sig.score:+d}{wtxt}）：{sig.reason}")
                for note in result["notes"]:
                    st.markdown(f"⚖️ {note}")
                for m in a["missing"]:
                    st.caption(f"— {m}")
        st.caption("⚠️ 判斷由指標自動計算，只反映過去的資料，不代表未來走勢，不構成投資建議。")

        df = full[full.index > full.index[-1] - pd.DateOffset(months=PERIODS[period_label])]
        st.plotly_chart(build_chart(df, a["support"], a["resistance"]), width="stretch")
        with st.expander("查看原始資料"):
            cols = ["Open", "High", "Low", "Close", "Volume", "MA5", "MA20", "MA60", "K", "D", "RSI", "DIF", "MACD", "OSC"]
            st.dataframe(df[cols].iloc[::-1].round(2), width="stretch")

# 回測
with tab_bt:
    symbol, hist5 = fetch_history(selected, "5y")
    if hist5.empty:
        st.error(f"抓不到「{selected}」的資料。")
    else:
        with st.spinner("回測計算中（第一次約需數秒）…"):
            raw = cached_score_frame(symbol, "5y")
            mraw = cached_score_frame(market_index(symbol), "5y")
        if raw.empty:
            st.info("資料不足，無法回測。")
        else:
            mratio = score_series(mraw, {}) if not mraw.empty else None
            ratio = score_series(raw, weights, mratio)
            table = run_backtest(hist5["Close"], ratio)
            st.markdown(f"### {fetch_name(symbol)}：判斷準不準？")
            st.caption(f"回測期間 {ratio.index[0]:%Y-%m-%d} ～ {ratio.index[-1]:%Y-%m-%d}，共 {len(ratio)} 個交易日。"
                       "每天只用當天以前的資料評分，再看之後 5 天、20 天的實際漲跌。")
            show_table(table.reset_index(names="判斷"),
                       {"次數": "{:,.0f}", "5日上漲機率%": "{:.1f}%", "5日平均報酬%": "{:+.2f}%",
                        "20日上漲機率%": "{:.1f}%", "20日平均報酬%": "{:+.2f}%"},
                       change_cols=("5日平均報酬%", "20日平均報酬%"), verdict_cols=("判斷",))
            base = table.loc["所有交易日（對照）"]
            bull = table.loc[["強烈偏多", "偏多"]].dropna(subset=["20日上漲機率%"])
            if bull["次數"].sum() and pd.notna(base["20日上漲機率%"]):
                bull_rate = (bull["20日上漲機率%"] * bull["次數"]).sum() / bull["次數"].sum()
                diff = bull_rate - base["20日上漲機率%"]
                verdict = "有參考價值" if diff >= 5 else "參考價值有限" if diff >= 0 else "效果不佳，建議調整權重"
                st.info(f"判斷「偏多」以上時，20 日後上漲機率 {bull_rate:.1f}%，"
                        f"比隨便哪天買（{base['20日上漲機率%']:.1f}%）{'高' if diff >= 0 else '低'} {abs(diff):.1f} 個百分點：**{verdict}**。")
            st.caption("回測只用五項技術指標＋大盤濾網（週線、法人、融資、基本面沒有逐日的歷史評分）。"
                       "可以在左側調整權重，看哪種組合比較準。過去表現不代表未來。")
            st.markdown("#### 歷史評分走勢")
            st.plotly_chart(build_history_chart(hist5["Close"].reindex(ratio.index), ratio), width="stretch")

# 選股掃描與排行
with tab_scan:
    st.markdown("掃描**台灣 50 成分股**，用技術面＋週線＋大盤濾網評分（籌碼、基本面需逐檔查詢，請在個股分析看）。")
    if st.button("🔍 開始掃描", type="primary"):
        with st.spinner("下載 50 檔股票資料中…"):
            st.session_state.scan = run_scan(weights)
    scan = st.session_state.get("scan")
    if scan is not None and not scan.empty:
        fmt = {"收盤價": "{:,.2f}", "漲跌幅%": "{:+.2f}%", "量比": "{:.1f} 倍", "K": "{:.0f}", "多空指數": "{:+.0f}"}
        cols = ["代號", "名稱", "收盤價", "漲跌幅%", "量比", "K", "多空指數", "綜合判斷"]
        picks = st.multiselect("篩選判斷", ORDER, default=["強烈偏多", "偏多"])
        hit = scan[scan["綜合判斷"].isin(picks)].sort_values("多空指數", ascending=False)
        st.markdown(f"#### 符合條件：{len(hit)} 檔")
        show_table(hit[cols], fmt, change_cols=("漲跌幅%", "多空指數"))

        r1, r2, r3 = st.columns(3)
        with r1:
            st.markdown("#### 🚀 今日漲幅前 10")
            show_table(scan.nlargest(10, "漲跌幅%")[["代號", "名稱", "漲跌幅%", "綜合判斷"]], fmt, change_cols=("漲跌幅%",))
        with r2:
            st.markdown("#### 📊 成交量暴增前 10")
            show_table(scan.nlargest(10, "量比")[["代號", "名稱", "量比", "漲跌幅%"]], fmt, change_cols=("漲跌幅%",))
        with r3:
            st.markdown("#### ✨ KD 低檔黃金交叉")
            kd = scan[scan["KD低檔金叉"]]
            if kd.empty:
                st.caption("目前沒有符合的股票。")
            else:
                show_table(kd[["代號", "名稱", "K", "綜合判斷"]], fmt)
        st.caption("量比 = 今日成交量 ÷ 20 日均量。")

        add = st.multiselect("加入自選股", [c for c in scan["代號"] if c not in st.session_state.watchlist],
                             format_func=lambda c: f"{c} {TW50.get(c, '')}")
        if add and st.button("加入自選股"):
            st.session_state.watchlist += add
            save_watchlist(st.session_state.watchlist)
            st.rerun()
    elif scan is not None:
        st.warning("掃描失敗，請稍後再試。")
