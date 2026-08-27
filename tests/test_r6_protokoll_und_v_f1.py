"""R6 (Rohcode auf dem Schirm, Sichtung 25 Aug) und V-F1 (falsche Nachforderung
nach gerissener Kreuzprüfung) — beides Motor-/Anzeigeschicht, kein UI-Prompt.
"""

from __future__ import annotations

import re

import pytest

from fallpruefer import ansicht, store
from fallpruefer.konfig import WURZEL
from fallpruefer.pipeline import fall_aus_verzeichnis, gate1_nachforderung, referat_markieren, gate3_bestaetigen
from fallpruefer.schema import schema_laden

FAELLE = WURZEL / "demo" / "faelle"
ROHCODE = re.compile(r"\b(initial|nachreichung|schema_reload|nachforderung_(vbs|video|vor_ort)|"
                     r"musterbrief_[a-z_]+|widerspruch_rueckforderung|kuendigung_bei_wirksam|"
                     r"bedeutsame_schadenshoehe|neuigkeitswert|dauerbrenner)\b")


@pytest.fixture(autouse=True)
def eigener_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "pfad", lambda: tmp_path / "faelle.jsonl")


def _akte(fall):
    return ansicht.bauen(fall, schema_laden(fall.schema_.fallgruppe_id))


def test_kein_protokoll_satz_traegt_einen_code():
    fall = fall_aus_verzeichnis(FAELLE / "nordlicht_agb_fehlen", case_id="F-2026-7401")
    gate1_nachforderung(fall)
    gate3_bestaetigen(fall)
    referat_markieren(fall, ["dauerbrenner", "neuigkeitswert"])
    akte = _akte(fall)
    assert akte.protokoll, "kein Protokoll?"
    for e in akte.protokoll:
        text = e.beschreibung or ""
        assert not ROHCODE.search(text), f"{e.aktion.label}: „{text}“ trägt einen Code"
    texte = [e.beschreibung for e in akte.protokoll]
    assert any("Ersteingang" in t for t in texte), "Lauftrigger wird als Wort gezeigt"
    assert any("Nachforderung von Unterlagen" in t for t in texte), "Vorlagentitel statt id"
    assert any("Dauerbrenner" in t for t in texte), "Kriterien-Label statt Code"


def test_eingegangen_ist_ein_satz_kein_code():
    fall = fall_aus_verzeichnis(FAELLE / "drehkreuz", case_id="F-2026-7402")
    for d in _akte(fall).dokumente:
        assert d.eingegangen not in ("eingang", "nachreichung")
        assert d.eingegangen == "mit dem Ersteingang"


def test_gerissene_kreuzpruefung_fordert_nichts_nach_was_in_der_akte_liegt():
    """V-F1: P2 geht im Störfall über die Kreuzprüfung auf FEHLT — der Vertrag
    liegt als D3 vor und darf nicht als fehlend gemeldet werden."""
    fall = fall_aus_verzeichnis(FAELLE / "stoerfall_kraftwerk", case_id="F-2026-7403")
    p2 = next(e for e in fall.aktuelle_pruefung().ergebnisse if e.pruefpunkt_id == "P2")
    assert p2.zustand.value == "FEHLT"
    assert p2.missing == []
    # und die Klasse: ein FEHLT_wenn nennt nur, was es selbst vermisst
    from fallpruefer.evaluator import _felder_der_bedingung

    assert _felder_der_bedingung({"eine": [{"fehlt": "a.x"}, {"nicht": {"verifiziert": "b.y"}},
                                            {"dok_fehlt": "agb"}]}) == ["a.x", "b.y"]


def test_ein_vorhanden_feld_auf_false_bleibt_fehlend():
    """Die Kostenkalkulation (P11) meldet sich weiter über `.vorhanden` — sonst
    verschwände der Unternehmensposten aus jeder Vollständigkeitsliste."""
    fall = fall_aus_verzeichnis(FAELLE / "seepark_seite_fehlt", case_id="F-2026-7404")
    p11 = next(e for e in fall.aktuelle_pruefung().ergebnisse if e.pruefpunkt_id == "P11")
    assert p11.missing == ["kostenkalkulation.vorhanden"]


# --------------------------------------------------------------------------
# R5 — Feld-IDs sind keine Beschriftung
# --------------------------------------------------------------------------


def test_jedes_preiserhoehung_feld_hat_ein_label():
    schema = schema_laden("preiserhoehung")
    ohne = [f.feld_id for d in schema.dokumenten_soll.dokumente for f in d.felder if not f.label]
    assert not ohne, f"ohne label rendert die feld_id auf dem Schirm: {ohne}"
    for d in schema.dokumenten_soll.dokumente:
        for f in d.felder:
            assert "_" not in f.label and "." not in f.label, f.feld_id


def test_verwendete_felder_und_fehlt_saetze_tragen_das_label():
    fall = fall_aus_verzeichnis(FAELLE / "nordlicht_agb_fehlen", case_id="F-2026-7405")
    akte = _akte(fall)
    zeilen = [p for s in akte.pruefpfad.stufen for p in s.pruefpunkte]
    verwendet = [v for p in zeilen for v in p.verwendet]
    assert verwendet and all(v.feld_label for v in verwendet)
    # „Es fehlt: …" nennt Labels, keine Punkt-Pfade
    for p in zeilen:
        if p.zustand.code == "FEHLT":
            assert not re.search(r"\b[a-z]+\.[a-z_]+\b", p.grund), p.grund
