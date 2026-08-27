"""Mutation tests for the area „Einordnung und Vollständigkeit" (`evaluator.py`).

Six mutations of `_einordnung`, `_gate_luecke`, `_lesbare_luecken`,
`_vollstaendigkeit` and the gate loop of `pruefen()` survived the 117 tests the
build had. Each test below fails on exactly one of them.

Every case is **built by hand**: documents and Fakten are constructed here, and
the state of every Prüfpunkt is derived from `schemas/preiserhoehung.json` and
the rule grammar of `analysis/15_data_contract.md` §1 (fixed branch order
`FEHLT_wenn → NEIN_wenn → WERTUNG_wenn → JA_wenn → sonst`; three-valued, a
branch fires only on `true`; **implicit FEHLT** when no branch fired and a
`pflicht: true` Eingabe is absent). The derivation is written into each test.
Nothing here was read off a run.

The shared starting point is `_BASIS` — a case in which every tragend
Prüfpunkt is JA (derivation in the comment on `_BASIS`). Each test states the
one deviation it needs.
"""

from __future__ import annotations

import copy

import pytest

from fallpruefer import evaluator
from fallpruefer.fall import Dokument, Faktum, Fall, SchemaRef, SeiteText
from fallpruefer.schema import schema_laden
from fallpruefer.vokabular import Dokumenttyp, Einordnung, Quelle, Rolle, Zustand

WEG = object()  # marks a fact that this case does not have

# The document texts are never read by a rule of this schema: the only
# primitive that would look at them is `kreuzpruefung_klauselverweis`, and it
# returns None while `erhoehungsschreiben.klauselverweis` is unset — which it
# is in every case here, the field being `pflicht: false` in the Soll.
_DOKUMENTE = (
    ("D1", Dokumenttyp.ERHOEHUNGSSCHREIBEN, "Anpassung des Monatsbeitrags."),
    ("D2", Dokumenttyp.AGB, "Allgemeine Geschaeftsbedingungen."),
    ("D3", Dokumenttyp.VERTRAG, "Mitgliedsvertrag."),
)

_DOK_ID = {"erhoehungsschreiben": "D1", "agb": "D2", "vertrag": "D3"}

