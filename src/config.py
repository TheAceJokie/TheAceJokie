"""Configuration: risk limits (tunable) and secrets (from environment).

Secrets are loaded from environment / .env and are NEVER hardcoded or logged.
Risk limits live here as data so they can be reviewed, version-controlled, and
unit-tested independently of any live key.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RiskLimits(BaseModel):
    """Hard, code-enforced risk parameters. The LLM cannot override these.

    Defaults are deliberately conservative. Tune them here, not in business code.
    """

    # Fraction of equity risked on a single trade (distance entry->stop). 1%.
    max_risk_per_trade_pct: float = Field(default=0.01, gt=0, le=0.05)
    # Cap any single position's market value as a fraction of equity.
    max_position_pct: float = Field(default=0.20, gt=0, le=1.0)
    # Cap total invested exposure as a fraction of equity (1.0 = no margin).
    max_total_exposure_pct: float = Field(default=1.0, gt=0, le=2.0)
    # Cap exposure to any single sector.
    max_sector_pct: float = Field(default=0.40, gt=0, le=1.0)
    # Maximum number of concurrent open positions.
    max_open_positions: int = Field(default=5, ge=1)
    # Daily realized-loss limit as a fraction of equity. Breach -> kill switch.
    daily_loss_limit_pct: float = Field(default=0.03, gt=0, le=0.20)
    # Minimum model confidence required to consider a trade at all.
    min_confidence: float = Field(default=0.60, ge=0.0, le=1.0)
    # Stop must be at least this far from entry (avoids noise-tight stops)...
    min_stop_distance_pct: float = Field(default=0.005, gt=0, le=0.10)
    # ...and no further than this (avoids absurd risk per share).
    max_stop_distance_pct: float = Field(default=0.20, gt=0, le=0.50)


class Settings(BaseSettings):
    """Secrets and runtime flags, loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    anthropic_api_key: str = ""
    # Dry run: never submit real orders, just log what would happen.
    dry_run: bool = True

    @property
    def is_paper(self) -> bool:
        return "paper" in self.alpaca_base_url.lower()


def load_settings() -> Settings:
    return Settings()
