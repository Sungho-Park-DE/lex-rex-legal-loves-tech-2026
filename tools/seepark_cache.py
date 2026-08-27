"""Hand-authored `cache/llm/` entries for the Seepark fiction — both stages.

The counter-proof case (12 §5 Fälle 3 und 3b): the first stage is missing a
*page*, not a document, and the second stage ends in `wirksam`. Franz' own
reason for wanting it: „damit unser Werkzeug nicht wirkt, als finde es immer
einen Fehler."

The first stage deliberately records what a model would really return for the
incomplete Mitgliedsbedingungen — the fields that stand on page 1, and nothing
for the clause fields. Inventing a value there would be the exact failure the
quote verification exists to catch.

Run:  .venv/bin/python tools/seepark_cache.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools._cache_basis import melden, schreiben  # noqa: E402

from fallpruefer.konfig import WURZEL  # noqa: E402

FALL = WURZEL / "demo" / "faelle" / "seepark_seite_fehlt"

KLASSIFIKATION = {
    "D1": {
        "dokumenttyp": "erhoehungsschreiben",
        "konfidenz": 0.96,
        "begruendung": "Anschreiben eines Studios, das eine Beitragsanpassung zum 01.11.2026 ankündigt und die Kostenentwicklung darlegt.",
    },
    "D2": {
        "dokumenttyp": "agb",
        "konfidenz": 0.91,
        "begruendung": "Nummerierte Mitgliedsbedingungen; der Seitenfuß weist sie als Seite 1 von 3 aus, der Text bricht nach Ziffer 4 ab.",
    },
    "D3": {
        "dokumenttyp": "vertrag",
        "konfidenz": 0.95,
        "begruendung": "Mitgliedsvertrag mit Vertragsdatum, Tarif, Beitrag, Laufzeit und Unterschriftszeile.",
    },
    "D4": {
        "dokumenttyp": "agb",
        "konfidenz": 0.93,
        "begruendung": "Fortsetzung derselben Mitgliedsbedingungen, Seite 2 von 3, mit Ziffer 5 (Beiträge und Beitragsanpassung).",
    },
}

ANLASS = (
    "Anlass einer Anpassung des monatlichen Beitrags sind ausschließlich "
    "Veränderungen der Kosten, die dem Studio für den Betrieb entstehen, nämlich "
    "der Kosten für Energie, Personal, Miete der Studiofläche und Wartung der Geräte."
)
VORAUSSETZUNG = (
    "Voraussetzung einer Erhöhung ist, dass die nach ihrem Anteil an den "
    "Betriebskosten gewichtete Summe der in Ziffer 5.1 genannten Kosten seit dem "
    "Vertragsschluss oder seit der letzten Anpassung um mehr als 3 Prozent "
    "gestiegen ist"
)
UMFANG = (
    "Der Umfang der Erhöhung ist auf den Prozentsatz begrenzt, um den die in "
    "Ziffer 5.1 genannten Kosten gestiegen sind, höchstens jedoch auf 5 Prozent "
    "des zuletzt geschuldeten Beitrags."
)
SENKUNG = (
    "Sinken die in Ziffer 5.1 genannten Kosten, ist das Studio verpflichtet, den "
    "Beitrag nach denselben Maßstäben und im selben Umfang zu senken."
)
KUENDIGUNG = (
    "Das Mitglied kann den Vertrag bis zum Wirksamwerden der Anpassung zu diesem "
    "Zeitpunkt kündigen. Auf dieses Kündigungsrecht weist das Studio in der "
    "Mitteilung hin."
)
HINWEIS_IM_BRIEF = (
    "Wie in Ziffer 5.4 vereinbart, weisen wir Sie auf Ihr Kündigungsrecht hin"
)

EXTRAKTION = {
    "D1": [
        ("erhoehungsschreiben.datum", "2026-08-20", "Würzburg, 20.08.2026", 1),
        ("erhoehungsschreiben.form", "brief",
         "Seepark Aktiv GmbH · Randersackerer Straße 12 · 97072 Würzburg", 1),
        ("erhoehungsschreiben.wirksam_ab", "2026-11-01", "mit Wirkung zum 01.11.2026", 1),
        ("erhoehungsschreiben.alter_betrag", "32,00", "von 32,00 EUR auf 33,60 EUR", 1),
        ("erhoehungsschreiben.neuer_betrag", "33,60", "von 32,00 EUR auf 33,60 EUR", 1),
        ("erhoehungsschreiben.grundlage_genannt", "klausel",
         "nach Ziffer 5.2 unserer Mitgliedsbedingungen", 1),
        ("erhoehungsschreiben.klauselverweis", "Ziffer 5.2", "Ziffer 5.2", 1),
        ("erhoehungsschreiben.klauselzitat", UMFANG, UMFANG, 1),
        ("erhoehungsschreiben.zustimmungsmechanismus", "keiner", HINWEIS_IM_BRIEF, 1),
        ("erhoehungsschreiben.kuendigungshinweis", True, HINWEIS_IM_BRIEF, 1),
        ("erhoehungsschreiben.begruendung",
         "gestiegene Energie- und Personalkosten (5,0 Prozent)",
         "die Kosten für Energie und Personal, an die Ziffer 5.1 unserer Mitgliedsbedingungen die Beitragshöhe knüpft, sind seit Ihrem Vertragsschluss um 5,0 Prozent gestiegen", 1),
        ("erhoehungsschreiben.zitierte_fundstellen", [],
         "nach Ziffer 5.2 unserer Mitgliedsbedingungen", 1),
        ("erhoehungsschreiben.absender", "Seepark Aktiv GmbH",
         "Seepark Aktiv GmbH · Randersackerer Straße 12 · 97072 Würzburg", 1),
        ("erhoehungsschreiben.absender_adresse", "Randersackerer Straße 12, 97072 Würzburg",
         "Randersackerer Straße 12 · 97072 Würzburg", 1),
    ],
    # page 1 only — every clause field is absent because the clause is not on
    # this page. That absence is the case.
    "D2": [
        ("agb.fassung_datum", "2024-06-01", "Fassung vom 01.06.2024", 1),
        ("agb.leistungsaenderungsrecht", False,
         "3.1 Das Studio hält die in der Studiobeschreibung genannten Geräte, Kurse und den Wellnessbereich in dem dort beschriebenen Umfang bereit.", 1),
    ],
    "D3": [
        ("vertrag.datum", "2025-03-15", "Vertragsdatum: 15.03.2025", 1),
        ("vertrag.laufzeit_monate", 24, "Laufzeit: 24 Monate ab Vertragsbeginn.", 1),
        ("vertrag.beitrag", "32,00", "Monatlicher Beitrag: 32,00 EUR", 1),
        ("vertrag.agb_einbezogen_hinweis", True,
         "Die Mitgliedsbedingungen in der Fassung vom 01.06.2024 habe ich erhalten und erkenne sie an.", 1),
    ],
    "D4": [
        ("agb.fassung_datum", "2024-06-01", "Fassung vom 01.06.2024", 1),
        ("agb.preisklausel_text", UMFANG, UMFANG, 1),
        ("agb.preisklausel_ziffer", "5.2", "5.2 Voraussetzung einer Erhöhung ist", 1),
        ("agb.klausel_ueberschrift", "Beiträge", "5. Beiträge und Beitragsanpassung", 1),
        ("agb.nennt_anlass", True, ANLASS, 1),
        ("agb.nennt_voraussetzungen", True, VORAUSSETZUNG, 1),
        ("agb.nennt_umfang", True, UMFANG, 1),
        ("agb.kostenbezug", True, ANLASS, 1),
        ("agb.senkungspflicht", "pflicht", SENKUNG, 1),
        ("agb.kuendigungsrecht_bei_erhoehung", True, KUENDIGUNG, 1),
        # Paulina, Runde 3 (29 §3): keine Formvorgabe für den Widerspruch in
        # diesen AGB — Beleg ist die Klausel, in der sie stehen müsste.
        ("agb.widerspruch_formerfordernis", "keine_angabe", KUENDIGUNG, 1),
    ],
}

VORSCHLAEGE = {
    "vorschlaege": [
        {
            "fallgruppe_id": "preiserhoehung",
            "begruendung": "Das Studio erhöht den laufenden Monatsbeitrag einseitig.",
            "zitate": ["dass der Beitrag ab November von 32,00 auf 33,60 Euro steigt"],
        },
        {
            "fallgruppe_id": "klausel_check",
            "begruendung": "Im Kern steht die Wirksamkeit der Preisanpassungsklausel in den Bedingungen.",
            "zitate": [],
        },
    ]
}


if __name__ == "__main__":
    geschrieben = schreiben(FALL, KLASSIFIKATION, EXTRAKTION, VORSCHLAEGE,
                            dateien=["schreiben.md", "bedingungen_seite1.md", "vertrag.md"])
    geschrieben += schreiben(FALL, KLASSIFIKATION, EXTRAKTION, VORSCHLAEGE,
                             dateien=["schreiben.md", "bedingungen_seite1.md", "vertrag.md",
                                      "bedingungen_seite2_nachgereicht.md"])
    melden(geschrieben)
