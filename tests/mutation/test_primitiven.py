"""The whitelisted primitives, pinned against the contract — not against the engine.

`fallpruefer/primitiven.py` is the only code a Prüfschema may call by name, and
the four demo cases exercise exactly one value of each: 40/75/54/70 days for
`tage_zwischen`, one Preisgarantie of 11 months, no Kontoauszug at all. A
mutation run over the module (23 Aug) showed the consequence — eleven mutations
that change what the advisor is told survived all 117 tests, three of them on
code no test enters at all.

Every expectation in this file is derived by hand from
`analysis/15_data_contract.md` §1 (three-valued logic) and §2 (the rule blocks
of P2, P3, P10 and P12) plus `schemas/preiserhoehung.json`. The derivation is
written above each assertion. Nothing here was produced by running the engine
and writing down what it printed — a test that agrees with the engine by
construction tests nothing.

The two rules the whole file circles around:

  * §1: „a `feld` that is absent makes its atom `null`" — and the module
    docstring: None „never silently becomes 0 or False". A `null` that turns
    into `0` does not stay quiet, it *asserts a fact* („null Tage Vorlauf",
    „0,00 € überzahlt") about a document the engine has not read.
  * The direction and the boundary of a comparison are legal content, not
    implementation detail: P10's Vorlaufzeit is strict at 30 days, P3's
    interval runs from the Vertragsdatum forward, and P12 counts from the
    Stichtag *inclusive*.
"""

from __future__ import annotations

import pytest

from fallpruefer import primitiven
from fallpruefer.evaluator import Fallkontext, _betrag, annahmen_anwenden, pruefpunkt_auswerten
from fallpruefer.fall import Dokument, Fall, Faktum, SchemaRef, SeiteText
from fallpruefer.schema import schema_laden
from fallpruefer.vokabular import Dokumenttyp, Zustand


@pytest.fixture(scope="module")
def schema():
    return schema_laden("preiserhoehung")


def _kontext(schema, fakten: dict, dokumente=()) -> Fallkontext:
    """A case built from nothing but the facts a test names.

    No demo directory, no adapter, no cache: the point of these tests is a
    value the four scripted cases never produce, so they must not inherit
    anything from them.
    """
    fall = Fall(case_id="F-MUT-PRIM", schema=SchemaRef(fallgruppe_id="preiserhoehung"))
    fall.dokumente = list(dokumente)
    fall.fakten = [
        Faktum(feld_id=fid, wert=wert, verifiziert=True) for fid, wert in fakten.items()
    ]
    return Fallkontext(fall=fall, schema=schema)


def _dok(dok_id: str, typ: Dokumenttyp, text: str) -> Dokument:
    return Dokument(dok_id=dok_id, dokumenttyp=typ, seiten=[SeiteText(nr=1, text_original=text)])


# Arguments exactly as `schemas/preiserhoehung.json` writes them.
P10_FRIST_ARGS = {"a": "erhoehungsschreiben.zugang", "b": "erhoehungsschreiben.wirksam_ab"}
P3_GARANTIE_ARGS = {"a": "vertrag.datum", "b": "erhoehungsschreiben.wirksam_ab"}


# --------------------------------------------------------------------------
# tage_zwischen — P10's Vorlaufzeit
# --------------------------------------------------------------------------


def test_tage_zwischen_zaehlt_die_kalendertage_ohne_zuschlag():
    """M2. The number P10 compares against `frist_min_tage` and the Fristkarte
    prints as „{wert} Tage".

    Derivation: Zugang 02.03.2026 → wirksam ab 01.04.2026. March 2026 has 31
    days, so 02.03. → 31.03. is 29 days and one more day reaches 01.04. — 30
    days. (This is 20 §102's Fall 1 exactly: it sits *on* the boundary, which
    is why one day of drift decides it.)
    """
    k = _kontext(None, {
        "erhoehungsschreiben.zugang": "2026-03-02",
        "erhoehungsschreiben.wirksam_ab": "2026-04-01",
    })
    assert primitiven.tage_zwischen(k, P10_FRIST_ARGS) == 30


