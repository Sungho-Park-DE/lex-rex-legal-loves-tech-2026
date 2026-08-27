// Mirrors the backend view-model 1:1. German keys stay exactly as delivered.

export type Tone = "gruen" | "gelb" | "rot" | "grau";

export interface Vok {
  code: string;
  label: string;
  tone: Tone;
  /** 1.6: one delivered sentence for the tooltip (Rolle, Typ). Absent = no tooltip. */
  detail?: string | null;
}

export interface EinordnungVok extends Vok {
  label_basis: string;
}

export interface Zitat {
  dok_id: string;
  seite: number;
  zitat: string;
  feld_id: string | null;
}

export interface FallgruppeVorschlag {
  fallgruppe: Vok;
  stufe: Vok;
  begruendung: string;
  zitate: Zitat[];
}

export interface Kopf {
  case_id: string;
  ticket_nr: string;
  thema: string;
  kanal: Vok;
  anbieter: string;
  gegner: string | null;
  eingegangen_am: string;
  status: Vok;
  fallgruppe: Vok;
  stufe: Vok;
  fallgruppe_bestaetigt: boolean;
  fallgruppe_vorschlag_fehlt: boolean;
  fallgruppe_vorschlaege: FallgruppeVorschlag[];
  /** 1.14: das verifizierte Zitat aus dem Erhoehungsschreiben, das die
      bestaetigte Fallgruppe traegt — erst NACH Gate 2 gesetzt. */
  fallgruppe_beleg: Zitat | null;
  schema_stopp_text: string | null;
  hinweis: string | null;
}

/** View model 1.4: state of a missing item, e.g. code "existiert_nicht". */
export interface Fehlzustand extends Vok {}

export interface Fehlend {
  was: string;
  grund: string;
  quelle: Vok;
  dokumenttyp: Vok | null;
  feld_id: string | null;
  felder: string[];
  pruefpunkt_id: string | null;
  beschaffungsweg: string;
  fehlzustand?: Fehlzustand | null;
  aussage?: string | null;
}

export interface PruefumfangEintrag {
  pruefpunkt_id: string;
  titel: string;
  zustand: Vok;
  text: string;
}

export interface Hero {
  einordnung: EinordnungVok;
  vollstaendigkeit: {
    verbraucher: Fehlend[];
    unternehmen: Fehlend[];
    vollstaendig_verbraucherseite: boolean;
  };
  plain: string[];
  pruefumfang: PruefumfangEintrag[];
}

export interface OffenerPunkt {
  art: Vok;
  text: string;
  /** Schluessel, keine Anzeige — dient dem Sprung in die Detailzeile. */
  pruefpunkt_id: string | null;
  /** 1.13: das Wort. Fehlt es, steht nichts da — die ID ist kein Rueckfall. */
  pruefpunkt_titel: string | null;
  quelle: Vok | null;
  feld_id: string | null;
  feld_label: string | null;
}

export interface Anker {
  key: string;
  label: string;
  ebene: Vok;
  status: Vok | null;
  geprueft: boolean;
  /**
   * 1.15: `geprueft` als geliefertes Wort — „Fundstelle gegengelesen" (gruen)
   * bzw. „Fundstelle ungeprueft" (grau), mit `detail` fuers Popover. Der Chip
   * schreibt seither kein eigenes „ungeprueft" mehr (Regel 1).
   */
  pruefstand: Vok;
  aufgeloest: boolean;
  kernaussage: string | null;
  text: string | null;
  url: string | null;
  stand: string | null;
}

export interface VerwendetesFeld {
  feld_id: string;
  /** 1.7 (R5): Beschriftung für den Schirm; `feld_id` bleibt der Schlüssel. */
  feld_label?: string | null;
  wert_anzeige: string;
  herkunft: Vok;
  badge: Vok | null;
  verifiziert: boolean | null;
  zitat: Zitat | null;
  annahme_anzeige: string | null;
}

export interface Kennzahl {
  name: string;
  wert: string;
  stand?: string | null;
  annahmen: string[];
}

export interface Override {
  neuer_zustand: Vok;
  grund: string;
  von: string;
  zeit: string;
}

