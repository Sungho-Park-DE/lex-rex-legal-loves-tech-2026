"""Mutation coverage for the three-valued rule grammar (contract §1).

The grammar is the one module every Prüfpunkt, every Dokumenten-Soll condition
and every letter variant runs through, and it is the module whose failure mode
is silent: a wrong `null → false` never raises, never renders red, and simply
lets a branch fire (or not) one step earlier than the law says. A mutation run
over `fallpruefer/regeln.py` found fourteen such edits that the suite did not
notice — every one of them a line the contract states literally.

Each test below pins exactly one of those lines. The expected value is derived
by hand in the comment above it from `analysis/15_data_contract.md` §1/§2 and
from `schemas/preiserhoehung.json`; where a rule from that file is used, it is
read out of the schema at runtime rather than retyped, so the test cannot drift
away from the file the Jurist edits.

Two conventions this file follows on purpose:

* it asserts with `is True` / `is False` / `is None`, never on truthiness — the
  whole point of the grammar is that `None` and `False` are different answers,
  and `assert not auswerten(...)` cannot tell them apart;
* it uses the production `Fallkontext`, not a test double, so the fact lookup
  („an unverified value is not a value") is the real one.
"""

from __future__ import annotations

from datetime import date

import pytest

from fallpruefer.evaluator import Fallkontext
from fallpruefer.fall import Dokument, Fall, Faktum, SeiteText
from fallpruefer.regeln import RegelFehler, auswerten
from fallpruefer.schema import Pruefpunkt, schema_laden
from fallpruefer.vokabular import Dokumenttyp, Einordnung, label


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _schema():
    return schema_laden("preiserhoehung")


def _pruefpunkt(pid: str) -> Pruefpunkt:
    p = _schema().pruefpunkt(pid)
    assert p is not None, f"{pid} steht nicht mehr in schemas/preiserhoehung.json"
    return p


def _regel(pid: str, zweig: str) -> dict:
    """The branch condition verbatim out of `schemas/preiserhoehung.json`.

    Read from the file instead of retyped: the point of a schema-driven engine
    is that the rule lives in the JSON, so a test that pins the rule's meaning
    has to pin the JSON's rule, not a copy of it.
    """
    regel = _pruefpunkt(pid).regel or {}
    assert zweig in regel, f"{pid} hat keinen Zweig {zweig} mehr"
    return regel[zweig]


def _rechtsbehelf_wenn(rid: str) -> dict:
    r = _schema().rechtsbehelfe.nach_id(rid)
    assert r is not None and r.wenn, f"{rid} hat keine Bedingung mehr"
    return r.wenn


def _faktum(feld_id: str, wert, verifiziert: bool | None = None) -> Faktum:
    """One extracted fact.

    `verifiziert=None` is the normal case (a value whose quote was checked);
    `verifiziert=False` is the trust layer's refusal — `Fallkontext` then hands
    out neither the value nor a „belegt".
    """
    return Faktum(feld_id=feld_id, wert=wert, verifiziert=verifiziert)


def _kontext(fakten=(), dokumente=(), parameter=None, extra=None) -> Fallkontext:
    fall = Fall(case_id="F-MUT-REGELN", schema={"fallgruppe_id": "preiserhoehung"})
    fall.fakten.extend(fakten)
    for i, typ in enumerate(dokumente, start=1):
        fall.dokumente.append(Dokument(
            dok_id=f"D{i}", dokumenttyp=Dokumenttyp(typ),
            seiten=[SeiteText(nr=1, text_original="", text_pseudonym="")],
        ))
    k = Fallkontext(fall=fall, schema=_schema(), extra=dict(extra or {}))
    k.parameter_block = parameter
    return k


# --------------------------------------------------------------------------
# §1 — the three-valued core
# --------------------------------------------------------------------------


