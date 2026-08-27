"""„Wie oft hatten wir das schon?" in der Fallakte — unter derselben Schwelle.

Die Frage kam aus der parallelen UI-Session: darf in der Fallakte
„FitPoint 24: 3 Fälle im Bestand" stehen, obwohl `store.py` als Zusicherung
führt, dass kein Cluster unterhalb `k_min` berichtet wird?

Die Antwort steckt darin, was die Schwelle schützt. Sie schützt nicht den Fall,
den die Beraterin ohnehin offen vor sich hat — sie schützt **die anderen, die
mitgezählt werden**. „3 Fälle" heißt „zwei weitere außer diesem"; bei zwei
hieße es „eine weitere", und wer eine davon kennt oder selbst bearbeitet, hat
die Beschwerde dieser einen Person identifiziert. Zwischen Radar und Fallakte
wechselt der Leser, nicht das Risiko.
"""

from __future__ import annotations

import json

import pytest

from fallpruefer import store
from fallpruefer.konfig import konfig


@pytest.fixture
def leerer_store(tmp_path, monkeypatch):
    ziel = tmp_path / "faelle.jsonl"
    monkeypatch.setattr(store, "pfad", lambda: ziel)
    return ziel


def _schreiben(ziel, anbieter: str, anzahl: int, fallgruppe="preiserhoehung",
               pruefpunkte=("P6",)):
    """Schreibt so, wie `satz_bauen` schreiben würde — **inklusive Faltung**.

    Die erste Fassung legte den Namen ungefaltet ab, also eine Zeile, die der
    echte Schreiber nie erzeugt. Ein Fixture, das etwas Unmögliches ablegt,
    testet die Leseseite gegen eine Welt, die es nicht gibt; genau daran ist
    der Faltungsfehler zuerst vorbeigelaufen.
    """
    with ziel.open("a", encoding="utf-8") as f:
        for i in range(anzahl):
            f.write(json.dumps({
                "fall_hash": f"{anbieter}-{fallgruppe}-{i}", "zeit": "2026-08-01T10:00:00+02:00",
                "fallgruppe_id": fallgruppe, "stufe": "A",
                "anbieter": store.schluessel(anbieter),
                "einordnung": "wahrscheinlich unwirksam",
                "pruefpunkte_nein": list(pruefpunkte),
            }, ensure_ascii=False) + "\n")


def test_unter_der_schwelle_ist_von_gar_nichts_nicht_zu_unterscheiden(leerer_store):
    """Der Kern. Gäbe es unterhalb der Schwelle einen Satz wie „unter der
    Meldeschwelle", sagte er „es gibt mindestens einen und weniger als k" — und
    das ist bei k = 2 genau die Re-Identifikation, die die Schwelle verhindern
    soll. Unterdrückt und leer müssen von außen gleich aussehen.
    """
    k_min = konfig().radar.k_min
    _schreiben(leerer_store, "Studio A", k_min - 1)

    unterdrueckt = store.anbieter_bestand("Studio A", "preiserhoehung")
    gar_nicht_da = store.anbieter_bestand("Studio Z", "preiserhoehung")
    assert unterdrueckt.as_dict() | {"anbieter": ""} == gar_nicht_da.as_dict() | {"anbieter": ""}
    assert unterdrueckt.faelle is None and not unterdrueckt.gleicher_pruefpunkt
    assert unterdrueckt.ausgewiesen is False


def test_ab_der_schwelle_steht_die_zahl_und_der_wiederkehrende_pruefpunkt(leerer_store):
    k_min = konfig().radar.k_min
    _schreiben(leerer_store, "Studio A", k_min, pruefpunkte=("P6", "P7"))
    b = store.anbieter_bestand("Studio A", "preiserhoehung")
    assert b.ausgewiesen and b.faelle == k_min
    # jeder der k Sätze bricht an P6 und P7 — die Dauerbrenner-Evidenz
    assert b.gleicher_pruefpunkt == {"P6": k_min, "P7": k_min}


def test_eine_andere_fallgruppe_zaehlt_nicht_mit(leerer_store):
    """Derselbe Anbieter kann in zwei Fallgruppen auftauchen. „Dauerbrenner"
    heißt: dieselbe Fallgruppe, sonst wird aus zwei verschiedenen Problemen
    ein erfundenes Muster."""
    k_min = konfig().radar.k_min
    _schreiben(leerer_store, "Studio A", k_min - 1, fallgruppe="preiserhoehung")
    _schreiben(leerer_store, "Studio A", k_min, fallgruppe="inkasso")
    assert store.anbieter_bestand("Studio A", "preiserhoehung").faelle is None
    assert store.anbieter_bestand("Studio A", "inkasso").faelle == k_min


