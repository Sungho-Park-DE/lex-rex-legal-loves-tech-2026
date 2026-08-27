"""Zustandsreihenfolge und Prüfpunkt-Auswertung — the order, asserted.

Contract 15 §1 states the one rule this file is about:

    "Evaluation order is fixed: FEHLT_wenn → NEIN_wenn → WERTUNG_wenn →
     JA_wenn → sonst; the first condition that is **true** fires."

The four demo cases never make two branches of one Prüfpunkt true at the same
time, so the whole sentence is unobservable through them: a reversed order, a
dropped `break`, even a deleted FEHLT arm all reproduce the same four verdicts.
The order only becomes visible where the branches overlap — and in
`schemas/preiserhoehung.json` P2 they overlap by construction, because its
`NEIN_wenn` is a strict subset of its `WERTUNG_wenn` (both contain
`agb.fassung_datum > vertrag.datum`).

So this file works on two levels:

  * synthetic Prüfpunkte, whose branches are grammar conditions (§1: `{"fehlt":
    F}` / `{"vorhanden": F}`) whose truth value is fixed by the facts, pinning
    each adjacent pair of the order and „first, not last";
  * the real P2 out of `schemas/preiserhoehung.json`, on a hand-built case, so
    the pairs are pinned where they decide a verdict.

Every expectation below is derived from the contract text and the schema JSON
and the derivation is written next to it. Nothing here was read off a run.
"""

from __future__ import annotations

from datetime import date

from fallpruefer.evaluator import Fallkontext, pruefpunkt_auswerten
from fallpruefer.fall import Dokument, Fall, Faktum, SeiteText
from fallpruefer.regeln import auswerten as bedingung_auswerten
from fallpruefer.schema import Pruefpunkt, schema_laden
from fallpruefer.vokabular import Badge, Dokumenttyp, Herkunft, Zustand

# --------------------------------------------------------------------------
# scaffolding
# --------------------------------------------------------------------------

# The one fact every synthetic Prüfpunkt below is anchored on. Its only job is
# to make two conditions of the §1 grammar decidable and opposite:
#   {"vorhanden": "vertrag.datum"} is true  — the fact is set
#   {"fehlt":     "vertrag.datum"} is false — the fact is set
BASISFAKTEN = {"vertrag.datum": date(2025, 3, 1)}

WAHR: dict = {"vorhanden": "vertrag.datum"}
FALSCH: dict = {"fehlt": "vertrag.datum"}


def _dokument(dok_id: str, typ: Dokumenttyp, text: str) -> Dokument:
    return Dokument(
        dok_id=dok_id, dokumenttyp=typ,
        seiten=[SeiteText(nr=1, text_original=text, text_pseudonym=text)],
    )


def _kontext(fakten: dict | None = None, dokumente: list[Dokument] | None = None):
    """A case object carrying exactly the facts and documents a test names."""
    schema = schema_laden("preiserhoehung")
    fall = Fall(case_id="F-MUT-REIHENFOLGE", schema={"fallgruppe_id": "preiserhoehung"})
    fall.dokumente.extend(dokumente or [])
    for feld_id, wert in (fakten or {}).items():
        fall.fakten.append(Faktum(
            feld_id=feld_id, wert=wert, dok_id="D1",
            herkunft=Herkunft.EXPLIZIT, verifiziert=True, badge=Badge.VERIFIZIERT,
        ))
    return Fallkontext(fall=fall, schema=schema), schema


def _synthetisch(regel: dict) -> Pruefpunkt:
    """A Prüfpunkt that exists only to make the order observable.

    Its single `pflicht` input is satisfied by BASISFAKTEN, so the implicit
    FEHLT of §1 („if no branch fired and any `eingaben` with `pflicht:true` is
    absent or unverified") can never fire and mask which branch did.
    """
    return Pruefpunkt.model_validate({
        "id": "PX", "rolle": "tragend", "typ": "fakt",
        "proposition": "Synthetischer Prüfpunkt für die Auswertungsreihenfolge.",
        "eingaben": [{"feld": "vertrag.datum", "pflicht": True}],
        "regel": regel,
    })