def test_nicht_auf_null_bleibt_null():
    """§1, wörtlich: „`nicht null` = null".

    Derivation. `agb.kostenbezug` is a Soll field of the `agb` document
    (§2, dokumenten_soll) and no AGB was handed in, so no Faktum carries it.
    §1: „a `feld` that is absent makes its atom `null`" → the inner atom is
    null. §1: „nicht null = null" → the whole condition is null. And §1: „a
    branch fires only on `true`" → a JA_wenn built this way must NOT fire on a
    case with no AGB at all.

    The mutant that drops the None-passthrough answers `not None` = True here,
    i.e. „JA — wirksam" on an Akte that contains no clause whatsoever.
    """
    k = _kontext()
    innen = {"feld": "agb.kostenbezug", "op": "==", "wert": True}

    assert auswerten(innen, k) is None
    assert auswerten({"nicht": innen}, k) is None

    # the other two rows of the same line, so the test pins the whole operator
    # and not just its null case
    assert auswerten({"nicht": True}, k) is False
    assert auswerten({"nicht": False}, k) is True


def test_alle_meldet_false_auch_wenn_ein_zweig_unbekannt_ist():
    """§1: „`alle` = false if any false, else null if any null, else true" —
    false has precedence over null, not the other way round.

    Derivation. The condition is the core of P7's JA_wenn (§2: senkungspflicht
    == „pflicht" AND kostenbezug == true), used here as an exclusion. On the
    Akte: `agb.senkungspflicht` is on file as „keine" — the clause grants no
    duty to pass reductions on — while `agb.kostenbezug` is not on file at all
    (the page carrying it is missing).

      * „keine" == „pflicht"  → false  (settled, whatever the missing page says)
      * kostenbezug == true   → null   (absent field, §1)
      * alle [false, null]    → FALSE  (false wins)
      * nicht false           → TRUE   (the exclusion holds)

    With the precedence turned round the `alle` answers null, the `nicht`
    answers null, and the exclusion goes quiet although it is settled.
    """
    k = _kontext(fakten=[_faktum("agb.senkungspflicht", "keine")])
    alle = {"alle": [
        {"feld": "agb.senkungspflicht", "op": "==", "wert": "pflicht"},
        {"feld": "agb.kostenbezug", "op": "==", "wert": True},
    ]}

    assert auswerten(alle, k) is False
    assert auswerten({"nicht": alle}, k) is True

    # second row of the same line: with no false among the children, one null
    # makes the whole thing null
    nur_null_daneben = {"alle": [
        {"feld": "agb.senkungspflicht", "op": "==", "wert": "keine"},
        {"feld": "agb.kostenbezug", "op": "==", "wert": True},
    ]}
    assert auswerten(nur_null_daneben, k) is None


def test_ein_fehlendes_feld_macht_seinen_atomwert_null_nicht_false():
    """§1: „a `feld` that is absent makes its atom `null`".

    Derivation. P14's WERTUNG_wenn (§2) reads
    `gespraech.monate_erhoeht_gezahlt`, which the Leitfaden fills — before the
    advisor has asked the question there is no Faktum for it. §1 gives that
    atom null, not false, and `nicht null` stays null.

    A false here is the exact collapse the module docstring names as the worst
    failure mode: under a `nicht` every unasked question would read as
    „condition met / nothing to worry about".
    """
    k = _kontext()
    atom = _regel("P14", "WERTUNG_wenn")

    assert auswerten(atom, k) is None
    assert auswerten({"nicht": atom}, k) is None


def test_unvergleichbare_typen_ergeben_null_nicht_false():
    """§1 three-valued logic — an operand that cannot be compared is „we cannot
    say", never „false" (`regeln._vergleichen`; the same rule is spelled out in
    tests/test_robustheit.py: „int < str ist ein TypeError, den die Grammatik
    auf None abbildet").

    Derivation. §2 declares `vertrag.laufzeit_monate` as `typ: "zahl"`, and
    P8's WERTUNG_wenn compares it against the literal 24. A model that returns
    the string „30" puts a str next to an int: Python refuses that comparison,
    and the value therefore says nothing — neither that the Laufzeit is over 24
    months nor that it is not.

    Answering false would let `nicht` turn a mistyped extraction into
    „geprüft und in Ordnung".
    """
    k = _kontext(fakten=[_faktum("vertrag.laufzeit_monate", "30")])
    atom = {"feld": "vertrag.laufzeit_monate", "op": ">", "wert": 24}

    assert auswerten(atom, k) is None
    assert auswerten({"nicht": atom}, k) is None


# --------------------------------------------------------------------------
# §1 — the atoms
# --------------------------------------------------------------------------


