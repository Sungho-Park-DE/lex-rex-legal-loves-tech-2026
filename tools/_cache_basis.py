"""Shared writer for the hand-authored `cache/llm/` entries of a fiction case.

Why the cache files are computed rather than checked in by hand: the key is
`hash(text_pseudonym + field spec)` (contract §9), so it changes whenever the
document text, the pseudonymisation or the Soll field list changes. The
*content* stays hand-written per case — these are the adapter outputs a model
would have to produce — and only the filenames are derived.

One helper, one behaviour: every case's cache tool calls `schreiben()` so that
a change to the adapter's input shape cannot leave one case's recordings valid
and another's stale.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fallpruefer.adapter import cache  # noqa: E402
from fallpruefer.adapter.basis import Aufruf  # noqa: E402
from fallpruefer.adapter.cache_adapter import feld_eingabe, seiten_eingabe  # noqa: E402
from fallpruefer.dokumente import laden  # noqa: E402
from fallpruefer.konfig import konfig  # noqa: E402
from fallpruefer.pipeline import fall_anlegen, pseudonymisieren  # noqa: E402
from fallpruefer.schema import schema_laden, taxonomie  # noqa: E402
from fallpruefer.vokabular import Dokumenttyp  # noqa: E402


def schreiben(
    verzeichnis: Path,
    klassifikation: dict[str, dict],
    extraktion: dict[str, list[tuple]],
    vorschlaege: dict,
    dateien: list[str] | None = None,
    fallgruppe_id: str = "preiserhoehung",
) -> list[str]:
    """`dateien` overrides the ticket's attachment list — a Nachreichung stage
    is the same case with more documents, and its recordings have to exist
    before the second run can replay."""
    k = konfig().llm
    ticket = json.loads((verzeichnis / "ticket.json").read_text(encoding="utf-8"))
    namen = dateien if dateien is not None else ticket["anhaenge"]
    dokumente = [laden(verzeichnis / n, f"D{i}") for i, n in enumerate(namen, start=1)]

    fall = fall_anlegen("F-CACHE", ticket, dokumente)
    pseudonymisieren(fall)
    schema = schema_laden(fallgruppe_id)
    geschrieben: list[str] = []

    for d in fall.dokumente:
        if d.dok_id not in klassifikation:
            raise SystemExit(f"keine Klassifikation für {d.dok_id} ({d.dateiname})")
        eingabe = {"seiten": seiten_eingabe(d.seiten)}
        pfad = cache.pfad_fuer("classify_doc", k.modell_klassifikation, k.prompt_version, eingabe)
        cache.schreiben(pfad, Aufruf(
            aufgabe="classify_doc", modell=k.modell_klassifikation,
            prompt_version=k.prompt_version, eingabe=eingabe,
            ausgabe=klassifikation[d.dok_id], dauer_ms=610, kosten_cent=0.05,
        ))
        geschrieben.append(pfad.name)

        typ = klassifikation[d.dok_id]["dokumenttyp"]
        sd = schema.dokumenten_soll.nach_typ(Dokumenttyp(typ))
        if not sd or not sd.felder:
            continue
        eingabe = {
            "dokumenttyp": typ,
            "seiten": seiten_eingabe(d.seiten),
            "felder": feld_eingabe(sd.felder),
        }
        ausgabe = {"felder": [
            {"feld_id": fid, "wert": wert, "zitat": zitat, "seite": seite}
            for fid, wert, zitat, seite in extraktion[d.dok_id]
        ]}
        pfad = cache.pfad_fuer("extract_fields", k.modell_extraktion, k.prompt_version, eingabe)
        cache.schreiben(pfad, Aufruf(
            aufgabe="extract_fields", modell=k.modell_extraktion,
            prompt_version=k.prompt_version, eingabe=eingabe, ausgabe=ausgabe,
            dauer_ms=4200, kosten_cent=1.1,
        ))
        geschrieben.append(pfad.name)

    doktypen = sorted(klassifikation[d.dok_id]["dokumenttyp"] for d in fall.dokumente)
    eingabe = {
        "freitext": fall.eingang.freitext_pseudonym,
        "doktypen": doktypen,
        "taxonomie": sorted(taxonomie()),
    }
    pfad = cache.pfad_fuer("propose_fallgruppe", k.modell_extraktion, k.prompt_version, eingabe)
    cache.schreiben(pfad, Aufruf(
        aufgabe="propose_fallgruppe", modell=k.modell_extraktion,
        prompt_version=k.prompt_version, eingabe=eingabe, ausgabe=vorschlaege,
        dauer_ms=3100, kosten_cent=0.6,
    ))
    geschrieben.append(pfad.name)
    return geschrieben


def melden(geschrieben: list[str]) -> None:
    print(f"{len(geschrieben)} Cache-Dateien geschrieben:")
    for n in geschrieben:
        print("  ", n)
