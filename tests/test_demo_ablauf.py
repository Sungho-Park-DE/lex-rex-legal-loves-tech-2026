"""Der Bühnenablauf, einmal von vorn bis hinten — über HTTP.

`14` §7 nennt vier Beats, die **nie gekürzt** werden. Jeder einzelne ist
irgendwo geprüft; **die Reihenfolge war es nirgends.** Und auf der Bühne ist
genau die Reihenfolge das Produkt: derselbe Fall, mehrfach angefasst, jedes Mal
mit einer anderen Antwort — und jede Antwort muss zur vorherigen passen.

Was dieser Test kann, was die Einzeltests nicht können: er hält den Fall
zwischen den Beats fest. Ein Defekt, der nur beim *zweiten* Anfassen entsteht,
ist in diesem Repo schon dreimal aufgetreten — die Gate-4-Wahl, die keine war;
der Override, der in keiner Fixture stand; die Hinweis-ID ohne Schema-Eintrag.

Läuft gegen einen **eigenen** Store. Gate 3 schreibt, der Store entscheidet über
das Radar, und ein Test darf den Demo-Zustand nicht anfassen (B7).
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from fallpruefer import store
from fallpruefer.api import app
from fallpruefer.konfig import WURZEL, konfig

FAELLE = WURZEL / "demo" / "faelle"
SCHEMA = WURZEL / "schemas" / "preiserhoehung.json"


@pytest.fixture(autouse=True)
def eigener_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "pfad", lambda: tmp_path / "faelle.jsonl")


@pytest.fixture
def klient():
    return TestClient(app)


def _anlegen(klient, verzeichnis, dateien, case_id, branche="fitness"):
    ticket = json.loads((verzeichnis / "ticket.json").read_text(encoding="utf-8"))
    antwort = klient.post("/faelle", json={
        "freitext": ticket["freitext"],
        "anhaenge": [{"dateiname": n, "text": (verzeichnis / n).read_text(encoding="utf-8")}
                     for n in dateien],
        "kanal": "vbs", "anbieter": ticket["anbieter"], "branche": branche,
        "identitaet": ticket["identitaet"], "case_id": case_id,
    })
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def _nachreichen(klient, case_id, verzeichnis, dateien):
    antwort = klient.post(f"/faelle/{case_id}/dokumente", json={"anhaenge": [
        {"dateiname": n, "text": (verzeichnis / n).read_text(encoding="utf-8")}
        for n in dateien
    ]})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


# --------------------------------------------------------------------------
# Beat 1 + 2 — der Flip, und dass das alte Urteil lesbar bleibt
# --------------------------------------------------------------------------


def test_akt_1_der_flip_und_das_paar_in_beiden_zustaenden(klient):
    """Nordlicht: `unklar` → Nachreichung → `wahrscheinlich unwirksam`.

    Geprüft wird nicht nur, dass sich das Urteil bewegt, sondern die drei
    Dinge, die den Beat auf der Bühne tragen: das **alte** Urteil bleibt
    lesbar (sonst ist es kein Vorher/Nachher), in **beiden** Zuständen liegt
    ein Schreiben vor (`14` §5, das Paar), und der Rechtsbehelf wechselt mit.
    """
    verzeichnis = FAELLE / "nordlicht_agb_fehlen"
    _anlegen(klient, verzeichnis, ["schreiben.md"], "F-DEMO-1")

    vorher = klient.get("/faelle/F-DEMO-1").json()
    assert vorher["hero"]["einordnung"]["label"].startswith("unklar")
    assert vorher["musterbrief"] and vorher["musterbrief"]["text"].strip()

    antwort = _nachreichen(klient, "F-DEMO-1", verzeichnis,
                           ["agb_nachgereicht.md", "vertrag_nachgereicht.md"])
    assert antwort["einordnung_vorher"].startswith("unklar")
    assert antwort["einordnung"] == "wahrscheinlich unwirksam"

    nachher = klient.get("/faelle/F-DEMO-1").json()
    assert nachher["hero"]["einordnung"]["label"] == "wahrscheinlich unwirksam"
    assert nachher["musterbrief"] and nachher["musterbrief"]["text"].strip()
    assert nachher["musterbrief"]["text"] != vorher["musterbrief"]["text"]

    # das Vorher ist nicht überschrieben, sondern steht als eigener Lauf da
    laeufe = nachher["laeufe"]
    assert len(laeufe) == 2
    assert [x["aktuell"] for x in laeufe] == [False, True]
    assert laeufe[0]["einordnung"].startswith("unklar")


def test_in_jedem_der_drei_zweige_liegt_ein_schreiben_bereit(klient):
    """Das Paar aus `14` §5, über HTTP und über alle drei Zweige — auch über
    `wirksam`, den Zweig, auf dem ein Werkzeug still zu werden pflegt und an
    dem eine Beraterin aufhört, ihm zu trauen."""
    faelle = [
        ("F-DEMO-W", FAELLE / "sauber_aktivpark",
         ["schreiben.md", "agb.md", "vertrag.md"], "wirksam"),
        ("F-DEMO-U", FAELLE / "nordlicht_agb_fehlen", ["schreiben.md"], "unklar"),
        ("F-DEMO-N", FAELLE / "drehkreuz",
         ["schreiben.md", "agb.md", "vertrag.md"], "wahrscheinlich unwirksam"),
    ]
    for case_id, verzeichnis, dateien, erwartet in faelle:
        _anlegen(klient, verzeichnis, dateien, case_id)
        sicht = klient.get(f"/faelle/{case_id}").json()
        assert sicht["hero"]["einordnung"]["label"].startswith(erwartet), case_id
        brief = sicht["musterbrief"]
        assert brief and brief["text"].strip(), f"{case_id}: Urteil ohne Schreiben"
        # kein ungefüllter Platzhalter — ein Brief mit Lücke wird nicht ausgegeben
        assert not re.search(konfig().platzhalter_regex, brief["text"]), case_id
        assert sicht["hero"]["einordnung"]["tone"] in ("gruen", "gelb", "rot", "grau")


# --------------------------------------------------------------------------
# Beat 3 — Akt 2, der Jurist-Edit
# --------------------------------------------------------------------------


def test_akt_2_der_jurist_edit_dreht_denselben_fall(klient):
    """Die Datei wird geändert, derselbe Fall läuft erneut, das Urteil dreht —
    ohne Neustart, ohne Deployment. „Das Papier und der Code sind dieselbe
    Datei" (`14` §7).

    Der Fall ist **`sauber_aktivpark`**, nicht Seepark: Seepark trägt die
    Pointe aus Akt 1, und ein Jurist-Edit dort überschriebe sie
    (`offene_punkte` §A.1).
    """
    _anlegen(klient, FAELLE / "sauber_aktivpark",
             ["schreiben.md", "agb.md", "vertrag.md"], "F-DEMO-2")
    assert klient.get("/faelle/F-DEMO-2").json()["hero"]["einordnung"]["label"] == "wirksam"

    sicherung = SCHEMA.read_text(encoding="utf-8")
    try:
        daten = json.loads(sicherung)
        for pp in daten["pruefpunkte"]:
            if pp["id"] == "P10":
                pp["parameter"]["frist_min_tage"] = 90
        SCHEMA.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")

        # der Knopf ist nur sinnvoll, wenn die Datei sich bewegt hat
        assert klient.get("/schema/preiserhoehung").json()["geaendert"] is True

        antwort = klient.post("/faelle/F-DEMO-2/neu-pruefen")
        assert antwort.status_code == 200, antwort.text
        sicht = klient.get("/faelle/F-DEMO-2").json()
        assert sicht["hero"]["einordnung"]["label"].startswith("unklar")
        assert "Bewertung" in sicht["hero"]["einordnung"]["label"]
        assert sicht["musterbrief"], "auch nach dem Edit gehört ein Schreiben dazu"
    finally:
        SCHEMA.write_text(sicherung, encoding="utf-8")

    # und zurück: die Datei ist wieder die alte, der Fall auch
    klient.post("/faelle/F-DEMO-2/neu-pruefen")
    assert klient.get("/faelle/F-DEMO-2").json()["hero"]["einordnung"]["label"] == "wirksam"


def test_der_edit_bewegt_genau_die_knoepfe_die_das_schema_anbietet(klient):
    """`GET /schema/{id}` liefert die Liste, aus der die Oberfläche die
    Edit-Felder baut. Steht dort ein Knopf, der nichts bewegt, ist er auf der
    Bühne schlimmer als keiner — dafür gibt es `test_rung3`. Hier nur, dass
    die Liste über HTTP überhaupt ankommt und auf Vorhandenes zeigt."""
    daten = klient.get("/schema/preiserhoehung").json()
    assert daten["jurist_edit_knoepfe"], "keine Edit-Knöpfe im Endpunkt"
    for pfad in daten["jurist_edit_knoepfe"]:
        assert pfad.startswith("pruefpunkte.")


# --------------------------------------------------------------------------
# Beat 4 — das Radar-„+1"
# --------------------------------------------------------------------------


def test_beat_4_gate_3_laesst_den_anbieter_auf_dem_radar_erscheinen(klient, tmp_path):
    """Der „+1"-Beat: ein Anbieter steht bei `k_min - 1` und ist deshalb
    **unterdrückt**. Die Beraterin bestätigt die Einordnung, und derselbe
    Anbieter erscheint — aus zwei Beratungen wird ein Muster.

    Der Test baut den Hintergrund selbst, statt sich auf `tools/radar_seed.py`
    im echten Store zu verlassen: was der Beat braucht, ist eine Eigenschaft
    (`k_min - 1`), keine Datei.
    """
    from tools.radar_seed import satz

    ticket = json.loads((FAELLE / "drehkreuz" / "ticket.json").read_text(encoding="utf-8"))
    anbieter = (ticket.get("anbieter") or "").lower()
    k_min = klient.get("/radar").json()["schwellen"]["k_min"]

    ziel = tmp_path / "faelle.jsonl"
    ziel.write_text("\n".join(
        json.dumps(satz(i, anbieter, "fitness", "wahrscheinlich unwirksam", "S3",
                        ["P6", "P7"], 5.0), ensure_ascii=False)
        for i in range(k_min - 1)
    ) + "\n", encoding="utf-8")

    vorher = klient.get("/radar").json()
    assert anbieter not in {c["anbieter"] for c in vorher["cluster"]}, \
        "der Anbieter ist schon sichtbar — der Beat hätte nichts zu zeigen"
    assert vorher["unter_schwelle_anbieter"] >= 1, "nichts unterdrückt, nichts zu enthüllen"

    _anlegen(klient, FAELLE / "drehkreuz",
             ["schreiben.md", "agb.md", "vertrag.md"], "F-DEMO-3")
    assert anbieter not in {c["anbieter"] for c in klient.get("/radar").json()["cluster"]}, \
        "ein unbestätigter Lauf darf nicht zählen — sonst zählt das Radar Meinungen"

    assert klient.post("/faelle/F-DEMO-3/gate3", json={}).status_code == 200

    nachher = klient.get("/radar").json()
    sichtbar = {c["anbieter"] for c in nachher["cluster"]}
    assert anbieter in sichtbar, "der +1-Beat feuert nicht"
    treffer = next(c for c in nachher["cluster"] if c["anbieter"] == anbieter)
    assert treffer["faelle"] == k_min


def test_der_ganze_ablauf_hinterlaesst_eine_lueckenlose_spur(klient):
    """Die RDG-/AI-Act-Argumentation (`14` §8) ruht darauf, dass jede
    Gate-Aktion ein Ereignis hinterlässt. Über den ganzen Ablauf geprüft, nicht
    je Aktion: ein Gate, das den Fall still ändert, ist das eine, was dieser
    Entwurf sich nicht leisten kann."""
    verzeichnis = FAELLE / "nordlicht_agb_fehlen"
    _anlegen(klient, verzeichnis, ["schreiben.md"], "F-DEMO-4")
    klient.post("/faelle/F-DEMO-4/fallgruppe", json={"fallgruppe_id": "preiserhoehung"})
    klient.post("/faelle/F-DEMO-4/nachforderung", json={})
    _nachreichen(klient, "F-DEMO-4", verzeichnis,
                 ["agb_nachgereicht.md", "vertrag_nachgereicht.md"])
    klient.post("/faelle/F-DEMO-4/override", json={
        "pruefpunkt_id": "P4", "neuer_zustand": "JA", "grund": "aus einem Parallelfall bekannt"})
    klient.post("/faelle/F-DEMO-4/gate3", json={})
    klient.post("/faelle/F-DEMO-4/referat", json={"kriterien": ["dauerbrenner"]})

    protokoll = klient.get("/faelle/F-DEMO-4").json()["protokoll"]
    aktionen = [e["aktion"]["code"] for e in protokoll]
    for erwartet in ("gate2_fallgruppe_gewaehlt", "gate1_nachforderung_erzeugt",
                     "nachreichung_eingegangen", "gate3_override",
                     "gate3_bestaetigt", "referat_markiert"):
        assert erwartet in aktionen, f"{erwartet} fehlt in der Spur"

    for eintrag in protokoll:
        assert eintrag["aktion"]["label"], "eine Zeile ohne Klartext"
        assert eintrag["schritt"]["label"]
        assert eintrag["akteur"], "eine Zeile ohne Akteur"
        # Kontrakt §12: die Rolle, nie der Name eines Menschen
        assert "Testberaterin" not in eintrag["akteur"]
