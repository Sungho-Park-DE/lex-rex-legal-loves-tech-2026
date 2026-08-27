"""Demo beenden — der Knopf unter dem Radar (Sungho, 27. Aug).

Der Store vergisst nicht (33 §8 Nr. 8): jede Probe, die Gate 3 fährt, hebt
FitPoint 24 auf 3 und verbrennt den Radar-Beat; und der Bühnen-Edit an der
Schemadatei bleibt in der Arbeitskopie stehen. Beides hat bis heute nach jeder
Probe ein Mensch von Hand zurückgesetzt. Hier tut es ein POST — die Saat
in-process (damit ein Test den Store umleiten kann), und aus HEAD kommt genau
**eine** Datei zurück, die des Bühnen-Edits; nichts sonst im Baum wird angefasst.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

from fallpruefer import store
from fallpruefer.konfig import WURZEL

# Die Datei, die in Akt 2 im Editor steht (33 §8 Nr. 6) — relativ zur Wurzel.
SCHEMA_DATEI = Path("schemas") / "preiserhoehung.json"
FITPOINT = "fitpoint 24"


def _radar_seed():
    spec = importlib.util.spec_from_file_location("radar_seed", WURZEL / "tools" / "radar_seed.py")
    modul = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modul)
    return modul


def radar_neu_saeen() -> tuple[int, int]:
    """Store leeren, Hintergrundzeilen neu schreiben → (Zeilen gesamt, davon FitPoint 24)."""
    _radar_seed().saeen(zuruecksetzen=True)
    saetze = store.lesen()
    return len(saetze), sum(1 for s in saetze if s.get("anbieter") == FITPOINT)


def schema_wiederherstellen(datei: Path = SCHEMA_DATEI, wurzel: Path = WURZEL) -> bool:
    """Die eine Datei des Bühnen-Edits aus HEAD zurückholen. True, wenn sie verändert war.

    `git checkout -- <datei>` und nichts Breiteres: im geteilten Baum liegt
    sonst fremde Arbeit (Register §0a). Der Motor liest die Datei beim nächsten
    Zugriff neu, weil der Checkout die mtime hebt (schema.py `_CACHE`).
    """
    geaendert = subprocess.run(["git", "diff", "--quiet", "--", str(datei)], cwd=wurzel).returncode != 0
    if geaendert:
        subprocess.run(["git", "checkout", "--", str(datei)], cwd=wurzel, check=True)
    return geaendert
