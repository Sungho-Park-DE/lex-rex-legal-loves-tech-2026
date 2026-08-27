# Data Contract v1.1 — VZ-I Fall-Prüfer

> Session working doc (English prose, **German keys**). Implements `14_produkt_richtung.md` (v2.1). v1.1 folds in the cold verification (33 agents): declarative rule grammar, gate semantics + `INAKTIV`, WERTUNG→unklar, guaranteed pair per branch, Anbieter/Störfall/Leitfaden carriers, pseudonym token syntax, re-run semantics, Paulina/Franz ingest adapters. **Team deliverables are still pending** — §13 states what the build assumes until they arrive; nothing here requires a change to the sent packets. Every legal value not confirmed by the law students carries `"geprueft": false` and renders grey (never on a slide). No schedule in this file.

## 0. Files, identifiers, vocabularies

```
schemas/_taxonomie.json          derived at load from schema files (display names, Stufe) — schema file is the Stufe SSOT
schemas/preiserhoehung.json      Stufe A — fitness skin; mechanism cross-sector, but only fitness anchors/cases are in scope now
schemas/inkasso.json             Stufe B — provisional Dokumenten-Soll from Paulina's four Runde-1 cases; Prüfpunkte [] until her list lands (→ A)
schemas/kuendigung.json          Stufe C — name only
schemas/klausel_check.json       Stufe C — name only
schemas/energie.json             NOT built — future skin file; Franz' six cross-sector cases are parked as skin-variant tests
normbasis/statutes_de.json       statute texts — MUST be seeded with the anchors below before the A-schema loads (see §5)
normbasis/caselaw.json           case-law anchors, each with geprueft flag + who verified
templates/musterbriefe/*.md      VZ templates with [PLATZHALTER] + front matter (source URL); ours until Paulina's downloads arrive
templates/nachforderung_*.md     vbs | vor_ort (= telefon) | video
templates/basis_eintrag.md       Abschluss export block
cases/<case_id>.json             full case object (contains the pseudonym map — never leaves the machine)
cache/llm/<aufgabe>_<modell>_<promptversion>_<eingabehash>.json   pseudonymised input + output; the demo replays from here
store/faelle.jsonl               anonymised records for the Radar (append-only)
tests/golden/<case_id>.json      expected results (from Lösungszettel; ours are geprueft:false)
tests/stoerfall/                 three prepared tampered documents (fabricated citation · misquoted clause · white-text injection)
demo/                            bookend handouts (ticket printout, finished Fallakte), demo case files
config.json
```

IDs: `fallgruppe_id` = schema file stem · `pruefpunkt_id` = `P<n>` (numbering = `analysis/detail/domain.json` 0–13, plus P14) · `feld_id` = `<dokumenttyp>.<name>` or a namespace `gespraech.<name>` (Leitfaden answers) / `intake.<name>` (advisor-set flags) · `dok_id` = `D<n>` · `run_id` = `R<n>` · semver versions; every result stores `schema_version` + `schema_stand`.

Binding vocabularies:
- `einordnung`: `"wirksam" | "wahrscheinlich unwirksam" | "unklar – es fehlt …"` — rendered with the named items: `unklar – es fehlt: AGB` / `unklar – es fehlt: Bewertung durch die Beraterin zu „Ist die Klausel überraschend?"`
- `zustand`: `JA | NEIN | FEHLT | WERTUNG | INAKTIV`
- `rolle`: `tragend | ergaenzend | gate | ableitung | strategie`
- `typ`: `fakt | text | wertung | lookup`
- `herkunft`: `explizit | angenommen | strittig | fehlt | gespraech | override`
- `dokumenttyp`: `erhoehungsschreiben | agb | vertrag | rechnung | kontoauszug | kostenkalkulation | anschreiben | auftragsbestaetigung | widerrufsbelehrung | inkassoschreiben | abtretungsurkunde | vollmacht | email | sonstiges`
- `pflicht`: `immer | bedingt | erwartet_wenn_vorhanden | hinweis` — `erwartet_wenn_vorhanden`: absence is a legal fact (recorded as `<typ>.vorhanden=false`), never requested; `hinweis`: company-side, never requested from the consumer, always listed as open
- `quelle`: `verbraucher | unternehmen`
- `kanal`: `vbs | vor_ort | telefon | video`
- `badge`: `verifiziert | nicht_gefunden | anker_ungeprueft | normbasis_fehlt | kreuzpruefung_fehlgeschlagen | angenommen | llm_befund`
- `ebene`: `gesetz | dogmatik | rechtsanwendung | unentscheidbar` · `anker.status`: `gefestigt | in_bewegung`
- pseudonym tokens: `@@PERSON_1@@`, `@@ADRESSE_1@@`, `@@EMAIL_1@@`, `@@TELEFON_1@@`, `@@IBAN_1@@`, `@@KUNDENNR_1@@`, `@@GEBURTSDATUM_1@@` — deliberately distinct from letter placeholders `[GROSSBUCHSTABEN]`

## 1. Rule grammar (`regelsprache`) — rules are data

Each Prüfpunkt has `"regel": {"FEHLT_wenn": C, "NEIN_wenn": C, "WERTUNG_wenn": C, "JA_wenn": C, "sonst": "JA|WERTUNG"}`. Evaluation order is fixed: `FEHLT_wenn → NEIN_wenn → WERTUNG_wenn → JA_wenn → sonst`; the first condition that is **true** fires. Conditions C:

```
C := {"alle": [C…]} | {"eine": [C…]} | {"nicht": C}
   | {"feld": F, "op": OP, "wert": V}          OP ∈ == != < <= > >= in nicht_in
   | {"feld": F, "op": OP, "feld2": F}
   | {"param": P, "op": OP, "feld": F} | {"feld": F, "op": OP, "param": P}
   | {"fehlt": F} | {"vorhanden": F} | {"verifiziert": F} | {"dok_fehlt": DOKUMENTTYP} | {"dok_vorhanden": DOKUMENTTYP}
   | {"prim": NAME, "args": {…}, "op": OP, "wert": V}   numeric/bool engine primitive
```
Three-valued logic: a `feld` that is absent makes its atom `null`; `alle` = false if any false, else null if any null, else true; `eine` = true if any true, else null if any null, else false; `nicht null` = null. A branch fires only on `true`. **Implicit FEHLT**: if no branch fired and any `eingaben` with `pflicht:true` is absent or unverified → `FEHLT` listing those inputs (owner from the Soll). Otherwise `sonst`.

> **Nachtrag 25 Aug (V-G1, V-F2):** Prädikat `{"dok_existiert_nicht": <typ>}` — wahr, wenn die Verbraucherin das Dokument als nie vorhanden festgestellt hat (`fall.nicht_vorhanden`, nicht zurückgezogen) und keines in der Akte liegt; `dok_fehlt` bleibt „fehlt aus beiden Gründen“. `bei_NEIN.deaktiviert` gilt auch an tragenden Punkten (sie laufen vor dem Rest, Schritt 1b in `pruefen()`); `schema_stopp` bleibt Gates vorbehalten. `satz_nein` · `fehlt_text` · `plain_grund` dürfen statt eines Strings eine Liste `[{"wenn": <Bedingung>, "satz": "…"}, {"satz": "Rest"}]` tragen — ein Satz je Arm, der erste zutreffende spricht.

Whitelisted primitives (the only code the schema may call by name — this IS the propagation engine): `tage_zwischen(a,b)`, `datum_plus(feld,tage)`, `monate_zwischen(a,b)`, `anzahl(liste)`, `summe_rueckforderung()`, `kreuzpruefung_klauselverweis()` (is the letter's cited Ziffer findable in agb/vertrag text?), `klauselzitat_stimmt()` (does the letter's quoted clause text match the clause text in agb/vertrag, normalised?), `normbasis_treffer(liste)` (count of cited Fundstellen resolvable in the Normbasis). Unknown primitive or feld → schema load error. Jurist-Edit edits this JSON — parameters, texts, anchors, roles, conditions — and the engine re-evaluates; no code changes.

## 2. Schema file — `schemas/preiserhoehung.json`