def _zustand(regel: dict) -> Zustand:
    k, schema = _kontext(BASISFAKTEN)
    return pruefpunkt_auswerten(_synthetisch(regel), k, schema).zustand


# --------------------------------------------------------------------------
# (i) the order itself, branch pair by branch pair
# --------------------------------------------------------------------------


def test_alle_vier_zweige_wahr_liefern_FEHLT():
    """§1: order FEHLT_wenn → NEIN_wenn → WERTUNG_wenn → JA_wenn, first true
    fires. With all four true the first one — FEHLT_wenn — is the answer, and
    no other state is reachable."""
    assert _zustand({
        "FEHLT_wenn": WAHR, "NEIN_wenn": WAHR,
        "WERTUNG_wenn": WAHR, "JA_wenn": WAHR, "sonst": "JA",
    }) == Zustand.FEHLT


def test_FEHLT_wenn_geht_vor_NEIN_wenn():
    """§1 names FEHLT_wenn before NEIN_wenn. Where both hold, the honest answer
    is „es fehlt …", not a hard „nicht erfüllt" over a document nobody has."""
    assert _zustand({"FEHLT_wenn": WAHR, "NEIN_wenn": WAHR, "sonst": "JA"}) == Zustand.FEHLT


def test_NEIN_wenn_geht_vor_WERTUNG_wenn():
    """§1 names NEIN_wenn before WERTUNG_wenn: a point the rule can decide is
    decided, not handed to the Beraterin as a Bewertungsfrage."""
    assert _zustand({"NEIN_wenn": WAHR, "WERTUNG_wenn": WAHR, "sonst": "JA"}) == Zustand.NEIN


def test_WERTUNG_wenn_geht_vor_JA_wenn():
    """§1 names WERTUNG_wenn before JA_wenn. Both true means the Prüfpunkt is a
    Bewertungsfrage; upgrading it to „erfüllt" would answer a question the
    schema declared open."""
    assert _zustand({"WERTUNG_wenn": WAHR, "JA_wenn": WAHR, "sonst": "JA"}) == Zustand.WERTUNG


def test_FEHLT_wenn_wird_ueberhaupt_ausgewertet():
    """FEHLT_wenn is part of the §1 rule grammar and has to be dispatched on.

    Only FEHLT_wenn is true here; `sonst` is JA and the one `pflicht` input is
    verified, so an engine that never looks at FEHLT_wenn answers „erfüllt" —
    the schema's own gap statement would be unreachable (P2 carries a
    `fehlt_text` of its own for exactly this branch)."""
    assert _zustand({
        "FEHLT_wenn": WAHR, "NEIN_wenn": FALSCH,
        "WERTUNG_wenn": FALSCH, "JA_wenn": FALSCH, "sonst": "JA",
    }) == Zustand.FEHLT


def test_der_erste_wahre_zweig_gewinnt_nicht_der_letzte():
    """§1: „the first condition that is **true** fires."

    NEIN_wenn stands before JA_wenn in the order, so with both true the state
    is NEIN. An engine that keeps scanning after the first hit answers with the
    last true branch instead — the exact inversion of the sentence."""
    assert _zustand({"NEIN_wenn": WAHR, "JA_wenn": WAHR, "sonst": "JA"}) == Zustand.NEIN


# --------------------------------------------------------------------------
# (ii) the same order on the real P2, where it decides a verdict
# --------------------------------------------------------------------------

# schemas/preiserhoehung.json, P2 „Einbeziehung der Preisklausel":
#   FEHLT_wenn   kreuzpruefung_klauselverweis() == false
#   NEIN_wenn    alle[ agb.fassung_datum > vertrag.datum ,
#                      vertrag.aenderungsvereinbarung_hinweis != true ,
#                      dok_vorhanden: vertrag ]
#   WERTUNG_wenn eine[ fehlt: vertrag.agb_einbezogen_hinweis ,
#                      agb.fassung_datum > vertrag.datum ]
#   sonst        JA
# NEIN_wenn is a strict subset of WERTUNG_wenn — both require the later AGB
# Fassung — so on this Prüfpunkt the two branches overlap by construction.