def test_tage_zwischen_ohne_zugang_bleibt_null_und_wird_nicht_zu_null_tagen(schema):
    """M3. 15 §1: an absent `feld` makes its atom `null`; the module docstring:
    None „never silently becomes 0 or False".

    `0` here would not be a missing value, it would be the claim „zero days of
    notice" — the worst possible reading of a letter whose wirksam_ab could not
    be read at all.
    """
    k = _kontext(schema, {"erhoehungsschreiben.wirksam_ab": "2026-04-01"})
    assert primitiven.tage_zwischen(k, P10_FRIST_ARGS) is None


def test_p10_wertung_greift_erst_unterhalb_von_dreissig_tagen(schema):
    """M2, at the level the contract states it.

    15 §2 P10 `WERTUNG_wenn`:
        {"eine": [{"prim": "tage_zwischen", "args": {zugang, wirksam_ab},
                   "op": "<", "param": "frist_min_tage"},
                  {"feld": "erhoehungsschreiben.form", "op": "in",
                   "wert": ["aushang", "website"]}]}
    with `parameter.frist_min_tage = 30`. The operator is `<`, so the boundary
    is exact: 30 days is still enough, 29 is not.

    Both cases are built so that only the first atom can move:
      * form = „brief" → the second atom is false;
      * kuendigungshinweis = true → P10's `NEIN_wenn` (which needs
        kuendigungshinweis == false) is false and cannot fire;
      * every `pflicht: true` input (datum, wirksam_ab, form,
        kuendigungshinweis) is present, so with no branch firing the implicit
        FEHLT of §1 does not apply and `sonst: "JA"` is reached.

    Dates: 03.03.2026 → 01.04.2026 = 29 days (28 days to 31.03. plus one);
           02.03.2026 → 01.04.2026 = 30 days.
    """
    p10 = schema.pruefpunkt("P10")

    basis = {
        "erhoehungsschreiben.datum": "2026-02-27",
        "erhoehungsschreiben.wirksam_ab": "2026-04-01",
        "erhoehungsschreiben.form": "brief",
        "erhoehungsschreiben.kuendigungshinweis": True,
    }

    knapp = _kontext(schema, {**basis, "erhoehungsschreiben.zugang": "2026-03-03"})
    assert pruefpunkt_auswerten(p10, knapp, schema).zustand == Zustand.WERTUNG, \
        "29 Tage Vorlauf liegen unter frist_min_tage=30 und gehören der Beraterin vorgelegt"

    genau = _kontext(schema, {**basis, "erhoehungsschreiben.zugang": "2026-03-02"})
    assert pruefpunkt_auswerten(p10, genau, schema).zustand == Zustand.JA, \
        "30 Tage erfuellen den Vergleich < 30 nicht — er ist strikt"


def test_p10_ohne_lesbaren_zugang_behauptet_keine_null_tage(schema):
    """M3, at the level the contract states it.

    Same construction as above, but `erhoehungsschreiben.zugang` is absent
    (`pflicht: false` in P10's `eingaben`, so its absence is not an implicit
    FEHLT). Per §1 the first atom of `WERTUNG_wenn` is then `null`, the second
    is false, so `eine` = null — and a branch fires only on `true`. No branch
    fires, every `pflicht: true` input is present, so `sonst: "JA"`.

    The Fristkarte is the second half of the same statement: 15 §2 P10.frist
    renders „{wert} Tage · Stand {stichtag}". With no Zugang there is no
    value to render, so there must be no card — „0 Tage · Stand 27.08.2026"
    would be a fact about a date the engine never had.
    """
    p10 = schema.pruefpunkt("P10")
    k = _kontext(schema, {
        "erhoehungsschreiben.datum": "2026-02-27",
        "erhoehungsschreiben.wirksam_ab": "2026-04-01",
        "erhoehungsschreiben.form": "brief",
        "erhoehungsschreiben.kuendigungshinweis": True,
    })
    erg = pruefpunkt_auswerten(p10, k, schema)
    assert erg.zustand == Zustand.JA
    assert erg.frist is None, "ohne Zugang gibt es keine Vorlaufzeit anzuzeigen"