```json
{
  "fallgruppe_id": "preiserhoehung",
  "name": "Preiserhöhung im Verbrauchervertrag",
  "skin": "fitness",
  "stufe": "A",
  "version": "0.7.0",
  "stand": "2026-08-25",
  "geprueft_von": [],
  "regelsprache": "v1",
  "jurist_edit_knoepfe": ["pruefpunkte.P10.parameter.frist_min_tage", "pruefpunkte.P6.anker"],

  "annahmen": [
    {"id": "zugang_plus_3", "feld": "erhoehungsschreiben.zugang", "wert": "datum_plus(erhoehungsschreiben.datum, 3)", "anzeige": "Zugang: angenommen (mangels Angabe) — rechtlich zählt der Tag des Einwurfs, § 130 BGB", "kommentar": "Die drei Tage sind eine Rechenannahme ohne Rechtsgrundlage: für Privatbriefe gibt es keine Zugangsfiktion (§ 130 Abs. 1 BGB; BAG 2 AZR 111/19, BGH XII ZR 148/05 — es zählen die örtlichen Postzustellzeiten). Bis V-Z1 bleibt der Rechenweg, die Beschriftung sagt jetzt, was sie ist. analysis/34 §2.", "geprueft": false},
    {"id": "verbrauchervertrag", "feld": "intake.verbrauchervertrag", "wert": true, "anzeige": "Verbrauchervertrag angenommen (natürliche Person, privater Zweck)", "geprueft": false}
  ],

  "dokumenten_soll": {
    "gruppen": [{"id": "klausel", "mindestens_eines": ["agb", "vertrag"], "anzeigename": "die Preisklausel — in den AGB oder im Vertrag"}],
    "dokumente": [
      {"dokumenttyp": "erhoehungsschreiben", "pflicht": "immer", "quelle": "verbraucher",
       "anzeigename": "das Erhöhungsschreiben (Brief, E-Mail, App-Nachricht oder Foto vom Aushang)",
       "begruendung_satz": "Aus dem Schreiben ergibt sich, worauf das Studio die Erhöhung stützt und ab wann sie gelten soll.",
       "beschaffungsweg": "Brief, E-Mail, Studio-App, Foto vom Aushang",
       "felder": [
         {"feld_id": "erhoehungsschreiben.datum", "label": "Datum des Schreibens", "typ": "datum", "pflicht": true},
         {"feld_id": "erhoehungsschreiben.zugang", "label": "Zugang des Schreibens", "typ": "datum", "pflicht": false},
         {"feld_id": "erhoehungsschreiben.form", "label": "Form der Mitteilung", "typ": "enum", "werte": ["brief", "email", "app", "aushang", "website", "unbekannt"], "wert_labels": {"brief": "Brief", "email": "E-Mail", "app": "App-Nachricht", "aushang": "Aushang im Studio", "website": "Hinweis auf der Website", "unbekannt": "unbekannt"}, "pflicht": true},
         {"feld_id": "erhoehungsschreiben.wirksam_ab", "label": "Erhöhung soll gelten ab", "typ": "datum", "pflicht": true},
         {"feld_id": "erhoehungsschreiben.alter_betrag", "label": "bisheriger Beitrag", "typ": "betrag", "pflicht": false},
         {"feld_id": "erhoehungsschreiben.neuer_betrag", "label": "neuer Beitrag", "typ": "betrag", "pflicht": true},
         {"feld_id": "erhoehungsschreiben.grundlage_genannt", "label": "genannte Grundlage", "typ": "enum", "werte": ["klausel", "gesetz", "zustimmung_aktiv", "zustimmungsfiktion", "neue_entgeltposition", "keine"], "wert_labels": {"klausel": "eine Vertragsklausel", "gesetz": "eine gesetzliche Regelung", "zustimmung_aktiv": "eine aktive Zustimmung", "zustimmungsfiktion": "eine Zustimmungsfiktion", "neue_entgeltposition": "eine neue Entgeltposition", "keine": "keine"}, "pflicht": true, "zitat_pflicht": true},
         {"feld_id": "erhoehungsschreiben.klauselverweis", "label": "Verweis auf die Klausel", "typ": "text", "pflicht": false, "beschreibung": "zitierte Ziffer, z. B. „Ziffer 5.2“"},
         {"feld_id": "erhoehungsschreiben.klauselzitat", "label": "zitierter Klauseltext", "typ": "text", "pflicht": false, "zitat_pflicht": true, "beschreibung": "Wortlaut der Klausel, so wie das Schreiben ihn wiedergibt"},
         {"feld_id": "erhoehungsschreiben.zustimmungsmechanismus", "label": "Zustimmungsmechanismus", "typ": "enum", "werte": ["schweigen", "weiternutzung", "klick", "unterschrift", "keiner"], "wert_labels": {"schweigen": "Schweigen", "weiternutzung": "die weitere Nutzung", "klick": "einen Klick", "unterschrift": "eine Unterschrift", "keiner": "keinen Mechanismus"}, "pflicht": true, "zitat_pflicht": true},
         {"feld_id": "erhoehungsschreiben.kuendigungshinweis", "label": "Kündigungshinweis", "typ": "bool", "pflicht": true, "zitat_pflicht": true},
         {"feld_id": "erhoehungsschreiben.begruendung", "label": "Begründung der Erhöhung", "typ": "text", "pflicht": false},
         {"feld_id": "erhoehungsschreiben.zitierte_fundstellen", "label": "zitierte Fundstellen", "typ": "liste_text", "pflicht": false, "zitat_pflicht": true, "beschreibung": "alle §§ und Aktenzeichen, die das Schreiben selbst nennt"},
         {"feld_id": "erhoehungsschreiben.absender", "label": "Absender", "typ": "text", "pflicht": true, "beschreibung": "Name des Anbieters laut Briefkopf"},
         {"feld_id": "erhoehungsschreiben.absender_adresse", "label": "Absenderadresse", "typ": "text", "pflicht": false}
       ]},
      {"dokumenttyp": "agb", "pflicht": "bedingt", "bedingung": {"dok_fehlt": "vertrag"}, "gruppe": "klausel", "quelle": "verbraucher",
       "anzeigename": "die AGB, die bei Vertragsschluss galten",
       "begruendung_satz": "Daraus ergibt sich, ob das Studio den Beitrag überhaupt einseitig ändern darf und unter welchen Bedingungen.",
       "beschaffungsweg": "Mitgliedsvertrag (Rückseite/Anlage), Studio-Website, Studio-App",
       "felder": [
         {"feld_id": "agb.fassung_datum", "label": "Stand der AGB", "typ": "datum", "pflicht": false},
         {"feld_id": "agb.preisklausel_text", "label": "Wortlaut der Preisklausel", "typ": "text", "pflicht": true, "zitat_pflicht": true, "beschreibung": "Wortlaut der Preisanpassungsklausel — die ganze Klausel mit allen Sätzen (Anlass, Voraussetzungen, Umfang bzw. Kappung), nicht nur der erste Satz; ohne ihn gilt das Dokument als unvollständig"},
         {"feld_id": "agb.preisklausel_ziffer", "label": "Ziffer der Preisklausel", "typ": "text", "pflicht": false},
         {"feld_id": "agb.klausel_ueberschrift", "label": "Überschrift der Klausel", "typ": "text", "pflicht": false, "zitat_pflicht": true},
         {"feld_id": "agb.nennt_anlass", "label": "Anlass genannt", "typ": "bool", "beschreibung": "Anlass der Erhöhung in der Klausel", "pflicht": true, "zitat_pflicht": true},
         {"feld_id": "agb.nennt_voraussetzungen", "label": "Voraussetzungen genannt", "typ": "bool", "beschreibung": "Voraussetzungen der Erhöhung in der Klausel", "pflicht": true, "zitat_pflicht": true},
         {"feld_id": "agb.nennt_umfang", "label": "Umfang genannt", "typ": "bool", "beschreibung": "Umfang der Erhöhung in der Klausel", "pflicht": true, "zitat_pflicht": true},
         {"feld_id": "agb.kostenbezug", "label": "Kostenbezug", "typ": "bool", "pflicht": true, "zitat_pflicht": true, "beschreibung": "knüpft die Erhöhung an Kostenentwicklung?"},
         {"feld_id": "agb.senkungspflicht", "label": "Senkungspflicht", "typ": "enum", "werte": ["pflicht", "ermessen", "keine"], "wert_labels": {"pflicht": "Pflicht zur Senkung", "ermessen": "Senkung im Ermessen", "keine": "keine Senkungsregel"}, "beschreibung": "Regelung zur Weitergabe von Kostensenkungen", "pflicht": true, "zitat_pflicht": true},
         {"feld_id": "agb.kuendigungsrecht_bei_erhoehung", "label": "Kündigungsrecht bei Erhöhung", "typ": "bool", "pflicht": true, "zitat_pflicht": true},
         {"feld_id": "agb.erklaerungsfiktion_text", "label": "Wortlaut der Erklärungsfiktion", "typ": "text", "pflicht": false, "zitat_pflicht": true},
         {"feld_id": "agb.erklaerungsfiktion_frist_und_hinweis", "label": "Frist und Hinweis in der Fiktionsklausel", "typ": "bool", "pflicht": false, "zitat_pflicht": true, "beschreibung": "nennt die Fiktionsklausel Frist und Hinweispflicht (§ 308 Nr. 5)?"},
         {"feld_id": "agb.widerspruchsfrist_tage", "label": "Widerspruchsfrist (Tage)", "typ": "zahl", "pflicht": false, "zitat_pflicht": true, "beschreibung": "Frist in Tagen, innerhalb derer die AGB einen Widerspruch gegen die Anpassung verlangen (zwei Wochen = 14); nur wenn die AGB eine solche Frist nennen"},
         {"feld_id": "agb.widerspruch_formerfordernis", "label": "Form des Widerspruchs", "typ": "enum", "werte": ["schriftform", "textform", "formfrei", "keine_angabe"], "wert_labels": {"schriftform": "Schriftform (schriftlich / Unterschrift)", "textform": "Textform (E-Mail genügt)", "formfrei": "formfrei", "keine_angabe": "keine Formvorgabe in den AGB"}, "pflicht": false, "zitat_pflicht": true, "beschreibung": "Welche Form verlangen die AGB für den Widerspruch gegen die Anpassung? „schriftlich“ ohne Zusatz = schriftform; „in Textform“ / „per E-Mail“ = textform"},
         {"feld_id": "agb.leistungsaenderungsrecht", "label": "Leistungsänderungsrecht", "typ": "bool", "pflicht": false, "zitat_pflicht": true},
         {"feld_id": "agb.leistungsaenderung_mit_grund", "label": "Leistungsänderung mit Grund", "typ": "bool", "pflicht": false, "zitat_pflicht": true}
       ]},
      {"dokumenttyp": "vertrag", "pflicht": "immer", "gruppe": "klausel", "quelle": "verbraucher",
       "anzeigename": "den Mitgliedsvertrag oder das Anmeldeformular",
       "begruendung_satz": "Daraus ergeben sich Vertragsdatum, Laufzeit, der vereinbarte Beitrag und eine mögliche Preisgarantie.",
       "beschaffungsweg": "Unterlagen vom Vertragsschluss, Kundenkonto im Studio",
       "felder": [
         {"feld_id": "vertrag.datum", "label": "Vertragsdatum", "typ": "datum", "beschreibung": "Datum des Vertragsschlusses", "pflicht": true},
         {"feld_id": "vertrag.laufzeit_monate", "label": "Laufzeit (Monate)", "typ": "zahl", "pflicht": false},
         {"feld_id": "vertrag.verlaengerung_text", "label": "Verlängerungsklausel", "typ": "text", "pflicht": false, "zitat_pflicht": true},
         {"feld_id": "vertrag.beitrag", "label": "vereinbarter Beitrag", "typ": "betrag", "pflicht": true},
         {"feld_id": "vertrag.vertragsbeginn", "label": "Vertragsbeginn", "typ": "datum", "pflicht": false},
         {"feld_id": "vertrag.preisgarantie_monate", "label": "Preisgarantie (Monate)", "typ": "zahl", "pflicht": false},
         {"feld_id": "vertrag.preisgarantie_bis", "label": "Preisgarantie bis", "typ": "datum", "pflicht": false},
         {"feld_id": "vertrag.agb_einbezogen_hinweis", "label": "Hinweis auf Einbeziehung der AGB", "typ": "bool", "pflicht": false, "zitat_pflicht": true},
         {"feld_id": "vertrag.aenderungsvereinbarung_hinweis", "label": "Hinweis auf spätere AGB-Änderung", "typ": "bool", "pflicht": false, "zitat_pflicht": true, "beschreibung": "wurde eine spätere AGB-Änderung vereinbart?"},
         {"feld_id": "vertrag.preisklausel_text", "label": "Preisklausel im Vertrag", "typ": "text", "pflicht": false, "zitat_pflicht": true, "beschreibung": "falls die Preisklausel im Vertrag selbst steht (dann gelten die agb.*-Klauselfelder analog als vertrag.*)"}
       ]},
      {"dokumenttyp": "kontoauszug", "pflicht": "bedingt", "bedingung": {"feld": "gespraech.rueckforderung_gewuenscht", "op": "==", "wert": true}, "quelle": "verbraucher",
       "anzeigename": "Kontoauszüge oder Abbuchungsbelege seit der Erhöhung",
       "begruendung_satz": "Daraus ergibt sich, wie viel zu viel gezahlt wurde.",
       "beschaffungsweg": "Online-Banking",
       "felder": [{"feld_id": "kontoauszug.abbuchungen", "label": "Abbuchungen", "typ": "liste_betrag_datum", "pflicht": true}]},
      {"dokumenttyp": "kostenkalkulation", "pflicht": "hinweis", "quelle": "unternehmen",
       "anzeigename": "die Kostenkalkulation des Studios",
       "begruendung_satz": "Eine Begründung im Schreiben genügt dafür nicht: Erst die Aufstellung, welche Kosten sich um wie viel verändert haben, macht die Höhe der Erhöhung prüfbar.",
       "beschaffungsweg": "Auskunftsverlangen an das Studio — nie als Nachforderung beim Verbraucher",
       "felder": []}
    ]
  },

  "baum": {
    "id": "root", "op": "AND", "titel": "Preiserhöhung wirksam?",
    "kinder": [
      {"id": "S0", "op": "AND", "titel": "Stufe 0 — Anwendungsbereich", "kinder": ["P0"]},
      {"id": "S1", "op": "AND", "titel": "Stufe 1 — Rechtsgrundlage", "kinder": ["P1a", "P1"]},
      {"id": "S2", "op": "AND", "titel": "Stufe 2 — Einbeziehung", "kinder": ["P2", "P3", "P4"]},
      {"id": "S3", "op": "AND", "titel": "Stufe 3 — Inhaltskontrolle", "kinder": ["P8", "P8c", "P9", "P5", "P6", "P7"]},
      {"id": "S4", "op": "AND", "titel": "Stufe 4 — Ausübung formell", "kinder": ["P10"]},
      {"id": "S5", "op": "AND", "titel": "Stufe 5 — Ausübung materiell", "kinder": ["P11"]},
      {"id": "S6", "op": "AND", "titel": "Hinweise", "kinder": ["P8b", "P8d", "P14"]}
    ],
    "hinweis": "P12 (Rechtsfolgen) und P13 (Strategie) sind Ableitungen, keine Knoten. Knoten S5/S6 enthalten nur ergaenzend-Prüfpunkte und tragen nicht zur Einordnung bei."
  },

  "pruefpunkte": [
    {"id": "P0", "titel": "Anwendungsbereich / Regime", "rolle": "gate", "typ": "fakt",
     "proposition": "Es geht um eine einseitige Preisänderung in einem laufenden Fitnessvertrag (allgemeines AGB-Recht, kein Sonderregime).",
     "eingaben": [{"feld": "erhoehungsschreiben.grundlage_genannt", "pflicht": true}, {"feld": "gespraech.zustimmung_aktiv_belegt", "pflicht": false}],
     "regel": {
       "NEIN_wenn": {"alle": [{"feld": "erhoehungsschreiben.grundlage_genannt", "op": "==", "wert": "zustimmung_aktiv"}, {"feld": "gespraech.zustimmung_aktiv_belegt", "op": "==", "wert": true}]},
       "WERTUNG_wenn": {"feld": "erhoehungsschreiben.grundlage_genannt", "op": "==", "wert": "neue_entgeltposition"},
       "sonst": "JA"},
     "bei_NEIN": {"schema_stopp": true, "text": "Kein einseitiger Eingriff — ein echter Änderungsvertrag wird von diesem Schema nicht geprüft (Widerruf/Anfechtung wären die Fragen)."},
     "wertungsfrage": "Ist die neue Entgeltposition (z. B. Servicepauschale) eine Preiserhöhung im Sinne dieses Schemas oder eine neue Leistung?",
     "anker": [{"norm": "§ 310 Abs. 3 BGB", "key": "bgb_310_3", "ebene": "gesetz", "geprueft": false}],
     "leitfaden_frage": {"text": "Haben Sie der Erhöhung aktiv zugestimmt — unterschrieben, geklickt, am Terminal bestätigt?", "typ": "ja_nein", "fuellt": "gespraech.zustimmung_aktiv_belegt"},
     "satz_ja": "Einseitige Änderung eines laufenden Vertrags — das Prüfschema ist anwendbar.", "plain_grund": "Das Studio hat den Beitrag von sich aus geändert."},

    {"id": "P1a", "titel": "Erhöhung überhaupt erklärt", "rolle": "tragend", "typ": "fakt",
     "proposition": "Dem Mitglied ist eine Erhöhung erklärt worden — es gibt ein Erhöhungsschreiben (oder eine gleichwertige Mitteilung).",
     "eingaben": [],
     "regel": {"NEIN_wenn": {"dok_existiert_nicht": "erhoehungsschreiben"}, "sonst": "JA"},
     "bei_NEIN": {"deaktiviert": ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P8c", "P9", "P10", "P11"], "text": "Ohne Erklärung gibt es nichts zu prüfen — der alte Preis gilt weiter."},
     "anker": [{"norm": "§ 812 Abs. 1 S. 1 BGB", "key": "bgb_812", "ebene": "gesetz", "geprueft": false}],
     "rechtsbehelf_bei_NEIN": "rueckforderung_ohne_erklaerung",
     "satz_ja": "Eine Erhöhung ist erklärt worden; ihre Formalien werden gesondert geprüft.",
     "satz_nein": "Nach Angabe des Mitglieds hat es nie eine Erhöhungsmitteilung gegeben — ohne Erklärung entfällt der Rechtsgrund, der alte Beitrag gilt weiter, die Mehrabbuchung ist ohne Rechtsgrund (§ 812 Abs. 1 S. 1 BGB).",
     "plain_grund": "Das Studio hat die Erhöhung nie erklärt — dann gilt weiter der alte Preis.",
     "geprueft_von": [{"wer": "Franz", "am": "2026-08-24", "beleg": "Runde 3, Rückmeldung zu Fall 6", "umfang": "Ohne Erklärung entfällt der Rechtsgrund; Herausgabeanspruch nach § 812 Abs. 1 S. 1 BGB.", "vorbehalt": "Die Regel greift nur auf die Angabe des Mitglieds hin (Fehlzustand „existiert nicht“); ob wirklich nie erklärt wurde, ist Tatsachenfrage."}]},

    {"id": "P1", "titel": "Rechtsgrundlage der Erhöhung", "rolle": "tragend", "typ": "fakt",
     "proposition": "Das Schreiben benennt eine Grundlage für die Erhöhung (Klausel, Gesetz oder eine Zustimmungsfrage).",
     "eingaben": [{"feld": "erhoehungsschreiben.grundlage_genannt", "pflicht": true}],
     "regel": {"NEIN_wenn": {"feld": "erhoehungsschreiben.grundlage_genannt", "op": "==", "wert": "keine"}, "sonst": "JA"},
     "anker": [], "rechtsbehelf_bei_NEIN": "widerspruch_rueckforderung",
     "satz_ja": "Das Schreiben nennt eine Grundlage ({erhoehungsschreiben.grundlage_genannt}).", "satz_nein": "Das Schreiben nennt keine Grundlage — der neue Beitrag wird nur mitgeteilt.",
     "plain_grund": "Das Studio sagt nicht, woraus es das Recht zur Erhöhung herleitet."},

    {"id": "P2", "titel": "Einbeziehung der Preisklausel", "rolle": "tragend", "typ": "fakt",
     "proposition": "Die Preisklausel war bei Vertragsschluss Vertragsbestandteil, und die zitierte Klausel steht in dieser Fassung.",
     "satz_ja": "Die zitierte Klausel steht so in den vorgelegten AGB, und deren Fassung ist nach den vorliegenden Unterlagen nicht jünger als der Vertrag.",
     "eingaben": [{"feld": "agb.preisklausel_text", "pflicht": true, "oder": "vertrag.preisklausel_text"}, {"feld": "agb.fassung_datum", "pflicht": false}, {"feld": "vertrag.datum", "pflicht": true}, {"feld": "vertrag.agb_einbezogen_hinweis", "pflicht": false}, {"feld": "vertrag.aenderungsvereinbarung_hinweis", "pflicht": false}],
     "regel": {
       "FEHLT_wenn": {"prim": "kreuzpruefung_klauselverweis", "args": {}, "op": "==", "wert": false},
       "NEIN_wenn": {"alle": [{"feld": "agb.fassung_datum", "op": ">", "feld2": "vertrag.datum"}, {"feld": "vertrag.aenderungsvereinbarung_hinweis", "op": "!=", "wert": true}, {"dok_vorhanden": "vertrag"}]},
       "WERTUNG_wenn": {"eine": [{"fehlt": "vertrag.agb_einbezogen_hinweis"}, {"feld": "agb.fassung_datum", "op": ">", "feld2": "vertrag.datum"}]},
       "sonst": "JA"},
     "fehlt_text": "die Stelle mit {erhoehungsschreiben.klauselverweis} — in den vorliegenden AGB nicht gefunden",
     "anker": [{"norm": "§ 305 Abs. 2 BGB", "key": "bgb_305_2", "ebene": "gesetz", "geprueft": false}],
     "rechtsbehelf_bei_NEIN": "widerspruch_rueckforderung",
     "wertungsfrage": "Galt die zitierte Klauselfassung schon bei Vertragsschluss, und wurde sie wirksam einbezogen?",
     "leitfaden_frage": {"text": "Haben Sie beim Vertragsschluss die AGB bekommen oder unterschrieben, dass Sie sie kennen?", "typ": "ja_nein", "fuellt": "vertrag.agb_einbezogen_hinweis"},
     "geprueft_hinweis": {"regel_NEIN": false, "kommentar": "Franz/Paulina: NEIN nur, wenn die bei Vertragsschluss geltende Fassung die Klausel nicht enthielt und keine Änderungsvereinbarung vorliegt"},
     "plain_grund": "Die Klausel, auf die sich das Studio beruft, war so bei Vertragsschluss nicht vereinbart."},

    {"id": "P3", "titel": "Vorrang der Individualabrede / Preisgarantie", "rolle": "tragend", "typ": "fakt",
     "proposition": "Es gibt keine Preisgarantie, die den Erhöhungszeitpunkt abdeckt.",
     "satz_ja": "Nach den vorliegenden Unterlagen deckt keine Preisgarantie den Zeitpunkt der Erhöhung ab.",
     "eingaben": [{"feld": "vertrag.preisgarantie_monate", "pflicht": false}, {"feld": "vertrag.preisgarantie_bis", "pflicht": false}, {"feld": "vertrag.vertragsbeginn", "pflicht": false}, {"feld": "vertrag.datum", "pflicht": true}, {"feld": "erhoehungsschreiben.wirksam_ab", "pflicht": true}],
     "regel": {"NEIN_wenn": {"alle": [{"eine": [{"feld": "vertrag.preisgarantie_monate", "op": ">", "wert": 0}, {"vorhanden": "vertrag.preisgarantie_bis"}]}, {"eine": [{"alle": [{"vorhanden": "vertrag.preisgarantie_monate"}, {"prim": "monate_zwischen", "args": {"a": ["vertrag.vertragsbeginn", "vertrag.datum"], "b": "erhoehungsschreiben.wirksam_ab"}, "op": "<", "feld": "vertrag.preisgarantie_monate"}]}, {"alle": [{"vorhanden": "vertrag.preisgarantie_bis"}, {"feld": "erhoehungsschreiben.wirksam_ab", "op": "<=", "feld2": "vertrag.preisgarantie_bis"}]}]}]}, "sonst": "JA"},
     "anker": [{"norm": "§ 305b BGB", "key": "bgb_305b", "ebene": "gesetz", "geprueft": false}],
     "rechtsbehelf_bei_NEIN": "widerspruch_rueckforderung",
     "satz_nein": "Der Vertrag enthält eine Preisgarantie über {vertrag.preisgarantie_monate} Monate — die Erhöhung zum {erhoehungsschreiben.wirksam_ab} fällt in diesen Zeitraum.",
     "plain_grund": "Das Studio hat Ihnen den Preis für einen bestimmten Zeitraum zugesichert."},

    {"id": "P4", "titel": "Überraschende Klausel / Unklarheit", "rolle": "tragend", "typ": "text",
     "proposition": "Die Preisklausel ist weder überraschend platziert noch mehrdeutig.",
     "satz_ja": "Die Klausel steht unter der Überschrift „{agb.klausel_ueberschrift}“ — an erwartbarer Stelle und eindeutig bezeichnet.",
     "eingaben": [{"feld": "agb.preisklausel_text", "pflicht": true, "oder": "vertrag.preisklausel_text"}, {"feld": "agb.klausel_ueberschrift", "pflicht": false}],
     "regel": {"JA_wenn": {"alle": [{"verifiziert": "agb.klausel_ueberschrift"}, {"feld": "agb.klausel_ueberschrift", "op": "in", "wert": ["Preise", "Beiträge", "Preisanpassung", "Beitragsanpassung", "Entgelt"]}]}, "sonst": "WERTUNG"},
     "wertungsfrage": "Ist die Klausel an überraschender Stelle oder unter irreführender Überschrift versteckt, oder mehrdeutig formuliert?",
     "anker": [{"norm": "§ 305c BGB", "key": "bgb_305c", "ebene": "gesetz", "geprueft": false}],
     "rechtsbehelf_bei_NEIN": "widerspruch_rueckforderung",
     "plain_grund": "Die Klausel ist versteckt oder unklar."},

    {"id": "P5", "titel": "Kontrollfähigkeit", "rolle": "gate", "typ": "fakt",
     "proposition": "Die Klausel ist ein Preisänderungsvorbehalt (kontrollfähig), keine Vereinbarung des ursprünglichen Preises.",
     "satz_ja": "Die Klausel behält eine Änderung des laufenden Preises vor und ist damit der Inhaltskontrolle zugänglich.",
     "eingaben": [{"feld": "agb.preisklausel_text", "pflicht": true, "oder": "vertrag.preisklausel_text"}],
     "regel": {"NEIN_wenn": {"feld": "gespraech.klausel_ist_urspruenglicher_preis", "op": "==", "wert": true}, "sonst": "JA"},
     "bei_NEIN": {"deaktiviert": ["P6", "P7", "P8", "P9"], "text": "Die Klausel regelt den ursprünglichen Preis — Inhaltskontrolle entfällt, es bleiben die Formalien."},
     "anker": [{"norm": "§ 307 Abs. 3 BGB", "key": "bgb_307_3", "ebene": "gesetz", "geprueft": false}]},

    {"id": "P6", "titel": "Transparenzgebot", "rolle": "tragend", "typ": "text",
     "proposition": "Die Klausel nennt Anlass, Voraussetzungen und Umfang einer Erhöhung so genau, dass die Kundin sie selbst nachvollziehen könnte.",
     "satz_ja": "Die Klausel nennt Anlass, Voraussetzungen und Umfang der Erhöhung.",
     "eingaben": [{"feld": "agb.nennt_anlass", "pflicht": true}, {"feld": "agb.nennt_voraussetzungen", "pflicht": true}, {"feld": "agb.nennt_umfang", "pflicht": true}],
     "regel": {
       "NEIN_wenn": {"alle": [{"eine": [{"feld": "agb.nennt_anlass", "op": "==", "wert": false}, {"feld": "agb.nennt_voraussetzungen", "op": "==", "wert": false}, {"feld": "agb.nennt_umfang", "op": "==", "wert": false}]}, {"verifiziert": "agb.preisklausel_text"}]},
       "JA_wenn": {"alle": [{"feld": "agb.nennt_anlass", "op": "==", "wert": true}, {"feld": "agb.nennt_voraussetzungen", "op": "==", "wert": true}, {"feld": "agb.nennt_umfang", "op": "==", "wert": true}, {"verifiziert": "agb.nennt_anlass"}, {"verifiziert": "agb.nennt_voraussetzungen"}, {"verifiziert": "agb.nennt_umfang"}]},
       "sonst": "WERTUNG"},
     "wertungsfrage": "Reicht die Bestimmtheit der Klausel aus — kann die Kundin Anlass, Voraussetzungen und Umfang einer Erhöhung selbst nachvollziehen?",
     "anker": [{"norm": "§ 307 Abs. 1 S. 2 BGB", "key": "bgb_307_1_2", "ebene": "gesetz", "geprueft": false}],
     "rechtsbehelf_bei_NEIN": "widerspruch_rueckforderung",
     "satz_nein": "Die Klausel sagt nicht, wann und in welchem Umfang erhöht werden darf („{agb.preisklausel_text}“) — das genügt dem Transparenzgebot nicht.",
     "geprueft_von": [{"wer": "Paulina", "am": "2026-08-24", "beleg": "Runde 3, Nachfrage per WhatsApp zu den zwei unsignierten Punkten der Demo-Linie", "umfang": "Best\u00e4tigt den Satz, so wie er im Programm steht: \u201eDie Klausel muss Anlass, Voraussetzungen und Umfang der Erh\u00f6hung nennen. Fehlt eines davon, ist sie intransparent.\u201c Vorgelegt mit \u00a7 307 Abs. 1 S. 2 BGB.", "vorbehalt": "Best\u00e4tigt ist die Regel, nicht ihre Anwendung auf eine einzelne Klausel. Ob eine Klausel den Anlass, die Voraussetzungen und den Umfang tats\u00e4chlich nennt, entscheidet bei uns die Extraktion aus dem Dokument \u2014 nicht sie. Wo diese drei Angaben nicht als gepr\u00fcft vorliegen, geht der Punkt deshalb auf WERTUNG und fragt die Beraterin, statt selbst zu entscheiden."}],
     "plain_grund": "Die Klausel sagt nicht klar, wann und wie stark erhöht werden darf."},

    {"id": "P7", "titel": "Symmetrie- und Kostenweitergabegebot", "rolle": "tragend", "typ": "text",
     "proposition": "Die Klausel beschränkt Erhöhungen auf echte Kostensteigerungen und verpflichtet zur Weitergabe von Kostensenkungen.",
     "satz_ja": "Die Klausel verpflichtet zur Weitergabe von Kostensenkungen und knüpft die Erhöhung an die Kostenentwicklung.",
     "eingaben": [{"feld": "agb.senkungspflicht", "pflicht": true}, {"feld": "agb.kostenbezug", "pflicht": true}],
     "regel": {
       "NEIN_wenn": {"alle": [{"feld": "agb.senkungspflicht", "op": "in", "wert": ["ermessen", "keine"]}, {"verifiziert": "agb.senkungspflicht"}]},
       "JA_wenn": {"alle": [{"feld": "agb.senkungspflicht", "op": "==", "wert": "pflicht"}, {"feld": "agb.kostenbezug", "op": "==", "wert": true}, {"verifiziert": "agb.senkungspflicht"}, {"verifiziert": "agb.kostenbezug"}]},
       "sonst": "WERTUNG"},
     "wertungsfrage": "Ist die Senkungsregel eine echte Pflicht oder nur ein Ermessen, und knüpft die Klausel an Kosten an?",
     "anker": [{"norm": "§ 307 Abs. 1 S. 1, Abs. 2 BGB", "key": "bgb_307_1_1", "ebene": "gesetz", "geprueft": false}],
     "rechtsbehelf_bei_NEIN": "widerspruch_rueckforderung",
     "geprueft_von": [{"wer": "Franz", "am": "2026-08-23", "beleg": "Runde 3, Aufgabe 2 Nr. 3", "umfang": "Die fehlende Symmetrie bleibt ein eigener tragender Prüfungspunkt und geht nicht in der Transparenzprüfung auf."}],
     "plain_grund": "Das Studio darf erhöhen, muss aber nicht senken — das ist einseitig."},

    {"id": "P8", "titel": "Erklärungsfiktion (§ 308 Nr. 5)", "rolle": "tragend", "typ": "fakt",
     "proposition": "Die Klausel verstößt nicht gegen § 308 Nr. 5 (Erklärungsfiktion ohne Mindestanforderungen).",
     "satz_ja": "Die Erhöhung hängt nach den vorliegenden Unterlagen nicht von einer Erklärungsfiktion ohne Frist und Hinweis ab.",
     "eingaben": [{"feld": "erhoehungsschreiben.zustimmungsmechanismus", "pflicht": true}, {"feld": "agb.erklaerungsfiktion_frist_und_hinweis", "pflicht": false}, {"feld": "agb.widerspruchsfrist_tage", "pflicht": false}],
     "regel": {
       "NEIN_wenn": {"eine": [
         {"alle": [{"feld": "erhoehungsschreiben.zustimmungsmechanismus", "op": "==", "wert": "schweigen"}, {"feld": "agb.erklaerungsfiktion_frist_und_hinweis", "op": "==", "wert": false}, {"verifiziert": "agb.erklaerungsfiktion_frist_und_hinweis"}]},
         {"alle": [{"feld": "agb.widerspruchsfrist_tage", "op": "<", "param": "widerspruchsfrist_klar_zu_kurz_tage"}, {"verifiziert": "agb.widerspruchsfrist_tage"}]}]},
       "WERTUNG_wenn": {"eine": [{"feld": "agb.widerspruchsfrist_tage", "op": "<", "param": "widerspruchsfrist_unbedenklich_ab_tage"}]},
       "sonst": "JA"},
     "parameter": {"widerspruchsfrist_klar_zu_kurz_tage": 7, "widerspruchsfrist_unbedenklich_ab_tage": 42, "geprueft": false, "kommentar": "Franz, Runde 3 Aufgabe 2: unter einer Woche klar zu kurz, 14 Tage seine Untergrenze, 4–6 Wochen üblich. Die Untergrenze (14) liegt bewusst NICHT im NEIN-Band: Fall 1 hat genau 14 Tage, und er nennt das selbst „die Crux“ — also WERTUNG, nie NEIN. Paulina hält in demselben Fall die Frist für ausreichend (29 §2.3, sie hat allerdings die Vorlaufzeit gemessen)."},
     "wertungsfrage": "Ist die Widerspruchsfrist in den AGB angemessen (§ 308 Nr. 5 lit. a)?",
     "anker": [{"norm": "§ 308 Nr. 5 BGB", "key": "bgb_308_5", "ebene": "gesetz", "geprueft": false}],
     "rechtsbehelf_bei_NEIN": "widerspruch_rueckforderung",
     "geprueft_von": [{"wer": "Franz", "am": "2026-08-23", "beleg": "Runde 3, Aufgabe 2", "umfang": "§ 308 Nr. 5 lit. a trägt: eine Zustimmungsfiktion greift nicht, wenn die Widerspruchsfrist unangemessen ist. Seine Maßstäbe: unter einer Woche klar zu kurz, 14 Tage Untergrenze, 4 bis 6 Wochen üblich.", "vorbehalt": "Bestätigt ist der Maßstab, nicht die Umsetzung: die Schwellen 7 und 42 Tage sind unsere Übersetzung seiner Worte, und der Bereich dazwischen wird bewusst der Beraterin vorgelegt statt entschieden. Paulina liest lit. a anders: maßgeblich ist für sie die Zeit bis zum Wirksamwerden, weil bis dahin widersprochen werden kann — nach dieser Lesart ist die Frist in Fall 1 ausreichend (Antwort vom 26.08.2026). Die Frage ist zwischen beiden offen; das Programm folgt hier Franz und misst die Widerspruchsfrist."}],
     "satz_nein": [{"wenn": {"alle": [{"feld": "agb.widerspruchsfrist_tage", "op": "<", "param": "widerspruchsfrist_klar_zu_kurz_tage"}, {"verifiziert": "agb.widerspruchsfrist_tage"}]}, "satz": "Die Widerspruchsfrist von {agb.widerspruchsfrist_tage} Tagen ist eindeutig zu kurz — eine Zustimmung kann so nicht fingiert werden (§ 308 Nr. 5 lit. a BGB)."}, {"satz": "Die Klausel fingiert die Zustimmung durch Schweigen, ohne eine angemessene Frist zu setzen und auf die Folgen des Schweigens hinzuweisen (§ 308 Nr. 5 BGB)."}], "plain_grund": "Die Klausel verstößt gegen ein gesetzliches Klauselverbot."},

    {"id": "P8c", "titel": "Formerfordernis für den Widerspruch (§ 309 Nr. 13 lit. b)", "rolle": "tragend", "typ": "fakt",
     "proposition": "Die AGB binden den Widerspruch gegen die Anpassung an keine strengere Form als die Textform.",
     "satz_ja": "Für den Widerspruch verlangen die AGB nach den vorliegenden Unterlagen keine strengere Form als die Textform.",
     "eingaben": [{"feld": "agb.widerspruch_formerfordernis", "pflicht": false}],
     "regel": {
       "NEIN_wenn": {"alle": [{"feld": "agb.widerspruch_formerfordernis", "op": "==", "wert": "schriftform"}, {"verifiziert": "agb.widerspruch_formerfordernis"}]},
       "sonst": "JA"},
     "anker": [{"norm": "§ 309 Nr. 13 lit. b BGB", "key": "bgb_309_13", "ebene": "gesetz", "geprueft": false}],
     "rechtsbehelf_bei_NEIN": "widerspruch_rueckforderung",
     "satz_nein": "Die AGB verlangen für den Widerspruch Schriftform („{zitat}“) — strenger als die Textform, die § 309 Nr. 13 lit. b BGB als Obergrenze zulässt. Die Formvorgabe ist unwirksam; ein mündlicher oder per E-Mail erklärter Widerspruch zählt. Und weil die AGB damit keinen wirksamen Weg für die ausdrückliche Erklärung eröffnen, greift die Zustimmungsfiktion auch dann nicht, wenn gar nicht widersprochen wurde.",
     "plain_grund": "Das Studio verlangt für den Widerspruch eine Unterschrift — das darf es nicht, eine E-Mail oder ein Wort an der Rezeption reicht.",
     "geprueft_von": [{"wer": "Paulina", "am": "2026-08-24", "beleg": "Runde 3, Aufgabe 2", "umfang": "§ 309 Nr. 13 trägt: „schriftlich“ wird regelmäßig als Schriftform i. S. d. § 126 BGB ausgelegt, das ist strenger als Textform; die Klausel ist ein eigener Unwirksamkeitsgrund neben der Fiktion, und weil damit kein funktionierender Erklärungsweg eröffnet ist, greift die Fiktion nach § 308 Nr. 5 lit. a auch ohne Widerspruch nicht.", "vorbehalt": "Sie zitiert die Norm ohne Buchstaben; der amtliche Text hat a/b/c als Alternativen, lit. b ist der Fitness-Fall — Zitierweise ist unsere Korrektur, die Subsumtion ihre. Franz hat zur selben Frage widersprüchlich geantwortet; die Umsetzung als harter NEIN-Punkt stützt sich auf ihre Antwort allein. Nicht bestätigt: ob „schriftlich“ im Einzelfall doch als Textform auszulegen ist — dafür steht das Feld auf textform."}]},
    {"id": "P8d", "titel": "Laufzeit und Verlängerung (§ 309 Nr. 9, Hinweis)", "rolle": "ergaenzend", "typ": "fakt",
     "proposition": "Die Laufzeit- und Verlängerungsregel des Vertrags verstößt nicht gegen § 309 Nr. 9 BGB.",
     "satz_ja": "Nach den vorliegenden Unterlagen überschreitet die Laufzeit 24 Monate nicht, und eine Verlängerungsklausel liegt nicht vor.",
     "eingaben": [{"feld": "vertrag.laufzeit_monate", "pflicht": false}, {"feld": "vertrag.verlaengerung_text", "pflicht": false}],
     "regel": {
       "WERTUNG_wenn": {"eine": [{"feld": "vertrag.laufzeit_monate", "op": ">", "wert": 24}, {"vorhanden": "vertrag.verlaengerung_text"}]},
       "sonst": "JA"},
     "wertungsfrage": "Verstößt die Laufzeit-/Verlängerungsregel gegen § 309 Nr. 9 BGB (Fassung seit 01.03.2022; für davor geschlossene Verträge gilt die alte Fassung, Art. 229 § 60 EGBGB)?",
     "anker": [{"norm": "§ 309 Nr. 9 BGB (Fassung seit 01.03.2022)", "key": "bgb_309_9", "ebene": "gesetz", "geprueft": false}],
     "pruefumfang_text": "Hinweis: Die Laufzeit- oder Verlängerungsregel ist möglicherweise unwirksam (§ 309 Nr. 9) — das betrifft nicht die Preiserhöhung (§ 306 Abs. 1: der Vertrag bleibt im Übrigen wirksam), wohl aber die Kündigung und den Zeitraum, in dem die Erhöhung noch droht."},

    {"id": "P8b", "titel": "Leistungsänderungsrecht (Hinweis)", "rolle": "ergaenzend", "typ": "fakt",
     "proposition": "Die AGB enthalten kein Leistungsänderungsrecht ohne triftigen Grund.",
     "satz_ja": "Nach den vorliegenden Unterlagen enthalten die AGB kein Leistungsänderungsrecht ohne triftigen Grund.",
     "eingaben": [{"feld": "agb.leistungsaenderungsrecht", "pflicht": false}, {"feld": "agb.leistungsaenderung_mit_grund", "pflicht": false}],
     "regel": {"NEIN_wenn": {"alle": [{"feld": "agb.leistungsaenderungsrecht", "op": "==", "wert": true}, {"feld": "agb.leistungsaenderung_mit_grund", "op": "==", "wert": false}]}, "sonst": "JA"},
     "anker": [{"norm": "§ 308 Nr. 4 BGB", "key": "bgb_308_4", "ebene": "gesetz", "geprueft": false}],
     "pruefumfang_text": "Hinweis: Die AGB enthalten ein Leistungsänderungsrecht ohne Grund — betrifft nicht die Preiserhöhung selbst, aber die Beratung."},

    {"id": "P9", "titel": "Zustimmungsfiktion", "rolle": "tragend", "typ": "fakt",
     "proposition": "Das Schreiben wertet weder Schweigen noch Weiternutzung als Zustimmung zur Preisänderung.",
     "satz_ja": "Das Schreiben wertet nach den vorliegenden Unterlagen weder Schweigen noch Weiternutzung als Zustimmung.",
     "eingaben": [{"feld": "erhoehungsschreiben.zustimmungsmechanismus", "pflicht": true}],
     "regel": {"NEIN_wenn": {"alle": [{"feld": "erhoehungsschreiben.zustimmungsmechanismus", "op": "in", "wert": ["schweigen", "weiternutzung"]}, {"verifiziert": "erhoehungsschreiben.zustimmungsmechanismus"}]}, "sonst": "JA"},
     "anker": [
       {"norm": "§ 308 Nr. 5 BGB", "key": "bgb_308_5", "ebene": "gesetz", "geprueft": false},
       {"gericht": "BGH", "az": "XI ZR 26/20", "datum": "2021-04-27", "key": "bgh_xi_zr_26_20", "ebene": "dogmatik", "status": "gefestigt", "geprueft": false, "kernaussage": "Zustimmungsfiktion in AGB für Entgeltänderungen unwirksam (Banken); die Begründung ist allgemeines Vertragsrecht, nicht Bankrecht. Auf Fitness angewandt von LG Bamberg 13 O 730/22, das dieses Urteil ausdrücklich zitiert."},
       {"gericht": "LG Bamberg", "az": "13 O 730/22", "datum": "2024-03-15", "key": "lg_bamberg_13_o_730_22", "ebene": "rechtsanwendung", "status": "gefestigt", "geprueft": true, "klaeger": "vzbv", "kernaussage": "Drehkreuz/Weiternutzung als Zustimmung = aggressive geschäftliche Handlung"}],
     "rechtsbehelf_bei_NEIN": "widerspruch_rueckforderung",
     "satz_nein": "Das Schreiben wertet {erhoehungsschreiben.zustimmungsmechanismus} als Zustimmung („{zitat}“) — Schweigen oder Weitertrainieren ist keine Zustimmung.",
     "leitfaden_frage": {"text": "Sind Sie nach dem Schreiben weiter ins Studio gegangen?", "typ": "ja_nein", "fuellt": "gespraech.weiternutzung_erfolgt", "hinweis": "ändert die Einordnung nicht; relevant für Rückforderung und Gespräch"},
     "geprueft_von": [{"wer": "Paulina", "am": "2026-08-24", "beleg": "Runde 3, Nachfrage per WhatsApp zu den zwei unsignierten Punkten der Demo-Linie", "umfang": "Bestätigt den Satz, so wie er im Programm steht: \u201eSchweigen oder Weitertrainieren ist keine Zustimmung zu einem h\u00f6heren Beitrag.\u201c Vorgelegt mit den drei Fundstellen \u00a7 308 Nr. 5 BGB, BGH XI ZR 26/20 und LG Bamberg 13 O 730/22.", "vorbehalt": "Best\u00e4tigt ist der Satz, nicht seine Unbedingtheit und nicht die Fundstellen. Zwei Dinge deckt ihre Zusage nicht: (1) Unsere Regel gilt ohne Ausnahme, w\u00e4hrend Franz\u2019 Antwort aus Runde 3 sich liest, als sei die Fiktion bei angemessener Frist in Ordnung \u2014 diese Spannung ist offen. (2) BGH XI ZR 26/20 ist eine Bankensache; die \u00dcbertragbarkeit auf Fitness hat Paulina am 26.08.2026 bejaht \u2014 LG Bamberg 13 O 730/22 wendet das Urteil ausdr\u00fccklich an. Das Bamberger Urteil hat sie am 26.08.2026 im Original gelesen \u2014 es ist der erste best\u00e4tigte Anker im Bestand. Offen bleibt das Urteil des BGH selbst: das hat niemand aus dem Team im Original gelesen, deshalb steht dieser eine Anker weiter auf \u201eungepr\u00fcft\u201c."}],
     "plain_grund": "Weitertrainieren oder Schweigen gilt nicht als Zustimmung zu einem höheren Beitrag."},

    {"id": "P10", "titel": "Formalien des Erhöhungsschreibens", "rolle": "tragend", "typ": "fakt",
     "proposition": "Das Schreiben ist in zumutbarer Form und rechtzeitig zugegangen, nennt was sich ab wann ändert, und weist auf ein bestehendes Kündigungsrecht hin.",
     "satz_ja": "Das Schreiben nennt, was sich ab wann ändert; ein Kündigungshinweis fehlt nicht, wo er nötig wäre.",
     "eingaben": [{"feld": "erhoehungsschreiben.datum", "pflicht": true}, {"feld": "erhoehungsschreiben.zugang", "pflicht": false}, {"feld": "erhoehungsschreiben.wirksam_ab", "pflicht": true}, {"feld": "erhoehungsschreiben.form", "pflicht": true}, {"feld": "erhoehungsschreiben.kuendigungshinweis", "pflicht": true}, {"feld": "agb.kuendigungsrecht_bei_erhoehung", "pflicht": false}],
     "parameter": {"frist_min_tage": 30, "geprueft": false, "kommentar": "Franz: welche Vorlaufzeit ist bei Fitnessverträgen angemessen? Bis dahin WERTUNG, nie NEIN"},
     "regel": {
       "NEIN_wenn": {"alle": [{"feld": "agb.kuendigungsrecht_bei_erhoehung", "op": "==", "wert": true}, {"feld": "erhoehungsschreiben.kuendigungshinweis", "op": "==", "wert": false}, {"verifiziert": "erhoehungsschreiben.kuendigungshinweis"}]},
       "WERTUNG_wenn": {"eine": [{"prim": "tage_zwischen", "args": {"a": "erhoehungsschreiben.zugang", "b": "erhoehungsschreiben.wirksam_ab"}, "op": "<", "param": "frist_min_tage"}, {"feld": "erhoehungsschreiben.form", "op": "in", "wert": ["aushang", "website"]}]},
       "sonst": "JA"},
     "wertungsfrage": "War die Vorlaufzeit angemessen, und genügt die gewählte Form (Aushang/Website statt persönlicher Mitteilung)?",
     "frist": {"name": "Vorlaufzeit", "prim": "tage_zwischen", "args": {"a": "erhoehungsschreiben.zugang", "b": "erhoehungsschreiben.wirksam_ab"}, "anzeige": "{wert} Tage · Stand {stichtag}"},
     "anker": [],
     "rechtsbehelf_bei_NEIN": "widerspruch_rueckforderung_vergangenheit",
     "geprueft_von": [{"wer": "Franz", "am": "2026-08-23", "beleg": "Runde 3, Aufgabe 3", "umfang": "Es gibt keine pauschale gesetzliche Vorlauffrist. Die vertraglich vereinbarte Frist gilt, und ihr Unterschreiten ist eine Vertragsverletzung, die keiner Bewertung mehr bedarf.", "vorbehalt": "Das Programm rechnet hier noch gegen eine feste Zahl von 30 Tagen. Nach seiner Antwort gibt es die gar nicht — maßgeblich ist die Frist, die der Vertrag selbst nennt. Steht dort eine, gilt sie."}],
     "plain_grund": "Das Schreiben genügt den Formalien nicht: Vorlaufzeit, Form oder der Hinweis auf das Kündigungsrecht."},

    {"id": "P11", "titel": "Ausübungskontrolle § 315", "rolle": "ergaenzend", "typ": "wertung",
     "proposition": "Die Höhe der Erhöhung ist durch die Kostenentwicklung gerechtfertigt.",
     "eingaben": [{"feld": "kostenkalkulation.vorhanden", "pflicht": false}],
     "regel": {"WERTUNG_wenn": {"dok_vorhanden": "kostenkalkulation"}, "sonst": "FEHLT"},
     "fehlt_owner": "unternehmen",
     "anker": [{"norm": "§ 315 Abs. 3 BGB", "key": "bgb_315_3", "ebene": "gesetz", "geprueft": false}, {"norm": "BGH VIII ZR 138/07", "key": "bgh_viii_zr_138_07", "ebene": "rechtsanwendung", "geprueft": false}],
     "rechtsbehelf_bei_FEHLT": "auskunftsverlangen_vorbehalt",
     "pruefumfang_text": "NICHT geprüft: ob die Höhe der Erhöhung angemessen ist (§ 315 BGB) — dazu fehlt die Kostenkalkulation des Studios."},

    {"id": "P14", "titel": "Langes widerspruchsloses Zahlen (Wertungsfrage)", "rolle": "ergaenzend", "typ": "wertung",
     "proposition": "In der widerspruchslosen Zahlung des erhöhten Beitrags liegt keine konkludente Zustimmung.",
     "satz_ja": "Die Wertungsfrage stellt sich hier nicht: nach den vorliegenden Angaben sind sechs Monate widerspruchslosen Zahlens nicht erreicht.",
     "eingaben": [{"feld": "gespraech.monate_erhoeht_gezahlt", "pflicht": false}],
     "regel": {"WERTUNG_wenn": {"feld": "gespraech.monate_erhoeht_gezahlt", "op": ">=", "wert": 6}, "sonst": "JA"},
     "wertungsfrage": "Die Verbraucherin hat {gespraech.monate_erhoeht_gezahlt} Monate den erhöhten Beitrag widerspruchslos gezahlt — kann darin eine stillschweigende Zustimmung liegen?",
     "leitfaden_frage": {"text": "Seit wie vielen Monaten zahlen Sie den erhöhten Beitrag?", "typ": "zahl", "fuellt": "gespraech.monate_erhoeht_gezahlt"},
     "anker": [], "geprueft": false,
     "pruefumfang_text": "Offen: ob langes widerspruchsloses Zahlen als Zustimmung gewertet werden kann — Einschätzung der Beraterin."},

    {"id": "P12", "titel": "Rechtsfolgen bei Unwirksamkeit", "rolle": "ableitung",
     "eingaben": [{"feld": "kontoauszug.abbuchungen", "pflicht": false}, {"feld": "vertrag.beitrag", "pflicht": true}, {"feld": "erhoehungsschreiben.wirksam_ab", "pflicht": true}],
     "nur_wenn": {"feld": "einordnung", "op": "==", "wert": "wahrscheinlich unwirksam"},
     "berechnung": {"prim": "summe_rueckforderung", "args": {}},
     "fristen": [{"name": "Verjährung Rückforderung", "regel": "3 Jahre ab Jahresende der Zahlung", "anker": ["bgb_195", "bgb_199"]}, {"name": "SEPA-Rückbuchung", "regel": "8 Wochen ab Belastung", "anker": [], "geprueft": false}],
     "anker": [{"norm": "§ 306 BGB", "key": "bgb_306", "ebene": "gesetz", "geprueft": false}, {"norm": "§ 812 BGB", "key": "bgb_812", "ebene": "gesetz", "geprueft": false}, {"norm": "§§ 195, 199 BGB", "key": "bgb_195", "ebene": "gesetz", "geprueft": false}],
     "betrag": {"name": "Rückforderung", "anzeige": "{betrag} € (Annahme: alle Abbuchungen seit {erhoehungsschreiben.wirksam_ab} belegt)"}},

    {"id": "P13", "titel": "Nächster Schritt", "rolle": "strategie",
     "leitfaden_frage": {"text": "Möchten Sie im Studio bleiben und nur den alten Beitrag zahlen — oder kündigen? Und sollen zu viel gezahlte Beträge zurückgefordert werden?", "typ": "mehrfach", "fuellt": ["gespraech.strategie", "gespraech.rueckforderung_gewuenscht"], "werte": {"gespraech.strategie": ["bleiben", "kuendigen", "offen"]}, "feld_labels": {"gespraech.strategie": "Bleiben oder kündigen?", "gespraech.rueckforderung_gewuenscht": "Rückforderung gewünscht?"}, "wert_labels": {"gespraech.strategie": {"bleiben": "bleiben", "kuendigen": "kündigen", "offen": "noch offen"}}}}
  ],

  "aggregation": {
    "AND": "NEIN wenn ein aktives Kind NEIN; sonst FEHLT wenn eines FEHLT; sonst WERTUNG wenn eines WERTUNG; sonst JA. INAKTIV-Kinder werden ignoriert; ein Knoten ohne aktive Kinder ist INAKTIV.",
    "OR": "JA wenn ein aktives Kind JA; sonst WERTUNG wenn eines WERTUNG; sonst FEHLT wenn eines FEHLT; sonst NEIN.",
    "nur_rolle": ["tragend"],
    "gates": "Ein gate-Prüfpunkt trägt nie zur Einordnung bei. gate NEIN mit schema_stopp → Einordnung wird nicht berechnet; Fallakte zeigt den bei_NEIN.text, Gate 2 bietet Fallgruppe-Wechsel/Sonstiges an; Ereignis schema_stopp. gate NEIN mit deaktiviert → die genannten Prüfpunkte erhalten zustand INAKTIV (Prüfumfang: „nicht anwendbar“).",
    "einordnung": {
      "wahrscheinlich unwirksam": "root == NEIN",
      "unklar – es fehlt …": "root == FEHLT → es fehlt: fehlende Eingaben der tragenden FEHLT-Prüfpunkte (nach owner gruppiert) · root == WERTUNG → es fehlt: Bewertung durch die Beraterin zu <wertungsfrage> (Gate 3 entscheidet per override)",
      "wirksam": "root == JA (alle aktiven tragenden Prüfpunkte JA)"
    },
    "vollstaendigkeit": "unabhängig von der Einordnung: alle FEHLT über alle Prüfpunkte inkl. ergaenzend, nach quelle gruppiert — verbraucher → Nachforderung (Gate 1), unternehmen → Auskunftsverlangen/Bestreiten (Gate 4); Pflicht-Dokumente, die fehlen, auch ohne Prüfpunkt",
    "gerissene_stufe": "erste Stufe S1…S4 mit Zustand NEIN — bestimmt den Rechtsbehelf",
    "pruefumfang": "alle WERTUNG/FEHLT/INAKTIV-Prüfpunkte mit pruefumfang_text oder wertungsfrage; immer sichtbar"
  },

  "rechtsbehelfe": {
    "garantie_pro_zweig": {
      "wahrscheinlich unwirksam": ["widerspruch_rueckforderung"],
      "unklar – es fehlt …": ["nachforderung", "bestreiten_nachweise_verlangen"],
      "wirksam": ["kuendigung_bei_wirksam", "auskunftsverlangen_vorbehalt"]
    },
    "liste": [
      {"id": "rueckforderung_ohne_erklaerung", "titel": "Rückforderung — Erhöhung nie erklärt", "wenn": {"feld": "pruefpunkt.P1a.zustand", "op": "==", "wert": "NEIN"}, "musterbrief": "musterbrief_fitness_rueckforderung_ohne_erklaerung", "geprueft": false, "kommentar": "Franz zu Fall 6 (30 §9): ohne Erklärung entfällt der Rechtsgrund, § 812 Abs. 1 S. 1 BGB. Verdrängt in diesem Zweig den Widerspruch — es gibt nichts, dem man widersprechen könnte."},
      {"id": "widerspruch_rueckforderung", "titel": "Widerspruch + Rückforderung", "wenn": {"alle": [{"feld": "gerissene_stufe", "op": "in", "wert": ["S1", "S2", "S3"]}, {"nicht": {"feld": "pruefpunkt.P1a.zustand", "op": "==", "wert": "NEIN"}}]}, "musterbrief": "musterbrief_fitness_widerspruch_rueckforderung", "geprueft": false},
      {"id": "widerspruch_rueckforderung_vergangenheit", "titel": "Widerspruch + Rückforderung für die Vergangenheit (formeller Mangel, heilbar)", "wenn": {"feld": "gerissene_stufe", "op": "==", "wert": "S4"}, "musterbrief": "musterbrief_fitness_widerspruch", "geprueft": false},
      {"id": "nachforderung", "titel": "Unterlagen nachfordern", "wenn": {"alle": [{"feld": "einordnung", "op": "==", "wert": "unklar – es fehlt …"}, {"feld": "fehlt_verbraucher", "op": "!=", "wert": []}]}, "musterbrief": "nachforderung_{kanal}", "empfaenger": "verbraucher"},
      {"id": "bestreiten_nachweise_verlangen", "titel": "Nachweise vom Unternehmen verlangen", "wenn": {"alle": [{"feld": "einordnung", "op": "==", "wert": "unklar – es fehlt …"}, {"feld": "fehlt_unternehmen", "op": "!=", "wert": []}]}, "musterbrief": "musterbrief_auskunftsverlangen", "geprueft": false},
      {"id": "auskunftsverlangen_vorbehalt", "titel": "Zahlung unter Vorbehalt + Auskunftsverlangen", "wenn": {"feld": "einordnung", "op": "==", "wert": "wirksam"}, "musterbrief": "musterbrief_auskunftsverlangen", "geprueft": false},
      {"id": "kuendigung_bei_wirksam", "titel": "Kündigung (Sonderkündigung falls Klausel sie einräumt, sonst ordentlich)", "wenn": {"feld": "einordnung", "op": "==", "wert": "wirksam"}, "musterbrief": "musterbrief_kuendigung", "geprueft": false, "kommentar": "Franz’ Aufgabe 3 entscheidet Sonderkündigung vs ordentlich — bis dahin beide Varianten im Template"}
    ],
    "ranking": "hauptvorschlag = erster Treffer in garantie_pro_zweig[einordnung]; gespraech.strategie == 'kuendigen' zieht kuendigung_bei_wirksam nach vorn; alle weiteren Treffer als vorschlaege[]"
  },

  "beratungshinweise": [
    {"id": "H6", "art": "warnung", "titel": "Das Schreiben zitiert seine eigene Klausel falsch", "text": "Der Klauseltext, den das Schreiben in Anf\u00fchrungszeichen setzt, steht so nicht in den AGB. Das Programm hat mit dem Wortlaut aus den AGB gerechnet und den aus dem Schreiben nicht verwendet. Sehen Sie sich die beiden Fassungen nebeneinander an, bevor Sie antworten.", "wenn": {"prim": "klauselzitat_stimmt", "args": {}, "op": "==", "wert": false}, "anker": []},
    {"id": "H7", "art": "warnung", "titel": "Die Entscheidung, auf die sich das Schreiben beruft, kennen wir nicht", "text": "Das Schreiben st\u00fctzt sich auf eine Fundstelle, die in unserer Normbasis nicht vorkommt. Das Programm hat sie deshalb nicht verwendet \u2014 weder f\u00fcr noch gegen die Erh\u00f6hung. Bevor Sie darauf eingehen, pr\u00fcfen Sie, ob es die Entscheidung gibt und ob sie den Fall wirklich betrifft.", "wenn": {"alle": [{"feld": "erhoehungsschreiben.zitierte_fundstellen", "op": "!=", "wert": []}, {"prim": "normbasis_treffer", "args": {"liste": "erhoehungsschreiben.zitierte_fundstellen"}, "op": "==", "wert": 0}]}, "anker": []},
    {"id": "H1", "art": "warnung", "titel": "Die Lastschrift nicht zurückgeben lassen",
     "text": "Sagen Sie der Kundin, bevor sie danach fragt: Die erste erhöhte Abbuchung nicht über die Bank zurückgehen lassen. Das Geld kommt nicht über die Rücklastschrift zurück, sondern über einen Rückzahlungsanspruch gegen das Unternehmen. Eine zurückgegebene Lastschrift setzt sie dagegen in Verzug, kostet eine Rücklastschriftpauschale (im Bestand 3,50 € und 12,00 €) und führt im schlechtesten Fall zu genau dem Inkassoverfahren, vor dem sie Angst hat. Der bessere Weg: unter Vorbehalt weiterzahlen und zurückfordern.",
     "wenn": {"vorhanden": "erhoehungsschreiben.wirksam_ab"},
     "anker": [{"norm": "§ 286 BGB", "key": "bgb_286", "ebene": "gesetz", "geprueft": false}],
     "geprueft_von": [{"wer": "Franz", "am": "2026-08-23", "beleg": "Runde 3, Aufgabe 1", "umfang": "Der Rückerhalt läuft nicht über den Widerruf gegenüber der Bank, sondern über einen Rückzahlungsanspruch gegen den Empfänger."}]},

    {"id": "H5", "art": "hebel", "titel": "Zahlung unter Vorbehalt — zweimal, nicht einmal", "text": "Wenn die Kundin weiterzahlt, gehören zwei Dinge zusammen: der Satz im Schreiben an das Unternehmen (steht im Musterschreiben) und der Verwendungszweck der Überweisung. Lassen Sie sie dort „Zahlung unter Vorbehalt“ eintragen. Der Grund ist nicht Förmlichkeit: bestünde die Forderung am Ende doch, gerät sie ohne den Vorbehalt in Bedrängnis wegen Mahngebühren und Verzug — und mit ihm nicht.", "wenn": {"eine": [{"feld": "einordnung", "op": "==", "wert": "wirksam"}, {"feld": "einordnung", "op": "==", "wert": "unklar – es fehlt …"}]}, "anker": [], "geprueft_von": [{"wer": "Franz", "am": "2026-08-23", "beleg": "Runde 3, Aufgabe 1", "umfang": "Zahlung unter Vorbehalt gehört in den Verwendungszweck und/oder in ein Schreiben an den Zahlungsempfänger, ausdrücklich ohne Anerkennung einer Rechtspflicht und unter Vorbehalt der Rückforderung — sonst drohen Mahngebühren, falls die Forderung doch besteht."}]},

    {"id": "H2", "art": "hebel", "titel": "Die Darlegungslast liegt beim Verwender",
     "text": "Die Kundin muss nichts beweisen. Wer sich auf eine Klausel in Allgemeinen Geschäftsbedingungen beruft, muss darlegen, dass sie einbezogen wurde und wie sie lautete. Das Auskunftsverlangen darf das ausdrücklich sagen — ohne Paragraf, so wie die Musterbriefe der Verbraucherzentrale es auch tun.",
     "wenn": {"eine": [{"feld": "pruefpunkt.P2.zustand", "op": "==", "wert": "FEHLT"}, {"feld": "pruefpunkt.P5.zustand", "op": "==", "wert": "FEHLT"}]},
     "anker": [],
     "geprueft_von": [{"wer": "Franz", "am": "2026-08-23", "beleg": "Runde 2, Gutachten zu Fall 3", "umfang": "Auch ohne die fehlende AGB-Seite steht fest, dass die Darlegungslast beim Verwender liegt."}]},
     {"id": "H8", "art": "hebel", "titel": "Die Unterlagen kann die Kundin beim Anbieter verlangen",
      "text": "Wenn die Kundin ihre AGB oder ihren Vertrag nicht mehr hat, ist sie nicht darauf angewiesen, sie wiederzufinden — sie kann sie beim Anbieter anfordern. Aus dem laufenden Vertrag folgt die Nebenpflicht, ihr die eigenen Vertragsunterlagen zugänglich zu machen (§ 241 Abs. 2 BGB); gibt der Anbieter sie nicht heraus, ist das eine Pflichtverletzung. Im Brief an die Kundin steht davon nur der praktische Schritt und kein Paragraf — so wie die Musterbriefe der Verbraucherzentrale es auch tun. Der Paragraf steht hier, damit Sie ihn nennen können, wenn das Studio mauert.",
      "wenn": {"feld": "fehlt_verbraucher", "op": "!=", "wert": []},
      "anker": [{"norm": "§ 241 Abs. 2 BGB", "key": "bgb_241_2", "ebene": "gesetz", "geprueft": false}],
      "geprueft_von": [{"wer": "Franz", "am": "2026-08-26", "beleg": "Runde 4, Redigat des Nachforderungsbriefs",
        "umfang": "Die Nichtbereitstellung der Vertragsunterlagen ist eine Verletzung der vertraglichen Nebenpflicht aus § 241 Abs. 2 BGB.",
        "vorbehalt": "Er wollte den Paragrafen in den Brief an die Kundin schreiben. Paulina hat am selben Tag an den acht Musterbriefen der Verbraucherzentrale abgelesen, dass dort keine Paragrafen stehen. Deshalb steht der Inhalt im Brief und der Paragraf auf diesem Schirm — die Entscheidung ist unsere, nicht seine."}]},

    {"id": "H3", "art": "hebel", "titel": "Zwei Hebel — sehen Sie im Vertrag nach, das Programm kann es nicht?",
     "text": "Wenn Sie Unterlagen beim Unternehmen statt bei der Kundin holen wollen, lohnen zwei Blicke in den Vertrag, die das Programm nicht selbst prüfen kann. Erstens: Steht im Unterschriftsblock eine Bestätigung, die AGB erhalten zu haben, und ist sie mit SEPA-Mandat und Widerrufsbelehrung zu einer einzigen Unterschrift gebündelt? Dann ist sie als Beweislastumkehr angreifbar (§ 309 Nr. 12 lit. b BGB); die Ausnahme für gesondert unterschriebene Empfangsbekenntnisse greift bei einer gebündelten Unterschrift nicht. Zweitens: Nennt das Formular als Ort der Unterzeichnung die Wohnung der Kundin? Dann besteht ein zweiter, unabhängiger Anspruch auf die vollständigen Vertragsbedingungen (§ 312f Abs. 1 BGB).",
     "wenn": {"feld": "fehlt_verbraucher", "op": "!=", "wert": []},
     "anker": [],
     "geprueft_von": [{"wer": "Franz", "am": "2026-08-23", "beleg": "Runde 2, Gutachten zu Fall 3", "umfang": "Beide Hebel benannt und begründet, ausdrücklich als Argumente für die Nachforderung und nicht als Prüfpunkte.", "vorbehalt": "Ob sie hier greifen, hängt an zwei Tatsachen, die wir nicht extrahieren: ob es eine gebündelte Bestätigungsklausel gibt und wo unterschrieben wurde. Deshalb steht hier eine Frage an Sie und keine Feststellung."}]},

    {"id": "H4", "art": "merker", "titel": "Bei jungen Verträgen zuerst die Widerrufsbelehrung",
     "text": "Der Vertrag ist noch keine 13 Monate alt. Prüfen Sie vor der Klauselkontrolle die Widerrufsbelehrung: Ist sie fehlerhaft, läuft die Widerrufsfrist noch, und das trägt oft schneller als die Inhaltskontrolle der AGB.",
     "wenn": {"prim": "tage_zwischen", "args": {"a": "vertrag.datum", "b": "heute"}, "op": "<", "wert": 379},
     "anker": [{"norm": "§ 356 BGB", "key": "bgb_356", "ebene": "gesetz", "geprueft": false}],
     "geprueft_von": [{"wer": "Franz", "am": "2026-08-23", "beleg": "Runde 2, Gutachten zu Fall 3", "umfang": "Bei jüngeren Verträgen stets mitprüfen; eine fehlerhafte Widerrufsbelehrung trägt oft schneller als die AGB-Kontrolle.", "vorbehalt": "Die Grenze von 379 Tagen (12 Monate und 14 Tage, § 356 Abs. 4 BGB) ist unsere Umrechnung seiner Aussage, nicht seine Zahl."}]}
  ],
  "plain_saetze": {
    "wahrscheinlich unwirksam": "Die Erhöhung steht auf wackeligen Beinen: {plain_grund_hauptpruefpunkt} Sie können widersprechen und den alten Beitrag weiterzahlen.",
    "unklar – es fehlt …": "Ob die Erhöhung wirksam ist, lässt sich noch nicht sagen — dazu brauchen wir noch {fehlende_liste_plain}.",
    "wirksam": "Die Erhöhung ist nach den vorliegenden Unterlagen nicht zu beanstanden. Sie können bleiben und zahlen — oder kündigen."
  }
}
```