def test_ohne_anbieter_wird_nichts_behauptet(leerer_store):
    assert store.anbieter_bestand(None, "preiserhoehung").faelle is None
    assert store.anbieter_bestand("Studio A", None).faelle is None


def test_die_bestaetigung_eines_falls_bringt_den_zaehler_ueber_die_schwelle(leerer_store):
    """Das ist der „+1"-Beat aus 14 §7, von der Datenseite gesehen.

    Vor Gate 3 steht der Fall nicht im Store, der Anbieter liegt einen Fall
    unter der Schwelle, und die Fallakte sagt über andere Fälle **nichts**.
    Die Bestätigung schreibt den Satz — und damit erscheint der Zähler
    überhaupt erst. Ein unterdrücktes Feld, das sichtbar wird, erzählt die
    k-Anonymität besser als eine Zahl, die hochzählt.
    """
    k_min = konfig().radar.k_min
    _schreiben(leerer_store, "Studio A", k_min - 1)
    assert store.anbieter_bestand("Studio A", "preiserhoehung").ausgewiesen is False

    _schreiben(leerer_store, "Studio A", 1)   # die Gate-3-Bestätigung
    danach = store.anbieter_bestand("Studio A", "preiserhoehung")
    assert danach.ausgewiesen is True and danach.faelle == k_min


def test_die_anzeigeform_findet_ihren_eigenen_satz_wieder(leerer_store, monkeypatch):
    """Der Fehler, den diese Datei zuerst NICHT gefunden hat.

    `satz_bauen` faltet den Anbieter beim Schreiben (`schluessel`), die Abfrage
    verglich ihn aber roh — also traf sie nie, und **jeder** Anbieter kam als
    „unter der Schwelle" zurück. Von außen ist das nicht zu sehen: unterdrückt
    und leer müssen identisch aussehen, das ist die Regel eine Ebene höher.
    Auf der Bühne wäre der Zähler nach Gate 3 einfach nicht erschienen, ohne
    dass jemand hätte sagen können, ob das die Schwelle ist oder ein Fehler.

    Die ersten Tests hier haben ihn übersehen, weil sie mit der bereits
    gefalteten Form gefragt haben — mit dem Wert, den die Funktion erwartet,
    statt mit dem, den ein Aufrufer hat. Deshalb ist dies ein Rundlauf und
    keine feste Zeichenkette: was die Schreibseite ablegt, muss die Leseseite
    mit dem **Originalnamen** wiederfinden.
    """
    from fallpruefer import store as st

    anzeigename = "FitPoint 24"
    k_min = konfig().radar.k_min
    zeilen = []
    for i in range(k_min):
        satz = {"fall_hash": f"h{i}", "zeit": "2026-08-01T10:00:00+02:00",
                "fallgruppe_id": "preiserhoehung", "stufe": "A",
                "anbieter": st.schluessel(anzeigename),   # wie satz_bauen es tut
                "einordnung": "wahrscheinlich unwirksam", "pruefpunkte_nein": ["P6"]}
        zeilen.append(json.dumps(satz, ensure_ascii=False))
    leerer_store.write_text("\n".join(zeilen) + "\n", encoding="utf-8")

    b = store.anbieter_bestand(anzeigename, "preiserhoehung")
    assert b.ausgewiesen, "die Anzeigeform findet ihren eigenen Satz nicht wieder"
    assert b.faelle == k_min


@pytest.mark.parametrize("form", ["FitPoint 24", "fitpoint 24", "  FITPOINT 24  "])
def test_schreibweise_und_leerraum_machen_keine_zwei_anbieter(leerer_store, form):
    """Zwei Cluster halber Größe hätten beide unter `k_min` gelegen — die
    Schwelle hätte dann etwas unterdrückt, das es als Muster gibt."""
    k_min = konfig().radar.k_min
    _schreiben(leerer_store, "FitPoint 24", k_min)
    assert store.anbieter_bestand(form, "preiserhoehung").faelle == k_min


def test_der_demofall_traegt_die_anzeigeform(leerer_store):
    """`demo/faelle/drehkreuz/ticket.json` trägt „FitPoint 24" — genau der
    Wert, mit dem die Fallakte fragen wird."""
    from fallpruefer.konfig import WURZEL

    ticket = json.loads(
        (WURZEL / "demo" / "faelle" / "drehkreuz" / "ticket.json").read_text(encoding="utf-8"))
    assert ticket["anbieter"] != store.schluessel(ticket["anbieter"]), (
        "wenn Anzeigeform und Store-Form hier zufällig gleich sind, testet der "
        "Rundlauf oben nichts mehr"
    )
