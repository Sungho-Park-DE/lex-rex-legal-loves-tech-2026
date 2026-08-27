"""The rule grammar (contract §1) — one generic evaluator, no Prüfpunkt knows.

Three-valued on purpose. A missing field makes its atom `null`, and a branch
fires only on `true`: that is what keeps „we don't know" from collapsing into
„not a problem", which is the single most damaging failure mode a legal triage
tool can have.

    alle  = false if any false, else null if any null, else true
    eine  = true  if any true,  else null if any null, else false
    nicht null = null

Nothing in this module knows what a Preiserhöhung is. It is the same evaluator
for the second Fallgruppe, for the Dokumenten-Soll conditions and for the
letter variants — only the context differs.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fallpruefer.primitiven import PRIMITIVE, Kontext

ABWESEND = object()

_OPS = {"==", "!=", "<", "<=", ">", ">=", "in", "nicht_in"}


class RegelFehler(RuntimeError):
    pass


def _vergleichen(links: Any, op: str, rechts: Any) -> bool | None:
    if links is ABWESEND or rechts is ABWESEND or links is None or rechts is None:
        # `in` against a known list is still decidable when the left side is
        # known; every other shape with a null operand is null.
        return None
    try:
        if op == "==":
            return _gleich(links, rechts)
        if op == "!=":
            return not _gleich(links, rechts)
        if op == "in":
            return links in rechts
        if op == "nicht_in":
            return links not in rechts
        links, rechts = _angleichen(links, rechts)
        if op == "<":
            return links < rechts
        if op == "<=":
            return links <= rechts
        if op == ">":
            return links > rechts
        if op == ">=":
            return links >= rechts
    except TypeError:
        # incomparable types are "we cannot say", never "false"
        return None
    raise RegelFehler(f"unbekannter Operator „{op}“")


def _gleich(a: Any, b: Any) -> bool:
    if isinstance(a, date) or isinstance(b, date):
        a, b = _angleichen(a, b)
    return a == b


def _angleichen(a: Any, b: Any) -> tuple[Any, Any]:
    """Dates arrive typed; numbers may arrive as int next to float."""
    from fallpruefer.zeit import parse_datum

    if isinstance(a, date) and isinstance(b, str):
        return a, parse_datum(b)
    if isinstance(b, date) and isinstance(a, str):
        return parse_datum(a), b
    if isinstance(a, bool) or isinstance(b, bool):
        return a, b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a), float(b)
    return a, b


def _seite(k: Kontext, bedingung: dict, schluessel: str) -> Any:
    """Resolve one side of a comparison: `wert` literal, `feld`/`feld2` lookup,
    `param` from the Prüfpunkt's parameters, or a `prim` call."""
    if schluessel == "wert":
        return bedingung["wert"]
    if schluessel in ("feld", "feld2"):
        return k.feld(bedingung[schluessel])
    if schluessel == "param":
        return k.parameter(bedingung["param"])
    raise RegelFehler(f"unbekannte Seite „{schluessel}“")


def auswerten(bedingung: Any, k: Kontext) -> bool | None:
    """Evaluate one condition of the grammar. Returns True / False / None."""
    if bedingung is None:
        return None
    if isinstance(bedingung, bool):
        return bedingung
    if not isinstance(bedingung, dict):
        raise RegelFehler(f"Bedingung ist kein Objekt: {bedingung!r}")

    # An empty child list is „we cannot say", not vacuous truth. Mathematically
    # `all([])` is True and `any([])` is False, and both would be a trap here:
    # the Akt-2 beat is a person deleting conditions in a text editor, and
    # removing the last child of an `alle` would have made the Prüfpunkt fire
    # instead of going quiet. „A branch fires only on `true`" (module docstring)
    # has to survive an edit that empties the branch.
    if "alle" in bedingung:
        if not bedingung["alle"]:
            return None
        werte = [auswerten(c, k) for c in bedingung["alle"]]
        if any(w is False for w in werte):
            return False
        return None if any(w is None for w in werte) else True

    if "eine" in bedingung:
        if not bedingung["eine"]:
            return None
        werte = [auswerten(c, k) for c in bedingung["eine"]]
        if any(w is True for w in werte):
            return True
        return None if any(w is None for w in werte) else False

    if "nicht" in bedingung:
        w = auswerten(bedingung["nicht"], k)
        return None if w is None else not w

    if "fehlt" in bedingung:
        return k.feld(bedingung["fehlt"]) is None

    if "vorhanden" in bedingung:
        return k.feld(bedingung["vorhanden"]) is not None

    if "verifiziert" in bedingung:
        return k.verifiziert(bedingung["verifiziert"])

    if "dok_fehlt" in bedingung:
        return not k.dok_vorhanden(bedingung["dok_fehlt"])

    if "dok_vorhanden" in bedingung:
        return k.dok_vorhanden(bedingung["dok_vorhanden"])

    # V-G1: der dritte Fehlzustand, für eine Regel lesbar. `dok_fehlt` ist für
    # „nie erhalten" und „noch nicht eingereicht" derselbe Wert; erst dieses
    # Prädikat lässt eine Regel das Urteil ändern statt nur den Adressaten
    # (Franz zu Fall 6, `30` §9).
    if "dok_existiert_nicht" in bedingung:
        return k.dok_existiert_nicht(bedingung["dok_existiert_nicht"])

    op = bedingung.get("op")
    if op is not None:
        if op not in _OPS:
            raise RegelFehler(f"unbekannter Operator „{op}“")
        # Key order decides which operand is left and which is right — that is
        # exactly what the contract's notation means when it distinguishes
        # {"param": P, "op": OP, "feld": F} from {"feld": F, "op": OP, "param": P}.
        seiten = [s for s in bedingung if s in ("prim", "feld", "feld2", "param", "wert")]
        if len(seiten) < 2:
            raise RegelFehler(f"Vergleich ohne zwei Seiten: {bedingung!r}")
        links = _operand(k, bedingung, seiten[0])
        rechts = _operand(k, bedingung, seiten[1])
        return _vergleichen(links, op, rechts)

    raise RegelFehler(f"unverständliche Bedingung: {bedingung!r}")


def _operand(k: Kontext, bedingung: dict, schluessel: str) -> Any:
    if schluessel == "prim":
        name = bedingung["prim"]
        if name not in PRIMITIVE:
            raise RegelFehler(f"unbekanntes Primitiv „{name}“")
        return PRIMITIVE[name](k, bedingung.get("args") or {})
    return _seite(k, bedingung, schluessel)
