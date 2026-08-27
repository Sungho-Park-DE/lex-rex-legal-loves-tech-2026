"""The paths that used to return a bare HTTP 500.

Found in the cold verification of 23 Aug. Each of these is the same shape: an
input the scripted demo never produces — a document pasted with a `---` line on
top, a ticket without an Anbieter, a date the model transposed, a schema file
saved with a typo while the process was starting — and in every case the answer
was a red box with no sentence in it. The tool is handed to other people
(`16` §1); „it works on the four cases we wrote" is not the same claim as „it
works".

The rule these tests pin down is the one `brief.py` already states for letters
and `adapter/basis.py` for extracted values: **an unusable input is refused
with its reason, never silently patched and never allowed to take the request
down.**
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fallpruefer import brief as brief_modul
from fallpruefer import dokumente, schema as schema_modul, zeit
from fallpruefer.api import app
from fallpruefer.evaluator import Fallkontext, pruefen
from fallpruefer.konfig import WURZEL
from fallpruefer.pipeline import _schema_von, fall_aus_verzeichnis

NORDLICHT = WURZEL / "demo" / "faelle" / "nordlicht_agb_fehlen"
DREHKREUZ = WURZEL / "demo" / "faelle" / "drehkreuz"


# --------------------------------------------------------------------------
# Values the model can get wrong
# --------------------------------------------------------------------------


@pytest.mark.parametrize("roh", ["2026-13-01", "31.02.2026", "2026-02-30", "00.00.0000"])
def test_ein_unmoegliches_datum_faellt_weg_statt_die_anfrage_mitzunehmen(roh):
    """A well-formed but impossible date is not a date. `date(2026, 13, 1)`
    raises, and the exception used to travel all the way out of the validator
    to a 500 — so one transposed day and month cost the whole intake instead of
    one field."""
    assert zeit.parse_datum(roh) is None


def test_gueltige_daten_parsen_weiterhin():
    assert zeit.parse_datum("2026-09-01") == zeit.parse_datum("01.09.2026")
    assert zeit.parse_datum("September 2026") is None


# --------------------------------------------------------------------------
# Documents as they actually arrive
# --------------------------------------------------------------------------


def test_ein_dokument_das_mit_drei_strichen_beginnt_verliert_keinen_text():
    """A leading `---` is what a PDF-to-markdown converter, a Word paste and a
    page separator all produce. Treating the block between the first two `---`
    as front matter on faith deleted whole clauses before L0 ever saw them,
    with nothing on screen to say so."""
    roh = (
        "---\n\n# Mitgliedsbedingungen\n\n"
        "Ziffer 5.2: Der Betreiber darf den Beitrag anpassen.\n\n---\n\nStand 01/2024\n"
    )
    d = dokumente.aus_freitext(roh, "D1")
    assert "Ziffer 5.2" in d.text_original
    assert d.fassung_datum is None


def test_echtes_frontmatter_wird_weiterhin_gelesen():
    """The narrowing must not cost the fiction-file affordance it was built
    for (18 #45): a real `key: value` block is still front matter."""
    d = dokumente.aus_freitext(
        "---\nfassung_datum: 2024-06-01\ndokumenttyp: agb\n---\nZiffer 5.2 …\n", "D1"
    )
    assert d.fassung_datum == "2024-06-01"
    assert "Ziffer 5.2" in d.text_original
    assert "fassung_datum" not in d.text_original


# --------------------------------------------------------------------------
# Letters: complete, or refused
# --------------------------------------------------------------------------


def test_ein_fehlendes_faktum_macht_keinen_gedankenstrich_im_brief():
    """`brief.py` promises „an unfillable placeholder is a render error, never
    a blank". Six placeholders came through `kontext.anzeige`, which renders a
    missing fact as „—" — not the empty string the guard tested for — so the
    advisor was handed a finished-looking Widerspruch saying the Beitrag rose
    „von — auf 36,90 €"."""
    fall = fall_aus_verzeichnis(DREHKREUZ, "F-ROB-BRIEF")
    for feld in ("erhoehungsschreiben.absender_adresse", "erhoehungsschreiben.alter_betrag"):
        for f in [x for x in fall.fakten if x.feld_id == feld]:
            fall.fakten.remove(f)
    schema = _schema_von(fall)
    fall.pruefungen.append(pruefen(fall, schema, trigger="test"))

    k = Fallkontext(fall=fall, schema=schema)
    vorlage = brief_modul.vorlage_laden("musterbrief_fitness_widerspruch_rueckforderung")
    werte = brief_modul.platzhalter_werte(fall, fall.aktuelle_pruefung(), k)
    assert werte["[ALTER_BEITRAG]"] == ""

    with pytest.raises(brief_modul.BriefFehler) as fehler:
        brief_modul.rendern(vorlage, werte, brief_modul.varianten_waehlen(vorlage, k))
    assert "[ALTER_BEITRAG]" in str(fehler.value)


def test_gate1_ohne_anbieter_antwortet_mit_grund_statt_mit_500():
    """`BriefFehler` is a RuntimeError, and the gate endpoints caught only
    ValueError — so the first button of the „unklar" act answered a ticket
    without an Anbieter with a blank 500 the presenter cannot talk over."""
    klient = TestClient(app)
    ticket = json.loads((NORDLICHT / "ticket.json").read_text(encoding="utf-8"))
    angelegt = klient.post("/faelle", json={
        "freitext": ticket["freitext"], "branche": "fitness",      # kein „anbieter"
        "identitaet": ticket["identitaet"], "case_id": "F-ROB-GATE1",
        "anhaenge": [{"dateiname": "schreiben.md",
                      "text": (NORDLICHT / "schreiben.md").read_text(encoding="utf-8")}],
    })
    assert angelegt.status_code == 200, angelegt.text

    antwort = klient.post("/faelle/F-ROB-GATE1/nachforderung", json={})
    assert antwort.status_code == 409, antwort.text
    assert "[ANBIETER]" in antwort.json()["detail"]


# --------------------------------------------------------------------------
# A schema file saved mid-edit
# --------------------------------------------------------------------------


def test_kaltstart_mit_kaputtem_schema_meldet_einen_schemafehler():
    """The Akt-2 tolerance (18 #40/#44) works once a good version has been
    loaded. Starting the process *inside* the window between „save with typo"
    and „fix typo" hit the bare `raise`, so callers that type-check on
    SchemaFehler — including `schema_laden_oder_letzte`, the tolerant read path
    itself — saw a raw JSONDecodeError and passed a 500 to the UI."""
    verzeichnis = Path(tempfile.mkdtemp())
    (verzeichnis / "preiserhoehung.json").write_text("{ das ist kein JSON", encoding="utf-8")
    schema_modul._CACHE.clear()
    try:
        for laden in (schema_modul.schema_laden, schema_modul.schema_laden_oder_letzte):
            with pytest.raises(schema_modul.SchemaFehler) as fehler:
                laden("preiserhoehung", verzeichnis=verzeichnis)
            assert "preiserhoehung.json" in str(fehler.value)
    finally:
        schema_modul._CACHE.clear()


# --------------------------------------------------------------------------
# What the screen says about itself
# --------------------------------------------------------------------------


def test_die_was_fehlt_liste_nennt_jede_unterlage_genau_einmal():
    """The dedup of 18 #28/#29 reached the letter and the verdict but not the
    projection, so the panel asked for the same AGB once per unfound field —
    seven identical rows beside a letter that, correctly, asked once. The rows
    must also read the same way the verdict does; that they agree is the point."""
    from fallpruefer import ansicht
    from fallpruefer.schema import schema_laden

    for verzeichnis, erwartet in ((NORDLICHT, 2), (WURZEL / "demo" / "faelle" / "seepark_seite_fehlt", 1)):
        fall = fall_aus_verzeichnis(verzeichnis, f"F-ROB-DUP-{verzeichnis.name}")
        a = ansicht.bauen(fall, schema_laden(fall.schema_.fallgruppe_id))
        posten = a.hero.vollstaendigkeit.verbraucher
        assert len(posten) == erwartet, [p.was for p in posten]
        assert len({p.was for p in posten}) == len(posten), "zwei Zeilen mit demselben Text"
        # the detail is not lost, it moved one level down
        assert any(p.felder for p in posten)
        # and every row appears in the verdict sentence it belongs to
        verdikt = fall.aktuelle_pruefung().einordnung
        for p in posten:
            assert p.was in verdikt, f"{p.was!r} steht nicht im Verdikt {verdikt!r}"
        # „Offene Punkte" is built from the same grouping
        fehlt = [o for o in a.offene_punkte if o.art.code == "fehlt"]
        assert len(fehlt) == erwartet


def test_der_radar_nennt_keinen_anbieter_den_k_min_gerade_unterdrueckt():
    """k_min is the whole DSGVO answer on Screen 2. The cluster list applied it;
    `markierte_faelle` did not, and named the suppressed Anbieter two lines
    under the notice promising it would not."""
    import json as _json

    from fallpruefer import store

    saetze = store.lesen() or []
    if not saetze:
        pytest.skip("leerer Store — tools/radar_seed.py läuft nur vor der Demo")

    einzeln = next((s["anbieter"] for s in saetze
                    if sum(1 for x in saetze if x.get("anbieter") == s["anbieter"]) < 3
                    and s.get("anbieter")), None)
    if einzeln is None:
        pytest.skip("kein Anbieter unter k_min im Store")

    ziel = Path(tempfile.mkdtemp()) / "faelle.jsonl"
    ziel.write_text("\n".join(
        _json.dumps({**s, "referat_flag": ["dreist_ungewoehnlich"]}
                    if s.get("anbieter") == einzeln else s, ensure_ascii=False)
        for s in saetze), encoding="utf-8")
    echt, store.pfad = store.pfad, lambda: ziel
    try:
        r = store.radar()
    finally:
        store.pfad = echt

    sichtbar = {c["anbieter"] for c in r["cluster"]}
    genannt = {m["anbieter"] for m in r["markierte_faelle"] if m["anbieter"]}
    assert not (genannt - sichtbar), f"unter k_min genannt: {genannt - sichtbar}"
    # and the flagged case is still listed — it is just anonymous
    assert any(m["anbieter"] is None for m in r["markierte_faelle"])
    assert all(len(m["zeit"]) == 10 for m in r["markierte_faelle"]), "Zeit auf den Tag gerundet"


def test_die_fusszeile_nennt_die_schema_version_die_das_urteil_gefaellt_hat():
    """`_schema_von` re-reads the file on every gate action, so a run can be
    decided by a newer version than the one stamped on the case. Footer, case
    stamp and store row have to agree with the run — the store row and the
    Basis-Eintrag both leave the tool."""
    import json as _json

    from fallpruefer import ansicht, schema as schema_modul, store
    from fallpruefer.pipeline import gate3_override

    datei = WURZEL / "schemas" / "preiserhoehung.json"
    original = datei.read_text(encoding="utf-8")
    fall = fall_aus_verzeichnis(DREHKREUZ, "F-ROB-VERSION")
    # the footer names *the* version that produced the verdict — read it from
    # the file instead of pinning a literal that every rule change bumps
    assert fall.schema_.version == _json.loads(original)["version"]

    geaendert = _json.loads(original)
    geaendert["version"] = "0.3.0"
    try:
        datei.write_text(_json.dumps(geaendert, ensure_ascii=False, indent=2), encoding="utf-8")
        schema_modul._CACHE.clear()
        gate3_override(fall, "P8", "JA", grund="Test")     # a gate action, not „neu prüfen"

        pruefung = fall.aktuelle_pruefung()
        sicht = ansicht.bauen(fall, _schema_von(fall))
        assert pruefung.schema_version == "0.3.0"
        assert fall.schema_.version == "0.3.0"
        assert sicht.fusszeile.schema_version == "0.3.0"
        assert store.satz_bauen(fall)["schema_version"] == "0.3.0"
    finally:
        datei.write_text(original, encoding="utf-8")
        schema_modul._CACHE.clear()


def test_eine_verworfene_extraktion_steht_im_protokoll():
    """„Jede Antwort geht durch einen Prüfer" is the trust pitch — and the
    moment the verifier struck left no trace at all: both callers threw
    `extrahieren`'s return value away, so a caught hallucination looked exactly
    like a value the document does not contain."""
    from fallpruefer import pipeline as pl
    from fallpruefer.adapter.basis import validiere_extraktion
    from fallpruefer.schema import schema_laden

    def erfundene_zitate(fall, schema, adapter, nur=None):
        aus: list[str] = []
        for d in fall.dokumente:
            sd = schema.dokumenten_soll.nach_typ(d.dokumenttyp)
            if not sd or not sd.felder:
                continue
            extraktion, aufruf = adapter.extract_fields(d.seiten, sd.felder, d.dokumenttyp.value)
            for feld in extraktion.felder:
                feld.zitat = "diesen Satz hat niemand geschrieben"
            run_id = pl._run_protokollieren(fall, "extract_fields", aufruf, d.dok_id)
            fakten, verworfen = validiere_extraktion(
                extraktion, sd.felder, d.seiten, d.dok_id, run_id)
            fall.fakten.extend(fakten)
            aus.extend(f"{d.dok_id}:{v}" for v in verworfen)
        return aus

    echt, pl.extrahieren = pl.extrahieren, erfundene_zitate
    try:
        fall = pl.fall_aus_verzeichnis(DREHKREUZ, "F-ROB-VERWORFEN")
    finally:
        pl.extrahieren = echt

    ereignis = next((e for e in fall.ereignisse if e.aktion == "extraktion_verworfen"), None)
    assert ereignis is not None, "der Prüfer hat zugeschlagen und nichts hinterlassen"
    assert ereignis.model_dump()["details"]["felder"]
    # and nothing survived to carry a confident verdict
    assert fall.aktuelle_pruefung().einordnung.startswith("unklar")
    assert schema_laden("preiserhoehung")     # der Lauf hat das Schema nicht beschädigt


# --------------------------------------------------------------------------
# Values, rules and references the engine must not get generous about
# --------------------------------------------------------------------------


@pytest.mark.parametrize(("roh", "erwartet"), [
    ("29,90", 29.90),          # how the demo documents write it
    ("29.90", 29.90),          # how the live prompt used to ask for it
    ("1.234,56", 1234.56),
    ("29,90 EUR", 29.90),      # was dropped entirely before
    ("36,90 €", 36.90),
    (36.9, 36.9),
])
def test_betraege_werden_von_einem_parser_gelesen(roh, erwartet):
    """Two parsers for one format: `zeit.parse_betrag` was right and the
    adapter carried a cruder copy that stripped every dot, so „29.90" became
    2 990,00 € — on the live path only, which is why no test replaying a
    hand-written German-comma cache ever saw it."""
    from fallpruefer.adapter.basis import _wert_parsen
    from fallpruefer.schema import Feld

    assert _wert_parsen(roh, Feld(feld_id="x.betrag", typ="betrag")) == pytest.approx(erwartet)


@pytest.mark.parametrize(("schluessel", "wert", "erwartet"), [
    ("regel", {"NEIN_Wenn": True}, "unbekannter Regel-Schlüssel"),
    ("regel", {"sonst": "ja"}, "ist kein Zustand"),
    ("parameter", {"frist_min_tage": "90"}, "als Zahl schreiben"),
])
def test_der_jurist_edit_validator_faengt_die_tippfehler_die_menschen_machen(
    schluessel, wert, erwartet, tmp_path
):
    """Akt 2 is a person editing this JSON in a text editor while the program
    runs, and all three of these *loaded* before: the mis-cased rule key was
    ignored (so the Prüfpunkt returned the opposite state), the lowercase
    `sonst` crashed at runtime rather than at load, and a quoted number turned
    every comparison against it into „we cannot say", because `int < str` is a
    TypeError the grammar maps to None."""
    import copy
    import json as _json

    from fallpruefer import schema as sm

    roh = _json.loads((WURZEL / "schemas" / "preiserhoehung.json").read_text(encoding="utf-8"))
    d = copy.deepcopy(roh)
    ziel = next(p for p in d["pruefpunkte"] if p["id"] == "P10")
    ziel.setdefault(schluessel, {}).update(wert)
    (tmp_path / "preiserhoehung.json").write_text(_json.dumps(d, ensure_ascii=False), encoding="utf-8")

    sm._CACHE.clear()
    try:
        with pytest.raises(sm.SchemaFehler) as fehler:
            sm.schema_laden("preiserhoehung", verzeichnis=tmp_path)
        assert erwartet in str(fehler.value)
    finally:
        sm._CACHE.clear()


def test_eine_geleerte_bedingung_laesst_den_pruefpunkt_nicht_feuern():
    """`all([])` is True and `any([])` is False, and both are traps here: the
    Akt-2 beat is someone deleting conditions in an editor, and removing the
    last child of an `alle` would have made the Prüfpunkt fire."""
    from fallpruefer.regeln import auswerten

    class LeererKontext:
        def feld(self, name):        return None
        def dok_vorhanden(self, typ): return False

    k = LeererKontext()
    assert auswerten({"alle": []}, k) is None
    assert auswerten({"eine": []}, k) is None


@pytest.mark.parametrize(("verweis", "quelle", "erwartet"), [
    ("Ziffer 12", "Die Mindestlaufzeit beträgt 12 Monate.", False),
    ("Ziffer 12", "Ziffer 12: Der Beitrag kann angepasst werden.", True),
    ("Ziffer 12", "12) Der Beitrag kann angepasst werden.", True),
    ("Ziffer 5.2", "5.2 Der Betreiber darf den Beitrag anpassen.", True),
    ("Ziffer 5.2", "Die Laufzeit endet nach 5.24 Monaten.", False),
])
def test_der_klauselverweis_wird_nicht_von_einer_beliebigen_zahl_bestaetigt(
    verweis, quelle, erwartet
):
    """The primitive answers „has the letter shown its ground?". Plain
    substring matching confirmed „Ziffer 12" against „beträgt 12 Monate" —
    it reported a ground the document does not contain, which is the one
    outcome it exists to prevent."""
    from fallpruefer.primitiven import kreuzpruefung_klauselverweis

    class Kontext:
        def feld(self, name):
            return verweis if name == "erhoehungsschreiben.klauselverweis" else None

        def dok_text(self, typ):
            return quelle if typ == "agb" else ""

    assert kreuzpruefung_klauselverweis(Kontext(), {}) is erwartet


def test_ein_ausgebliebener_fallgruppen_vorschlag_ist_sichtbar():
    """Swallowed silently, the case fell through to STANDARD_FALLGRUPPE and an
    Inkasso complaint came back as a Preiserhöhung assessment complete with
    „das Erhöhungsschreiben fehlt" — a confident answer to a question nobody
    asked. Gate 2 corrects it, so the advisor has to be able to see it."""
    from fallpruefer import pipeline as pl

    def scheitert(fall, adapter):
        raise RuntimeError("CacheFehlt: kein Vorschlag")

    echt, pl.fallgruppe_vorschlagen = pl.fallgruppe_vorschlagen, scheitert
    try:
        fall = pl.fall_aus_verzeichnis(DREHKREUZ, "F-ROB-FALLGRUPPE")
    finally:
        pl.fallgruppe_vorschlagen = echt

    assert fall.fallgruppe.vorschlag_fehlt is True
    assert any(e.aktion == "fallgruppe_vorschlag_fehlgeschlagen" for e in fall.ereignisse)
    # the case still runs — a missing proposal must not stop intake (Gate 2 decides)
    assert fall.aktuelle_pruefung() is not None


# --------------------------------------------------------------------------
# Contradictions, and the golden runner that has to notice them
# --------------------------------------------------------------------------


def test_zwei_widersprechende_belegstellen_werden_markiert_statt_ausgewuerfelt():
    """Contract §9 defines `herkunft: strittig` and nothing set it, so the
    engine took whichever fact was appended last (`_faktum` ends
    `kandidaten[-1]`): a document contradicting itself turned `wirksam` into
    `wahrscheinlich unwirksam` with nothing on screen to say why. A
    contradiction is marked, not resolved — which of the two readings holds is
    a judgement, and judgements belong to the advisor."""
    from fallpruefer.adapter.basis import _widersprueche_markieren
    from fallpruefer.fall import Faktum
    from fallpruefer.vokabular import Herkunft

    fall = fall_aus_verzeichnis(WURZEL / "demo" / "faelle" / "sauber_aktivpark", "F-ROB-STRITTIG")
    assert fall.aktuelle_pruefung().einordnung == "wirksam"
    assert fall.aktuelle_pruefung().ergebnis("P7").zustand.value == "JA"

    echt = next(f for f in fall.fakten if f.feld_id == "agb.senkungspflicht")
    fall.fakten.append(Faktum(
        feld_id="agb.senkungspflicht", wert="keine", dok_id=echt.dok_id,
        herkunft=Herkunft.EXPLIZIT, quelle=echt.quelle, verifiziert=True,
    ))
    _widersprueche_markieren([f for f in fall.fakten if f.feld_id == "agb.senkungspflicht"])
    fall.pruefungen.append(pruefen(fall, _schema_von(fall), trigger="test"))

    erg = fall.aktuelle_pruefung().ergebnis("P7")
    assert erg.zustand.value == "FEHLT", "ein Widerspruch darf kein hartes NEIN tragen"
    assert erg.herkunft.value == "strittig"
    assert erg.badge.value == "nicht_gefunden"
    assert fall.aktuelle_pruefung().einordnung.startswith("unklar")


def test_uebereinstimmende_doppelbelege_bleiben_unauffaellig():
    """Two quotes saying the same thing are corroboration, not a conflict."""
    from fallpruefer.adapter.basis import _widersprueche_markieren
    from fallpruefer.fall import Faktum
    from fallpruefer.vokabular import Herkunft

    fakten = [
        Faktum(feld_id="agb.senkungspflicht", wert="pflicht", dok_id="D2",
               herkunft=Herkunft.EXPLIZIT, verifiziert=True),
        Faktum(feld_id="agb.senkungspflicht", wert="pflicht", dok_id="D3",
               herkunft=Herkunft.EXPLIZIT, verifiziert=True),
    ]
    _widersprueche_markieren(fakten)
    assert all(f.herkunft is Herkunft.EXPLIZIT and f.verifiziert for f in fakten)


def test_der_golden_runner_meldet_einen_vertippten_erwartet_schluessel():
    """Renaming every expectation key in a golden file deleted all of its
    coverage and stayed green. These files get hand-edited exactly when a
    Lösungszettel arrives (15 §13) — which is when a typo happens."""
    import json as _json

    from fallpruefer import golden

    quelle = WURZEL / "tests" / "golden" / "drehkreuz.json"
    d = _json.loads(quelle.read_text(encoding="utf-8"))
    stufen = d.get("stufen") or d.get("stages") or []
    for stufe in stufen:
        e = stufe["erwartet"]
        for alt, neu in (("zustaende", "zustaend"), ("gekippte_pruefpunkte", "gekippte_pruefpunkt")):
            if alt in e:
                e[neu] = e.pop(alt)

    ziel = Path(tempfile.mkdtemp()) / "drehkreuz.json"
    ziel.write_text(_json.dumps(d, ensure_ascii=False), encoding="utf-8")
    erg = golden.lauf(ziel)
    assert not erg.gruen
    assert any("unbekannter erwartet-Schlüssel" in a.was for a in erg.abweichungen)


def test_ein_unbekanntes_verdikt_gilt_nicht_als_unklar():
    """`_zweig` folded anything unrecognised into „unklar", which blinded the
    runner's own safety metric: „falsche sichere Antworten" counts an expected
    unklar answered as a hard verdict, and a garbled verdict string was filed
    as a correct unklar instead."""
    from fallpruefer.golden import _zweig

    assert _zweig("wirksam") == "wirksam"
    assert _zweig("unklar – es fehlt: die AGB") == "unklar"
    for kaputt in ("", "banana", "Kein einseitiger Eingriff — …", "unklar weil"):
        assert _zweig(kaputt).startswith("UNBEKANNT"), kaputt


# --------------------------------------------------------------------------
# Stufe B/C — the second Fallgruppe has to be openable
# --------------------------------------------------------------------------


def test_eine_fallgruppe_ohne_pruefschema_ist_darstellbar():
    """`neu_pruefen` ran only `if schema.pruefpunkte`, so a Fallgruppe without a
    Prüfschema produced no Soll and no Prüfung at all: `ansicht.bauen` refused
    the case (HTTP 409) and a Gate-2 switch left the *previous* Fallgruppe's red
    verdict, filled Widerspruch and trace standing under the new „nicht
    hinterlegt" header.

    Written against `inkasso` while that file was still a stub. Inkasso has had
    fourteen Prüfpunkte since v0.3.0, so the empty case now needs an actually
    empty schema — `klausel_check` (Stufe C) is one. The invariant is unchanged
    and is about empty schemas, not about Inkasso.
    """
    from fallpruefer import ansicht
    from fallpruefer.pipeline import gate2_fallgruppe
    from fallpruefer.schema import schema_laden

    fall = fall_aus_verzeichnis(DREHKREUZ, "F-ROB-LEER")
    assert fall.aktuelle_pruefung().einordnung == "wahrscheinlich unwirksam"

    gate2_fallgruppe(fall, "klausel_check")
    sicht = ansicht.bauen(fall, schema_laden("klausel_check"))

    # no verdict is claimed, and the limitation sentence stands in its place
    assert fall.aktuelle_pruefung().einordnung_code is None
    assert sicht.hero.einordnung.tone == "grau"
    # `label` is the Stufe-specific sentence from `config.texte` (18 #19) and
    # differs between B and C — the invariant is the code and its basis, not
    # the wording, which an editor may change without changing behaviour.
    assert sicht.hero.einordnung.code == "keine_pruefung"
    assert sicht.hero.einordnung.label_basis == "keine Prüfung hinterlegt"
    assert sicht.hero.einordnung.label.strip()
    # the old Fallgruppe's letter and remedy are gone, not left on screen
    assert sicht.musterbrief is None
    assert not fall.rechtsbehelf.vorschlaege


def test_ein_schema_stopp_raeumt_die_vorige_fallgruppe_ab():
    """The same clean-up, but through the door Stufe B now actually walks
    through: Inkasso has rules, and its first one is a gate.

    Switching a fitness case to `inkasso` no longer hits „nichts hinterlegt" —
    it hits P1, which stops the schema because there is no Inkassoschreiben.
    That is a better answer than the placeholder was: it names the reason
    instead of the gap. What must still hold is that no verdict is claimed, the
    previous Fallgruppe's letter is gone, and what 14 §2 promises for Stufe B —
    Dokumenten-Soll and Gate 1 — runs anyway.
    """
    from fallpruefer import ansicht
    from fallpruefer.pipeline import gate1_nachforderung, gate2_fallgruppe
    from fallpruefer.schema import schema_laden

    fall = fall_aus_verzeichnis(DREHKREUZ, "F-ROB-STUFEB")
    gate2_fallgruppe(fall, "inkasso")
    pruefung = fall.aktuelle_pruefung()
    sicht = ansicht.bauen(fall, schema_laden("inkasso"))

    assert pruefung.einordnung_code is None
    assert "Inkassoschreiben" in (pruefung.schema_stopp_text or "")
    assert sicht.hero.einordnung.tone == "grau"
    assert sicht.musterbrief is None
    assert not fall.rechtsbehelf.vorschlaege
    # …and what Stufe B *does* promise runs: the Inkasso Soll and Gate 1
    assert "inkassoschreiben" in fall.dokumenten_soll["gefordert"]
    assert gate1_nachforderung(fall).dokumente


def test_kein_begruendungssatz_traegt_eine_rechtliche_aussage(tmp_path):
    """`begruendung_satz` is pasted verbatim into the Gate-1 letter, which may
    not assess anything (14 §4 step 3). The runtime lint caught it — at the
    button press. The schema author hears about it at load now."""
    import copy
    import json as _json

    from fallpruefer import schema as sm

    d = _json.loads((WURZEL / "schemas" / "inkasso.json").read_text(encoding="utf-8"))
    kaputt = copy.deepcopy(d)
    kaputt["dokumenten_soll"]["dokumente"][0]["begruendung_satz"] = (
        "Damit prüfen wir, ob die Forderung wirksam ist."
    )
    (tmp_path / "inkasso.json").write_text(_json.dumps(kaputt, ensure_ascii=False), encoding="utf-8")

    sm._CACHE.clear()
    try:
        with pytest.raises(sm.SchemaFehler, match="rechtliche Aussage"):
            sm.schema_laden("inkasso", verzeichnis=tmp_path)
    finally:
        sm._CACHE.clear()


def test_ein_gestopptes_schema_hinterlaesst_ein_ereignis():
    """Contract §2/§12 name a `schema_stopp` event and no code wrote one, so
    the single outcome that ends an assessment left no line in the audit trail
    the RDG framing rests on."""
    from fallpruefer.pipeline import gate3_override

    fall = fall_aus_verzeichnis(DREHKREUZ, "F-ROB-STOPP")
    gate3_override(fall, "P0", "NEIN", grund="Echter Änderungsvertrag.")

    assert fall.aktuelle_pruefung().schema_stopp_text
    assert any(e.aktion == "schema_stopp" for e in fall.ereignisse)


def test_gate4_aktualisiert_den_store_satz_eines_bestaetigten_falls(tmp_path, monkeypatch):
    """Contract §8: „written at Gate 3 confirmation (and updated at Gate 4)".
    Only Gate 3 and the Referat flag wrote, so `rechtsbehelf` froze on the
    program's first proposal — and that field is the Referat's evaluation of
    which remedies the advisors actually need."""
    import json as _json

    from fallpruefer import store
    from fallpruefer.pipeline import gate3_bestaetigen, gate4_rechtsbehelf

    ziel = tmp_path / "faelle.jsonl"
    monkeypatch.setattr(store, "pfad", lambda: ziel)

    fall = fall_aus_verzeichnis(NORDLICHT, "F-ROB-GATE4")
    vorschlaege = fall.rechtsbehelf.vorschlaege
    assert len(vorschlaege) >= 2, vorschlaege

    gate3_bestaetigen(fall)
    zeilen = ziel.read_text(encoding="utf-8").strip().splitlines()
    assert _json.loads(zeilen[-1])["rechtsbehelf"] == fall.rechtsbehelf.hauptvorschlag

    andere = next(v for v in vorschlaege if v != fall.rechtsbehelf.hauptvorschlag)
    gate4_rechtsbehelf(fall, andere)
    zeilen = ziel.read_text(encoding="utf-8").strip().splitlines()
    assert _json.loads(zeilen[-1])["rechtsbehelf"] == andere
    assert len(zeilen) == 1, "der Satz wird aktualisiert, nicht dupliziert"


def test_ein_unbestaetigter_fall_kommt_durch_gate4_nicht_in_den_store(tmp_path, monkeypatch):
    """The other half of the same rule: Gate 4 updates a row, it never creates
    one — an unconfirmed run is a proposal, and a Radar built from proposals
    counts the program's opinions."""
    from fallpruefer import store
    from fallpruefer.pipeline import gate4_rechtsbehelf

    ziel = tmp_path / "faelle.jsonl"
    monkeypatch.setattr(store, "pfad", lambda: ziel)

    fall = fall_aus_verzeichnis(NORDLICHT, "F-ROB-GATE4B")
    gate4_rechtsbehelf(fall, fall.rechtsbehelf.vorschlaege[0])
    assert not ziel.exists() or not ziel.read_text(encoding="utf-8").strip()


def test_die_fallgruppe_aus_dem_intake_gewinnt_gegen_den_modellvorschlag():
    """`POST /faelle` declares `fallgruppe_id` and discarded it: only
    `SchemaRef` was set, `fallgruppe.gewaehlt` stayed empty, and the proposal
    overwrote it on every intake — so the Stufe-B/C beat was not reachable over
    HTTP by any route that shows it correctly."""
    klient = TestClient(app)
    ticket = json.loads((NORDLICHT / "ticket.json").read_text(encoding="utf-8"))
    antwort = klient.post("/faelle", json={
        "freitext": ticket["freitext"], "anbieter": ticket["anbieter"], "branche": "fitness",
        "identitaet": ticket["identitaet"], "case_id": "F-ROB-HINT",
        "fallgruppe_id": "klausel_check",
        "anhaenge": [{"dateiname": "schreiben.md",
                      "text": (NORDLICHT / "schreiben.md").read_text(encoding="utf-8")}],
    })
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["fallgruppe_id"] == "klausel_check"
    assert antwort.json()["stufe"] == "C"
    # a hint, not a Gate-2 confirmation
    assert klient.get("/faelle/F-ROB-HINT").json()["kopf"]["fallgruppe_bestaetigt"] is False


# --------------------------------------------------------------------------
# House style and the corpus
# --------------------------------------------------------------------------


def test_auskunft_bekommt_vier_wochen_und_geld_vierzehn_tage():
    """The VZ house style read off the eight original Musterbriefe (22 §8) has
    two deadline standards: 14 days for money back, four weeks for information.
    One config value gave every letter the money deadline — including the
    Auskunftsverlangen, which is half of the guaranteed pair in the `wirksam`
    branch and therefore on screen."""
    import re

    from fallpruefer.pipeline import gate4_rechtsbehelf

    fall = fall_aus_verzeichnis(WURZEL / "demo" / "faelle" / "sauber_aktivpark", "F-ROB-FRIST")
    fristen = {}
    for rid in fall.rechtsbehelf.vorschlaege:
        gate4_rechtsbehelf(fall, rid)
        treffer = re.search(r"bis zum (\d{2}\.\d{2}\.\d{4})", fall.rechtsbehelf.brief.text)
        fristen[fall.rechtsbehelf.brief.template_id] = treffer.group(1) if treffer else None

    assert fristen["musterbrief_auskunftsverlangen"] == "24.09.2026"   # vier Wochen
    assert fristen["musterbrief_kuendigung"] == "10.09.2026"           # 14 Tage


def test_eine_wirksame_erhoehung_heisst_nicht_noch_nicht_wirksam():
    """`monate_zwischen` counts whole months, so an increase effective on the
    1st read „noch nicht wirksam" for its first 30 days — a false statement in
    the Schadenshöhe line the Referat reads for „bedeutsame Schadenshöhe"."""
    from datetime import date

    from fallpruefer import brief as brief_modul, zeit as zeit_modul

    class Kontext:
        def __init__(self, ab):
            self.ab = ab

        def feld(self, name):
            return {"erhoehungsschreiben.alter_betrag": 29.90,
                    "erhoehungsschreiben.neuer_betrag": 36.90}.get(name)

        def datum(self, name):
            return self.ab

    class OhneRueckforderung:
        ergebnisse: list = []

    echt, zeit_modul.heute = zeit_modul.heute, lambda: date(2026, 8, 27)
    try:
        assert "noch nicht wirksam" in brief_modul._schadenshoehe(
            OhneRueckforderung(), Kontext(date(2026, 9, 1)))
        assert "noch nicht wirksam" not in brief_modul._schadenshoehe(
            OhneRueckforderung(), Kontext(date(2026, 8, 1)))
        assert "3 Monate" in brief_modul._schadenshoehe(
            OhneRueckforderung(), Kontext(date(2026, 5, 27)))
    finally:
        zeit_modul.heute = echt


def test_die_referat_markierung_verlangt_gate_3(tmp_path, monkeypatch):
    """`store.py` states the invariant („every confirmed case counts") and
    `gate3_bestaetigen` gives the reason: a Radar built from unconfirmed runs
    counts the program's opinions rather than the advisory's findings. The flag
    wrote a row — and a Radar +1 — with Gate 3 never pressed. 14 §4 already
    puts Gate 3 (step 6) before the flag (step 9); now the code says so."""
    from fallpruefer import store
    from fallpruefer.pipeline import gate3_bestaetigen, referat_markieren

    monkeypatch.setattr(store, "pfad", lambda: tmp_path / "faelle.jsonl")

    fall = fall_aus_verzeichnis(DREHKREUZ, "F-ROB-REFERAT")
    with pytest.raises(ValueError, match="Gate 3"):
        referat_markieren(fall, ["neuigkeitswert"], "Test")
    assert not (tmp_path / "faelle.jsonl").exists()

    gate3_bestaetigen(fall)
    satz = referat_markieren(fall, ["neuigkeitswert"], "Test")
    assert satz["referat_flag"] == ["neuigkeitswert"]
