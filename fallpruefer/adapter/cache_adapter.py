"""Cache-only adapter — replays `cache/llm/`, never calls a provider.

This is the default until `ANTHROPIC_API_KEY` is set, and the mode the demo
runs in. It shares the request shaping with the live adapter so a recording
made live replays byte-identically here.
"""

from __future__ import annotations

from typing import Any

from fallpruefer.adapter import cache
from fallpruefer.adapter.basis import (
    Aufruf,
    Extraktion,
    Klassifikation,
    LLMAdapter,
    Vorschlaege,
)
from fallpruefer.fall import SeiteText
from fallpruefer.konfig import konfig
from fallpruefer.schema import Feld


def seiten_eingabe(seiten: list[SeiteText]) -> list[dict[str, Any]]:
    """Only `text_pseudonym` ever leaves the machine (contract §4)."""
    return [{"nr": s.nr, "text": s.text_pseudonym or s.text_original} for s in seiten]


def feld_eingabe(felder: list[Feld]) -> list[dict[str, Any]]:
    return [
        {
            "feld_id": f.feld_id,
            "typ": f.typ,
            "werte": f.werte,
            "beschreibung": f.beschreibung,
            "zitat_pflicht": f.zitat_pflicht,
            "pflicht": f.pflicht,
        }
        for f in felder
    ]


class CacheAdapter(LLMAdapter):
    def __init__(self, strikt: bool = True) -> None:
        self.strikt = strikt
        self.k = konfig().llm

    # -- shared plumbing ----------------------------------------------------

    def _hole(self, aufgabe: str, modell: str, eingabe: dict[str, Any]) -> Aufruf:
        pfad = cache.pfad_fuer(aufgabe, modell, self.k.prompt_version, eingabe)
        treffer = cache.lesen(pfad)
        if treffer is None:
            raise cache.CacheFehlt(pfad, eingabe)
        return treffer

    # -- the three tasks ----------------------------------------------------

    def classify_doc(self, seiten: list[SeiteText]) -> tuple[Klassifikation, Aufruf]:
        eingabe = {"seiten": seiten_eingabe(seiten)}
        aufruf = self._hole("classify_doc", self.k.modell_klassifikation, eingabe)
        return Klassifikation.model_validate(aufruf.ausgabe), aufruf

    def extract_fields(
        self, seiten: list[SeiteText], felder: list[Feld], dokumenttyp: str
    ) -> tuple[Extraktion, Aufruf]:
        eingabe = {
            "dokumenttyp": dokumenttyp,
            "seiten": seiten_eingabe(seiten),
            "felder": feld_eingabe(felder),
        }
        aufruf = self._hole("extract_fields", self.k.modell_extraktion, eingabe)
        return Extraktion.model_validate(aufruf.ausgabe), aufruf

    def propose_fallgruppe(
        self, freitext: str, doktypen: list[str], taxonomie: dict[str, dict]
    ) -> tuple[Vorschlaege, Aufruf]:
        eingabe = {
            "freitext": freitext,
            "doktypen": sorted(doktypen),
            "taxonomie": sorted(taxonomie),
        }
        aufruf = self._hole("propose_fallgruppe", self.k.modell_extraktion, eingabe)
        return Vorschlaege.model_validate(aufruf.ausgabe), aufruf
