"""The view model — what `GET /faelle/{id}` returns and the Lovable UI draws.

Scope is exactly 14 §6 screen 1 (Fallakte): header · hero (Einordnung Ampel +
Vollständigkeit + plain sentences + Prüfumfang) · Offene Punkte · Prüfpfad
(trace) · Musterbrief preview · Referat panel · Abschluss panel · footer, plus
the documents the viewer pane renders.

Two rules this file exists to enforce:

1. It is a **projection**, never a computation. Everything here was decided by
   the engine (`evaluator.py`, `rechtsbehelf.py`, `brief.py`); this module only
   reshapes it. No verdict, deadline or label is derived here.
2. Every enum leaves as `{code, label, tone}` (17 §0), built from
   `vokabular.LABELS`. The frontend renders `label`, colours by `tone` and keys
   logic on `code` — it never owns a code→string map (06 ⑧, CLAUDE.md).

JSON keys are German; `tone` is the one English key, fixed by the Lovable
project knowledge (17 §2) before this module existed.
"""

from __future__ import annotations

from enum import Enum

from typing import Any

from pydantic import BaseModel, Field

from fallpruefer import vokabular as vok

ANSICHT_VERSION = "1.15"  # 1.15: Anker.pruefstand — „ungeprüft" als geliefertes Wort mit Objekt, nicht mehr im UI getippt; 1.4: geprueft_von+fehlzustand; 1.5: beratungshinweise[] + trigger:Vokabel; 1.6: Vokabel.detail (Rolle/Typ-Tooltip); 1.7: pruefpfad[].hinweis_abmahnung (Anleitung §7) + normrang/Rangfolge (§2) + VerwendetesFeld.feld_label (R5); 1.8: pruefpfad.baum (BaumKnoten, R7); 1.9: pruefpfad.legende; 1.10: BaumKnoten.norm_kurz/kurzwort (K58); 1.11: gerissene_stufe_titel; 1.12: LeitfadenFrage.feld_labels/wert_labels (H4); 1.13: OffenerPunkt.pruefpunkt_titel/feld_label; 1.14: Kopf.fallgruppe_beleg (Pruefpfad und Lauf) — das Wort zur Kennung, damit die Anzeige „S2“ nicht selbst uebersetzen muss


class Vokabel(BaseModel):
    """An enum value, already labelled for the UI."""

    code: str
    label: str
    tone: vok.Ton
    # 1.6: ein Satz für den Tooltip, nur wo das Wort allein nicht trägt
    # (Rolle, Typ). Fehlt er, zeigt das UI nichts — es erfindet keinen.
    detail: str | None = None

    @classmethod
    def von(cls, wert: Enum) -> "Vokabel":
        return cls(code=wert.value, label=vok.label(wert), tone=vok.ton(wert),
                   detail=vok.erklaerung(wert))


def vokabel(wert: Enum | None) -> Vokabel | None:
    return None if wert is None else Vokabel.von(wert)


# --------------------------------------------------------------------------
# shared leaves
# --------------------------------------------------------------------------


class Zitat(BaseModel):
    """A verified span. The viewer highlights `zitat` inside page `seite` of
    document `dok_id` by plain substring match — if it is not found it shows a
    „nicht gefunden" state and never fakes a highlight."""

    dok_id: str
    seite: int
    zitat: str
    feld_id: str | None = None


class Anker(BaseModel):
    """A citation card. `aufgeloest` says the key resolved against the
    Normbasis; `geprueft` says a law student has confirmed it. Unverified
    anchors render grey and never go on a slide (15 §2 note iv)."""

    key: str
    label: str
    ebene: Vokabel
    status: Vokabel | None = None
    geprueft: bool
    # 1.15: dasselbe wie `geprueft`, nur als Wort statt als Wahrheitswert.
    # Die Anzeige hat das Wort bis 26.08. selbst getippt („· ungeprüft") und
    # dabei das Objekt verloren — jetzt kommt es wie jedes Label von hier.
    pruefstand: Vokabel | None = None
    aufgeloest: bool
    kernaussage: str | None = None
    text: str | None = None
    url: str | None = None
    stand: str | None = None


