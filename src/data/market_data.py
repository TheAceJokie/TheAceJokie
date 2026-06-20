"""Fetch historical daily bars from Alpaca and compute per-symbol features.

Alpaca imports are kept inside this module so the risk engine and its tests
never need the broker SDK installed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from src.config import Settings
from src.data.indicators import compute_features


class MarketData:
    def __init__(self, settings: Settings) -> None:
        # Imported lazily so the package works without alpaca-py for unit tests.
        from alpaca.data.historical import StockHistoricalDataClient

        self._client = StockHistoricalDataClient(
            settings.alpaca_api_key, settings.alpaca_secret_key
        )

    def daily_bars(self, symbol: str, lookback_days: int = 200) -> pd.DataFrame:
        """Return chronological daily OHLCV for a single symbol."""
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=datetime.now(timezone.utc) - timedelta(days=lookback_days * 2),
        )
        df = self._client.get_stock_bars(request).df
        if df.empty:
            return df
        # Multi-index (symbol, timestamp) -> single symbol frame.
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol, level="symbol")
        return df.sort_index()

    def features_for(self, symbol: str) -> dict[str, float] | None:
        """Fetch bars and compute the compact feature summary, or None if thin."""
        bars = self.daily_bars(symbol)
        if bars.empty or len(bars) < 60:
            return None
        return compute_features(bars)