def test_fehlt_meint_abwesend_nicht_verneint():
    """§1: `{"fehlt": F}` = the field is absent. §0 keeps the two apart at the
    vocabulary level too — `herkunft: fehlt` is a different value from
    `herkunft: gespraech`, an answer the consumer gave.

    Derivation. P2's WERTUNG_wenn (§2) is
    `eine [ {fehlt: vertrag.agb_einbezogen_hinweis}, {agb.fassung_datum > vertrag.datum} ]`,
    and the Leitfaden question behind that field is „Haben Sie beim
    Vertragsschluss die AGB bekommen …?". The consumer answered it with „no",
    so `vertrag.agb_einbezogen_hinweis` is on file as false. No AGB version
    date was extracted.

      * fehlt(agb_einbezogen_hinweis) → FALSE — the field is there, the answer
        is „nein"; that is knowledge, not a gap
      * fassung_datum > vertrag.datum → null (absent field, §1)
      * eine [false, null]            → NULL → WERTUNG does not fire

    The mutant reads the answered „nein" as a missing answer: the atom becomes
    true, `eine` becomes true, and the consumer's own statement disappears from
    the assessment behind a „die Beraterin muss das noch bewerten".
    """
    k = _kontext(fakten=[_faktum("vertrag.agb_einbezogen_hinweis", False)])

    assert auswerten({"fehlt": "vertrag.agb_einbezogen_hinweis"}, k) is False
    assert auswerten(_regel("P2", "WERTUNG_wenn"), k) is None

    # and the honest gap still is one
    assert auswerten({"fehlt": "agb.fassung_datum"}, _kontext()) is True


def test_vorhanden_meint_nicht_null_nicht_wahrheitswert():
    """§1: `{"vorhanden": F}` = the field is present — the counterpart of
    `fehlt`, so the two have to answer the same question with opposite signs.

    Derivation. P8d's WERTUNG_wenn (§2 — the Laufzeit arm, split out of P8 on
    24 Aug because § 306 Abs. 1 keeps the price clause alive when the
    Laufzeit clause falls; ergänzend, so it never moves the Einordnung) is
    `eine [ {vertrag.laufzeit_monate > 24}, {vorhanden: vertrag.verlaengerung_text} ]`.
    On the Akte: a 12-month Laufzeit, and a `vertrag.verlaengerung_text` that
    was extracted as an empty string (the Verlängerungsklausel's heading was
    found, the body came back blank).

      * 12 > 24                        → false
      * vorhanden(verlaengerung_text)  → TRUE — the field is on file
      * eine [false, true]             → TRUE → WERTUNG, § 309 Nr. 9 gets looked at

    A truthiness test answers false for an empty text and for 0,00 €, so the
    Prüfpunkt would step over an extraction it actually has.
    """
    k = _kontext(fakten=[
        _faktum("vertrag.laufzeit_monate", 12),
        _faktum("vertrag.verlaengerung_text", ""),
        _faktum("erhoehungsschreiben.alter_betrag", 0.0),
    ])

    assert auswerten({"vorhanden": "vertrag.verlaengerung_text"}, k) is True
    assert auswerten(_regel("P8d", "WERTUNG_wenn"), k) is True
    # „0,00 €" is a number the letter has to be able to read, not an absence
    assert auswerten({"vorhanden": "erhoehungsschreiben.alter_betrag"}, k) is True

    # the pair: what is really absent is absent for both atoms
    leer = _kontext()
    assert auswerten({"vorhanden": "vertrag.verlaengerung_text"}, leer) is False
    assert auswerten({"fehlt": "vertrag.verlaengerung_text"}, leer) is True


