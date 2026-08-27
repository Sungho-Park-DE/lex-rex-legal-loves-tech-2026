"""Franz' Anleitung „Einordnung und Auswertung der Fälle" (24. Aug), §3–§6.

Das Papier ist die erste juristische Vorgabe, die wir für den **Radar** haben —
bis dahin war er die einzige Fläche, deren Rechnung niemand geprüft hatte. Drei
seiner Sätze sind hier als Test festgehalten, weil sie leise brechen können:

- §5 „Fälle ohne Betragsangabe gelten als **unbeziffert, nicht als null**."
  Ein Median, in den Nullen einlaufen, ist nicht falsch berechnet, sondern
  falsch beantwortet — und sieht genauso aus wie ein richtiger.
- §5 „Bereits entstandener und künftig drohender Schaden werden **getrennt**
  ausgewiesen — nur Letzterer ist abwendbar." Eine Summe aus beidem ist die
  Zahl, die keine Beratung tragen kann.
- §3/§6 Verbreitung (Verwender) und Betroffenheit (Verbraucher) sind **zwei**
  Zahlen. Wer sie zusammenzieht, sagt etwas über den Markt, was er nicht weiß.

Dazu die Bedingung, die keiner seiner Sätze kennt, die aber über allem steht:
die k_min-Schwelle gilt auf der neuen Achse genauso, sonst ist eine Zeile
„Klauseltyp X: 1 Verwender" neben der Anbieterliste ein Fingerabdruck.
"""

from __future__ import annotations

import pytest

from fallpruefer import store, zeit
from fallpruefer.konfig import WURZEL
from fallpruefer.pipeline import fall_aus_verzeichnis

FAELLE = WURZEL / "demo" / "faelle"


@pytest.fixture(autouse=True)
def eigener_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "pfad", lambda: tmp_path / "faelle.jsonl")


def _satz(**ueberschreiben):
    basis = {
        "fall_hash": "h" * 32, "zeit": "2026-08-01T10:00:00+02:00",
        "fallgruppe_id": "preiserhoehung", "stufe": "A", "anbieter": "a gmbh",
        "gegner": None, "branche": "fitness", "einordnung": "wahrscheinlich unwirksam",
        "gerissene_stufe": "S3", "pruefpunkte_nein": ["P6"], "fehlte": [],
        "rechtsbehelf": "widerspruch_rueckforderung", "betrag_erhoehung_gerundet": 5.0,
        "referat_flag": [], "kanal": "vbs", "schema_version": "0.2.0",
        "schaden_entstanden": 10.0, "schaden_drohend": 60.0, "schaden_basis": "laufzeit",
    }
    basis.update(ueberschreiben)
    return basis


def _schreiben(saetze):
    p = store.pfad()
    p.parent.mkdir(parents=True, exist_ok=True)
    import json
    with p.open("w", encoding="utf-8") as f:
        for s in saetze:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------
# §5 — der Schaden je Einzelfall
# --------------------------------------------------------------------------


def test_unbeziffert_ist_nicht_null():
    """Der Fall ohne Betrag zieht den Median nicht nach unten, sondern steht daneben."""
    _schreiben([
        _satz(fall_hash="a" * 32, schaden_drohend=60.0),
        _satz(fall_hash="b" * 32, schaden_drohend=60.0),
        _satz(fall_hash="c" * 32, schaden_entstanden=None, schaden_drohend=None,
              schaden_basis="unbeziffert", betrag_erhoehung_gerundet=None),
    ])
    s = store.radar()["cluster"][0]["schaden"]
    assert s["drohend_median"] == 60.0, "ein unbezifferter Fall wurde als 0 mitgemittelt"
    assert s["fallzahl"] == 2, "die Fallzahl muss die bezifferten Fälle meinen"
    assert s["unbeziffert"] == 1, "die unbezifferten Fälle müssen sichtbar bleiben"


def test_entstanden_und_drohend_bleiben_getrennt():
    """Nur der drohende Schaden ist abwendbar — eine Gesamtsumme gibt es nicht."""
    _schreiben([_satz(fall_hash=c * 32, schaden_entstanden=10.0, schaden_drohend=60.0)
                for c in "abc"])
    s = store.radar()["cluster"][0]["schaden"]
    assert s["entstanden_summe"] == 30.0
    assert s["drohend_summe"] == 180.0
    assert "summe" not in s and "gesamt" not in s, (
        "eine addierte Gesamtsumme wäre genau die Zahl, die §5 verbietet")