class Fachpruefung(BaseModel):
    """Wer diese Bewertung fachlich bestätigt hat — Kontrakt §2, pro Prüfpunkt.

    Nie schemaweit: einige Prüfpunkte sind unsere eigenen und wurden von
    niemandem entschieden, ein pauschaler Name wäre genau die Falschzuschreibung,
    gegen die der Entwurf gebaut ist.

    `vorbehalt` ist der Schlüssel, auf den es ankommt. Franz hat zu P10 die
    *Regel* bestätigt und zugleich gesagt, dass es die pauschale Zahl, die wir
    implementiert haben, gar nicht gibt. Ohne dieses Feld würde seine
    Zuschreibung unsere Umsetzung mitdecken — die Bestätigung stünde auf dem
    Schirm und der Vorbehalt nirgends.
    """

    wer: str
    am: str
    beleg: str
    umfang: str
    vorbehalt: str | None = None


class VerwendetesFeld(BaseModel):
    """One input the Prüfpunkt actually used, with where it came from."""

    feld_id: str
    # R5 (1.7): die Beschriftung für den Schirm; `feld_id` bleibt der Schlüssel
    # (Dedup strittiger Zeilen, Klick-Ziel). Fehlt das Label im Schema, ist es
    # None — das UI erfindet keins.
    feld_label: str | None = None
    wert_anzeige: str
    herkunft: Vokabel
    badge: Vokabel
    verifiziert: bool | None = None
    zitat: Zitat | None = None
    annahme_anzeige: str | None = None


class Frist(BaseModel):
    name: str
    wert: str
    stand: str
    annahmen: list[str] = Field(default_factory=list)


class Betrag(BaseModel):
    name: str
    wert: str
    annahmen: list[str] = Field(default_factory=list)


class Override(BaseModel):
    neuer_zustand: Vokabel
    grund: str
    von: str
    zeit: str


# --------------------------------------------------------------------------
# header
# --------------------------------------------------------------------------


class FallgruppenVorschlag(BaseModel):
    fallgruppe: Vokabel
    stufe: Vokabel
    begruendung: str
    zitate: list[Zitat] = Field(default_factory=list)


class Kopf(BaseModel):
    case_id: str
    ticket_nr: str | None = None
    thema: str | None = None
    kanal: Vokabel
    anbieter: str | None = None
    gegner: str | None = None
    eingegangen_am: str | None = None
    status: Vokabel
    fallgruppe: Vokabel
    stufe: Vokabel
    fallgruppe_bestaetigt: bool
    fallgruppe_vorschlag_fehlt: bool = False
    fallgruppe_vorschlaege: list[FallgruppenVorschlag] = Field(default_factory=list)
    # 1.14 — Team-Rueckmeldung 26. Aug: das graue Feld zeigte als Beleg das
    # Ticketzitat der Verbraucherin, waehrend die Begruendung daneben sagte, das
    # Studio „stuetzt sich auf eine AGB-Klausel". Diese Haelfte belegte das Zitat
    # nicht — der Vorschlag entsteht aus dem Freitext, das Modell sieht die
    # Dokumente gar nicht (`adapter.propose_fallgruppe`). Nach Gate 2 liegt der
    # Satz aus dem Erhoehungsschreiben vor, verifiziert; erst dann steht er hier.
    fallgruppe_beleg: Zitat | None = None
    # set when a gate stopped the schema (15 §2 aggregation.gates)
    schema_stopp_text: str | None = None
    hinweis: str | None = None


# --------------------------------------------------------------------------
# hero
# --------------------------------------------------------------------------


class EinordnungAnsicht(BaseModel):
    """`label` is the fully rendered verdict the UI prints verbatim, e.g.
    „unklar – es fehlt: AGB". `label_basis` is the bare enum wording."""

    code: str
    label: str
    label_basis: str
    tone: vok.Ton


