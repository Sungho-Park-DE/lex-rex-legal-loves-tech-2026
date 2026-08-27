"""Hand-authored `cache/llm/` entries for the Nordlicht fiction — both stages.

This is the flip case (12 §5 Fälle 2 und 2b): the first stage has nothing but
the Erhöhungsschreiben, the second adds the AGB and the Mitgliedsvertrag the
Nachforderung asked for. `propose_fallgruppe` is recorded twice because its
input carries the list of document types, which is exactly what changes
between the two stages; the per-document recordings are keyed on the document
text alone and are therefore shared.

Run:  .venv/bin/python tools/nordlicht_cache.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools._cache_basis import melden, schreiben  # noqa: E402

from fallpruefer.konfig import WURZEL  # noqa: E402

FALL = WURZEL / "demo" / "faelle" / "nordlicht_agb_fehlen"

KLASSIFIKATION = {
    "D1": {
        "dokumenttyp": "erhoehungsschreiben",
        "konfidenz": 0.95,
        "begruendung": "Anschreiben eines Sportclubs, das eine Beitragsanpassung zum 01.10.2026 ankündigt und sich auf eine AGB-Ziffer beruft.",
    },
    "D2": {
        "dokumenttyp": "agb",
        "konfidenz": 0.96,
        "begruendung": "Nummerierte Allgemeine Geschäftsbedingungen mit Geltungsbereich, Leistungen, Beiträgen und Laufzeit.",
    },
    "D3": {
        "dokumenttyp": "vertrag",
        "konfidenz": 0.94,
        "begruendung": "Mitgliedsvertrag mit Vertragsdatum, Tarif, Beitrag, Mindestlaufzeit und Unterschriftszeile.",
    },
}

KLAUSEL = "Wir behalten uns vor, die Beiträge anzupassen."
ZIFFER_72 = (
    "7.2 Wir behalten uns vor, die Beiträge anzupassen. Die Anpassung wird dem "
    "Mitglied mitgeteilt."
)
# The span an extractor would have to look at to say „kein Kündigungshinweis":
# the closing block of the letter, where one would stand if there were one.
SCHLUSS = (
    "Der Einzug erfolgt wie gewohnt zum Monatsersten. Ihre Mitgliedschaft läuft "
    "im Übrigen unverändert weiter."
)

EXTRAKTION = {
    "D1": [
        ("erhoehungsschreiben.datum", "2026-08-05", "Augsburg, 05.08.2026", 1),
        ("erhoehungsschreiben.form", "brief",
         "Nordlicht Sportclub GmbH · Schießgrabenstraße 9 · 86152 Augsburg", 1),
        ("erhoehungsschreiben.wirksam_ab", "2026-10-01", "ab dem 01.10.2026", 1),
        ("erhoehungsschreiben.alter_betrag", "27,50",
         "statt bisher 27,50 EUR nunmehr 31,90 EUR", 1),
        ("erhoehungsschreiben.neuer_betrag", "31,90",
         "statt bisher 27,50 EUR nunmehr 31,90 EUR", 1),
        ("erhoehungsschreiben.grundlage_genannt", "klausel",
         "Nach Ziffer 7.2 unserer Allgemeinen Geschäftsbedingungen", 1),
        ("erhoehungsschreiben.klauselverweis", "Ziffer 7.2", "Ziffer 7.2", 1),
        ("erhoehungsschreiben.klauselzitat", KLAUSEL, KLAUSEL, 1),
        ("erhoehungsschreiben.zustimmungsmechanismus", "keiner", SCHLUSS, 1),
        ("erhoehungsschreiben.kuendigungshinweis", False, SCHLUSS, 1),
        ("erhoehungsschreiben.begruendung", "gestiegene Energiekosten",
         "Energiekosten für unsere Trainingsflächen und die Sauna sind im vergangenen Jahr deutlich gestiegen", 1),
        ("erhoehungsschreiben.zitierte_fundstellen", [],
         "Nach Ziffer 7.2 unserer Allgemeinen Geschäftsbedingungen", 1),
        ("erhoehungsschreiben.absender", "Nordlicht Sportclub GmbH",
         "Nordlicht Sportclub GmbH · Schießgrabenstraße 9 · 86152 Augsburg", 1),
        ("erhoehungsschreiben.absender_adresse", "Schießgrabenstraße 9, 86152 Augsburg",
         "Schießgrabenstraße 9 · 86152 Augsburg", 1),
    ],
    "D2": [
        ("agb.fassung_datum", "2023-01-15", "Fassung vom 15.01.2023", 1),
        ("agb.preisklausel_text", KLAUSEL, KLAUSEL, 2),
        ("agb.preisklausel_ziffer", "7.2", "7.2 Wir behalten uns vor", 2),
        ("agb.klausel_ueberschrift", "Beiträge", "7. Beiträge", 2),
        ("agb.nennt_anlass", False, ZIFFER_72, 2),
        ("agb.nennt_voraussetzungen", False, ZIFFER_72, 2),
        ("agb.nennt_umfang", False, ZIFFER_72, 2),
        ("agb.kostenbezug", False, ZIFFER_72, 2),
        ("agb.senkungspflicht", "keine", ZIFFER_72, 2),
        ("agb.kuendigungsrecht_bei_erhoehung", False, ZIFFER_72, 2),
        # Paulina, Runde 3 (29 §3): keine Formvorgabe für den Widerspruch in
        # diesen AGB — Beleg ist die Klausel, in der sie stehen müsste.
        ("agb.widerspruch_formerfordernis", "keine_angabe", ZIFFER_72, 2),
        ("agb.leistungsaenderungsrecht", False,
         "3.1 Der Club stellt die in der Clubbeschreibung genannten Trainingsflächen, Kurse und den Saunabereich zur Verfügung.", 1),
    ],
    "D3": [
        ("vertrag.datum", "2025-11-03", "Vertragsdatum: 03.11.2025", 1),
        ("vertrag.laufzeit_monate", 12, "Mindestlaufzeit: 12 Monate", 1),
        ("vertrag.verlaengerung_text",
         "Der Vertrag verlängert sich um jeweils 12 Monate, wenn er nicht 3 Monate vor Ablauf gekündigt wird.",
         "Verlängerung: Der Vertrag verlängert sich um jeweils 12 Monate, wenn er nicht 3 Monate vor Ablauf gekündigt wird.", 1),
        ("vertrag.beitrag", "27,50", "Monatlicher Beitrag: 27,50 EUR", 1),
        ("vertrag.agb_einbezogen_hinweis", True,
         "Die Allgemeinen Geschäftsbedingungen in der Fassung vom 15.01.2023 habe ich erhalten und erkenne sie an.", 1),
    ],
}

VORSCHLAEGE = {
    "vorschlaege": [
        {
            "fallgruppe_id": "preiserhoehung",
            "begruendung": "Der Club erhöht den laufenden Monatsbeitrag einseitig.",
            "zitate": ["dass mein Beitrag ab Oktober von 27,50 auf 31,90 Euro steigt"],
        },
        {
            "fallgruppe_id": "klausel_check",
            "begruendung": "Im Kern steht die Wirksamkeit der Preisanpassungsklausel in den AGB.",
            "zitate": [],
        },
    ]
}


if __name__ == "__main__":
    geschrieben = schreiben(FALL, KLASSIFIKATION, EXTRAKTION, VORSCHLAEGE,
                            dateien=["schreiben.md"])
    geschrieben += schreiben(FALL, KLASSIFIKATION, EXTRAKTION, VORSCHLAEGE,
                             dateien=["schreiben.md", "agb_nachgereicht.md",
                                      "vertrag_nachgereicht.md"])
    melden(geschrieben)
