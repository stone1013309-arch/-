"""抓資料：股價用 Yahoo Finance，台股法人、融資融券、基本面用 FinMind。"""
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

from tw50 import TW50

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"


def is_tw(symbol: str) -> bool:
    return symbol.endswith((".TW", ".TWO"))


def _naive(df: pd.DataFrame) -> pd.DataFrame:
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


@st.cache_data(ttl=300, show_spinner=False)
def fetch_history(code: str, period: str) -> tuple[str, pd.DataFrame]:
    """回傳 (Yahoo 代號, 歷史資料)。純數字代號自動嘗試上市 .TW、上櫃 .TWO。"""
    code = code.strip().upper()
    candidates = [f"{code}.TW", f"{code}.TWO"] if code.isdigit() or code[:-1].isdigit() else [code]
    for symbol in candidates:
        df = yf.Ticker(symbol).history(period=period, auto_adjust=False)
        if not df.empty:
            return symbol, _naive(df)
    return candidates[0], pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def download_many(symbols: tuple[str, ...], period: str) -> dict[str, pd.DataFrame]:
    """一次下載多檔股票（選股掃描用）。"""
    raw = yf.download(list(symbols), period=period, group_by="ticker", auto_adjust=False,
                      progress=False, threads=True)
    out = {}
    for s in symbols:
        if s in raw.columns.get_level_values(0):
            df = raw[s].dropna(how="all")
            if not df.empty:
                out[s] = _naive(df.copy())
    return out


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_name(symbol: str) -> str:
    code = symbol.split(".")[0]
    if code in TW50:
        return TW50[code]
    try:
        info = yf.Ticker(symbol).info
        return info.get("longName") or info.get("shortName") or symbol
    except Exception:
        return symbol


# ---------- FinMind（台股） ----------
@st.cache_data(ttl=3600, show_spinner=False)
def finmind(dataset: str, stock_id: str, days: int, token: str = "") -> pd.DataFrame:
    params = {"dataset": dataset, "data_id": stock_id, "start_date": str(date.today() - timedelta(days=days))}
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.get(FINMIND_URL, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != 200:
        raise RuntimeError(body.get("msg", "FinMind 回傳錯誤"))
    return pd.DataFrame(body.get("data", []))


def fetch_institutional(stock_id: str, token: str = "") -> pd.DataFrame:
    """三大法人買賣超（股數）。欄位：date, name, buy, sell。"""
    return finmind("TaiwanStockInstitutionalInvestorsBuySell", stock_id, 20, token)


def fetch_margin(stock_id: str, token: str = "") -> pd.DataFrame:
    """融資融券餘額（張）。"""
    return finmind("TaiwanStockMarginPurchaseShortSale", stock_id, 20, token)


def fetch_tw_fundamentals(stock_id: str, token: str = "") -> dict:
    """本益比、殖利率、最新月營收年增率、近四季 EPS。抓不到的欄位為 None。"""
    out = {"PER": None, "殖利率": None, "營收年增": None, "EPS": None}
    per = finmind("TaiwanStockPER", stock_id, 14, token)
    if not per.empty:
        last = per.sort_values("date").iloc[-1]
        out["PER"] = float(last["PER"]) or None
        out["殖利率"] = float(last["dividend_yield"])
    rev = finmind("TaiwanStockMonthRevenue", stock_id, 450, token)
    if not rev.empty:
        rev = rev.sort_values("date")
        last = rev.iloc[-1]
        prev = rev[(rev["revenue_year"] == last["revenue_year"] - 1) & (rev["revenue_month"] == last["revenue_month"])]
        if not prev.empty and prev["revenue"].iloc[0]:
            out["營收年增"] = (last["revenue"] / prev["revenue"].iloc[0] - 1) * 100
    fin = finmind("TaiwanStockFinancialStatements", stock_id, 450, token)
    if not fin.empty:
        eps = fin[fin["type"] == "EPS"].sort_values("date")["value"]
        if len(eps) >= 4:
            out["EPS"] = float(eps.iloc[-4:].sum())
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_us_fundamentals(symbol: str) -> dict:
    info = yf.Ticker(symbol).info
    yld = info.get("trailingAnnualDividendYield")
    growth = info.get("revenueGrowth")
    return {
        "PER": info.get("trailingPE"),
        "殖利率": yld * 100 if yld is not None else None,
        "營收年增": growth * 100 if growth is not None else None,
        "EPS": info.get("trailingEps"),
    }