class VollstaendigkeitsPosten(BaseModel):
    """Ein fehlendes Stück. `fehlzustand` sagt, WARUM es fehlt — das ist eine
    andere Achse als `quelle` (bei wem) und entscheidet, ob Gate 1 überhaupt
    fragt. `existiert_nicht` trägt die `aussage` der Verbraucherin im O-Ton:
    sie ist der Beleg für die Feststellung und wird als Zitat gezeigt, nicht zu
    einer Kategorie eingedampft."""

    """One gap, named the way it will be closed: the consumer sends a paper,
    not a field. Several unfound fields of the same document are therefore one
    Posten — `felder` carries them for the detail line, `feld_id` stays set
    only when the Posten really is about a single field."""

    was: str
    grund: str
    quelle: Vokabel
    dokumenttyp: Vokabel | None = None
    feld_id: str | None = None
    felder: list[str] = Field(default_factory=list)
    pruefpunkt_id: str | None = None
    beschaffungsweg: str | None = None
    fehlzustand: Vokabel | None = None
    aussage: str | None = None


class Vollstaendigkeit(BaseModel):
    verbraucher: list[VollstaendigkeitsPosten] = Field(default_factory=list)
    unternehmen: list[VollstaendigkeitsPosten] = Field(default_factory=list)
    vollstaendig_verbraucherseite: bool


class PruefumfangEintrag(BaseModel):
    pruefpunkt_id: str
    titel: str
    zustand: Vokabel
    text: str


class Hero(BaseModel):
    einordnung: EinordnungAnsicht
    vollstaendigkeit: Vollstaendigkeit
    plain: list[str]
    pruefumfang: list[PruefumfangEintrag] = Field(default_factory=list)


# --------------------------------------------------------------------------
# offene Punkte  (14 §6: consumer-side FEHLT + WERTUNG questions + Leitfaden)
# --------------------------------------------------------------------------


class OffenerPunkt(BaseModel):
    """1.13: `pruefpunkt_id` und `feld_id` bleiben die Identitaet (die UI
    springt damit in die Detailzeile), aber sie sind **keine Anzeige** — auf
    dem Schirm stand „P8d" neben der Frage der Beraterin. Das Wort steht
    daneben, dieselbe Regel wie `gerissene_stufe_titel` (1.11) und
    `LeitfadenFrage.feld_labels` (1.12)."""

    art: Vokabel
    text: str
    pruefpunkt_id: str | None = None
    pruefpunkt_titel: str | None = None
    quelle: Vokabel | None = None
    feld_id: str | None = None
    feld_label: str | None = None


# --------------------------------------------------------------------------
# Prüfpfad (trace)
# --------------------------------------------------------------------------


class AbmahnungHinweis(BaseModel):
    """Franz' Anleitung §7: der Klauseltyp dieses Prüfpunkts war schon Gegenstand
    einer Abmahnung oder Klage. `badge` ist der Chip (Ton geliefert), `text` der
    Satz dahinter (Gericht, Az., Träger, Datum, Prüfstand) — das UI schreibt
    keinen eigenen. `geprueft` ist das Feld aus der Normbasis: false heißt, kein
    Mensch aus dem Team hat das Original gelesen, und der Satz sagt „ungeprüft"."""

    badge: Vokabel
    text: str
    geprueft: bool
    quelle_url: str | None = None