def test_ein_unverifiziertes_zitat_traegt_kein_NEIN():
    """§1: `{"verifiziert": F}`. 14 §3 trust layer: every LLM output passes a
    deterministic validator before it can carry a statement.

    Derivation. P6's NEIN_wenn (§2) is
    `alle [ eine[ nennt_anlass==false, nennt_voraussetzungen==false, nennt_umfang==false ],
            verifiziert: agb.preisklausel_text ]`.
    The second half is there precisely so a Transparenz-NEIN can only be spoken
    about a clause text the tool could check. On the Akte: the model reports
    „nennt keinen Anlass", the other two flags come back true — and the quoted
    `agb.preisklausel_text` failed the quote check.

      * eine [true, false, false]            → true
      * verifiziert(agb.preisklausel_text)   → FALSE — the fact exists, the
        check refused it
      * alle [true, false]                   → FALSE → no NEIN

    With the guard gone every atom reports „belegt" and P6 fires NEIN, i.e. the
    tool says „wahrscheinlich unwirksam" about a clause text it demonstrably
    could not verify. tests/stoerfall/ is still empty, so nothing else covers
    this beat.
    """
    k = _kontext(fakten=[
        _faktum("agb.nennt_anlass", False),
        _faktum("agb.nennt_voraussetzungen", True),
        _faktum("agb.nennt_umfang", True),
        _faktum("agb.preisklausel_text", "Wir dürfen die Beiträge anpassen.", verifiziert=False),
    ])

    assert auswerten({"verifiziert": "agb.preisklausel_text"}, k) is False
    assert auswerten(_regel("P6", "NEIN_wenn"), k) is False


# --------------------------------------------------------------------------
# §1 — the operator set OP ∈ == != < <= > >= in nicht_in
# --------------------------------------------------------------------------


def test_kleiner_als_ist_streng_an_der_grenze():
    """§1 operator `<`. Two Prüfpunkte sit on that boundary with real cases on
    it, so the strictness is not academic.

    Derivation P10. `schemas/preiserhoehung.json` sets
    P10.parameter.frist_min_tage = 30 (asserted below), and P10's WERTUNG_wenn
    is `eine [ tage_zwischen(zugang, wirksam_ab) < frist_min_tage,
               form in [aushang, website] ]`.
    Zugang 01.01.2026, wirksam ab 31.01.2026 → 30 days of notice; the letter
    came by post.

      * 30 < 30      → FALSE — „mindestens 30 Tage" is met exactly
      * „brief" in [aushang, website] → false
      * eine [false, false] → FALSE → no WERTUNG; P10 falls through to sonst: JA

    analysis/20_franz_lieferung_r2.md:102 puts Franz' Fall 1 on exactly this
    boundary, so `<=` would tip the main demo case to WERTUNG and the whole
    Einordnung to „unklar".

    Derivation P3. NEIN_wenn is
    `alle [ preisgarantie_monate > 0, monate_zwischen(vertrag.datum, wirksam_ab) < preisgarantie_monate ]`.
    Contract 01.01.2025, 12 months of price guarantee, increase effective
    01.01.2026 → monate_zwischen = 12 whole months.

      * 12 > 0   → true
      * 12 < 12  → FALSE — the increase takes effect the day the guarantee runs
        out, so it is not inside the guaranteed period
      * alle [true, false] → FALSE → no NEIN

    `<=` would answer „wahrscheinlich unwirksam" for an increase that starts
    the moment the guarantee ends.
    """
    p10 = _pruefpunkt("P10")
    assert (p10.parameter or {})["frist_min_tage"] == 30
    k10 = _kontext(
        fakten=[
            _faktum("erhoehungsschreiben.zugang", date(2026, 1, 1)),
            _faktum("erhoehungsschreiben.wirksam_ab", date(2026, 1, 31)),
            _faktum("erhoehungsschreiben.form", "brief"),
        ],
        parameter=p10.parameter,
    )
    assert auswerten(_regel("P10", "WERTUNG_wenn"), k10) is False

    k3 = _kontext(fakten=[
        _faktum("vertrag.datum", date(2025, 1, 1)),
        _faktum("vertrag.preisgarantie_monate", 12),
        _faktum("erhoehungsschreiben.wirksam_ab", date(2026, 1, 1)),
    ])
    assert auswerten(_regel("P3", "NEIN_wenn"), k3) is False

    # one day short of the guarantee, the same rule does fire — so the test
    # pins a boundary, not a rule that never triggers
    k3_knapp = _kontext(fakten=[
        _faktum("vertrag.datum", date(2025, 1, 1)),
        _faktum("vertrag.preisgarantie_monate", 12),
        _faktum("erhoehungsschreiben.wirksam_ab", date(2025, 12, 31)),
    ])
    assert auswerten(_regel("P3", "NEIN_wenn"), k3_knapp) is True


