"""Gesprächsleitfaden — the questions the advisor asks, and what they fill.

Ladder rung 6 (14 §10). The last input channel: a case is not only documents.
Some of what decides a Prüfpunkt is never on paper — did you actively agree,
did you keep going to the studio, how many months have you paid the higher
fee, do you want the money back. `15` §2 already carries those as
`leitfaden_frage` on five Prüfpunkte and the engine already reads the fields
they fill; nothing produced them, so those rules were dead.

Two things this module is deliberately NOT:

* It is not a chatbot and not an intake form for the consumer. The advisor is
  on the phone or across the table; these are the questions worth asking, in
  the order they change something.
* It is not a way to write arbitrary facts. Only a `feld_id` that some
  `leitfaden_frage` in the loaded schema declares as `fuellt` can be set, and
  the value has to parse for the declared `typ`. The API is otherwise a
  fact-injection endpoint into a legal assessment.

An answer is a fact like any other: `herkunft: gespraech`, `badge: angenommen`
(what someone said is not a verified quote — the two-axis display carries that
honestly), and it triggers a re-run, so the verdict that follows names the
answer as its ground.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from fallpruefer import zeit
from fallpruefer.fall import Fall, Faktum
from fallpruefer.schema import Pruefpunkt, Schema
from fallpruefer.vokabular import Badge, Herkunft, Rolle, Zustand

# Status of a question, from the advisor's point of view.
OFFEN = "offen"                # worth asking — it can still change something
BEANTWORTET = "beantwortet"    # asked and answered in this case
ERUEBRIGT = "eruebrigt"        # the documents already say it
ENTFAELLT = "entfaellt"        # its Prüfpunkt is not in play at all

_TYPEN = ("ja_nein", "zahl", "mehrfach", "text")


class LeitfadenFehler(ValueError):
    """A rejected answer. The message is shown to the advisor."""


class Frage(BaseModel):
    pruefpunkt_id: str
    pruefpunkt_titel: str = ""
    text: str
    typ: str = "ja_nein"
    fuellt: list[str] = Field(default_factory=list)
    werte: dict[str, list[str]] = Field(default_factory=dict)
    # Was auf dem Schirm steht, wenn eine Frage mehrere Felder fuellt. Ohne
    # sie rendert die Anzeige die Feld-ID — „gespraech.strategie" stand so
    # auf allen drei Faellen (35 H4).
    feld_labels: dict[str, str] = Field(default_factory=dict)
    wert_labels: dict[str, dict[str, str]] = Field(default_factory=dict)
    hinweis: str | None = None
    status: str = OFFEN
    grund: str = ""
    antwort: dict[str, Any] = Field(default_factory=dict)
    zustand: str | None = None


def _fuellt(lf: dict) -> list[str]:
    wert = lf.get("fuellt")
    if wert is None:
        return []
    return list(wert) if isinstance(wert, list) else [wert]


def _fakten(fall: Fall, feld_id: str) -> list[Faktum]:
    return [f for f in fall.fakten if f.feld_id == feld_id]


def _zustand(fall: Fall, pruefpunkt_id: str) -> Zustand | None:
    pruefung = fall.aktuelle_pruefung()
    if pruefung is None:
        return None
    erg = next((e for e in pruefung.ergebnisse if e.pruefpunkt_id == pruefpunkt_id), None)
    return erg.zustand if erg else None


def _status(fall: Fall, p: Pruefpunkt, ziele: list[str]) -> tuple[str, str]:
    """Why this question is or is not worth asking right now.

    The point of the Leitfaden is not to hand someone fourteen questions. It is
    to say which two of them still decide something — so the ordering rule
    below is the actual product, not the list.
    """
    belegt = {z: _fakten(fall, z) for z in ziele}
    aus_gespraech = {
        z: any(f.herkunft == Herkunft.GESPRAECH for f in fs) for z, fs in belegt.items()
    }
    if ziele and all(aus_gespraech.values()):
        return BEANTWORTET, "im Gespräch bereits beantwortet"

    zustand = _zustand(fall, p.id)
    # A `strategie` Prüfpunkt is INAKTIV by construction (18 #7) — it decides no
    # verdict. Its answer still steers which remedy is proposed first
    # (`rechtsbehelf.py`), so it must stay askable.
    if p.rolle != Rolle.STRATEGIE and zustand == Zustand.INAKTIV:
        return ENTFAELLT, "der Prüfpunkt ist in diesem Fall nicht anwendbar"

    if ziele and all(belegt[z] for z in ziele):
        return ERUEBRIGT, "steht schon in den Unterlagen"

    if zustand in (Zustand.FEHLT, Zustand.WERTUNG):
        return OFFEN, f"der Prüfpunkt steht auf {zustand.value} — die Antwort kann ihn bewegen"
    return OFFEN, "noch nicht belegt"


_RANG = {OFFEN: 0, BEANTWORTET: 1, ERUEBRIGT: 2, ENTFAELLT: 3}


def fragen(fall: Fall, schema: Schema) -> list[Frage]:
    """Every Leitfaden question of the loaded schema, sorted so the ones that
    can still move the assessment come first."""
    raus: list[Frage] = []
    for p in schema.pruefpunkte:
        lf = p.leitfaden_frage
        if not lf or not lf.get("text"):
            continue
        ziele = _fuellt(lf)
        status, grund = _status(fall, p, ziele)
        zustand = _zustand(fall, p.id)
        antwort = {}
        for z in ziele:
            treffer = [f for f in _fakten(fall, z) if f.herkunft == Herkunft.GESPRAECH]
            if treffer:
                antwort[z] = treffer[-1].wert
        raus.append(Frage(
            pruefpunkt_id=p.id, pruefpunkt_titel=p.titel, text=lf["text"],
            typ=lf.get("typ", "ja_nein"), fuellt=ziele,
            werte=lf.get("werte") or {},
            feld_labels=lf.get("feld_labels") or {}, wert_labels=lf.get("wert_labels") or {},
            hinweis=lf.get("hinweis"),
            status=status, grund=grund, antwort=antwort,
            zustand=zustand.value if zustand else None,
        ))
    # inside a status band the schema order stands: it is the order of the
    # Prüfschema, which is the order a jurist thinks in.
    raus.sort(key=lambda f: _RANG.get(f.status, 9))
    return raus


# --------------------------------------------------------------------------
# answering
# --------------------------------------------------------------------------


def _ziele(schema: Schema) -> dict[str, tuple[Pruefpunkt, dict]]:
    """feld_id -> the question that declares it. The whitelist."""
    raus: dict[str, tuple[Pruefpunkt, dict]] = {}
    for p in schema.pruefpunkte:
        lf = p.leitfaden_frage
        if not lf:
            continue
        for z in _fuellt(lf):
            raus[z] = (p, lf)
    return raus


def _pruefen_wert(feld_id: str, wert: Any, lf: dict) -> Any:
    """Parse against the declared `typ`. A value that does not parse is
    refused, not coerced — the same rule the LLM adapter's validator follows."""
    typ = lf.get("typ", "ja_nein")
    if typ not in _TYPEN:
        raise LeitfadenFehler(f"{feld_id}: unbekannter Fragetyp „{typ}“")
    if wert is None:
        return None
    if typ == "ja_nein":
        if isinstance(wert, bool):
            return wert
        s = str(wert).strip().lower()
        if s in ("ja", "true", "1"):
            return True
        if s in ("nein", "false", "0"):
            return False
        raise LeitfadenFehler(f"{feld_id}: „{wert}“ ist kein Ja oder Nein")
    if typ == "zahl":
        try:
            zahl = float(str(wert).replace(",", "."))
        except (TypeError, ValueError):
            raise LeitfadenFehler(f"{feld_id}: „{wert}“ ist keine Zahl") from None
        return int(zahl) if zahl.is_integer() else zahl
    if typ == "mehrfach":
        erlaubt = (lf.get("werte") or {}).get(feld_id)
        if erlaubt is not None and wert not in erlaubt:
            raise LeitfadenFehler(
                f"{feld_id}: „{wert}“ ist keine der vorgesehenen Antworten ({', '.join(erlaubt)})"
            )
        return wert
    return str(wert)