# --------------------------------------------------------------------------
# `_BASIS` — every tragend Prüfpunkt JA, derived from schemas/preiserhoehung.json
#
#   P1  NEIN_wenn grundlage_genannt == "keine" → "klausel", false → sonst JA
#   P2  FEHLT_wenn kreuzpruefung == false → prim is None (no klauselverweis),
#       null → no fire. NEIN_wenn alle[fassung_datum > vertrag.datum →
#       2024-01-10 > 2024-02-01 = false, …] → false. WERTUNG_wenn
#       eine[fehlt agb_einbezogen_hinweis → false (it is set), fassung_datum >
#       vertrag.datum → false] → false. Pflicht-Eingaben (preisklausel_text,
#       vertrag.datum) present → sonst JA
#   P3  NEIN_wenn alle[preisgarantie_monate > 0 → null (absent), monate_zwischen
#       < preisgarantie_monate → null] → null → no fire; Pflicht-Eingaben
#       (vertrag.datum, wirksam_ab) present → sonst JA
#   P4  JA_wenn alle[verifiziert klausel_ueberschrift → true, klausel_ueberschrift
#       in [Preise, Beiträge, …] → "Beiträge", true] → JA
#   P6  NEIN_wenn alle[eine[anlass/voraussetzungen/umfang == false] → false, …]
#       → false. JA_wenn all three true and verified → JA
#   P7  NEIN_wenn senkungspflicht in [ermessen, keine] → "pflicht", false.
#       JA_wenn alle[senkungspflicht == "pflicht", kostenbezug == true, both
#       verified] → JA
#   P8  NEIN_wenn alle[zustimmungsmechanismus == "schweigen" → "unterschrift",
#       false, …] → false. WERTUNG_wenn eine[laufzeit_monate > 24 → 12 > 24
#       false, vorhanden verlaengerung_text → false] → false → sonst JA
#   P9  NEIN_wenn zustimmungsmechanismus in [schweigen, weiternutzung] →
#       "unterschrift", false → sonst JA
#   P10 NEIN_wenn alle[kuendigungsrecht_bei_erhoehung == true → true,
#       kuendigungshinweis == false → true == false, false] → false.
#       WERTUNG_wenn eine[tage_zwischen(zugang 2026-01-08, wirksam_ab
#       2026-04-01) = 83 < frist_min_tage 30 → false, form in [aushang,
#       website] → "brief", false] → false → sonst JA
#
# Both gates are JA: P0 NEIN_wenn alle[grundlage_genannt == "zustimmung_aktiv"
# → false, …] → false, WERTUNG_wenn == "neue_entgeltposition" → false → sonst
# JA; P5 NEIN_wenn gespraech.klausel_ist_urspruenglicher_preis == true → null
# → no fire, Pflicht-Eingabe preisklausel_text present → sonst JA.
#
# Tree (schema `baum`, AND everywhere, INAKTIV children ignored — 15 §2
# `aggregation.AND`): S0 = {P0} gate only → INAKTIV · S1 = {P1} JA · S2 =
# {P2,P3,P4} JA · S3 = {P5 gate, P6..P9} JA · S4 = {P10} JA · S5 = {P11}
# ergaenzend only → INAKTIV · S6 = {P8b,P14} ergaenzend only → INAKTIV.
# root = AND(JA, JA, JA, JA) = JA → „wirksam" (15 §2 `aggregation.einordnung`).
#
# The two ergaenzend Prüfpunkte are unaffected by aggregation (`nur_rolle`:
# ["tragend"]) but P11 matters for Vollständigkeit: WERTUNG_wenn
# dok_vorhanden kostenkalkulation → false → `sonst: FEHLT`, `fehlt_owner`
# unternehmen. The Soll lists the same document (`pflicht: hinweis`, never
# supplied) — that pair is the subject of `test_dieselbe_luecke_…`.
# --------------------------------------------------------------------------
_BASIS: dict[str, object] = {
    # Erhöhungsschreiben — all `pflicht: true` fields of the Soll
    "erhoehungsschreiben.datum": "2026-01-05",
    "erhoehungsschreiben.zugang": "2026-01-08",
    "erhoehungsschreiben.form": "brief",
    "erhoehungsschreiben.wirksam_ab": "2026-04-01",
    "erhoehungsschreiben.neuer_betrag": 49.90,
    "erhoehungsschreiben.grundlage_genannt": "klausel",
    "erhoehungsschreiben.zustimmungsmechanismus": "unterschrift",
    "erhoehungsschreiben.kuendigungshinweis": True,
    "erhoehungsschreiben.absender": "AktivPark Fitness GmbH",
    # AGB — all `pflicht: true` fields, plus the two the rules read
    "agb.fassung_datum": "2024-01-10",
    "agb.preisklausel_text": "Der Beitrag kann an gestiegene Energie- und Personalkosten angepasst werden; sinken diese, ist der Beitrag zu senken.",
    "agb.klausel_ueberschrift": "Beiträge",
    "agb.nennt_anlass": True,
    "agb.nennt_voraussetzungen": True,
    "agb.nennt_umfang": True,
    "agb.kostenbezug": True,
    "agb.senkungspflicht": "pflicht",
    "agb.kuendigungsrecht_bei_erhoehung": True,
    # Vertrag — both `pflicht: true` fields, plus what P2 and P8 read
    "vertrag.datum": "2024-02-01",
    "vertrag.beitrag": 39.90,
    "vertrag.laufzeit_monate": 12,
    "vertrag.agb_einbezogen_hinweis": True,
}