def test_groesser_gleich_schliesst_die_grenze_ein():
    """§1 operator `>=`.

    Derivation. P14's WERTUNG_wenn (§2) is
    `gespraech.monate_erhoeht_gezahlt >= 6`. The consumer answered the
    Leitfaden question with „six months".

      * 6 >= 6 → TRUE → WERTUNG: the advisor gets the Verwirkungs-/
        Zustimmungsfrage put in front of her, which is what P14 exists for
      * 5 >= 6 → false → sonst: JA

    A `>` silently drops exactly the person who is on the boundary.
    """
    regel = _regel("P14", "WERTUNG_wenn")

    k_grenze = _kontext(fakten=[_faktum("gespraech.monate_erhoeht_gezahlt", 6)])
    assert auswerten(regel, k_grenze) is True

    k_darunter = _kontext(fakten=[_faktum("gespraech.monate_erhoeht_gezahlt", 5)])
    assert auswerten(regel, k_darunter) is False


def test_nicht_in_ist_die_verneinung_von_in():
    """§1 lists `nicht_in` as an operator of the grammar in its own right.

    No Prüfpunkt in `schemas/preiserhoehung.json` uses it today (Jurist-Edit
    and the second schema file will), so the condition below is built from that
    line of §1 rather than read out of the file — and it is paired with the
    `in` it has to be the opposite of. `erhoehungsschreiben.form` and its enum
    values come from §2's Soll; „aushang"/„website" are the two P10 treats as
    the doubtful forms.

      * form „aushang": in [aushang, website] → true, nicht_in → FALSE
      * form „brief":   in [aushang, website] → false, nicht_in → TRUE

    An inverted `nicht_in` cannot be seen on screen: the JSON still reads
    correctly, only the engine answers the other way round.
    """
    drin = {"feld": "erhoehungsschreiben.form", "op": "in", "wert": ["aushang", "website"]}
    draussen = {"feld": "erhoehungsschreiben.form", "op": "nicht_in", "wert": ["aushang", "website"]}

    k_aushang = _kontext(fakten=[_faktum("erhoehungsschreiben.form", "aushang")])
    assert auswerten(drin, k_aushang) is True
    assert auswerten(draussen, k_aushang) is False

    k_brief = _kontext(fakten=[_faktum("erhoehungsschreiben.form", "brief")])
    assert auswerten(drin, k_brief) is False
    assert auswerten(draussen, k_brief) is True


def test_ungleich_ist_die_verneinung_von_gleich():
    """§1 operator `!=`.

    Derivation P2. NEIN_wenn (§2) is
    `alle [ agb.fassung_datum > vertrag.datum,
            vertrag.aenderungsvereinbarung_hinweis != true,
            dok_vorhanden: vertrag ]`.
    The middle atom is the escape hatch: a newer AGB version is only a problem
    if no change to the contract was agreed. On the Akte: contract 10.01.2024,
    AGB version 01.06.2025, and the contract itself records that a later AGB
    change was agreed.

      * 01.06.2025 > 10.01.2024      → true
      * true != true                 → FALSE — the change was agreed
      * dok_vorhanden(vertrag)       → true
      * alle [true, false, true]     → FALSE → no NEIN

    With `!=` behaving like `==`, P2 says NEIN precisely when the AGB change
    was validly agreed — a „wahrscheinlich unwirksam" built on the fact that
    everything was in order.

    Derivation rechtsbehelfe. `bestreiten_nachweise_verlangen.wenn` (§2) is
    `alle [ einordnung == „unklar – es fehlt …", fehlt_unternehmen != [] ]`.
    With the Kostenkalkulation outstanding on the company side, the list is
    non-empty, so the second atom is true and the remedy matches.
    """
    k2 = _kontext(
        fakten=[
            _faktum("vertrag.datum", date(2024, 1, 10)),
            _faktum("agb.fassung_datum", date(2025, 6, 1)),
            _faktum("vertrag.aenderungsvereinbarung_hinweis", True),
        ],
        dokumente=["vertrag", "agb"],
    )
    assert auswerten({"feld": "vertrag.aenderungsvereinbarung_hinweis",
                      "op": "!=", "wert": True}, k2) is False
    assert auswerten(_regel("P2", "NEIN_wenn"), k2) is False

    k_rb = _kontext(extra={
        "einordnung": label(Einordnung.UNKLAR),
        "fehlt_unternehmen": ["kostenkalkulation"],
    })
    assert auswerten(_rechtsbehelf_wenn("bestreiten_nachweise_verlangen"), k_rb) is True


