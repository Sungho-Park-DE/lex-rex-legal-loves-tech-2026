"""Der Moment mit der Auftraggeberin im Vorführmodus: ein Dokument, das das Werkzeug nicht kennt.

Ohne Schlüssel (`cache`-Modus, tools/demo_start.py) ist ein Cache-Miss ein
erwarteter Zustand. Bis heute Abend war er ein HTTP 500 mit dem Text
„CacheFehlt: Kein Cache-Eintrag: extract_fields_…json (cache-only Modus —
entweder ANTHROPIC_API_KEY setzen oder die Datei anlegen: /Users/…)" — und
das UI zeigt `detail` als Toast. Ein Dateipfad auf der Bühne, in dem Moment,
in dem die Auftraggeberin die Maus hat.

Jetzt: 409 mit einem Satz für die Beraterin, der Pfad geht ins Log.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from fallpruefer import store
from fallpruefer.api import UNBEKANNTES_DOKUMENT, app
from fallpruefer.konfig import WURZEL, konfig

SEEPARK = WURZEL / "demo" / "faelle" / "seepark_seite_fehlt"


@pytest.fixture(autouse=True)
def cache_only(tmp_path, monkeypatch):
    # Auch wenn auf der Maschine ein Schlüssel liegt: dieser Test misst den Vorführmodus.
    monkeypatch.setattr(konfig().llm, "nur_cache", True)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(store, "pfad", lambda: tmp_path / "faelle.jsonl")


def _anlegen(klient: TestClient, case_id: str) -> None:
    ticket = json.loads((SEEPARK / "ticket.json").read_text(encoding="utf-8"))
    antwort = klient.post("/faelle", json={
        "freitext": ticket["freitext"],
        "anhaenge": [{"dateiname": n, "text": (SEEPARK / n).read_text(encoding="utf-8")}
                     for n in ticket["anhaenge"]],
        "kanal": "vbs", "anbieter": ticket["anbieter"], "branche": "fitness",
        "identitaet": ticket["identitaet"], "case_id": case_id,
    })
    assert antwort.status_code == 200, antwort.text


def test_unbekanntes_dokument_ist_ein_satz_kein_pfad():
    klient = TestClient(app)
    _anlegen(klient, "CACHEMISS-1")
    antwort = klient.post("/faelle/CACHEMISS-1/dokumente", json={"anhaenge": [
        {"dateiname": "juror.md", "text": "Ein Vertrag, den das Werkzeug noch nie gesehen hat."}
    ]})
    assert antwort.status_code == 409, antwort.text
    detail = antwort.json()["detail"]
    assert detail == UNBEKANNTES_DOKUMENT
    for verboten in ("cache", "Cache", "ANTHROPIC", ".json", "/Users", "CacheFehlt"):
        assert verboten not in detail, f"Technik im Satz für die Beraterin: {verboten!r}"


def test_die_bekannten_unterlagen_laufen_im_selben_modus_durch():
    """Die Gegenprobe: derselbe Modus, die vorbereiteten Dokumente — kein 409."""
    klient = TestClient(app)
    _anlegen(klient, "CACHEMISS-2")
    seite2 = (SEEPARK / "bedingungen_seite2_nachgereicht.md").read_text(encoding="utf-8")
    antwort = klient.post("/faelle/CACHEMISS-2/dokumente", json={"anhaenge": [
        {"dateiname": "bedingungen_seite2_nachgereicht.md", "text": seite2}
    ]})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["einordnung"] == "wirksam"