# The three fields a contradiction overwrites, stashed verbatim so a withdrawal
# restores them rather than reconstructing them. Reconstruction would have to
# guess whether the original was `verifiziert` or `angenommen`, and a guess
# about the provenance of a fact is exactly what this program must not make.
#
# The name carries no leading underscore on purpose: `Faktum` allows extra
# fields, but pydantic drops underscore-prefixed attributes from `model_dump`,
# and a case is written to `cases/` and read back on every API request. A stash
# that does not survive that round trip would work in a unit test and be gone
# in the running program — the worst place for state to disappear.
_VORHER = "vor_widerspruch"


def _ist_gespraechsantwort(f: Faktum) -> bool:
    """Is this fact a previous Leitfaden answer?

    Not simply `herkunft == GESPRAECH`: marking a contradiction **overwrites**
    the herkunft with `strittig`, so a contested answer stopped answering to
    that name — and „replace the previous answer" silently stopped finding it,
    leaving three facts on one field after a correction. The stash is the
    stable half; it remembers what the fact was before it was contested.
    """
    if f.herkunft == Herkunft.GESPRAECH:
        return True
    vorher = getattr(f, _VORHER, None)
    return bool(vorher) and vorher.get("herkunft") == Herkunft.GESPRAECH.value


def _markieren(f: Faktum) -> None:
    if getattr(f, _VORHER, None) is None:
        setattr(f, _VORHER, {"herkunft": f.herkunft.value, "verifiziert": f.verifiziert,
                             "badge": f.badge.value if f.badge else None})
    f.herkunft = Herkunft.STRITTIG
    f.verifiziert = False
    f.badge = Badge.NICHT_GEFUNDEN


