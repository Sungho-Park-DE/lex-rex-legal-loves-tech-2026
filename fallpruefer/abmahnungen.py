"""Franz' Anleitung §7: „erneutes Auftreten einer bereits abgemahnten Klausel
löst einen Hinweis aus."

Die Datei `normbasis/abmahnungen.json` hält je Verfahren einen Eintrag, und
das Matching ist bewusst dumm: der Klauseltyp des Eintrags ist ein Prüfpunkt
(`fallgruppe/P-id`), ein Fall trifft, wenn derselbe Prüfpunkt bei ihm NEIN
steht. Kein Name, kein Fuzzy-Text — der Verwender spielt keine Rolle (der
Radar nennt unter `k_min` keinen, `store.py`), und ein Hinweis, der „dieselbe
Klausel" sagt, weil ein LLM zwei Texte ähnlich fand, wäre genau die Zuordnung,
die 14 §3 der Motorschicht verbietet.

`geprueft:false` ist kein Makel, sondern das Feld, das der Schirm zeigt (14 §8):
jeder Eintrag trägt „ungeprüft", bis ein Mensch aus dem Team das Original
gelesen hat.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fallpruefer.konfig import WURZEL
from fallpruefer.vokabular import Massnahme, Traeger, label
from fallpruefer import zeit

PFAD = WURZEL / "normbasis" / "abmahnungen.json"


@dataclass(frozen=True)
class Abmahnung:
    id: str
    klauseltyp: str          # "<fallgruppe_id>/<pruefpunkt_id>"
    verwender: str | None    # Beklagter des öffentlichen Verfahrens, nicht ein Fall von uns
    gegenstand: str
    massnahme: Massnahme
    traeger: Traeger
    gericht: str | None
    az: str | None
    datum: str | None
    ausgang: str | None
    quelle: str | None
    geprueft: bool

    @property
    def fallgruppe_id(self) -> str:
        return self.klauseltyp.split("/", 1)[0]

    @property
    def pruefpunkt_id(self) -> str:
        return self.klauseltyp.split("/", 1)[1]

    def _massnahme_datum(self) -> str:
        m = label(self.massnahme)
        return f"{m} {zeit.datum_de(self.datum)}" if self.datum else m

    def kurz(self) -> str:
        """Träger · Maßnahme Datum — die Zeile für den Radar."""
        return f"{label(self.traeger)} · {self._massnahme_datum()}"

    def satz(self) -> str:
        """Der Satz im Prüfpfad: Verwender des Vorverfahrens (öffentlich),
        Gericht und Aktenzeichen, Maßnahme mit Datum, Träger — und immer der
        Prüfstand am Ende. Beispiel: „Klauseltyp bereits Gegenstand eines
        Verfahrens: FitOne GmbH, OLG Bamberg 3 UKl 20/24 e, Vergleich
        21.02.2025 (VZ Bayern) · ungeprüft"."""
        teile = []
        if self.verwender:
            teile.append(self.verwender)
        stelle = " ".join(x for x in (self.gericht, self.az) if x)
        if stelle:
            teile.append(stelle)
        teile.append(f"{self._massnahme_datum()} ({label(self.traeger)})")
        return ("Klauseltyp bereits Gegenstand eines Verfahrens: " + ", ".join(teile)
                + " · " + ("geprüft" if self.geprueft else "ungeprüft"))



@lru_cache(maxsize=1)
def _laden(pfad: Path = PFAD) -> tuple[Abmahnung, ...]:
    if not pfad.exists():
        return ()
    roh = json.loads(pfad.read_text(encoding="utf-8"))["eintraege"]
    return tuple(
        Abmahnung(
            id=e["id"], klauseltyp=e["klauseltyp"], verwender=e.get("verwender"),
            gegenstand=e.get("gegenstand", ""),
            massnahme=Massnahme(e["massnahme"]), traeger=Traeger(e["traeger"]),
            gericht=e.get("gericht"), az=e.get("az"), datum=e.get("datum"),
            ausgang=e.get("ausgang"), quelle=e.get("quelle"),
            geprueft=bool(e.get("geprueft", False)),
        )
        for e in roh
    )


def alle() -> tuple[Abmahnung, ...]:
    return _laden()


def nach_id(abm_id: str) -> Abmahnung | None:
    return next((a for a in alle() if a.id == abm_id), None)


def treffer(fallgruppe_id: str | None, pruefpunkte_nein: list[str]) -> list[Abmahnung]:
    """Die Einträge, deren Klauseltyp bei diesem Fall NEIN steht — sortiert nach
    Datum, neuester zuerst, damit der erste Treffer der aktuellste ist."""
    if not fallgruppe_id:
        return []
    nein = set(pruefpunkte_nein or [])
    hits = [a for a in alle()
            if a.fallgruppe_id == fallgruppe_id and a.pruefpunkt_id in nein]
    return sorted(hits, key=lambda a: a.datum or "", reverse=True)


def fuer_pruefpunkt(fallgruppe_id: str | None, pruefpunkt_id: str) -> list[Abmahnung]:
    return treffer(fallgruppe_id, [pruefpunkt_id])