def _fall(case_id: str, abweichungen: dict[str, object] | None = None) -> Fall:
    werte = dict(_BASIS)
    werte.update(abweichungen or {})
    return Fall(
        case_id=case_id,
        schema=SchemaRef(fallgruppe_id="preiserhoehung"),
        dokumente=[
            Dokument(dok_id=did, dokumenttyp=typ,
                     seiten=[SeiteText(nr=1, text_original=text, text_pseudonym=text)])
            for did, typ, text in _DOKUMENTE
        ],
        fakten=[
            Faktum(feld_id=fid, wert=wert, dok_id=_DOK_ID.get(fid.split(".", 1)[0]))
            for fid, wert in werte.items() if wert is not WEG
        ],
    )


@pytest.fixture(scope="module")
def schema():
    return schema_laden("preiserhoehung")


def _pruefung(fall: Fall, s):
    return evaluator.pruefen(fall, s, trigger="mutationstest")


def _zustaende(pruefung, s) -> dict[str, Zustand]:
    return {e.pruefpunkt_id: e.zustand for e in pruefung.ergebnisse}


def _tragende(s) -> list[str]:
    return [p.id for p in s.pruefpunkte if p.rolle in s.nur_rolle]


# --------------------------------------------------------------------------
# 1) the INAKTIV floor of the Einordnung
# --------------------------------------------------------------------------


def test_ohne_aktiven_tragenden_pruefpunkt_bleibt_die_einordnung_unklar(schema):
    """Root aggregates to INAKTIV → „unklar – es fehlt: eine anwendbare Prüfung".

    15 §2 `aggregation.einordnung` defines a verdict only for root ==
    NEIN / FEHLT / WERTUNG / JA; „wirksam" is bound to *root == JA (alle
    aktiven tragenden Prüfpunkte JA)*. Root == INAKTIV means no tragend
    Prüfpunkt was evaluated at all, so none of the three verdicts is earned.
    `18` #9 fixes the floor for that state verbatim: „`unklar – es fehlt: eine
    anwendbare Prüfung`. Cannot occur with the current schema; it is a floor,
    not a feature."

    The state is reachable exactly the way 15 §2 `gates` describes — „gate NEIN
    mit deaktiviert → die genannten Prüfpunkte erhalten zustand INAKTIV" — once
    a Jurist-Edit widens `P5.bei_NEIN.deaktiviert` (the file is the UI, 15 §1)
    from {P6,P7,P8,P9} to every tragend Prüfpunkt. The edit is done on a copy
    of the loaded schema, so no file is touched.

    Derivation: `gespraech.klausel_ist_urspruenglicher_preis = true` fires
    P5's NEIN_wenn → gate NEIN with `deaktiviert` (no `schema_stopp`, so the
    Einordnung *is* computed). Every tragend Prüfpunkt → INAKTIV; INAKTIV
    children are ignored, a node without active children is INAKTIV → S1..S4
    INAKTIV, S0/S5/S6 INAKTIV as always → root INAKTIV.
    """
    s = copy.deepcopy(schema)
    s.pruefpunkt("P5").bei_NEIN["deaktiviert"] = _tragende(s)

    p = _pruefung(_fall("F-MUT-EIN-1", {"gespraech.klausel_ist_urspruenglicher_preis": True}), s)
    z = _zustaende(p, s)

    # preconditions of the derivation, so a failure says which half broke
    assert z["P5"] == Zustand.NEIN, "das Gate muss NEIN sein, sonst greift `deaktiviert` nicht"
    assert [z[pid] for pid in _tragende(s)] == [Zustand.INAKTIV] * len(_tragende(s))
    assert p.baum_zustaende["root"] == Zustand.INAKTIV

    assert p.einordnung == "unklar – es fehlt: eine anwendbare Prüfung"
    assert p.einordnung_code is Einordnung.UNKLAR, (
        "kein tragender Prüfpunkt wurde geprüft — „wirksam“ wäre die falsche sichere Antwort"
    )


# --------------------------------------------------------------------------
# 2) a gate in WERTUNG is an open Vorfrage
# --------------------------------------------------------------------------


