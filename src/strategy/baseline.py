"""Deterministic ATR-based swing entry — the phase-0 baseline strategy.

Produces a TradeIntent with an ATR-derived stop and a 1.5:1 reward:risk target.
Prices come from real computed features; the risk engine still sizes and may veto.
"""

from __future__ import annotations

from src.models import Candidate, Side, TradeIntent

STOP_ATR_MULT = 2.0          # stop = entry - 2*ATR
TARGET_RR = 1.5              # take-profit at 1.5x the risked distance
BASELINE_CONFIDENCE = 0.70   # deterministic baseline confidence


def baseline_intent(candidate: Candidate) -> TradeIntent | None:
    """Build a long swing intent for a candidate, or None if ATR is unusable."""
    feats = candidate.features
    entry = float(feats["close"])
    atr = float(feats.get("atr14", 0.0))
    if atr <= 0 or entry <= 0:
        return None

    stop = entry - STOP_ATR_MULT * atr
    if stop <= 0:
        return None
    target = entry + TARGET_RR * (entry - stop)

    return TradeIntent(
        symbol=candidate.symbol,
        side=Side.BUY,
        entry_price=round(entry, 2),
        stop_price=round(stop, 2),
        take_profit_price=round(target, 2),
        confidence=BASELINE_CONFIDENCE,
        sector=candidate.sector,
        rationale=(
            f"baseline: uptrend, RSI {feats.get('rsi14', 0):.0f}, "
            f"20d ret {feats.get('ret_20d', 0):.1%}, ATR-based stop"
        ),
    )
