"""B1 — run the live adapter path once and diff it against the hand-written cache.

Why this tool exists (`analysis/offene_punkte.md` B1): `anthropic_adapter.py` is
88 statements at 0 % coverage, the only skipped test is its live replay, and all
four goldens descend from cache that was written by hand to be correct. The
entire layer that *reads a document* has therefore never executed against a
model. The „amount 100x too large" defect (`basis._wert_parsen`) lived exactly
in that gap: the prompt asks for „29,90", the parser dropped the dot, and no
test could see it because every test replayed a hand-written German-comma cache.

The deliverable is a list of ADAPTER-LAYER defects, not a score for the model.
A live answer that differs from the cache is interesting only when the
difference tells us something about our prompt, our parser or our validator:

  VERWORFEN   the model answered and OUR validator threw the answer away
              -> the strongest signal. Prompt and validator disagree.
  TYP         the value did not parse against the field spec
              -> `_wert_parsen` vs. the format the prompt asks for.
  ZITAT       the quote is not a substring of the pseudonymised page
              -> the model paraphrased, or L0 rewrote the span it quoted.
  FEHLT       the cache has a fact here, live produced none
              -> the field spec's `beschreibung` does not carry the field.
  ZUSATZ      live produced a fact the cache does not have (often fine).
  WERT        both sides produced a valid fact, values differ.

It never writes to `cache/llm/`: live calls go through
`AnthropicAdapter(cache_lesen=False)`, which by construction makes a real call
and records nothing. The demo cache is read-only here.

Run:
    .venv/bin/python tools/live_diff.py               # dry run: plan + cost estimate
    ANTHROPIC_API_KEY=... .venv/bin/python tools/live_diff.py --live
    ... --live --fall seepark_seite_fehlt             # one case only
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fallpruefer.adapter import cache  # noqa: E402
from fallpruefer.adapter.basis import (  # noqa: E402
    Aufruf,
    Extraktion,
    Klassifikation,
    Vorschlaege,
    _wert_parsen,
    validiere_extraktion,
    validiere_klassifikation,
    validiere_vorschlaege,
)
from fallpruefer.adapter.cache_adapter import feld_eingabe, seiten_eingabe  # noqa: E402
from fallpruefer.dokumente import laden  # noqa: E402
from fallpruefer.konfig import WURZEL, konfig  # noqa: E402
from fallpruefer.pipeline import fall_anlegen, pseudonymisieren  # noqa: E402
from fallpruefer.schema import schema_laden, taxonomie  # noqa: E402
from fallpruefer.text import enthaelt  # noqa: E402
from fallpruefer.vokabular import Dokumenttyp  # noqa: E402

# The wired cases. Franz' `pulse_drehkreuz`/`rundschau_agb_fehlen` have no
# cache and are deliberately absent.
FAELLE = ["drehkreuz", "sauber_aktivpark", "nordlicht_agb_fehlen", "seepark_seite_fehlt"]


def stufen(verzeichnis: Path) -> list[list[str]]:
    """Derived, not duplicated: stage 1 is the ticket's `anhaenge`, stage 2 is
    that plus every `*_nachgereicht.md` in the directory. That is exactly what
    the four cache tools write, and deriving it means a new Nachreichung file
    is picked up here without editing this list — a second hand-kept copy of
    those file names is precisely the thing that goes stale."""
    ticket = json.loads((verzeichnis / "ticket.json").read_text(encoding="utf-8"))
    erste = list(ticket["anhaenge"])
    nach = sorted(p.name for p in verzeichnis.glob("*_nachgereicht.md"))
    fehlend = [n for n in erste + nach if not (verzeichnis / n).exists()]
    if fehlend:
        raise SystemExit(f"{verzeichnis.name}: Datei(en) fehlen: {fehlend}")
    return [erste, erste + nach] if nach else [erste]


@dataclass
class Befund:
    """One difference, already classified. `art` is the defect class."""

    art: str
    fall: str
    stufe: int
    aufgabe: str
    dok: str
    feld: str = ""
    cache_wert: Any = None
    live_wert: Any = None
    detail: str = ""


@dataclass
class Lauf:
    befunde: list[Befund] = field(default_factory=list)
    aufrufe: int = 0
    geplant: int = 0
    cache_kosten_cent: float = 0.0
    kosten_cent: float = 0.0
    dauer_ms: int = 0
    felder_geprueft: int = 0
    felder_gleich: int = 0
    # je Live-Aufruf eine Zeile: Aufgabe, Modell, Dauer, Kosten -- B1 hatte
    # nur die Summe, und "8,2 s je Aufruf" ist ein Schnitt ueber zwei Modelle
    detail: list[dict] = field(default_factory=list)
    # one live call per DISTINCT cache key: a document that appears in both
    # stages produces the identical `eingabe`, so the production adapter would
    # serve the second one from cache too. Calling twice would also let one
    # input give two answers and read as a difference in both places.
    memo: dict[str, Aufruf] = field(default_factory=dict)

    def add(self, b: Befund) -> None:
        self.befunde.append(b)


# --------------------------------------------------------------------------
# why did the validator drop this field?
# --------------------------------------------------------------------------


def warum_verworfen(treffer, spec, seiten_text: dict[int, str]) -> tuple[str, str]:
    """Re-derive the validator's reason. Kept OUT of `basis.py` on purpose: the
    production validator returns ids, not reasons, and a diagnostic must not
    change the code path it diagnoses. The caller asserts that this function
    agrees with the validator — a disagreement prints UNBEKANNT rather than a
    plausible guess."""
    if spec is None:
        return "VERWORFEN", "feld_id steht nicht in der Soll-Liste"
    wert = _wert_parsen(treffer.wert, spec)
    if wert is None and not (spec.typ == "liste_text" and treffer.wert == []):
        return "TYP", f"{treffer.wert!r} parst nicht als {spec.typ}" + (
            f" (erlaubt: {spec.werte})" if spec.typ == "enum" and spec.werte else ""
        )
    zitat = (treffer.zitat or "").strip()
    if spec.zitat_pflicht and not zitat:
        return "ZITAT", "zitat_pflicht, aber kein Zitat geliefert"
    if zitat and not any(enthaelt(t, zitat) for t in seiten_text.values()):
        return "ZITAT", f"Zitat steht so nicht im Dokument: {zitat[:80]!r}"
    return "UNBEKANNT", "Validator hat verworfen, dieser Nachbau nicht"


# --------------------------------------------------------------------------
# comparison
# --------------------------------------------------------------------------


def fakten_map(fakten) -> dict[str, Any]:
    return {f.feld_id: f.wert for f in fakten}


def vergleiche_extraktion(
    lauf: Lauf, fall: str, stufe: int, dok: str,
    cache_roh: Extraktion, live_roh: Extraktion, felder, seiten,
) -> None:
    specs = {f.feld_id: f for f in felder}
    seiten_text = {s.nr: (s.text_pseudonym or s.text_original) for s in seiten}

    c_fakten, c_verworfen = validiere_extraktion(cache_roh, felder, seiten, dok)
    l_fakten, l_verworfen = validiere_extraktion(live_roh, felder, seiten, dok)
    c_map, l_map = fakten_map(c_fakten), fakten_map(l_fakten)
    live_roh_map = {t.feld_id: t for t in live_roh.felder}

    # 1. what the live model answered and our own validator then threw away
    for fid in l_verworfen:
        art, detail = warum_verworfen(live_roh_map.get(fid), specs.get(fid), seiten_text)
        lauf.add(Befund(art, fall, stufe, "extract_fields", dok, fid,
                        cache_wert=c_map.get(fid),
                        live_wert=getattr(live_roh_map.get(fid), "wert", None),
                        detail=detail))

    # 2. the cache's own entries, for the record — a hand-written cache that
    #    its own validator rejects is a defect in the fixture, not the model
    for fid in c_verworfen:
        lauf.add(Befund("CACHE_VERWORFEN", fall, stufe, "extract_fields", dok, fid,
                        detail="der handgeschriebene Cache-Eintrag ist selbst ungueltig"))

    # 3. field-by-field on what survived validation
    for fid in sorted(set(c_map) | set(l_map)):
        lauf.felder_geprueft += 1
        if fid in c_map and fid not in l_map:
            if fid not in l_verworfen:      # already reported above if it was
                lauf.add(Befund("FEHLT", fall, stufe, "extract_fields", dok, fid,
                                cache_wert=c_map[fid],
                                detail="Cache hat einen Fakt, live keinen"))
        elif fid in l_map and fid not in c_map:
            lauf.add(Befund("ZUSATZ", fall, stufe, "extract_fields", dok, fid,
                            live_wert=l_map[fid],
                            detail="live liefert ein Feld, das der Cache nicht kennt"))
        elif str(c_map[fid]) != str(l_map[fid]):
            lauf.add(Befund("WERT", fall, stufe, "extract_fields", dok, fid,
                            cache_wert=c_map[fid], live_wert=l_map[fid]))
        else:
            lauf.felder_gleich += 1


# --------------------------------------------------------------------------
# one case, one stage
# --------------------------------------------------------------------------


def stufe_pruefen(lauf: Lauf, adapter, fall_name: str, stufe: int,
                  dateien: list[str], live: bool) -> None:
    k = konfig().llm
    verzeichnis = WURZEL / "demo" / "faelle" / fall_name
    ticket = json.loads((verzeichnis / "ticket.json").read_text(encoding="utf-8"))
    dokumente = [laden(verzeichnis / n, f"D{i}") for i, n in enumerate(dateien, start=1)]

    fall = fall_anlegen("F-DIFF", ticket, dokumente)
    pseudonymisieren(fall)
    schema = schema_laden("preiserhoehung")

    def hole(aufgabe: str, modell: str, eingabe: dict[str, Any]) -> tuple[Aufruf, Aufruf | None]:
        pfad = cache.pfad_fuer(aufgabe, modell, k.prompt_version, eingabe)
        gecacht = cache.lesen(pfad)
        if gecacht is None:
            raise SystemExit(
                f"Kein Cache-Eintrag fuer {aufgabe} in {fall_name} Stufe {stufe}:\n"
                f"  {pfad.name}\n"
                f"  -> zuerst tools/{fall_name.split('_')[0]}_cache.py laufen lassen."
            )
        if pfad.name not in lauf.memo:
            lauf.geplant += 1
            lauf.cache_kosten_cent += gecacht.kosten_cent
        if not live:
            lauf.memo.setdefault(pfad.name, gecacht)
            return gecacht, None
        if (schon := lauf.memo.get(pfad.name)) is not None:
            return gecacht, schon
        echt = adapter._live(aufgabe, modell, eingabe)
        lauf.memo[pfad.name] = echt
        lauf.aufrufe += 1
        lauf.kosten_cent += echt.kosten_cent
        lauf.dauer_ms += echt.dauer_ms
        lauf.detail.append({"fall": fall_name, "stufe": stufe, "aufgabe": aufgabe, "modell": modell,
                            "dauer_ms": echt.dauer_ms, "kosten_cent": echt.kosten_cent})
        return gecacht, echt

    klass_typ: dict[str, str] = {}
    for d in fall.dokumente:
        eingabe = {"seiten": seiten_eingabe(d.seiten)}
        gecacht, echt = hole("classify_doc", k.modell_klassifikation, eingabe)
        c_k = Klassifikation.model_validate(gecacht.ausgabe)
        klass_typ[d.dok_id] = c_k.dokumenttyp
        if echt is not None:
            l_k = Klassifikation.model_validate(echt.ausgabe)
            c_typ, c_frag = validiere_klassifikation(c_k)
            l_typ, l_frag = validiere_klassifikation(l_k)
            if c_typ != l_typ:
                lauf.add(Befund("KLASSE", fall_name, stufe, "classify_doc", d.dok_id,
                                cache_wert=c_typ.value, live_wert=l_typ.value,
                                detail=f"live-Konfidenz {l_k.konfidenz:.2f}"
                                       f"{' -> Rueckfrage' if l_frag else ''}"))
            elif l_frag and not c_frag:
                lauf.add(Befund("KONFIDENZ", fall_name, stufe, "classify_doc", d.dok_id,
                                cache_wert=f"{c_k.konfidenz:.2f}", live_wert=f"{l_k.konfidenz:.2f}",
                                detail="live faellt unter die Schwelle -> sonstiges + Rueckfrage"))

        sd = schema.dokumenten_soll.nach_typ(Dokumenttyp(klass_typ[d.dok_id]))
        if not sd or not sd.felder:
            continue
        eingabe = {
            "dokumenttyp": klass_typ[d.dok_id],
            "seiten": seiten_eingabe(d.seiten),
            "felder": feld_eingabe(sd.felder),
        }
        gecacht, echt = hole("extract_fields", k.modell_extraktion, eingabe)
        if echt is not None:
            vergleiche_extraktion(
                lauf, fall_name, stufe, d.dok_id,
                Extraktion.model_validate(gecacht.ausgabe),
                Extraktion.model_validate(echt.ausgabe),
                sd.felder, d.seiten,
            )

    eingabe = {
        "freitext": fall.eingang.freitext_pseudonym,
        "doktypen": sorted(klass_typ[d.dok_id] for d in fall.dokumente),
        "taxonomie": sorted(taxonomie()),
    }
    gecacht, echt = hole("propose_fallgruppe", k.modell_extraktion, eingabe)
    if echt is not None:
        tax = {i: {} for i in taxonomie()}
        txt = fall.eingang.freitext_pseudonym or ""
        c_v = validiere_vorschlaege(Vorschlaege.model_validate(gecacht.ausgabe), tax, txt)
        l_v = validiere_vorschlaege(Vorschlaege.model_validate(echt.ausgabe), tax, txt)
        c_top = c_v[0].fallgruppe_id if c_v else None
        l_top = l_v[0].fallgruppe_id if l_v else None
        if c_top != l_top:
            lauf.add(Befund("FALLGRUPPE", fall_name, stufe, "propose_fallgruppe", "T0",
                            cache_wert=c_top, live_wert=l_top))
        roh = len(Vorschlaege.model_validate(echt.ausgabe).vorschlaege)
        if roh and not l_v:
            lauf.add(Befund("VERWORFEN", fall_name, stufe, "propose_fallgruppe", "T0",
                            detail=f"{roh} Vorschlaege, alle vom Validator verworfen"))


# --------------------------------------------------------------------------


def main() -> None:
    live = "--live" in sys.argv
    nur = None
    if "--fall" in sys.argv:
        nur = sys.argv[sys.argv.index("--fall") + 1]

    # Sweep-Knoepfe (31 par. 4): vor dem Adapter setzen, der liest die Konfiguration
    # beim Bau. Der Bericht bekommt dann einen eigenen Namen, damit B1 stehen bleibt.
    k = konfig().llm
    variante = ""
    if "--effort" in sys.argv:
        k.effort = sys.argv[sys.argv.index("--effort") + 1]
        variante += f"_effort-{k.effort}"
    if "--extraktion" in sys.argv:
        k.modell_extraktion = sys.argv[sys.argv.index("--extraktion") + 1]
        variante += f"_{k.modell_extraktion}"

    adapter = None
    if live:
        from fallpruefer.adapter.anthropic_adapter import AnthropicAdapter, schluessel_vorhanden
        if not schluessel_vorhanden():
            raise SystemExit("--live ohne ANTHROPIC_API_KEY. Ohne Schluessel ist nur der "
                             "Trockenlauf moeglich (Aufrufplan + Kostenschaetzung).")
        # cache_lesen=False: jeder Aufruf geht wirklich raus und NICHTS wird
        # geschrieben — cache/llm/ bleibt unangetastet.
        adapter = AnthropicAdapter(cache_lesen=False)

    lauf = Lauf()
    for name in FAELLE:
        if nur and name != nur:
            continue
        for i, dateien in enumerate(stufen(WURZEL / "demo" / "faelle" / name), start=1):
            stufe_pruefen(lauf, adapter, name, i, dateien, live)

    if not live:
        print("Trockenlauf — jeder Cache-Eintrag ist vorhanden und der Aufrufplan steht.")
        print(f"Modelle: klassifikation={k.modell_klassifikation}  "
              f"extraktion={k.modell_extraktion}  prompt_version={k.prompt_version}")
        print(f"{lauf.geplant} Live-Aufrufe wuerde --live machen "
              f"({len(list(cache.cache_verzeichnis().glob('*.json')))} Dateien liegen in cache/llm/).")
        print(f"Grobe Schaetzung: {lauf.cache_kosten_cent:.1f} ct — aber die Kostenwerte im "
              f"Cache sind von Hand gesetzt, nicht gemessen. Genau das misst --live mit.")
        print("\nDann:  ANTHROPIC_API_KEY=... .venv/bin/python tools/live_diff.py --live")
        return

    bericht = WURZEL / "analysis" / "detail" / f"live_diff{variante}.json"
    bericht.parent.mkdir(parents=True, exist_ok=True)
    bericht.write_text(json.dumps({
        "aufrufe": lauf.aufrufe,
        "kosten_cent": round(lauf.kosten_cent, 3),
        "dauer_ms": lauf.dauer_ms,
        "felder_geprueft": lauf.felder_geprueft,
        "felder_gleich": lauf.felder_gleich,
        "modelle": {"klassifikation": k.modell_klassifikation,
                    "extraktion": k.modell_extraktion,
                    "prompt_version": k.prompt_version,
                    "effort": k.effort or "high (Voreinstellung)"},
        "aufrufe_detail": lauf.detail,
        "befunde": [b.__dict__ for b in lauf.befunde],
    }, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    print(f"{lauf.aufrufe} Live-Aufrufe · {lauf.kosten_cent:.2f} ct · "
          f"{lauf.dauer_ms / 1000:.1f} s  (effort {k.effort or 'high, Voreinstellung'})")
    je: dict[tuple[str, str], list[int]] = {}
    for z in lauf.detail:
        je.setdefault((z["aufgabe"], z["modell"]), []).append(z["dauer_ms"])
    for (auf, mod), ds in sorted(je.items()):
        ds.sort()
        print(f"  {auf:18s} {mod:18s} n={len(ds):2d}  median {ds[len(ds) // 2] / 1000:.1f} s"
              f"  min {ds[0] / 1000:.1f}  max {ds[-1] / 1000:.1f}")
    print(f"Felder: {lauf.felder_gleich}/{lauf.felder_geprueft} identisch zum Cache")
    if not lauf.befunde:
        print("\nKeine Abweichung. Der Cache bildet die Live-Strecke ab.")
    else:
        nach_art: dict[str, list[Befund]] = {}
        for b in lauf.befunde:
            nach_art.setdefault(b.art, []).append(b)
        # defect classes first, then the merely-different ones
        rang = {"VERWORFEN": 0, "TYP": 1, "ZITAT": 2, "CACHE_VERWORFEN": 3, "UNBEKANNT": 4,
                "KLASSE": 5, "KONFIDENZ": 6, "FALLGRUPPE": 7, "FEHLT": 8, "WERT": 9, "ZUSATZ": 10}
        for art in sorted(nach_art, key=lambda a: rang.get(a, 99)):
            gruppe = nach_art[art]
            print(f"\n{art} ({len(gruppe)})")
            for b in gruppe:
                ort = f"{b.fall}/{b.stufe} {b.dok}" + (f".{b.feld}" if b.feld else "")
                print(f"  {ort}")
                if b.cache_wert is not None or b.live_wert is not None:
                    print(f"      cache={b.cache_wert!r}  live={b.live_wert!r}")
                if b.detail:
                    print(f"      {b.detail}")
    print(f"\nBericht: {bericht.relative_to(WURZEL)}")


if __name__ == "__main__":
    main()
