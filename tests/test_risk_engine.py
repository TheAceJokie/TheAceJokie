"""Unit tests for the deterministic risk engine — the capital guardrail.

These run without any network or broker dependency.
"""

from __future__ import annotations

import pytest

from src.config import RiskLimits
from src.models import PortfolioState, Position, Side, TradeIntent
from src.risk import RiskEngine


def make_portfolio(**kwargs) -> PortfolioState:
    defaults = dict(equity=100_000.0, buying_power=100_000.0)
    defaults.update(kwargs)
    return PortfolioState(**defaults)


def make_intent(**kwargs) -> TradeIntent:
    defaults = dict(
        symbol="AAPL",
        side=Side.BUY,
        entry_price=100.0,
        stop_price=95.0,  # 5% stop
        take_profit_price=115.0,
        confidence=0.8,
        sector="TECH",
    )
    defaults.update(kwargs)
    return TradeIntent(**defaults)


# --- Sizing ----------------------------------------------------------------


def test_position_sized_by_risk_rule():
    # equity 100k, 1% risk = $1000 risked. risk/share = $5 -> 200 shares.
    engine = RiskEngine(RiskLimits(max_risk_per_trade_pct=0.01))
    decision = engine.evaluate(make_intent(), make_portfolio())
    assert decision.approved
    assert decision.qty == 200
    assert decision.risk_amount == pytest.approx(1000.0)


def test_single_position_cap_can_bind():
    # 1% risk would allow 200 sh ($20k). But max_position_pct=0.10 -> $10k -> 100 sh.
    engine = RiskEngine(
        RiskLimits(max_risk_per_trade_pct=0.01, max_position_pct=0.10)
    )
    decision = engine.evaluate(make_intent(), make_portfolio())
    assert decision.approved
    assert decision.qty == 100


def test_buying_power_cap_can_bind():
    engine = RiskEngine(RiskLimits(max_risk_per_trade_pct=0.05))
    # Only $3000 buying power -> 30 shares at $100.
    decision = engine.evaluate(make_intent(), make_portfolio(buying_power=3000.0))
    assert decision.approved
    assert decision.qty == 30


# --- Hard gates ------------------------------------------------------------


def test_low_confidence_rejected():
    engine = RiskEngine(RiskLimits(min_confidence=0.6))
    decision = engine.evaluate(make_intent(confidence=0.4), make_portfolio())
    assert not decision.approved
    assert "confidence" in decision.reason


def test_trading_halted_rejected():
    engine = RiskEngine()
    decision = engine.evaluate(make_intent(), make_portfolio(trading_halted=True))
    assert not decision.approved
    assert "halt" in decision.reason.lower()


def test_daily_loss_limit_acts_as_kill_switch():
    engine = RiskEngine(RiskLimits(daily_loss_limit_pct=0.03))
    # Lost $3,500 today on 100k equity -> beyond the 3% ($3,000) limit.
    decision = engine.evaluate(
        make_intent(), make_portfolio(realized_pnl_today=-3_500.0)
    )
    assert not decision.approved
    assert "loss limit" in decision.reason


def test_max_open_positions_rejected():
    engine = RiskEngine(RiskLimits(max_open_positions=2))
    portfolio = make_portfolio(
        open_positions=[
            Position(symbol="MSFT", qty=10, avg_entry_price=300, sector="TECH"),
            Position(symbol="KO", qty=10, avg_entry_price=60, sector="CONSUMER"),
        ]
    )
    decision = engine.evaluate(make_intent(), portfolio)
    assert not decision.approved
    assert "max open positions" in decision.reason


def test_already_held_symbol_rejected():
    engine = RiskEngine()
    portfolio = make_portfolio(
        open_positions=[
            Position(symbol="AAPL", qty=10, avg_entry_price=90, sector="TECH")
        ]
    )
    decision = engine.evaluate(make_intent(symbol="AAPL"), portfolio)
    assert not decision.approved
    assert "already holding" in decision.reason


def test_sector_cap_can_zero_out_sizing():
    # Sector already at the 40% cap -> no room for another TECH name.
    engine = RiskEngine(RiskLimits(max_sector_pct=0.40))
    portfolio = make_portfolio(
        open_positions=[
            Position(symbol="MSFT", qty=400, avg_entry_price=100, sector="TECH")
        ]
    )
    decision = engine.evaluate(make_intent(symbol="NVDA"), portfolio)
    assert not decision.approved
    assert "zero shares" in decision.reason


# --- Stop geometry ---------------------------------------------------------


def test_stop_too_tight_rejected():
    engine = RiskEngine(RiskLimits(min_stop_distance_pct=0.01))
    # 0.2% stop is below the 1% minimum.
    decision = engine.evaluate(
        make_intent(entry_price=100.0, stop_price=99.8), make_portfolio()
    )
    assert not decision.approved
    assert "too tight" in decision.reason


def test_stop_too_wide_rejected():
    engine = RiskEngine(RiskLimits(max_stop_distance_pct=0.10))
    # 20% stop exceeds the 10% maximum.
    decision = engine.evaluate(
        make_intent(entry_price=100.0, stop_price=80.0), make_portfolio()
    )
    assert not decision.approved
    assert "too wide" in decision.reason


def test_intent_rejects_stop_above_entry_at_construction():
    # The model itself refuses an incoherent long (stop above entry).
    with pytest.raises(ValueError):
        make_intent(entry_price=100.0, stop_price=105.0)


def test_sell_side_rejected_in_phase0():
    engine = RiskEngine()
    # Build a SELL intent bypassing the long-only price validator.
    intent = TradeIntent.model_construct(
        symbol="AAPL",
        side=Side.SELL,
        entry_price=100.0,
        stop_price=105.0,
        take_profit_price=None,
        confidence=0.9,
        sector="TECH",
        rationale="",
    )
    decision = engine.evaluate(intent, make_portfolio())
    assert not decision.approved
    assert "long-only" in decision.reason
