"""Regenerate the UI fixtures from the engine.

The fixture is the contract the Lovable frontend builds against, so it must be
what `GET /faelle/{id}` actually returns — not a hand-written approximation of
it. It started as one (no engine existed yet); from here it is generated, and
`tests/test_rung1.py::test_api_fallakte_hat_fixture_struktur` fails if the two
drift apart.

Two fixtures, because one is not enough to build the UI against:

  drehkreuz_fallakte.json  F-2026-0001  the happy path — everything present, one
                                        run, no Nachforderung.
  seepark_fallakte.json    F-2026-0002  the flip — arrives incomplete („unklar –
                                        es fehlt …"), Gate 1 produces a
                                        Nachforderung, the missing page is handed
                                        in, and the verdict changes to `wirksam`.
  nordlicht_fallakte.json  F-2026-0003  the open case — the ticket arrives with
                                        ONLY the Erhöhungsschreiben, Gate 1 has
                                        asked, nothing has come back yet.

The second one exists because the first cannot show two of the beats the UI has
to render: `laeufe[]` has a single entry there and `nachforderungen[]` is empty,
so a frontend built only against F-2026-0001 renders a one-chip history and
hides the Gate-1 panel — and „the flip" (14 §7, a beat that must never be cut)
is unbuildable and untestable. It also happens to be the case that ends in
`wirksam`, so the green verdict and the Kündigung letter get a shape too.

The third exists because the other two are both *finished*: every consumer-side
gap is resolved, `hero.vollstaendigkeit.verbraucher` is empty in both, and the
verdict is final. Everything the UI renders only while a case is still open was
therefore unreachable from any fixture — the yellow „unklar – es fehlt …" hero,
consumer-side Vollständigkeits-Posten, an OPEN Nachforderung, and the
„Existiert nicht" action (V-N2), which by design only attaches to open
consumer-side items. K6 fixed that action's gate, and the fix was untestable:
no fixture could make the button appear at all.

Run after changing the demo documents, the schema file or the view model:

    .venv/bin/python tools/drehkreuz_cache.py     # keys depend on the text
    .venv/bin/python tools/seepark_cache.py
    .venv/bin/python tools/demo_fixture.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fallpruefer import ansicht  # noqa: E402
from fallpruefer.dokumente import laden  # noqa: E402
from fallpruefer.konfig import WURZEL  # noqa: E402
from fallpruefer.pipeline import (  # noqa: E402
    fall_aus_verzeichnis,
    fall_speichern,
    gate1_nachforderung,
    nachreichung,
)
from fallpruefer.schema import schema_laden  # noqa: E402

FIXTURES = WURZEL / "demo" / "fixtures"


def bauen(fall) -> dict:
    fall_speichern(fall)
    return ansicht.bauen(fall, schema_laden(fall.schema_.fallgruppe_id)).model_dump(mode="json")


def happy_path() -> dict:
    fall = fall_aus_verzeichnis(WURZEL / "demo" / "faelle" / "drehkreuz", "F-2026-0001")
    # the fixture shows a finished case: Gate 2 confirmed
    fall.fallgruppe.bestaetigt = True
    return bauen(fall)


def flip() -> dict:
    """Stage 1 -> Gate 1 -> Nachreichung, i.e. exactly the path the demo takes.

    The Nachreichung goes through `pipeline.nachreichung()` rather than loading
    all four documents at once: loading them together would produce the right
    final verdict with only ONE entry in `laeufe[]`, which is the very thing
    this fixture exists to carry.
    """
    verzeichnis = WURZEL / "demo" / "faelle" / "seepark_seite_fehlt"
    fall = fall_aus_verzeichnis(verzeichnis, "F-2026-0002")
    fall.fallgruppe.bestaetigt = True
    nachforderung = gate1_nachforderung(fall)
    nachgereicht = [laden(verzeichnis / "bedingungen_seite2_nachgereicht.md", "D4")]
    fall = nachreichung(fall, nachgereicht, nachforderung_id=nachforderung.id)
    return bauen(fall)


def offen() -> dict:
    """Stage 1 + Gate 1, and then — nothing. The case is still waiting.

    Same start as the flip, deliberately stopped before the Nachreichung: the
    open state is not a truncated flip but its own thing. The Nachforderung
    keeps status `offen` (the advisor has not even marked it „angefordert"),
    so the panel's action buttons have something real to act on.
    """
    fall = fall_aus_verzeichnis(
        WURZEL / "demo" / "faelle" / "nordlicht_agb_fehlen", "F-2026-0003"
    )
    fall.fallgruppe.bestaetigt = True
    gate1_nachforderung(fall)
    return bauen(fall)


def schreiben(ziel: Path, daten: dict) -> None:

    # The fixture is a *shape* contract, not a case: the frontend needs the keys
    # to be stable, not the clock. Wall-clock run times made every regeneration
    # a git diff, so anyone who ran the tool as the handoff says to had to
    # decide whether a one-line timestamp change was a real drift. Real event
    # logs keep real time (14 §5) — this sample does not.
    for i, lauf in enumerate(daten.get("laeufe", [])):
        lauf["zeit"] = f"2026-08-20T09:{i:02d}:00+02:00"
    for i, n in enumerate(daten.get("nachforderungen", [])):
        if n.get("zeit"):
            n["zeit"] = f"2026-08-20T09:{i:02d}:00+02:00"
    # R6: dasselbe für das Protokoll — bisher trug jede Zeile die Wanduhr der
    # Regenerierung („25.08., 01:22"), also weder den Fall noch den Stichtag.
    for i, e in enumerate(daten.get("protokoll", [])):
        e["zeit"] = f"2026-08-20T09:{i % 60:02d}:00+02:00"

    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(daten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # every quote must be findable in the page it points at — that is the whole
    # click-to-highlight contract, and the UI must never have to guess
    seiten = {(d["dok_id"], s["nr"]): s["text_original"]
              for d in daten["dokumente"] for s in d["seiten"]}
    fehler: list[str] = []

    def pruefe(z: dict) -> None:
        text = seiten.get((z["dok_id"], z["seite"]), "")
        if z["zitat"] not in text:
            fehler.append(f"{z['dok_id']}/{z['seite']}: {z['zitat'][:70]!r}")

    def sammeln(o) -> None:
        if isinstance(o, dict):
            if {"dok_id", "seite", "zitat"} <= set(o):
                pruefe(o)
            for v in o.values():
                sammeln(v)
        elif isinstance(o, list):
            for v in o:
                sammeln(v)

    sammeln(daten)
    print(f"{ziel.relative_to(WURZEL)} — {ziel.stat().st_size // 1024} KB · "
          f"{len(daten.get('laeufe', []))} Lauf/Läufe · "
          f"{len(daten.get('nachforderungen', []))} Nachforderung(en) · "
          f"„{daten['hero']['einordnung']['label']}\"")
    if fehler:
        print("  ZITATE NICHT IM QUELLTEXT GEFUNDEN:")
        for f in fehler:
            print("   ", f)
        raise SystemExit(1)
    print("  alle Zitate als Teilstring ihrer Seite verifiziert")


# Der zweite Ablageort derselben erzeugten Dateien. Wer nur hier regeneriert,
# lässt alles unter lex-rex.lovable.app auf dem alten Stand — am 24. Aug lag
# die Kopie zweimal einen halben Tag hinter dem Motor. `--ui` kopiert und
# schreibt dazu `radar.json` aus dem Store (nach `tools/radar_seed.py`).
UI_FIXTURES = Path.home() / "dev" / "llt26-ui" / "public" / "fixtures"
ZUORDNUNG = {
    "drehkreuz_fallakte.json": "faelle/F-2026-0001.json",
    "seepark_fallakte.json": "faelle/F-2026-0002.json",
    "nordlicht_fallakte.json": "faelle/F-2026-0003.json",
}


def ins_ui_kopieren() -> None:
    if not UI_FIXTURES.exists():
        print(f"UI-Repo nicht da ({UI_FIXTURES}) — nur demo/fixtures/ geschrieben")
        return
    import shutil

    for quelle, ziel in ZUORDNUNG.items():
        shutil.copyfile(FIXTURES / quelle, UI_FIXTURES / ziel)
        print(f"  {quelle} → {ziel}")
    from fallpruefer import store

    radar = store.radar()
    if not radar["cluster"]:
        print("  radar.json NICHT geschrieben: Store leer — erst tools/radar_seed.py")
        return
    (UI_FIXTURES / "radar.json").write_text(
        json.dumps(radar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  radar.json ← GET /radar ({radar['faelle_gesamt']} Fälle,"
          f" {len(radar['markierte_faelle'])} markiert)")


def main() -> None:
    schreiben(FIXTURES / "drehkreuz_fallakte.json", happy_path())
    schreiben(FIXTURES / "seepark_fallakte.json", flip())
    schreiben(FIXTURES / "nordlicht_fallakte.json", offen())
    if "--ui" in sys.argv:
        ins_ui_kopieren()


if __name__ == "__main__":
    main()