class TraceEintrag(BaseModel):
    """One Prüfpunkt as the trace renders it."""

    pruefpunkt_id: str
    titel: str
    proposition: str
    zustand: Vokabel
    rolle: Vokabel
    # `typ` is absent for ableitung/strategie Prüfpunkte (P12/P13 carry no typ
    # in the schema); `badge` is null when a Prüfpunkt used no facts at all —
    # there was nothing to verify, so no chip is shown.
    typ: Vokabel | None = None
    herkunft: Vokabel
    badge: Vokabel | None = None
    grund: str
    zitate: list[Zitat] = Field(default_factory=list)
    anker: list[Anker] = Field(default_factory=list)
    verwendet: list[VerwendetesFeld] = Field(default_factory=list)
    fehlt: list[str] = Field(default_factory=list)
    owner: Vokabel | None = None
    wertungsfrage: str | None = None
    llm_befund: bool = False
    geprueft_von: list[Fachpruefung] = Field(default_factory=list)
    frist: Frist | None = None
    betrag: Betrag | None = None
    override: Override | None = None
    inaktiv_grund: str | None = None
    # 1.7 — nur gesetzt, wenn der Punkt NEIN steht UND ein Eintrag in
    # normbasis/abmahnungen.json denselben Klauseltyp nennt.
    hinweis_abmahnung: AbmahnungHinweis | None = None
    # 1.7 — Anleitung §2: Chip „wertungsfrei" an Punkten, deren Anker in
    # § 309 / § 308 BGB liegt. Die Reihenfolge der Zeilen einer Stufe folgt
    # derselben Rangfolge (NEIN zuerst: 309 > 308 > 307 > sonst, tragend vor
    # ergänzend); die Einordnung selbst kennt keinen Rang.
    normrang: Vokabel | None = None


class StufenEintrag(BaseModel):
    stufe_id: str
    titel: str
    zustand: Vokabel
    pruefpunkte: list[TraceEintrag] = Field(default_factory=list)


class BaumKnoten(BaseModel):
    """1.8 (R7, Luis' Kritik 25 Aug): der Prüfpfad als Baum — Wurzel → Stufen →
    Prüfpunkte, ein Knoten je Schema-Knoten, der Zustand aus derselben Prüfung
    wie die Detailzeilen. **Nur Projektion**: nichts hier wird bewertet, und
    kein Titel ist eine ID (R5)."""

    knoten_id: str
    art: Vokabel                      # wurzel · stufe · pruefpunkt (Baummarker)
    titel: str
    op: Vokabel | None = None         # Verknuepfung, nur an Wurzel/Stufe
    zustand: Vokabel
    rolle: Vokabel | None = None      # nur am Prüfpunkt
    gerissen: bool = False
    marker: Vokabel | None = None     # „gerissen"-Chip, geliefert statt hart
    inaktiv_durch: str | None = None  # Titel des Punkts, dessen bei_NEIN diesen Knoten abschaltete
    anzahl_pruefpunkte: int = 0
    # 1.10 (K58): das Diagramm zeigt Normen statt Titel — vier Juristen lesen
    # „§ 308 Nr. 5", nicht „Erklärungsfiktion (§ 308 Nr. 5)". `norm_kurz` ist
    # die Fundstelle des ersten Ankers ohne „BGB", `kurzwort` die amtliche
    # Überschrift in ein bis zwei Wörtern. Beides nur am Prüfpunkt.
    norm_kurz: str | None = None
    kurzwort: str | None = None
    # „amtlich" = Gesetzesüberschrift (wörtlich, hinten gekürzt), „titel" =
    # unser Prüfpunkt-Titel, weil die Norm keine eigene Überschrift hat.
    kurzwort_quelle: str | None = None
    kinder: list["BaumKnoten"] = Field(default_factory=list)


class Pruefpfad(BaseModel):
    """Stufen → Prüfpunkte (17 §2 screen 1 item 4). The flat trace is
    `[p for s in stufen for p in s.pruefpunkte]` — deliberately not duplicated.
    1.8: `baum` ist dieselbe Struktur als Baum, für die Übersicht über der Liste."""

    wurzel: Vokabel
    gerissene_stufe: str | None = None
    gerissene_stufe_titel: str | None = None
    stufen: list[StufenEintrag] = Field(default_factory=list)
    ableitungen: list[TraceEintrag] = Field(default_factory=list)
    baum: BaumKnoten | None = None
    # 1.9: die Zeichen, die im Baum vorkommen UND einen Erklärungssatz haben —
    # in genau der Form, in der sie dort stehen. Nötig, seit der Baum das
    # Abzeichen „tragend" nicht mehr zeigt (K55): das Wort fällt sonst auf dem
    # Schirm nirgends mehr, und Franz benutzt es im Vortrag. Die Sätze kommen
    # aus `vokabular.ERKLAERUNG`, nicht aus der Anzeige.
    legende: list[Vokabel] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Musterbrief