# --------------------------------------------------------------------------
# monate_zwischen — P3's Preisgarantie
# --------------------------------------------------------------------------


def test_monate_zwischen_misst_vom_vertrag_zur_erhoehung(schema):
    """M4. 15 §2 P3 `NEIN_wenn` calls
        {"prim": "monate_zwischen", "args": {"a": "vertrag.datum",
                                             "b": "erhoehungsschreiben.wirksam_ab"}}
    and compares it `<` against `vertrag.preisgarantie_monate`. The proposition
    „Es gibt keine Preisgarantie, die den Erhöhungszeitpunkt abdeckt" only has
    a meaning if the interval runs *from* the Vertragsdatum *to* the increase —
    a swapped pair turns every elapsed guarantee into a negative number, and a
    negative number is below every positive Garantiedauer.

    Derivation: 01.03.2019 → 01.03.2026 = (2026−2019)·12 + (3−3) = 84 whole
    months; the day of month is equal, so no partial month is deducted.
    """
    k = _kontext(schema, {
        "vertrag.datum": "2019-03-01",
        "erhoehungsschreiben.wirksam_ab": "2026-03-01",
    })
    assert primitiven.monate_zwischen(k, P3_GARANTIE_ARGS) == 84


def test_monate_zwischen_ohne_vertragsdatum_bleibt_null(schema):
    """M5. 15 §1 again: the absent `vertrag.datum` makes the atom `null`.

    `0` would read as „the increase takes effect in the month the contract was
    signed" — inside every Preisgarantie there is.
    """
    k = _kontext(schema, {"erhoehungsschreiben.wirksam_ab": "2026-03-01"})
    assert primitiven.monate_zwischen(k, P3_GARANTIE_ARGS) is None


def test_p3_eine_abgelaufene_preisgarantie_traegt_kein_nein(schema):
    """M4, at the level the contract states it.

    15 §2 P3 `NEIN_wenn` = {"alle": [preisgarantie_monate > 0,
                                     monate_zwischen(vertrag.datum, wirksam_ab)
                                     < preisgarantie_monate]}, sonst „JA".

    Contract from 01.03.2019, 12 months of Preisgarantie, increase effective
    01.03.2026: 84 months have run, 84 < 12 is false, so `alle` is false and
    the branch does not fire. Both `pflicht: true` inputs (vertrag.datum,
    erhoehungsschreiben.wirksam_ab) are present → `sonst: "JA"`.

    A NEIN here would put `satz_nein` into the Musterbrief: „Der Vertrag
    enthält eine Preisgarantie über 12 Monate — die Erhöhung zum 01.03.2026
    fällt in diesen Zeitraum." That sentence would go to the company on VZ
    letterhead about a guarantee that ran out in 2020.
    """
    p3 = schema.pruefpunkt("P3")
    k = _kontext(schema, {
        "vertrag.preisgarantie_monate": 12,
        "vertrag.datum": "2019-03-01",
        "erhoehungsschreiben.wirksam_ab": "2026-03-01",
    })
    assert pruefpunkt_auswerten(p3, k, schema).zustand == Zustand.JA


def test_p3_ohne_vertragsdatum_meldet_die_luecke_statt_zu_urteilen(schema):
    """M5, at the level the contract states it.

    Preisgarantie 12 is on file, `vertrag.datum` is not (the contract page with
    the date is missing or unreadable). Per §1 the second atom of `NEIN_wenn`
    is `null`, the first is true, so `alle` = null and the branch does not
    fire. `JA_wenn` does not exist, so §1's *implicit FEHLT* applies: P3 lists
    `vertrag.datum` with `pflicht: true` and it is absent → FEHLT.

    This is the shape `test_keine_falschen_sicheren_antworten` exists for: the
    honest answer is „it is missing", never a verdict derived from a date the
    engine never read.
    """
    p3 = schema.pruefpunkt("P3")
    k = _kontext(schema, {
        "vertrag.preisgarantie_monate": 12,
        "erhoehungsschreiben.wirksam_ab": "2026-03-01",
    })
    erg = pruefpunkt_auswerten(p3, k, schema)
    assert erg.zustand == Zustand.FEHLT
    assert "vertrag.datum" in erg.missing


