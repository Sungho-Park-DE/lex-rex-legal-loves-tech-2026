"""28 F8: eine Leitfaden-Frage, die die Beraterin gerade beantwortet hat, stand
weiter unter „Offene Punkte" als „Frage ans Gespräch" — direkt neben dem
Panel, in dem sie eben als beantwortet abgehakt wurde. Nicht die Oberfläche
war schuld: `ansicht._offene_punkte` kannte die Antworten nicht.

Der Fall: Seepark, P14 (langes widerspruchsloses Zahlen) bekommt „8 Monate".
Danach ist P14 WERTUNG — die Wertungsfrage an die Beraterin bleibt zu Recht
offen —, aber die Gesprächsfrage „Seit wie vielen Monaten …?" ist erledigt.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from fallpruefer import store
from fallpruefer.api import app
from fallpruefer.konfig import WURZEL

SEEPARK = WURZEL / "demo" / "faelle" / "seepark_seite_fehlt"


@pytest.fixture(autouse=True)
def eigener_store(tmp_path, monkeypatch):
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


def _fragen_p14(ansicht: dict) -> list[dict]:
    return [o for o in ansicht["offene_punkte"]
            if o.get("pruefpunkt_id") == "P14" and o["art"]["code"] == "frage"]


def test_beantwortete_gespraechsfrage_steht_nicht_mehr_unter_offene_punkte():
    klient = TestClient(app)
    _anlegen(klient, "OFFEN-P14")
    vorher = klient.get("/faelle/OFFEN-P14").json()
    frage = next(f for f in vorher["leitfaden"]["fragen"] if f["pruefpunkt_id"] == "P14")
    assert frage["status"]["code"] == "offen"
    feld = frage["fuellt"][0]

    antwort = klient.post("/faelle/OFFEN-P14/leitfaden", json={"antworten": {feld: 8}})
    assert antwort.status_code == 200, antwort.text

    nachher = klient.get("/faelle/OFFEN-P14").json()
    frage = next(f for f in nachher["leitfaden"]["fragen"] if f["pruefpunkt_id"] == "P14")
    assert frage["status"]["code"] != "offen", "die Antwort ist angekommen"
    assert _fragen_p14(nachher) == [], (
        "die beantwortete Gesprächsfrage steht noch unter Offene Punkte (28 F8)")
    # die Wertungsfrage an die Beraterin bleibt — das ist ihr Urteil, nicht die Antwort der Kundin
    zustand = next(e for st in nachher["pruefpfad"]["stufen"] for e in st["pruefpunkte"]
                   if e["pruefpunkt_id"] == "P14")["zustand"]["code"]
    if zustand == "WERTUNG":
        assert any(o.get("pruefpunkt_id") == "P14" and o["art"]["code"] == "wertung"
                   for o in nachher["offene_punkte"])