# --------------------------------------------------------------------------


class RechtsbehelfsVorschlag(BaseModel):
    rechtsbehelf_id: str
    titel: str
    hauptvorschlag: bool
    geprueft: bool


class Musterbrief(BaseModel):
    rechtsbehelf_id: str
    titel: str
    text: str
    status: Vokabel
    template_id: str
    variante: str | None = None
    quelle: Vokabel
    quelle_url: str | None = None
    empfaenger: Vokabel
    platzhalter: dict[str, str] = Field(default_factory=dict)
    geprueft: bool = False
    vorschlaege: list[RechtsbehelfsVorschlag] = Field(default_factory=list)


# --------------------------------------------------------------------------
# document viewer
# --------------------------------------------------------------------------


class Seite(BaseModel):
    nr: int
    text_original: str


class DokumentAnsicht(BaseModel):
    dok_id: str
    dokumenttyp: Vokabel
    dateiname: str | None = None
    quelle: Vokabel
    eingegangen: str
    typ_bestaetigt: bool = False
    seiten: list[Seite] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Referat / Abschluss / footer
# --------------------------------------------------------------------------


class NachforderungAnsicht(BaseModel):
    """Gate 1 — what the advisor copies, and whether they said they sent it.

    The status is separate from the text on purpose: the tool never dispatches
    anything (14 §8), so „angefordert" is a statement the advisor makes, not
    something the program can observe.
    """

    id: str
    kanal: Vokabel
    dokumente: list[Vokabel] = Field(default_factory=list)
    text: str
    status: Vokabel
    zeit: str | None = None


class LaufAnsicht(BaseModel):
    """One entry of `pruefungen[]` — the flip is only visible as a *pair*
    (14 §7), so the history belongs in the view model rather than in the
    frontend's local state."""

    run_id: str
    # Vokabel since 1.5. As a raw code the UI was forbidden to translate it
    # (rule 2) and the screen said „R-1 · initial" — a code where a reader of
    # the history needs an answer to „what happened between these two runs".
    trigger: Vokabel
    zeit: str | None = None
    einordnung: str
    einordnung_tone: vok.Ton
    gerissene_stufe: str | None = None
    gerissene_stufe_titel: str | None = None
    aktuell: bool
    gate3_bestaetigt: bool = False
    gate3_gueltig: bool = True


class BeratungshinweisAnsicht(BaseModel):
    """A sentence of Franz' that is deliberately NOT a Prüfpunkt — advice to
    the advisor, not a finding about the case. Three kinds, told apart by the
    delivered tone: a `warnung` and a `hebel` act on THIS case (gelb), a
    `merker` explicitly does not (grau). `geprueft_von` matters more here than
    on a Prüfpunkt: these are attributed sentences, and a hint without its
    attribution would be the louder gap."""

    id: str
    art: Vokabel
    titel: str
    text: str
    anker: list[Anker] = Field(default_factory=list)
    geprueft_von: list[Fachpruefung] = Field(default_factory=list)


class ReferatKriterium(BaseModel):
    id: str
    label: str
    angehakt: bool
    evidenz: str | None = None


class ReferatPanel(BaseModel):
    kriterien: list[ReferatKriterium] = Field(default_factory=list)
    notiz: str = ""
    markiert: bool = False
    hinweis: str | None = None


class AbschlussPanel(BaseModel):
    basis_export_erzeugt: bool = False
    basis_text: str | None = None
    wiedervorlagen: list[str] = Field(default_factory=list)
    geschlossen: bool = False


class Fusszeile(BaseModel):
    disclaimer: str
    ki_hinweis: str
    schema_version: str
    schema_stand: str
    stand: str
    stichtag: str
    stichtag_modus: str
    betriebskosten_cent: float = 0.0
    fachpruefung_bestaetigt: int = 0
    fachpruefung_gesamt: int = 0
    normbasis_modus: str | None = None


