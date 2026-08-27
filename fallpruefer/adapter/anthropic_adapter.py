"""The live adapter — Anthropic, structured output, recorded to cache.

It subclasses the cache adapter on purpose: request shaping, cache keys and
validators are shared, so a live recording replays byte-identically and the
demo never depends on the venue's wifi. A live call happens only on a cache
miss; the result is written back at the same key.

The layer boundary is enforced by what this file *cannot* express. There is no
prompt here that asks whether a clause is valid, what the deadline is, or which
letter to send. The model is asked three questions only: what is this document,
what do these declared fields say and where exactly does each answer stand, and
which Fallgruppe does this sound like. Everything else is `evaluator.py`.

Every extraction answer must carry a verbatim span. That is not a nicety — the
validator drops any field whose quote is not a substring of the pseudonymised
page, so an invented value cannot become a fact.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from pydantic import BaseModel, Field

from fallpruefer.adapter import cache
from fallpruefer.adapter.basis import Aufruf
from fallpruefer.adapter.cache_adapter import CacheAdapter
from fallpruefer.vokabular import Dokumenttyp

# Anthropic list price per 1M tokens (skill cache 2026-06-24). Only used for
# the „Betriebskosten dieses Falls" line in the Fallakte footer — an honest
# order of magnitude for the jury, not an invoice.
PREISE: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

MAX_TOKENS = 16000


# --------------------------------------------------------------------------
# what the model is asked to return (JSON schema is derived from these)
# --------------------------------------------------------------------------


class LiveKlassifikation(BaseModel):
    dokumenttyp: Dokumenttyp
    konfidenz: float = Field(ge=0.0, le=1.0)
    begruendung: str


class LiveFeld(BaseModel):
    feld_id: str
    # Always as text — the deterministic validator parses it against the field
    # spec's `typ`. Letting the model pick a JSON type invites a date that is
    # sometimes a string and sometimes an object.
    wert: str | None
    # The verbatim span this value stands on. A field without one is dropped.
    zitat: str | None
    seite: int | None


class LiveExtraktion(BaseModel):
    felder: list[LiveFeld]


class LiveVorschlag(BaseModel):
    fallgruppe_id: str
    begruendung: str
    zitate: list[str]


class LiveVorschlaege(BaseModel):
    vorschlaege: list[LiveVorschlag]


# --------------------------------------------------------------------------
# prompts — deliberately narrow
# --------------------------------------------------------------------------

SYSTEM_KLASSIFIKATION = """\
Du bist ein Klassifikator für Dokumente aus der Verbraucherberatung.
Du bestimmst ausschließlich den Dokumenttyp. Du bewertest nichts rechtlich.

Gib den Typ aus der vorgegebenen Liste zurück, eine Konfidenz zwischen 0 und 1
und einen kurzen Satz, woran du den Typ erkennst.
Wenn du unsicher bist, gib eine niedrige Konfidenz an — ein ehrliches
„unsicher" ist nützlich, ein geratener Typ ist schädlich."""

SYSTEM_EXTRAKTION = """\
Du liest ein Dokument aus der Verbraucherberatung und füllst eine vorgegebene
Feldliste. Du bewertest nichts rechtlich und ziehst keine Schlüsse.

Regeln:
1. Fülle nur Felder aus der Liste. Erfinde keine Feld-IDs.
2. Zu JEDEM Feld gehört `zitat`: eine WÖRTLICHE, zusammenhängende Textstelle
   aus dem Dokument, Zeichen für Zeichen. Kürze nicht, glätte nicht, fasse
   nicht zusammen. Ein Zitat, das so nicht im Dokument steht, führt dazu, dass
   das Feld verworfen wird.
3. Auch ein `false` oder ein „nein" braucht ein Zitat: die Stelle, die du
   geprüft hast und an der die Angabe fehlt oder verneint wird.
4. `seite` ist die Seitenzahl, auf der das Zitat steht.
5. Findest du ein Feld nicht, lass es weg. Rate nicht.
6. Werte als Text: Datum als YYYY-MM-DD, Beträge so wie im Dokument, also mit
   Komma als Dezimaltrennzeichen (z. B. 29,90 — nicht 29.90); Währungszeichen
   dürfen stehen bleiben. bool als true/false, enum exakt einer der erlaubten
   Werte, Listen mit Semikolon getrennt (leere Liste = leerer String).
7. Der Text enthält Platzhalter der Form @@PERSON_1@@ oder @@ADRESSE_2@@.
   Das sind pseudonymisierte Identitäten. Lass sie unverändert stehen."""

