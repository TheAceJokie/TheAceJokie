"""Tests for the baseline deterministic strategy (pure, no network)."""

from __future__ import annotations

from src.models import Candidate
from src.strategy import baseline_intent


def make_candidate(**over):
    feats = {"close": 100.0, "atr14": 2.0, "rsi14": 55.0, "ret_20d": 0.05}
    feats.update(over.pop("features", {}))
    defaults = dict(symbol="AAPL", price=feats["close"], sector="TECH", features=feats)
    defaults.update(over)
    return Candidate(**defaults)


def test_builds_long_intent_with_atr_stop_and_target():
    intent = baseline_intent(make_candidate())
    assert intent is not None
    # stop = 100 - 2*2 = 96; target = 100 + 1.5*(100-96) = 106
    assert intent.entry_price == 100.0
    assert intent.stop_price == 96.0
    assert intent.take_profit_price == 106.0
    assert intent.confidence == 0.70


def test_returns_none_on_zero_atr():
    assert baseline_intent(make_candidate(features={"close": 100.0, "atr14": 0.0})) is None