AGB_TEXT = (
    "Allgemeine Geschäftsbedingungen, Fassung Januar 2026\n"
    "Ziffer 4.1 Beiträge — Der Monatsbeitrag ist im Voraus zu zahlen.\n"
    "Ziffer 4.3 Der Beitrag kann angepasst werden.\n"
)
VERTRAG_TEXT = (
    "Mitgliedsvertrag vom 01.03.2025\n"
    "Laufzeit 12 Monate, Monatsbeitrag 29,90 EUR.\n"
)
# Neither text contains „5.2" in any form, so the letter's cited Ziffer is not
# findable — `kreuzpruefung_klauselverweis` returns False, not None.

P2_FAKTEN = {
    "agb.preisklausel_text": "Der Beitrag kann angepasst werden.",
    "agb.fassung_datum": date(2026, 1, 1),      # AGB-Fassung nach …
    "vertrag.datum": date(2025, 3, 1),          # … dem Vertragsschluss
    "vertrag.aenderungsvereinbarung_hinweis": False,
    # vertrag.agb_einbezogen_hinweis is deliberately NOT set: {"fehlt": …} in
    # WERTUNG_wenn is then true as well.
}


def _p2_auswerten(fakten: dict):
    k, schema = _kontext(fakten, [
        _dokument("D1", Dokumenttyp.AGB, AGB_TEXT),
        _dokument("D2", Dokumenttyp.VERTRAG, VERTRAG_TEXT),
    ])
    return pruefpunkt_auswerten(schema.pruefpunkt("P2"), k, schema)


def test_P2_nennt_die_fehlende_seite_statt_hart_zu_urteilen():
    """All three declared branches of P2 are true at once here:

      FEHLT_wenn   the letter cites „Ziffer 5.2"; neither document contains a
                   5.2, so the primitive is False and `False == false` is true
      NEIN_wenn    01.01.2026 > 01.03.2025 · aenderungsvereinbarung_hinweis is
                   False, so `!= true` · the Vertrag document is on file
      WERTUNG_wenn vertrag.agb_einbezogen_hinweis is absent → `fehlt` is true

    §1 order makes FEHLT the answer, and P2's own `fehlt_text` — „die Seite mit
    {erhoehungsschreiben.klauselverweis}" — is what the advisor reads. Under
    NEIN the case would be judged unwirksam on a page nobody has ever seen;
    under WERTUNG the missing page is never named at all."""
    erg = _p2_auswerten({**P2_FAKTEN, "erhoehungsschreiben.klauselverweis": "Ziffer 5.2"})
    assert erg.zustand == Zustand.FEHLT
    assert erg.grund == "die Stelle mit Ziffer 5.2 — in den vorliegenden AGB nicht gefunden"


def test_P2_entscheidet_statt_die_Beraterin_zu_fragen():
    """Same case, but the letter cites no Ziffer at all: `kreuzpruefung_
    klauselverweis` returns None (nothing to check), so `None == false` is null
    and FEHLT_wenn cannot fire. NEIN_wenn and WERTUNG_wenn both stay true, and
    §1 puts NEIN first.

    `grund` comes from P2's `plain_grund` (it declares no `satz_nein`), which
    is what routes the case to `rechtsbehelf_bei_NEIN`
    („widerspruch_rueckforderung") instead of a Bewertungsfrage."""
    erg = _p2_auswerten(P2_FAKTEN)
    assert erg.zustand == Zustand.NEIN
    assert erg.grund == (
        "Die Klausel, auf die sich das Studio beruft, "
        "war so bei Vertragsschluss nicht vereinbart."
    )


# --------------------------------------------------------------------------
# (iii) the parameter block belongs to its own Prüfpunkt
# --------------------------------------------------------------------------


