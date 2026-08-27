"""Hand-authored `cache/llm/` entries for the „sauberer Fall" fiction.

This is the case that has to come out `wirksam` (12 §5 Fall 5, 14 §7 „Paar in
jedem Zweig"). The extraction below is therefore the *demanding* one: every
criterion P6 and P7 test has to be answered `true` **and** carry a span that
really stands in the AGB, because both rules require `verifiziert` before they
may say JA. A model that only guessed „sieht sauber aus" would land on WERTUNG,
not on `wirksam` — which is the correct behaviour and the reason the quotes
below are the whole point.

Run:  .venv/bin/python tools/sauber_aktivpark_cache.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools._cache_basis import melden, schreiben  # noqa: E402

from fallpruefer.konfig import WURZEL  # noqa: E402

FALL = WURZEL / "demo" / "faelle" / "sauber_aktivpark"

KLASSIFIKATION = {
    "D1": {
        "dokumenttyp": "erhoehungsschreiben",
        "konfidenz": 0.96,
        "begruendung": "Anschreiben eines Fitnessstudios, das eine Beitragsanpassung zum 01.10.2026 ankündigt und die Kostenentwicklung darlegt.",
    },
    "D2": {
        "dokumenttyp": "agb",
        "konfidenz": 0.97,
        "begruendung": "Nummerierte Allgemeine Geschäftsbedingungen mit Geltungsbereich, Beiträgen, Beitragsanpassung und Laufzeit.",
    },
    "D3": {
        "dokumenttyp": "vertrag",
        "konfidenz": 0.95,
        "begruendung": "Mitgliedsvertrag mit Vertragsdatum, Tarif, Beitrag, Laufzeit und Unterschriftszeile.",
    },
}

ANLASS = (
    "Anlass einer Anpassung des monatlichen Beitrags sind ausschließlich "
    "Veränderungen der Kosten, die dem Studio für den Betrieb entstehen, nämlich "
    "der Kosten für Energie, Personal, Miete der Studiofläche und Wartung der "
    "Trainingsgeräte."
)
VORAUSSETZUNG = (
    "Voraussetzung einer Erhöhung ist, dass die nach ihrem Anteil an den "
    "Betriebskosten gewichtete Summe der in Ziffer 6.1 genannten Kosten seit dem "
    "Vertragsschluss oder seit der letzten Anpassung um mehr als 3 Prozent "
    "gestiegen ist."
)
UMFANG = (
    "Der Umfang der Erhöhung ist auf den Prozentsatz begrenzt, um den die in "
    "Ziffer 6.1 genannten Kosten gestiegen sind, höchstens jedoch auf 5 Prozent "
    "des zuletzt geschuldeten Beitrags."
)
SENKUNG = (
    "Sinken die in Ziffer 6.1 genannten Kosten, ist das Studio verpflichtet, den "
    "Beitrag nach denselben Maßstäben und im selben Umfang zu senken."
)
KUENDIGUNG = (
    "Das Mitglied kann den Vertrag bis zum Wirksamwerden der Anpassung zu diesem "
    "Zeitpunkt kündigen. Auf dieses Kündigungsrecht weist das Studio in der "
    "Mitteilung hin."
)
HINWEIS_IM_BRIEF = (
    "Wie in Ziffer 6.5 vereinbart, weisen wir Sie ausdrücklich auf Ihr "
    "Kündigungsrecht hin"
)

EXTRAKTION = {
    "D1": [
        ("erhoehungsschreiben.datum", "2026-07-15", "Regensburg, 15.07.2026", 1),
        ("erhoehungsschreiben.form", "brief",
         "AktivPark Fitness GmbH · Donaustraße 27 · 93055 Regensburg", 1),
        ("erhoehungsschreiben.wirksam_ab", "2026-10-01", "mit Wirkung zum 01.10.2026", 1),
        ("erhoehungsschreiben.alter_betrag", "34,90", "von 34,90 EUR auf 36,35 EUR", 1),
        ("erhoehungsschreiben.neuer_betrag", "36,35", "von 34,90 EUR auf 36,35 EUR", 1),
        ("erhoehungsschreiben.grundlage_genannt", "klausel",
         "Auf Grundlage von Ziffer 6.3 unserer Allgemeinen Geschäftsbedingungen", 1),
        ("erhoehungsschreiben.klauselverweis", "Ziffer 6.3", "Ziffer 6.3", 1),
        ("erhoehungsschreiben.klauselzitat", UMFANG, UMFANG, 1),
        # „keiner": the letter asks for nothing and reads nothing into silence —
        # it announces a unilateral adjustment and offers a way out. The span
        # that carries that is the Kündigungshinweis, not an absence.
        ("erhoehungsschreiben.zustimmungsmechanismus", "keiner", HINWEIS_IM_BRIEF, 1),
        ("erhoehungsschreiben.kuendigungshinweis", True, HINWEIS_IM_BRIEF, 1),
        ("erhoehungsschreiben.begruendung",
         "gewichtete Steigerung der Betriebskosten um 4,2 Prozent",
         "Nach ihrem Anteil an unseren Betriebskosten gewichtet ergibt das eine Steigerung von 4,2 Prozent.", 1),
        ("erhoehungsschreiben.zitierte_fundstellen", [],
         "Auf Grundlage von Ziffer 6.3 unserer Allgemeinen Geschäftsbedingungen", 1),
        ("erhoehungsschreiben.absender", "AktivPark Fitness GmbH",
         "AktivPark Fitness GmbH · Donaustraße 27 · 93055 Regensburg", 1),
        ("erhoehungsschreiben.absender_adresse", "Donaustraße 27, 93055 Regensburg",
         "Donaustraße 27 · 93055 Regensburg", 1),
    ],
    "D2": [
        ("agb.fassung_datum", "2024-11-01", "Fassung vom 01.11.2024", 1),
        ("agb.preisklausel_text", UMFANG, UMFANG, 2),
        ("agb.preisklausel_ziffer", "6.3", "6.3 Der Umfang der Erhöhung", 2),
        ("agb.klausel_ueberschrift", "Beitragsanpassung", "6. Beitragsanpassung", 2),
        ("agb.nennt_anlass", True, ANLASS, 2),
        ("agb.nennt_voraussetzungen", True, VORAUSSETZUNG, 2),
        ("agb.nennt_umfang", True, UMFANG, 2),
        ("agb.kostenbezug", True, ANLASS, 2),
        ("agb.senkungspflicht", "pflicht", SENKUNG, 2),
        ("agb.kuendigungsrecht_bei_erhoehung", True, KUENDIGUNG, 2),
        # Paulina, Runde 3 (29 §3): keine Formvorgabe für den Widerspruch in
        # diesen AGB — Beleg ist die Klausel, in der sie stehen müsste.
        ("agb.widerspruch_formerfordernis", "keine_angabe", KUENDIGUNG, 2),
        # no Erklärungsfiktion anywhere in these AGB — the span that was looked
        # at is the adjustment clause itself
        ("agb.leistungsaenderungsrecht", False,
         "3.1 Das Studio hält die in der Studiobeschreibung genannten Geräte und Kurse in dem dort beschriebenen Umfang bereit.", 1),
    ],
    "D3": [
        ("vertrag.datum", "2025-03-01", "Vertragsdatum: 01.03.2025", 1),
        ("vertrag.laufzeit_monate", 24, "Laufzeit: 24 Monate ab Vertragsbeginn.", 1),
        ("vertrag.beitrag", "34,90", "Monatlicher Beitrag: 34,90 EUR", 1),
        ("vertrag.agb_einbezogen_hinweis", True,
         "Die Allgemeinen Geschäftsbedingungen in der Fassung vom 01.11.2024 habe ich erhalten und erkenne sie an.", 1),
    ],
}

VORSCHLAEGE = {
    "vorschlaege": [
        {
            "fallgruppe_id": "preiserhoehung",
            "begruendung": "Das Studio erhöht den laufenden Monatsbeitrag einseitig.",
            "zitate": ["Mein Fitnessstudio erhöht meinen Beitrag ab Oktober von 34,90 auf 36,35 Euro"],
        },
        {
            "fallgruppe_id": "klausel_check",
            "begruendung": "Im Kern steht die Wirksamkeit der Preisanpassungsklausel in den AGB.",
            "zitate": [],
        },
    ]
}


if __name__ == "__main__":
    melden(schreiben(FALL, KLASSIFIKATION, EXTRAKTION, VORSCHLAEGE))