def test_ein_gate_in_WERTUNG_ist_eine_offene_vorfrage(schema):
    """A gate left on WERTUNG must not let a hard verdict through.

    15 §0 lists WERTUNG as a `zustand` of its own next to FEHLT, and 15 §1
    lets a branch fire only on `true` — „we don't know" never collapses into
    „not a problem". For the Prüfpunkte that carry the Einordnung 15 §2 spells
    that out (root == WERTUNG → unklar); a *gate* asks the prior question of
    whether the schema applies at all, so an unanswered one cannot leave a
    „wirksam"/„wahrscheinlich unwirksam" standing either.

    Derivation: `erhoehungsschreiben.grundlage_genannt = "neue_entgeltposition"`
    is P0's `WERTUNG_wenn` (schema, verbatim) → gate P0 WERTUNG. P1 is the only
    other Prüfpunkt reading that field and its NEIN_wenn tests `== "keine"` →
    false → sonst JA, so the tree is the `_BASIS` tree: root == JA. With the
    Vorfrage open, the verdict must be `unklar`, not „wirksam".
    """
    fall = _fall("F-MUT-EIN-2",
                 {"erhoehungsschreiben.grundlage_genannt": "neue_entgeltposition"})
    p = _pruefung(fall, schema)
    z = _zustaende(p, schema)

    assert z["P0"] == Zustand.WERTUNG
    assert z["P5"] == Zustand.JA
    assert [z[pid] for pid in _tragende(schema)] == [Zustand.JA] * len(_tragende(schema))
    assert p.baum_zustaende["root"] == Zustand.JA

    assert p.einordnung_code is Einordnung.UNKLAR, (
        "die Vorfrage „ist das überhaupt eine Preiserhöhung?“ ist offen"
    )
    assert p.einordnung.startswith("unklar – es fehlt:")


# --------------------------------------------------------------------------
# 3) one missing field is named, two are generalised
# --------------------------------------------------------------------------


def test_eine_einzelne_feldluecke_wird_beim_namen_genannt(schema):
    """`18` #29: document absent → `anzeigename`; document present with
    **several** required fields unfound → `anzeigename — liegen vor, aber unvollständig`; **a
    single** missing field → the field itself, „so the precise case (‚die Seite
    mit Ziffer 5.2') does not get blurred into the general one". 14 §5 asks for
    the named inputs. Both sides of the boundary are asserted here, because the
    boundary is what the wording rests on.

    Derivation, one gap: `agb.kostenbezug` removed. P7's JA_wenn needs
    `kostenbezug == true` → null → no fire; NEIN_wenn tests senkungspflicht in
    [ermessen, keine] → false; no branch fired and `agb.kostenbezug` is a
    `pflicht: true` Eingabe of P7 → implicit FEHLT (15 §1) with
    missing = [agb.kostenbezug], owner = the Soll's `quelle` for agb =
    verbraucher. S3 = AND(P6 JA, P7 FEHLT, P8 JA, P9 JA) = FEHLT → root FEHLT.
    The Soll reports the same gap (agb present, `pflicht: true` field unfound).
    The verdict for root == FEHLT lists the gaps of the tragenden
    FEHLT-Prüfpunkte (15 §2); the AGB group holds exactly one entry, and that
    entry has a `feld_id` → it is named by its own `beschreibung` from the
    Soll: „knüpft die Erhöhung an Kostenentwicklung?".

    Derivation, two gaps: additionally `agb.nennt_umfang` removed → P6's
    NEIN_wenn eine[…, nennt_umfang == false] → null → no fire, JA_wenn → null →
    no fire, `pflicht: true` Eingabe absent → FEHLT. Now the AGB group holds
    two entries → „die AGB, die bei Vertragsschluss galten — liegen vor, aber unvollständig".
    """
    feld = schema.dokumenten_soll.feld("agb.kostenbezug")
    dok = schema.dokumenten_soll.nach_typ(Dokumenttyp.AGB)

    eine = _pruefung(_fall("F-MUT-EIN-3a", {"agb.kostenbezug": WEG}), schema)
    assert _zustaende(eine, schema)["P7"] == Zustand.FEHLT
    assert eine.baum_zustaende["root"] == Zustand.FEHLT
    assert eine.einordnung == "unklar – es fehlt: " + feld.beschreibung
    assert "unvollständig" not in eine.einordnung, (
        "eine einzelne Feldlücke darf nicht zur unvollständigen Unterlage verallgemeinert werden"
    )

    zwei = _pruefung(
        _fall("F-MUT-EIN-3b", {"agb.kostenbezug": WEG, "agb.nennt_umfang": WEG}), schema)
    assert _zustaende(zwei, schema)["P6"] == Zustand.FEHLT
    assert zwei.einordnung == f"unklar – es fehlt: {dok.anzeigename} — liegen vor, aber unvollständig"  # V-29