def test_der_parameterblock_ueberlebt_den_pruefpunkt_nicht():
    """§1: `{"param": P, …}` resolves against *the Prüfpunkt's* parameters, and
    `jurist_edit_knoepfe` addresses them as „pruefpunkte.P10.parameter.
    frist_min_tage" — they belong to P10 and to nothing else.

    P10 is the only Prüfpunkt in `schemas/preiserhoehung.json` that declares
    any (`frist_min_tage: 30`). Conditions evaluated after it — the `nur_wenn`
    of an Ableitung runs on the same Fallkontext — must therefore see no
    parameters: a `{"param": "frist_min_tage"}` there is null („we cannot
    say"), never P10's 30."""
    k, schema = _kontext({
        "erhoehungsschreiben.datum": date(2026, 7, 15),
        "erhoehungsschreiben.zugang": date(2026, 7, 18),
        "erhoehungsschreiben.wirksam_ab": date(2026, 10, 1),
        "erhoehungsschreiben.form": "brief",
        "erhoehungsschreiben.kuendigungshinweis": True,
        "vertrag.laufzeit_monate": 12,
    })
    p10 = schema.pruefpunkt("P10")
    assert p10.parameter and p10.parameter["frist_min_tage"] == 30, "Schema-Annahme des Tests"

    pruefpunkt_auswerten(p10, k, schema)

    assert k.parameter_block is None
    assert k.parameter("frist_min_tage") is None
    # 30 > 12 would be true; scoped correctly the comparison is undecidable
    assert bedingung_auswerten(
        {"param": "frist_min_tage", "op": ">", "feld": "vertrag.laufzeit_monate"}, k
    ) is None


# --------------------------------------------------------------------------
# (iv) the implicit FEHLT lists every missing input, not the first
# --------------------------------------------------------------------------


def test_implizites_FEHLT_nennt_alle_fehlenden_pflichteingaben():
    """§1: „Implicit FEHLT: if no branch fired and any `eingaben` with
    `pflicht:true` is absent or unverified → FEHLT **listing those inputs**" —
    plural, and the Nachforderung is built from that list.

    P6 (`schemas/preiserhoehung.json`) declares exactly three inputs, all
    `pflicht: true`: agb.nennt_anlass, agb.nennt_voraussetzungen,
    agb.nennt_umfang. With the AGB on file but none of the three extracted:

      NEIN_wenn  alle[ eine[…==false ×3] , verifiziert: agb.preisklausel_text ]
                 → the `eine` is null (three null atoms), the `verifiziert` is
                   true → `alle` is null → does not fire
      JA_wenn    alle[ …==true ×3 , verifiziert ×3 ] → the three `verifiziert`
                 atoms are false → `alle` is false → does not fire

    No branch fires, all three `pflicht` inputs are unverified, so the state is
    FEHLT and `missing` is all three in schema order. Reporting only the first
    makes the Nachforderung understate what the consumer has to supply."""
    k, schema = _kontext({"agb.preisklausel_text": "Der Beitrag kann angepasst werden."},
                         [_dokument("D1", Dokumenttyp.AGB, AGB_TEXT)])
    erg = pruefpunkt_auswerten(schema.pruefpunkt("P6"), k, schema)

    assert erg.zustand == Zustand.FEHLT
    assert erg.missing == [
        "agb.nennt_anlass", "agb.nennt_voraussetzungen", "agb.nennt_umfang",
    ]
    # `_fehlt_satz` names each one, so the trace line understates too.
    #
    # Seit F5 stehen dort die Anzeigenamen aus dem Dokumenten-Soll und **nicht
    # mehr** die rohen feld_id — `nennt_anlass` stand vorher wörtlich auf dem
    # Schirm der Beraterin. Die Zusicherung ist unverändert („jede fehlende
    # Pflichteingabe wird genannt"), nur der Beleg ist jetzt der lesbare Name.
    for name in ("Anlass der Erhöhung", "Voraussetzungen der Erhöhung",
                 "Umfang der Erhöhung"):
        assert name in erg.grund
    assert "nennt_anlass" not in erg.grund, "rohe feld_id im Spurtext"
