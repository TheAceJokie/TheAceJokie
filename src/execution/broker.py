"""Broker wrapper around Alpaca's trading API.

This is the ONLY layer that touches broker credentials. The LLM never reaches
here — it produces intents, the risk engine approves a sized decision, and only
then does this layer submit a bracket order (or echo it in dry-run mode).
"""

from __future__ import annotations

from src.config import Settings
from src.models import OrderResult, PortfolioState, Position, RiskDecision


class Broker:
    def __init__(self, settings: Settings, sector_of=None) -> None:
        self._settings = settings
        self._sector_of = sector_of or (lambda _s: "UNKNOWN")
        from alpaca.trading.client import TradingClient

        self._client = TradingClient(
            settings.alpaca_api_key,
            settings.alpaca_secret_key,
            paper=settings.is_paper,
        )

    def portfolio_state(self) -> PortfolioState:
        """Read live account state into the model the risk engine understands."""
        account = self._client.get_account()
        positions = [
            Position(
                symbol=p.symbol,
                qty=float(p.qty),
                avg_entry_price=float(p.avg_entry_price),
                sector=self._sector_of(p.symbol),
            )
            for p in self._client.get_all_positions()
        ]
        return PortfolioState(
            equity=float(account.equity),
            buying_power=float(account.buying_power),
            open_positions=positions,
            realized_pnl_today=0.0,  # wired from the day's fills in a later phase
            trading_halted=account.trading_blocked or account.account_blocked,
        )

    def submit_bracket(self, decision: RiskDecision, symbol: str) -> OrderResult:
        """Submit a bracket order (entry + stop + target) for an approved decision.

        In dry-run mode nothing is sent — we just report what would happen.
        """
        if not decision.approved:
            return OrderResult(
                symbol=symbol, qty=0, submitted=False,
                dry_run=self._settings.dry_run,
                detail=f"not approved: {decision.reason}",
            )

        if self._settings.dry_run:
            return OrderResult(
                symbol=symbol, qty=decision.qty, submitted=False, dry_run=True,
                detail=(
                    f"DRY RUN: BUY {decision.qty} {symbol} @ {decision.entry_price} "
                    f"stop {decision.stop_price} target {decision.take_profit_price} "
                    f"(risk ${decision.risk_amount:.0f})"
                ),
            )

        from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
        from alpaca.trading.requests import (
            LimitOrderRequest,
            StopLossRequest,
            TakeProfitRequest,
        )

        request = LimitOrderRequest(
            symbol=symbol,
            qty=decision.qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            limit_price=decision.entry_price,
            order_class=OrderClass.BRACKET,
            take_profit=(
                TakeProfitRequest(limit_price=decision.take_profit_price)
                if decision.take_profit_price
                else None
            ),
            stop_loss=StopLossRequest(stop_price=decision.stop_price),
        )
        order = self._client.submit_order(request)
        return OrderResult(
            symbol=symbol, qty=decision.qty, submitted=True, dry_run=False,
            broker_order_id=str(order.id),
            detail=f"submitted bracket order {order.id}",
        )