Notes: (i) `zitat_pflicht` fields: the quote is the examined clause span; a `false` value still carries the span that was examined. (ii) `oder` on an eingabe means either field satisfies it (Klausel in AGB or in Vertrag). (iii) For `typ: text` Prüfpunkte the result carries `llm_befund: true`. (iv) `geprueft:false` anchors render grey and are blocked from slides; regel-level judgments flagged via `geprueft_hinweis`.

## 3. Schema skeletons — inkasso (B), kuendigung/klausel_check (C)

`schemas/inkasso.json`: `stufe: "B"`, `pruefpunkte: []`, `dokumenten_soll` **provisional from Paulina's four Runde-1 cases** (replaced 1:1 by her Runde-2 list via the ingest adapter in §13): `inkassoschreiben` (immer, felder: absender, auftraggeber, aktenzeichen, gesamtbetrag, hauptforderung, zinsen, kosten, zahlungsfrist, datum, abtretung_erwaehnt, rechnung_erwaehnt, registereintrag_angabe, zitierte_fundstellen) · `rechnung` (immer) · `auftragsbestaetigung` (immer: vertragsdatum, laufzeit, betrag, widerrufsbelehrung_text, widerrufsfrist_angabe, kontaktweg) · `widerrufsbelehrung` (erwartet_wenn_vorhanden) · `anschreiben` (bedingt: der irreführende Auslöser-Brief) · `abtretungsurkunde` (bedingt: {"feld": "inkassoschreiben.abtretung_erwaehnt", "op": "==", "wert": true}; quelle unternehmen) · `vollmacht` (bedingt: nicht abgetreten; quelle unternehmen) · `email` (bedingt). Remedy ids reserved: `widerruf`, `anfechtung_taeuschung`, `bestreiten_nachweise_verlangen`. Stufe B→A: set `stufe:"A"` once `pruefpunkte` non-empty and `geprueft_von` non-empty — no other change. `eingang.gegner` (Inkassobüro) + `eingang.anbieter` (Auftraggeber) both cluster keys.