export interface AbmahnungHinweis {
  badge: Vok;
  text: string;
  geprueft: boolean;
  quelle_url: string | null;
}

export interface Pruefpunkt {
  pruefpunkt_id: string;
  titel: string;
  proposition: string;
  zustand: Vok;
  rolle: Vok;
  typ: Vok | null;
  herkunft: Vok;
  badge: Vok | null;
  grund: string;
  zitate: Zitat[];
  anker: Anker[];
  verwendet: VerwendetesFeld[];
  fehlt: string[];
  owner: Vok | null;
  wertungsfrage: string | null;
  llm_befund: boolean;
  frist: Kennzahl | null;
  betrag: Kennzahl | null;
  override: Override | null;
  inaktiv_grund: string | null;
  /** View model 1.4: expert confirmations of this Prüfpunkt. May be absent/empty. */
  geprueft_von?: Fachpruefung[];
  /**
   * 1.7, Franz' Anleitung §7: der Klauseltyp war schon Gegenstand einer Abmahnung
   * oder Klage. `text` ist der ganze Satz (endet mit „· ungeprüft", solange
   * `geprueft` false ist) — wird verbatim gezeigt, nie gekürzt oder ergänzt.
   */
  hinweis_abmahnung?: AbmahnungHinweis | null;
  /** 1.7, Anleitung §2: Chip „wertungsfrei" an § 309 / § 308-Punkten. */
  normrang?: Vok | null;
}

export interface Fachpruefung {
  wer: string;
  beleg: string;
  am: string;
  umfang: string | null;
  vorbehalt: string | null;
}

export interface Stufe {
  stufe_id: string;
  titel: string;
  zustand: Vok;
  pruefpunkte: Pruefpunkt[];
}

/**
 * View model 1.8 (R7): derselbe Prüfpfad als Baum. Dieselben Zustände wie die
 * Detailliste — keine zweite Bewertung, keine eigene Sortierung: Blätter und
 * Reihenfolge sind identisch mit `stufen[].pruefpunkte[]`.
 */
export interface BaumKnoten {
  knoten_id: string;
  /** wurzel · stufe · pruefpunkt */
  art: Vok;
  titel: string;
  /** „alle müssen halten" — nur an Wurzel und Stufe */
  op: Vok | null;
  zustand: Vok;
  /** nur am Prüfpunkt */
  rolle: Vok | null;
  gerissen: boolean;
  /** das Wort „gerissen" kommt geliefert, nie aus dem UI */
  marker: Vok | null;
  /** Titel des Punktes, dessen Nichterfüllung diesen Knoten gegenstandslos machte */
  inaktiv_durch: string | null;
  anzahl_pruefpunkte: number;
  /** 1.10 (K58): Fundstelle des ersten Ankers ohne „BGB" — null, wenn der Punkt keinen hat. */
  norm_kurz?: string | null;
  /**
   * 1.10 (K58): die amtliche Überschrift der Norm — wörtlich, nur hinten
   * gekürzt; wo zwei Punkte dieselbe Norm haben, steht unser Titel.
   */
  kurzwort?: string | null;
  /** „amtlich" = Gesetzesüberschrift · „titel" = unser Prüfpunkt-Titel. */
  kurzwort_quelle?: string | null;
  kinder: BaumKnoten[];
}

export interface Pruefpfad {
  wurzel: Vok;
  gerissene_stufe: string | null;
  /** ansicht 1.11: das Wort neben der Kennung. `gerissene_stufe` bleibt die
      Identitaet (Regeln und Goldens lesen sie), der Titel ist die Anzeige. */
  gerissene_stufe_titel: string | null;
  stufen: Stufe[];
  ableitungen: Pruefpunkt[];
  baum?: BaumKnoten | null;
  /**
   * 1.9: die Zeichen, die im Baum vorkommen und einen Erklärungssatz haben —
   * fertige Vokabeln mit `detail`. Enthält „tragend", das der Baum bewusst
   * nicht mehr als Abzeichen zeigt.
   */
  legende?: Vok[];
}

