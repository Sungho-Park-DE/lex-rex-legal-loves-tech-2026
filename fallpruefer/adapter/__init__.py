"""Adapter selection — one place, so no caller ever knows which one it got.

Without `ANTHROPIC_API_KEY` (or with `llm.nur_cache`) the program runs
cache-only and quietly: an offline machine is a normal state for this build,
not an error. `14 §3`: swapping the model changes neither Einordnung nor
letters, so which adapter answered is a footnote, not a branch.
"""

from __future__ import annotations

import os

from fallpruefer.adapter.basis import (  # noqa: F401  (re-exported)
    Aufruf,
    Extraktion,
    FallgruppenTreffer,
    FeldTreffer,
    Klassifikation,
    LLMAdapter,
    Vorschlaege,
    validiere_extraktion,
    validiere_klassifikation,
    validiere_vorschlaege,
)
from fallpruefer.adapter.cache_adapter import CacheAdapter
from fallpruefer.konfig import konfig


def live_moeglich() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY")) and not konfig().llm.nur_cache


def adapter_holen(live: bool | None = None) -> LLMAdapter:
    nutze_live = live_moeglich() if live is None else live
    if nutze_live:
        from fallpruefer.adapter.anthropic_adapter import AnthropicAdapter

        return AnthropicAdapter()
    return CacheAdapter()
