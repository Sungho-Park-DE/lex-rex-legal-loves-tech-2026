"""`cache/llm/` — the demo replays from here (contract §9).

Two reasons this exists beyond saving money: a demo must not depend on a
conference wifi and a provider's p99, and a golden test is only a test if the
same input gives the same output. Cached and live runs go through exactly the
same validators, so replay is not a weaker path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fallpruefer.adapter.basis import Aufruf, cache_name
from fallpruefer.konfig import WURZEL


class CacheFehlt(RuntimeError):
    """Cache-only mode and nothing recorded for this input."""

    def __init__(self, pfad: Path, eingabe: dict[str, Any]) -> None:
        self.pfad = pfad
        self.eingabe = eingabe
        super().__init__(
            f"Kein Cache-Eintrag: {pfad.name}\n"
            f"  (cache-only Modus — entweder ANTHROPIC_API_KEY setzen oder\n"
            f"   die Datei anlegen: {pfad})"
        )


def cache_verzeichnis() -> Path:
    p = WURZEL / "cache" / "llm"
    p.mkdir(parents=True, exist_ok=True)
    return p


def pfad_fuer(aufgabe: str, modell: str, prompt_version: str, eingabe: dict[str, Any]) -> Path:
    return cache_verzeichnis() / cache_name(aufgabe, modell, prompt_version, eingabe)


def lesen(pfad: Path) -> Aufruf | None:
    if not pfad.exists():
        return None
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    daten["aus_cache"] = True
    return Aufruf.model_validate(daten)


def schreiben(pfad: Path, aufruf: Aufruf) -> None:
    daten = aufruf.model_dump(mode="json")
    daten["aus_cache"] = False  # this file records a live run
    pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
