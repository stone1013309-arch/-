"""技術指標計算：均線、KD、RSI、MACD。"""
import pandas as pd


def add_ma(df: pd.DataFrame, windows=(5, 20, 60)) -> pd.DataFrame:
    for w in windows:
        df[f"MA{w}"] = df["Close"].rolling(w).mean()
    return df


def add_kd(df: pd.DataFrame, n: int = 9) -> pd.DataFrame:
    """台灣常用的 KD（RSV 以 1/3 平滑）。"""
    low_n = df["Low"].rolling(n).min()
    high_n = df["High"].rolling(n).max()
    rsv = (df["Close"] - low_n) / (high_n - low_n) * 100
    k, d = [], []
    prev_k = prev_d = 50.0
    for v in rsv:
        if pd.isna(v):
            k.append(float("nan"))
            d.append(float("nan"))
            continue
        prev_k = prev_k * 2 / 3 + v / 3
        prev_d = prev_d * 2 / 3 + prev_k / 3
        k.append(prev_k)
        d.append(prev_d)
    df["K"] = k
    df["D"] = d
    return df


def add_rsi(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    df["RSI"] = 100 - 100 / (1 + gain / loss)
    return df


def add_macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> pd.DataFrame:
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    df["DIF"] = ema_fast - ema_slow
    df["MACD"] = df["DIF"].ewm(span=signal, adjust=False).mean()
    df["OSC"] = df["DIF"] - df["MACD"]
    return df


def add_all(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for f in (add_ma, add_kd, add_rsi, add_macd):
        df = f(df)
    return df
