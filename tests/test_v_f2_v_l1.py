"""V-F2 (ein Satz pro Arm) und V-L1 („geprüft, nicht enthalten" ist ein Befund)."""

from __future__ import annotations

import pytest

from fallpruefer.adapter.basis import Extraktion, FeldTreffer, validiere_extraktion
from fallpruefer.evaluator import pruefpunkt_auswerten, satz
from fallpruefer.fall import SeiteText
from fallpruefer.schema import Feld, schema_laden
from tests.mutation.test_regeln import _faktum, _kontext


def _p8():
    return next(p for p in schema_laden("preiserhoehung").pruefpunkte if p.id == "P8")


def test_p8_spricht_je_arm_einen_anderen_satz():
    schema = schema_laden("preiserhoehung")
    p = _p8()
    # Arm 1: Widerspruchsfrist eindeutig zu kurz
    k = _kontext(fakten=[_faktum("agb.widerspruchsfrist_tage", 3),
                         _faktum("erhoehungsschreiben.zustimmungsmechanismus", "schweigen")],
                 dokumente=("agb", "erhoehungsschreiben"))
    e = pruefpunkt_auswerten(p, k, schema)
    assert e.zustand.value == "NEIN"
    assert "3 Tagen" in e.grund and "zu kurz" in e.grund, e.grund
    # Arm 2: Fiktion ohne Frist und Hinweis
    k = _kontext(fakten=[_faktum("erhoehungsschreiben.zustimmungsmechanismus", "schweigen"),
                         _faktum("agb.erklaerungsfiktion_frist_und_hinweis", False)],
                 dokumente=("agb", "erhoehungsschreiben"))
    e = pruefpunkt_auswerten(p, k, schema)
    assert e.zustand.value == "NEIN"
    assert "Schweigen" in e.grund and "zu kurz" not in e.grund, e.grund


def test_arme_ohne_treffer_fallen_auf_den_rest_zurueck():
    k = _kontext()
    arme = [{"wenn": {"vorhanden": "agb.x"}, "satz": "A"}, {"satz": "Rest"}]
    assert satz(arme, k) == "Rest"
    assert satz([{"wenn": {"vorhanden": "agb.x"}, "satz": "A"}], k) == ""
    assert satz("nur ein String", k) == "nur ein String"


def test_ein_arm_ohne_satz_wird_beim_laden_abgewiesen(tmp_path):
    import json

    from fallpruefer.konfig import WURZEL
    from fallpruefer.schema import SchemaFehler

    roh = json.loads((WURZEL / "schemas" / "preiserhoehung.json").read_text(encoding="utf-8"))
    p8 = next(p for p in roh["pruefpunkte"] if p["id"] == "P8")
    p8["satz_nein"] = [{"wenn": {"vorhanden": "agb.x"}}]
    (tmp_path / "preiserhoehung.json").write_text(json.dumps(roh, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SchemaFehler):
        schema_laden("preiserhoehung", verzeichnis=tmp_path)


# --------------------------------------------------------------------------
# V-L1
# --------------------------------------------------------------------------

SEITE = [SeiteText(nr=1, text_original="§ 5 Beiträge. Der Beitrag beträgt 29,90 €. Weitere Regelungen: keine.",
                   text_pseudonym="§ 5 Beiträge. Der Beitrag beträgt 29,90 €. Weitere Regelungen: keine.")]
FELDER = [Feld(feld_id="agb.preisklausel_text", typ="text", pflicht=True),
          Feld(feld_id="agb.fassung_datum", typ="datum")]


def test_null_mit_zitat_ist_ein_befund_kein_muell():
    ex = Extraktion(felder=[FeldTreffer(feld_id="agb.preisklausel_text", wert=None,
                                        zitat="Weitere Regelungen: keine.", seite=1)])
    fakten, verworfen = validiere_extraktion(ex, FELDER, SEITE, "D2")
    assert verworfen == []
    assert len(fakten) == 1 and fakten[0].wert is None and fakten[0].quelle is not None
    assert fakten[0].verifiziert is True


def test_null_ohne_zitat_bleibt_verworfen():
    ex = Extraktion(felder=[FeldTreffer(feld_id="agb.preisklausel_text", wert=None)])
    fakten, verworfen = validiere_extraktion(ex, FELDER, SEITE, "D2")
    assert fakten == [] and verworfen == ["agb.preisklausel_text"]


def test_null_mit_erfundenem_zitat_bleibt_verworfen():
    ex = Extraktion(felder=[FeldTreffer(feld_id="agb.preisklausel_text", wert=None,
                                        zitat="steht so nicht auf der Seite", seite=1)])
    fakten, verworfen = validiere_extraktion(ex, FELDER, SEITE, "D2")
    assert fakten == [] and verworfen == ["agb.preisklausel_text"]


def test_ein_datumsfeld_darf_nicht_leer_mit_zitat_antworten():
    ex = Extraktion(felder=[FeldTreffer(feld_id="agb.fassung_datum", wert=None,
                                        zitat="Weitere Regelungen: keine.", seite=1)])
    fakten, verworfen = validiere_extraktion(ex, FELDER, SEITE, "D2")
    assert verworfen == ["agb.fassung_datum"]


def test_der_leere_befund_bleibt_fuer_die_regel_unsichtbar_und_fuer_den_schirm_sichtbar():
    from fallpruefer.fall import Faktum, Quellenangabe

    schema = schema_laden("preiserhoehung")
    f = Faktum(feld_id="agb.preisklausel_text", wert=None, dok_id="D2", verifiziert=True,
               quelle=Quellenangabe(dok_id="D2", seite=1, zitat_pseudonym="Weitere Regelungen: keine."))
    k = _kontext(fakten=[f], dokumente=("agb",))
    assert k.feld("agb.preisklausel_text") is None
    assert k.verifiziert("agb.preisklausel_text") is False
    p5 = next(p for p in schema.pruefpunkte if p.id == "P5")
    e = pruefpunkt_auswerten(p5, k, schema)
    assert e.zustand.value == "FEHLT" and "agb.preisklausel_text" in e.missing
    from fallpruefer import ansicht
    zeilen = ansicht._verwendet(e, k.fall, k, schema)
    assert any(z.feld_id == "agb.preisklausel_text" and "nicht enthalten" in z.wert_anzeige and z.zitat
               for z in zeilen)
