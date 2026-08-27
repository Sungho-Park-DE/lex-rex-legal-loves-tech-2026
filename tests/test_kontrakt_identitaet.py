"""Two things that were asserted by nothing.

`test_rung1.py::test_schema_laedt_verbatim_aus_dem_contract` promises in its
name that the schema file is the `15` §2 block verbatim — and then only checks
that the loaded schema matches the file it was loaded from, which is trivially
true. The actual identity, on which Act 2's „das Papier und der Code sind
dieselbe Datei" (14 §7) rests, was held by nothing but discipline.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from fallpruefer.konfig import WURZEL
from fallpruefer.regeln import auswerten
from fallpruefer.schema import schema_laden

KONTRAKT = WURZEL / "analysis" / "15_data_contract.md"
SCHEMA = WURZEL / "schemas" / "preiserhoehung.json"


def _block_aus_dem_kontrakt() -> str:
    zeilen = KONTRAKT.read_text(encoding="utf-8").split("\n")
    start = next(i for i, z in enumerate(zeilen) if z.startswith("## 2. Schema file"))
    auf = next(i for i in range(start, len(zeilen)) if zeilen[i].startswith("```json"))
    zu = next(i for i in range(auf + 1, len(zeilen)) if zeilen[i].strip() == "```")
    return "\n".join(zeilen[auf + 1 : zu]) + "\n"


def test_das_papier_und_der_code_sind_dieselbe_datei():
    """`schemas/preiserhoehung.json` must be the `15` §2 JSON block, byte for byte.

    Not „equivalent JSON" — byte for byte. A jurist reads the contract and edits
    the file; if the two drift, one of the two is lying, and the Akt-2 beat is
    built on them being the same text.
    """
    assert _block_aus_dem_kontrakt() == SCHEMA.read_text(encoding="utf-8"), (
        "schemas/preiserhoehung.json und der JSON-Block in 15 §2 sind "
        "auseinandergelaufen — beide im selben Commit ändern."
    )


# --------------------------------------------------------------------------
# P3 — the Preisgarantie is measured from the Vertragsbeginn (V-N1)
# --------------------------------------------------------------------------


def _regel_p3():
    p3 = next(p for p in schema_laden("preiserhoehung").pruefpunkte if p.id == "P3")
    return p3.regel["NEIN_wenn"]


def _k(**fakten):
    from tests.mutation.test_regeln import _faktum, _kontext

    return _kontext(fakten=[_faktum(a, b) for a, b in fakten.items()])


@pytest.mark.parametrize(
    "name,fakten,erwartet",
    [
        # Franz' Fall 4 shape (24 §3.2): signed 14.11.2025, contract STARTS
        # 01.12.2025, twelve months guaranteed. The guarantee therefore runs to
        # 30.11.2026. An increase effective 15.11.2026 is inside it.
        #   from Vertragsbeginn: 11 whole months < 12  -> inside  -> NEIN
        #   from Vertragsdatum:  12 whole months, not < 12 -> outside -> no NEIN
        # The old rule measured from vertrag.datum and got the second answer.
        ("ab Vertragsbeginn, Erhöhung innerhalb der Garantie",
         dict(**{"vertrag.datum": date(2025, 11, 14),
                 "vertrag.vertragsbeginn": date(2025, 12, 1),
                 "vertrag.preisgarantie_monate": 12,
                 "erhoehungsschreiben.wirksam_ab": date(2026, 11, 15)}), True),
        # Same case with no Vertragsbeginn extracted: the fallback to
        # vertrag.datum must still work, and gives the other answer honestly.
        ("ohne Vertragsbeginn faellt die Messung auf vertrag.datum zurueck",
         dict(**{"vertrag.datum": date(2025, 11, 14),
                 "vertrag.preisgarantie_monate": 12,
                 "erhoehungsschreiben.wirksam_ab": date(2026, 11, 15)}), False),
        # 24 §3.1: the document names an END DATE, not a month count.
        ("nur ein Enddatum, Erhoehung davor",
         dict(**{"vertrag.datum": date(2025, 1, 1),
                 "vertrag.preisgarantie_bis": date(2026, 11, 30),
                 "erhoehungsschreiben.wirksam_ab": date(2026, 6, 1)}), True),
        ("nur ein Enddatum, Erhoehung danach",
         dict(**{"vertrag.datum": date(2025, 1, 1),
                 "vertrag.preisgarantie_bis": date(2026, 11, 30),
                 "erhoehungsschreiben.wirksam_ab": date(2026, 12, 1)}), False),
        # Regression guard. The first draft of this rule left the unused arm at
        # null, so `eine[false, null]` was null and a clean „the guarantee had
        # expired" turned into „unknown" — P3 would have gone to FEHLT instead
        # of JA. Caught by tests/mutation/test_regeln.py, pinned here.
        ("Garantie exakt abgelaufen ist FALSE, nicht null",
         dict(**{"vertrag.datum": date(2025, 1, 1),
                 "vertrag.preisgarantie_monate": 12,
                 "erhoehungsschreiben.wirksam_ab": date(2026, 1, 1)}), False),
        ("gar keine Garantie ist FALSE, nicht null",
         dict(**{"vertrag.datum": date(2025, 1, 1),
                 "erhoehungsschreiben.wirksam_ab": date(2026, 1, 1)}), False),
    ],
)
def test_P3_misst_ab_vertragsbeginn(name, fakten, erwartet):
    assert auswerten(_regel_p3(), _k(**fakten)) is erwartet, name


def test_die_beiden_neuen_felder_stehen_im_unterlagen_soll():
    """A rule that reads a field the Soll does not declare can never be filled:
    extraction only ever asks for the document's own field list."""
    roh = json.loads(SCHEMA.read_text(encoding="utf-8"))
    vertrag = next(d for d in roh["dokumenten_soll"]["dokumente"]
                   if d["dokumenttyp"] == "vertrag")
    ids = {f["feld_id"] for f in vertrag["felder"]}
    assert {"vertrag.vertragsbeginn", "vertrag.preisgarantie_bis"} <= ids