SYSTEM_FALLGRUPPE = """\
Du ordnest die Schilderung eines Verbraucheranliegens einer Fallgruppe zu.
Du bewertest nichts rechtlich; die Beraterin entscheidet.

Regeln:
1. Nur IDs aus der vorgegebenen Taxonomie. Erfinde keine.
2. Höchstens drei Vorschläge, der wahrscheinlichste zuerst.
3. `zitate` sind WÖRTLICHE Textstellen aus der Schilderung, Zeichen für
   Zeichen. Ein Zitat, das so nicht dasteht, wird verworfen.
4. Passt nichts, gib eine leere Liste zurück."""


class AnthropicAdapter(CacheAdapter):
    def __init__(self, cache_lesen: bool = True) -> None:
        super().__init__()
        import anthropic

        # `cache_lesen=False` forces a real call even when a recording exists —
        # that is how the replay-equivalence test proves the cache is faithful.
        self.cache_lesen = cache_lesen
        self._client = anthropic.Anthropic()

    # -- cache first, live on miss -----------------------------------------

    def _hole(self, aufgabe: str, modell: str, eingabe: dict[str, Any]) -> Aufruf:
        pfad = cache.pfad_fuer(aufgabe, modell, self.k.prompt_version, eingabe)
        if self.k.cache and self.cache_lesen and (treffer := cache.lesen(pfad)) is not None:
            return treffer

        aufruf = self._live(aufgabe, modell, eingabe)
        if self.k.cache and self.cache_lesen:
            cache.schreiben(pfad, aufruf)
        return aufruf

    def _live(self, aufgabe: str, modell: str, eingabe: dict[str, Any]) -> Aufruf:
        bauer = {
            "classify_doc": self._prompt_klassifikation,
            "extract_fields": self._prompt_extraktion,
            "propose_fallgruppe": self._prompt_fallgruppe,
        }[aufgabe]
        system, nachricht, modell_klasse = bauer(eingabe)

        start = time.monotonic()
        antwort = self._client.messages.parse(
            model=modell,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": nachricht}],
            output_format=modell_klasse,
            **self._ausgabe_konfig(aufgabe),
        )
        dauer_ms = int((time.monotonic() - start) * 1000)

        if antwort.stop_reason == "refusal":
            raise RuntimeError(
                f"{aufgabe}: Anfrage abgelehnt "
                f"({getattr(antwort.stop_details, 'category', 'ohne Angabe')})"
            )

        ausgabe = self._nachbereiten(aufgabe, antwort.parsed_output, eingabe)
        return Aufruf(
            aufgabe=aufgabe, modell=modell, prompt_version=self.k.prompt_version,
            eingabe=eingabe, ausgabe=ausgabe, dauer_ms=dauer_ms,
            kosten_cent=kosten_cent(modell, antwort.usage), aus_cache=False,
        )

    def _ausgabe_konfig(self, aufgabe: str) -> dict[str, Any]:
        """`output_config.effort` nur dort, wo das Modell den Parameter kennt:
        bei den Opus-Aufgaben. `classify_doc` laeuft auf Haiku 4.5, das ihn mit
        400 beantwortet. Ohne gesetzten Effort bleibt der Aufruf, wie er immer
        war -- Voreinstellung `high`, adaptives Denken (Opus-5-Semantik)."""
        if self.k.effort and aufgabe != "classify_doc":
            return {"output_config": {"effort": self.k.effort}}
        return {}

    # -- request shaping ----------------------------------------------------

    @staticmethod
    def _seitentext(eingabe: dict[str, Any]) -> str:
        return "\n\n".join(
            f"<seite nr=\"{s['nr']}\">\n{s['text']}\n</seite>" for s in eingabe["seiten"]
        )

    def _prompt_klassifikation(self, eingabe: dict[str, Any]):
        typen = ", ".join(t.value for t in Dokumenttyp)
        nachricht = (
            f"Erlaubte Dokumenttypen: {typen}\n\n"
            f"Dokument:\n{self._seitentext(eingabe)}"
        )
        return SYSTEM_KLASSIFIKATION, nachricht, LiveKlassifikation

    def _prompt_extraktion(self, eingabe: dict[str, Any]):
        felder = json.dumps(eingabe["felder"], ensure_ascii=False, indent=1)
        nachricht = (
            f"Dokumenttyp: {eingabe['dokumenttyp']}\n\n"
            f"Zu füllende Felder:\n{felder}\n\n"
            f"Dokument:\n{self._seitentext(eingabe)}"
        )
        return SYSTEM_EXTRAKTION, nachricht, LiveExtraktion

    def _prompt_fallgruppe(self, eingabe: dict[str, Any]):
        nachricht = (
            f"Taxonomie (erlaubte IDs): {', '.join(eingabe['taxonomie'])}\n"
            f"Eingereichte Dokumenttypen: {', '.join(eingabe['doktypen']) or 'keine'}\n\n"
            f"Schilderung:\n{eingabe['freitext']}"
        )
        return SYSTEM_FALLGRUPPE, nachricht, LiveVorschlaege

    # -- shape the answer like a cached one --------------------------------

    @staticmethod
    def _nachbereiten(
        aufgabe: str, geparst: BaseModel, eingabe: dict[str, Any]
    ) -> dict[str, Any]:
        """Shape the answer like a cached one.

        The only transformation here is the list convention from the prompt
        („Listen mit Semikolon getrennt"), and it is applied ONLY to fields the
        Soll declares as `liste_text`. It used to be applied to every string
        containing a semicolon, which is wrong for the same reason the amount
        parser was wrong: a post-processing rule that does not know the field
        spec. German prose contains semicolons, so a `typ: text` answer got
        split into a list, and `_wert_parsen` then turned that list back into a
        string with `str()` — leaving a Python repr, „['Keine Preisklausel im
        Vertragstext', 'nur Hinweis auf Ziffer 6']", as the value of a field
        that is interpolated into the trace and into letters.

        Found by the first live run (`tools/live_diff.py`, B1): three fields
        across two cases, all of them `typ: text`. No test could see it,
        because every test replayed hand-written cache that never had a
        semicolon in it.
        """
        daten = geparst.model_dump(mode="json")
        if aufgabe != "extract_fields":
            return daten
        # `eingabe` is required, not defaulted: a default of None would make
        # this silently stop splitting genuine `liste_text` answers for any
        # future caller — the same shape of silent failure as the bug above.
        listen = {
            f["feld_id"]
            for f in eingabe.get("felder", [])
            if f.get("typ") == "liste_text"
        }
        for f in daten["felder"]:
            if f.get("feld_id") in listen and isinstance(f.get("wert"), str):
                # empty string = empty list, per the prompt
                f["wert"] = [t.strip() for t in f["wert"].split(";") if t.strip()]
        return daten


def kosten_cent(modell: str, usage: Any) -> float:
    """List price for one call, in cents. Cache reads are ~0.1x, writes ~1.25x."""
    ein, aus = PREISE.get(modell, (0.0, 0.0))
    eingabe_tokens = getattr(usage, "input_tokens", 0) or 0
    ausgabe_tokens = getattr(usage, "output_tokens", 0) or 0
    cache_lesen = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_schreiben = getattr(usage, "cache_creation_input_tokens", 0) or 0
    dollar = (
        eingabe_tokens * ein
        + cache_lesen * ein * 0.1
        + cache_schreiben * ein * 1.25
        + ausgabe_tokens * aus
    ) / 1_000_000
    return round(dollar * 100, 4)


def schluessel_vorhanden() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))
