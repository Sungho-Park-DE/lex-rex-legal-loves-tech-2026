"""V-I2 — ein widersprochenes Feld fällt nicht mehr aus der Spur.

Gefunden von der parallelen UI-Session beim Bau des Felder-Panels. Zwei
`strittig`-Fakten machen `Fallkontext.feld()` zu None, die Regel liest den Wert
also nicht, und der Evaluator verbuchte in `verwendet` nur, was er gelesen hat
— das Feld verschwand vollständig. Auf dem Schirm stand „Bewertung nötig" mit
einer allgemeinen Frage, und die beiden Aussagen, die sich widersprechen,
standen nirgends. Die Beraterin sollte an Gate 3 einen Konflikt auflösen,
dessen beide Hälften unsichtbar waren.

`missing` ist der falsche Ort dafür: das ist die Sprache für „fehlt" und
speist die Gate-1-Nachforderung — das Werkzeug würde bei der Verbraucherin
eine Unterlage anfordern, die längst in der Akte liegt. Deshalb eine dritte
Liste. Die Spur ist Beweismittel und wird aus der Fallakte gelesen, nicht aus
der Projektion, also gehört sie in den Motor.
"""

from __future__ import annotations

import pytest

from fallpruefer.konfig import WURZEL
from fallpruefer.pipeline import fall_aus_verzeichnis, leitfaden_antworten
from fallpruefer.vokabular import Herkunft, Zustand

FELD = "vertrag.agb_einbezogen_hinweis"


def _ergebnis(fall, pruefpunkt_id="P2"):
    return next(e for e in fall.pruefungen[-1].ergebnisse
                if e.pruefpunkt_id == pruefpunkt_id)


@pytest.fixture
def widersprochen():
    """Der Drehkreuz-Vertrag sagt, die AGB seien einbezogen; die Verbraucherin
    sagt im Gespräch, sie habe sie nie bekommen."""
    fall = fall_aus_verzeichnis(WURZEL / "demo" / "faelle" / "drehkreuz", "F-STRIT")
    leitfaden_antworten(fall, {FELD: False})
    return fall


def test_das_widersprochene_feld_steht_in_der_spur(widersprochen):
    erg = _ergebnis(widersprochen)
    assert erg.zustand == Zustand.WERTUNG
    assert erg.strittige_felder == [FELD]


def test_es_steht_nicht_in_missing(widersprochen):
    """Sonst fordert Gate 1 bei der Verbraucherin eine Unterlage an, die in der
    Akte liegt — der Vertrag ist da, er widerspricht nur der Aussage."""
    erg = _ergebnis(widersprochen)
    assert FELD not in erg.missing
    for eintrag in widersprochen.dokumenten_soll.get("fehlt") or []:
        assert eintrag.get("feld_id") != FELD


def test_es_steht_nicht_in_verwendet(widersprochen):
    """`verwendet` heißt „gelesen und benutzt". Die Regel konnte den Wert nicht
    lesen; stünde das Feld dort, hieße `verwendet` zweierlei."""
    assert FELD not in _ergebnis(widersprochen).verwendet


def test_beide_seiten_sind_im_fall_und_keine_gewinnt(widersprochen):
    seiten = [f for f in widersprochen.fakten if f.feld_id == FELD]
    assert len(seiten) == 2
    assert {f.wert for f in seiten} == {True, False}
    assert all(f.herkunft == Herkunft.STRITTIG and f.verifiziert is False for f in seiten)


def test_ohne_widerspruch_bleibt_die_liste_leer():
    fall = fall_aus_verzeichnis(WURZEL / "demo" / "faelle" / "drehkreuz", "F-STRIT-OK")
    for erg in fall.pruefungen[-1].ergebnisse:
        assert erg.strittige_felder == [], erg.pruefpunkt_id


def test_ein_bloss_fehlendes_feld_ist_nicht_strittig():
    """Nordlicht liegt ohne AGB vor — viele Felder fehlen, keines ist
    umstritten. „Es fehlt" und „es ist zu viel da" sind zwei Aussagen."""
    fall = fall_aus_verzeichnis(WURZEL / "demo" / "faelle" / "nordlicht_agb_fehlen", "F-STRIT-FEHLT")
    ergebnisse = fall.pruefungen[-1].ergebnisse
    assert any(e.missing for e in ergebnisse), "dieser Fall soll etwas vermissen"
    assert all(e.strittige_felder == [] for e in ergebnisse)