`schemas/kuendigung.json`, `schemas/klausel_check.json`: `{fallgruppe_id, name, stufe: "C", pruefpunkte: [], dokumenten_soll: {dokumente: []}}`.

## 4. Case object — `cases/<case_id>.json`

```json
{
  "case_id": "F-2026-0001",
  "schema": {"fallgruppe_id": "preiserhoehung", "version": "0.2.0", "stand": "2026-08-23"},
  "status": "offen",
  "stichtag": "2026-08-27",
  "eingang": {"kanal": "vbs", "ticket_nr": "VBS-48213", "thema": "Allgemeines Verbraucherrecht", "freitext_original": "…", "freitext_pseudonym": "…",
              "anbieter": "FitPoint 24", "anbieter_quelle": "extrahiert|beraterin", "gegner": null, "branche": "fitness", "eingegangen_am": "…",
              "identitaet": {"name": "…", "adresse": "…", "email": "…", "telefon": "…"}, "sensible_inhalte_flag": false},
  "pseudonyme": {"@@PERSON_1@@": "Ingeborg Maier", "@@ADRESSE_1@@": "…", "@@KUNDENNR_1@@": "…"},
  "dokumente": [
    {"dok_id": "D1", "dokumenttyp": "erhoehungsschreiben", "dateiname": "schreiben.pdf", "hash": "…", "seiten": [{"nr": 1, "text_original": "…", "text_pseudonym": "…"}], "quelle": "verbraucher", "eingegangen": "eingang", "typ_konfidenz": 0.98, "typ_bestaetigt": true},
    {"dok_id": "D2", "dokumenttyp": "agb", "eingegangen": "nachreichung", "nachforderung_id": "N1", "fassung_datum": "2022-01-01"}
  ],
  "fakten": [
    {"feld_id": "erhoehungsschreiben.zustimmungsmechanismus", "dok_id": "D1", "wert": "weiternutzung", "herkunft": "explizit",
     "quelle": {"dok_id": "D1", "seite": 1, "zitat_pseudonym": "Mit Ihrem nächsten Check-in am Drehkreuz stimmen Sie dem neuen Beitrag zu.", "offset": null}, "verifiziert": true, "badge": "verifiziert", "llm_run": "R1"},
    {"feld_id": "erhoehungsschreiben.zugang", "dok_id": "D1", "wert": "2026-08-05", "herkunft": "angenommen", "annahme_id": "zugang_plus_3", "verifiziert": null, "badge": "angenommen"},
    {"feld_id": "gespraech.weiternutzung_erfolgt", "wert": true, "herkunft": "gespraech", "von": "Beraterin", "zeit": "…"}
  ],
  "fallgruppe": {"vorschlaege": [{"id": "preiserhoehung", "begruendung": "…", "zitate": ["…"]}], "gewaehlt": "preiserhoehung", "stufe": "A", "gate2_von": "Beraterin", "zeit": "…"},
  "dokumenten_soll": {"vollstaendig": false, "fehlt": [{"dokumenttyp": "agb", "feld_id": null, "quelle": "verbraucher", "grund": "nicht eingereicht"}, {"dokumenttyp": "kostenkalkulation", "quelle": "unternehmen", "grund": "hinweis"}], "relevante_agb_fassung": "D2"},
  "nachforderungen": [{"id": "N1", "kanal": "vbs", "dokumente": ["agb", "vertrag"], "text": "…", "status": "eingegangen", "markiert_von": "Beraterin", "zeit": "…"}],
  "pruefungen": [
    {"run_id": "R-1", "trigger": "initial", "zeit": "…", "schema_version": "0.2.0", "ergebnisse": ["…"], "einordnung": "unklar – es fehlt: AGB", "aktuell": false},
    {"run_id": "R-2", "trigger": "nachreichung", "ausgeloest_durch": "N1", "zeit": "…", "schema_version": "0.2.0",
     "ergebnisse": [
       {"pruefpunkt_id": "P9", "zustand": "NEIN", "grund": "Weiternutzung als Zustimmung gewertet", "verwendet": ["erhoehungsschreiben.zustimmungsmechanismus"], "zitate": [{"dok_id": "D1", "seite": 1, "text": "…"}], "anker": ["bgb_308_5", "bgh_xi_zr_26_20", "lg_bamberg_13_o_730_22"], "missing": [], "owner": null, "wertungsfrage": null, "llm_befund": false, "badge": "verifiziert"},
       {"pruefpunkt_id": "P11", "zustand": "FEHLT", "missing": ["kostenkalkulation"], "owner": "unternehmen"},
       {"pruefpunkt_id": "P6", "zustand": "JA", "llm_befund": true, "badge": "llm_befund"}
     ],
     "baum_zustaende": {"S0": "JA", "S1": "JA", "S2": "JA", "S3": "NEIN", "S4": "JA", "root": "NEIN"},
     "einordnung": "wahrscheinlich unwirksam",
     "vollstaendigkeit": {"verbraucher": [], "unternehmen": ["kostenkalkulation"]},
     "gerissene_stufe": "S3",
     "pruefumfang": ["P11", "P14"],
     "plain": "Die Erhöhung steht auf wackeligen Beinen: Weitertrainieren oder Schweigen gilt nicht als Zustimmung zu einem höheren Beitrag. Sie können widersprechen und den alten Beitrag weiterzahlen.",
     "gate3": {"aktion": "bestaetigt", "von": "Beraterin", "zeit": "…"},
     "aktuell": true}
  ],
  "overrides": [{"pruefpunkt_id": "P4", "neuer_zustand": "JA", "grund": "Klausel steht unter „Beiträge“, nicht überraschend", "von": "Beraterin", "zeit": "…", "gilt_fuer_runs": "ab R-2"}],
  "leitfaden": {"fragen": [{"pruefpunkt_id": "P9", "text": "…", "antwort": true}], "fristen": [{"name": "Vorlaufzeit", "wert": "26 Tage", "stand": "2026-08-27", "annahmen": ["Zugang = Datum + 3 Tage"]}]},
  "rechtsbehelf": {"hauptvorschlag": "widerspruch_rueckforderung", "vorschlaege": ["widerspruch_rueckforderung"], "gewaehlt": "widerspruch_rueckforderung", "gate4_von": "Beraterin",
                   "brief": {"template_id": "musterbrief_fitness_widerspruch_rueckforderung", "quelle_url": null, "platzhalter": {"[VERTRAGSDATUM]": "…"}, "status": "uebergeben", "empfaenger": "anbieter"}},
  "referat_markierung": {"kriterien": ["dauerbrenner"], "notiz": "", "von": "Beraterin", "zeit": "…", "evidenz": {"cluster_anbieter": 4, "betrag_erhoehung": 7.0}},
  "abschluss": {"basis_export_erzeugt": true, "wiedervorlagen": [], "geschlossen": false},
  "ereignisse": [{"zeit": "…", "akteur": "Beraterin", "aktion": "l0_pseudonymisiert", "details": {"tokens": 3}}],
  "llm_runs": [{"id": "R1", "aufgabe": "extract_fields", "modell": "…", "prompt_version": "…", "dok_id": "D1", "cache_datei": "cache/llm/…json", "dauer_ms": 2100, "kosten_cent": 1.2, "zeit": "…"}]
}
```

