"""Phase-0 pipeline: data -> screen -> baseline strategy -> risk -> execute.

No LLM yet. This proves the funnel and the safety layer work end to end. The
LLM agents slot in at the marked step in a later phase, replacing `baseline_intent`.
"""

from __future__ import annotations

import logging

from config import universe
from src.config import RiskLimits, Settings, load_settings
from src.data.market_data import MarketData
from src.execution import Broker
from src.risk import RiskEngine
from src.screener import screen
from src.strategy import baseline_intent

log = logging.getLogger("pipeline")

MAX_FINALISTS = 3  # how many top candidates to actually act on per run


def run_once(settings: Settings | None = None, limits: RiskLimits | None = None) -> None:
    """Run a single end-to-end cycle (intended to run once daily after close)."""
    settings = settings or load_settings()
    engine = RiskEngine(limits or RiskLimits())
    market = MarketData(settings)
    broker = Broker(settings, sector_of=universe.sector_of)

    portfolio = broker.portfolio_state()
    log.info(
        "account: equity=%.2f buying_power=%.2f positions=%d halted=%s",
        portfolio.equity, portfolio.buying_power,
        len(portfolio.open_positions), portfolio.trading_halted,
    )

    # 1) Compute features across the universe (deterministic, zero tokens).
    features = {}
    for symbol in universe.symbols():
        try:
            feats = market.features_for(symbol)
        except Exception as exc:  # data hiccup on one symbol shouldn't halt all
            log.warning("features failed for %s: %s", symbol, exc)
            continue
        if feats:
            features[symbol] = feats

    # 2) Deterministic screen -> ranked candidates.
    candidates = screen(features, universe.sector_of)
    log.info("screen passed %d/%d symbols", len(candidates), len(features))

    # 3) Act on the top finalists.
    #    >>> LLM agent team slots in HERE in phase 2-3 (replacing baseline_intent).
    for candidate in candidates[:MAX_FINALISTS]:
        intent = baseline_intent(candidate)
        if intent is None:
            continue

        # Re-read portfolio so each decision respects prior ones this run.
        portfolio = broker.portfolio_state()
        decision = engine.evaluate(intent, portfolio)
        if not decision.approved:
            log.info("REJECT %s: %s", candidate.symbol, decision.reason)
            continue

        result = broker.submit_bracket(decision, candidate.symbol)
        log.info("%s -> %s", candidate.symbol, result.detail)
