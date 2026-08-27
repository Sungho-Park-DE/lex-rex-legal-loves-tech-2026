"""Der Leitfaden-Endpunkt, über HTTP — den Weg, den die UI geht.

Diese Datei existiert wegen eines Fehlers, den 259 Tests nicht hatten und
`ruff` in einer Sekunde fand: `leitfaden_antworten` fehlte in der Importliste
von `api.py`. Der Endpunkt war registriert, die Suite grün, das Modul dahinter
vollständig getestet — und der erste echte Aufruf hätte einen `NameError`
geworfen, weil kein Test den Endpunkt je über HTTP angefasst hat.

`18` #45 hat dieselbe Lehre schon einmal aufgeschrieben: „every cold pass of
this build should go over HTTP, not in-process — that is the path the UI
takes."
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from fallpruefer.api import app
from fallpruefer.konfig import WURZEL

DREHKREUZ = WURZEL / "demo" / "faelle" / "drehkreuz"


@pytest.fixture
def klient():
    return TestClient(app)


@pytest.fixture
def fall_id(klient):
    ticket = json.loads((DREHKREUZ / "ticket.json").read_text(encoding="utf-8"))
    anhaenge = [{"dateiname": n, "text": (DREHKREUZ / n).read_text(encoding="utf-8")}
                for n in ticket["anhaenge"]]
    antwort = klient.post("/faelle", json={
        "freitext": ticket["freitext"], "anhaenge": anhaenge, "kanal": "vbs",
        "anbieter": ticket["anbieter"], "identitaet": ticket["identitaet"],
        "case_id": "F-2026-9601",
    })
    assert antwort.status_code == 200, antwort.text
    return antwort.json()["case_id"]


def test_eine_antwort_haengt_einen_lauf_an(klient, fall_id):
    antwort = klient.post(f"/faelle/{fall_id}/leitfaden",
                          json={"antworten": {"gespraech.monate_erhoeht_gezahlt": 8}})
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert daten["case_id"] == fall_id
    assert daten["strittig"] == []
    assert daten["run_id"]

    akte = klient.get(f"/faelle/{fall_id}").json()
    assert [lauf["trigger"]["code"] for lauf in akte["laeufe"]] == ["initial", "leitfaden_antwort"]


def test_ein_widerspruch_kommt_als_strittig_zurueck(klient, fall_id):
    antwort = klient.post(f"/faelle/{fall_id}/leitfaden",
                          json={"antworten": {"vertrag.agb_einbezogen_hinweis": False}})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["strittig"] == ["vertrag.agb_einbezogen_hinweis"]


def test_ein_feld_ausserhalb_des_leitfadens_wird_mit_400_abgewiesen(klient, fall_id):
    antwort = klient.post(f"/faelle/{fall_id}/leitfaden",
                          json={"antworten": {"agb.preisklausel_text": "was ich gern haette"}})
    assert antwort.status_code == 400
    assert "kein Leitfaden-Feld" in antwort.json()["detail"]


def test_ein_ungueltiger_wert_schreibt_auch_die_gueltige_antwort_nicht(klient, fall_id):
    """Der Stapel ist atomar, und das muss über HTTP genauso gelten wie im
    Modul — die UI schickt mehrere Antworten in einer Anfrage."""
    antwort = klient.post(f"/faelle/{fall_id}/leitfaden", json={"antworten": {
        "gespraech.monate_erhoeht_gezahlt": 8,
        "gespraech.strategie": "auswandern",
    }})
    assert antwort.status_code == 400
    akte = klient.get(f"/faelle/{fall_id}").json()
    assert [lauf["trigger"]["code"] for lauf in akte["laeufe"]] == ["initial"]


def test_ohne_antworten_gibt_es_400(klient, fall_id):
    assert klient.post(f"/faelle/{fall_id}/leitfaden", json={"antworten": {}}).status_code == 400


def test_ein_unbekannter_fall_gibt_404(klient):
    antwort = klient.post("/faelle/F-GIBT-ES-NICHT/leitfaden",
                          json={"antworten": {"gespraech.weiternutzung_erfolgt": True}})
    assert antwort.status_code == 404
