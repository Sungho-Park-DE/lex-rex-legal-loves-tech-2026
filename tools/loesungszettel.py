"""Read a filled Lösungszettel back into `tests/golden/<case_id>.json`.

This is the „drop-in path (no code)" that `15` §13 promises for Franz' cases.
It is deliberately the *second* half of a pair: `tools/loesungszettel_vorlage.py`
generates the form from the Prüfschema, this reads the same shape back. Nothing
here guesses at free prose, and nothing translates his numbering — the form
prints our P-IDs, so there is no numbering to translate.

    .venv/bin/python tools/loesungszettel.py data/eingang/franz_loesungen.md
    .venv/bin/python tools/loesungszettel.py <datei> --pruefen      # nur prüfen, nichts schreiben

What it refuses to do:

  * **Write a half-read file.** Every problem it finds is reported and nothing
    is written. A golden file that is silently thin is worse than no golden
    file — it reports OK for a case nobody checked.
  * **Invent the company side.** `fehlt` always contains what the *company*
    owes (`pflicht: hinweis`), which is a property of the Dokumenten-Soll and
    not a finding about the case. Those rows come from the schema; the consumer
    side comes from Franz. Two sources, and the file says which is which.
  * **Translate his verdict words.** The form makes him pick one of our three.
    His own vocabulary defines `wahrscheinlich_unwirksam` as „the material does
    not carry the proof yet", which is our `unklar` — a word-for-word mapping
    would promote unclear cases to hard verdicts. See `schemas/_quellen_map.json`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fallpruefer.konfig import WURZEL  # noqa: E402
from fallpruefer.schema import schema_laden  # noqa: E402
from fallpruefer.vokabular import Pflicht, Quelle  # noqa: E402

ZIEL = WURZEL / "tests" / "golden"

_BLOCK = re.compile(r"^##\s+Fall\b", re.M)
_ANGEKREUZT = re.compile(r"^\s*-\s*\[[xX]\]\s*(.+?)\s*$", re.M)
# `[ \t]*`, not `\s*`: `\s` matches a newline, so an empty field swallowed the
# line break and captured the *next* label as its value.
_FELD = re.compile(r"^\*\*(?P<name>[^*]+?):?\*\*[ \t]*(?P<wert>.*?)[ \t]*$", re.M)
def _kennung(zeile: str) -> str:
    """`**P6** — Transparenzgebot` -> `P6`; ``` `agb` — die AGB … ``` -> `agb`;
    `**`unklar – es fehlt …`**` -> `unklar – es fehlt …`.

    Cut at the em dash only — the en dash inside „unklar – es fehlt" is part of
    the verdict string, and confusing the two silently drops the whole verdict.
    """
    ohne_markdown = zeile.replace("**", "").replace("`", "").strip()
    return ohne_markdown.split(" — ")[0].strip()


@dataclass
class Stufe:
    name: str
    dokumente: list[str]
    einordnung: str | None = None
    unklar_grund: list[str] = field(default_factory=list)
    wertungsfrage: str = ""
    gekippt: list[str] = field(default_factory=list)
    gates_nein: list[str] = field(default_factory=list)
    kipp_punkt: str = ""
    kipp_grund: str = ""
    fehlt: list[str] = field(default_factory=list)
    rechtsbehelf: str | None = None
    fundstellen: str = ""
    anmerkung: str = ""


def _abschnitt(block: str, ueberschrift: str) -> str:
    """Everything under `### <n>. <heading>` up to the next `###`."""
    m = re.search(rf"^###\s*\d+\.\s*{re.escape(ueberschrift)}.*?$", block, re.M)
    if not m:
        return ""
    rest = block[m.end():]
    weiter = re.search(r"^###\s", rest, re.M)
    return rest[: weiter.start()] if weiter else rest


def _ohne_kommentare(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def _kennungen(text: str) -> list[str]:
    """The bare identifiers of the ticked lines — `P6`, `agb`, `wirksam`."""
    aus: list[str] = []
    for zeile in _ANGEKREUZT.findall(_ohne_kommentare(text)):
        k = _kennung(zeile)
        if k:
            aus.append(k)
    return aus


def _feld(block: str, name: str) -> str:
    for m in _FELD.finditer(_ohne_kommentare(block)):
        if m.group("name").strip().lower().startswith(name.lower()):
            return m.group("wert").strip().strip("`")
    return ""


def _block_lesen(block: str) -> tuple[str, Stufe]:
    kennung = _feld(block, "Fall-Kennung")
    stufe = Stufe(
        name=_feld(block, "Stufe") or "initial",
        dokumente=[d.strip() for d in _feld(block, "Unterlagen").split(",") if d.strip()],
    )

    eins = _abschnitt(block, "Einordnung")
    gekreuzt = _kennungen(eins)
    # the two „woran liegt es" boxes are in the same section as the verdicts
    stufe.einordnung = next((g for g in gekreuzt if g.startswith(("wirksam", "wahrscheinlich", "unklar"))), None)
    stufe.unklar_grund = [g for g in gekreuzt if g.startswith("Es ")]
    stufe.wertungsfrage = _feld(eins, "Bewertungsfrage")

    zwei = _abschnitt(block, "Welche Prüfpunkte")
    stufe.gekippt = [g for g in _kennungen(zwei) if re.fullmatch(r"P\d+[a-z]?", g)]
    stufe.kipp_punkt = _feld(zwei, "Kipp-Punkt")
    stufe.kipp_grund = _feld(zwei, "Warum")

    drei = _abschnitt(block, "Welche Unterlagen fehlen")
    stufe.fehlt = _kennungen(drei)

    vier = _abschnitt(block, "Welcher Rechtsbehelf")
    rb = _kennungen(vier)
    stufe.rechtsbehelf = rb[0] if rb else None
    stufe.fundstellen = _feld(vier, "Fundstellen")

    # the section runs to the end of the block, so the `---` separator is in it
    stufe.anmerkung = _ohne_kommentare(_abschnitt(block, "Anmerkung")).strip().strip("-").strip()
    return kennung, stufe


def _pruefen(kennung: str, stufe: Stufe, schema) -> list[str]:
    p_ids = {p.id for p in schema.pruefpunkte}
    dok_typen = {d.dokumenttyp.value for d in schema.dokumenten_soll.dokumente}
    rb_ids = {r.id for r in schema.rechtsbehelfe.liste}
    ort = f"{kennung or '<ohne Kennung>'} / {stufe.name}"
    f: list[str] = []

    if not kennung or kennung.startswith("<"):
        f.append(f"{ort}: „Fall-Kennung“ ist nicht ausgefüllt.")
    if not stufe.dokumente:
        f.append(f"{ort}: keine Unterlagen genannt — welche Dateien liegen in dieser Stufe vor?")
    if stufe.einordnung is None:
        f.append(f"{ort}: keine Einordnung angekreuzt. Genau eine der drei ist Pflicht.")
    for pid in stufe.gekippt + stufe.gates_nein:
        if pid not in p_ids:
            f.append(f"{ort}: „{pid}“ ist kein Prüfpunkt dieses Schemas ({', '.join(sorted(p_ids))}).")
    for typ in stufe.fehlt:
        if typ not in dok_typen:
            f.append(f"{ort}: „{typ}“ ist keine Unterlagenart dieses Schemas.")
    if stufe.rechtsbehelf and stufe.rechtsbehelf not in rb_ids:
        f.append(f"{ort}: „{stufe.rechtsbehelf}“ ist kein Rechtsbehelf dieses Schemas.")

    e = stufe.einordnung or ""
    if e.startswith("unklar") and not stufe.unklar_grund:
        f.append(f"{ort}: „unklar“ angekreuzt, aber nicht woran es liegt (Unterlage / Bewertung).")
    if e == "wahrscheinlich unwirksam" and not stufe.gekippt:
        f.append(f"{ort}: „wahrscheinlich unwirksam“ ohne einen einzigen gerissenen Prüfpunkt — "
                 "welcher ist es? (Wenn nur der Nachweis fehlt, ist es „unklar“.)")
    if e == "wirksam" and stufe.gekippt:
        f.append(f"{ort}: „wirksam“, aber {', '.join(stufe.gekippt)} sind als nicht erfüllt "
                 "angekreuzt — das widerspricht sich.")
    if stufe.kipp_punkt and stufe.kipp_punkt not in stufe.gekippt:
        f.append(f"{ort}: Kipp-Punkt „{stufe.kipp_punkt}“ ist oben nicht angekreuzt.")
    return f


def _unternehmensseite(schema) -> list[dict]:
    """Rows the Lösungszettel cannot produce and must not be asked for.

    A `pflicht: hinweis` document on the company side is open in every case by
    design (18 #29) — it is a property of the Dokumenten-Soll, not a finding
    about this case, so it comes from the schema and not from Franz.
    """
    return [
        {"dokumenttyp": d.dokumenttyp.value, "quelle": d.quelle.value}
        for d in schema.dokumenten_soll.dokumente
        if d.quelle != Quelle.VERBRAUCHER and d.pflicht == Pflicht.HINWEIS
    ]


def _golden(kennung: str, stufen: list[Stufe], schema, quelle: str) -> dict:
    unternehmen = _unternehmensseite(schema)
    aus_stufen = []
    for s in stufen:
        erwartet: dict = {"einordnung": s.einordnung}
        if s.gekippt:
            erwartet["gekippte_pruefpunkte"] = sorted(s.gekippt)
        erwartet["fehlt"] = [
            {"dokumenttyp": t, "quelle": "verbraucher"} for t in sorted(s.fehlt)
        ] + unternehmen
        if s.rechtsbehelf:
            erwartet["hauptvorschlag"] = s.rechtsbehelf
        herleitung = " · ".join(x for x in (
            f"Kippt an {s.kipp_punkt}: {s.kipp_grund}" if s.kipp_punkt else "",
            f"Bewertungsfrage: {s.wertungsfrage}" if s.wertungsfrage else "",
            f"Fundstellen: {s.fundstellen}" if s.fundstellen else "",
            s.anmerkung,
        ) if x)
        if herleitung:
            erwartet["herleitung"] = herleitung
        erwartet["dokumente"] = s.dokumente
        aus_stufen.append({"name": s.name, "dokumente": s.dokumente, "erwartet": erwartet})

    return {
        "case_id": kennung,
        "titel": f"Lösungszettel {kennung}",
        "quelle": quelle,
        "geprueft": True,
        "gating": True,
        "fall_verzeichnis": f"demo/faelle/{kennung}",
        "fallgruppe_id": schema.fallgruppe_id,
        "kommentar": (
            "Erzeugt aus einem ausgefüllten Lösungszettel (tools/loesungszettel.py). "
            "Die verbraucherseitigen `fehlt`-Zeilen stammen aus dem Zettel; die "
            "unternehmensseitigen aus dem Dokumenten-Soll des Schemas — die stehen in "
            "jedem Fall offen und sind kein Befund über diesen Fall."
        ),
        "stufen": aus_stufen,
    }


def lesen(pfad: Path, fallgruppe_id: str) -> tuple[dict[str, dict], list[str]]:
    text = pfad.read_text(encoding="utf-8")
    schema = schema_laden(fallgruppe_id)
    grenzen = [m.start() for m in _BLOCK.finditer(text)]
    if not grenzen:
        return {}, [f"{pfad.name}: kein einziger „## Fall“-Block gefunden."]

    fehler: list[str] = []
    je_fall: dict[str, list[Stufe]] = {}
    for i, start in enumerate(grenzen):
        ende = grenzen[i + 1] if i + 1 < len(grenzen) else len(text)
        kennung, stufe = _block_lesen(text[start:ende])
        fehler.extend(_pruefen(kennung, stufe, schema))
        if kennung and not kennung.startswith("<"):
            je_fall.setdefault(kennung, []).append(stufe)

    quelle = f"Lösungszettel {pfad.name}, eingelesen mit tools/loesungszettel.py"
    return {k: _golden(k, s, schema, quelle) for k, s in je_fall.items()}, fehler


def _kurz(p: Path) -> str:
    try:
        return str(p.relative_to(WURZEL))
    except ValueError:
        return str(p)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("datei", type=Path)
    p.add_argument("--fallgruppe", default="preiserhoehung")
    p.add_argument("--ziel", type=Path, default=ZIEL)
    p.add_argument("--pruefen", action="store_true", help="nur prüfen, nichts schreiben")
    a = p.parse_args()

    golden, fehler = lesen(a.datei, a.fallgruppe)

    if fehler:
        print(f"{len(fehler)} Problem(e) — es wird nichts geschrieben:\n")
        for f in fehler:
            print(f"  - {f}")
        print("\nEin halb gelesener Zettel ergibt ein Golden, das OK meldet und nichts prüft.")
        raise SystemExit(1)

    if not golden:
        print("Nichts zu schreiben.")
        raise SystemExit(1)

    for kennung, daten in sorted(golden.items()):
        n = len(daten["stufen"])
        if a.pruefen:
            print(f"  OK  {kennung}: {n} Stufe(n), Einordnung "
                  f"{' -> '.join(s['erwartet']['einordnung'] for s in daten['stufen'])}")
            continue
        ziel = a.ziel / f"{kennung}.json"
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(json.dumps(daten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  {_kurz(ziel)} — {n} Stufe(n), geprueft: true (gating)")

    if not a.pruefen:
        print("\nJetzt: den Fall unter `demo/faelle/<kennung>/` anlegen, das Cache-Werkzeug "
              "dafür laufen lassen, dann `pytest tests/ -q`.")


if __name__ == "__main__":
    main()
