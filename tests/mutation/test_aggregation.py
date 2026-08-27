"""Baum-Aggregation, Gates und INAKTIV — the half of contract §2 that no demo
case exercises.

Every expectation in this file is derived by hand from
`analysis/15_data_contract.md` §1 (rule grammar) / §2 (`aggregation`) and from
`schemas/preiserhoehung.json`; the derivation is written next to the assert.
Nothing here was read off an engine run.

What was uncovered, and why the existing suite cannot see it:

* **OR.** All seven Stufen of `schemas/preiserhoehung.json` declare `op: "AND"`,
  so the whole OR row of the §2 table has never been evaluated. The first
  Prüfschema with alternative Begründungswege (Franz' §§ 308/309-vor-307
  branches) would be the first to run it — in production. `_oder_schema()`
  below is that schema, built from the §1 grammar alone.
* **INAKTIV.** A gate that deactivates Prüfpunkte is exercised at Prüfpunkt
  level (`test_rung3.test_override_auf_das_kontrollfaehigkeits_gate_…`) but
  neither the node state above them nor the Prüfumfang box below them is
  compared anywhere.
* **Open gates over a JA root.** The downgrade rule is asserted only for a
  root that is already FEHLT; the case „alle tragenden Prüfpunkte JA, aber
  eine Vorfrage offen" — a Freispruch the program never checked — is not.
"""

from __future__ import annotations

import pytest

from fallpruefer import evaluator, pipeline as pl
from fallpruefer import schema as schema_modul
from fallpruefer.fall import Fall, Faktum
from fallpruefer.konfig import WURZEL
from fallpruefer.schema import Schema, schema_laden
from fallpruefer.vokabular import Einordnung, Zustand

AKTIVPARK = WURZEL / "demo" / "faelle" / "sauber_aktivpark"


# --------------------------------------------------------------------------
# OR aggregation — contract §2:
#   "OR": "JA wenn ein aktives Kind JA; sonst WERTUNG wenn eines WERTUNG;
#          sonst FEHLT wenn eines FEHLT; sonst NEIN."
# --------------------------------------------------------------------------