Rules: `text_pseudonym` / `freitext_pseudonym` are the **only** forms sent to the LLM; the pseudonym map never leaves the machine and is never passed to any LLM call. Re-identification happens in two local places only: the advisor UI (display) and template fill. Quotes are verified against `text_pseudonym` (normalised: whitespace collapse, soft hyphen removed, quotes unified, NFC) and de-tokenised for display, where the viewer locates them in `text_original` of the same page. Facts are keyed by `(feld_id, dok_id)`; P2 uses `dokumenten_soll.relevante_agb_fassung` = the AGB whose `fassung_datum ≤ vertrag.datum` (latest such), else the only one. `pruefungen[]`: each trigger (initial · nachreichung · leitfaden_antwort · override · schema_reload) creates a new run; overrides persist as entries and are re-applied to later runs unless withdrawn; a new run invalidates the previous `gate3` confirmation. `gespraech.*` facts come from Leitfaden answers (herkunft gespraech) and trigger a re-run. `eingang.anbieter` is L0-whitelisted (legal person) and advisor-editable. `sensible_inhalte_flag` = keyword hit (Krankheit, Behinderung, Pflege, Schwangerschaft, Religion, Gewerkschaft) → advisor notice only (K4 handling open).

## 5. Check result (engine output per Prüfpunkt)

