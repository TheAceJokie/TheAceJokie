"""Strategies that turn candidates into trade intents.

Phase 0 uses a deterministic baseline so the whole pipeline runs end-to-end
before any LLM is involved. From phase 2 the LLM agents produce intents instead.
"""

from .baseline import baseline_intent

__all__ = ["baseline_intent"]