def _oder_schema(root_op: str) -> Schema:
    """A Prüfschema whose Stufen are OR nodes — alternative Begründungswege.

    Four Prüfpunkte, one per Zustand, driven by three `gespraech.*` facts and
    one that is deliberately never supplied. Each is written in the §1 grammar
    and reaches its state through the fixed branch order
    `FEHLT_wenn → NEIN_wenn → WERTUNG_wenn → JA_wenn → sonst`:

      PJA     no branch, no Pflichteingabe          → `sonst: JA`
      PNEIN   NEIN_wenn: gespraech.nein == true     → NEIN   (fact set true)
      PWERT   WERTUNG_wenn: gespraech.wertung == t. → WERTUNG(fact set true)
      PFEHLT  FEHLT_wenn: {"fehlt": <never set>}    → FEHLT

    The pairs under the OR nodes then cover every rung of the §2 precedence
    ladder. All four are `tragend`, which is what `aggregation.nur_rolle` says
    counts, so none of them is skipped for its role.
    """
    daten = {
        "fallgruppe_id": "mutation_oder",
        "name": "OR-Aggregation (Testschema, kein Rechtsinhalt)",
        "stufe": "C",
        "version": "0.0.1",
        "stand": "2026-08-23",
        "aggregation": {"nur_rolle": ["tragend"]},
        "pruefpunkte": [
            {"id": "PJA", "rolle": "tragend", "typ": "fakt",
             "proposition": "Weg A trägt.",
             "regel": {"sonst": "JA"}},
            {"id": "PNEIN", "rolle": "tragend", "typ": "fakt",
             "proposition": "Weg B trägt.",
             "regel": {"NEIN_wenn": {"feld": "gespraech.nein", "op": "==", "wert": True},
                       "sonst": "JA"}},
            {"id": "PWERT", "rolle": "tragend", "typ": "fakt",
             "proposition": "Weg C trägt.",
             "regel": {"WERTUNG_wenn": {"feld": "gespraech.wertung", "op": "==", "wert": True},
                       "sonst": "JA"}},
            {"id": "PFEHLT", "rolle": "tragend", "typ": "fakt",
             "proposition": "Weg D trägt.",
             "regel": {"FEHLT_wenn": {"fehlt": "gespraech.nie_geliefert"},
                       "sonst": "JA"}},
        ],
        "baum": {
            "id": "root", "op": root_op, "titel": "Trägt einer der Wege?",
            "kinder": [
                {"id": "O_JA_NEIN", "op": "OR", "titel": "JA neben NEIN",
                 "kinder": ["PJA", "PNEIN"]},
                {"id": "O_WERT_NEIN", "op": "OR", "titel": "WERTUNG neben NEIN",
                 "kinder": ["PWERT", "PNEIN"]},
                {"id": "O_FEHLT_NEIN", "op": "OR", "titel": "FEHLT neben NEIN",
                 "kinder": ["PFEHLT", "PNEIN"]},
                {"id": "O_NUR_NEIN", "op": "OR", "titel": "nur NEIN",
                 "kinder": ["PNEIN"]},
                {"id": "O_JA_WERT", "op": "OR", "titel": "JA neben WERTUNG",
                 "kinder": ["PJA", "PWERT"]},
                {"id": "O_WERT_FEHLT", "op": "OR", "titel": "WERTUNG neben FEHLT",
                 "kinder": ["PWERT", "PFEHLT"]},
            ],
        },
    }
    s = Schema.model_validate(daten)
    # the same load-time check a Jurist-Edit passes — this is a schema the
    # engine would really accept, not a hand-built object that bypasses it
    schema_modul.pruefen(s)
    return s


def _oder_fall(case_id: str) -> Fall:
    fall = Fall.model_validate({"case_id": case_id,
                                "schema": {"fallgruppe_id": "mutation_oder"}})
    fall.fakten = [
        Faktum(feld_id="gespraech.nein", wert=True),
        Faktum(feld_id="gespraech.wertung", wert=True),
        # gespraech.nie_geliefert is intentionally absent → PFEHLT fires FEHLT
    ]
    return fall


def test_ein_OR_knoten_nimmt_den_besten_weg_nicht_den_schlechtesten():
    """§2 `aggregation.OR`, read as a precedence ladder JA > WERTUNG > FEHLT >
    NEIN, applied to the six pairs of `_oder_schema`:

      O_JA_NEIN     aktive [JA, NEIN]      → ein Kind JA            → JA
      O_WERT_NEIN   aktive [WERTUNG, NEIN] → kein JA, ein WERTUNG   → WERTUNG
      O_FEHLT_NEIN  aktive [FEHLT, NEIN]   → kein JA/WERTUNG, FEHLT → FEHLT
      O_NUR_NEIN    aktive [NEIN]          → sonst                  → NEIN
      O_JA_WERT     aktive [JA, WERTUNG]   → ein Kind JA            → JA
      O_WERT_FEHLT  aktive [WERTUNG, FEHLT]→ kein JA, ein WERTUNG   → WERTUNG

    An OR node is the schema saying „einer dieser Wege genügt". Aggregating it
    with AND semantics turns every alternative into a further requirement, and
    the four states are exactly where that shows.
    """
    pruefung = evaluator.pruefen(_oder_fall("F-MUT-OR-1"), _oder_schema("AND"),
                                 trigger="mutation")

    assert {pid: pruefung.ergebnis(pid).zustand for pid in
            ("PJA", "PNEIN", "PWERT", "PFEHLT")} == {
        "PJA": Zustand.JA, "PNEIN": Zustand.NEIN,
        "PWERT": Zustand.WERTUNG, "PFEHLT": Zustand.FEHLT,
    }, "die vier Prüfpunkte erreichen ihre Zustände nicht wie in §1 hergeleitet"

    assert {k: v for k, v in pruefung.baum_zustaende.items() if k.startswith("O_")} == {
        "O_JA_NEIN": Zustand.JA,
        "O_WERT_NEIN": Zustand.WERTUNG,
        "O_FEHLT_NEIN": Zustand.FEHLT,
        "O_NUR_NEIN": Zustand.NEIN,
        "O_JA_WERT": Zustand.JA,
        "O_WERT_FEHLT": Zustand.WERTUNG,
    }