def test_eine_einzelne_unverifizierte_aussage_ist_kein_widerspruch():
    """Ein Fakt, dessen Zitat die Prüfung nicht bestanden hat, ist unbrauchbar
    — aber er widerspricht niemandem. „Strittig" verlangt zwei Seiten; sonst
    stünde in der Spur ein Konflikt, den die Beraterin nicht auflösen kann,
    weil es nur eine Aussage gibt."""
    from fallpruefer.evaluator import pruefen
    from fallpruefer.schema import schema_laden

    fall = fall_aus_verzeichnis(WURZEL / "demo" / "faelle" / "drehkreuz", "F-STRIT-EINZEL")
    einzeln = next(f for f in fall.fakten if f.feld_id == FELD)
    einzeln.verifiziert = False          # Zitat nicht bestätigt, aber nur eine Aussage
    einzeln.herkunft = Herkunft.STRITTIG  # selbst wenn die Herkunft es behauptet
    fall.fakten = [f for f in fall.fakten if f is einzeln or f.feld_id != FELD]

    pruefung = pruefen(fall, schema_laden("preiserhoehung"))
    erg = next(e for e in pruefung.ergebnisse if e.pruefpunkt_id == "P2")
    assert erg.strittige_felder == []


def test_eine_zurueckgenommene_antwort_raeumt_die_liste_wieder(widersprochen):
    """Korrigiert sich die Verbraucherin auf den Wert der Unterlage, ist der
    Konflikt weg — und die Spur darf ihn nicht behalten."""
    leitfaden_antworten(widersprochen, {FELD: True})
    erg = _ergebnis(widersprochen)
    assert erg.strittige_felder == []
    assert erg.zustand == Zustand.JA


def test_der_widerspruch_ueberlebt_speichern_und_laden(tmp_path, monkeypatch):
    """Der Fall wird bei jedem API-Aufruf nach `cases/` geschrieben und wieder
    gelesen. Die Notiz, was ein Fakt vor dem Widerspruch war, liegt deshalb in
    einem Extra-Feld **ohne** führenden Unterstrich: pydantic wirft
    unterstrich-präfixierte Attribute aus `model_dump`, der Merker wäre im
    Unittest da und im laufenden Programm weg. Danach ließe sich ein
    zurückgenommener Widerspruch nicht mehr auflösen und die Unterlage bliebe
    dauerhaft als „widersprüchlich" markiert.
    """
    from fallpruefer import konfig as kmod
    from fallpruefer.pipeline import fall_laden, fall_speichern

    monkeypatch.setattr(kmod, "WURZEL", kmod.WURZEL)
    fall = fall_aus_verzeichnis(WURZEL / "demo" / "faelle" / "drehkreuz", "F-STRIT-RT")
    leitfaden_antworten(fall, {FELD: False})
    fall_speichern(fall)

    geladen = fall_laden("F-STRIT-RT")
    seiten = [f for f in geladen.fakten if f.feld_id == FELD]
    assert all(getattr(f, "vor_widerspruch", None) for f in seiten), (
        "der Merker hat das Speichern nicht überlebt"
    )

    # …und die Rücknahme funktioniert über den echten Pfad
    leitfaden_antworten(geladen, {FELD: True})
    erg = _ergebnis(geladen)
    assert erg.strittige_felder == [] and erg.zustand == Zustand.JA
    wieder = [f for f in geladen.fakten if f.feld_id == FELD]
    assert Herkunft.EXPLIZIT in {f.herkunft for f in wieder}, (
        "die Unterlage ist nicht in ihren ursprünglichen Zustand zurückgekehrt"
    )


def test_ein_erneuter_widerspruch_haeuft_keine_fakten_an():
    """Nein → ja → nein darf nicht vier Fakten auf einem Feld hinterlassen.

    Der erste Anlauf tat genau das: „die vorige Antwort ersetzen" suchte nach
    `herkunft == gespraech`, und die Widerspruchsmarkierung hatte genau diese
    Herkunft überschrieben — die Antwort hörte auf, unter ihrem eigenen Namen
    auffindbar zu sein.
    """
    fall = fall_aus_verzeichnis(WURZEL / "demo" / "faelle" / "drehkreuz", "F-STRIT-ZYKLUS")
    for wert in (False, True, False):
        leitfaden_antworten(fall, {FELD: wert})
        assert len([f for f in fall.fakten if f.feld_id == FELD]) == 2
    assert _ergebnis(fall).strittige_felder == [FELD]