def test_gekappte_faelle_werden_gezaehlt():
    """Eine hilfsweise auf 24 Monate gekappte Zahl darf nicht wie eine gemessene aussehen."""
    _schreiben([
        _satz(fall_hash="a" * 32, schaden_basis="laufzeit"),
        _satz(fall_hash="b" * 32, schaden_basis="fallback_24"),
        _satz(fall_hash="c" * 32, schaden_basis="fallback_24"),
    ])
    s = store.radar()["cluster"][0]["schaden"]
    assert s["gekappt"] == 2
    assert set(s["basen"]) == {"laufzeit", "fallback_24"}


def test_summiert_wird_nur_innerhalb_einer_fallgruppe():
    """§5: „Summiert wird nur innerhalb einer Fallgruppe."""
    _schreiben([
        _satz(fall_hash="a" * 32, schaden_drohend=60.0),
        _satz(fall_hash="b" * 32, schaden_drohend=60.0),
        _satz(fall_hash="c" * 32, fallgruppe_id="inkasso", schaden_drohend=900.0),
    ])
    c = store.radar()["cluster"][0]
    assert c["fallgruppe_id"] == "preiserhoehung"
    assert c["schaden"]["drohend_summe"] == 120.0, "eine fremde Fallgruppe wurde mitsummiert"


def test_schaden_rechnet_aus_den_feldern_die_es_schon_gibt():
    """Die Formel läuft auf allen vier Demofällen — ohne ein neues Soll-Feld.

    Der Test hält damit auch fest, warum das heute überhaupt ging: `wirksam_ab`
    ist Pflichtfeld, und `laufzeit_monate` steht im Vertrag. Fällt eines davon
    aus der Feldliste, bricht hier etwas, bevor der Radar still 24 Monate
    behauptet.
    """
    for name in ("drehkreuz", "seepark_seite_fehlt", "sauber_aktivpark",
                 "nordlicht_agb_fehlen"):
        fall = fall_aus_verzeichnis(FAELLE / name, "T-1")
        s = store._schaden(fall)
        assert s["basis"] != "unbeziffert", f"{name}: kein Betrag extrahiert"
        assert s["drohend"] > 0, f"{name}: drohender Schaden ist null"


def test_vertragsdatum_statt_vertragsbeginn_wird_benannt():
    """`24` §3.2: das Vertrags*datum* ist nicht der Vertrags*beginn*.

    Wir rechnen trotzdem damit, wenn nichts anderes da ist — aber die Basis
    sagt es, damit die Näherung auf dem Schirm steht statt in einem Kommentar.
    """
    fall = fall_aus_verzeichnis(FAELLE / "drehkreuz", "T-1")
    assert store._schaden(fall)["basis"] == "laufzeit_vertragsdatum"


# --------------------------------------------------------------------------
# §3 / §6 — die Klauseltyp-Achse
# --------------------------------------------------------------------------


def test_verbreitung_und_betroffenheit_sind_zwei_zahlen():
    """Drei Verwender, vier Fälle — wer das zusammenzieht, sagt etwas Falsches."""
    _schreiben([
        _satz(fall_hash="a" * 32, anbieter="a gmbh"),
        _satz(fall_hash="b" * 32, anbieter="a gmbh"),
        _satz(fall_hash="c" * 32, anbieter="b gmbh"),
        _satz(fall_hash="d" * 32, anbieter="c gmbh"),
    ])
    z = next(z for z in store.radar()["klauseltypen"] if z["pruefpunkt_id"] == "P6")
    assert z["verbreitung"] == 3
    assert z["betroffenheit"] == 4
    assert z["grundgesamtheit"] == 4
    assert z["quote"] == 1.0


