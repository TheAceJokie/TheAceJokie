"""Tests for the deterministic screener (pure, no network)."""

from __future__ import annotations

from src.screener import ScreenCriteria, screen
from src.screener.screener import passes


def good_features(**over):
    feats = {
        "close": 100.0,
        "sma50": 90.0,        # close > sma50 -> uptrend
        "rsi14": 55.0,
        "ret_20d": 0.05,
        "avg_dollar_vol": 5.0e7,
        "atr14": 2.0,
    }
    feats.update(over)
    return feats


def test_clean_uptrend_passes():
    assert passes(good_features(), ScreenCriteria())


def test_low_liquidity_filtered():
    assert not passes(good_features(avg_dollar_vol=1.0e6), ScreenCriteria())


def test_downtrend_filtered():
    assert not passes(good_features(close=80.0), ScreenCriteria())  # below sma50


def test_overbought_filtered():
    assert not passes(good_features(rsi14=85.0), ScreenCriteria())


def test_negative_momentum_filtered():
    assert not passes(good_features(ret_20d=-0.02), ScreenCriteria())


def test_screen_ranks_by_momentum():
    feats = {
        "AAA": good_features(ret_20d=0.02),
        "BBB": good_features(ret_20d=0.10),
        "CCC": good_features(ret_20d=0.05),
        "LOW": good_features(avg_dollar_vol=1.0),  # filtered out
    }
    out = screen(feats, sector_of=lambda s: "TECH")
    assert [c.symbol for c in out] == ["BBB", "CCC", "AAA"]
    assert all(c.sector == "TECH" for c in out)
