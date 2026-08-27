"""Der Test für die R1-Klasse: jede Route, die das UI aufruft, muss im Backend
existieren.

Am 24. Aug waren Gate 1, Gate 2, Gate 4 und Abschluss im Live-Modus zwei Tage
lang 404 (`28` F1): `api.ts` postete auf ein `/aktionen/`-Präfix, das es nie
gab. 343 Tests waren grün, weil kein Test die Grenze zwischen den beiden
Repos ansieht — und der Fixture-Modus ersetzt jeden Schreibzugriff durch einen
Toast, kann das also prinzipbedingt nicht finden.

Dieser Test liest `src/lib/api.ts` im UI-Repo und hält jeden Pfad gegen
`app.routes`. Er ist bewusst grob (Regex, keine TypeScript-Analyse): er soll
den einen Fehler fangen, der schon einmal passiert ist, nicht die Sprache
parsen. Fehlt das UI-Repo auf der Maschine, wird übersprungen — dann sagt der
Skip-Grund, was nicht geprüft wurde.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from fallpruefer.api import app

API_TS = Path.home() / "dev" / "llt26-ui" / "src" / "lib" / "api.ts"

pytestmark = pytest.mark.skipif(
    not API_TS.exists(),
    reason=f"UI-Repo nicht auf dieser Maschine ({API_TS}) — Routen-Grenze ungeprüft",
)


def _backend_pfade() -> set[str]:
    return {r.path for r in app.routes if hasattr(r, "path")}


def _ui_segmente(src: str) -> set[str]:
    """Alles, was nach `/faelle/${…caseId…}/` kommt — in den Spezialfunktionen
    und in der Aktion→Route-Tabelle `AKTION_PFAD`."""
    segmente = set(re.findall(
        r"\$\{BASE\}/faelle/\$\{encodeURIComponent\(caseId\)\}/([a-z0-9-]+)", src))
    tabelle = re.search(r"AKTION_PFAD[^{]*\{([^}]*)\}", src, re.S)
    if tabelle:
        segmente |= set(re.findall(r':\s*"([a-z0-9-]+)"', tabelle.group(1)))
    return segmente


def _ohne_kommentare(src: str) -> str:
    """Der Kommentar in api.ts, der das Verbot erklärt, nennt das Präfix — der
    Test darf nur Code sehen, nicht seine eigene Begründung."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(z.split("//")[0] for z in src.split("\n"))


def test_kein_aktionen_praefix_mehr():
    """Der Bug selbst, wörtlich."""
    assert "/aktionen/" not in _ohne_kommentare(API_TS.read_text(encoding="utf-8")), (
        "api.ts postet wieder auf /aktionen/ — dieses Präfix hat das Backend nie gehabt (28 F1)")


def test_jede_ui_route_existiert_im_backend():
    src = API_TS.read_text(encoding="utf-8")
    segmente = _ui_segmente(src)
    assert segmente, "keine /faelle/{id}/… Pfade in api.ts gefunden — Regex oder Datei geändert?"
    backend = _backend_pfade()
    fehlend = sorted(s for s in segmente if f"/faelle/{{case_id}}/{s}" not in backend)
    assert not fehlend, f"UI ruft Routen auf, die das Backend nicht hat: {fehlend}"


def test_die_beiden_lesenden_routen_existieren():
    src = API_TS.read_text(encoding="utf-8")
    backend = _backend_pfade()
    if "${BASE}/radar" in src:
        assert "/radar" in backend
    if "${BASE}/faelle/${encodeURIComponent(caseId)}`" in src:
        assert "/faelle/{case_id}" in backend


def test_die_tabelle_deckt_jeden_aktionsnamen():
    """`AKTION_PFAD` ist als `Record<AktionName, string>` typisiert — TypeScript
    erzwingt Vollständigkeit. Hier nur die Gegenprobe, dass kein Eintrag auf
    einen Pfad zeigt, den es nicht gibt (Tippfehler im Wert)."""
    src = API_TS.read_text(encoding="utf-8")
    tabelle = re.search(r"AKTION_PFAD[^{]*\{([^}]*)\}", src, re.S)
    if not tabelle:
        pytest.skip("kein AKTION_PFAD in api.ts — generischer Sender wurde entfernt")
    backend = _backend_pfade()
    for name, pfad in re.findall(r'(\w+):\s*"([a-z0-9-]+)"', tabelle.group(1)):
        assert f"/faelle/{{case_id}}/{pfad}" in backend, f"{name} → /{pfad} existiert nicht"