def test_klauseltyp_unter_k_min_wird_zurueckgehalten():
    """Ein Klauseltyp bei genau einem Verwender ist neben der Anbieterliste ein Name."""
    _schreiben([
        _satz(fall_hash="a" * 32, anbieter="a gmbh", pruefpunkte_nein=["P6", "P9"]),
        _satz(fall_hash="b" * 32, anbieter="b gmbh", pruefpunkte_nein=["P6"]),
        _satz(fall_hash="c" * 32, anbieter="c gmbh", pruefpunkte_nein=["P6"]),
    ])
    r = store.radar()
    ids = {z["pruefpunkt_id"] for z in r["klauseltypen"]}
    assert ids == {"P6"}, "P9 steht bei einem einzigen Verwender und muss weg sein"
    assert r["unter_schwelle_klauseltypen"] == 1, (
        "zurückgehaltene Zeilen werden gezählt, nicht verschwiegen")


def test_klauseltyp_traegt_einen_titel_keinen_code():
    """Der Radar wird vom Referat gelesen; „P6" sagt dort nichts."""
    _schreiben([_satz(fall_hash=c * 32, anbieter=f"{c} gmbh") for c in "abc"])
    z = store.radar()["klauseltypen"][0]
    assert z["titel"] == "Transparenzgebot"
    assert z["titel"] != z["pruefpunkt_id"]


# --------------------------------------------------------------------------
# §4 — der Satz, der die Auswertung einordnet
# --------------------------------------------------------------------------


def test_geltungsbereich_steht_im_payload():
    """§4: „Jede Auswertung weist aus, dass sie das Beratungsaufkommen abbildet."""
    _schreiben([_satz(fall_hash=c * 32) for c in "abc"])
    text = store.radar()["geltungsbereich"]
    assert "Beratungsaufkommen" in text
    assert "nicht den Markt" in text


# --------------------------------------------------------------------------
# Der Beat, der das alles überleben muss
# --------------------------------------------------------------------------


def test_der_plus_eins_beat_bleibt_scharf():
    """`14` §7: FitPoint 24 steht bei 2, die Gate-3-Bestätigung ist die +1.

    Jede Radar-Änderung kann das kippen, und auf der Bühne merkt man es zu
    spät. Der Test baut den Zustand nach, den `tools/radar_seed.py` erzeugt,
    und drückt die dritte Zeile hinein.
    """
    zwei = [_satz(fall_hash=c * 32, anbieter="fitpoint 24") for c in "ab"]
    andere = [_satz(fall_hash=c * 32, anbieter="bodyline gyms") for c in "cde"]
    _schreiben(zwei + andere)
    sichtbar = {c["anbieter"] for c in store.radar()["cluster"]}
    assert "fitpoint 24" not in sichtbar, "FitPoint 24 darf vor der +1 nicht sichtbar sein"

    _schreiben(zwei + andere + [_satz(fall_hash="f" * 32, anbieter="fitpoint 24")])
    r = store.radar()
    sichtbar = {c["anbieter"] for c in r["cluster"]}
    assert "fitpoint 24" in sichtbar, "die +1 hat den Cluster nicht über die Schwelle gebracht"
    c = next(c for c in r["cluster"] if c["anbieter"] == "fitpoint 24")
    assert c["schaden"]["drohend_summe"] is not None, (
        "der neu sichtbare Cluster muss auch eine Schadenszahl tragen")


def test_stichtag_kommt_aus_der_konfiguration():
    """Der Schaden hängt an `heute()` — im Demo-Modus am gepinnten Stichtag."""
    assert zeit.heute() == zeit.stichtag()


# --------------------------------------------------------------------------
# §5 „nächstmöglicher Kündigungstermin" — das Gesetz sagt, was das ist
# --------------------------------------------------------------------------


def _mit(fall, feld_id, wert):
    for f in fall.fakten:
        if f.feld_id == feld_id:
            f.wert = wert
            return fall
    raise AssertionError(f"{feld_id} nicht im Fall")


def _ohne(fall, feld_id):
    fall.fakten = [f for f in fall.fakten if f.feld_id != feld_id]
    return fall


