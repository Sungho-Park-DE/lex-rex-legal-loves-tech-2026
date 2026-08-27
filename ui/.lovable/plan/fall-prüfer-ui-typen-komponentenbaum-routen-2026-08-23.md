# Fall-Prüfer UI — Typen, Komponentenbaum, Routen

Grundlage: beide Fixtures wurden vollständig gelesen. Beide haben **identische Top-Level-Schlüssel**:
`ansicht_version, case_id, kopf, hero, offene_punkte, pruefpfad, musterbrief, nachforderungen, laeufe, leitfaden, referat, abschluss, dokumente, protokoll, fusszeile`.
Unterschiede: F-2026-0002 hat zwei `laeufe[]` (R-1 „unklar – es fehlt: …", R-2 „wirksam", `aktuell: true` nur bei R-2) und eine `nachforderungen[]`-Position (N1, Status „eingegangen"); F-2026-0001 hat `nachforderungen: []` und einen einzigen Lauf mit `gerissene_stufe: "S2"` (in 0002 überall `null`). Die Typen deckelen beide Fälle ohne Varianten-Union — nur Arrays und Nullables.

## Routen

| Datei | URL | Inhalt |
| --- | --- | --- |
| `src/routes/faelle.$id.tsx` | `/faelle/:id` | Fallakte, zwei Spalten |
| `src/routes/referat.tsx` | `/referat` | Muster-Radar |
| `src/routes/index.tsx` | `/` | Redirect auf `/faelle/F-2026-0001` (Demo-Einstieg, keine eigene Seite) |

- Laden über TanStack Query: Loader ruft `ensureQueryData(fallQuery(id))`, Komponente `useSuspenseQuery`. Analog `radarQuery()` für `/referat`.
- `src/lib/api.ts` ist das einzige Modul mit Netzzugriff: `VITE_API_BASE_URL` gesetzt → `GET {base}/faelle/{id}`, `GET {base}/vokabular`, POST-Aktionen; sonst Fixture-Modus → `GET /fixtures/faelle/{id}.json`, `/fixtures/radar.json`, alle Aktionen no-op + Toast „Demo-Modus: nicht gespeichert".
- `head()` je Route: eigener Titel/Description (z. B. „Fallakte F-2026-0001 · VZ-I Fall-Prüfer"), `robots: noindex` (internes Fachwerkzeug).

## Komponentenbaum

```text
/faelle/:id  FallaktePage
  FallakteHeader        kopf (Fallgruppe, Stufe, Status, Kanal, Ticket, Vorschläge, "Fallgruppe bestätigen")
  ├── Links: DokumentViewer      dokumente[] (Tab je Dokument, seiten[].text_original als Fließtext)
  └── Rechts: CasePanel
        HeroCard             hero.einordnung + hero.vollstaendigkeit + hero.plain + hero.pruefumfang
        OffenePunkte         offene_punkte[]
        LaeufeTimeline       laeufe[] (Verlauf der Einordnungen, aktueller Lauf hervorgehoben)
        NachforderungenPanel nachforderungen[] + "Nachforderung erzeugen/markieren"
        Pruefpfad            pruefpfad.stufen[] -> PruefpunktRow[], danach pruefpfad.ableitungen[]
        LeitfadenPanel       leitfaden.fragen[] + leitfaden.offen
        MusterbriefPreview   musterbrief + vorschlaege[] (Rechtsbehelf-Wahl)
        ReferatPanel         referat.kriterien[] + notiz + markiert
        AbschlussPanel       abschluss
        ProtokollPanel       protokoll[] (einklappbar)
  Fusszeile               fusszeile

/referat  ReferatPage
  RadarView
    ClusterBar[]         cluster[] (Fälle, Einordnungs-Split, Schwellenmarker)
    SonstigesBucket      unter_schwelle_anbieter
    MarkierteFaelleListe markierte_faelle[]
    RadarTick            "+1"-Zähler (nur erlaubte Animation)

geteilt: ToneBadge (Enum {code,label,tone}), ZustandChip, ZitatLink, AnkerPopover
```

Regeln: jede Komponente erhält nur ihren Slice als Props; kein Panel kennt den ganzen View-Model. `label` wird gerendert, `tone` färbt, `code` steuert Logik. Keine Prozentzahlen, keine im UI erfundenen Labels.

Klick-auf-Zitat: `ZitatLink` erhält `{dok_id, seite, zitat}` und setzt den Viewer-State (aktives Dokument + Seite + Suchstring). Highlight per einfachem `indexOf` im Seitentext; kein Treffer → sichtbarer Zustand „Zitat auf dieser Seite nicht gefunden".

## `src/types/viewmodel.ts` (Schlüssel 1:1 deutsch)

```ts
export type Tone = "gruen" | "gelb" | "rot" | "grau";
export interface Enum { code: string; label: string; tone: Tone }
export interface Einordnung extends Enum { label_basis: string }  // hero.einordnung
export interface Zitat { dok_id: string; seite: number; zitat: string; feld_id: string | null }

export interface Kopf {
  case_id: string; ticket_nr: string; thema: string; kanal: Enum;
  anbieter: string; gegner: string | null; eingegangen_am: string;
  status: Enum; fallgruppe: Enum; stufe: Enum;
  fallgruppe_bestaetigt: boolean; fallgruppe_vorschlag_fehlt: boolean;
  fallgruppe_vorschlaege: Array<{ fallgruppe: Enum; stufe: Enum; begruendung: string; zitate: Zitat[] }>;
  schema_stopp_text: string | null; hinweis: string | null;
}

export interface Fehlend {
  was: string; grund: string; quelle: Enum; dokumenttyp: Enum;
  feld_id: string | null; felder: string[];
  pruefpunkt_id: string | null; beschaffungsweg: string;
}
export interface Hero {
  einordnung: Einordnung;
  vollstaendigkeit: { verbraucher: Fehlend[]; unternehmen: Fehlend[]; vollstaendig_verbraucherseite: boolean };
  plain: string[];
  pruefumfang: Array<{ pruefpunkt_id: string; titel: string; zustand: Enum; text: string }>;
}

export interface OffenerPunkt {
  art: Enum; text: string;
  pruefpunkt_id: string | null; quelle: Enum | null; feld_id: string | null;
}

export interface Anker {
  key: string; label: string; ebene: Enum; status: Enum | null;
  geprueft: boolean; aufgeloest: boolean;
  kernaussage: string | null; text: string; url: string | null; stand: string | null;
}
export interface VerwendetesFeld {
  feld_id: string; wert_anzeige: string; herkunft: Enum; badge: Enum;
  verifiziert: boolean; zitat: Zitat | null; annahme_anzeige: string | null;
}
export interface Kennzahl { name: string; wert: string; stand?: string; annahmen: string[] } // frist / betrag
export interface Pruefpunkt {
  pruefpunkt_id: string; titel: string; proposition: string;
  zustand: Enum; rolle: Enum; typ: Enum | null; herkunft: Enum; badge: Enum;
  grund: string; zitate: Zitat[]; anker: Anker[]; verwendet: VerwendetesFeld[];
  fehlt: string[]; owner: Enum | null; wertungsfrage: string | null; llm_befund: boolean;
  frist: Kennzahl | null; betrag: Kennzahl | null;
  override: { wert: Enum; begruendung: string; akteur: string; zeit: string } | null;
  inaktiv_grund: string | null;
}
export interface Pruefpfad {
  wurzel: Enum; gerissene_stufe: string | null;
  stufen: Array<{ stufe_id: string; titel: string; zustand: Enum; pruefpunkte: Pruefpunkt[] }>;
  ableitungen: Pruefpunkt[];
}

export interface Musterbrief {
  rechtsbehelf_id: string; titel: string; text: string; status: Enum;
  template_id: string; variante: string | null; quelle: Enum; quelle_url: string | null;
  empfaenger: Enum; platzhalter: Record<string, string>; geprueft: boolean;
  vorschlaege: Array<{ rechtsbehelf_id: string; titel: string; hauptvorschlag: boolean; geprueft: boolean }>;
}

export interface Nachforderung {
  id: string; kanal: Enum; dokumente: Enum[]; text: string; status: Enum; zeit: string;
}
export interface Lauf {
  run_id: string; trigger: string; zeit: string;
  einordnung: string; einordnung_tone: Tone;
  gerissene_stufe: string | null; aktuell: boolean;
  gate3_bestaetigt: boolean; gate3_gueltig: boolean;
}

export interface LeitfadenFrage {
  pruefpunkt_id: string; pruefpunkt_titel: string; text: string; typ: string;
  fuellt: string[]; werte: Record<string, string>; hinweis: string | null;
  status: Enum; grund: string; antwort: Record<string, unknown>; zustand: Enum;
}
export interface Referat {
  kriterien: Array<{ id: string; label: string; angehakt: boolean; evidenz: string | null }>;
  notiz: string; markiert: boolean; hinweis: string;
}
export interface Abschluss {
  basis_export_erzeugt: boolean; basis_text: string | null;
  wiedervorlagen: Array<{ titel: string; datum: string; grund: string }>; geschlossen: boolean;
}
export interface Dokument {
  dok_id: string; dokumenttyp: Enum; dateiname: string; quelle: Enum;
  eingegangen: string; typ_bestaetigt: boolean;
  seiten: Array<{ nr: number; text_original: string }>;
}
export interface ProtokollEintrag {
  zeit: string; akteur: string; aktion: Enum; schritt: Enum; beschreibung: string;
}
export interface Fusszeile {
  disclaimer: string; ki_hinweis: string; schema_version: string; schema_stand: string;
  stand: string; stichtag: string; stichtag_modus: string;
  betriebskosten_cent: number; normbasis_modus: string;
}

export interface FallAnsicht {
  ansicht_version: string; case_id: string;
  kopf: Kopf; hero: Hero; offene_punkte: OffenerPunkt[]; pruefpfad: Pruefpfad;
  musterbrief: Musterbrief; nachforderungen: Nachforderung[]; laeufe: Lauf[];
  leitfaden: { fragen: LeitfadenFrage[]; offen: number };
  referat: Referat; abschluss: Abschluss;
  dokumente: Dokument[]; protokoll: ProtokollEintrag[]; fusszeile: Fusszeile;
}

export interface RadarAnsicht {
  stand: string; faelle_gesamt: number;
  schwellen: { beschwerden: number; beratungen: number; k_min: number };
  cluster: Array<{
    anbieter: string; branche: string; faelle: number;
    einordnungen: Record<string, number>; pruefpunkte_nein: Record<string, number>;
    betrag_median: number; referat_flags: number;
  }>;
  unter_schwelle_anbieter: number;
  markierte_faelle: Array<{ case_id: string; anbieter: string; einordnung: string; kriterien: string[] }>;
  hinweis: string;
}
```

## Annahmen, die ich sonst stillschweigend treffen würde

1. **Router**: TanStack Router (Template-Vorgabe), nicht React Router wie im Projektwissen genannt — Dateiroute `faelle.$id.tsx`.
2. **`/` bleibt nicht leer**: Redirect auf `/faelle/F-2026-0001`, da nur zwei Screens erlaubt sind und die Platzhalterseite weg muss.
3. **Leere Arrays im Fixture haben keinen Typ-Beweis**: `felder: []`, `abschluss.wiedervorlagen: []`, `markierte_faelle: []`, `pruefpunkt.override: null`, `leitfaden.werte/antwort: {}` — die oben gezeigten Formen sind geraten. Wenn Sie die echten Formen kennen, korrigiere ich sie vor der Implementierung.
4. **`enum.code`-Werte werden nicht zu Unions eingeengt** (`string`, nicht `"gruen"|…` außer bei `tone`), damit neue Backend-Codes die UI nicht brechen.
5. **`laeufe[]` wird als Verlaufsleiste gerendert** (kein Umschalten der Ansicht auf alte Läufe); dargestellt wird immer der aktuelle Lauf, alte Läufe nur als Zeile „R-1 · unklar – es fehlt: … → R-2 · wirksam". Einordnungstexte werden wörtlich aus `laeufe[].einordnung` übernommen.
6. **`nachforderungen[]` bekommt ein eigenes Panel** unterhalb „Offene Punkte" (im Projektwissen nicht als eigener Punkt der Panel-Reihenfolge gelistet, aber F-2026-0002 liefert Daten dafür).
7. **`leitfaden` und `protokoll` bekommen je ein zusätzliches, eingeklapptes Panel** — beide sind im Fixture gefüllt, in der vorgegebenen Panel-Reihenfolge aber nicht genannt.
8. **`musterbrief.platzhalter`** wird als Tabelle unter dem Brieftext gezeigt; Platzhalter im Text werden **nicht** ersetzt (der Text kommt bereits fertig vom Backend).
9. **`anker[].text`** ist teils sehr lang → nur `label` als Chip, Volltext in einem Popover/Accordion, mit `url`-Link und `stand`.
10. **Radar**: `unter_schwelle_anbieter` ist der „Sonstiges"-Bucket; `schwellen.beschwerden/beratungen` werden als Marker an den Balken gezeichnet; der „+1"-Tick ist im Fixture-Modus ein reiner Demo-Effekt bei Refetch, kein Polling.
11. **`fusszeile.betriebskosten_cent`** wird als „0,04 €" formatiert dargestellt (Feld heißt cent, Wert ist 4.05 → gelesen als Cent).
12. **Sprache/Datumsformat**: Anzeige in `de-DE`, ISO-Zeitstempel werden formatiert; die im Fixture bereits deutsch formatierten Felder (`stand`, `[HEUTE]`) bleiben unangetastet.
13. **Aktionen im Fixture-Modus** ändern keinen lokalen State (kein optimistisches Umschalten von Checkboxen) — nur Toast, damit die UI nie etwas behauptet, was das Backend nicht bestätigt hat.
14. **Kein `/vokabular`-Aufruf im Fixture-Modus**; Labels kommen ausschließlich aus dem View-Model.
