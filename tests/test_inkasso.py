"""B3 — Paulinas 14 Prüfpunkte, als Regeln.

Her list (`22` §11, from `data/eingang/paulina_runde2_pruefpunkte_inkasso.pdf`)
with her numbering kept: her 1-14 are P1-P14. The role mapping is `22` §12.
Expectations are derived by hand from that table and from
`schemas/inkasso.json`; nothing here is read back out of the engine.

Inkasso is Stufe B and off the demo path (`14` §2). These tests exist because
a Fallgruppe whose rules nobody executed is a Fallgruppe nobody can trust —
and because the second schema is the scaling claim of the whole pitch
(„eine Schema-Datei, kein Code").
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from fallpruefer.evaluator import Fallkontext
from fallpruefer.konfig import WURZEL
from fallpruefer.fall import Fall, Faktum
from fallpruefer.regeln import auswerten
from fallpruefer.schema import schema_laden
from fallpruefer.vokabular import Rolle, Zustand


@pytest.fixture(scope="module")
def schema():
    return schema_laden("inkasso")


def _p(schema, pid):
    return next(p for p in schema.pruefpunkte if p.id == pid)


def _k(schema, fakten: dict, dokumente: list[str] | None = None, parameter=None):
    from fallpruefer.fall import Dokument
    from fallpruefer.vokabular import Dokumenttyp

    fall = Fall(case_id="F-INK", schema={"fallgruppe_id": "inkasso", "version": "", "stand": ""})
    fall.fakten = [Faktum(feld_id=k, wert=v) for k, v in fakten.items()]
    for i, typ in enumerate(dokumente or [], start=1):
        fall.dokumente.append(Dokument(dok_id=f"D{i}", dokumenttyp=Dokumenttyp(typ)))
    k = Fallkontext(fall=fall, schema=schema)
    if parameter:
        k.parameter_block = parameter
    return k


# --------------------------------------------------------------------------
# the shape Paulina specified
# --------------------------------------------------------------------------


def test_ihre_vierzehn_punkte_sind_vollstaendig_und_in_ihrer_nummerierung(schema):
    assert [p.id for p in schema.pruefpunkte] == [f"P{i}" for i in range(1, 15)]


def test_die_rollen_entsprechen_der_zuordnung_aus_22_paragraf_12(schema):
    """`22` §12: Nr. 1 und Nr. 3 sind Gates, Nr. 14 ist Strategie, alles andere
    tragend. **Kein einziger ergänzender Punkt** — anders als bei
    Preiserhöhung, wo drei von sechzehn ergänzend sind. Folge im AND-Baum:
    jeder der elf tragenden Punkte kann den Fall allein kippen."""
    rollen = {p.id: p.rolle for p in schema.pruefpunkte}
    assert rollen["P1"] == Rolle.GATE and rollen["P3"] == Rolle.GATE
    assert rollen["P14"] == Rolle.STRATEGIE
    tragend = [pid for pid, r in rollen.items() if r == Rolle.TRAGEND]
    assert len(tragend) == 11
    assert not [p for p in schema.pruefpunkte if p.rolle == Rolle.ERGAENZEND]


def test_nur_zwei_punkte_sind_bewertungsfragen(schema):
    """Sie wurde gefragt „Punkt 6 dürfte einer sein — welche noch?" und
    antwortete: keine weitere. Nr. 8 (§ 123) ist ihre einzige. P12
    (Inkassokosten) ist unsere zweite und aus einem anderen Grund: für die
    Höhe fehlt uns die Norm, und eine erfundene Gebührenschwelle wäre
    schlimmer als eine offene Frage."""
    wertungen = [p.id for p in schema.pruefpunkte if getattr(p.typ, "value", p.typ) == "wertung"]
    assert wertungen == ["P8", "P12"]
    assert _p(schema, "P12").anker == [], "P12 darf keinen Anker behaupten, den niemand benannt hat"


def test_jeder_tragende_punkt_haengt_im_baum(schema):
    im_baum = {k for stufe in schema.baum.kinder for k in stufe.kinder}
    assert {p.id for p in schema.pruefpunkte} == im_baum


def test_das_gate_ohne_fernabsatz_deaktiviert_genau_die_vier_widerrufspunkte(schema):
    """`22` §12: ohne Fernabsatz oder Haustürsituation gibt es kein
    Widerrufsrecht — die vier Widerrufspunkte müssen dann INAKTIV werden,
    nicht NEIN. Ein NEIN wäre die Behauptung, das Widerrufsrecht sei geprüft
    und verneint worden."""
    assert _p(schema, "P3").bei_NEIN["deaktiviert"] == ["P4", "P5", "P6", "P7"]


# --------------------------------------------------------------------------
# the rules
# --------------------------------------------------------------------------


def test_P2_schweigen_ist_keine_annahme(schema):
    """Ihre Nr. 2, §§ 145 ff. BGB. Bestreitet die Verbraucherin den
    Vertragsschluss und liegt weder Vertrag noch Auftragsbestätigung vor, ist
    kein Vertrag belegt → NEIN. Liegt eine Vertragsgrundlage vor, entscheidet
    das Programm nicht selbst → WERTUNG."""
    regel = _p(schema, "P2").regel
    ohne = _k(schema, {"gespraech.vertragsschluss_bestritten": True})
    assert auswerten(regel["NEIN_wenn"], ohne) is True

    mit = _k(schema, {"gespraech.vertragsschluss_bestritten": True,
                      "vertrag.datum": date(2026, 1, 5)}, dokumente=["vertrag"])
    assert auswerten(regel["NEIN_wenn"], mit) is False
    assert auswerten(regel["WERTUNG_wenn"], mit) is True


def test_P5_eine_belehrung_ohne_kontaktweg_ist_nicht_ordnungsgemaess(schema):
    """Ihre Nr. 5, §§ 355, 356 BGB: Frist, Fristbeginn und Kontaktweg sind die
    drei Pflichtangaben. Fehlt eine, ist die Belehrung fehlerhaft — und dann
    beginnt die Frist nicht zu laufen."""
    regel = _p(schema, "P5").regel
    vollstaendig = _k(schema, {
        "widerrufsbelehrung.frist_angabe": "14 Tage",
        "widerrufsbelehrung.fristbeginn_angabe": "ab Erhalt der Ware",
        "widerrufsbelehrung.kontaktangaben": "widerruf@example.de",
    }, dokumente=["widerrufsbelehrung"])
    assert auswerten(regel["NEIN_wenn"], vollstaendig) is False

    ohne_kontakt = _k(schema, {
        "widerrufsbelehrung.frist_angabe": "14 Tage",
        "widerrufsbelehrung.fristbeginn_angabe": "ab Erhalt der Ware",
    }, dokumente=["widerrufsbelehrung"])
    assert auswerten(regel["NEIN_wenn"], ohne_kontakt) is True


def test_P6_misst_die_frist_gegen_heute(schema):
    """Ihre Nr. 6. Eine Widerrufsfrist läuft gegen den Kalender, nicht gegen
    ein zweites Dokumentendatum — das ist die erste Regel im Haus, die das
    tut. `heute` geht über `zeit.heute()`, also über denselben Stichtag wie
    jedes andere angezeigte Datum.

    Herleitung: `widerrufsfrist_tage: 14`. Ein Vertrag von vor 3 Tagen liegt
    innerhalb, einer von vor 30 Tagen nicht.
    """
    from fallpruefer.zeit import heute

    p6 = _p(schema, "P6")
    assert p6.parameter["widerrufsfrist_tage"] == 14
    ja = p6.regel["JA_wenn"]

    frisch = _k(schema, {"vertrag.datum": heute() - timedelta(days=3)},
                parameter=p6.parameter)
    assert auswerten(ja, frisch) is True

    alt = _k(schema, {"vertrag.datum": heute() - timedelta(days=30)},
             parameter=p6.parameter)
    assert auswerten(ja, alt) is False, (
        "ohne ein aufloesbares `heute` faellt dieser Arm auf null und der "
        "Punkt rutscht in jedem Fall auf `sonst: NEIN` — ein falsches Urteil, "
        "kein fehlendes"
    )


def test_P7_eine_email_genuegt_fuer_den_widerruf(schema):
    """Ihre Nr. 7: „reicht die E-Mail?" — § 355 Abs. 1 S. 2 BGB verlangt keine
    Schriftform. Ist der Widerruf erklärt, ist der Punkt gerissen: die
    Forderung steht dann auf einem widerrufenen Vertrag."""
    regel = _p(schema, "P7").regel
    k = _k(schema, {"email.enthaelt_widerruf": True}, dokumente=["email"])
    assert auswerten(regel["NEIN_wenn"], k) is True


def test_P11_ohne_abtretung_und_ohne_vollmacht_fehlt_die_berechtigung(schema):
    """Ihre Nr. 11: Das Inkassobüro muss belegen, dass es die Forderung
    einziehen darf — durch Abtretung oder durch Vollmacht. Eines von beidem
    genügt."""
    regel = _p(schema, "P11").regel
    nichts = _k(schema, {"inkassoschreiben.abtretung_erwaehnt": True})
    assert auswerten(regel["NEIN_wenn"], nichts) is True

    mit_vollmacht = _k(schema, {}, dokumente=["vollmacht"])
    assert auswerten(regel["NEIN_wenn"], mit_vollmacht) is False


def test_P13_ohne_registerangabe_ist_der_punkt_gerissen(schema):
    """Ihre Nr. 13, § 10 RDG. Sie hat ihn ausdrücklich als tragend markiert —
    im AND-Baum kann also allein die fehlende Registerangabe den Fall
    kippen. Dazu steht eine Rückfrage offen (`22` §13 Frage 2)."""
    regel = _p(schema, "P13").regel
    ohne = _k(schema, {"inkassoschreiben.absender": "Muster Inkasso GmbH"})
    assert auswerten(regel["NEIN_wenn"], ohne) is True
    mit = _k(schema, {"inkassoschreiben.absender": "Muster Inkasso GmbH",
                      "inkassoschreiben.registereintrag_angabe": "AG Berlin, Reg-Nr. 1234"})
    assert auswerten(regel["NEIN_wenn"], mit) is False


# --------------------------------------------------------------------------
# end to end
# --------------------------------------------------------------------------


def test_ohne_inkassoschreiben_stoppt_das_gate_das_schema(schema):
    """P1 ist ein Gate: ohne das Schreiben gibt es keinen Ausgangspunkt, und
    das Programm sagt das, statt ein Urteil zu erfinden."""
    from fallpruefer.evaluator import pruefen

    fall = Fall(case_id="F-INK-LEER",
                schema={"fallgruppe_id": "inkasso", "version": "", "stand": ""})
    pruefung = pruefen(fall, schema)
    assert pruefung.einordnung_code is None
    assert "Inkassoschreiben" in (pruefung.schema_stopp_text or "")
    erg = {e.pruefpunkt_id: e.zustand for e in pruefung.ergebnisse}
    assert erg["P1"] == Zustand.NEIN


def test_jeder_zweig_hat_einen_garantierten_rechtsbehelf(schema):
    """`15` §3: Verdikt ohne Schreiben hilft niemandem — auch nicht bei
    `wirksam`. Bei Inkasso ist das Bestreiten mit Nachweisverlangen der
    Rückfallweg in jedem Zweig."""
    garantie = schema.rechtsbehelfe.garantie_pro_zweig
    assert set(garantie) == {"wahrscheinlich unwirksam", "unklar – es fehlt …", "wirksam"}
    ids = {r.id for r in schema.rechtsbehelfe.liste}
    for zweig, vorgesehen in garantie.items():
        assert vorgesehen, zweig
        assert set(vorgesehen) <= ids, f"{zweig} nennt einen Rechtsbehelf, den es nicht gibt"


def test_alle_anker_und_alle_rechtsbehelfe_sind_ungeprueft(schema):
    """Kein Anker und kein Musterbrief dieser Fallgruppe ist von einer
    Juristin abgenommen. Ein Test hält das fest, damit nichts still auf eine
    Folie wandert."""
    for p in schema.pruefpunkte:
        for a in p.anker:
            assert a.get("geprueft") is False, f"{p.id}: {a['key']}"
    for r in schema.rechtsbehelfe.liste:
        assert r.geprueft is False, r.id


def test_ein_gate_das_pruefpunkte_abschaltet_muss_sagen_warum(schema, tmp_path):
    """`evaluator.pruefen` kopiert `bei_NEIN.text` in den `inaktiv_grund` jedes
    abgeschalteten Prüfpunkts, und das ist der einzige Satz, den der Bildschirm
    für sie hat. Bleibt er leer, fallen bei Inkasso vier Punkte kommentarlos
    aus der Spur und die Fallakte sieht aus, als hätte das Programm etwas
    vergessen — dabei hat es entschieden, dass sie nicht anwendbar sind.

    Das ist eine rechtliche Aussage, sie gehört in die Datei, die die Juristin
    bearbeitet, nicht in einen Fallback im Motor. Also weist der Loader eine
    Datei ohne diesen Satz ab.
    """
    import json

    from fallpruefer.schema import SchemaFehler, schema_laden as laden

    p3 = _p(schema, "P3")
    assert p3.bei_NEIN["text"].strip(), "P3 schaltet vier Punkte ab und muss das begründen"

    roh = json.loads((WURZEL / "schemas" / "inkasso.json").read_text(encoding="utf-8"))
    next(x for x in roh["pruefpunkte"] if x["id"] == "P3")["bei_NEIN"].pop("text")
    (tmp_path / "inkasso.json").write_text(json.dumps(roh, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SchemaFehler, match="ohne in .bei_NEIN.text. zu sagen warum"):
        laden("inkasso", verzeichnis=tmp_path)


def test_ein_gate_kann_keinen_pruefpunkt_abschalten_den_es_nicht_gibt(tmp_path):
    import json

    from fallpruefer.schema import SchemaFehler, schema_laden as laden

    roh = json.loads((WURZEL / "schemas" / "inkasso.json").read_text(encoding="utf-8"))
    next(x for x in roh["pruefpunkte"] if x["id"] == "P3")["bei_NEIN"]["deaktiviert"] = ["P4", "P99"]
    (tmp_path / "inkasso.json").write_text(json.dumps(roh, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SchemaFehler, match="P99"):
        laden("inkasso", verzeichnis=tmp_path)


def test_die_vier_widerrufspunkte_werden_wirklich_inaktiv_und_nennen_den_grund(schema):
    """Die sichtbarste Wirkung, die eine einzelne Leitfaden-Antwort im ganzen
    Programm hat: „im Ladengeschäft" schaltet vier Prüfpunkte ab.

    Herleitung aus 22 §12: ohne Fernabsatz oder Haustürsituation gibt es kein
    Widerrufsrecht — die vier Punkte müssen INAKTIV werden, **nicht NEIN**. Ein
    NEIN wäre die Behauptung, das Widerrufsrecht sei geprüft und verneint
    worden.
    """
    from fallpruefer.evaluator import pruefen
    from fallpruefer.fall import Dokument
    from fallpruefer.vokabular import Dokumenttyp

    def lauf(situation):
        fall = Fall(case_id="F-INK-GATE",
                    schema={"fallgruppe_id": "inkasso", "version": "", "stand": ""})
        fall.dokumente = [Dokument(dok_id="D1", dokumenttyp=Dokumenttyp("inkassoschreiben"))]
        fall.fakten = [Faktum(feld_id="gespraech.abschlusssituation", wert=situation),
                       Faktum(feld_id="inkassoschreiben.absender", wert="Muster Inkasso GmbH")]
        return {e.pruefpunkt_id: e for e in pruefen(fall, schema).ergebnisse}

    laden = lauf("geschaeftsraum")
    assert laden["P3"].zustand == Zustand.NEIN
    for pid in ("P4", "P5", "P6", "P7"):
        assert laden[pid].zustand == Zustand.INAKTIV, pid
        assert "Geschäftsräumen" in (laden[pid].inaktiv_grund or ""), (
            f"{pid} verschwindet ohne Begründung aus der Spur"
        )

    fern = lauf("fernabsatz")
    assert fern["P3"].zustand == Zustand.JA
    assert all(fern[pid].zustand != Zustand.INAKTIV for pid in ("P4", "P7"))


def test_kein_satz_fuer_den_bildschirm_nennt_eine_pruefpunkt_nummer(tmp_path):
    """„P5" ist unsere Buchhaltung. Eine Beraterin, die „die Belehrung ist
    fehlerhaft (P5)" liest, erfährt nichts, was sie nicht ohnehin sieht; in
    einem Brief an die Verbraucherin erführe sie weniger als nichts.

    Der Evaluator hält diese Regel längst — ein Test hält fest, dass er keinen
    Prüfpunkt benennt. Ausgerechnet die Schemasätze standen außerhalb davon,
    und genau dort werden die Nummern getippt. Meine erste Fassung von
    P6.wertungsfrage hatte eine.
    """
    import json

    from fallpruefer.schema import SchemaFehler, schema_laden as laden

    roh = json.loads((WURZEL / "schemas" / "inkasso.json").read_text(encoding="utf-8"))
    next(x for x in roh["pruefpunkte"] if x["id"] == "P6")["wertungsfrage"] = (
        "Die Belehrung ist fehlerhaft (P5) — wie lange läuft die Frist?")
    (tmp_path / "inkasso.json").write_text(json.dumps(roh, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SchemaFehler, match="benennt die Sache, nicht die Nummer"):
        laden("inkasso", verzeichnis=tmp_path)
