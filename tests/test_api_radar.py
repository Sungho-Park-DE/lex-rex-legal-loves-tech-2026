"""Die drei Endpunkte, die noch nie ein Test über HTTP angefasst hat.

Gefunden, während die Anzeige-Sitzung die erste Live-Probe vorbereitet: von 17
Routen waren `POST /faelle/{id}/referat`, `GET /radar` und `GET /fallgruppen`
ausschließlich in-process geprüft. Ausgerechnet die ersten beiden tragen den
„+1"-Beat — Screen 2 aus `14` §6, einer der vier „never cut"-Beats aus `14` §7.

Das ist die Familie, die in diesem Repo schon dreimal zugeschlagen hat: der
`leitfaden_antworten`-NameError, den 259 grüne In-Process-Tests durchgelassen
haben, weil kein Test den Endpunkt über HTTP anfasste; und auf der Anzeigeseite
ein Flip-Knopf, der multipart sprach, wo das Backend JSON erwartet — im
Fixture-Modus prinzipbedingt unsichtbar, auf der Bühne ein 422.

`GET /radar` liest nur `store/faelle.jsonl`. Der Store ist gitignored, die Datei
kann also fehlen — auch das ist hier eine Antwort und kein Ausfall.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from fallpruefer import store
from fallpruefer.api import app
from fallpruefer.konfig import WURZEL

DREHKREUZ = WURZEL / "demo" / "faelle" / "drehkreuz"

# Aus dem Demofall, gegen den geprüft wird, dass nichts davon auf Screen 2 steht.
IDENTITAET = ("Ingeborg", "Maier", "Bahnhofstraße", "4711-2233", "@@")


@pytest.fixture(autouse=True)
def eigener_store(tmp_path, monkeypatch):
    """**Pflicht, nicht Hygiene.** Gate 3 schreibt in den Store, und der Store
    entscheidet über das Radar: drei bestätigte Fälle desselben Anbieters heben
    ihn über `k_min` und lassen ihn im Cluster erscheinen.

    Die erste Fassung dieser Datei drückte viermal Gate 3 auf einen
    drehkreuz-Fall — und hat damit „FitPoint 24" über die Schwelle geschoben
    und den „+1"-Beat aus `14` §7 still getötet. Nicht einmal, sondern bei
    **jedem** `pytest`-Lauf. Genau die Falle, vor der `21` warnt, und sie ist
    unsichtbar, weil unterdrückt und leer auf dem Schirm gleich aussehen.

    Dasselbe Muster wie `test_rung2.leerer_store`, hier `autouse`: wer in dieser
    Datei einen Test hinzufügt, soll nicht daran denken müssen.
    """
    monkeypatch.setattr(store, "pfad", lambda: tmp_path / "faelle.jsonl")


@pytest.fixture
def klient():
    return TestClient(app)


@pytest.fixture
def fall_id(klient):
    case_id = "F-2026-9901"
    ticket = json.loads((DREHKREUZ / "ticket.json").read_text(encoding="utf-8"))
    antwort = klient.post("/faelle", json={
        "freitext": ticket["freitext"],
        "anhaenge": [{"dateiname": n, "text": (DREHKREUZ / n).read_text(encoding="utf-8")}
                     for n in ("schreiben.md", "agb.md", "vertrag.md")],
        "kanal": "vbs", "anbieter": ticket["anbieter"],
        "identitaet": ticket["identitaet"], "case_id": case_id,
    })
    assert antwort.status_code == 200, antwort.text
    return case_id


# --------------------------------------------------------------------------
# GET /fallgruppen
# --------------------------------------------------------------------------


def test_fallgruppen_liefert_die_taxonomie_aus_den_schemadateien(klient):
    """Kontrakt §0: die Taxonomie wird beim Laden abgeleitet, nichts wird
    zweimal gepflegt. Über HTTP heißt das: jede Schemadatei taucht auf."""
    antwort = klient.get("/fallgruppen")
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()

    dateien = {p.stem for p in (WURZEL / "schemas").glob("*.json")
               if not p.stem.startswith("_")}
    assert set(daten) == dateien
    for fid, eintrag in daten.items():
        assert eintrag.get("stufe") in ("A", "B", "C"), fid
        assert eintrag.get("name"), fid


# --------------------------------------------------------------------------
# GET /radar
# --------------------------------------------------------------------------


def test_radar_antwortet_mit_der_form_die_screen_2_erwartet(klient):
    antwort = klient.get("/radar")
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    for schluessel in ("cluster", "faelle_gesamt", "schwellen",
                       "unter_schwelle_anbieter", "markierte_faelle", "stand"):
        assert schluessel in daten, schluessel
    assert isinstance(daten["cluster"], list)


def test_das_radar_kann_keine_identitaet_zeigen(klient, fall_id):
    """`store.py` hat gar keinen Zugriff auf ein Fallobjekt — es liest nur die
    anonymisierten Zeilen. Der Test hält das an der Grenze fest, weil genau
    hier ein Fehler nicht auffiele, sondern **hinausginge**: Screen 2 ist der
    Bildschirm, den das Referat sieht."""
    klient.post(f"/faelle/{fall_id}/gate3", json={})
    roh = klient.get("/radar").text
    for geheim in IDENTITAET:
        assert geheim not in roh, f"„{geheim}“ steht auf dem Radar"


def test_unterhalb_von_k_min_wird_kein_anbieter_genannt(klient):
    """Die k-Anonymitätsregel aus Kontrakt §8, über HTTP gelesen — und die
    Zahl kommt aus der Antwort, nicht aus einer im Test wiederholten Konstante.
    Genau diese Regel hat schon einmal einen echten Bug versteckt
    (`anbieter_bestand` traf nie zu, und „unterdrückt" sah aus wie „leer")."""
    daten = klient.get("/radar").json()
    k_min = daten["schwellen"]["k_min"]
    for c in daten["cluster"]:
        assert c["faelle"] >= k_min, f"{c.get('anbieter')} unter k_min genannt"


# --------------------------------------------------------------------------
# POST /faelle/{id}/referat
# --------------------------------------------------------------------------


def test_referat_setzt_das_flag_und_gibt_den_hash_zurueck(klient, fall_id):
    klient.post(f"/faelle/{fall_id}/gate3", json={})
    antwort = klient.post(f"/faelle/{fall_id}/referat", json={
        "kriterien": ["dauerbrenner"],
        "notiz": "Dieselbe Klausel liegt in zwei weiteren Beratungen vor.",
    })
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert daten["case_id"] == fall_id
    assert daten["kriterien"] == ["dauerbrenner"]
    assert daten["fall_hash"], "ohne Hash findet die Markierung ihre Zeile im Store nicht"


def test_die_markierung_erscheint_auf_dem_radar_ohne_den_fall_zu_verraten(klient, fall_id):
    klient.post(f"/faelle/{fall_id}/gate3", json={})
    klient.post(f"/faelle/{fall_id}/referat", json={"kriterien": ["dauerbrenner"]})

    antwort = klient.get("/radar")
    assert antwort.status_code == 200
    assert len(antwort.json()["markierte_faelle"]) >= 1
    for geheim in IDENTITAET:
        assert geheim not in antwort.text


def test_referat_ohne_gate3_wird_abgewiesen_und_nicht_still_geschluckt(klient, fall_id):
    """`referat_markieren` schreibt in den Store, und in den Store darf nur ein
    **bestätigter** Lauf — sonst zählt das Radar die Meinungen des Programms
    statt die Befunde der Beratungsstelle. Über HTTP muss daraus ein 4xx
    werden und keine 200 mit stiller Wirkungslosigkeit."""
    antwort = klient.post(f"/faelle/{fall_id}/referat", json={"kriterien": ["dauerbrenner"]})
    assert antwort.status_code == 400, antwort.text


def test_ein_erfundenes_kriterium_wird_abgewiesen(klient, fall_id):
    """Aufgefallen, weil dieser Test zuerst „breitenwirkung" erfunden hat und
    der Endpunkt zu Recht 400 gab: die sechs FWN-Kriterien stehen als Daten in
    `config.json`, damit niemand ein siebtes erfindet (`10` §, „no invented
    taxonomy"). Über HTTP heißt das 400 mit Begründung, nicht stilles Schlucken."""
    klient.post(f"/faelle/{fall_id}/gate3", json={})
    antwort = klient.post(f"/faelle/{fall_id}/referat",
                          json={"kriterien": ["breitenwirkung"]})
    assert antwort.status_code == 400
    assert "config.json" in antwort.json()["detail"]


def test_eine_leere_kriterienliste_hebt_die_markierung_auf(klient, fall_id):
    """Frage der Anzeige-Sitzung vor der Live-Probe: ihr „Markierung aufheben"
    schickt `{kriterien: []}` — versteht der Endpunkt das als Aufheben oder
    weist er es ab? Nachgemessen: er hebt auf, 200, und der Fall fällt aus
    `markierte_faelle`. Das ist richtig, war aber nirgends zugesichert."""
    klient.post(f"/faelle/{fall_id}/gate3", json={})
    klient.post(f"/faelle/{fall_id}/referat", json={"kriterien": ["dauerbrenner"]})
    assert len(klient.get("/radar").json()["markierte_faelle"]) == 1

    antwort = klient.post(f"/faelle/{fall_id}/referat", json={"kriterien": []})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["kriterien"] == []
    assert klient.get("/radar").json()["markierte_faelle"] == []


# --------------------------------------------------------------------------
# die zwei Anzeige-Helfer in store.py (6e87a67, Anzeige-Sitzung)
# --------------------------------------------------------------------------


def test_jede_einordnung_findet_ihren_ton_auch_als_variante():
    """Der Store hält das Urteil als Anzeigestring, nicht als Enum — die
    identitätsfreien Zeilen tragen keine Codes. Der Ton wird deshalb per
    Präfix zurückgeholt, und „unklar – es fehlt: die AGB …" muss dabei auf die
    Grundform „unklar – es fehlt …" treffen. Sonst blieben genau die Fälle
    grau, um die es auf Screen 2 geht."""
    from fallpruefer.vokabular import Einordnung, label, ton

    for e in Einordnung:
        assert store._einordnung_ton(label(e)) == ton(e).value

    assert store._einordnung_ton(
        "unklar – es fehlt: die AGB, die bei Vertragsschluss galten"
    ) == ton(Einordnung.UNKLAR).value
    assert store._einordnung_ton(
        "unklar – es fehlt: Bewertung durch die Beraterin zu „War die Vorlaufzeit …“"
    ) == ton(Einordnung.UNKLAR).value

    # Unbekanntes bleibt grau statt sich eine Farbe auszusuchen
    assert store._einordnung_ton("") == "grau"
    assert store._einordnung_ton("irgendetwas anderes") == "grau"


def test_ein_pruefpunkt_titel_faellt_auf_die_id_zurueck_statt_zu_scheitern():
    """Eine alte Store-Zeile kann einen Prüfpunkt nennen, den ein Schema-Edit
    entfernt hat — dieselbe Familie wie die gespeicherte Hinweis-ID. Dann ist
    die rohe id der ehrliche Rest: lesbar schlägt falsch, und eine Radarzeile
    darf den Schirm nicht mitnehmen."""
    assert store._pruefpunkt_titel("preiserhoehung", "P7") == "Symmetrie- und Kostenweitergabegebot"
    assert store._pruefpunkt_titel("preiserhoehung", "P999") == "P999"
    assert store._pruefpunkt_titel("gibt_es_nicht", "P7") == "P7"
    assert store._pruefpunkt_titel(None, "P7") == "P7"


def test_das_radar_zeigt_keine_rohen_pruefpunkt_ids(klient):
    """Der Befund vom ersten echten /referat-Schirm: „Nicht erfüllte
    Prüfpunkte: P7 (2), P3 (1)" — rohe ids vor der Referatsleitung, dieselbe
    Familie wie „(Gate 4)". Hier über HTTP festgehalten, damit die Auflösung
    nicht still wieder verlorengeht.

    Die **Store-Zeilen** behalten die ids: dort sind sie Beweis, nicht Anzeige.

    ⚠️ Der Test **muss** einen Cluster erzeugen. Mit einem einzigen bestätigten
    Fall liegt der Anbieter unter `k_min`, `cluster` ist leer, die Schleife läuft
    über nichts und der Test ist grün, ohne etwas zu messen — beim ersten
    Schreiben war er genau das. Deshalb die Zusicherung vor der Schleife.
    """
    import re

    ticket = json.loads((DREHKREUZ / "ticket.json").read_text(encoding="utf-8"))
    anhaenge = [{"dateiname": n, "text": (DREHKREUZ / n).read_text(encoding="utf-8")}
                for n in ("schreiben.md", "agb.md", "vertrag.md")]
    k_min = klient.get("/radar").json()["schwellen"]["k_min"]
    for i in range(k_min):
        cid = f"F-2026-99{10 + i}"
        klient.post("/faelle", json={
            "freitext": ticket["freitext"], "anhaenge": anhaenge, "kanal": "vbs",
            "anbieter": ticket["anbieter"], "identitaet": ticket["identitaet"],
            "case_id": cid,
        })
        klient.post(f"/faelle/{cid}/gate3", json={})

    cluster = klient.get("/radar").json()["cluster"]
    assert cluster, "kein Cluster — der Test würde über nichts laufen"
    assert any(c.get("pruefpunkte_nein") for c in cluster), \
        "kein einziger gerissener Prüfpunkt im Payload — nichts zu prüfen"

    for c in cluster:
        for eintrag in c.get("pruefpunkte_nein") or []:
            assert not re.fullmatch(r"P\d+[a-z]?", eintrag["titel"]), \
                f"rohe Prüfpunkt-ID auf dem Radar: {eintrag['titel']}"
        for eintrag in c.get("einordnungen") or []:
            assert eintrag["tone"] in ("gruen", "gelb", "rot", "grau")