| Field | Type | Set by | Meaning |
|---|---|---|---|
| `pruefpunkt_id` | id | engine | |
| `zustand` | JA/NEIN/FEHLT/WERTUNG/INAKTIV | engine | |
| `grund` | text | engine from `satz_*` / `plain_grund` | one sentence for the trace |
| `verwendet[]`, `zitate[]`, `anker[]` | | engine | quotes verified; anchors resolved (unverified → grey) |
| `missing[]`, `owner` | feld_id / dokumenttyp; verbraucher/unternehmen | engine ← Soll | FEHLT only |
| `strittige_felder[]` | feld_id | engine | **v1.2** — declared inputs that carry two contradicting facts and are therefore unusable |
| `wertungsfrage` | text | schema | WERTUNG only |
| `llm_befund` | bool | engine | typ text decided on extracted criteria |
| `badge` | enum | engine | see vocab |
| `frist` / `betrag` | {name, wert, stand, annahmen[]} | engine | via `heute()` |
| `override` | ref | Gate 3 | applied in recompute |

**Three lists of feld_ids, three different statements — they must not be merged.**

| | means | who acts on it |
|---|---|---|
| `verwendet[]` | read, and the rule used the value | the trace shows the quote |
| `missing[]` | required and absent | **Gate 1 asks the consumer for it** |
| `strittige_felder[]` | present twice, contradicting, therefore unusable | the advisor resolves it at Gate 3 |

