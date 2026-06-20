"""The deterministic risk engine.

This is the single point that turns a *proposed* TradeIntent into an approved,
precisely-sized order — or vetoes it. It has the final word over any AI decision.

Design rules:
- Default to inaction: anything ambiguous or limit-breaching is rejected.
- All sizing math happens here, in code — never in an LLM.
- Pure and side-effect-free, so it is fully unit-testable without network/broker.
"""

from __future__ import annotations

import math

from src.config import RiskLimits
from src.models import PortfolioState, RiskDecision, Side, TradeIntent


class RiskEngine:
    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def evaluate(self, intent: TradeIntent, portfolio: PortfolioState) -> RiskDecision:
        """Return an approved, sized RiskDecision or a rejection with a reason."""
        lim = self.limits

        # --- Hard gates (reject outright) ------------------------------------
        if portfolio.trading_halted:
            return self._reject("trading is halted (kill switch active)")

        # Daily loss limit acts as an automatic kill switch.
        loss_limit = -lim.daily_loss_limit_pct * portfolio.equity
        if portfolio.realized_pnl_today <= loss_limit:
            return self._reject(
                f"daily loss limit reached "
                f"({portfolio.realized_pnl_today:.2f} <= {loss_limit:.2f})"
            )

        if intent.side is not Side.BUY:
            return self._reject("phase 0 is long-only; only BUY entries are sized")

        if intent.confidence < lim.min_confidence:
            return self._reject(
                f"confidence {intent.confidence:.2f} < min {lim.min_confidence:.2f}"
            )

        # No pyramiding in phase 0: skip symbols we already hold.
        if portfolio.position_for(intent.symbol) is not None:
            return self._reject(f"already holding {intent.symbol}")

        if len(portfolio.open_positions) >= lim.max_open_positions:
            return self._reject(
                f"max open positions reached ({lim.max_open_positions})"
            )

        # --- Stop geometry ----------------------------------------------------
        risk_per_share = intent.entry_price - intent.stop_price
        if risk_per_share <= 0:
            return self._reject("stop is not below entry")

        stop_dist_pct = risk_per_share / intent.entry_price
        if stop_dist_pct < lim.min_stop_distance_pct:
            return self._reject(
                f"stop too tight ({stop_dist_pct:.3%} < {lim.min_stop_distance_pct:.3%})"
            )
        if stop_dist_pct > lim.max_stop_distance_pct:
            return self._reject(
                f"stop too wide ({stop_dist_pct:.3%} > {lim.max_stop_distance_pct:.3%})"
            )

        # --- Position sizing: take the most restrictive of every limit -------
        # 1) Risk-per-trade: dollars risked = equity * max_risk_per_trade_pct.
        risk_dollars = portfolio.equity * lim.max_risk_per_trade_pct
        qty_by_risk = math.floor(risk_dollars / risk_per_share)

        # 2) Single-position cap.
        qty_by_position = math.floor(
            (portfolio.equity * lim.max_position_pct) / intent.entry_price
        )

        # 3) Remaining total exposure headroom.
        exposure_cap = portfolio.equity * lim.max_total_exposure_pct
        remaining_exposure = max(0.0, exposure_cap - portfolio.exposure())
        qty_by_exposure = math.floor(remaining_exposure / intent.entry_price)

        # 4) Remaining sector headroom.
        sector_cap = portfolio.equity * lim.max_sector_pct
        remaining_sector = max(
            0.0, sector_cap - portfolio.sector_exposure(intent.sector)
        )
        qty_by_sector = math.floor(remaining_sector / intent.entry_price)

        # 5) Available buying power.
        qty_by_cash = math.floor(portfolio.buying_power / intent.entry_price)

        qty = min(
            qty_by_risk,
            qty_by_position,
            qty_by_exposure,
            qty_by_sector,
            qty_by_cash,
        )

        if qty <= 0:
            return self._reject(
                "sizing yields zero shares after applying limits "
                f"(risk={qty_by_risk}, pos={qty_by_position}, "
                f"exp={qty_by_exposure}, sector={qty_by_sector}, cash={qty_by_cash})"
            )

        return RiskDecision(
            approved=True,
            reason="approved",
            qty=qty,
            entry_price=intent.entry_price,
            stop_price=intent.stop_price,
            take_profit_price=intent.take_profit_price,
            risk_amount=qty * risk_per_share,
        )

    @staticmethod
    def _reject(reason: str) -> RiskDecision:
        return RiskDecision(approved=False, reason=reason)