class LeitfadenFrage(BaseModel):
    """One question for the phone (14 §4 step 7). `typ` and `fuellt` are keyed
    on, never rendered: `typ` picks the input widget (ja_nein · zahl ·
    mehrfach · text), `werte[feld_id]` holds the allowed values for `mehrfach`.
    Everything a person reads is `text`, `hinweis`, `status.label`, `grund` —
    and, where a question fills more than one field, `feld_labels[feld_id]` and
    `wert_labels[feld_id][code]`.

    The last two exist because the rule „never rendered" had no alternative to
    offer: a `mehrfach` question needs a caption per input, and with no label
    channel the UI printed the id. „gespraech.strategie" and
    „gespraech.rueckforderung_gewuenscht" stood on the screen of all three
    cases, next to a select whose options were the raw codes (`35` H4). Missing
    label = fall back to the id; that is a gap in the schema, not a licence."""

    pruefpunkt_id: str
    pruefpunkt_titel: str = ""
    text: str
    typ: str = "ja_nein"
    fuellt: list[str] = Field(default_factory=list)
    werte: dict[str, list[str]] = Field(default_factory=dict)
    feld_labels: dict[str, str] = Field(default_factory=dict)
    wert_labels: dict[str, dict[str, str]] = Field(default_factory=dict)
    hinweis: str | None = None
    status: Vokabel
    grund: str = ""
    antwort: dict[str, Any] = Field(default_factory=dict)
    zustand: Vokabel | None = None


class LeitfadenPanel(BaseModel):
    """`POST /faelle/{id}/leitfaden` takes `{antworten: {feld_id: wert}, von}`.
    The batch is atomic — one invalid value rejects all of it with a German
    `detail` and writes nothing — so the panel may send several answers at once.
    An accepted batch appends a run (`trigger: leitfaden_antwort`), which shows
    up in `laeufe[]` and `protokoll[]`: the verdict can change mid-call."""

    fragen: list[LeitfadenFrage] = Field(default_factory=list)
    offen: int = 0


class ProtokollEintrag(BaseModel):
    """One line of the event log (contract §12) — the audit trail the RDG and
    AI-Act framing rests on (14 §8), which until now had no surface at all.

    `akteur` is a role, never an advisor: the log is oversight evidence and
    must not become Leistungskontrolle. `beschreibung` is rendered from the
    event's details by a whitelist in `ansicht.py`; the raw detail dict is
    never shipped, because it may carry pseudonym tokens or an exception text.
    """

    zeit: str
    akteur: str
    aktion: Vokabel
    schritt: Vokabel | None = None
    beschreibung: str = ""


# --------------------------------------------------------------------------
# the whole screen
# --------------------------------------------------------------------------


class FallakteAnsicht(BaseModel):
    """`GET /faelle/{id}`. One object, one screen."""

    ansicht_version: str = ANSICHT_VERSION
    case_id: str
    kopf: Kopf
    hero: Hero
    offene_punkte: list[OffenerPunkt] = Field(default_factory=list)
    pruefpfad: Pruefpfad
    musterbrief: Musterbrief | None = None
    nachforderungen: list[NachforderungAnsicht] = Field(default_factory=list)
    laeufe: list[LaufAnsicht] = Field(default_factory=list)
    leitfaden: LeitfadenPanel
    beratungshinweise: list[BeratungshinweisAnsicht] = Field(default_factory=list)
    referat: ReferatPanel
    abschluss: AbschlussPanel
    dokumente: list[DokumentAnsicht] = Field(default_factory=list)
    protokoll: list[ProtokollEintrag] = Field(default_factory=list)
    fusszeile: Fusszeile


class VokabularAntwort(BaseModel):
    """`GET /vokabular` — every vocabulary, already labelled."""

    ansicht_version: str = ANSICHT_VERSION
    vokabulare: dict[str, list[Vokabel]]

    @classmethod
    def bauen(cls) -> "VokabularAntwort":
        return cls(
            vokabulare={
                name: [Vokabel.von(w) for w in enum_klasse]
                for name, enum_klasse in vok.VOKABULARE.items()
            }
        )