`missing` is the wrong home for a contradiction: the document is *in* the file, and listing it there
makes the tool request a document it already has. `verwendet` is the wrong home too — the rule could
not read the value, and putting it there would make `verwendet` mean two things. Without the third
list the field left the trace entirely: the screen said „Bewertung nötig" with a general question and
the two statements that disagree stood nowhere, so the advisor was asked to resolve a conflict whose
halves were invisible.

A contradiction is **marked, never resolved** (§9): both facts go `herkunft: strittig`,
`verifiziert: false`, so `feld()` yields nothing and the Prüfpunkt falls to WERTUNG. Marking both —
rather than trusting whichever fact the resolver happens to return — is what makes the outcome
independent of the lookup order.

A contested fact keeps its pre-contradiction state in `vor_widerspruch` so that a **withdrawal
restores it**: the document never changed, only the statement about it did, and a corrected answer
must not leave the file permanently marked. The key carries no leading underscore because pydantic
drops underscore-prefixed attributes from `model_dump`, and a case is written and read back on every
request.

## 6. Normbasis — seed is mandatory

`normbasis/statutes_de.json` must contain before the A-schema loads: `bgb_305_2, bgb_305b, bgb_305c, bgb_306, bgb_307_1_1, bgb_307_1_2, bgb_307_3, bgb_308_4, bgb_308_5, bgb_309_9, bgb_310_3, bgb_315_3, bgb_812, bgb_195, bgb_199` (and for Inkasso later: §§ 145 ff., 312b/c/g, 355, 356, 123, 286 BGB, Art. 246a EGBGB, RDG) — fetch via `data/fetch_statutes.py` against gesetze-im-internet, record `stand` + `url`; `data/statutes_de.json` (prep repo) does **not** contain these and is not a valid seed as-is. Entries: `{key, gesetz, norm, absatz, text, stand, url, geprueft}`. `caselaw.json`: `{key, gericht, az, datum, klaeger, kernaussage, url, ebene, status, geprueft, geprueft_von, geprueft_am}`. Resolver: `strict` mode (demo) → unresolved key = schema load error; `dev` mode → warning + anchor rendered `anker_ungeprueft`. A citation found in a document (`*.zitierte_fundstellen`) is a fact: `normbasis_treffer(liste)` marks each as found/not found; never copied into `anker[]`; rendered „im Schreiben zitiert — nicht in unserer Normbasis, nicht verwendet".