def test_ein_datumsfeld_vergleicht_sich_mit_einem_datumsliteral():
    """§1 allows `==` / `!=` on any feld, `typ: datum` included — and §2
    declares `vertrag.datum` as `typ: "datum"`, which the extraction validator
    parses into a real date. A `wert` literal in a JSON rule, on the other
    hand, can only ever be a string, so the two sides have to be brought onto
    one type before they are compared.

    Derivation. A Stichtagsregel a Jurist could enter tomorrow —
    `{"feld": "vertrag.datum", "op": "==", "wert": "2024-01-10"}` — on a case
    whose contract is dated 10.01.2024:

      * == → TRUE
      * != → false

    Without the alignment `date(2024, 1, 10) == "2024-01-10"` is false, so such
    a rule never fires and its `!=` twin always does — silently, because the
    JSON looks right.
    """
    k = _kontext(fakten=[_faktum("vertrag.datum", date(2024, 1, 10))])

    assert auswerten({"feld": "vertrag.datum", "op": "==", "wert": "2024-01-10"}, k) is True
    assert auswerten({"feld": "vertrag.datum", "op": "!=", "wert": "2024-01-10"}, k) is False
    # the German spelling has to align just as well, and a different day must
    # still come out false
    assert auswerten({"feld": "vertrag.datum", "op": "==", "wert": "10.01.2024"}, k) is True
    assert auswerten({"feld": "vertrag.datum", "op": "==", "wert": "2024-01-11"}, k) is False


# --------------------------------------------------------------------------
# §1 — a broken rule has to fail loudly (14 §7, Akt 2)
# --------------------------------------------------------------------------


def test_ein_unbekannter_operator_faellt_auch_bei_unvollstaendiger_akte_auf():
    """§1 closes the operator set (OP ∈ == != < <= > >= in nicht_in), and
    `fallpruefer/schema.py` does not check operators — the whitelist in
    `regeln.py` is the only place a typo can be caught. 14 §7 (Akt 2): a broken
    rule file must fail loudly.

    Derivation. `=<` is not in the set, so the condition is not a condition and
    the engine owes an error — and it owes it independently of the Akte, since
    whether a rule is well-formed does not depend on which documents happen to
    be on file. The incomplete Akte is the case that matters: a comparison with
    an absent operand short-circuits to null before any operator is applied, so
    without the whitelist the typo produces a quiet null in exactly the cases
    the tool is built for.
    """
    kaputt = {"feld": "agb.nennt_anlass", "op": "=<", "wert": True}

    with pytest.raises(RegelFehler):
        auswerten(kaputt, _kontext())  # nothing extracted yet

    with pytest.raises(RegelFehler):
        auswerten(kaputt, _kontext(fakten=[_faktum("agb.nennt_anlass", True)]))


def test_ein_vergleich_mit_nur_einer_seite_ist_ein_fehler():
    """§1: a comparison C always has two sides (`feld`+`wert`, `feld`+`feld2`,
    `param`+`feld`, `prim`+`wert`). One side is not half a rule, it is no rule.

    Derivation. The Akt-2 gesture is a person editing the JSON; deleting the
    `wert` key leaves `{"feld": "vertrag.beitrag", "op": "=="}` behind. There
    is nothing to compare against, so there is no truth value to hand back —
    the engine has to say so, the way `schema.py` refuses a broken file.

    Returning null instead lets the Prüfpunkt fall through to `sonst` and the
    advisor sees a plausible result instead of the message that her edit is
    incomplete.
    """
    k = _kontext(fakten=[_faktum("vertrag.beitrag", 29.9)])

    with pytest.raises(RegelFehler):
        auswerten({"feld": "vertrag.beitrag", "op": "=="}, k)

    # the same shape with both sides present is a valid rule
    assert auswerten({"feld": "vertrag.beitrag", "op": "==", "wert": 29.9}, k) is True
