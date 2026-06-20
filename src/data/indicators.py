"""Indicator computation — pure pandas, no network, no LLM.

Every number the strategy and the LLM ever see about a chart is produced here,
in code. The LLM is handed these facts; it never recomputes them.
"""

from __future__ import annotations

import pandas as pd
import pandas_ta as ta


def compute_features(bars: pd.DataFrame) -> dict[str, float]:
    """Compute a compact feature summary from a single symbol's daily OHLCV.

    `bars` must have columns: open, high, low, close, volume (chronological).
    Returns a flat dict of the latest indicator readings — small on purpose so
    it is cheap to pass to an LLM later.
    """
    if len(bars) < 60:
        raise ValueError("need at least 60 bars to compute features")

    close = bars["close"]
    high = bars["high"]
    low = bars["low"]
    volume = bars["volume"]

    sma20 = ta.sma(close, length=20)
    sma50 = ta.sma(close, length=50)
    rsi14 = ta.rsi(close, length=14)
    atr14 = ta.atr(high, low, close, length=14)
    macd = ta.macd(close)  # columns: MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9

    last_close = float(close.iloc[-1])
    avg_dollar_vol = float((close * volume).tail(20).mean())

    return {
        "close": last_close,
        "sma20": _last(sma20),
        "sma50": _last(sma50),
        "rsi14": _last(rsi14),
        "atr14": _last(atr14),
        "atr_pct": _last(atr14) / last_close if last_close else 0.0,
        "macd_hist": _last(macd["MACDh_12_26_9"]) if macd is not None else 0.0,
        "ret_20d": float(close.iloc[-1] / close.iloc[-21] - 1.0),
        "avg_dollar_vol": avg_dollar_vol,
    }


def _last(series: pd.Series) -> float:
    val = series.dropna()
    return float(val.iloc[-1]) if len(val) else 0.0