# --------------------------------------------------------------------------
# datum_plus — the Zugangsvermutung of annahmen[0]
# --------------------------------------------------------------------------


def test_datum_plus_addiert_vorwaerts():
    """M7. 15 §2 annahmen[0] „zugang_plus_3": Zugang = „datum_plus(
    erhoehungsschreiben.datum, 3)", displayed as „Zugang = Datum des Schreibens
    + 3 Tage (angenommen)". A letter is received *after* it is written.

    Derivation: 15.06.2026 + 3 days = 18.06.2026.
    """
    k = _kontext(None, {"erhoehungsschreiben.datum": "2026-06-15"})
    from datetime import date

    assert primitiven.datum_plus(k, {"feld": "erhoehungsschreiben.datum", "tage": 3}) == date(2026, 6, 18)


def test_die_zugangsannahme_setzt_den_zugang_nach_dem_briefdatum(schema):
    """M7, through the annahmen parser that actually reaches this primitive.

    `evaluator.annahmen_anwenden` reads the expression string out of
    `schemas/preiserhoehung.json` and fills `erhoehungsschreiben.zugang` when
    the document did not carry one. Everything P10 measures hangs off this
    anchor, so the sign of the addition decides the main demo case: three days
    the wrong way is a six-day error, always in the generous direction.

    Derivation: Briefdatum 15.06.2026 + 3 = 18.06.2026, and 18.06. is after
    15.06. — the second assertion is the statement `anzeige` makes.
    """
    from datetime import date

    fall = Fall(case_id="F-MUT-ANNAHME", schema=SchemaRef(fallgruppe_id="preiserhoehung"))
    fall.fakten = [Faktum(feld_id="erhoehungsschreiben.datum", wert="2026-06-15", verifiziert=True)]
    k = Fallkontext(fall=fall, schema=schema)

    annahmen_anwenden(fall, schema, k)

    assert k.feld("erhoehungsschreiben.zugang") == date(2026, 6, 18)
    assert k.datum("erhoehungsschreiben.zugang") > k.datum("erhoehungsschreiben.datum"), \
        "der Zugang kann nicht vor dem Schreiben liegen"


# --------------------------------------------------------------------------
# kreuzpruefung_klauselverweis — P2's FEHLT_wenn
# --------------------------------------------------------------------------

# P2 evaluates to JA on this fixture unless the cross-check says false:
#   FEHLT_wenn  = {prim: kreuzpruefung_klauselverweis, op: "==", wert: false}
#   NEIN_wenn   = {alle: [agb.fassung_datum > vertrag.datum, …]}   → 01.01.2024
#                 is not after 01.06.2024, so `alle` is false
#   WERTUNG_wenn= {eine: [{fehlt: vertrag.agb_einbezogen_hinweis},
#                         agb.fassung_datum > vertrag.datum]}      → both false
#   sonst „JA", and P2's `pflicht: true` inputs (agb.preisklausel_text,
#   vertrag.datum) are both present, so the implicit FEHLT does not apply.
P2_BASIS = {
    "agb.preisklausel_text": "Der Betreiber darf den Monatsbeitrag anpassen.",
    "agb.fassung_datum": "2024-01-01",
    "vertrag.datum": "2024-06-01",
    "vertrag.agb_einbezogen_hinweis": True,
}


