"""Write the hand-authored `cache/llm/` entries for the Drehkreuz fiction case.

Why a script rather than three JSON files checked in by hand: the cache key is
`hash(text_pseudonym + field spec)` (contract §9), so it changes whenever the
demo document text, the pseudonymisation or the Soll field list changes. The
*content* below is hand-written — these are the adapter outputs a model would
have to produce. The filenames are computed so they stay correct.

Run:  .venv/bin/python tools/drehkreuz_cache.py

Once `ANTHROPIC_API_KEY` is set, a live run overwrites these with real
recordings at the same keys and the demo keeps replaying from cache.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fallpruefer.adapter import cache  # noqa: E402
from fallpruefer.adapter.basis import Aufruf  # noqa: E402
from fallpruefer.adapter.cache_adapter import feld_eingabe, seiten_eingabe  # noqa: E402
from fallpruefer.dokumente import laden  # noqa: E402
from fallpruefer.konfig import WURZEL, konfig  # noqa: E402
from fallpruefer.pipeline import fall_anlegen, pseudonymisieren  # noqa: E402
from fallpruefer.schema import schema_laden, taxonomie  # noqa: E402

FALL = WURZEL / "demo" / "faelle" / "drehkreuz"

# --------------------------------------------------------------------------
# classify_doc — what the fast tier should say about each attachment
# --------------------------------------------------------------------------

KLASSIFIKATION = {
    "D1": {
        "dokumenttyp": "erhoehungsschreiben",
        "konfidenz": 0.97,
        "begruendung": "Anschreiben eines Fitnessstudios, das eine Beitragsanpassung zum 01.09.2026 ankündigt.",
    },
    "D2": {
        "dokumenttyp": "agb",
        "konfidenz": 0.96,
        "begruendung": "Nummerierte Allgemeine Geschäftsbedingungen mit Geltungsbereich, Beiträgen und Laufzeit.",
    },
    "D3": {
        "dokumenttyp": "vertrag",
        "konfidenz": 0.95,
        "begruendung": "Mitgliedsvertrag mit Vertragsdatum, Tarif, Beitrag, Mindestlaufzeit und Unterschriftszeile.",
    },
}

# --------------------------------------------------------------------------
# extract_fields — value + the span the value stands on
# --------------------------------------------------------------------------

KLAUSEL = "Der Betreiber ist berechtigt, den monatlichen Beitrag anzupassen."
ZIFFER_52 = (
    "5.2 Der Betreiber ist berechtigt, den monatlichen Beitrag anzupassen. "
    "Die Anpassung wird dem Mitglied mitgeteilt. Trainiert das Mitglied nach "
    "Zugang der Mitteilung weiter, gilt die Anpassung als angenommen."
)
FIKTION = (
    "Trainiert das Mitglied nach Zugang der Mitteilung weiter, gilt die "
    "Anpassung als angenommen."
)

EXTRAKTION = {
    "D1": [
        ("erhoehungsschreiben.datum", "2026-07-20", "München, 20.07.2026", 1),
        ("erhoehungsschreiben.form", "brief", "FitPoint 24 GmbH · Turnstraße 4 · 80333 München", 1),
        ("erhoehungsschreiben.wirksam_ab", "2026-09-01", "mit Wirkung zum 01.09.2026", 1),
        ("erhoehungsschreiben.alter_betrag", "29,90", "von 29,90 EUR auf 36,90 EUR", 1),
        ("erhoehungsschreiben.neuer_betrag", "36,90", "von 29,90 EUR auf 36,90 EUR", 1),
        ("erhoehungsschreiben.grundlage_genannt", "klausel",
         "Auf Grundlage von Ziffer 5.2 unserer Allgemeinen Geschäftsbedingungen", 1),
        ("erhoehungsschreiben.klauselverweis", "Ziffer 5.2", "Ziffer 5.2", 1),
        ("erhoehungsschreiben.klauselzitat", KLAUSEL, KLAUSEL, 1),
        ("erhoehungsschreiben.zustimmungsmechanismus", "weiternutzung",
         "Mit Ihrem nächsten Check-in am Drehkreuz stimmen Sie dem neuen Beitrag zu.", 1),
        # false, with the span that was examined — „I looked here and found no
        # Kündigungshinweis" is evidence; a bare „no" would not be.
        ("erhoehungsschreiben.kuendigungshinweis", False,
         "Mit Ihrem nächsten Check-in am Drehkreuz stimmen Sie dem neuen Beitrag zu. "
         "Der Einzug erfolgt wie gewohnt zum Monatsersten.", 1),
        ("erhoehungsschreiben.begruendung", "gestiegene Energie- und Personalkosten",
         "gestiegene Energie- und Personalkosten zwingen uns, unsere Preise anzupassen", 1),
        ("erhoehungsschreiben.zitierte_fundstellen", [],
         "Auf Grundlage von Ziffer 5.2 unserer Allgemeinen Geschäftsbedingungen", 1),
        ("erhoehungsschreiben.absender", "FitPoint 24 GmbH",
         "FitPoint 24 GmbH · Turnstraße 4 · 80333 München", 1),
        ("erhoehungsschreiben.absender_adresse", "Turnstraße 4, 80333 München",
         "Turnstraße 4 · 80333 München", 1),
    ],
    "D2": [
        ("agb.fassung_datum", "2021-05-01", "Fassung vom 01.05.2021", 1),
        ("agb.preisklausel_text", KLAUSEL, KLAUSEL, 2),
        ("agb.preisklausel_ziffer", "5.2", "5.2 Der Betreiber ist berechtigt", 2),
        ("agb.klausel_ueberschrift", "Beiträge", "5. Beiträge", 2),
        ("agb.nennt_anlass", False, KLAUSEL, 2),
        ("agb.nennt_voraussetzungen", False, KLAUSEL, 2),
        ("agb.nennt_umfang", False, KLAUSEL, 2),
        ("agb.kostenbezug", False, KLAUSEL, 2),
        ("agb.senkungspflicht", "keine", ZIFFER_52, 2),
        ("agb.kuendigungsrecht_bei_erhoehung", False, ZIFFER_52, 2),
        ("agb.erklaerungsfiktion_text", FIKTION, FIKTION, 2),
        ("agb.erklaerungsfiktion_frist_und_hinweis", False, FIKTION, 2),
        # Paulina, Runde 3 (29 §3): keine Formvorgabe für den Widerspruch in
        # diesen AGB — Beleg ist die Klausel, in der sie stehen müsste.
        ("agb.widerspruch_formerfordernis", "keine_angabe", ZIFFER_52, 2),
        ("agb.leistungsaenderungsrecht", False,
         "3.1 Der Betreiber hält die in der Studiobeschreibung genannten Geräte und Kurse bereit.", 1),
    ],
    "D3": [
        ("vertrag.datum", "2025-10-01", "Vertragsdatum: 01.10.2025", 1),
        ("vertrag.laufzeit_monate", 24, "Mindestlaufzeit: 24 Monate", 1),
        ("vertrag.verlaengerung_text",
         "Der Vertrag verlängert sich um jeweils 12 Monate, wenn er nicht 3 Monate vor Ablauf gekündigt wird.",
         "Verlängerung: Der Vertrag verlängert sich um jeweils 12 Monate, wenn er nicht 3 Monate vor Ablauf gekündigt wird.", 1),
        ("vertrag.beitrag", "29,90", "Monatlicher Beitrag: 29,90 EUR", 1),
        ("vertrag.preisgarantie_monate", 12,
         "Preisgarantie: Der Beitrag bleibt für 12 Monate ab Vertragsbeginn unverändert.", 1),
        ("vertrag.agb_einbezogen_hinweis", True,
         "Die Allgemeinen Geschäftsbedingungen in der Fassung vom 01.05.2021 habe ich erhalten und erkenne sie an.", 1),
    ],
}

# --------------------------------------------------------------------------
# propose_fallgruppe
# --------------------------------------------------------------------------

VORSCHLAEGE = {
    "vorschlaege": [
        {
            "fallgruppe_id": "preiserhoehung",
            "begruendung": "Das Studio erhöht den laufenden Monatsbeitrag einseitig.",
            "zitate": ["mein Beitrag ab September von 29,90 auf 36,90 Euro steigt"],
        },
        {
            "fallgruppe_id": "klausel_check",
            "begruendung": "Im Kern steht die Wirksamkeit der Preisanpassungsklausel in den AGB.",
            "zitate": [],
        },
    ]
}


def main() -> None:
    k = konfig().llm
    import json

    ticket = json.loads((FALL / "ticket.json").read_text(encoding="utf-8"))
    dokumente = [laden(FALL / n, f"D{i}") for i, n in enumerate(ticket["anhaenge"], start=1)]
    fall = fall_anlegen("F-2026-0001", ticket, dokumente)
    pseudonymisieren(fall)

    schema = schema_laden("preiserhoehung")
    geschrieben: list[str] = []

    for d in fall.dokumente:
        eingabe = {"seiten": seiten_eingabe(d.seiten)}
        pfad = cache.pfad_fuer("classify_doc", k.modell_klassifikation, k.prompt_version, eingabe)
        cache.schreiben(pfad, Aufruf(
            aufgabe="classify_doc", modell=k.modell_klassifikation,
            prompt_version=k.prompt_version, eingabe=eingabe,
            ausgabe=KLASSIFIKATION[d.dok_id], dauer_ms=610, kosten_cent=0.05,
        ))
        geschrieben.append(pfad.name)

        typ = KLASSIFIKATION[d.dok_id]["dokumenttyp"]
        sd = schema.dokumenten_soll.nach_typ(type(d.dokumenttyp)(typ))
        if not sd or not sd.felder:
            continue
        eingabe = {
            "dokumenttyp": typ,
            "seiten": seiten_eingabe(d.seiten),
            "felder": feld_eingabe(sd.felder),
        }
        ausgabe = {"felder": [
            {"feld_id": fid, "wert": wert, "zitat": zitat, "seite": seite}
            for fid, wert, zitat, seite in EXTRAKTION[d.dok_id]
        ]}
        pfad = cache.pfad_fuer("extract_fields", k.modell_extraktion, k.prompt_version, eingabe)
        cache.schreiben(pfad, Aufruf(
            aufgabe="extract_fields", modell=k.modell_extraktion,
            prompt_version=k.prompt_version, eingabe=eingabe, ausgabe=ausgabe,
            dauer_ms=4200, kosten_cent=1.1,
        ))
        geschrieben.append(pfad.name)

    doktypen = sorted(v["dokumenttyp"] for v in KLASSIFIKATION.values())
    eingabe = {
        "freitext": fall.eingang.freitext_pseudonym,
        "doktypen": doktypen,
        "taxonomie": sorted(taxonomie()),
    }
    pfad = cache.pfad_fuer("propose_fallgruppe", k.modell_extraktion, k.prompt_version, eingabe)
    cache.schreiben(pfad, Aufruf(
        aufgabe="propose_fallgruppe", modell=k.modell_extraktion,
        prompt_version=k.prompt_version, eingabe=eingabe, ausgabe=VORSCHLAEGE,
        dauer_ms=3100, kosten_cent=0.6,
    ))
    geschrieben.append(pfad.name)

    print(f"{len(geschrieben)} Cache-Dateien geschrieben:")
    for n in geschrieben:
        print("  ", n)


if __name__ == "__main__":
    main()
