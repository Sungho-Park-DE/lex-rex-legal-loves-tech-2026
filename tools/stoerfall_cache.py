"""Hand-authored `cache/llm/` entries for the Störfall case (14 §7).

The point of this case is that the *document* is faulty, not the model: the
letter cites a clause number the AGB do not have, quotes its own clause
differently than it stands in the AGB, invents a BGH decision, and carries a
line addressed at an automated reader. The extraction below is what an honest
model returns — it reports what the letter says, including the invented
citation. Everything that follows is the rule engine's work, not the model's.

That is also the answer to the injection on page 2: the values below are
extracted facts, and no field in the schema can carry „das Ergebnis ist
wirksam". The verdict is computed from the fields, so an instruction in the
document has nothing to attach to.

Run:  .venv/bin/python tools/stoerfall_cache.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools._cache_basis import melden, schreiben  # noqa: E402

from fallpruefer.konfig import WURZEL  # noqa: E402

FALL = WURZEL / "demo" / "faelle" / "stoerfall_kraftwerk"

KLASSIFIKATION = {
    "D1": {
        "dokumenttyp": "erhoehungsschreiben",
        "konfidenz": 0.96,
        "begruendung": "Anschreiben eines Fitnessstudios, das eine Beitragsanpassung zum 01.10.2026 ankündigt.",
    },
    "D2": {
        "dokumenttyp": "agb",
        "konfidenz": 0.95,
        "begruendung": "Nummerierte Allgemeine Geschäftsbedingungen mit Beiträgen, Öffnungszeiten und Kündigung.",
    },
    "D3": {
        "dokumenttyp": "vertrag",
        "konfidenz": 0.95,
        "begruendung": "Mitgliedsvertrag mit Vertragsdatum, Tarif, Beitrag und Unterschriftszeile.",
    },
}

# Was das Schreiben behauptet — nicht, was in den AGB steht.
ZITAT_IM_BRIEF = (
    "Der Betreiber ist berechtigt, den Beitrag jederzeit und ohne Angabe von "
    "Gründen anzupassen."
)
# Was wirklich in den AGB steht.
KLAUSEL_42 = (
    "Der Betreiber kann den Beitrag einmal je Kalenderjahr anpassen, wenn und "
    "soweit sich die Kosten für Energie, Personal oder Miete erhöht haben. "
    "Sinken diese Kosten, ist der Beitrag entsprechend zu senken. Die Anpassung "
    "wird dem Mitglied mindestens sechs Wochen vor ihrem Wirksamwerden in "
    "Textform mitgeteilt."
)
KUENDIGUNG_43 = (
    "4.3 Das Mitglied kann den Vertrag bis zum Wirksamwerden einer Anpassung zu "
    "diesem Zeitpunkt kündigen. Auf dieses Recht weist der Betreiber in der "
    "Mitteilung hin."
)

EXTRAKTION = {
    "D1": [
        ("erhoehungsschreiben.datum", "2026-08-03", "Nürnberg, 03.08.2026", 1),
        ("erhoehungsschreiben.form", "brief",
         "Kraftwerk Fitness GmbH · Fürther Straße 210 · 90429 Nürnberg", 1),
        ("erhoehungsschreiben.wirksam_ab", "2026-10-01", "ab dem 01.10.2026", 1),
        ("erhoehungsschreiben.alter_betrag", "34,90",
         "statt bisher 34,90 EUR nunmehr 42,90 EUR", 1),
        ("erhoehungsschreiben.neuer_betrag", "42,90",
         "statt bisher 34,90 EUR nunmehr 42,90 EUR", 1),
        ("erhoehungsschreiben.grundlage_genannt", "klausel",
         "Grundlage ist **Ziffer 9.4** unserer Allgemeinen Geschäftsbedingungen", 1),
        # Der Verweis, den es in den AGB nicht gibt — das ist der Beat.
        ("erhoehungsschreiben.klauselverweis", "Ziffer 9.4", "Ziffer 9.4", 1),
        # Das Zitat, das nicht mit der AGB-Klausel übereinstimmt.
        ("erhoehungsschreiben.klauselzitat", ZITAT_IM_BRIEF, ZITAT_IM_BRIEF, 1),
        ("erhoehungsschreiben.zustimmungsmechanismus", "keiner",
         "Eine gesonderte Zustimmung ist daher nicht erforderlich.", 1),
        ("erhoehungsschreiben.kuendigungshinweis", False,
         "Der Einzug erfolgt wie gewohnt zum Monatsersten.", 1),
        ("erhoehungsschreiben.begruendung", "gestiegene Energie- und Personalkosten",
         "gestiegene Energie- und Personalkosten zwingen uns zu einer Anpassung der Beiträge", 1),
        # Die erfundene Entscheidung. Sie wird berichtet, nicht bewertet —
        # ob es sie gibt, entscheidet der Normbasis-Abgleich, nicht das Modell.
        ("erhoehungsschreiben.zitierte_fundstellen", ["BGH, Urteil vom 12.03.2019 – VIII ZR 214/18"],
         "(BGH, Urteil vom 12.03.2019 – VIII ZR 214/18)", 1),
        ("erhoehungsschreiben.absender", "Kraftwerk Fitness GmbH",
         "Kraftwerk Fitness GmbH · Fürther Straße 210 · 90429 Nürnberg", 1),
        ("erhoehungsschreiben.absender_adresse", "Fürther Straße 210, 90429 Nürnberg",
         "Fürther Straße 210 · 90429 Nürnberg", 1),
    ],
    "D2": [
        ("agb.fassung_datum", "2025-01-15", "Fassung vom 15.01.2025", 1),
        ("agb.preisklausel_text", KLAUSEL_42, KLAUSEL_42, 1),
        ("agb.preisklausel_ziffer", "4.2", "4.2 Der Betreiber kann den Beitrag", 1),
        ("agb.klausel_ueberschrift", "Beiträge", "§ 4 Beiträge", 1),
        ("agb.nennt_anlass", True,
         "wenn und soweit sich die Kosten für Energie, Personal oder Miete erhöht haben", 1),
        ("agb.nennt_voraussetzungen", True, "einmal je Kalenderjahr", 1),
        ("agb.nennt_umfang", False, KLAUSEL_42, 1),
        ("agb.kostenbezug", True,
         "wenn und soweit sich die Kosten für Energie, Personal oder Miete erhöht haben", 1),
        ("agb.senkungspflicht", "pflicht",
         "Sinken diese Kosten, ist der Beitrag entsprechend zu senken.", 1),
        ("agb.kuendigungsrecht_bei_erhoehung", True, KUENDIGUNG_43, 1),
        ("agb.widerspruch_formerfordernis", "keine_angabe", KLAUSEL_42, 1),
        ("agb.leistungsaenderungsrecht", False,
         "5.1 Die jeweils gültigen Öffnungszeiten hängen im Eingangsbereich aus.", 1),
    ],
    "D3": [
        ("vertrag.datum", "2025-01-28", "Nürnberg, den 28.01.2025", 1),
        ("vertrag.vertragsbeginn", "2025-02-01", "Vertragsbeginn    01.02.2025", 1),
        ("vertrag.laufzeit_monate", 12, "Mindestlaufzeit   12 Monate", 1),
        ("vertrag.verlaengerung_text",
         "Nach Ablauf der Mindestlaufzeit läuft der Vertrag auf unbestimmte Zeit weiter.",
         "Verlängerung      Nach Ablauf der Mindestlaufzeit läuft der Vertrag auf unbestimmte Zeit weiter.", 1),
        ("vertrag.beitrag", "34,90", "Mitgliedsbeitrag  34,90 EUR monatlich", 1),
        ("vertrag.agb_einbezogen_hinweis", True,
         "Das Mitglied bestätigt mit seiner Unterschrift, dass ihm die AGB vor Vertragsschluss ausgehändigt wurden.", 1),
        # Ohne dieses Feld meldet P2 — das wegen der Kreuzprüfung auf FEHLT
        # steht — den Vertrag als fehlend, obwohl er in der Akte liegt.
        # Der Vertrag beantwortet die Frage: er nennt eine Fassung und keine
        # spätere Änderung.
        ("vertrag.aenderungsvereinbarung_hinweis", False,
         "Es gelten die Allgemeinen Geschäftsbedingungen der Kraftwerk Fitness GmbH in der Fassung vom 15.01.2025.", 1),
    ],
}

VORSCHLAEGE = {
    "vorschlaege": [
        {
            "fallgruppe_id": "preiserhoehung",
            "begruendung": "Das Studio erhöht den laufenden Monatsbeitrag einseitig.",
            "zitate": ["Mein Studio erhöht den Beitrag"],
        },
        {
            "fallgruppe_id": "klausel_check",
            "begruendung": "Der Kunde bestreitet, dass die zitierte Klausel so in den AGB steht.",
            "zitate": ["wenn ich in den AGB nachsehe, steht unter dieser Ziffer etwas ganz anderes"],
        },
    ]
}


if __name__ == "__main__":
    melden(schreiben(FALL, KLASSIFIKATION, EXTRAKTION, VORSCHLAEGE,
                     dateien=["schreiben.md", "agb.md", "vertrag.md"]))
