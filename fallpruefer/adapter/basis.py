"""The LLM adapter — its four tasks, its output shapes, and its validators.

The layer boundary (14 §3) in one file: the model does exactly three things
here — say what a document is, pull declared fields out of it with a quote,
and propose a Fallgruppe. It never decides an Einordnung, a remedy, a deadline
or a sentence in a letter.

Every output passes a deterministic validator before it becomes a fact:

  classify_doc      value ∈ enum; konfidenz < 0.6 → sonstiges + advisor confirm
  extract_fields    quote must be a substring of the pseudonymised page, in
                    normalised space; type must parse; a `zitat_pflicht` field
                    without a quote is FEHLT, not a value. A `false` still has
                    to carry the span that was examined — "I looked here and
                    found nothing" is evidence; "no" on its own is not.
  propose_fallgruppe ids ∈ taxonomy; quotes verified; the advisor decides.

A field that fails validation does not become a weaker fact. It becomes no
fact at all, and the Prüfpunkt goes FEHLT.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from fallpruefer import zeit
from fallpruefer.fall import Faktum, Quellenangabe, SeiteText
from fallpruefer.schema import Feld
from fallpruefer.text import enthaelt
from fallpruefer.vokabular import Badge, Dokumenttyp, Herkunft

KONFIDENZ_SCHWELLE = 0.6


# --------------------------------------------------------------------------
# what the model is asked to return
# --------------------------------------------------------------------------


class Klassifikation(BaseModel):
    dokumenttyp: str
    konfidenz: float = 0.0
    begruendung: str = ""


class FeldTreffer(BaseModel):
    feld_id: str
    wert: Any = None
    zitat: str | None = None
    seite: int | None = None


class Extraktion(BaseModel):
    felder: list[FeldTreffer] = Field(default_factory=list)


class FallgruppenTreffer(BaseModel):
    fallgruppe_id: str
    begruendung: str = ""
    zitate: list[str] = Field(default_factory=list)


class Vorschlaege(BaseModel):
    vorschlaege: list[FallgruppenTreffer] = Field(default_factory=list)


class Aufruf(BaseModel):
    """One adapter call, as it is cached (contract §9)."""

    aufgabe: str
    modell: str
    prompt_version: str
    eingabe: dict[str, Any]
    ausgabe: dict[str, Any] = Field(default_factory=dict)
    dauer_ms: int = 0
    kosten_cent: float = 0.0
    zeit: str | None = None
    aus_cache: bool = True


def eingabe_hash(daten: dict[str, Any]) -> str:
    roh = json.dumps(daten, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()[:16]


def cache_name(aufgabe: str, modell: str, prompt_version: str, daten: dict[str, Any]) -> str:
    modell_kurz = modell.replace("/", "-")
    return f"{aufgabe}_{modell_kurz}_{prompt_version}_{eingabe_hash(daten)}.json"


# --------------------------------------------------------------------------
# the adapter interface
# --------------------------------------------------------------------------


class LLMAdapter(ABC):
    @abstractmethod
    def classify_doc(self, seiten: list[SeiteText]) -> tuple[Klassifikation, Aufruf]: ...

    @abstractmethod
    def extract_fields(
        self, seiten: list[SeiteText], felder: list[Feld], dokumenttyp: str
    ) -> tuple[Extraktion, Aufruf]: ...

    @abstractmethod
    def propose_fallgruppe(
        self, freitext: str, doktypen: list[str], taxonomie: dict[str, dict]
    ) -> tuple[Vorschlaege, Aufruf]: ...


# --------------------------------------------------------------------------
# validators — these run on every adapter, live or cached
# --------------------------------------------------------------------------


def validiere_klassifikation(k: Klassifikation) -> tuple[Dokumenttyp, bool]:
    """Returns the type and whether the advisor has to confirm it."""
    try:
        typ = Dokumenttyp(k.dokumenttyp)
    except ValueError:
        return Dokumenttyp.SONSTIGES, True
    if k.konfidenz < KONFIDENZ_SCHWELLE:
        return Dokumenttyp.SONSTIGES, True
    return typ, False


def _wert_parsen(wert: Any, spec: Feld) -> Any:
    """Type parse per the field spec. Returns None when it does not parse —
    a value the schema cannot use is not a value."""
    if wert is None:
        return None
    typ = spec.typ
    if typ == "datum":
        return zeit.parse_datum(wert)
    if typ in ("betrag", "zahl"):
        if isinstance(wert, bool):
            return None
        # `zeit.parse_betrag` is the one amount parser: it strips „€"/„EUR"
        # and treats „." as a thousands separator **only when a comma is also
        # present**. This function used to carry a second, cruder copy that
        # dropped every dot unconditionally — so the „29.90" the live prompt
        # asks for became 2 990,00 €, while „29,90 EUR", which is how the demo
        # documents actually write it, was dropped entirely. Two parsers for
        # one format is how the two disagreed for as long as every test
        # replayed a hand-written German-comma cache.
        zahl = zeit.parse_betrag(wert)
        if zahl is None:
            return None
        return int(zahl) if typ == "zahl" and zahl.is_integer() else zahl
    if typ == "bool":
        if isinstance(wert, bool):
            return wert
        s = str(wert).strip().lower()
        if s in ("true", "ja", "yes", "1"):
            return True
        if s in ("false", "nein", "no", "0"):
            return False
        return None
    if typ == "enum":
        s = str(wert).strip()
        return s if (spec.werte and s in spec.werte) else None
    if typ == "liste_text":
        if isinstance(wert, list):
            return [str(w) for w in wert]
        # live convention: semicolon-separated, empty string = empty list
        text = str(wert).strip()
        if not text or text.lower() in ("keine", "-", "[]"):
            return []
        return [t.strip() for t in text.split(";") if t.strip()]
    if typ == "liste_betrag_datum":
        return wert if isinstance(wert, list) else None
    return str(wert)


def validiere_extraktion(
    extraktion: Extraktion,
    felder: list[Feld],
    seiten: list[SeiteText],
    dok_id: str,
    llm_run: str | None = None,
) -> tuple[list[Faktum], list[str]]:
    """Turn raw extraction into facts. Returns (facts, rejected feld_ids)."""
    specs = {f.feld_id: f for f in felder}
    seiten_text = {s.nr: (s.text_pseudonym or s.text_original) for s in seiten}
    fakten: list[Faktum] = []
    verworfen: list[str] = []

    for treffer in extraktion.felder:
        spec = specs.get(treffer.feld_id)
        if spec is None:
            verworfen.append(treffer.feld_id)
            continue

        wert = _wert_parsen(treffer.wert, spec)
        # V-L1: „geprüft, nicht enthalten" ist ein Befund, kein Müll. Ein
        # Textfeld darf `null` antworten, WENN ein Zitat sagt, wo gesucht
        # wurde — das Zitat wird wie jedes andere gegen die Seite verifiziert.
        # Ohne Zitat bleibt `null` das, was es war: verworfen.
        geprueft_leer = (
            spec.typ == "text" and treffer.wert is None and bool((treffer.zitat or "").strip())
        )
        if wert is None and not geprueft_leer and not (spec.typ == "liste_text" and treffer.wert == []):
            verworfen.append(treffer.feld_id)
            continue

        zitat = (treffer.zitat or "").strip()
        if spec.zitat_pflicht and not zitat:
            # a bool `false` still has to carry the span that was examined
            verworfen.append(treffer.feld_id)
            continue

        quelle = None
        verifiziert: bool | None = None
        if zitat:
            seite = treffer.seite if treffer.seite in seiten_text else None
            if seite is None:
                seite = next((nr for nr, t in seiten_text.items() if enthaelt(t, zitat)), None)
            verifiziert = seite is not None and enthaelt(seiten_text[seite], zitat)
            if not verifiziert:
                verworfen.append(treffer.feld_id)
                continue
            quelle = Quellenangabe(dok_id=dok_id, seite=seite, zitat_pseudonym=zitat)

        fakten.append(Faktum(
            feld_id=treffer.feld_id, wert=wert, dok_id=dok_id,
            herkunft=Herkunft.EXPLIZIT, quelle=quelle, verifiziert=verifiziert,
            badge=Badge.VERIFIZIERT if verifiziert else Badge.ANGENOMMEN,
            llm_run=llm_run,
        ))

    _widersprueche_markieren(fakten)
    return fakten, verworfen


def _widersprueche_markieren(fakten: list[Faktum]) -> None:
    """Two verified quotes, two different values for the same field.

    Contract §9 defines `herkunft: strittig` for exactly this and nothing set
    it, so the engine took whichever fact happened to be appended last
    (`evaluator._faktum` ends `return kandidaten[-1]`) — on a real case that
    silently turned `wirksam` into `wahrscheinlich unwirksam` with nothing on
    screen to say a document had contradicted itself. That is the failure mode
    the whole quote verification exists to prevent.

    A contradiction is marked, not resolved: `verifiziert=False` makes the
    Prüfpunkt fall to FEHLT and name the field, and the red „widersprüchlich
    belegt" chip says why. Which of the two readings is right is a judgement,
    and judgements belong to the advisor at Gate 3.
    """
    nach_feld: dict[str, list[Faktum]] = {}
    for f in fakten:
        nach_feld.setdefault(f.feld_id, []).append(f)
    for gruppe in nach_feld.values():
        if len(gruppe) < 2 or len({str(f.wert) for f in gruppe}) < 2:
            continue
        for f in gruppe:
            f.herkunft = Herkunft.STRITTIG
            f.verifiziert = False
            f.badge = Badge.NICHT_GEFUNDEN


def validiere_vorschlaege(
    v: Vorschlaege, taxonomie: dict[str, dict], seiten_text: str
) -> list[FallgruppenTreffer]:
    gueltig: list[FallgruppenTreffer] = []
    for t in v.vorschlaege:
        if t.fallgruppe_id not in taxonomie:
            continue
        t.zitate = [z for z in t.zitate if enthaelt(seiten_text, z)]
        gueltig.append(t)
    return gueltig[:3]