# --------------------------------------------------------------------------
# 4) the same gap stands once in Vollständigkeit
# --------------------------------------------------------------------------


def test_dieselbe_luecke_steht_nur_einmal_in_der_vollstaendigkeit(schema):
    """`18` #12: „`<typ>.vorhanden` als fehlender Posten wird gegen den
    Dokument-Eintrag dedupliziert — sonst erschien kostenkalkulation zweimal
    (once from the Soll `pflicht: hinweis`, once from P11 FEHLT). Was a real
    bug." 15 §2 `vollstaendigkeit` is the list of what is missing, grouped by
    `quelle`; a document that is missing once is one entry, and Screen 1, the
    Gate-1 letter and the store record all count it.

    Derivation, company side: the Soll's `kostenkalkulation` is `pflicht:
    hinweis`, `quelle: unternehmen`, never supplied → one entry with no
    `feld_id` (it is the document). P11 (`sonst: FEHLT`, `fehlt_owner:
    unternehmen`) has the single Eingabe `kostenkalkulation.vorhanden`, which
    names that same document, not a field inside it → the same key.

    Derivation, consumer side (the `agb.kostenbezug` case of the test above):
    the Soll reports the unfound `pflicht: true` field, and P7 reports the same
    `feld_id` in `missing` with owner verbraucher → again the same key.
    """
    p = _pruefung(_fall("F-MUT-EIN-4a"), schema)
    schluessel = [(e.dokumenttyp, e.feld_id, e.quelle) for e in p.vollstaendigkeit["unternehmen"]]
    assert schluessel == [(Dokumenttyp.KOSTENKALKULATION, None, Quelle.UNTERNEHMEN)]
    assert p.vollstaendigkeit["verbraucher"] == []

    q = _pruefung(_fall("F-MUT-EIN-4b", {"agb.kostenbezug": WEG}), schema)
    assert [(e.dokumenttyp, e.feld_id, e.quelle) for e in q.vollstaendigkeit["verbraucher"]] == [
        (Dokumenttyp.AGB, "agb.kostenbezug", Quelle.VERBRAUCHER)
    ]


# --------------------------------------------------------------------------
# 5) the WERTUNG verdict names the question
# --------------------------------------------------------------------------


def test_das_wertungs_verdikt_nennt_die_wertungsfrage(schema):
    """15 §2: „root == WERTUNG → es fehlt: Bewertung durch die Beraterin zu
    <wertungsfrage>", and the binding vocabulary of 15 §0 renders it with the
    question spelled out: „unklar – es fehlt: Bewertung durch die Beraterin zu
    ‚Ist die Klausel überraschend?'". Without the question the Beraterin is
    told that a judgement is missing but not which one — and that sentence is
    the hand-over to Gate 3.

    Derivation: `agb.klausel_ueberschrift = "Sonstige Bestimmungen"`. P4's only
    branch is JA_wenn alle[verifiziert klausel_ueberschrift → true,
    klausel_ueberschrift in [Preise, Beiträge, Preisanpassung,
    Beitragsanpassung, Entgelt] → false] → false → no fire; P4's only
    `pflicht: true` Eingabe (agb.preisklausel_text) is present, so no implicit
    FEHLT → `sonst: WERTUNG`. S2 = AND(P2 JA, P3 JA, P4 WERTUNG) = WERTUNG →
    root = AND(JA, WERTUNG, JA, JA) = WERTUNG. P4 is the only tragend WERTUNG,
    so its `wertungsfrage` from the schema is the one the verdict must carry.
    """
    p = _pruefung(_fall("F-MUT-EIN-5",
                        {"agb.klausel_ueberschrift": "Sonstige Bestimmungen"}), schema)
    z = _zustaende(p, schema)
    assert z["P4"] == Zustand.WERTUNG
    assert [pid for pid in _tragende(schema) if z[pid] == Zustand.WERTUNG] == ["P4"]
    assert p.baum_zustaende["root"] == Zustand.WERTUNG

    frage = schema.pruefpunkt("P4").wertungsfrage
    assert p.einordnung.startswith("unklar – es fehlt: Bewertung durch die Beraterin zu ")
    assert frage in p.einordnung, "das Verdikt nennt die Wertungsfrage nicht"