def test_ohne_zitierte_ziffer_ist_die_kreuzpruefung_nicht_fehlgeschlagen(schema):
    """M9. 15 §1: „a `feld` that is absent makes its atom `null`".

    `false` is not the same statement as `null` here, and 15 §2 P2 is what
    makes the difference visible: `FEHLT_wenn` fires on `== false`, i.e. false
    means „checked, and the cited Ziffer is not in the document". A letter that
    cites no Ziffer at all („gemäß unseren AGB", grundlage_genannt = „gesetz")
    has nothing to check — the question has no subject, so the answer is null.

    If it were false, P2 would go FEHLT and P2's `fehlt_text` would demand
    „die Seite mit {erhoehungsschreiben.klauselverweis}" from the consumer —
    a sentence that ends in an empty placeholder.
    """
    agb = _dok("D2", Dokumenttyp.AGB, "Ziffer 5.2 Der Betreiber darf den Monatsbeitrag anpassen.")
    k = _kontext(schema, dict(P2_BASIS), [agb])

    assert primitiven.kreuzpruefung_klauselverweis(k, {}) is None

    erg = pruefpunkt_auswerten(schema.pruefpunkt("P2"), k, schema)
    assert erg.zustand == Zustand.JA, "ein fehlender Verweis ist keine fehlgeschlagene Kreuzprüfung"


def test_eine_ziffer_mit_nachgestelltem_punkt_gilt_als_gefunden(schema):
    """M12. 18 §14 Finding #10: the match is two-stage, „full string, then the
    last token", and the second stage alone is not enough.

    Derivation from the code the finding describes: the short form is accepted
    only inside `(?<![\\w.,])5\\.2(?![\\w.,])`. German AGB normally write the
    heading as „Ziffer 5.2. Beitragsanpassung" — with a trailing full stop —
    and that full stop breaks the lookahead. The full string „Ziffer 5.2"
    stands in the document as a plain substring, so the first stage carries it.

    Without the first stage the primitive answers false on a *correct* letter,
    P2's `FEHLT_wenn` fires, and the engine demands a page that is already in
    the Akte — the Seepark beat, played on a case that has no gap.
    """
    agb = _dok(
        "D2",
        Dokumenttyp.AGB,
        "Ziffer 5.2. Beitragsanpassung\nDer Betreiber darf den Monatsbeitrag anpassen.",
    )
    k = _kontext(schema, {**P2_BASIS, "erhoehungsschreiben.klauselverweis": "Ziffer 5.2"}, [agb])

    assert primitiven.kreuzpruefung_klauselverweis(k, {}) is True

    erg = pruefpunkt_auswerten(schema.pruefpunkt("P2"), k, schema)
    assert erg.zustand == Zustand.JA, "die zitierte Ziffer steht im Dokument — nichts fehlt"


def test_ein_verweis_ohne_ziffer_gilt_als_geprueft_und_nicht_gefunden(schema):
    """M14. The counterpart of the M9 test, on the other side of the same line.

    A reference that *is* made but carries no number at all („laut
    Preisanpassungsklausel", „Ziffer fünf") has been checked: the primitive
    looked for it in the AGB and the contract and did not find it. That is a
    finding, so 15 §2 P2 `FEHLT_wenn` ({prim …, "op": "==", "wert": false})
    fires and the Prüfpunkt goes FEHLT — rather than falling through to a JA
    the document does not support, with the Fallakte reading as though the
    Klauselverweis had been verified.

    The AGB text below deliberately does not contain the word
    „Preisanpassungsklausel", so the full-string stage cannot match either.
    """
    agb = _dok("D2", Dokumenttyp.AGB, "Ziffer 5.2 Der Betreiber darf den Monatsbeitrag anpassen.")
    k = _kontext(
        schema,
        {**P2_BASIS, "erhoehungsschreiben.klauselverweis": "laut Preisanpassungsklausel"},
        [agb],
    )

    assert primitiven.kreuzpruefung_klauselverweis(k, {}) is False

    erg = pruefpunkt_auswerten(schema.pruefpunkt("P2"), k, schema)
    assert erg.zustand == Zustand.FEHLT


# --------------------------------------------------------------------------
# summe_rueckforderung — P12's Betragskarte
# --------------------------------------------------------------------------

# 15 §2 P12: eingaben kontoauszug.abbuchungen · vertrag.beitrag ·
# erhoehungsschreiben.wirksam_ab, berechnung = summe_rueckforderung(),
# betrag.anzeige = „{betrag} € (Annahme: alle Abbuchungen seit
# {erhoehungsschreiben.wirksam_ab} belegt)".
P12_BASIS = {
    "vertrag.beitrag": 29.90,
    "erhoehungsschreiben.wirksam_ab": "2026-04-01",
}


