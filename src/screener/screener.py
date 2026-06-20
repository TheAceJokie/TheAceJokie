"""Deterministic screen: cut the universe to a handful of candidates in code.

This is the wide end of the funnel — it runs over the whole universe with zero
LLM tokens, so the expensive AI layer only ever sees a few finalists.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.models import Candidate


class ScreenCriteria(BaseModel):
    min_price: float = Field(default=5.0)              # avoid penny stocks
    min_avg_dollar_vol: float = Field(default=2.0e7)   # liquidity: $20M/day
    rsi_min: float = Field(default=40.0)               # not too weak
    rsi_max: float = Field(default=72.0)               # not overbought
    require_uptrend: bool = True                       # close > sma50
    require_positive_momentum: bool = True             # 20d return > 0


def passes(features: dict[str, float], crit: ScreenCriteria) -> bool:
    if features.get("close", 0.0) < crit.min_price:
        return False
    if features.get("avg_dollar_vol", 0.0) < crit.min_avg_dollar_vol:
        return False
    rsi = features.get("rsi14", 0.0)
    if not (crit.rsi_min <= rsi <= crit.rsi_max):
        return False
    if crit.require_uptrend and features.get("close", 0.0) <= features.get("sma50", 0.0):
        return False
    if crit.require_positive_momentum and features.get("ret_20d", 0.0) <= 0.0:
        return False
    return True


def screen(
    features_by_symbol: dict[str, dict[str, float]],
    sector_of,
    criteria: ScreenCriteria | None = None,
) -> list[Candidate]:
    """Return candidates passing the screen, ranked by momentum (best first)."""
    crit = criteria or ScreenCriteria()
    candidates: list[Candidate] = []
    for symbol, feats in features_by_symbol.items():
        if not feats or not passes(feats, crit):
            continue
        candidates.append(
            Candidate(
                symbol=symbol,
                price=feats["close"],
                sector=sector_of(symbol),
                avg_dollar_volume=feats.get("avg_dollar_vol", 0.0),
                features=feats,
            )
        )
    candidates.sort(key=lambda c: c.features.get("ret_20d", 0.0), reverse=True)
    return candidates
