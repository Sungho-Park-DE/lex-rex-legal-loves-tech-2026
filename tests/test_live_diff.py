"""The B1 harness, tested against synthetic defects.

`tools/live_diff.py` exists because the live adapter path has never run, and
its output is meant to drive decisions about the adapter layer. A diagnostic
nobody has exercised is the same trap one rung up, so this file feeds it
hand-made „live" answers whose defect class is known and asserts that it says
the right thing — including that its reason-deriver never disagrees with the
production validator without saying so.
"""

from __future__ import annotations

import json

from tools.live_diff import Lauf, stufen, vergleiche_extraktion

from fallpruefer.adapter.basis import Extraktion
from fallpruefer.dokumente import laden
from fallpruefer.konfig import WURZEL
from fallpruefer.pipeline import fall_anlegen, pseudonymisieren
from fallpruefer.schema import schema_laden
from fallpruefer.vokabular import Dokumenttyp

FALL = WURZEL / "demo" / "faelle" / "sauber_aktivpark"


def _agb_dokument():
    """The Aktivpark AGB, pseudonymised exactly as the adapter would see it."""
    ticket = json.loads((FALL / "ticket.json").read_text(encoding="utf-8"))
    dokumente = [laden(FALL / n, f"D{i}") for i, n in enumerate(ticket["anhaenge"], start=1)]
    fall = fall_anlegen("F-TEST", ticket, dokumente)
    pseudonymisieren(fall)
    schema = schema_laden("preiserhoehung")
    sd = schema.dokumenten_soll.nach_typ(Dokumenttyp.AGB)
    dok = next(d for d in fall.dokumente if "agb" in d.dateiname)
    return dok, sd.felder


def _arten(cache_felder, live_felder):
    dok, felder = _agb_dokument()
    lauf = Lauf()
    vergleiche_extraktion(
        lauf, "test", 1, dok.dok_id,
        Extraktion.model_validate({"felder": cache_felder}),
        Extraktion.model_validate({"felder": live_felder}),
        felder, dok.seiten,
    )
    return lauf, [b.art for b in lauf.befunde]


def _echtes_feld_und_zitat():
    """A field the Aktivpark AGB really carries, with a span really in it —
    so a test that expects „accepted" is not passing for the wrong reason."""
    dok, felder = _agb_dokument()
    seite = dok.seiten[0]
    text = seite.text_pseudonym or seite.text_original
    spec = next(f for f in felder if f.typ == "text")
    return spec.feld_id, text.strip().splitlines()[0][:40], seite.nr


def test_ein_nicht_vorhandenes_zitat_wird_als_ZITAT_gemeldet():
    fid, zitat, nr = _echtes_feld_und_zitat()
    gut = [{"feld_id": fid, "wert": "irgendein Text", "zitat": zitat, "seite": nr}]
    erfunden = [{"feld_id": fid, "wert": "irgendein Text",
                 "zitat": "diese Zeichenfolge steht garantiert nirgends im Dokument",
                 "seite": nr}]
    lauf, arten = _arten(gut, erfunden)
    assert "ZITAT" in arten
    assert "UNBEKANNT" not in arten, "der Nachbau widerspricht dem Validator"
    assert "steht so nicht im Dokument" in lauf.befunde[0].detail


def test_ein_unbekanntes_feld_wird_als_VERWORFEN_gemeldet():
    fid, zitat, nr = _echtes_feld_und_zitat()
    gut = [{"feld_id": fid, "wert": "x", "zitat": zitat, "seite": nr}]
    erfunden = gut + [{"feld_id": "agb.gibt_es_nicht", "wert": "x",
                       "zitat": zitat, "seite": nr}]
    lauf, arten = _arten(gut, erfunden)
    assert "VERWORFEN" in arten
    assert "UNBEKANNT" not in arten


def test_ein_enum_ausserhalb_der_liste_wird_als_TYP_gemeldet():
    dok, felder = _agb_dokument()
    spec = next((f for f in felder if f.typ == "enum" and f.werte), None)
    if spec is None:
        return  # no enum field in this Soll — nothing to assert
    _, zitat, nr = _echtes_feld_und_zitat()
    gut = [{"feld_id": spec.feld_id, "wert": spec.werte[0], "zitat": zitat, "seite": nr}]
    falsch = [{"feld_id": spec.feld_id, "wert": "ein-wert-den-es-nicht-gibt",
               "zitat": zitat, "seite": nr}]
    lauf, arten = _arten(gut, falsch)
    assert "TYP" in arten
    assert "UNBEKANNT" not in arten
    assert "parst nicht als enum" in lauf.befunde[0].detail


def test_ein_fehlendes_und_ein_zusaetzliches_feld_werden_unterschieden():
    fid, zitat, nr = _echtes_feld_und_zitat()
    eintrag = {"feld_id": fid, "wert": "x", "zitat": zitat, "seite": nr}
    lauf, arten = _arten([eintrag], [])
    assert arten == ["FEHLT"]
    lauf, arten = _arten([], [eintrag])
    assert arten == ["ZUSATZ"]


def test_gleiche_antwort_erzeugt_keinen_befund():
    fid, zitat, nr = _echtes_feld_und_zitat()
    eintrag = [{"feld_id": fid, "wert": "x", "zitat": zitat, "seite": nr}]
    lauf, arten = _arten(eintrag, eintrag)
    assert arten == []
    assert lauf.felder_gleich == 1


def test_die_stufen_werden_aus_dem_verzeichnis_abgeleitet_nicht_gepflegt():
    """The stage lists used to be a second hand-kept copy of the file names the
    four cache tools pass. They are derived now; this asserts the derivation
    still matches what those tools actually write."""
    assert stufen(WURZEL / "demo" / "faelle" / "drehkreuz") == [
        ["schreiben.md", "agb.md", "vertrag.md"]]
    assert stufen(WURZEL / "demo" / "faelle" / "nordlicht_agb_fehlen") == [
        ["schreiben.md"],
        ["schreiben.md", "agb_nachgereicht.md", "vertrag_nachgereicht.md"]]
    assert stufen(WURZEL / "demo" / "faelle" / "seepark_seite_fehlt") == [
        ["schreiben.md", "bedingungen_seite1.md", "vertrag.md"],
        ["schreiben.md", "bedingungen_seite1.md", "vertrag.md",
         "bedingungen_seite2_nachgereicht.md"]]
