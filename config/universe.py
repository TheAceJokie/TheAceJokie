"""Initial trading universe.

Kept small and liquid for phase 0. Replace/expand later (e.g. pull S&P 500
constituents). Sector tags are used by the risk engine's concentration cap.
"""

from __future__ import annotations

# symbol -> sector
UNIVERSE: dict[str, str] = {
    "AAPL": "TECH",
    "MSFT": "TECH",
    "NVDA": "TECH",
    "GOOGL": "TECH",
    "META": "TECH",
    "AMZN": "CONSUMER",
    "TSLA": "CONSUMER",
    "JPM": "FINANCIAL",
    "BAC": "FINANCIAL",
    "V": "FINANCIAL",
    "JNJ": "HEALTH",
    "UNH": "HEALTH",
    "PFE": "HEALTH",
    "XOM": "ENERGY",
    "CVX": "ENERGY",
    "KO": "CONSUMER",
    "PG": "CONSUMER",
    "WMT": "CONSUMER",
    "DIS": "CONSUMER",
    "NFLX": "TECH",
}


def symbols() -> list[str]:
    return list(UNIVERSE.keys())


def sector_of(symbol: str) -> str:
    return UNIVERSE.get(symbol, "UNKNOWN")
