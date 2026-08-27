"""The whitelisted primitives — the only code a Prüfschema may call by name.

Contract §1: "Unknown primitive or feld → schema load error." This registry IS
that whitelist, and it is deliberately short. A primitive returns a plain
number, bool or None; the rule grammar then compares it. None means "cannot be
computed from what we have" and propagates as null through the three-valued
logic — it never silently becomes 0 or False.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

from fallpruefer import zeit
from fallpruefer.text import normalisieren


class Kontext(Protocol):
    """What a primitive is allowed to see. Implemented by `evaluator.Fallkontext`."""

    def feld(self, name: str) -> Any: ...
    def datum(self, name: str) -> Any: ...
    def dok_vorhanden(self, typ: str) -> bool: ...
    def dok_existiert_nicht(self, typ: str) -> bool: ...
    def dok_text(self, typ: str) -> str: ...
    def fundstellen_treffer(self, fundstellen: list[str]) -> list[tuple[str, bool]]: ...


def _arg(k: Kontext, wert: Any) -> Any:
    """A primitive argument is either a feld id or a literal."""
    if isinstance(wert, str) and "." in wert:
        gefunden = k.feld(wert)
        return gefunden if gefunden is not None else None
    return wert


def _datum(k: Kontext, wert: Any) -> Any:
    """A date argument is a feld id, or a LIST of feld ids meaning „the first
    one that is present".

    The list form exists because a legal period rarely hangs on the field that
    happens to be easiest to extract. A Preisgarantie runs from the
    Vertragsbeginn; the Vertragsdatum is only the day the paper was signed, and
    the two differ whenever a contract starts at the beginning of the following
    month. Writing that fallback as nested `eine`/`fehlt` branches is possible
    but unreadable — and this file is edited live by a Volljurist during the
    demo (14 §7), so the readable form is the correct one.
    """
    if isinstance(wert, list):
        for kandidat in wert:
            gefunden = k.datum(kandidat)
            if gefunden is not None:
                return gefunden
        return None
    return k.datum(wert)


def tage_zwischen(k: Kontext, args: dict) -> int | None:
    a, b = _datum(k, args["a"]), _datum(k, args["b"])
    return None if a is None or b is None else zeit.tage_zwischen(a, b)


def monate_zwischen(k: Kontext, args: dict) -> int | None:
    a, b = _datum(k, args["a"]), _datum(k, args["b"])
    return None if a is None or b is None else zeit.monate_zwischen(a, b)


def datum_plus(k: Kontext, args: dict) -> Any:
    basis = _datum(k, args.get("feld") or args.get("a"))
    tage = _arg(k, args.get("tage", args.get("b", 0)))
    if basis is None or tage is None:
        return None
    return zeit.tage_addieren(basis, int(tage))


def anzahl(k: Kontext, args: dict) -> int | None:
    liste = _arg(k, args.get("liste"))
    return None if liste is None else len(liste)


def summe_rueckforderung(k: Kontext, args: dict) -> float | None:
    """What was overpaid since the increase took effect.

    None — not 0 — when there are no Abbuchungen: nothing has been overpaid
    *yet* is a different statement from nothing is owed, and the letter picks a
    different variant for each.
    """
    abbuchungen = k.feld("kontoauszug.abbuchungen")
    vereinbart = k.feld("vertrag.beitrag")
    ab = k.datum("erhoehungsschreiben.wirksam_ab")
    if not abbuchungen or vereinbart is None:
        return None
    summe = 0.0
    for eintrag in abbuchungen:
        betrag = eintrag.get("betrag") if isinstance(eintrag, dict) else None
        datum = zeit.parse_datum(eintrag.get("datum")) if isinstance(eintrag, dict) else None
        if betrag is None:
            continue
        if ab is not None and datum is not None and datum < ab:
            continue
        summe += float(betrag) - float(vereinbart)
    return round(summe, 2) if summe > 0 else None


def kreuzpruefung_klauselverweis(k: Kontext, args: dict) -> bool | None:
    """Is the Ziffer the letter cites actually findable in the AGB or contract?

    A letter that points at „Ziffer 5.2" of a document in which no 5.2 exists
    has not shown its ground — the Prüfpunkt goes FEHLT, not NEIN.
    """
    verweis = k.feld("erhoehungsschreiben.klauselverweis")
    if not verweis:
        return None
    quelle = f"{k.dok_text('agb')}\n{k.dok_text('vertrag')}"
    if not quelle.strip():
        return None
    nadel = normalisieren(str(verweis))
    heu = normalisieren(quelle)
    if nadel in heu:
        return True

    # The letter writes „Ziffer 5.2", the AGB may write only „5.2", so the bare
    # number has to be matchable on its own. Plain substring matching was too
    # generous: it confirmed „Ziffer 12" against „…beträgt 12 Monate", i.e. it
    # reported a ground the document does not contain — the one outcome this
    # primitive exists to prevent. So the bare form is accepted only where it
    # reads as a clause number:
    #   * „5.2"  — a sectioned number is unambiguous on its own;
    #   * „12"   — a bare integer only next to a clause marker („Ziffer 12",
    #              „§ 12", „12)", „12:"). „12 Monate" is not a reference.
    # Anything else is False, not None: the reference was checked and not
    # found, which sends the Prüfpunkt to FEHLT rather than to a NEIN it
    # cannot support.
    kurz = nadel.split()[-1] if nadel.split() else nadel
    if not kurz or not any(c.isdigit() for c in kurz):
        return False
    grenze = rf"(?<![\w.,]){re.escape(kurz)}(?![\w.,])"
    if re.search(r"\d[.,]\d", kurz):
        return re.search(grenze, heu) is not None
    marker = r"(?:ziffer|zif\.?|nr\.?|nummer|punkt|abs\.?|absatz|art\.?|artikel|§)\s*"
    return bool(
        re.search(rf"{marker}{re.escape(kurz)}(?![\w.,])", heu, re.IGNORECASE)
        or re.search(rf"(?<![\w.,]){re.escape(kurz)}\s*[):.]", heu)
    )


def klauselzitat_stimmt(k: Kontext, args: dict) -> bool | None:
    """Does the clause text the letter quotes match the clause in the AGB?

    The Störfall beat: a letter that misquotes its own clause fails here and
    the Prüfpunkt degrades to `kreuzpruefung_fehlgeschlagen`.
    """
    zitat = k.feld("erhoehungsschreiben.klauselzitat")
    klausel = k.feld("agb.preisklausel_text") or k.feld("vertrag.preisklausel_text")
    if not zitat or not klausel:
        return None
    a, b = normalisieren(str(zitat)).strip('"'), normalisieren(str(klausel)).strip('"')
    return a in b or b in a


def normbasis_treffer(k: Kontext, args: dict) -> int | None:
    """How many of the citations the *document* makes resolve in our Normbasis.

    Never copied into a Prüfpunkt's anchors — a citation found in a document is
    a fact about that document (contract §6).
    """
    liste = _arg(k, args.get("liste"))
    if liste is None:
        return None
    return sum(1 for _, gefunden in k.fundstellen_treffer(list(liste)) if gefunden)


PRIMITIVE = {
    "tage_zwischen": tage_zwischen,
    "datum_plus": datum_plus,
    "monate_zwischen": monate_zwischen,
    "anzahl": anzahl,
    "summe_rueckforderung": summe_rueckforderung,
    "kreuzpruefung_klauselverweis": kreuzpruefung_klauselverweis,
    "klauselzitat_stimmt": klauselzitat_stimmt,
    "normbasis_treffer": normbasis_treffer,
}
