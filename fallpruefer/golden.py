"""The golden runner (contract §11) — definition of done per ladder rung.

It compares four things per stage, and reports one headline: **falsche sichere
Antworten** — cases where the expectation was „unklar" and the program answered
„wirksam" or „wahrscheinlich unwirksam". A tool that says „I don't know" too
often is annoying; a tool that is confidently wrong is the one that costs an
advisor their credibility, so that cell gets its own line.

`geprueft: false` files are advisory (ours, our own fiction); `true` ones gate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from fallpruefer.konfig import WURZEL

ZWEIGE = ["wirksam", "wahrscheinlich unwirksam", "unklar"]


@dataclass
class Abweichung:
    stufe: str
    was: str
    erwartet: object
    bekommen: object

    def __str__(self) -> str:
        return f"[{self.stufe}] {self.was}: erwartet {self.erwartet!r}, bekommen {self.bekommen!r}"


@dataclass
class Ergebnis:
    case_id: str
    geprueft: bool
    gating: bool
    abweichungen: list[Abweichung] = field(default_factory=list)
    matrix: dict[tuple[str, str], int] = field(default_factory=dict)
    # How many of the eight possible comparisons each stage actually ran.
    # A hand-transcribed Lösungszettel that only states the Einordnung passes
    # one check and reports OK — which reads exactly like a case that passed
    # all eight. The count is the difference between „green" and „covered".
    abdeckung: list[tuple[str, int]] = field(default_factory=list)

    @property
    def gruen(self) -> bool:
        return not self.abweichungen

    @property
    def falsche_sichere_antworten(self) -> int:
        return sum(
            n for (erw, bek), n in self.matrix.items()
            if erw == "unklar" and bek in ("wirksam", "wahrscheinlich unwirksam")
        )


# Everything a stage may expect. A key outside this set is a typo, not a
# feature — see `_unbekannte_schluessel`.
# Keys that assert something. Everything here is compared; a key outside both
# sets is a typo, not a feature (see the unknown-key check in `lauf`).
ERWARTET_PRUEFUNGEN = {
    "einordnung", "fehlt", "gekippte_pruefpunkte", "hauptvorschlag",
    "gerissene_stufe", "zustaende", "dokumenttypen", "brief_gerendert",
}
# Keys that are prose for the reader — the stage's document list, the hand
# derivation, a remark. Deliberately not compared, and named separately so
# nobody mistakes a file full of prose for a file full of assertions.
ERWARTET_PROSA = {"dokumente", "herleitung", "kommentar"}
ERWARTET_SCHLUESSEL = ERWARTET_PRUEFUNGEN | ERWARTET_PROSA


def _zweig(einordnung: str) -> str:
    """Map a verdict onto its branch — and refuse to guess.

    Folding anything unrecognised into „unklar" made the runner's own safety
    metric blind: „falsche sichere Antworten" counts expected-unklar answered
    as a hard verdict, and a garbled or empty verdict string was filed as a
    correct „unklar" instead. Two of the three branch strings are compared
    verbatim elsewhere; this makes the third one just as pinned.
    """
    if einordnung in ZWEIGE:
        return einordnung
    if einordnung.startswith("unklar – es fehlt"):
        return "unklar"
    return f"UNBEKANNT({einordnung[:40]})"


def lauf(pfad: Path, adapter=None) -> Ergebnis:
    """Run every stage of one golden file.

    A multi-stage file is not N independent cases: stage 2 continues stage 1's
    case object through `pipeline.nachreichung()`, which is the code path the
    demo's flip actually takes. Re-creating the case from the full document
    list would test the same engine on more input and would never notice that
    the re-run semantics (contract §4) are broken.
    """
    from fallpruefer.dokumente import laden
    from fallpruefer.pipeline import fall_anlegen, nachreichung, verarbeiten

    spec = json.loads(pfad.read_text(encoding="utf-8"))
    verzeichnis = WURZEL / spec["fall_verzeichnis"]
    ticket = json.loads((verzeichnis / "ticket.json").read_text(encoding="utf-8"))

    erg = Ergebnis(
        case_id=spec["case_id"],
        geprueft=bool(spec.get("geprueft")),
        gating=bool(spec.get("gating", spec.get("geprueft"))),
    )

    fall = None
    gesehen: list[str] = []
    for stufe in spec["stufen"]:
        name = stufe["name"]
        erwartet = stufe["erwartet"]
        dateinamen = list(stufe["dokumente"])

        if fall is None:
            dokumente = [
                laden(verzeichnis / dateiname, f"D{i}")
                for i, dateiname in enumerate(dateinamen, start=1)
            ]
            fall = fall_anlegen(
                spec["case_id"], ticket, dokumente, spec.get("fallgruppe_id")
            )
            fall = verarbeiten(fall, adapter, trigger="initial" if name == "initial" else name)
        else:
            neu_dazu = [d for d in dateinamen if d not in gesehen]
            fall = nachreichung(
                fall, [laden(verzeichnis / d) for d in neu_dazu], adapter=adapter
            )
        gesehen = dateinamen

        pruefung = fall.aktuelle_pruefung()
        if pruefung is None:
            erg.abweichungen.append(Abweichung(name, "pruefung", "eine Prüfung", None))
            continue

        unbekannt = sorted(set(erwartet) - ERWARTET_SCHLUESSEL)
        if unbekannt:
            # Renaming every key in a golden file used to delete all its
            # coverage and stay green. These files get hand-edited exactly when
            # a Lösungszettel arrives (15 §13), which is when a typo happens.
            erg.abweichungen.append(
                Abweichung(name, "unbekannter erwartet-Schlüssel", sorted(ERWARTET_SCHLUESSEL), unbekannt)
            )

        erg.abdeckung.append((name, len(set(erwartet) & ERWARTET_PRUEFUNGEN)))

        # A P-ID that is not in the schema is a transcription error — and it is
        # invisible under an equality check, which just reports a set that does
        # not match without saying that one side names something imaginary.
        from fallpruefer.schema import schema_laden_oder_letzte

        bekannte_ids = {
            pp.id for pp in schema_laden_oder_letzte(fall.schema_.fallgruppe_id).pruefpunkte
        }
        genannt = set(erwartet.get("gekippte_pruefpunkte") or []) | set(erwartet.get("zustaende") or {})
        unbekannte_ids = sorted(genannt - bekannte_ids)
        if unbekannte_ids:
            erg.abweichungen.append(
                Abweichung(name, "unbekannte Prüfpunkt-ID", sorted(bekannte_ids), unbekannte_ids))

        bekommen = pruefung.einordnung
        schluessel = (_zweig(erwartet["einordnung"]), _zweig(bekommen))
        erg.matrix[schluessel] = erg.matrix.get(schluessel, 0) + 1
        if _zweig(bekommen) != _zweig(erwartet["einordnung"]):
            erg.abweichungen.append(Abweichung(name, "einordnung", erwartet["einordnung"], bekommen))

        if "gekippte_pruefpunkte" in erwartet:
            gekippt = {e.pruefpunkt_id for e in pruefung.ergebnisse if e.zustand.value == "NEIN"}
            # equality, not „expected is a subset": a Prüfpunkt the engine
            # kipped and the derivation does not know about is exactly as wrong
            # as one it missed, and four of the six stages expect [] — which
            # under a subset check asserted nothing at all.
            if set(erwartet["gekippte_pruefpunkte"]) != gekippt:
                erg.abweichungen.append(
                    Abweichung(name, "gekippte_pruefpunkte", erwartet["gekippte_pruefpunkte"], sorted(gekippt))
                )

        if "fehlt" in erwartet:
            ist = {
                (f.dokumenttyp.value if f.dokumenttyp else f.feld_id, quelle)
                for quelle, liste in pruefung.vollstaendigkeit.items()
                for f in liste
            }
            # `.get`, not `[…]`: a hand-transcribed row without `quelle` used to
            # raise KeyError out of the runner and take every other case with
            # it. A transcription error is a finding about one file.
            soll = {(f.get("dokumenttyp") or f.get("feld_id"), f.get("quelle"))
                    for f in erwartet["fehlt"]}
            ohne_quelle = [f for f in erwartet["fehlt"] if not f.get("quelle")]
            if ohne_quelle:
                erg.abweichungen.append(Abweichung(
                    name, "fehlt-Eintrag ohne „quelle“",
                    "verbraucher | unternehmen", ohne_quelle))
            if soll != ist:
                erg.abweichungen.append(Abweichung(name, "fehlt", sorted(soll), sorted(ist)))

        if "hauptvorschlag" in erwartet:
            ist = fall.rechtsbehelf.hauptvorschlag
            if ist != erwartet["hauptvorschlag"]:
                erg.abweichungen.append(Abweichung(name, "hauptvorschlag", erwartet["hauptvorschlag"], ist))

        # optional, beyond §11 — free to check and catches more
        if "gerissene_stufe" in erwartet and pruefung.gerissene_stufe != erwartet["gerissene_stufe"]:
            erg.abweichungen.append(
                Abweichung(name, "gerissene_stufe", erwartet["gerissene_stufe"], pruefung.gerissene_stufe)
            )
        for pid, soll_zustand in (erwartet.get("zustaende") or {}).items():
            e = pruefung.ergebnis(pid)
            ist = e.zustand.value if e else None
            if ist != soll_zustand:
                erg.abweichungen.append(Abweichung(name, f"zustand {pid}", soll_zustand, ist))
        for dok_id, soll_typ in (erwartet.get("dokumenttypen") or {}).items():
            d = fall.dokument(dok_id)
            ist = d.dokumenttyp.value if d else None
            if ist != soll_typ:
                erg.abweichungen.append(Abweichung(name, f"dokumenttyp {dok_id}", soll_typ, ist))
        if erwartet.get("brief_gerendert") and not (fall.rechtsbehelf.brief and fall.rechtsbehelf.brief.text):
            erg.abweichungen.append(Abweichung(name, "brief_gerendert", True, False))

    return erg


def alle(verzeichnis: Path | None = None, adapter=None) -> list[Ergebnis]:
    v = verzeichnis or (WURZEL / "tests" / "golden")
    return [lauf(p, adapter) for p in sorted(v.glob("*.json"))]


def bericht(ergebnisse: list[Ergebnis]) -> str:
    zeilen: list[str] = []
    gesamt: dict[tuple[str, str], int] = {}
    for e in ergebnisse:
        marke = "OK  " if e.gruen else "FAIL"
        art = "gating" if e.gating else "advisory"
        gelaufen = sum(n for _, n in e.abdeckung)
        moeglich = len(e.abdeckung) * len(ERWARTET_PRUEFUNGEN)
        deckung = f", {gelaufen}/{moeglich} Vergleiche" if moeglich else ""
        zeilen.append(f"{marke} {e.case_id} ({art}, geprueft={str(e.geprueft).lower()}{deckung})")
        for a in e.abweichungen:
            zeilen.append(f"       {a}")
        if e.abweichungen:
            # Both kinds fail the build — a deviation is a regression either
            # way, and these four files are the only thing standing between a
            # refactor and a silently different verdict. What differs is who
            # is right by default, and that decides what you do next.
            zeilen.append(
                "       ↳ GATING: das ist die Lesart einer Juristin. Weicht die Engine ab, "
                "ist zuerst zu klären, ob die Regel im Schema falsch ist (Jurist-Edit) "
                "oder der Zettel unsere Begriffe anders meint — nicht die Erwartung anpassen."
                if e.gating else
                "       ↳ ADVISORY: das ist unsere eigene Herleitung. Eine Abweichung ist "
                "zuerst ein Verdacht gegen die Engine — oder gegen die Herleitung."
            )
        for k, n in e.matrix.items():
            gesamt[k] = gesamt.get(k, 0) + n

    zeilen.append("")
    zeilen.append("Konfusionsmatrix (Zeile = erwartet, Spalte = bekommen)")
    kopf = " " * 26 + "".join(f"{z:>26}" for z in ZWEIGE)
    zeilen.append(kopf)
    for erw in ZWEIGE:
        zelle = f"{erw:<26}" + "".join(f"{gesamt.get((erw, bek), 0):>26}" for bek in ZWEIGE)
        zeilen.append(zelle)
    falsch = sum(
        n for (erw, bek), n in gesamt.items()
        if erw == "unklar" and bek in ("wirksam", "wahrscheinlich unwirksam")
    )
    zeilen.append("")
    zeilen.append(f"falsche sichere Antworten: {falsch}")
    return "\n".join(zeilen)