def test_ein_tragender_OR_pfad_der_haelt_macht_den_fall_nicht_unwirksam():
    """The same schema with `root: op OR`. Its active children are the six node
    states above — [JA, WERTUNG, FEHLT, NEIN, JA, WERTUNG] — so §2 OR gives
    root == JA („ein aktives Kind JA"), and §2 `einordnung` gives „wirksam"
    for root == JA. No gate exists in this schema, so nothing downgrades it.

    With AND semantics on the OR node the single NEIN child would decide the
    whole case and the verdict would read „wahrscheinlich unwirksam" — the tool
    telling a Verbraucherin her provider is in the wrong because *one* of
    several sufficient justifications does not hold.
    """
    pruefung = evaluator.pruefen(_oder_fall("F-MUT-OR-2"), _oder_schema("OR"),
                                 trigger="mutation")

    assert pruefung.baum_zustaende["root"] == Zustand.JA
    assert pruefung.einordnung_code == Einordnung.WIRKSAM
    assert pruefung.einordnung == "wirksam"


# --------------------------------------------------------------------------
# INAKTIV — contract §2 `aggregation.AND` („INAKTIV-Kinder werden ignoriert;
# ein Knoten ohne aktive Kinder ist INAKTIV") and `aggregation.gates`
# („gate NEIN mit deaktiviert → die genannten Prüfpunkte erhalten zustand
# INAKTIV (Prüfumfang: „nicht anwendbar")").
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def abgeschaltete_inhaltskontrolle():
    """AktivPark — the `wirksam` case (`tests/golden/sauber_aktivpark.json`,
    all tragenden Prüfpunkte JA) — with Gate 3 answering the Kontrollfähigkeits-
    Vorfrage P5 with NEIN.

    `schemas/preiserhoehung.json` P5.bei_NEIN = {"deaktiviert":
    ["P6","P7","P8","P9"]}, so those four go INAKTIV and Stufe 3 has run on
    nothing at all.
    """
    fall = pl.fall_aus_verzeichnis(AKTIVPARK, "F-MUT-INAKTIV")
    pl.gate3_override(fall, "P5", "NEIN",
                      grund="Die Klausel regelt den ursprünglichen Preis.")
    return fall.aktuelle_pruefung()


def test_eine_abgeschaltete_stufe_gilt_nicht_als_erfuellt(abgeschaltete_inhaltskontrolle):
    """S3's `kinder` are ["P8","P8c","P9","P5","P6","P7"]. P5 is `rolle: gate`
    and `aggregation.nur_rolle` is ["tragend"], so it never reaches the node at
    all; P6–P9 are the four the gate just switched off. §2 AND: „INAKTIV-Kinder
    werden ignoriert" — so S3 must aggregate over what is left, and what is
    left since 24 Aug is exactly one point: **P8c**, § 309 Nr. 13 lit. b. It
    controls a *different* clause (the Widerspruchs-Formklausel, not the
    Preisklausel whose Kontrollfähigkeit P5 just denied), so P5 rightly does
    not switch it off. S3 == P8c's own state, and nothing else leaks in.

    Counting INAKTIV children instead of skipping them would make S3 aggregate
    [INAKTIV × 4, JA]: still JA here — which is why the second assertion pins
    that S3 *equals* P8c and does not merely happen to be JA. The „node without
    active children is INAKTIV" half of the rule is held by
    `test_einordnung.py` (root INAKTIV once every tragend point is off).
    """
    p = abgeschaltete_inhaltskontrolle
    assert [p.ergebnis(pid).zustand for pid in ("P6", "P7", "P8", "P9")] == \
        [Zustand.INAKTIV] * 4
    assert p.ergebnis("P8c").zustand != Zustand.INAKTIV, \
        "P5 (Kontrollfähigkeit der Preisklausel) darf die Formklausel nicht abschalten"
    assert p.baum_zustaende["S3"] == p.ergebnis("P8c").zustand


