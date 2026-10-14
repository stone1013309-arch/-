"""Streamlit 介面：streamlit run app.py"""

from __future__ import annotations

import os

import streamlit as st

from stockpicker.config import DEFAULT_WEIGHTS, WATCHLISTS
from stockpicker.data import DemoProvider, YahooProvider
from stockpicker.scoring import scan, to_frame
from stockpicker.technical import add_indicators

st.set_page_config(page_title="每日選股", page_icon="📈", layout="wide")
st.title("📈 每日選股")
st.caption("結合前一交易日新聞、技術分析與公司財報，找出值得關注的股票。僅供研究參考，不構成投資建議。")

with st.sidebar:
    st.header("設定")
    demo = st.toggle("示範模式（離線模擬資料）", value=False)
    market = st.selectbox("市場", list(WATCHLISTS))
    default = WATCHLISTS[market]
    custom = st.text_area("自訂代號（每行一個，留空用預設清單）", placeholder="2330.TW\n2454.TW")

    st.subheader("權重")
    wt = st.slider("技術面", 0.0, 1.0, DEFAULT_WEIGHTS["technical"], 0.05)
    wf = st.slider("基本面", 0.0, 1.0, DEFAULT_WEIGHTS["fundamental"], 0.05)
    wn = st.slider("新聞面", 0.0, 1.0, DEFAULT_WEIGHTS["news"], 0.05)
    use_llm = st.checkbox("用 Claude 判讀新聞情緒", value=False,
                          disabled=not os.environ.get("ANTHROPIC_API_KEY"),
                          help="需設定環境變數 ANTHROPIC_API_KEY")
    run = st.button("開始分析", type="primary", width="stretch")

if custom.strip():
    all_names = {k: v for wl in WATCHLISTS.values() for k, v in wl.items()}
    watchlist = {t.strip(): all_names.get(t.strip(), t.strip()) for t in custom.splitlines() if t.strip()}
else:
    watchlist = default

if run:
    provider = DemoProvider() if demo else YahooProvider()
    weights = {"technical": wt, "fundamental": wf, "news": wn}
    with st.spinner(f"從 {provider.name} 取得 {len(watchlist)} 檔資料中…"):
        st.session_state.reports = scan(watchlist, provider, weights, use_llm=use_llm)
        st.session_state.source = provider.name

reports = st.session_state.get("reports")
if not reports:
    st.info("在左側選擇市場後按「開始分析」。")
    st.stop()

st.caption(f"資料來源：{st.session_state.source}")
df = to_frame(reports)

buys = [r for r in reports if r.rating == "建議買進"]
c1, c2, c3 = st.columns(3)
c1.metric("掃描檔數", len(reports))
c2.metric("建議買進", len(buys))
c3.metric("最高分", f"{reports[0].ticker} {reports[0].total}")


def _color(v):
    return {"建議買進": "background-color: #c8f7c5", "觀察": "background-color: #fff3c4"}.get(v, "")


st.dataframe(df.style.map(_color, subset=["建議"]), width="stretch", hide_index=True)

st.subheader("個股明細")
pick = st.selectbox("選擇股票", [f"{r.ticker} {r.name}" for r in reports])
r = next(x for x in reports if f"{x.ticker} {x.name}" == pick)

a, b, c, d = st.columns(4)
a.metric("綜合", r.total, r.rating, delta_color="off")
b.metric("技術面", r.technical.score)
c.metric("基本面", r.fundamental.score)
d.metric("新聞面", r.news.score)
if r.error:
    st.warning(r.error)

if r.history is not None and len(r.history):
    ind = add_indicators(r.history).tail(120)
    st.line_chart(ind[["Close", "MA20", "MA60"]])
    st.bar_chart(ind["MACD_hist"], height=150)

left, right = st.columns(2)
with left:
    st.markdown("**評分理由**")
    for reason in r.technical.reasons + r.fundamental.reasons + r.news.reasons:
        st.markdown(f"- {reason}")
    if r.fundamental.metrics:
        st.markdown("**財報指標**")
        st.table({k: [round(v, 2)] for k, v in r.fundamental.metrics.items()})
with right:
    st.markdown("**前一交易日以來新聞**")
    if not r.news.items:
        st.write("無")
    for n in r.news.items:
        icon = "🟢" if n.sentiment > 0.2 else "🔴" if n.sentiment < -0.2 else "⚪"
        title = f"[{n.title}]({n.link})" if n.link else n.title
        st.markdown(f"{icon} {title}  \n<small>{n.source} · {n.published:%m/%d %H:%M}</small>",
                    unsafe_allow_html=True)
