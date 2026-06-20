"""Core data schemas shared across every layer.

Kept dependency-light (pydantic + stdlib only) so the risk engine and its tests
never need network or broker libraries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Side(str, Enum):
    """Direction of a trade. Phase 0 is long-only; SELL is reserved for exits."""

    BUY = "buy"
    SELL = "sell"


class Candidate(BaseModel):
    """A symbol that passed the deterministic screener, with computed features.

    All indicator values are computed in Python and handed to the LLM as facts —
    the model never recalculates them.
    """

    symbol: str
    price: float
    sector: str = "UNKNOWN"
    avg_dollar_volume: float = 0.0
    features: dict[str, float] = Field(default_factory=dict)


class TradeIntent(BaseModel):
    """A *proposed* trade. Produced by the strategy/LLM, never executed directly.

    The risk engine is the only thing that turns an intent into an executable
    order — and it may veto it. Prices come from real market data; the engine
    recomputes quantity itself.
    """

    symbol: str
    side: Side = Side.BUY
    entry_price: float = Field(gt=0)
    stop_price: float = Field(gt=0)
    take_profit_price: float | None = Field(default=None, gt=0)
    confidence: float = Field(ge=0.0, le=1.0)
    sector: str = "UNKNOWN"
    rationale: str = ""

    @model_validator(mode="after")
    def _check_price_geometry(self) -> "TradeIntent":
        # For a long entry, stop must sit below entry and target above it.
        if self.side is Side.BUY:
            if self.stop_price >= self.entry_price:
                raise ValueError("stop_price must be below entry_price for a long")
            if self.take_profit_price is not None and self.take_profit_price <= self.entry_price:
                raise ValueError("take_profit_price must be above entry_price for a long")
        return self


class Position(BaseModel):
    """An open position currently held in the account."""

    symbol: str
    qty: float
    avg_entry_price: float = Field(gt=0)
    sector: str = "UNKNOWN"

    @property
    def market_value(self) -> float:
        return self.qty * self.avg_entry_price


class PortfolioState(BaseModel):
    """Snapshot of the account the risk engine reasons about."""

    equity: float = Field(gt=0)
    buying_power: float = Field(ge=0)
    open_positions: list[Position] = Field(default_factory=list)
    realized_pnl_today: float = 0.0
    trading_halted: bool = False

    def position_for(self, symbol: str) -> Position | None:
        return next((p for p in self.open_positions if p.symbol == symbol), None)

    def exposure(self) -> float:
        return sum(p.market_value for p in self.open_positions)

    def sector_exposure(self, sector: str) -> float:
        return sum(p.market_value for p in self.open_positions if p.sector == sector)


class RiskDecision(BaseModel):
    """The risk engine's verdict on a TradeIntent."""

    approved: bool
    reason: str
    qty: int = 0
    entry_price: float = 0.0
    stop_price: float = 0.0
    take_profit_price: float | None = None
    risk_amount: float = 0.0  # dollars at risk if stop is hit
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrderResult(BaseModel):
    """Outcome of submitting an order to the broker (or a dry-run echo)."""

    symbol: str
    qty: int
    submitted: bool
    dry_run: bool
    broker_order_id: str | None = None
    detail: str = ""