def test_der_pruefumfang_nennt_die_abgeschaltete_inhaltskontrolle(
        abgeschaltete_inhaltskontrolle):
    """§2 `aggregation.pruefumfang`: „alle WERTUNG/FEHLT/INAKTIV-Prüfpunkte mit
    pruefumfang_text oder wertungsfrage; immer sichtbar" — the box that answers
    „was wurde NICHT geprüft?".

    Derived per Prüfpunkt, in the file order of `schemas/preiserhoehung.json`
    (P0…P8, P8b, P9, P10, P11, P14, P12, P13), for AktivPark with P5 = NEIN.
    States from `tests/golden/sauber_aktivpark.json` plus the gate:

      P0  JA               → kein Kandidatenzustand
      P1–P4  JA            → dito
      P5  NEIN (override)  → NEIN ist kein Kandidatenzustand; ein gate, das
                             beantwortet ist, ist nicht „nicht geprüft"
      P6  INAKTIV + wertungsfrage („Reicht die Bestimmtheit…")   → drin
      P7  INAKTIV + wertungsfrage („Ist die Senkungsregel…")     → drin
      P8  INAKTIV + wertungsfrage („Verstößt die Laufzeit-…")    → drin
      P8b JA                                                     → raus
      P9  INAKTIV, ohne wertungsfrage/pruefumfang_text, aber mit
          inaktiv_grund (dem bei_NEIN-Text des Gates)            → drin
      P10 JA                                                     → raus
      P11 FEHLT + pruefumfang_text („NICHT geprüft: ob die Höhe…")→ drin
      P14 JA (gespraech.monate_erhoeht_gezahlt fehlt)            → raus
      P12 ableitung, nur_wenn verlangt einordnung == „wahrschein-
          lich unwirksam", die Einordnung ist „wirksam" → INAKTIV
          mit inaktiv_grund                                      → drin
      P13 strategie ohne regel → INAKTIV, aber ohne inaktiv_grund
          und ohne Text                                          → raus

    Dropping INAKTIV from the state list leaves exactly ['P11'] — the box then
    conceals the one thing the gate just did.
    """
    assert abgeschaltete_inhaltskontrolle.pruefumfang == \
        ["P6", "P7", "P8", "P9", "P11", "P12"]


# --------------------------------------------------------------------------
# Open gates — §2 `aggregation.gates` („Ein gate-Prüfpunkt trägt nie zur
# Einordnung bei") together with `einordnung.wirksam` („root == JA"), which
# 14 §3 reads as: a Vorfrage that is still open is not an answer.
# --------------------------------------------------------------------------


def _aktivpark_mit_neuer_entgeltposition(case_id: str):
    """AktivPark, but the Erhöhungsschreiben stützt sich auf eine neue
    Entgeltposition — the one value that makes P0's WERTUNG_wenn fire."""
    fall = pl.fall_aus_verzeichnis(AKTIVPARK, case_id)
    for f in fall.fakten:
        if f.feld_id == "erhoehungsschreiben.grundlage_genannt":
            f.wert = "neue_entgeltposition"
    return evaluator.pruefen(fall, schema_laden("preiserhoehung"), trigger="mutation")