def test_nach_ablauf_der_bindung_zaehlt_ein_monat(monkeypatch):
    """§ 309 Nr. 9 lit. b BGB n.F.: in der Verlängerung jederzeit mit höchstens
    einem Monat kündbar — also droht genau eine weitere Periode, nicht 24.

    Das war die Frage, die im Register für Franz stand; der amtliche Text
    beantwortet sie. drehkreuz: Vertrag 2025-10-01, 24 Monate → Bindung endet
    2027-10-01. Am 2027-11-15 ist sie vorbei.
    """
    from datetime import date

    monkeypatch.setattr(zeit, "heute", lambda: date(2027, 11, 15))
    fall = fall_aus_verzeichnis(FAELLE / "drehkreuz", "T-1")
    s = store._schaden(fall)
    assert s["basis"] == "verlaengerung_monatlich"
    assert s["drohend"] == 7.0, "eine Periode à 7,00 € — nicht 24"
    assert s["entstanden"] == round(7.0 * zeit.monate_zwischen(date(2026, 9, 1), date(2027, 11, 15)), 2)


def test_altvertrag_vor_maerz_2022_darf_bis_zu_einem_jahr_verlaengern(monkeypatch):
    """Art. 229 § 60 S. 2 EGBGB: vor dem 01.03.2022 entstanden → § 309 a.F., und
    die ließ eine stillschweigende Verlängerung bis zu einem Jahr zu."""
    from datetime import date

    monkeypatch.setattr(zeit, "heute", lambda: date(2026, 8, 27))
    fall = _mit(fall_aus_verzeichnis(FAELLE / "drehkreuz", "T-1"), "vertrag.datum", "2021-06-01")
    s = store._schaden(fall)
    assert s["basis"] == "verlaengerung_altrecht"
    assert s["drohend"] == 7.0 * 12


def test_ohne_laufzeit_aber_mit_beginn_gilt_die_hoechstlaufzeit_ab_beginn(monkeypatch):
    """§ 309 Nr. 9 lit. a: länger als zwei Jahre bindet keine Erstlaufzeit. Ist
    der Beginn bekannt, ist „24 ab Beginn" der ehrliche Horizont — nicht „24 ab
    heute", das den Schaden bei einem zwei Jahre alten Vertrag verdoppelt."""
    from datetime import date

    monkeypatch.setattr(zeit, "heute", lambda: date(2026, 8, 27))
    fall = _ohne(fall_aus_verzeichnis(FAELLE / "drehkreuz", "T-1"), "vertrag.laufzeit_monate")
    s = store._schaden(fall)
    assert s["basis"] == "hoechstlaufzeit_24"
    # Beginn 2025-10-01 + 24 = 2027-10-01; ab wirksam_ab 2026-09-01 sind das 13 Monate
    assert s["drohend"] == 7.0 * 13


def test_verlaengerte_faelle_werden_im_block_gezaehlt():
    _schreiben([
        _satz(fall_hash="a" * 32, schaden_basis="verlaengerung_monatlich"),
        _satz(fall_hash="b" * 32, schaden_basis="verlaengerung_altrecht"),
        _satz(fall_hash="c" * 32, schaden_basis="laufzeit"),
    ])
    s = store.radar()["cluster"][0]["schaden"]
    assert s["verlaengert"] == 2
    assert s["gekappt"] == 0


# --------------------------------------------------------------------------
# §7 der Anleitung liest das Referat — als Wörter, nicht als Codes
# --------------------------------------------------------------------------


def test_markierte_faelle_tragen_labels_nicht_nur_codes():
    """Unter „Markierte Fälle" stand bis heute `schadenshoehe` — ein
    Code mit Unterstrich auf einem Schirm für Juristinnen. Die Labels kommen
    aus derselben Liste wie die Häkchen im Referat-Panel."""
    _schreiben([_satz(fall_hash="a" * 32, referat_flag=["schadenshoehe"])]
               + [_satz(fall_hash=c * 32) for c in "bc"])
    m = store.radar()["markierte_faelle"][0]
    assert m["kriterien"] == ["schadenshoehe"], "der Code bleibt — er ist das Datum"
    assert m["kriterien_labels"], "keine Labels geliefert"
    assert m["kriterien_labels"][0] != "schadenshoehe"
    assert "_" not in m["kriterien_labels"][0]


def test_unbekannter_kriterien_code_bleibt_lesbar():
    _schreiben([_satz(fall_hash="a" * 32, referat_flag=["gibt_es_nicht"])]
               + [_satz(fall_hash=c * 32) for c in "bc"])
    m = store.radar()["markierte_faelle"][0]
    assert m["kriterien_labels"] == ["gibt_es_nicht"], "ein unbekannter Code darf nicht verschwinden"
