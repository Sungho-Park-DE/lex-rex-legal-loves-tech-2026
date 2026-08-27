"""The Normbasis — statute texts and case-law anchors, and the resolver.

Contract §6: the seed is mandatory. A rule may not cite a ground that does not
exist, so `strict` mode (demo) turns an unresolved anchor key into a schema
load error; `dev` mode downgrades it to a warning and the anchor renders with
the `anker_ungeprueft` badge.

Two flags that are easy to confuse and mean different things:
  `aufgeloest` — the key was found in this corpus (a program fact)
  `geprueft`   — a law student confirmed the citation (a legal fact)
Everything is `geprueft: false` until Franz' Aufgabe 4 lands (15 §13).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fallpruefer.konfig import WURZEL, konfig
from fallpruefer.vokabular import AnkerStatus, Ebene


class NormbasisFehler(RuntimeError):
    """An anchor key a schema cites is not in the corpus (strict mode)."""


@dataclass(frozen=True)
class Ankereintrag:
    key: str
    label: str
    ebene: Ebene
    geprueft: bool
    aufgeloest: bool
    status: AnkerStatus | None = None
    kernaussage: str | None = None
    text: str | None = None
    url: str | None = None
    stand: str | None = None


@dataclass
class Normbasis:
    gesetze: dict[str, dict]
    rechtsprechung: dict[str, dict]
    modus: str = "dev"
    warnungen: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.warnungen is None:
            self.warnungen = []

    def aufloesen(self, key: str, schema_anker: dict | None = None) -> Ankereintrag:
        """Resolve one anchor key. `schema_anker` is the anchor as the schema
        file wrote it — it supplies the display label and `ebene` for entries
        the corpus does not carry (and is the SSOT for `geprueft`)."""
        s = schema_anker or {}
        if key in self.gesetze:
            e = self.gesetze[key]
            return Ankereintrag(
                key=key,
                label=s.get("norm") or e["norm"],
                ebene=Ebene(s.get("ebene", "gesetz")),
                geprueft=bool(s.get("geprueft", e.get("geprueft", False))),
                aufgeloest=True,
                text=e.get("text"),
                url=e.get("url"),
                stand=e.get("stand"),
            )
        if key in self.rechtsprechung:
            e = self.rechtsprechung[key]
            return Ankereintrag(
                key=key,
                label=f"{e['gericht']}, {e['az']} ({e['datum']})",
                ebene=Ebene(s.get("ebene", e.get("ebene", "rechtsanwendung"))),
                geprueft=bool(s.get("geprueft", e.get("geprueft", False))),
                aufgeloest=True,
                status=AnkerStatus(e["status"]) if e.get("status") else None,
                kernaussage=e.get("kernaussage"),
                url=e.get("url"),
            )

        meldung = f"Anker „{key}“ ist nicht in der Normbasis"
        if self.modus == "strict":
            raise NormbasisFehler(meldung)
        self.warnungen.append(meldung)
        return Ankereintrag(
            key=key,
            label=s.get("norm") or s.get("az") or key,
            ebene=Ebene(s.get("ebene", "unentscheidbar")),
            geprueft=False,
            aufgeloest=False,
        )

    def kennt(self, key: str) -> bool:
        return key in self.gesetze or key in self.rechtsprechung

    def treffer(self, fundstellen: list[str]) -> list[tuple[str, bool]]:
        """For `normbasis_treffer` — which citations a *document* makes are
        resolvable here. Never copied into a Prüfpunkt's anchors: a citation
        found in a document is a fact about the document, not a ground."""
        return [(f, self._findbar(f)) for f in fundstellen]

    def _findbar(self, fundstelle: str) -> bool:
        norm = _normalisieren(fundstelle)
        for e in self.gesetze.values():
            if _normalisieren(e["norm"]) == norm:
                return True
        return any(_normalisieren(e["az"]) == norm for e in self.rechtsprechung.values())


def _normalisieren(s: str) -> str:
    return " ".join(s.replace("§§", "§").split()).lower().rstrip(".,;")


@lru_cache(maxsize=1)
def normbasis(verzeichnis: Path | None = None) -> Normbasis:
    v = verzeichnis or (WURZEL / "normbasis")
    gesetze = json.loads((v / "statutes_de.json").read_text(encoding="utf-8"))["eintraege"]
    caselaw_pfad = v / "caselaw.json"
    rspr = (
        json.loads(caselaw_pfad.read_text(encoding="utf-8"))["eintraege"]
        if caselaw_pfad.exists()
        else {}
    )
    return Normbasis(gesetze=gesetze, rechtsprechung=rspr, modus=konfig().normbasis_modus)