def test_ein_gate_im_zustand_WERTUNG_ist_eine_offene_vorfrage():
    """P0's regel (schemas/preiserhoehung.json): NEIN_wenn needs
    grundlage_genannt == „zustimmung_aktiv" *and* gespraech.zustimmung_aktiv_
    belegt == true, WERTUNG_wenn needs grundlage_genannt == „neue_entgelt-
    position". Setting that one field therefore moves P0 — and only P0 — to
    WERTUNG; P1 is the only other Prüfpunkt reading the field and its NEIN_wenn
    tests against „keine", so P1 stays JA and the root stays JA.

    §1 is three-valued on purpose: a branch fires only on `true`, and „wir
    wissen es nicht" must not collapse into „kein Problem". A gate is where
    that matters most — it asks whether the Prüfschema applies at all. So an
    unanswered gate has to be collected as an open Vorfrage exactly like a
    FEHLT one, and §2 `einordnung` then renders it the way §0 spells it out:
    „unklar – es fehlt: Bewertung durch die Beraterin zu <wertungsfrage>".

    Treating only FEHLT as open leaves this case at „wirksam" — the false safe
    answer the golden runner counts separately, handed out for a question the
    program itself flagged as needing a Beraterin.
    """
    pruefung = _aktivpark_mit_neuer_entgeltposition("F-MUT-GATE-WERTUNG")

    assert pruefung.ergebnis("P0").zustand == Zustand.WERTUNG
    assert pruefung.baum_zustaende["root"] == Zustand.JA, \
        "die tragenden Prüfpunkte bleiben unberührt — sonst prüft der Test etwas anderes"
    assert pruefung.einordnung_code == Einordnung.UNKLAR
    assert pruefung.einordnung == (
        "unklar – es fehlt: Bewertung durch die Beraterin zu "
        "„Ist die neue Entgeltposition (z. B. Servicepauschale) eine "
        "Preiserhöhung im Sinne dieses Schemas oder eine neue Leistung?“"
    )


def test_eine_offene_vorfrage_verhindert_auch_den_freispruch():
    """The mirror image of `test_rung3.test_ein_offenes_gate_traegt_kein_hartes_
    urteil`, which only covers a root that is already FEHLT.

    Here every tragender Prüfpunkt is JA (AktivPark, `tests/golden/
    sauber_aktivpark.json`) and the Kontrollfähigkeits-Vorfrage P5 is set to
    FEHLT through Gate 3 — „ohne den Klauseltext kann ich das nicht sagen".
    P5.bei_NEIN fires only on NEIN, so P6–P9 keep their JA and the root stays
    JA.

    §2 says „wirksam": root == JA. It says so for a tree whose Vorfragen are
    answered — P5 NEIN would have removed the whole Inhaltskontrolle from the
    case (bei_NEIN.deaktiviert), so as long as P5 is open, nobody knows what
    those four JA are worth. Downgrading only a NEIN root and letting a JA root
    through hands the Verbraucherin a Freispruch for a Prüfung that never ran —
    the direction of error 14 §3 exists to forbid.
    """
    fall = pl.fall_aus_verzeichnis(AKTIVPARK, "F-MUT-GATE-FEHLT")
    assert fall.aktuelle_pruefung().einordnung == "wirksam", \
        "Ausgangslage laut tests/golden/sauber_aktivpark.json"

    pl.gate3_override(fall, "P5", "FEHLT",
                      grund="Ohne den Klauseltext ist die Kontrollfähigkeit offen.")
    p = fall.aktuelle_pruefung()

    assert p.ergebnis("P5").zustand == Zustand.FEHLT
    assert [p.ergebnis(pid).zustand for pid in ("P6", "P7", "P8", "P9")] == \
        [Zustand.JA] * 4, "die Deaktivierung hängt an NEIN, nicht an FEHLT"
    assert p.baum_zustaende["root"] == Zustand.JA
    assert p.einordnung_code == Einordnung.UNKLAR
    assert p.einordnung.startswith("unklar – es fehlt:")
