"""Entry point: run a single trading cycle.

Usage:
    python run.py

Reads keys from .env. Defaults to DRY_RUN=true and the Alpaca paper endpoint —
no real orders are sent until you explicitly change both.
"""

from __future__ import annotations

import logging

from src.config import load_settings
from src.orchestrator import run_once


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = load_settings()
    mode = "DRY RUN" if settings.dry_run else "LIVE ORDERS"
    market = "PAPER" if settings.is_paper else "REAL MONEY"
    logging.getLogger("run").info("starting cycle — %s on %s", mode, market)
    run_once(settings)


if __name__ == "__main__":
    main()