def _zuruecknehmen(f: Faktum) -> None:
    vorher = getattr(f, _VORHER, None)
    if not vorher:
        return
    f.herkunft = Herkunft(vorher["herkunft"])
    f.verifiziert = vorher["verifiziert"]
    f.badge = Badge(vorher["badge"]) if vorher["badge"] else None
    setattr(f, _VORHER, None)


def antworten(
    fall: Fall, schema: Schema, antworten: dict[str, Any], von: str = "Beraterin"
) -> list[str]:
    """Write the answers as facts. Returns the feld_ids that ended up `strittig`.

    Re-answering replaces the earlier answer instead of appending a second one:
    a person who corrects themselves has not contradicted the file, they have
    corrected it. A *document* that says something else is a different matter —
    that stays a contradiction and is marked, because which of the two is right
    is a judgement and judgements belong to the advisor at Gate 3.
    """
    erlaubt = _ziele(schema)
    unbekannt = [f for f in antworten if f not in erlaubt]
    if unbekannt:
        raise LeitfadenFehler(
            "kein Leitfaden-Feld in diesem Prüfschema: " + ", ".join(sorted(unbekannt))
        )

    # Parse EVERYTHING before writing ANYTHING. A batch with one good and one
    # bad answer used to leave the good one written as a fact and logged as an
    # event while the rejection stopped the re-run — so the case carried a
    # `gespraech` fact that no assessment had used, and the verdict on screen
    # was computed without it. Half-applied input is the one failure mode a
    # case file must not have.
    geprueft = {feld_id: _pruefen_wert(feld_id, roh, erlaubt[feld_id][1])
                for feld_id, roh in antworten.items()}

    strittig: list[str] = []
    jetzt = zeit.jetzt()
    for feld_id, wert in geprueft.items():
        # replace a previous answer to the same question
        fall.fakten = [
            f for f in fall.fakten
            if not (f.feld_id == feld_id and _ist_gespraechsantwort(f))
        ]
        # …and undo what that answer did to the *document's* fact. Marking the
        # document side `strittig` is right while the conflict exists, but the
        # document never changed — only the statement about it did. Left
        # standing, a withdrawn contradiction damages the file permanently:
        # the consumer corrects herself, the conflict is gone, and the trace
        # still says the contract is contested.
        for f in fall.fakten:
            if f.feld_id == feld_id:
                _zuruecknehmen(f)
        if wert is None:
            # No actor in the details: `fall.protokoll` refuses `von` outright,
            # because the event log must not become Leistungskontrolle (`15`
            # §12). The role is carried by the Ereignis itself; the *fact*
            # keeps `von` for display, exactly as `15` §4's example does.
            fall.protokoll("leitfaden_antwort", feld=feld_id, wert=None)
            continue

        aus_dokument = [f for f in fall.fakten if f.feld_id == feld_id]
        widerspruch = [f for f in aus_dokument if str(f.wert) != str(wert)]

        neu = Faktum(
            feld_id=feld_id, wert=wert, herkunft=Herkunft.GESPRAECH,
            badge=Badge.ANGENOMMEN, verifiziert=None, von=von, zeit=jetzt,
        )
        if widerspruch:
            # `18` #9 semantics, reused: mark, never resolve. The Prüfpunkt
            # falls to FEHLT and the chip says why.
            strittig.append(feld_id)
            # the answer itself is marked through the same door, so the stash
            # remembers it was a Leitfaden answer. Setting the fields directly
            # would overwrite `herkunft: gespraech` with `strittig` and the
            # next correction would no longer recognise it as „the previous
            # answer" — leaving three facts on one field.
            _markieren(neu)
            for f in widerspruch:
                _markieren(f)
        fall.fakten.append(neu)
        fall.protokoll(
            "leitfaden_antwort", feld=feld_id, wert=wert,
            **({"widerspricht_unterlage": True} if widerspruch else {}),
        )
    return strittig