export interface RechtsbehelfVorschlag {
  rechtsbehelf_id: string;
  titel: string;
  hauptvorschlag: boolean;
  geprueft: boolean;
}

export interface Musterbrief {
  rechtsbehelf_id: string;
  titel: string;
  text: string;
  status: Vok;
  template_id: string;
  variante: string | null;
  quelle: Vok;
  quelle_url: string | null;
  empfaenger: Vok;
  platzhalter: Record<string, string>;
  geprueft: boolean;
  vorschlaege: RechtsbehelfVorschlag[];
}

export interface Nachforderung {
  id: string;
  kanal: Vok;
  dokumente: Vok[];
  text: string;
  status: Vok;
  zeit: string;
}

export interface Lauf {
  run_id: string;
  trigger: Vok;
  zeit: string;
  einordnung: string;
  einordnung_tone: Tone;
  gerissene_stufe: string | null;
  /** ansicht 1.11: das Wort neben der Kennung. `gerissene_stufe` bleibt die
      Identitaet (Regeln und Goldens lesen sie), der Titel ist die Anzeige. */
  gerissene_stufe_titel: string | null;
  aktuell: boolean;
  gate3_bestaetigt: boolean;
  gate3_gueltig: boolean;
}

export interface LeitfadenFrage {
  pruefpunkt_id: string;
  pruefpunkt_titel: string;
  text: string;
  typ: string;
  fuellt: string[];
  werte: Record<string, string[]>;
  /** H4 (ansicht 1.12): Beschriftung je Eingabe und je Auswahlwert. Fehlt ein
      Label, bleibt die ID sichtbar — als Luecke im Schema, nicht als Erlaubnis. */
  feld_labels: Record<string, string>;
  wert_labels: Record<string, Record<string, string>>;
  hinweis: string | null;
  status: Vok;
  grund: string;
  antwort: Record<string, unknown>;
  zustand: Vok;
}

export interface Leitfaden {
  fragen: LeitfadenFrage[];
  offen: number;
}

export interface ReferatKriterium {
  id: string;
  label: string;
  angehakt: boolean;
  evidenz: string | null;
}

export interface Referat {
  kriterien: ReferatKriterium[];
  notiz: string;
  markiert: boolean;
  hinweis: string;
}

export interface Abschluss {
  basis_export_erzeugt: boolean;
  basis_text: string | null;
  wiedervorlagen: string[];
  geschlossen: boolean;
}

export interface DokumentSeite {
  nr: number;
  text_original: string;
}

export interface Dokument {
  dok_id: string;
  dokumenttyp: Vok;
  dateiname: string;
  quelle: Vok;
  eingegangen: string;
  typ_bestaetigt: boolean;
  seiten: DokumentSeite[];
}

export interface ProtokollEintrag {
  zeit: string;
  akteur: string;
  aktion: Vok;
  schritt: Vok;
  beschreibung: string;
}

export interface Fusszeile {
  disclaimer: string;
  ki_hinweis: string;
  schema_version: string;
  schema_stand: string;
  stand: string;
  stichtag: string;
  stichtag_modus: string;
  betriebskosten_cent: number;
  normbasis_modus: string;
  /** View model 1.4: counts arrive ready-made; never counted in the UI. */
  fachpruefung_bestaetigt?: number;
  fachpruefung_gesamt?: number;
}

/** View model 1.5: advisory notes written by a lawyer for the advisor. */
export interface Beratungshinweis {
  id: string;
  art: Vok;
  titel: string;
  text: string;
  anker: Anker[];
  geprueft_von: Fachpruefung[];
}

export interface FallAnsicht {
  ansicht_version: string;
  case_id: string;
  kopf: Kopf;
  hero: Hero;
  offene_punkte: OffenerPunkt[];
  pruefpfad: Pruefpfad;
  musterbrief: Musterbrief | null;
  nachforderungen: Nachforderung[];
  laeufe: Lauf[];
  leitfaden: Leitfaden;
  beratungshinweise?: Beratungshinweis[];
  referat: Referat;
  abschluss: Abschluss;
  dokumente: Dokument[];
  protokoll: ProtokollEintrag[];
  fusszeile: Fusszeile;
}

