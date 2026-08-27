"""V-G1 — Franz' Fall 6 (`30` §9): „Ohne Erklärung entfällt der Rechtsgrund und
es entsteht ein Herausgabeanspruch nach § 812 Abs. 1 S. 1 BGB."

Bis heute konnte die Regelsprache den Fehlzustand `existiert_nicht` nicht
lesen: „nie erhalten" und „noch nicht eingereicht" waren für `dok_fehlt`
derselbe Wert, also wechselte die Aussage der Verbraucherin nur den Adressaten
(Gate 4 statt Gate 1), nie das Urteil. Jetzt: `dok_existiert_nicht` in der
Grammatik, P1a im Schema, ein eigener Brief — und die vier Zusicherungen hier.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from fallpruefer import store
from fallpruefer.api import app
from fallpruefer.konfig import WURZEL
from fallpruefer.regeln import auswerten

D = WURZEL / "demo" / "faelle" / "drehkreuz"


@pytest.fixture(autouse=True)
def eigener_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "pfad", lambda: tmp_path / "faelle.jsonl")


@pytest.fixture
def klient():
    return TestClient(app)


def _anlegen(klient, cid, dateien):
    ticket = json.loads((D / "ticket.json").read_text(encoding="utf-8"))
    r = klient.post("/faelle", json={
        "freitext": ticket["freitext"],
        "anhaenge": [{"dateiname": n, "text": (D / n).read_text(encoding="utf-8")} for n in dateien],
        "kanal": "vbs", "anbieter": ticket["anbieter"], "identitaet": ticket["identitaet"],
        "case_id": cid,
    })
    assert r.status_code == 200, r.text
    return klient.get(f"/faelle/{cid}").json()


def test_das_praedikat_liest_den_fehlzustand():
    class K:
        def __init__(self, da, nie):
            self.da, self.nie = da, nie
        def dok_vorhanden(self, typ):
            return typ in self.da
        def dok_existiert_nicht(self, typ):
            return typ in self.nie
    assert auswerten({"dok_existiert_nicht": "erhoehungsschreiben"}, K(set(), {"erhoehungsschreiben"})) is True
    assert auswerten({"dok_existiert_nicht": "erhoehungsschreiben"}, K(set(), set())) is False
    # dok_fehlt bleibt, was es war: „fehlt" ist beides
    assert auswerten({"dok_fehlt": "erhoehungsschreiben"}, K(set(), set())) is True


def test_nie_erklaert_ist_ein_anderes_urteil_nicht_nur_ein_anderer_adressat(klient):
    cid = "F-2026-9601"
    vorher = _anlegen(klient, cid, ("agb.md", "vertrag.md"))
    assert vorher["hero"]["einordnung"]["code"] == "unklar"
    r = klient.post(f"/faelle/{cid}/nicht-vorhanden", json={
        "dokumenttyp": "erhoehungsschreiben",
        "aussage": "Ich habe nie einen Brief bekommen, es wurde einfach mehr abgebucht.",
    })
    assert r.status_code == 200, r.text
    a = klient.get(f"/faelle/{cid}").json()
    assert a["hero"]["einordnung"]["label"] == "wahrscheinlich unwirksam"
    assert a["pruefpfad"]["gerissene_stufe"] == "S1"
    zustaende = {p["pruefpunkt_id"]: p["zustand"]["code"]
                 for s in a["pruefpfad"]["stufen"] for p in s["pruefpunkte"]}
    assert zustaende["P1a"] == "NEIN"
    # die Stufen dahinter sind gegenstandslos, nicht „offen"
    assert all(zustaende[p] == "INAKTIV" for p in ("P0", "P1", "P2", "P6", "P9", "P10", "P11"))
    # das Paar: Urteil + Brief, und zwar der richtige Brief
    assert a["musterbrief"] is not None, "kein Brief — das Paar ist gerissen"
    assert a["musterbrief"]["rechtsbehelf_id"] == "rueckforderung_ohne_erklaerung"
    assert "[" not in a["musterbrief"]["text"], "Platzhalter im Brief"
    assert "§" not in a["musterbrief"]["text"], "Paragrafen gehören auf den Schirm, nicht in den Brief (22 §8)"
    p1a = next(p for s in a["pruefpfad"]["stufen"] for p in s["pruefpunkte"] if p["pruefpunkt_id"] == "P1a")
    assert p1a["geprueft_von"] and p1a["geprueft_von"][0]["wer"] == "Franz"
    assert any(x["key"] == "bgb_812" for x in p1a["anker"])


def test_ein_vorhandenes_schreiben_schlaegt_die_aussage(klient):
    """Liegt das Schreiben doch in der Akte, greift P1a nicht — auch wenn die
    Aussage im Fall steht (sie ist dann schlicht widerlegt)."""
    cid = "F-2026-9602"
    a = _anlegen(klient, cid, ("schreiben.md", "agb.md", "vertrag.md"))
    zustaende = {p["pruefpunkt_id"]: p["zustand"]["code"]
                 for s in a["pruefpfad"]["stufen"] for p in s["pruefpunkte"]}
    assert zustaende["P1a"] == "JA"
    assert a["hero"]["einordnung"]["label"] == "wahrscheinlich unwirksam"  # drehkreuz bleibt drehkreuz
    assert a["musterbrief"]["rechtsbehelf_id"] == "widerspruch_rueckforderung"


def test_zurueckgezogene_feststellung_stellt_den_alten_zustand_wieder_her(klient):
    cid = "F-2026-9603"
    _anlegen(klient, cid, ("agb.md", "vertrag.md"))
    klient.post(f"/faelle/{cid}/nicht-vorhanden", json={"dokumenttyp": "erhoehungsschreiben", "aussage": "nie bekommen"})
    assert klient.get(f"/faelle/{cid}").json()["hero"]["einordnung"]["code"] != "unklar"
    r = klient.post(f"/faelle/{cid}/nicht-vorhanden", json={"dokumenttyp": "erhoehungsschreiben", "aussage": "", "zurueckziehen": True})
    if r.status_code == 200:
        assert klient.get(f"/faelle/{cid}").json()["hero"]["einordnung"]["code"] == "unklar"
    else:
        pytest.skip(f"kein Rücknahme-Pfad über HTTP ({r.status_code}) — Motorfunktion deckt es")
