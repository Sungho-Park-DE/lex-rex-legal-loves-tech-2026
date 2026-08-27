"""`config.json` (contract 15 §10), loaded once.

Nothing else in the program reads the file; everything imports `konfig()`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

WURZEL = Path(__file__).resolve().parent.parent


class LLMKonfig(BaseModel):
    adapter: str = "anthropic"
    modell_klassifikation: str
    modell_extraktion: str
    prompt_version: str = "p1"
    # Effort fuer die Opus-Aufgaben (extract_fields, propose_fallgruppe).
    # None = Voreinstellung des Modells (`high`). Nie fuer classify_doc:
    # Haiku 4.5 beantwortet den Parameter mit 400. Der Cache-Schluessel
    # kennt den Effort nicht -- der Knopf ist fuer Live-Laeufe mit
    # cache_lesen=False gedacht (tools/live_diff.py --effort, 31 par. 4).
    effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None
    cache: bool = True
    # true → never call the provider, replay from cache/llm only
    nur_cache: bool = False
    vertragsbedingungen: dict[str, str] = Field(default_factory=dict)


class RadarKonfig(BaseModel):
    schwelle_beschwerden: int = 30
    schwelle_beratungen: int = 15
    k_min: int = 3


class PseudoKonfig(BaseModel):
    token_syntax: str = "@@TYP_N@@"
    quellen: list[str] = Field(default_factory=list)
    whitelist: list[str] = Field(default_factory=list)
    ner: bool = False
    sensible_keywords: list[str] = Field(default_factory=list)


class Konfig(BaseModel):
    demo_stichtag: str
    stichtag_modus: str = "demo"
    llm: LLMKonfig
    normbasis_modus: str = "dev"
    radar: RadarKonfig = Field(default_factory=RadarKonfig)
    platzhalter_regex: str = r"\[[A-Z0-9_]+\]"
    antwortfrist_tage: int = 14
    pseudonymisierung: PseudoKonfig = Field(default_factory=PseudoKonfig)
    log_akteur: str = "rolle"
    aufbewahrung_tage: dict[str, int | None] = Field(default_factory=dict)
    store_pfad: str = "store/faelle.jsonl"
    hmac_secret_env: str = "FP_HMAC_SECRET"
    texte: dict[str, str] = Field(default_factory=dict)
    # The six published FWN flag criteria (vzbv), verbatim — config, not code,
    # so nobody is tempted to invent a seventh (10 §, „no invented taxonomy").
    referat_kriterien: list[dict[str, str]] = Field(default_factory=list)
    referat_hinweis: str | None = None

    @property
    def wurzel(self) -> Path:
        return WURZEL


@lru_cache(maxsize=1)
def konfig(pfad: Path | None = None) -> Konfig:
    p = pfad or (WURZEL / "config.json")
    return Konfig.model_validate(json.loads(p.read_text(encoding="utf-8")))