export interface RadarEinordnung {
  text: string;
  anzahl: number;
  tone: Tone;
}

export interface RadarPruefpunktNein {
  titel: string;
  anzahl: number;
}

/**
 * Franz' Anleitung §5: „Bereits entstandener und künftig drohender Schaden
 * werden getrennt ausgewiesen — nur Letzterer ist abwendbar." Es gibt deshalb
 * bewusst keine addierte Gesamtsumme. `basen` sagt, wie gerechnet wurde;
 * `gekappt` zählt die Fälle, deren Zahl hilfsweise auf 24 Monate begrenzt ist.
 */
export interface RadarSchaden {
  drohend_median: number | null;
  drohend_summe: number | null;
  entstanden_median: number | null;
  entstanden_summe: number | null;
  fallzahl: number;
  unbeziffert: number;
  gekappt: number;
  /** Bindung abgelaufen, Vertrag läuft weiter — nur bis zum nächsten Kündigungstermin gerechnet (§ 309 Nr. 9 lit. b). */
  verlaengert: number;
  basen: string[];
}

/**
 * Franz' Anleitung §3/§6: Verbreitung (wie viele Verwender) und Betroffenheit
 * (wie viele Verbraucher) sind zwei Zahlen und werden nie zusammengezogen.
 */
export interface RadarKlauseltyp {
  pruefpunkt_id: string;
  titel: string;
  /** Fundstelle des Prüfpunkts, lang („§ 307 Abs. 1 S. 2 BGB") und in der
      Kurzform der Baumpillen („§ 307 I 2"). Beides geliefert, nie gemappt. */
  norm: string | null;
  norm_kurz: string | null;
  fallgruppe_id: string | null;
  verbreitung: number;
  betroffenheit: number;
  quote: number | null;
  grundgesamtheit: number;
  schaden_drohend_median: number | null;
  /** Anleitung §7: dieser Klauseltyp war schon Gegenstand eines Verfahrens. */
  bereits_abgemahnt: boolean;
  abmahnung_kurz: string | null;
  abmahnung_geprueft: boolean | null;
}

export interface RadarCluster {
  anbieter: string;
  branche: string | null;
  faelle: number;
  einordnungen: RadarEinordnung[];
  pruefpunkte_nein: RadarPruefpunktNein[];
  betrag_median: number | null;
  referat_flags: number;
  schaden: RadarSchaden;
  fallgruppe_id: string | null;
  /** Anleitung §7: Fälle dieses Clusters mit bereits abgemahntem Klauseltyp. */
  wiederholung: number;
}

/**
 * Kein `case_id`: die Auswertungsebene ist pseudonymisiert (Anleitung §7), und
 * das Backend sendet an dieser Stelle designbedingt nur den `fall_hash`.
 * `anbieter` ist `null`, wenn der Cluster dieses Anbieters unter `k_min` liegt.
 */
export interface MarkierterFall {
  /** vollstaendig, nur fuer `key=` — nie rendern. */
  fall_hash: string;
  /** die pseudonyme Kurzform, fertig geschnitten vom Motor. */
  fall_kennung: string;
  anbieter: string | null;
  einordnung: string;
  kriterien: string[];
  kriterien_labels: string[];
  zeit: string;
  wiederholung: number;
}

/** Anleitung §4/§7: Fassung der Prüflogik, unter der die Zeilen liefen. */
export interface PrueflogikFassungen {
  fallgruppe_id: string | null;
  aktuell: string | null;
  zeilen_aktuell: number;
  zeilen_aelter: number;
  aelteste: string | null;
}

export interface RadarAnsicht {
  stand: string;
  faelle_gesamt: number;
  schwellen: { beschwerden: number; beratungen: number; k_min: number };
  cluster: RadarCluster[];
  klauseltypen: RadarKlauseltyp[];
  unter_schwelle_klauseltypen: number;
  unter_schwelle_anbieter: number;
  markierte_faelle: MarkierterFall[];
  hinweis: string;
  geltungsbereich: string;
  wiederholungen_gesamt: number;
  prueflogik_fassungen: PrueflogikFassungen;
}