# --------------------------------------------------------------------------
# 6) the gap of an open gate is its Wertungsfrage
# --------------------------------------------------------------------------


def test_die_luecke_eines_offenen_gates_nennt_seine_wertungsfrage(schema):
    """Same rule as above (15 §2: „es fehlt: Bewertung durch die Beraterin zu
    <wertungsfrage>"), applied to the Vorfrage. A gate on WERTUNG has nothing
    in `missing` — it is not waiting for a document but for a judgement — so
    naming it by its missing inputs leaves the entry empty and the verdict
    falls back to the nameless „unklar – es fehlt: eine Vorfrage", which asks
    the Beraterin for nothing she can act on.

    Derivation: as in `test_ein_gate_in_WERTUNG_…` — `grundlage_genannt =
    "neue_entgeltposition"` fires P0's `WERTUNG_wenn`. A branch that fires
    leaves no missing inputs (15 §1: implicit FEHLT is what collects those, and
    it only runs when *no* branch fired), so the only thing left to name is
    P0's `wertungsfrage` from the schema.
    """
    fall = _fall("F-MUT-EIN-6",
                 {"erhoehungsschreiben.grundlage_genannt": "neue_entgeltposition"})
    p = _pruefung(fall, schema)

    erg = p.ergebnis("P0")
    assert erg.zustand == Zustand.WERTUNG and erg.missing == [], (
        "eine gefeuerte Regel hinterlässt keine fehlenden Eingaben"
    )

    frage = schema.pruefpunkt("P0").wertungsfrage
    assert p.einordnung.startswith("unklar – es fehlt: Bewertung durch die Beraterin zu ")
    assert frage in p.einordnung
    assert p.einordnung != "unklar – es fehlt: eine Vorfrage", (
        "der namenlose Rückfall verschweigt genau die Frage, die den Fall entscheidet"
    )


# --------------------------------------------------------------------------
# the schema this file derives from must keep the shape the derivations assume
# --------------------------------------------------------------------------


def test_die_ableitungsgrundlage_dieser_datei_stimmt_noch(schema):
    """Every derivation above reads the schema file. If that file moves, the
    tests must say so instead of quietly asserting something else."""
    assert schema.nur_rolle == {Rolle.TRAGEND}
    assert _tragende(schema) == ["P1a", "P1", "P2", "P3", "P4", "P6", "P7", "P8", "P8c", "P9", "P10"]  # P1a: Fall 6, V-G1 (25 Aug)
    assert [p.id for p in schema.pruefpunkte if p.rolle is Rolle.GATE] == ["P0", "P5"]
    assert schema.pruefpunkt("P0").regel["WERTUNG_wenn"] == {
        "feld": "erhoehungsschreiben.grundlage_genannt", "op": "==",
        "wert": "neue_entgeltposition",
    }
    assert schema.pruefpunkt("P5").bei_NEIN["deaktiviert"] == ["P6", "P7", "P8", "P9"]
    assert schema.pruefpunkt("P11").fehlt_owner is Quelle.UNTERNEHMEN
    assert schema.dokumenten_soll.nach_typ(Dokumenttyp.KOSTENKALKULATION).pflicht.value == "hinweis"
    assert schema.dokumenten_soll.feld("agb.kostenbezug").pflicht is True
