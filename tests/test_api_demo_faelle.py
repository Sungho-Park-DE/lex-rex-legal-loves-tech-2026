"""Bühnenauftakt (/neu, 27. Aug): die vorbereiteten Fälle kommen aus dem Backend,
nicht aus einem Dateidialog.

Sungho, 27. Aug früh: auf der Bühne wird kein Desktop-Ordner durchsucht — das
Werkzeug zeigt, welche Fälle vorbereitet sind, und die Beraterin wählt einen.
Zwei Dinge hält der Test fest: die Liste ist genau der Bestand in
`demo/faelle/` (jeder Ordner mit ticket.json, Fall 01 = drehkreuz, 33 §2), und
der Eintrag ist wörtlich die Nutzlast, die `tools/demo_start.py` schickt —
derselbe Text, dieselbe Identität, also derselbe Cache-Schlüssel. Fall 01
läuft aus der Liste ohne Schlüssel bis zur Einordnung.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from fallpruefer import store
from fallpruefer.api import app
from fallpruefer.konfig import WURZEL, konfig

VERZ = WURZEL / "demo" / "faelle"


@pytest.fixture(autouse=True)
def cache_only(tmp_path, monkeypatch):
    monkeypatch.setattr(konfig().llm, "nur_cache", True)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(store, "pfad", lambda: tmp_path / "faelle.jsonl")


def test_liste_ist_der_bestand_in_buehnenreihenfolge():
    liste = TestClient(app).get("/demo/faelle").json()
    erwartet = sorted(p.name for p in VERZ.iterdir() if (p / "ticket.json").is_file())
    assert sorted(f["fall"] for f in liste) == erwartet
    assert [f["nr"] for f in liste] == list(range(1, len(liste) + 1))
    assert liste[0]["fall"] == "drehkreuz", "Fall 01 ist der Bühnenfall (33 §2)"

    goldens = {p.stem for p in (WURZEL / "tests" / "golden").glob("*.json")}
    for f in liste:
        # vorbereitet = ein Golden existiert; die Suite spielt es cache-only ab
        assert f["vorbereitet"] == (f["fall"] in goldens), f["fall"]
        ticket = json.loads((VERZ / f["fall"] / "ticket.json").read_text(encoding="utf-8"))
        assert [a["dateiname"] for a in f["anhaenge"]] == ticket["anhaenge"], f["fall"]
        for a in f["anhaenge"]:
            assert a["text"] == (VERZ / f["fall"] / a["dateiname"]).read_text(encoding="utf-8")
        assert f["freitext"] == ticket["freitext"]
        assert f["identitaet"] == ticket["identitaet"]


def test_fall_01_laeuft_aus_der_liste_ohne_schluessel():
    klient = TestClient(app)
    fall = next(f for f in klient.get("/demo/faelle").json() if f["nr"] == 1)
    assert fall["vorbereitet"] is True
    nutzlast = {k: fall[k] for k in (
        "freitext", "kanal", "ticket_nr", "thema", "anbieter", "branche",
        "eingegangen_am", "identitaet", "anhaenge",
    )}
    nutzlast["case_id"] = "T-demo-liste-01"
    antwort = klient.post("/faelle", json=nutzlast)
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["einordnung"] == "wahrscheinlich unwirksam"
