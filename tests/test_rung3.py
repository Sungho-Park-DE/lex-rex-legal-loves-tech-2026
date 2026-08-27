"""Rung 3 of the ladder (14 §10) — the gates, and the Act-2 Jurist-Edit.

Six actions plus a schema reload, and one property that matters more than any
of them: **every gate leaves an event**. The RDG framing (14 §8) rests on the
four gates being an audit trail, and a gate that changes the case silently is
the single thing this design cannot afford — so the event names of contract
§12 are asserted, not assumed.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from fallpruefer import brief, evaluator, pipeline as pl
from fallpruefer.api import app
from fallpruefer.dokumente import laden
from fallpruefer.konfig import WURZEL
from fallpruefer.schema import SchemaFehler, schema_geaendert, schema_laden

NORDLICHT = WURZEL / "demo" / "faelle" / "nordlicht_agb_fehlen"
SEEPARK = WURZEL / "demo" / "faelle" / "seepark_seite_fehlt"
SCHEMA = WURZEL / "schemas" / "preiserhoehung.json"


def _fall(verzeichnis, dateien, case_id):
    ticket = json.loads((verzeichnis / "ticket.json").read_text(encoding="utf-8"))
    dokumente = [laden(verzeichnis / n, f"D{i}") for i, n in enumerate(dateien, start=1)]
    return pl.verarbeiten(pl.fall_anlegen(case_id, ticket, dokumente))


@pytest.fixture
def unklar_fall():
    return _fall(NORDLICHT, ["schreiben.md"], "F-GATE-1")


def _aktionen(fall) -> list[str]:
    return [e.aktion for e in fall.ereignisse]


# --------------------------------------------------------------------------
# Gate 1 — Nachforderung
# --------------------------------------------------------------------------


def test_gate1_erzeugt_den_text_und_verschickt_nichts(unklar_fall):
    n = pl.gate1_nachforderung(unklar_fall)
    assert n.status.value == "offen", "eine erzeugte Nachforderung gilt nie als verschickt"
    assert [d.value for d in n.dokumente] == ["agb", "vertrag"], "je Dokument ein Eintrag"
    assert n.text.count("- die AGB") == 1, "dasselbe Dokument zweimal angefordert"
    assert "unwirksam" not in n.text and "Anspruch" not in n.text
    assert "gate1_nachforderung_erzeugt" in _aktionen(unklar_fall)

    pl.nachforderung_status(unklar_fall, n.id, "angefordert")
    assert unklar_fall.nachforderungen[0].status.value == "angefordert"
    assert "gate1_nachforderung_markiert" in _aktionen(unklar_fall)


def test_gate1_kann_auf_einzelne_dokumente_beschraenkt_werden(unklar_fall):
    n = pl.gate1_nachforderung(unklar_fall, dokumenttypen=["agb"])
    assert [d.value for d in n.dokumente] == ["agb"]
    # the Vertrag is not requested — it only appears as a place to look for the
    # AGB („Mitgliedsvertrag (Rückseite/Anlage)"), which is the Beschaffungsweg
    assert "den Mitgliedsvertrag oder das Anmeldeformular" not in n.text


def test_gate1_fordert_nichts_an_wenn_verbraucherseitig_nichts_offen_ist():
    """The company side is an Auskunftsverlangen at Gate 4, never a Nachforderung."""
    fall = _fall(WURZEL / "demo" / "faelle" / "sauber_aktivpark",
                 ["schreiben.md", "agb.md", "vertrag.md"], "F-GATE-2")
    offen = fall.aktuelle_pruefung().vollstaendigkeit
    assert offen["unternehmen"] and not offen["verbraucher"]
    with pytest.raises(ValueError):
        pl.gate1_nachforderung(fall)


# --------------------------------------------------------------------------
# Gate 2 / Gate 3 / Gate 4
# --------------------------------------------------------------------------


def test_gate2_bestaetigt_ohne_neuen_lauf(unklar_fall):
    vorher = len(unklar_fall.pruefungen)
    pl.gate2_fallgruppe(unklar_fall, "preiserhoehung")
    assert unklar_fall.fallgruppe.bestaetigt
    assert len(unklar_fall.pruefungen) == vorher, "Bestätigen ist keine Änderung"
    assert "gate2_fallgruppe_gewaehlt" in _aktionen(unklar_fall)
    with pytest.raises(ValueError):
        pl.gate2_fallgruppe(unklar_fall, "gibt_es_nicht")


def test_gate3_override_verlangt_einen_grund(unklar_fall):
    with pytest.raises(ValueError):
        pl.gate3_override(unklar_fall, "P4", "JA", "   ")
    assert not unklar_fall.overrides, "ein Override ohne Grund darf nicht entstehen"


def test_gate3_override_laeuft_neu_und_laesst_sich_zuruecknehmen(unklar_fall):
    pl.gate3_override(unklar_fall, "P4", "JA", "AGB liegen der Beraterin aus einem Parallelfall vor")
    pruefung = unklar_fall.aktuelle_pruefung()
    assert pruefung.trigger == "override"
    erg = pruefung.ergebnis("P4")
    assert erg.zustand.value == "JA" and erg.override and erg.herkunft.value == "override"
    assert "gate3_override" in _aktionen(unklar_fall)

    pl.gate3_override(unklar_fall, "P4", zurueckziehen=True)
    assert unklar_fall.aktuelle_pruefung().ergebnis("P4").zustand.value == "FEHLT"
    assert "gate3_override_zurueckgezogen" in _aktionen(unklar_fall)


def test_gate3_override_ueberlebt_eine_nachreichung(unklar_fall):
    """Contract §4: an override persists across later runs unless withdrawn —
    the advisor should not have to re-decide the same question."""
    pl.gate3_override(unklar_fall, "P8", "NEIN", "Laufzeitregel verstößt gegen § 309 Nr. 9 n.F.")
    fall = pl.nachreichung(unklar_fall, [
        laden(NORDLICHT / "agb_nachgereicht.md"),
        laden(NORDLICHT / "vertrag_nachgereicht.md"),
    ])
    erg = fall.aktuelle_pruefung().ergebnis("P8")
    assert erg.zustand.value == "NEIN" and erg.override


def test_gate4_nimmt_nur_an_was_auch_vorgeschlagen_wurde(unklar_fall):
    with pytest.raises(ValueError):
        pl.gate4_rechtsbehelf(unklar_fall, "kuendigung_bei_wirksam")
    pl.gate4_rechtsbehelf(unklar_fall, "bestreiten_nachweise_verlangen")
    assert unklar_fall.rechtsbehelf.gewaehlt == "bestreiten_nachweise_verlangen"
    assert unklar_fall.rechtsbehelf.brief.template_id == "musterbrief_auskunftsverlangen"
    assert "gate4_rechtsbehelf_gewaehlt" in _aktionen(unklar_fall)
    # Wer gewählt hat, steht am Fall und nicht nur im Ereignislog: die Zeile
    # wurde gesetzt und von `rechtsbehelf_und_brief` sofort wieder überschrieben,
    # war also in jedem laufenden Fall None.
    assert unklar_fall.rechtsbehelf.gate4_von == "Beraterin"


# --------------------------------------------------------------------------
# Abschluss
# --------------------------------------------------------------------------


def test_abschluss_erzeugt_einen_basis_eintrag_ohne_identitaet(unklar_fall):
    pl.abschluss(unklar_fall, basis_export=True, schliessen=True)
    text = unklar_fall.abschluss.basis_text
    assert text and "Fallgruppe:" in text and "Einordnung:" in text
    for geheim in ("Sabine", "Kortmann", "Bahnhofstraße", "AB-771904"):
        assert geheim not in text, f"Basis-Eintrag enthält „{geheim}“"
    assert "@@" not in text
    assert unklar_fall.status.value == "geschlossen"
    assert {"abschluss_basis_export", "fall_geschlossen"} <= set(_aktionen(unklar_fall))


# --------------------------------------------------------------------------
# Akt 2 — Jurist-Edit
# --------------------------------------------------------------------------


def test_schema_wird_nach_einer_dateiaenderung_neu_gelesen():
    """„Das Papier und der Code sind dieselbe Datei" (14 §7 Akt 2) has to hold
    in a running process — a cache that needs a restart makes it a slogan."""
    sicherung = SCHEMA.read_text(encoding="utf-8")
    try:
        vorher = schema_laden("preiserhoehung").pruefpunkt("P10").parameter["frist_min_tage"]
        assert not schema_geaendert("preiserhoehung")

        daten = json.loads(sicherung)
        for pp in daten["pruefpunkte"]:
            if pp["id"] == "P10":
                pp["parameter"]["frist_min_tage"] = vorher + 60
        SCHEMA.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")

        assert schema_geaendert("preiserhoehung")
        assert schema_laden("preiserhoehung").pruefpunkt("P10").parameter["frist_min_tage"] == vorher + 60
    finally:
        SCHEMA.write_text(sicherung, encoding="utf-8")
    assert schema_laden("preiserhoehung").pruefpunkt("P10").parameter["frist_min_tage"] == vorher


def test_ein_kaputter_jurist_edit_nimmt_das_laufende_schema_nicht_mit():
    """A typo during a live demo must not take the program down: the last good
    version keeps serving and the error names the file."""
    sicherung = SCHEMA.read_text(encoding="utf-8")
    version = schema_laden("preiserhoehung").version
    try:
        SCHEMA.write_text("{ das ist kein JSON", encoding="utf-8")
        with pytest.raises(SchemaFehler) as fehler:
            schema_laden("preiserhoehung")
        assert version in str(fehler.value)
    finally:
        SCHEMA.write_text(sicherung, encoding="utf-8")
    assert schema_laden("preiserhoehung").version == version


def test_waehrend_eines_kaputten_edits_bleibt_die_fallakte_lesbar():
    """The other half of #40, found in a cold pass: `neu-pruefen` correctly
    refuses a broken file — but between „save with typo" and „fix typo" the
    Fallakte view must keep serving the last good version, not 500. A read
    path that dies mid-Jurist-Edit takes the whole demo screen with it."""
    klient = TestClient(app)
    ticket = json.loads((NORDLICHT / "ticket.json").read_text(encoding="utf-8"))
    klient.post("/faelle", json={
        "freitext": ticket["freitext"], "anbieter": ticket["anbieter"], "branche": "fitness",
        "identitaet": ticket["identitaet"], "case_id": "F-2026-9702",
        "anhaenge": [{"dateiname": "schreiben.md",
                      "text": (NORDLICHT / "schreiben.md").read_text(encoding="utf-8")}],
    })
    sicherung = SCHEMA.read_text(encoding="utf-8")
    try:
        SCHEMA.write_text("{ das ist kein JSON", encoding="utf-8")
        # the editor hears about the typo…
        assert klient.post("/faelle/F-2026-9702/neu-pruefen").status_code == 409
        # …and everyone else keeps working on the last good version
        assert klient.get("/faelle/F-2026-9702").status_code == 200
        stand = klient.get("/schema/preiserhoehung")
        assert stand.status_code == 200
        assert stand.json()["fehler"] and stand.json()["version"] == __import__("json").loads(sicherung)["version"]
        assert klient.post("/faelle/F-2026-9702/override", json={
            "pruefpunkt_id": "P4", "neuer_zustand": "JA", "grund": "Parallelfall",
        }).status_code == 200
    finally:
        SCHEMA.write_text(sicherung, encoding="utf-8")
    assert klient.get("/schema/preiserhoehung").json()["fehler"] is None


def test_jurist_edit_aendert_die_einordnung_desselben_falls():
    """The whole Act-2 beat in one test: one number in the JSON turns a
    `wirksam` case into `unklar`, and the trace names the question."""
    fall = _fall(SEEPARK, ["schreiben.md", "bedingungen_seite1.md", "vertrag.md"], "F-GATE-3")
    fall = pl.nachreichung(fall, [laden(SEEPARK / "bedingungen_seite2_nachgereicht.md")])
    assert fall.aktuelle_pruefung().einordnung == "wirksam"

    sicherung = SCHEMA.read_text(encoding="utf-8")
    try:
        daten = json.loads(sicherung)
        for pp in daten["pruefpunkte"]:
            if pp["id"] == "P10":
                pp["parameter"]["frist_min_tage"] = 90
        daten["version"] = "0.2.1-test"
        SCHEMA.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")

        pl.neu_pruefen_nach_schema(fall)
        pruefung = fall.aktuelle_pruefung()
        assert pruefung.trigger == "schema_reload"
        assert pruefung.einordnung.startswith("unklar")
        assert pruefung.ergebnis("P10").zustand.value == "WERTUNG"
        assert fall.schema_.version == "0.2.1-test"
        assert "schema_geladen" in _aktionen(fall)
        # the earlier verdict stays readable next to the new one
        assert [p.einordnung for p in fall.pruefungen][-2] == "wirksam"
    finally:
        SCHEMA.write_text(sicherung, encoding="utf-8")


def _seepark_unklar_wegen_bewertung(case_id: str, schema_umbau=None):
    """Seepark bis `wirksam`, dann `frist_min_tage` auf 90 — damit kippt der
    Grund des „unklar" von einem fehlenden *Dokument* auf eine fehlende
    *Bewertung*, und verbraucherseitig ist nichts mehr offen.

    `schema_umbau` darf zusätzlich am Schema drehen; damit lässt sich der
    Zustand *vor* V-39 herstellen, ohne ihn wieder einzubauen.
    """
    fall = _fall(SEEPARK, ["schreiben.md", "bedingungen_seite1.md", "vertrag.md"], case_id)
    fall = pl.nachreichung(fall, [laden(SEEPARK / "bedingungen_seite2_nachgereicht.md")])

    sicherung = SCHEMA.read_text(encoding="utf-8")
    try:
        daten = json.loads(sicherung)
        for pp in daten["pruefpunkte"]:
            if pp["id"] == "P10":
                pp["parameter"]["frist_min_tage"] = 90
        if schema_umbau:
            schema_umbau(daten)
        SCHEMA.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")
        pl.neu_pruefen_nach_schema(fall)
    finally:
        SCHEMA.write_text(sicherung, encoding="utf-8")
    return fall


def test_unklar_wegen_bewertung_fordert_keine_unterlagen_nach():
    """Two kinds of „unklar" (14 §5) that the schema's `garantie_pro_zweig`
    does not tell apart: a missing *document* and a missing *judgement*.

    When the case is unclear because a tragend Prüfpunkt is WERTUNG, nothing is
    open on the consumer side — a Nachforderung would ask for a list that does
    not exist.

    Seit V-39 entscheidet das die **Bedingung des Rechtsbehelfs**, nicht mehr
    der Rettungsversuch beim Rendern: `nachforderung` verlangt jetzt
    `fehlt_verbraucher != []`, spiegelbildlich zu `bestreiten_nachweise_verlangen`.
    Deshalb steht der unfüllbare Brief hier gar nicht mehr an erster Stelle —
    und es gibt auch kein `brief_nicht_erzeugt` mehr, weil nichts mehr
    schiefgehen muss, damit das Richtige passiert.

    Die Garantie des Zweigs bleibt davon unberührt: `waehlen()` hängt jeden
    garantierten Rechtsbehelf an, auch wenn sein `wenn` nicht zutrifft. Die
    Beraterin sieht also weiterhin beide — nur in der anderen Reihenfolge.
    """
    fall = _seepark_unklar_wegen_bewertung("F-GATE-4")

    pruefung = fall.aktuelle_pruefung()
    assert pruefung.einordnung.startswith("unklar – es fehlt: Bewertung")
    assert not pruefung.vollstaendigkeit["verbraucher"], "verbraucherseitig ist nichts offen"

    r = fall.rechtsbehelf
    assert set(r.vorschlaege) == {"nachforderung", "bestreiten_nachweise_verlangen"}, \
        "die Garantie des Zweigs bleibt vollständig sichtbar"
    assert r.vorschlaege[0] == "bestreiten_nachweise_verlangen"
    assert r.hauptvorschlag == "bestreiten_nachweise_verlangen"
    assert r.brief and r.brief.template_id == "musterbrief_auskunftsverlangen"
    assert not [e for e in fall.ereignisse if e.aktion == "brief_nicht_erzeugt"], \
        "der unfüllbare Brief wurde gar nicht erst versucht — das ist der Punkt von V-39"


def test_ohne_die_bedingung_faengt_der_rettungsversuch_es_immer_noch():
    """Zweite Verteidigungslinie, und sie darf nicht ungetestet verrotten.

    V-39 macht den unfüllbaren Brief unmöglich, *weil das Schema es sagt*. Der
    Rettungsversuch in `rechtsbehelf_und_brief` bleibt trotzdem richtig: er
    gilt für jeden Rechtsbehelf, dessen Vorlage aus einem anderen Grund ein
    Loch hat. Dieser Test stellt den Zustand vor V-39 her — die Bedingung wird
    auf die alte Fassung zurückgedreht — und prüft, dass der Fall auch dann ein
    Urteil **und** ein Schreiben liefert.
    """
    def alte_bedingung(daten):
        for r in daten["rechtsbehelfe"]["liste"]:
            if r["id"] == "nachforderung":
                r["wenn"] = {"feld": "einordnung", "op": "==", "wert": "unklar – es fehlt …"}

    fall = _seepark_unklar_wegen_bewertung("F-GATE-4B", alte_bedingung)

    r = fall.rechtsbehelf
    assert r.vorschlaege[0] == "nachforderung", "ohne die Bedingung steht er wieder vorn"
    assert r.hauptvorschlag == "bestreiten_nachweise_verlangen", \
        "der Rettungsversuch hat übernommen"
    assert r.brief and r.brief.template_id == "musterbrief_auskunftsverlangen"
    uebersprungen = [e for e in fall.ereignisse if e.aktion == "brief_nicht_erzeugt"]
    assert uebersprungen and uebersprungen[-1].details["rechtsbehelf_id"] == "nachforderung"


def test_eine_bewusste_gate4_wahl_meldet_ihren_fehler_statt_ihn_zu_umgehen(unklar_fall):
    """The fallback is for the *proposal*. If the advisor picked a remedy and
    its letter cannot be filled, they have to see that — silently handing them
    a different letter than the one they clicked is worse than an error."""
    pl.gate4_rechtsbehelf(unklar_fall, "nachforderung")
    assert unklar_fall.rechtsbehelf.brief.template_id == "nachforderung_vbs"


def test_zwei_agb_dokumente_ueber_die_api_waehlen_die_vollstaendige_fassung():
    """Found in a cold pass: every earlier test ran in-process, where the
    fiction file's front matter supplies `fassung_datum`. Over the API there
    is no front matter, both AGB documents had no date, and the old tie-break
    (`agbs[0]`) picked the page *without* the clause — so the Soll reported the
    AGB incomplete while the Prüfpunkte, reading the other document through a
    fallback, said `wirksam`. Two answers to one question (18 #33)."""
    klient = TestClient(app)
    ticket = json.loads((SEEPARK / "ticket.json").read_text(encoding="utf-8"))
    klient.post("/faelle", json={
        "freitext": ticket["freitext"], "anbieter": ticket["anbieter"], "branche": "fitness",
        "identitaet": ticket["identitaet"], "case_id": "F-2026-9703",
        "anhaenge": [{"dateiname": n, "text": (SEEPARK / n).read_text(encoding="utf-8")}
                     for n in ("schreiben.md", "bedingungen_seite1.md", "vertrag.md")],
    })
    antwort = klient.post("/faelle/F-2026-9703/dokumente", json={"anhaenge": [
        {"dateiname": "bedingungen_seite2_nachgereicht.md",
         "text": (SEEPARK / "bedingungen_seite2_nachgereicht.md").read_text(encoding="utf-8")},
    ]})
    assert antwort.json()["einordnung"] == "wirksam"
    ansicht = klient.get("/faelle/F-2026-9703").json()
    assert ansicht["hero"]["vollstaendigkeit"]["verbraucher"] == [], \
        "Einordnung wirksam, aber die AGB gelten als unvollständig — zwei Antworten auf eine Frage"


# --------------------------------------------------------------------------
# the API surface the UI posts to
# --------------------------------------------------------------------------


def test_jede_gate_aktion_hat_einen_endpunkt(tmp_path, monkeypatch):
    """`/gate3` schreibt in den Store, und der Store entscheidet über das Radar.

    Ohne die Umleitung legte **jeder** `pytest`-Lauf eine weitere bestätigte
    Nordlicht-Zeile in `store/faelle.jsonl` ab. Gemessen: nach einem frischen
    `radar_seed` steht Nordlicht bei 2, nach zwei Suite-Läufen bei 4 — also über
    `k_min`, und Screen 2 zeigt einen Cluster, den die Aussaat nie vorgesehen
    hat. Für FitPoint 24 wäre derselbe Mechanismus der stille Tod des
    „+1"-Beats aus `14` §7.
    """
    from fallpruefer import store

    monkeypatch.setattr(store, "pfad", lambda: tmp_path / "faelle.jsonl")
    klient = TestClient(app)
    ticket = json.loads((NORDLICHT / "ticket.json").read_text(encoding="utf-8"))
    antwort = klient.post("/faelle", json={
        "freitext": ticket["freitext"], "anbieter": ticket["anbieter"], "branche": "fitness",
        "identitaet": ticket["identitaet"], "case_id": "F-2026-9701",
        "anhaenge": [{"dateiname": "schreiben.md",
                      "text": (NORDLICHT / "schreiben.md").read_text(encoding="utf-8")}],
    })
    assert antwort.status_code == 200, antwort.text
    basis = "/faelle/F-2026-9701"

    assert klient.post(f"{basis}/fallgruppe", json={"fallgruppe_id": "preiserhoehung"}).status_code == 200
    n = klient.post(f"{basis}/nachforderung", json={}).json()
    assert klient.post(f"{basis}/nachforderung",
                       json={"nachforderung_id": n["id"], "status": "angefordert"}).status_code == 200
    assert klient.post(f"{basis}/override", json={
        "pruefpunkt_id": "P4", "neuer_zustand": "JA", "grund": "aus einem Parallelfall bekannt",
    }).status_code == 200
    assert klient.post(f"{basis}/override", json={"pruefpunkt_id": "P4"}).status_code == 400
    assert klient.post(f"{basis}/rechtsbehelf",
                       json={"rechtsbehelf_id": "nachforderung"}).status_code == 200
    assert klient.post(f"{basis}/gate3", json={}).status_code == 200
    assert klient.post(f"{basis}/abschluss", json={"basis_export": True}).status_code == 200
    assert klient.post(f"{basis}/neu-pruefen").status_code == 200
    assert klient.get("/schema/preiserhoehung").status_code == 200

    ansicht = klient.get(basis).json()
    # Bewusst hartkodiert: ein Versionssprung soll ein bewusster Akt sein
    # und nicht dadurch passieren, dass ein Test die Konstante importiert,
    # gegen die er prueft. 1.4 = geprueft_von (V-A1) + fehlzustand (V-N2).
    assert ansicht["ansicht_version"] == "1.15"  # 1.15 = Anker.pruefstand
    assert len(ansicht["nachforderungen"]) == 1
    assert ansicht["nachforderungen"][0]["status"]["code"] == "angefordert"
    assert ansicht["laeufe"] and ansicht["laeufe"][-1]["aktuell"]
    assert ansicht["abschluss"]["basis_text"]


# --------------------------------------------------------------------------
# Gates are decisions, not decoration (14 §3: „P0 NEIN stops the schema,
# P5 NEIN deactivates the Inhaltskontrolle")
# --------------------------------------------------------------------------


def _drehkreuz(case_id):
    return _fall(WURZEL / "demo" / "faelle" / "drehkreuz",
                 ["schreiben.md", "agb.md", "vertrag.md"], case_id)


def test_override_auf_das_anwendungsbereich_gate_stoppt_das_schema():
    """Gate 3 has to reach the gates. „Das ist ein echter Änderungsvertrag" is
    exactly the sentence a Beraterin says at P0 — and until this was fixed the
    chip flipped to „nicht erfüllt" while the tool went on printing
    „wahrscheinlich unwirksam" and handing over a Widerspruch for a case it had
    just been told it must not judge."""
    fall = _drehkreuz("F-GATE-P0")
    assert fall.aktuelle_pruefung().einordnung == "wahrscheinlich unwirksam"
    assert fall.aktuelle_pruefung().schema_stopp_text is None

    pl.gate3_override(fall, "P0", "NEIN", grund="Echter Änderungsvertrag, kein einseitiger Eingriff.")

    p = fall.aktuelle_pruefung()
    assert p.ergebnis("P0").zustand.value == "NEIN"
    assert p.schema_stopp_text, "P0.bei_NEIN.schema_stopp muss nach dem Override greifen"
    assert p.einordnung == p.schema_stopp_text
    assert p.einordnung_code is None, "ein gestopptes Schema hat keine Einordnung"


def test_override_auf_das_kontrollfaehigkeits_gate_deaktiviert_die_inhaltskontrolle():
    """P5 NEIN means the clause states the original price, so there is nothing
    to control — P6–P9 must go INAKTIV rather than stay on screen with a state."""
    fall = _fall(WURZEL / "demo" / "faelle" / "sauber_aktivpark",
                 ["schreiben.md", "agb.md", "vertrag.md"], "F-GATE-P5")
    vorher = [fall.aktuelle_pruefung().ergebnis(i).zustand.value for i in ("P6", "P7", "P8", "P9")]
    assert "INAKTIV" not in vorher

    pl.gate3_override(fall, "P5", "NEIN", grund="Die Klausel regelt den ursprünglichen Preis.")

    p = fall.aktuelle_pruefung()
    assert [p.ergebnis(i).zustand.value for i in ("P6", "P7", "P8", "P9")] == ["INAKTIV"] * 4
    assert p.ergebnis("P6").inaktiv_grund, "die Deaktivierung muss ihren Grund mitführen"


def test_ein_offenes_gate_traegt_kein_hartes_urteil():
    """A gate asks a Vorfrage. Unanswered, it must not collapse into „kein
    Problem": the engine used to act on a gate only when it was NEIN, so a P0
    whose input never extracted still let the tool emit „wahrscheinlich
    unwirksam" plus a Musterschreiben. An already-`unklar` verdict is left
    alone — it names the document the advisor has to request, which is the
    more useful sentence."""
    fall = _drehkreuz("F-GATE-OFFEN")
    for faktum in [f for f in fall.fakten
                   if f.feld_id == "erhoehungsschreiben.grundlage_genannt"]:
        fall.fakten.remove(faktum)
    fall.pruefungen.append(evaluator.pruefen(fall, schema_laden("preiserhoehung"), trigger="test"))

    p = fall.aktuelle_pruefung()
    assert p.ergebnis("P0").zustand.value == "FEHLT"
    assert p.einordnung.startswith("unklar – es fehlt:")
    assert "Erhöhungsschreiben" in p.einordnung

    # and the two unklar demo cases, which run with P5 FEHLT, keep their own
    # wording — the gate rule downgrades, it never overwrites
    unklar = _fall(NORDLICHT, ["schreiben.md"], "F-GATE-OFFEN-2")
    assert unklar.aktuelle_pruefung().ergebnis("P5").zustand.value == "FEHLT"
    assert unklar.aktuelle_pruefung().einordnung == (
        "unklar – es fehlt: die AGB, die bei Vertragsschluss galten, "
        "den Mitgliedsvertrag oder das Anmeldeformular"
    )


# --------------------------------------------------------------------------
# the event log on screen (contract §12, view model 1.2)
# --------------------------------------------------------------------------


def test_jede_protokoll_aktion_im_code_hat_ein_vokabular():
    """The log's third column is only honest if every `protokoll()` call site
    has a label. A new call site without one would otherwise render its raw
    snake_case action on the advisor's screen."""
    import re
    from pathlib import Path

    from fallpruefer.vokabular import PROTOKOLL_SCHRITT, Protokollaktion

    paket = Path(__file__).resolve().parents[1] / "fallpruefer"
    im_code = {
        m.group(1)
        for datei in paket.rglob("*.py")
        for m in re.finditer(r"\.protokoll\(\s*[\"']([a-z0-9_]+)[\"']", datei.read_text("utf-8"))
    }
    assert im_code, "keine protokoll()-Aufrufe gefunden — der Test misst nichts"
    fehlend = im_code - {a.value for a in Protokollaktion}
    assert not fehlend, f"protokoll()-Aktionen ohne Vokabeleintrag: {sorted(fehlend)}"
    assert set(PROTOKOLL_SCHRITT) == set(Protokollaktion)

    from fallpruefer.ansicht import _PROTOKOLL_TEXT

    assert set(_PROTOKOLL_TEXT) == set(Protokollaktion)


def test_das_protokoll_nennt_rollen_und_keine_namen():
    """Contract §12: oversight evidence, not Leistungskontrolle. The guard sits
    in `Fall.protokoll` because `von` is threaded through every gate function
    and had reached one call already (`fall_geschlossen`)."""
    fall = _drehkreuz("F-PROTOKOLL-1")
    with pytest.raises(ValueError, match="Rollen, keine Namen"):
        fall.protokoll("gate3_bestaetigt", von="Frau Testberaterin")

    pl.abschluss(fall, basis_export=True, schliessen=True, von="Frau Testberaterin")
    for e in fall.ereignisse:
        assert e.akteur == "Beraterin"
        assert "Testberaterin" not in json.dumps(e.details, ensure_ascii=False)


def test_das_protokoll_erzaehlt_den_flip():
    """The two runs, the Nachforderung between them and the letter that follows
    have to be readable from the log alone — that is what makes it evidence."""
    from fallpruefer import ansicht

    fall = _fall(SEEPARK, ["schreiben.md", "bedingungen_seite1.md", "vertrag.md"],
                 "F-PROTOKOLL-2")
    pl.gate1_nachforderung(fall)
    fall = pl.nachreichung(fall, [laden(SEEPARK / "bedingungen_seite2_nachgereicht.md")])
    zeilen = ansicht.bauen(fall, schema_laden("preiserhoehung")).protokoll

    aktionen = [z.aktion.code for z in zeilen]
    assert aktionen.count("pruefung_gelaufen") == 2
    assert aktionen.index("gate1_nachforderung_erzeugt") < \
        aktionen.index("nachreichung_eingegangen") < \
        len(aktionen) - 1 - aktionen[::-1].index("pruefung_gelaufen")

    # every line is labelled, stepped and free of raw enum codes
    for z in zeilen:
        assert z.aktion.label and z.aktion.label != z.aktion.code
        assert z.schritt is not None
        assert z.aktion.tone in ("grau", "gelb"), \
            "ein Protokolleintrag ist kein Urteil — gruen/rot gehören der Einordnung"
    beschreibungen = " ".join(z.beschreibung for z in zeilen)
    assert "agb" not in beschreibungen and "AGB" in beschreibungen


def test_override_steht_mit_grund_im_protokoll():
    """Gate 3 is the RDG hinge: the advisor's reason has to be readable back,
    de-tokenised, in the same place a reviewer looks."""
    from fallpruefer import ansicht

    fall = _drehkreuz("F-PROTOKOLL-3")
    pl.gate3_override(fall, "P6", "JA", "Klausel im Gespräch geklärt")
    zeilen = ansicht.bauen(fall, schema_laden("preiserhoehung")).protokoll

    zeile = next(z for z in zeilen if z.aktion.code == "gate3_override")
    assert zeile.aktion.tone == "gelb", "eine Überschreibung muss beim Nachlesen auffallen"
    # Bis zum 26. Aug stand hier „P6 in beschreibung" — der Test hat damit die
    # undichte Stelle festgehalten statt sie zu verhindern. Lesbar heisst: der
    # Titel des Prüfpunkts, nicht seine id (dieselbe Regel wie R6/K62).
    assert "Transparenzgebot" in zeile.beschreibung, zeile.beschreibung
    assert "P6" not in zeile.beschreibung, "Prüfpunkt-id auf dem Schirm"
    assert "geklärt" in zeile.beschreibung
    assert zeile.schritt.label.endswith("Gate 3")


def test_ein_widerspruch_zeigt_beide_seiten_im_felderpanel():
    """Ein Gesprächswert, der einer Unterlage widerspricht, hinterlässt ZWEI
    Fakten auf demselben `feld_id`, beide `strittig` — und der Prüfpunkt geht
    genau deshalb auf WERTUNG. `Fallkontext._faktum` liefert davon eines; das
    ist für die Regel richtig und für den Schirm falsch. Vorher stand
    „widersprüchlich belegt" neben einem Wert, und wogegen er sprach, war
    nicht zu sehen — die Beraterin sollte an Gate 3 einen Konflikt auflösen,
    dessen andere Hälfte nicht auf dem Bildschirm stand."""
    from fallpruefer import ansicht, leitfaden as lf

    fall = _drehkreuz("F-WIDERSPRUCH")
    schema = schema_laden("preiserhoehung")

    # Ein Widerspruch ist nur dort möglich, wo die Frage ein Feld füllt, das
    # AUCH in den Unterlagen steht. Die meisten Leitfadenfragen füllen
    # `gespraech.*` — Felder, die kein Dokument je trägt. Genau eine Frage im
    # Fitness-Schema trifft auf eine Unterlage, und das ist die, auf die es
    # hier ankommt: `eruebrigt`, „steht schon in den Unterlagen".
    belegt = {f.feld_id for f in fall.fakten}
    frage = next(
        (f for f in lf.fragen(fall, schema) if any(z in belegt for z in f.fuellt)), None
    )
    assert frage is not None, \
        "keine Leitfadenfrage trifft auf eine Unterlage — der Test misst nichts"
    feld_id = next(z for z in frage.fuellt if z in belegt)
    aus_dokument = [f for f in fall.fakten if f.feld_id == feld_id]

    gegenteil = not bool(aus_dokument[-1].wert) if frage.typ == "ja_nein" else "abweichend"
    strittig = lf.antworten(fall, schema, {feld_id: gegenteil})
    assert feld_id in strittig, "der Widerspruch wurde gar nicht erkannt"

    fall.pruefungen.append(evaluator.pruefen(fall, schema, trigger="test"))
    sicht = ansicht.bauen(fall, schema)

    zeilen = [
        v for eintrag in sicht.pruefpfad.stufen for tr in eintrag.pruefpunkte
        for v in tr.verwendet if v.feld_id == feld_id
    ] + [
        v for tr in sicht.pruefpfad.ableitungen
        for v in tr.verwendet if v.feld_id == feld_id
    ]
    assert len(zeilen) >= 2, \
        f"nur {len(zeilen)} Zeile(n) für {feld_id} — die Gegenseite fehlt auf dem Schirm"
    assert len({z.wert_anzeige for z in zeilen}) >= 2, \
        "beide Zeilen zeigen denselben Wert — der Widerspruch ist unsichtbar"
    assert all(z.herkunft.code == "strittig" for z in zeilen)

    # Und wieder zurück. Korrigiert sich die Verbraucherin auf den Wert der
    # Unterlage, ist der Konflikt weg — das Dokument hat sich nie geändert, nur
    # die Aussage darüber. Die Sektion muss also verschwinden können und nicht
    # nur erscheinen; ein Panel, das den Widerspruch stehen lässt, behauptet
    # einen Streit, den es nicht mehr gibt.
    lf.antworten(fall, schema, {feld_id: aus_dokument[-1].wert})
    fall.pruefungen.append(evaluator.pruefen(fall, schema, trigger="test"))
    danach = ansicht.bauen(fall, schema)
    zurueck = [
        v for eintrag in danach.pruefpfad.stufen for tr in eintrag.pruefpunkte
        for v in tr.verwendet if v.feld_id == feld_id
    ] + [
        v for tr in danach.pruefpfad.ableitungen
        for v in tr.verwendet if v.feld_id == feld_id
    ]
    assert len(zurueck) == 1, f"nach der Korrektur stehen noch {len(zurueck)} Zeilen"
    assert zurueck[0].herkunft.code != "strittig"


def test_der_leitfaden_traegt_seinen_status_und_seine_reihenfolge():
    """Der Sinn des Panels ist, dass die vier Zustände verschieden aussehen —
    eine Liste, die alle Fragen gleich darstellt, wirft weg, wofür das Modul
    da ist. Und die Sortierung kommt aus dem Motor, nicht aus der UI."""
    from fallpruefer import ansicht

    fall = _drehkreuz("F-LEITFADEN-VM")
    sicht = ansicht.bauen(fall, schema_laden("preiserhoehung"))

    assert sicht.leitfaden.fragen, "keine Leitfadenfragen im Viewmodel"
    assert sicht.leitfaden.offen == sum(
        1 for f in sicht.leitfaden.fragen if f.status.code == "offen")

    raenge = {"offen": 0, "beantwortet": 1, "eruebrigt": 2, "entfaellt": 3}
    folge = [raenge[f.status.code] for f in sicht.leitfaden.fragen]
    assert folge == sorted(folge), "die Reihenfolge des Motors wurde in der Projektion verdreht"

    for f in sicht.leitfaden.fragen:
        assert f.status.label and f.status.tone in ("gruen", "gelb", "grau")
        assert f.typ in ("ja_nein", "zahl", "mehrfach", "text")
        if f.typ == "mehrfach":
            # `typ` steht an der Frage, `fuellt` an den Feldern: P13 fragt in
            # einem Satz nach der Strategie (Auswahl) UND danach, ob
            # zurückgefordert werden soll (ja/nein). Nur das Auswahlfeld hat
            # `werte`. Deshalb lautet die Regel für die Oberfläche: `werte`
            # vorhanden → Auswahl, sonst der `typ` der Frage. Eine Frage ganz
            # ohne `werte` wäre dagegen nicht darstellbar.
            assert any(z in f.werte for z in f.fuellt), \
                "mehrfach ohne jede erlaubte Wertliste — das Eingabefeld hätte nichts anzuzeigen"
        if f.status.code != "offen":
            assert f.grund, "ein nicht-offener Status ohne Begründung erklärt sich nicht"


# --------------------------------------------------------------------------
# Der Gate-4-Vorbehalt gilt nur für eine Wahl, die ein Mensch getroffen hat
# --------------------------------------------------------------------------


def _seepark_mit_frist(tage: int, gate4: str | None = None):
    """Seepark durch beide Stufen, während `frist_min_tage` auf `tage` steht.

    Genau der Weg, den ein zweiter Fall nach einem Jurist-Edit nimmt: die
    Datei ist schon geändert, wenn der Fall zum ersten Mal läuft — nicht erst
    danach. `neu_pruefen_nach_schema()` deckt nur die andere Reihenfolge ab.
    """
    sicherung = SCHEMA.read_text(encoding="utf-8")
    try:
        daten = json.loads(sicherung)
        for pp in daten["pruefpunkte"]:
            if pp["id"] == "P10":
                pp["parameter"]["frist_min_tage"] = tage
        SCHEMA.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")

        fall = _fall(SEEPARK, ["schreiben.md", "bedingungen_seite1.md", "vertrag.md"],
                     "F-GATE4-VORBEHALT")
        if gate4:
            pl.gate4_rechtsbehelf(fall, gate4)
        return pl.nachreichung(fall, [laden(SEEPARK / "bedingungen_seite2_nachgereicht.md")])
    finally:
        SCHEMA.write_text(sicherung, encoding="utf-8")


def test_der_selbst_gesetzte_hauptvorschlag_ist_keine_wahl_der_beraterin():
    """`rechtsbehelf_und_brief` schreibt `gewaehlt` bei jedem Lauf selbst.

    Wird `gewaehlt` beim nächsten Lauf als Entscheidung eines Menschen gelesen,
    greift der Vorbehalt „die Wahl der Beraterin wird geehrt, auch wenn der
    Brief nicht füllbar ist" für einen Vorschlag, den nie jemand gewählt hat —
    und der Fall fliegt mit einem BriefFehler aus der Prüfung statt ein Urteil
    zu liefern. Gemessen: mit `frist_min_tage: 90` kippt Seepark in Stufe 2 von
    „es fehlt ein Dokument" auf „es fehlt eine Bewertung", die Liste der
    fehlenden Unterlagen ist damit leer, und der aus Stufe 1 stehengebliebene
    `nachforderung` lässt sich nicht mehr rendern.

    `gate4_von` ist das Unterscheidungsmerkmal: nur `gate4_rechtsbehelf` setzt es.
    """
    fall = _seepark_mit_frist(90)

    assert fall.rechtsbehelf.gate4_von is None
    pruefung = fall.aktuelle_pruefung()
    assert pruefung.einordnung.startswith("unklar"), pruefung.einordnung
    assert "Bewertung" in pruefung.einordnung
    # Das Paar aus 14 §5: in jedem Zweig ein Urteil UND ein Schreiben
    assert fall.rechtsbehelf.brief is not None, \
        "Urteil ohne Schreiben — der Vorbehalt hat den Brief eines Vorschlags erzwungen, " \
        "den niemand gewählt hat"
    assert fall.rechtsbehelf.brief.text.strip()


def test_die_wahl_der_beraterin_wird_weiterhin_streng_geehrt():
    """Die andere Hälfte, damit die Korrektur den Vorbehalt nicht mit abräumt:
    hat die Beraterin an Gate 4 tatsächlich gewählt, bekommt sie den
    Renderfehler — und nicht still einen anderen Brief."""
    with pytest.raises(brief.BriefFehler):
        _seepark_mit_frist(90, gate4="nachforderung")


def test_ohne_jurist_edit_bleibt_seepark_die_gegenprobe():
    """Kontrolle: der Pfad oben ist ein Sonderfall des Edits, nicht der
    Normalzustand — mit der Frist aus der Datei bleibt Stufe 2 `wirksam`."""
    fall = _seepark_mit_frist(30)
    assert fall.aktuelle_pruefung().einordnung == "wirksam"


# --------------------------------------------------------------------------
# Die Knöpfe, die auf der Bühne gedrückt werden
# --------------------------------------------------------------------------


def _mutieren(pp: dict, attribut: str, rest: list[str]) -> bool:
    """Die kleinstmögliche echte Änderung an dem, was der Knopf adressiert.

    Rückgabe False heißt „für dieses Attribut gibt es hier keine Mutation" —
    dann ist der Knopf schon strukturell kaputt und der Test sagt das.
    """
    if attribut == "parameter":
        name = rest[0]
        if name not in (pp.get("parameter") or {}):
            return False
        wert = pp["parameter"][name]
        pp["parameter"][name] = wert * 3 if isinstance(wert, (int, float)) else wert
        return isinstance(wert, (int, float))
    if attribut == "rolle":
        pp["rolle"] = "ergaenzend" if pp["rolle"] == "tragend" else "tragend"
        return True
    if attribut == "anker":
        if not pp.get("anker"):
            return False
        pp["anker"] = []
        return True
    return False


def _messwerte() -> dict:
    """Alles, was ein Knopf an den vier Demofällen bewegen könnte — über beide
    Flip-Stufen, denn ein Knopf, der nur die zweite Stufe bewegt, zählt auch."""
    aus = {}
    for golden in sorted((WURZEL / "tests" / "golden").glob("*.json")):
        spec = json.loads(golden.read_text(encoding="utf-8"))
        verzeichnis = WURZEL / spec["fall_verzeichnis"]
        fall, gesehen = None, []
        for stufe in spec["stufen"]:
            namen = list(stufe["dokumente"])
            if fall is None:
                fall = _fall(verzeichnis, namen, spec["case_id"])
            else:
                fall = pl.nachreichung(
                    fall, [laden(verzeichnis / n) for n in namen if n not in gesehen])
            gesehen = namen
            p = fall.aktuelle_pruefung()
            aus[(spec["case_id"], stufe["name"])] = (
                p.einordnung,
                p.gerissene_stufe,
                tuple(sorted((e.pruefpunkt_id, e.zustand.value) for e in p.ergebnisse)),
                tuple(sorted({a for e in p.ergebnisse for a in (e.anker or [])})),
            )
    return aus


def test_jeder_jurist_edit_knopf_bewegt_auch_etwas():
    """Ein Knopf, der auf der Bühne gedrückt wird und nichts bewegt, ist
    schlimmer als keiner — und genau das war `pruefpunkte.P9.rolle`: über alle
    vier Demofälle und beide Flip-Stufen blieben Urteil, gerissene Stufe,
    sämtliche Zustände und die Ankermenge identisch, weil P9 im einen Fall
    neben P3/P6/P7 auf NEIN steht und in den anderen JA ist.

    Strukturell war der Knopf in Ordnung — er adressierte ein existierendes
    Attribut eines existierenden Prüfpunkts. Deshalb prüft dieser Test nicht
    die Struktur, sondern die Wirkung, und zwar an derselben Grenze, an der der
    Jurist steht: Datei ändern, Fälle laufen lassen, hinsehen.

    „Bewegt etwas" ist bewusst weit: ein Anker, der verschwindet, bewegt kein
    Urteil, aber sehr wohl den Bildschirm — das ist ein anderer Beat, kein
    toter Knopf.
    """
    schema = schema_laden("preiserhoehung")
    assert schema.jurist_edit_knoepfe, "keine Knöpfe im Schema"

    vorher = _messwerte()
    sicherung = SCHEMA.read_text(encoding="utf-8")
    ohne_wirkung = []
    try:
        for pfad in schema.jurist_edit_knoepfe:
            teile = pfad.split(".")
            assert teile[0] == "pruefpunkte" and len(teile) >= 3, f"{pfad}: unlesbarer Pfad"
            pid, attribut, rest = teile[1], teile[2], teile[3:]

            daten = json.loads(sicherung)
            treffer = [pp for pp in daten["pruefpunkte"] if pp["id"] == pid]
            assert treffer, f"{pfad} zeigt auf einen Prüfpunkt, den es nicht gibt"
            assert attribut in treffer[0], f"{pfad} zeigt auf ein Attribut, das es nicht gibt"
            assert _mutieren(treffer[0], attribut, rest), f"{pfad} ist nicht veränderbar"

            SCHEMA.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")
            if _messwerte() == vorher:
                ohne_wirkung.append(pfad)
            SCHEMA.write_text(sicherung, encoding="utf-8")
    finally:
        SCHEMA.write_text(sicherung, encoding="utf-8")

    assert not ohne_wirkung, (
        "diese Jurist-Edit-Knöpfe bewegen in keinem der vier Demofälle "
        f"irgendetwas: {ohne_wirkung} — entweder aus dem Schema nehmen oder "
        "einen Fall bauen, in dem sie entscheiden"
    )


def test_kein_protokolleintrag_verraet_eine_interne_kennung(tmp_path, monkeypatch):
    """Der Wächter aus `test_rung1` fragt Schemadateien, ob ein Anzeigesatz die
    eigene Bauweise ausplaudert. Das **Protokoll** hat er nie gefragt — und dort
    stand am 26. Aug genau das, in vier Zeilen: „R-1 · Auslöser: …",
    „P6 → erfüllt", „R-2" hinter „Einordnung bestätigt" und der rohe `fall_hash`
    hinter „Fallobjekt gespeichert".

    Gefunden hat es niemand über die Fixtures: drei von vier Zeilen entstehen
    erst an einem Gate, und die Fixtures fahren nicht jedes Gate. Deshalb fährt
    dieser Test den Weg selbst — genau die Regel aus `27` §1.3.

    `D1 → Erhöhungsschreiben` bleibt bewusst: die Dokumentkennung ist das
    Verweissystem der Zitate und steht so auf dem Dokumentstreifen daneben.
    """
    import re

    from fallpruefer import ansicht, store
    from tests.test_rung1 import INTERNE_SPRACHE

    monkeypatch.setattr(store, "pfad", lambda: tmp_path / "faelle.jsonl")

    fall = _drehkreuz("F-PROTOKOLL-WAECHTER")
    # kein Gate 1: drehkreuz ist verbraucherseitig vollständig, da gibt es
    # nichts nachzufordern. Die vier Zeilen, um die es geht, entstehen ohnehin
    # an Gate 3 und beim Speichern.
    pl.gate3_override(fall, "P6", "JA", "Klausel im Gespräch geklärt")
    pl.gate3_bestaetigen(fall)

    zeilen = ansicht.bauen(fall, schema_laden("preiserhoehung")).protokoll
    assert len(zeilen) > 6, "der Weg ist nicht gefahren — der Wächter prüft nichts"
    aktionen = {z.aktion.code for z in zeilen}
    for pflicht in ("gate3_override", "gate3_bestaetigt", "store_geschrieben", "pruefung_gelaufen"):
        assert pflicht in aktionen, f"{pflicht} fehlt — der Wächter deckt die Zeile nicht ab"

    muster = dict(INTERNE_SPRACHE)
    muster["Laufmarke"] = r"\bR-\d+\b"
    muster["Hash"] = r"\b[0-9a-f]{12,}\b"

    funde = [
        f"{z.aktion.label}: {name} „{treffer}“ in „{z.beschreibung}“"
        for z in zeilen
        for name, m in muster.items()
        for treffer in re.findall(m, z.beschreibung or "")
    ]
    assert not funde, "interne Kennung im Protokoll:\n" + "\n".join(funde)


@pytest.mark.parametrize("name,cid", [("drehkreuz", "F-OP-1"), ("nordlicht_agb_fehlen", "F-OP-2")])
def test_jeder_offene_punkt_bringt_sein_wort_mit(name, cid, tmp_path, monkeypatch):
    """Sungho am Pixel, 26. Aug: neben der Frage der Beraterin stand „P8d".

    Der Protokoll-Wächter darüber hätte das nie gefunden — dort geht es um
    *Prosa*, hier um ein **Feld**, das die UI roh rendert. Ein Python-Test kann
    nicht sehen, was eine React-Komponente anzeigt; er kann aber sicherstellen,
    dass die Beschriftung überhaupt existiert. Zusammen mit der Regel im Pack
    („`pruefpunkt_id` ist Schlüssel, kein Rückfall auf die ID") ist das die
    Arbeitsteilung: das Modell garantiert das Wort, das Pack verbietet die id.
    """
    from fallpruefer import ansicht, store
    from fallpruefer.konfig import WURZEL
    from fallpruefer.pipeline import fall_aus_verzeichnis

    monkeypatch.setattr(store, "pfad", lambda: tmp_path / "faelle.jsonl")
    fall = fall_aus_verzeichnis(WURZEL / "demo" / "faelle" / name, case_id=cid)
    punkte = ansicht.bauen(fall, schema_laden("preiserhoehung")).offene_punkte
    assert punkte, f"{name} hat keine offenen Punkte — der Test prüft nichts"

    for p in punkte:
        if p.pruefpunkt_id:
            assert p.pruefpunkt_titel, f"{p.pruefpunkt_id} ohne Titel: „{p.text[:50]}“"
        if p.feld_id:
            assert p.feld_label, f"{p.feld_id} ohne Beschriftung: „{p.text[:50]}“"