def test_ohne_ueberzahlung_gibt_es_keinen_betrag_statt_null_euro(schema):
    """M16. 18 §14 Finding #8, and the primitive's own docstring: „Returns
    None, not 0. ‚Nothing has been overpaid yet' and ‚nothing is owed' are
    different statements, and the letter picks a different variant for each."

    Case: the increase was announced but the Kontoauszug still shows exactly
    the agreed 29,90 € — or it was already refunded. Nothing has been overpaid
    *yet*; the Rückforderung is not zero, it is not yet computable.

    `evaluator._betrag` branches on exactly that: `roh is None` → „noch nicht
    berechenbar" plus the note that the basis is missing. A 0,00 € card would
    instead report „no damage" on a case that has one, and 15 §7 has the
    Referat reading that line as „bedeutsame Schadenshöhe".
    """
    k = _kontext(schema, {
        **P12_BASIS,
        "kontoauszug.abbuchungen": [
            {"datum": "2026-04-01", "betrag": 29.90},
            {"datum": "2026-05-01", "betrag": 29.90},
        ],
    })

    assert primitiven.summe_rueckforderung(k, {}) is None

    angabe = _betrag(schema.pruefpunkt("P12"), k)
    assert angabe.roh is None
    assert angabe.wert == "noch nicht berechenbar"


def test_die_abbuchung_am_stichtag_zaehlt_mit(schema):
    """M17. The primitive's docstring: „What was overpaid **since** the
    increase took effect" — `erhoehungsschreiben.wirksam_ab` is the first day
    of the new price, not the last day of the old one, so the debit *on* that
    date is the first overpayment.

    It is also the typical one: increases take effect on the first of a month
    and studios debit on the first of a month, so excluding the Stichtag drops
    the first overpayment of every case.

    Derivation: agreed 29,90 €, debited 36,90 € on 01.04.2026 — the day the
    increase takes effect. 36,90 − 29,90 = 7,00 €.
    """
    k = _kontext(schema, {
        **P12_BASIS,
        "kontoauszug.abbuchungen": [{"datum": "2026-04-01", "betrag": 36.90}],
    })
    assert primitiven.summe_rueckforderung(k, {}) == pytest.approx(7.00)


def test_zurueckgefordert_wird_die_differenz_nicht_der_ganze_beitrag(schema):
    """M18. Overpaid is what was paid *above* what was agreed — which is the
    only reason 15 §2 carries `vertrag.beitrag` as `pflicht: true` and P12
    names it as an input at all.

    Derivation: agreed 29,90 €; debited 36,90 € on 01.05. and again on 01.06.,
    both after the 01.04. effective date. Overpayment per month 36,90 − 29,90 =
    7,00 €, over two months 14,00 €. The gross figure would be 73,80 € — a
    payment demand on VZ letterhead more than five times too high, and the same
    wrong Schadenshöhe in the Radar.
    """
    k = _kontext(schema, {
        **P12_BASIS,
        "kontoauszug.abbuchungen": [
            {"datum": "2026-05-01", "betrag": 36.90},
            {"datum": "2026-06-01", "betrag": 36.90},
        ],
    })
    assert primitiven.summe_rueckforderung(k, {}) == pytest.approx(14.00)


def test_abbuchungen_vor_der_erhoehung_bleiben_draussen(schema):
    """The guard the M17 test must not accidentally licence: a debit *before*
    the increase took effect is the old price being paid, not an overpayment —
    even if the amount already differs. Without this the „inclusive" statement
    above would read as „all debits count".

    Derivation: 01.03.2026 lies before the 01.04.2026 effective date, so it is
    skipped; the 01.04. debit contributes 36,90 − 29,90 = 7,00 €.
    """
    k = _kontext(schema, {
        **P12_BASIS,
        "kontoauszug.abbuchungen": [
            {"datum": "2026-03-01", "betrag": 36.90},
            {"datum": "2026-04-01", "betrag": 36.90},
        ],
    })
    assert primitiven.summe_rueckforderung(k, {}) == pytest.approx(7.00)