## 7. Templates and placeholders

Front matter: `id, titel, fallgruppe_id, rechtsbehelf_id, empfaenger (anbieter|gegner|verbraucher), quelle (vz_musterbrief|eigen), quelle_url, quelle_datum, hausstil_geprueft, varianten[{id, wenn}]`. Placeholder syntax `\[[A-Z0-9_]+\]`; **incoming names are normalised** (Paulina may write `[Vertragsdatum]` or `[Datum des Vertrags]` → `[VERTRAGSDATUM]`, `[DATUM_DES_VERTRAGS]`; we map, she changes nothing). `config.platzhalter_map` (binding):

| Placeholder | Source |
|---|---|
| `[NAME]`, `[ANSCHRIFT]` | identity (de-tokenised at fill) |
| `[ANBIETER]`, `[ANBIETER_ANSCHRIFT]` | `eingang.anbieter`, `erhoehungsschreiben.absender_adresse` |
| `[VERTRAGSDATUM]`, `[KUNDENNUMMER]`, `[ALTER_BEITRAG]`, `[NEUER_BEITRAG]`, `[ERHOEHUNG_AB]`, `[SCHREIBEN_DATUM]` | facts |
| `[RUECKFORDERUNG_BETRAG]`, `[FRIST_ENDE]`, `[HEUTE]` | computed (P12, `heute()` + config `antwortfrist_tage` 14) |
| `[FEHLENDE_UNTERLAGEN_LISTE]` | Nachforderung loop: anzeigename · begruendung_satz · beschaffungsweg |

Unknown placeholder → render error, never blank. Nachforderung templates: no legal statements in fixed text — lint blocks `wirksam|unwirksam|zahlen Sie|Anspruch|Widerruf` outside the document list; channel sentences: vbs „antworten Sie auf diese Anfrage mit Anhang", vor_ort/telefon „bitte zum Termin mitbringen, gern vorab per E-Mail", video „über das Transferportal hochladen". `basis_eintrag.md`: key-value block (Fallgruppe · Anbieter/Gegner · Einordnung · Rechtsbehelf · Fristen · Schadenshöhe = Rückforderung if computed else Differenz × Monate · Referat-Markierung · Schema-Version).

## 8. Store record — `store/faelle.jsonl`

```json
{"fall_hash": "hmac(case_id)", "zeit": "…", "fallgruppe_id": "preiserhoehung", "stufe": "A", "anbieter": "fitpoint 24", "gegner": null, "branche": "fitness", "einordnung": "wahrscheinlich unwirksam", "gerissene_stufe": "S3", "pruefpunkte_nein": ["P9"], "fehlte": ["agb"], "rechtsbehelf": "widerspruch_rueckforderung", "betrag_erhoehung_gerundet": 7.0, "referat_flag": ["dauerbrenner"], "kanal": "vbs", "schema_version": "0.2.0"}
```
No identities, no free text, no document text, no advisor name. `fall_hash` = HMAC(case_id, secret from config). Radar shows per-Anbieter counts only from `k_min` cases (config, 3) and rounds amounts. Written at Gate 3 confirmation (and updated at Gate 4/flag) — every confirmed case counts, all Stufen.

## 9. LLM adapter — I/O (all inputs pseudonymised)

| Call | Input | Output | Validator |
|---|---|---|---|
| `classify_doc(text_pseudonym)` | page texts | `{dokumenttyp, konfidenz, begruendung}` | enum; konfidenz < 0.6 → `sonstiges` + advisor confirm |
| `extract_fields(text_pseudonym, felder[])` | text + field specs (typ, werte, beschreibung, zitat_pflicht) | `[{feld_id, wert, zitat, seite}]` | quote substring-verified in pseudonym space (normalised) → else FEHLT; typ parse; `zitat_pflicht` without quote → FEHLT; bool false must still carry the examined span |
| `propose_fallgruppe(freitext_pseudonym, doktypen[], felder_kurz)` | case summary | top-3 `[{fallgruppe_id, begruendung, zitate[]}]` | ids ∈ taxonomy; quotes verified; advisor decides |
| `polish_plain(satz_template, fakten_kurz)` *stretch* | | sentence | reject if numbers/dates/§/Az not in the trace |

Cache: `cache/llm/<aufgabe>_<modell>_<prompt_version>_<hash(text_pseudonym + felder spec)>.json` storing input and output; demo replays from cache; `llm_runs[]` records file, latency, cost (feeds the Betriebskosten footer). `herkunft: strittig` is set by code when two verified quotes support conflicting values.

## 10. Config

```json
{
  "demo_stichtag": "2026-08-27", "stichtag_modus": "demo",
  "llm": {"adapter": "anthropic", "modell_klassifikation": "<fast tier>", "modell_extraktion": "<mid tier>", "prompt_version": "p1", "cache": true, "vertragsbedingungen": {"zero_retention": "ungeprueft", "eu_region": "ungeprueft"}},
  "normbasis_modus": "dev",
  "radar": {"schwelle_beschwerden": 30, "schwelle_beratungen": 15, "k_min": 3},
  "platzhalter_regex": "\\[[A-Z0-9_]+\\]", "antwortfrist_tage": 14,
  "pseudonymisierung": {"token_syntax": "@@TYP_N@@", "quellen": ["ticket_felder", "regex_iban", "regex_email", "regex_telefon", "regex_geburtsdatum", "regex_kundennummer"], "whitelist": ["eingang.anbieter", "eingang.gegner"], "ner": false, "sensible_keywords": ["Krankheit", "krank", "Behinderung", "Pflege", "schwanger", "Religion", "Gewerkschaft"]},
  "log_akteur": "rolle", "aufbewahrung_tage": {"cases": 30, "cache": 30, "store": null},
  "store_pfad": "store/faelle.jsonl", "hmac_secret_env": "FP_HMAC_SECRET"
}
```

## 11. Golden tests — `tests/golden/<case_id>.json`

```json
{"case_id": "franz_fall_2_unklar_agb", "quelle": "Franz Runde 2, Lösungszettel (ausstehend)", "geprueft": false, "stichtag": "2026-08-27",
 "stufen": [
   {"name": "initial", "dokumente": ["schreiben.md"], "erwartet": {"einordnung": "unklar – es fehlt …", "fehlt": [{"dokumenttyp": "agb", "quelle": "verbraucher"}], "gekippte_pruefpunkte": [], "hauptvorschlag": "nachforderung"}},
   {"name": "nachreichung", "dokumente": ["schreiben.md", "agb_nachgereicht.md"], "erwartet": {"einordnung": "wahrscheinlich unwirksam", "gekippte_pruefpunkte": ["P6"], "hauptvorschlag": "widerspruch_rueckforderung"}}
 ]}
```
Runner compares per stage: `einordnung`, `fehlt` (set of dokumenttyp/feld_id), `gekippte_pruefpunkte` (must include expected), `hauptvorschlag`; outputs a 3×3 confusion matrix and the headline „falsche sichere Antworten" (expected unklar, got wirksam/unwirksam). Lösungszettel ingest map: „Unklar — es fehlt was." / „wahrscheinlich unwirksam" / „wirksam" → binding enum; „Vollständigkeits-Status" text → `fehlt[]` by dokumenttyp keywords; „tragende Prüfpunkte" → `gekippte_pruefpunkte` via packet numbering (Preiserhöhung P0–P14; Inkasso 0–12 once her list exists). `geprueft:false` tests advisory, `true` gating.

## 12. Event log

`{zeit, akteur (rolle, not name — config log_akteur), aktion, details}` with actions: `l0_pseudonymisiert`, `dokument_klassifiziert`, `gate1_nachforderung_markiert`, `nachreichung_eingegangen`, `gate2_fallgruppe_gewaehlt`, `schema_stopp`, `pruefung_gelaufen {run_id, trigger}`, `gate3_bestaetigt`, `gate3_override`, `leitfaden_antwort`, `gate4_rechtsbehelf_gewaehlt`, `brief_erzeugt`, `referat_markiert`, `abschluss_basis_export`, `fall_geschlossen`, `schema_geladen {version}`, `ki_hinweis_angezeigt`. The log is oversight evidence; it must not become Leistungskontrolle — no advisor names, no per-advisor statistics anywhere.

## 13. Pending deliverables — what the build assumes until they arrive

| Expected from | What arrives | Until then the build uses | Drop-in path (no code) |
|---|---|---|---|
| Franz | 12 fitness cases with Lösungszettel (Einordnung, Vollständigkeit, Prüfpunkt-Nr., Rechtsbehelf), Nachreichungs-Dateien, wirksam-branch answer, citation checks | our own fiction cases (`demo/`, `tests/golden/*` with `geprueft:false`): Drehkreuz, unklar-AGB + Nachreichung, Preisgarantie, wirksam; `kuendigung_bei_wirksam` template carries both variants | drop his cases into `tests/golden/` via the ingest map; flip `geprueft:true`; set `geprueft_von`; set anchors `geprueft:true` only after his Aufgabe 4 |
| Paulina | Unterlagen-Soll table (immer/bedingt), per-document field lists, Inkasso Prüfpunkte 0–12 with tragend/Bewertungsfrage, VZ Musterbrief PDFs + text with placeholders, plain sentences, Fall-4 Nachreichung, cross-review | provisional inkasso Soll (§3), Stufe B; fitness letters written by us in house style (`quelle: eigen`), Nachforderung templates ours | Soll table → `dokumenten_soll` (our defaults for quelle/anzeigename/beschaffungsweg where her table has no column); Prüfpunkte → `pruefpunkte[]` with regelsprache (we transcribe; she reviews); PDFs → `templates/musterbriefe/` with front matter + normalised placeholders; Stufe → A |
| Both | citation verification | all anchors `geprueft:false`, grey, not on slides | flip flags |

Nothing in the sent packets changes; the contract adapts to them.

## 14. Open contract questions (for the law students, non-blocking)

P10 `frist_min_tage` and Form (Aushang/App) · wirksam-branch remedy · P2 NEIN condition · P8 Laufzeit rule · which `annahmen` are legally safe · Inkasso Prüfpunkte + conditions · every `geprueft:false` anchor · Art. 9 handling.
