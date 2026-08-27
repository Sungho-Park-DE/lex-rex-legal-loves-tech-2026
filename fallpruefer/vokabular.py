"""The binding vocabularies of data contract 15 §0 — as code, exactly once.

Every enum value the program or the UI ever shows originates here. Nothing
re-types these strings: the engine keys logic on the enum member, the view
model ships `{code, label, tone}` (contract §0 + 17 §0), and the frontend
renders `label` and colours by `tone`. JSON keys stay German.

`tone` is the only English key in the view model; it was fixed by the Lovable
project knowledge (17 §2 rule 2) before this module existed.
"""

from __future__ import annotations

from enum import Enum

# --------------------------------------------------------------------------
# tone — the 3-state traffic light plus neutral (14 §6, 06 ①)
# --------------------------------------------------------------------------


class Ton(str, Enum):
    GRUEN = "gruen"
    GELB = "gelb"
    ROT = "rot"
    GRAU = "grau"


# --------------------------------------------------------------------------
# the vocabularies
# --------------------------------------------------------------------------


class Einordnung(str, Enum):
    """Verdict. `label` carries the brief's exact wording — never rephrased."""

    WIRKSAM = "wirksam"
    WAHRSCHEINLICH_UNWIRKSAM = "wahrscheinlich_unwirksam"
    UNKLAR = "unklar"


class Zustand(str, Enum):
    JA = "JA"
    NEIN = "NEIN"
    FEHLT = "FEHLT"
    WERTUNG = "WERTUNG"
    INAKTIV = "INAKTIV"


class Rolle(str, Enum):
    TRAGEND = "tragend"
    ERGAENZEND = "ergaenzend"
    GATE = "gate"
    ABLEITUNG = "ableitung"
    STRATEGIE = "strategie"


class Typ(str, Enum):
    FAKT = "fakt"
    TEXT = "text"
    WERTUNG = "wertung"
    LOOKUP = "lookup"


class Herkunft(str, Enum):
    EXPLIZIT = "explizit"
    ANGENOMMEN = "angenommen"
    STRITTIG = "strittig"
    FEHLT = "fehlt"
    GESPRAECH = "gespraech"
    OVERRIDE = "override"


class Dokumenttyp(str, Enum):
    ERHOEHUNGSSCHREIBEN = "erhoehungsschreiben"
    AGB = "agb"
    VERTRAG = "vertrag"
    RECHNUNG = "rechnung"
    KONTOAUSZUG = "kontoauszug"
    KOSTENKALKULATION = "kostenkalkulation"
    ANSCHREIBEN = "anschreiben"
    AUFTRAGSBESTAETIGUNG = "auftragsbestaetigung"
    WIDERRUFSBELEHRUNG = "widerrufsbelehrung"
    INKASSOSCHREIBEN = "inkassoschreiben"
    ABTRETUNGSURKUNDE = "abtretungsurkunde"
    VOLLMACHT = "vollmacht"
    EMAIL = "email"
    SONSTIGES = "sonstiges"


class Pflicht(str, Enum):
    IMMER = "immer"
    BEDINGT = "bedingt"
    ERWARTET_WENN_VORHANDEN = "erwartet_wenn_vorhanden"
    HINWEIS = "hinweis"


class Quelle(str, Enum):
    VERBRAUCHER = "verbraucher"
    UNTERNEHMEN = "unternehmen"


class Fehlzustand(str, Enum):
    """Warum eine Unterlage fehlt — der dritte Zustand neben `Quelle` (V-N2).

    Bis hierher kannte das Modell nur „liegt noch nicht vor", und Gate 1 hat
    daraus eine Nachforderung an die Verbraucherin gemacht. Franz' Fall 6 ist
    der Fall, in dem das falsch wird: es gab nie ein Erhöhungsschreiben. Das
    Werkzeug hätte eine Frau um einen Brief gebeten, den sie nicht besitzen
    kann — die eine Stelle im Programm, an der heute etwas Falsches an einen
    Menschen hinausginge.

    `feld_fehlt_im_dokument` heißt bewusst nicht `nicht_gefunden`: diesen Code
    gibt es als `Badge` schon, für etwas anderes (ein Zitat, das kein Teilstring
    des Dokuments war), und beide stünden auf demselben Prüfpunkt-Bildschirm
    nebeneinander.
    """

    NICHT_EINGEREICHT = "nicht_eingereicht"
    FELD_FEHLT_IM_DOKUMENT = "feld_fehlt_im_dokument"
    EXISTIERT_NICHT = "existiert_nicht"


class Hinweisart(str, Enum):
    """Ein Beratungshinweis ist kein Prüfpunkt (T-H1/T-H6).

    Franz' Lieferungen enthalten mehrfach Sätze, die ausdrücklich keine
    Prüfpunkte sind — „das ist ein Beratungshinweis, kein Prüfpunkt" (`24`
    §5.2, §2.1) — und für die es bis hierher keine Fläche gab. Ein Hinweis
    prüft nichts und erfüllt nichts; er sagt der Beraterin etwas, das sie
    sonst selbst wissen müsste.
    """

    # die Kundin will etwas tun, das ihr schadet (SEPA-Rücklastschrift).
    # Gelb, nicht rot: rot heißt auf diesem Schirm „nicht erfüllt", und ein
    # Hinweis erfüllt nichts — er verlangt eine Handlung der Beraterin.
    WARNUNG = "warnung"
    # ein Argument, das die Beraterin in das Schreiben nehmen kann
    HEBEL = "hebel"
    # gilt nicht für diesen Fall, sondern generell für den nächsten
    MERKER = "merker"


class Massnahme(str, Enum):
    """Franz' Anleitung §7 — welche Maßnahme ein Eintrag in
    `normbasis/abmahnungen.json` festhält. Vergleich und Urteil sind getrennt:
    FitOne endete durch Vergleich, und „Urteil" wäre die Falschzuschreibung,
    die `30` §5 korrigiert hat."""

    ABMAHNUNG = "abmahnung"
    UNTERLASSUNGSERKLAERUNG = "unterlassungserklaerung"
    KLAGE = "klage"
    VERGLEICH = "vergleich"
    URTEIL = "urteil"


class Traeger(str, Enum):
    """Wer das Verfahren geführt hat. vzbv ≠ VZ Bayern (CLAUDE.md-Falle)."""

    VZ_BAYERN = "vz_bayern"
    VZBV = "vzbv"
    ANDERE_VZ = "andere_vz"


class Radarhinweis(str, Enum):
    """Anleitung §7: der Hinweis, der beim erneuten Auftreten einer bereits
    abgemahnten Klausel erscheint — als Chip im Prüfpfad und im Radar."""

    BEREITS_ABGEMAHNT = "bereits_abgemahnt"


class Normrang(str, Enum):
    """Franz' Anleitung §2: „Rangfolge: § 309 BGB vor § 308 BGB vor § 307 BGB,
    da wertungsfreie Treffer prozessual belastbarer sind." Der Chip an einem
    Prüfpunkt, dessen Anker in § 309 oder § 308 liegt. Nur Anzeige — die
    Einordnung kennt keinen Rang (14 §3, `evaluator.py`)."""

    WERTUNGSFREI = "wertungsfrei"


class Verknuepfung(str, Enum):
    """Wie ein Baumknoten seine Kinder zusammenfasst (Schema `baum[].op`)."""

    AND = "AND"
    OR = "OR"


class Baummarker(str, Enum):
    """Markierungen im Prüfbaum, die kein Zustand sind."""

    GERISSEN = "gerissen"
    WURZEL = "wurzel"
    STUFE = "stufe"
    PRUEFPUNKT = "pruefpunkt"


class Kanal(str, Enum):
    VBS = "vbs"
    VOR_ORT = "vor_ort"
    TELEFON = "telefon"
    VIDEO = "video"


class Badge(str, Enum):
    """Die zweite Achse neben `Herkunft` — und ja, auf dem Schirm sehen beide
    im Normalfall gleich aus.

    `Herkunft` sagt, **woher** ein Wert kommt (Unterlage · Gespräch · Annahme ·
    Beraterin · Widerspruch), `Badge` sagt, **wie belastbar** er ist (Zitat
    Zeichen für Zeichen wiedergefunden · Fundstelle ungeprüft · LLM-Auslegung).
    Nebeneinander stehen dann „im Dokument belegt" und „Zitat verifiziert",
    zweimal grün, und die Frage „ist das nicht dasselbe?" ist berechtigt.

    Gemessen 26. Aug über alle fünf Goldenfälle und beide Stufen (307 Chip-
    Zeilen) — wo die Achsen zusammenfallen und wo nicht:

    | Kombination                | n   | Ebene            |
    |----------------------------|-----|------------------|
    | explizit + verifiziert     | 233 | Feld + Prüfpunkt |
    | fehlt + (kein Badge)       |  45 | Prüfpunkt        |
    | **explizit + llm_befund**  |  15 | **nur Prüfpunkt**|
    | angenommen + (kein Badge)  |   7 | Prüfpunkt        |
    | angenommen + angenommen    |   7 | Feld             |

    Auf der **Feldzeile** gehen die beiden Achsen auf der Demolinie **nie**
    auseinander; auseinander gehen sie 15-mal, ausschließlich am Prüfpunkt-Kopf,
    und immer als `explizit + llm_befund`: der Wert steht in der Unterlage, aber
    den *Sinn* der Klausel hat das Sprachmodell gelesen. Das ist die eine Zeile,
    für die es zwei Chips braucht.

    Beide Chips bleiben trotzdem stehen (Register `D10`), aus einem Grund, den
    die Demolinie nicht zeigt: **drei Badges haben überhaupt keine Herkunft.**
    `anker_ungeprueft`, `normbasis_fehlt` und `kreuzpruefung_fehlgeschlagen`
    bewerten die Fundstelle bzw. den Abgleich Schreiben↔AGB, nicht die Herkunft
    eines Feldes — sie sind über `BADGE_RANG` am Prüfpunkt aggregiert und hätten
    in `Herkunft` keinen Platz. Ein Zusammenlegen der Chips verlöre genau die.

    Nicht auf der Demolinie, aber im Programm erreichbar:
    * `gespraech + angenommen` — Leitfaden-Antwort (`leitfaden.py:304`). Der
      einzige Fall mit **zwei verschiedenen Tönen**: grün neben gelb.
    * `explizit + angenommen` — Feld ohne `zitat_pflicht`, aus dem Dokument
      gelesen, aber ohne Zitat (`adapter/basis.py:232`).
    * `strittig + nicht_gefunden` — Widerspruch (`adapter/basis.py:_widersprueche_markieren`).

    Strukturell ausgeschlossen ist `explizit + nicht_gefunden`: ein Zitat, das
    nicht wiedergefunden wurde, führt zum Verwerfen des Faktums
    (`adapter/basis.py:224-226`), und ein Widerspruch schreibt die Herkunft auf
    `strittig` um. Wer diese Kombination auf dem Schirm sieht, sieht einen
    Fehler, keinen Fall.
    """

    VERIFIZIERT = "verifiziert"
    NICHT_GEFUNDEN = "nicht_gefunden"
    ANKER_UNGEPRUEFT = "anker_ungeprueft"
    NORMBASIS_FEHLT = "normbasis_fehlt"
    KREUZPRUEFUNG_FEHLGESCHLAGEN = "kreuzpruefung_fehlgeschlagen"
    ANGENOMMEN = "angenommen"
    LLM_BEFUND = "llm_befund"


class Ebene(str, Enum):
    GESETZ = "gesetz"
    DOGMATIK = "dogmatik"
    RECHTSANWENDUNG = "rechtsanwendung"
    UNENTSCHEIDBAR = "unentscheidbar"


class AnkerStatus(str, Enum):
    GEFESTIGT = "gefestigt"
    IN_BEWEGUNG = "in_bewegung"


class Ankerpruefstand(str, Enum):
    """Hat ein Mensch aus dem Team diese Fundstelle am Originaltext gelesen?

    Bis zum 26.08.2026 stand am Chip das blanke Wort „ungeprüft", von der
    Anzeigeseite selbst getippt. Es hat kein Objekt: „ungeprüft" konnte heißen
    „es ist ungeprüft, ob es diesen Paragrafen gibt" — das Gegenteil dessen,
    was gemeint war. Das Wort gehört deshalb hierher wie jedes andere (06 ⑧),
    mit dem Objekt darin, und die Anzeige tippt es nicht mehr nach.
    """

    GEPRUEFT = "geprueft"
    UNGEPRUEFT = "ungeprueft"


class Stufe(str, Enum):
    """Depth of coverage per Fallgruppe (14 §2)."""

    A = "A"
    B = "B"
    C = "C"


class Briefquelle(str, Enum):
    VZ_MUSTERBRIEF = "vz_musterbrief"
    EIGEN = "eigen"


class Briefstatus(str, Enum):
    ENTWURF = "entwurf"
    UEBERGEBEN = "uebergeben"


class Nachforderungsstatus(str, Enum):
    OFFEN = "offen"
    ANGEFORDERT = "angefordert"
    EINGEGANGEN = "eingegangen"


class Empfaenger(str, Enum):
    ANBIETER = "anbieter"
    GEGNER = "gegner"
    VERBRAUCHER = "verbraucher"


class OffenerPunktArt(str, Enum):
    """View-model only: what kind of open item a row in „Offene Punkte" is."""

    FEHLT = "fehlt"
    WERTUNG = "wertung"
    FRAGE = "frage"


class Fallstatus(str, Enum):
    OFFEN = "offen"
    GESCHLOSSEN = "geschlossen"


class Lauftrigger(str, Enum):
    """Why a run exists. Shown on the Verlauf strip — until 1.5 the UI got the
    raw code (`initial`) and was rightly forbidden to translate it (rule 2),
    so the raw code stood on the screen. The label answers the question a
    reader of the history actually has: what happened between these two runs."""

    INITIAL = "initial"
    NACHREICHUNG = "nachreichung"
    LEITFADEN_ANTWORT = "leitfaden_antwort"
    NICHT_VORHANDEN = "nicht_vorhanden"
    OVERRIDE = "override"
    FALLGRUPPE_GEWECHSELT = "fallgruppe_gewechselt"
    SCHEMA_RELOAD = "schema_reload"


class Leitfadenstatus(str, Enum):
    """Whether a Gesprächsleitfaden question is still worth asking. The point
    of the panel is that these four look different — a screen that renders all
    questions alike throws away what the module computes."""

    OFFEN = "offen"
    BEANTWORTET = "beantwortet"
    ERUEBRIGT = "eruebrigt"
    ENTFAELLT = "entfaellt"


class Protokollschritt(str, Enum):
    """Which of the 14 §4 steps a log line belongs to — ABBYY's „Schritt"
    column, but keyed on our own workflow rather than on a pipeline."""

    EINGANG = "eingang"
    EXTRAKTION = "extraktion"
    FALLGRUPPE = "fallgruppe"
    PRUEFUNG = "pruefung"
    NACHFORDERUNG = "nachforderung"
    NACHREICHUNG = "nachreichung"
    EINORDNUNG = "einordnung"
    LEITFADEN = "leitfaden"
    RECHTSBEHELF = "rechtsbehelf"
    REFERAT = "referat"
    ABSCHLUSS = "abschluss"


class Protokollaktion(str, Enum):
    """Contract §12. One member per `fall.protokoll(...)` call in the package —
    asserted by a test, so a new call site without a label fails the suite."""

    L0_PSEUDONYMISIERT = "l0_pseudonymisiert"
    DOKUMENT_KLASSIFIZIERT = "dokument_klassifiziert"
    EXTRAKTION_VERWORFEN = "extraktion_verworfen"
    FALLGRUPPE_VORSCHLAG_FEHLGESCHLAGEN = "fallgruppe_vorschlag_fehlgeschlagen"
    GATE2_FALLGRUPPE_GEWAEHLT = "gate2_fallgruppe_gewaehlt"
    SCHEMA_GELADEN = "schema_geladen"
    PRUEFUNG_GELAUFEN = "pruefung_gelaufen"
    SCHEMA_STOPP = "schema_stopp"
    GATE1_NACHFORDERUNG_ERZEUGT = "gate1_nachforderung_erzeugt"
    GATE1_NACHFORDERUNG_MARKIERT = "gate1_nachforderung_markiert"
    NACHREICHUNG_EINGEGANGEN = "nachreichung_eingegangen"
    DOKUMENT_ALS_NICHT_VORHANDEN_MARKIERT = "dokument_als_nicht_vorhanden_markiert"
    DOKUMENT_NICHT_VORHANDEN_ZURUECKGEZOGEN = "dokument_nicht_vorhanden_zurueckgezogen"
    GATE3_OVERRIDE = "gate3_override"
    GATE3_OVERRIDE_ZURUECKGEZOGEN = "gate3_override_zurueckgezogen"
    GATE3_BESTAETIGT = "gate3_bestaetigt"
    GATE3_UNGUELTIG = "gate3_ungueltig"
    LEITFADEN_ANTWORT = "leitfaden_antwort"
    GATE4_RECHTSBEHELF_GEWAEHLT = "gate4_rechtsbehelf_gewaehlt"
    RECHTSBEHELF_ENTFAELLT = "rechtsbehelf_entfaellt"
    BRIEF_ERZEUGT = "brief_erzeugt"
    BRIEF_NICHT_ERZEUGT = "brief_nicht_erzeugt"
    BRIEF_STATUS = "brief_status"
    REFERAT_MARKIERT = "referat_markiert"
    STORE_GESCHRIEBEN = "store_geschrieben"
    ABSCHLUSS_BASIS_EXPORT = "abschluss_basis_export"
    FALL_GESCHLOSSEN = "fall_geschlossen"


# --------------------------------------------------------------------------
# labels + tones — the single code -> (label, tone) map
# --------------------------------------------------------------------------

_G = Ton.GRUEN
_Y = Ton.GELB
_R = Ton.ROT
_N = Ton.GRAU

LABELS: dict[type[Enum], dict[Enum, tuple[str, Ton]]] = {
    Einordnung: {
        # binding wording, brief + 14 §5 — the UI prints these verbatim
        Einordnung.WIRKSAM: ("wirksam", _G),
        Einordnung.WAHRSCHEINLICH_UNWIRKSAM: ("wahrscheinlich unwirksam", _R),
        Einordnung.UNKLAR: ("unklar – es fehlt …", _Y),
    },
    Zustand: {
        Zustand.JA: ("erfüllt", _G),
        Zustand.NEIN: ("nicht erfüllt", _R),
        Zustand.FEHLT: ("Angabe fehlt", _Y),
        Zustand.WERTUNG: ("Bewertung nötig", _Y),
        # K58 (Sungho, 25 Aug): „nicht geprüft" ist das Wort aus `28` F3 und aus
        # Franz' Satz auf der Bühne — grau heißt nicht „in Ordnung", sondern
        # „hier hat das Programm nicht hingesehen". ⚠️ Nicht verwechseln mit
        # „(noch) nicht juristisch geprüft" (Anker, Briefe): das ist eine
        # Aussage über die Fundstelle, dieses hier über den Prüfpunkt.
        Zustand.INAKTIV: ("nicht geprüft", _N),
    },
    Rolle: {
        Rolle.TRAGEND: ("tragend", _N),
        Rolle.ERGAENZEND: ("ergänzend", _N),
        Rolle.GATE: ("Vorfrage", _N),
        Rolle.ABLEITUNG: ("Ableitung", _N),
        Rolle.STRATEGIE: ("Strategie", _N),
    },
    Typ: {
        Typ.FAKT: ("Tatsache", _N),
        Typ.TEXT: ("Textverständnis", _N),
        Typ.WERTUNG: ("Wertung", _N),
        Typ.LOOKUP: ("Nachschlagen", _N),
    },
    Herkunft: {
        Herkunft.EXPLIZIT: ("im Dokument belegt", _G),
        Herkunft.ANGENOMMEN: ("angenommen", _Y),
        Herkunft.STRITTIG: ("widersprüchlich belegt", _R),
        Herkunft.FEHLT: ("nicht belegt", _Y),
        Herkunft.GESPRAECH: ("aus dem Gespräch", _G),
        Herkunft.OVERRIDE: ("von der Beraterin gesetzt", _Y),
    },
    Dokumenttyp: {
        Dokumenttyp.ERHOEHUNGSSCHREIBEN: ("Erhöhungsschreiben", _N),
        Dokumenttyp.AGB: ("AGB", _N),
        Dokumenttyp.VERTRAG: ("Vertrag", _N),
        Dokumenttyp.RECHNUNG: ("Rechnung", _N),
        Dokumenttyp.KONTOAUSZUG: ("Kontoauszug", _N),
        Dokumenttyp.KOSTENKALKULATION: ("Kostenkalkulation", _N),
        Dokumenttyp.ANSCHREIBEN: ("Anschreiben", _N),
        Dokumenttyp.AUFTRAGSBESTAETIGUNG: ("Auftragsbestätigung", _N),
        Dokumenttyp.WIDERRUFSBELEHRUNG: ("Widerrufsbelehrung", _N),
        Dokumenttyp.INKASSOSCHREIBEN: ("Inkassoschreiben", _N),
        Dokumenttyp.ABTRETUNGSURKUNDE: ("Abtretungsurkunde", _N),
        Dokumenttyp.VOLLMACHT: ("Vollmacht", _N),
        Dokumenttyp.EMAIL: ("E-Mail", _N),
        Dokumenttyp.SONSTIGES: ("Sonstiges", _N),
    },
    Pflicht: {
        Pflicht.IMMER: ("immer erforderlich", _N),
        Pflicht.BEDINGT: ("bedingt erforderlich", _N),
        Pflicht.ERWARTET_WENN_VORHANDEN: ("erwartet, falls vorhanden", _N),
        Pflicht.HINWEIS: ("Hinweis — nicht beim Verbraucher anfordern", _N),
    },
    Quelle: {
        Quelle.VERBRAUCHER: ("Verbraucherseite", _N),
        Quelle.UNTERNEHMEN: ("Unternehmensseite", _N),
    },
    Hinweisart: {
        # Die Achse, die im Gespräch zählt, ist „betrifft das diesen Fall?" —
        # und sie fällt hier mit unserer eigenen Ton-Bedeutung zusammen: gelb
        # heißt durchgehend „hier muss ein Mensch etwas tun". Abraten und
        # Argumentieren sind beides Handlungen an diesem Fall, ein Merker ist
        # keine. Grün wäre für `hebel` falsch: grün heißt „erfüllt / belegt",
        # und H3 ist ausdrücklich eine Frage, deren Tatsachengrundlage wir
        # nicht haben. Den Unterschied zwischen Abraten und Argumentieren
        # trägt das Label — dafür ist es da.
        Hinweisart.WARNUNG: ("davon abraten", _Y),
        Hinweisart.HEBEL: ("zusätzliches Argument", _Y),
        Hinweisart.MERKER: ("für den nächsten Fall", _N),
    },
    Massnahme: {
        Massnahme.ABMAHNUNG: ("Abmahnung", _Y),
        Massnahme.UNTERLASSUNGSERKLAERUNG: ("Unterlassungserklärung", _Y),
        Massnahme.KLAGE: ("Unterlassungsklage", _Y),
        Massnahme.VERGLEICH: ("Vergleich", _Y),
        Massnahme.URTEIL: ("Urteil", _Y),
    },
    Traeger: {
        Traeger.VZ_BAYERN: ("VZ Bayern", _N),
        Traeger.VZBV: ("vzbv", _N),
        Traeger.ANDERE_VZ: ("andere Verbraucherzentrale", _N),
    },
    Radarhinweis: {
        Radarhinweis.BEREITS_ABGEMAHNT: ("bereits abgemahnt", _Y),
    },
    Normrang: {
        Normrang.WERTUNGSFREI: ("wertungsfrei", _N),
    },
    Ankerpruefstand: {
        Ankerpruefstand.GEPRUEFT: ("Fundstelle gegengelesen", _G),
        Ankerpruefstand.UNGEPRUEFT: ("Fundstelle ungeprüft", _N),
    },
    Verknuepfung: {
        Verknuepfung.AND: ("alle müssen halten", _N),
        Verknuepfung.OR: ("eines genügt", _N),
    },
    Baummarker: {
        Baummarker.GERISSEN: ("gerissen", _R),
        Baummarker.WURZEL: ("Gesamtergebnis", _N),
        Baummarker.STUFE: ("Stufe", _N),
        Baummarker.PRUEFPUNKT: ("Prüfpunkt", _N),
    },
    Fehlzustand: {
        Fehlzustand.NICHT_EINGEREICHT: ("noch nicht eingereicht", _Y),
        Fehlzustand.FELD_FEHLT_IM_DOKUMENT: ("im Dokument nicht enthalten", _Y),
        # grau, nicht rot: „nach Angabe nicht vorhanden" behauptet keinen
        # Verstoß und keinen Mangel. Die Beraterin hat etwas festgestellt, und
        # der Posten hört damit auf, eine offene Forderung zu sein — rot hieße
        # auf diesem Schirm „nicht erfüllt", und das sagt es nicht.
        Fehlzustand.EXISTIERT_NICHT: ("nach Angabe nicht vorhanden", _N),
    },
    Kanal: {
        Kanal.VBS: ("schriftlich (VBS)", _N),
        Kanal.VOR_ORT: ("vor Ort", _N),
        Kanal.TELEFON: ("Telefon", _N),
        Kanal.VIDEO: ("Video", _N),
    },
    Badge: {
        Badge.VERIFIZIERT: ("Zitat verifiziert", _G),
        Badge.NICHT_GEFUNDEN: ("Zitat nicht im Dokument gefunden", _R),
        Badge.ANKER_UNGEPRUEFT: ("Fundstelle noch nicht juristisch geprüft", _N),
        Badge.NORMBASIS_FEHLT: ("Norm nicht in unserer Normbasis", _R),
        Badge.KREUZPRUEFUNG_FEHLGESCHLAGEN: ("Kreuzprüfung fehlgeschlagen", _R),
        Badge.ANGENOMMEN: ("angenommen", _Y),
        Badge.LLM_BEFUND: ("LLM-Befund, bitte prüfen", _Y),
    },
    Ebene: {
        Ebene.GESETZ: ("Gesetz", _N),
        Ebene.DOGMATIK: ("Dogmatik", _N),
        Ebene.RECHTSANWENDUNG: ("Rechtsanwendung", _N),
        Ebene.UNENTSCHEIDBAR: ("unentscheidbar", _N),
    },
    AnkerStatus: {
        AnkerStatus.GEFESTIGT: ("gefestigt", _N),
        AnkerStatus.IN_BEWEGUNG: ("in Bewegung", _Y),
    },
    Stufe: {
        Stufe.A: ("Stufe A — volles Prüfschema", _N),
        Stufe.B: ("Stufe B — Unterlagen und Einordnungsvorschlag", _N),
        Stufe.C: ("Stufe C — nur Zuordnung", _N),
    },
    Briefquelle: {
        Briefquelle.VZ_MUSTERBRIEF: ("VZ-Musterbrief", _N),
        Briefquelle.EIGEN: ("Eigener Entwurf (nicht juristisch geprüft)", _Y),
    },
    Briefstatus: {
        Briefstatus.ENTWURF: ("Entwurf", _Y),
        Briefstatus.UEBERGEBEN: ("übergeben", _G),
    },
    Nachforderungsstatus: {
        Nachforderungsstatus.OFFEN: ("offen", _Y),
        Nachforderungsstatus.ANGEFORDERT: ("angefordert", _Y),
        Nachforderungsstatus.EINGEGANGEN: ("eingegangen", _G),
    },
    Empfaenger: {
        Empfaenger.ANBIETER: ("an den Anbieter", _N),
        Empfaenger.GEGNER: ("an die Gegenseite", _N),
        Empfaenger.VERBRAUCHER: ("an die Verbraucherin", _N),
    },
    OffenerPunktArt: {
        OffenerPunktArt.FEHLT: ("fehlende Unterlage", _Y),
        OffenerPunktArt.WERTUNG: ("Bewertung durch die Beraterin", _Y),
        OffenerPunktArt.FRAGE: ("Frage ans Gespräch", _Y),
    },
    Fallstatus: {
        Fallstatus.OFFEN: ("offen", _N),
        Fallstatus.GESCHLOSSEN: ("geschlossen", _N),
    },
    Lauftrigger: {
        Lauftrigger.INITIAL: ("Ersteingang", _N),
        Lauftrigger.NACHREICHUNG: ("nach Nachreichung", _N),
        Lauftrigger.LEITFADEN_ANTWORT: ("nach Antwort aus dem Gespräch", _N),
        Lauftrigger.NICHT_VORHANDEN: ("nach Feststellung: existiert nicht", _N),
        Lauftrigger.OVERRIDE: ("nach Überschreibung", _N),
        Lauftrigger.FALLGRUPPE_GEWECHSELT: ("nach Fallgruppenwechsel", _N),
        Lauftrigger.SCHEMA_RELOAD: ("nach Regeländerung", _N),
    },
    Leitfadenstatus: {
        Leitfadenstatus.OFFEN: ("offen", _Y),
        Leitfadenstatus.BEANTWORTET: ("beantwortet", _G),
        Leitfadenstatus.ERUEBRIGT: ("steht in den Unterlagen", _N),
        Leitfadenstatus.ENTFAELLT: ("entfällt", _N),
    },
    Protokollschritt: {
        Protokollschritt.EINGANG: ("Eingang", _N),
        Protokollschritt.EXTRAKTION: ("Extraktion", _N),
        Protokollschritt.FALLGRUPPE: ("Fallgruppe · Gate 2", _N),
        Protokollschritt.PRUEFUNG: ("Prüfung", _N),
        Protokollschritt.NACHFORDERUNG: ("Nachforderung · Gate 1", _N),
        Protokollschritt.NACHREICHUNG: ("Nachreichung", _N),
        Protokollschritt.EINORDNUNG: ("Einordnung · Gate 3", _N),
        Protokollschritt.LEITFADEN: ("Gesprächsleitfaden", _N),
        Protokollschritt.RECHTSBEHELF: ("Rechtsbehelf · Gate 4", _N),
        Protokollschritt.REFERAT: ("Referat", _N),
        Protokollschritt.ABSCHLUSS: ("Abschluss", _N),
    },
    # `tone` here is NOT the verdict traffic light: a log line is never a
    # verdict, so gruen and rot never occur. gelb means „this line has to be
    # explained when someone reads the log back" — the discarded, the failed
    # and the overridden. Everything else is grau.
    Protokollaktion: {
        Protokollaktion.L0_PSEUDONYMISIERT: ("Identitäten pseudonymisiert", _N),
        Protokollaktion.DOKUMENT_KLASSIFIZIERT: ("Dokument eingeordnet", _N),
        Protokollaktion.EXTRAKTION_VERWORFEN: ("Extraktion verworfen", _Y),
        Protokollaktion.FALLGRUPPE_VORSCHLAG_FEHLGESCHLAGEN: (
            "Fallgruppen-Vorschlag fehlgeschlagen", _Y),
        Protokollaktion.GATE2_FALLGRUPPE_GEWAEHLT: ("Fallgruppe gewählt", _N),
        Protokollaktion.SCHEMA_GELADEN: ("Prüfschema geladen", _N),
        Protokollaktion.PRUEFUNG_GELAUFEN: ("Prüfung gelaufen", _N),
        Protokollaktion.SCHEMA_STOPP: ("Prüfschema gestoppt", _Y),
        Protokollaktion.GATE1_NACHFORDERUNG_ERZEUGT: ("Nachforderung erzeugt", _N),
        Protokollaktion.GATE1_NACHFORDERUNG_MARKIERT: (
            "Nachforderung als angefordert markiert", _N),
        Protokollaktion.NACHREICHUNG_EINGEGANGEN: ("Unterlagen nachgereicht", _N),
        Protokollaktion.DOKUMENT_ALS_NICHT_VORHANDEN_MARKIERT:
            ("als nicht vorhanden festgestellt", _N),
        Protokollaktion.DOKUMENT_NICHT_VORHANDEN_ZURUECKGEZOGEN:
            ("Feststellung zurückgenommen", _N),
        Protokollaktion.GATE3_OVERRIDE: ("Prüfpunkt überschrieben", _Y),
        Protokollaktion.GATE3_OVERRIDE_ZURUECKGEZOGEN: (
            "Überschreibung zurückgezogen", _Y),
        Protokollaktion.GATE3_BESTAETIGT: ("Einordnung bestätigt", _N),
        Protokollaktion.GATE3_UNGUELTIG: ("Frühere Bestätigung überholt", _Y),
        Protokollaktion.LEITFADEN_ANTWORT: ("Antwort aus dem Gespräch", _N),
        Protokollaktion.GATE4_RECHTSBEHELF_GEWAEHLT: ("Rechtsbehelf gewählt", _N),
        Protokollaktion.RECHTSBEHELF_ENTFAELLT: ("Kein Rechtsbehelf hinterlegt", _Y),
        Protokollaktion.BRIEF_ERZEUGT: ("Musterschreiben erzeugt", _N),
        Protokollaktion.BRIEF_NICHT_ERZEUGT: ("Musterschreiben nicht erzeugt", _Y),
        Protokollaktion.BRIEF_STATUS: ("Briefstatus gesetzt", _N),
        Protokollaktion.REFERAT_MARKIERT: ("Für das Referat markiert", _N),
        Protokollaktion.STORE_GESCHRIEBEN: ("Fallobjekt gespeichert", _N),
        Protokollaktion.ABSCHLUSS_BASIS_EXPORT: ("Basis-Eintrag erzeugt", _N),
        Protokollaktion.FALL_GESCHLOSSEN: ("Fall geschlossen", _N),
    },
}

# Contract §12 / 14 §4 — which step a log line belongs to. Kept next to the
# labels because it is vocabulary, not logic: `ansicht.py` only looks it up.
PROTOKOLL_SCHRITT: dict[Protokollaktion, Protokollschritt] = {
    Protokollaktion.L0_PSEUDONYMISIERT: Protokollschritt.EINGANG,
    Protokollaktion.DOKUMENT_KLASSIFIZIERT: Protokollschritt.EXTRAKTION,
    Protokollaktion.EXTRAKTION_VERWORFEN: Protokollschritt.EXTRAKTION,
    Protokollaktion.FALLGRUPPE_VORSCHLAG_FEHLGESCHLAGEN: Protokollschritt.FALLGRUPPE,
    Protokollaktion.GATE2_FALLGRUPPE_GEWAEHLT: Protokollschritt.FALLGRUPPE,
    Protokollaktion.SCHEMA_GELADEN: Protokollschritt.PRUEFUNG,
    Protokollaktion.PRUEFUNG_GELAUFEN: Protokollschritt.PRUEFUNG,
    Protokollaktion.SCHEMA_STOPP: Protokollschritt.PRUEFUNG,
    Protokollaktion.GATE1_NACHFORDERUNG_ERZEUGT: Protokollschritt.NACHFORDERUNG,
    Protokollaktion.GATE1_NACHFORDERUNG_MARKIERT: Protokollschritt.NACHFORDERUNG,
    Protokollaktion.NACHREICHUNG_EINGEGANGEN: Protokollschritt.NACHREICHUNG,
    # Schritt NACHFORDERUNG, nicht NACHREICHUNG: die Feststellung entscheidet,
    # ob und bei wem etwas angefordert wird — sie steht neben Gate 1, nicht
    # neben dem Eingang von Unterlagen.
    Protokollaktion.DOKUMENT_ALS_NICHT_VORHANDEN_MARKIERT: Protokollschritt.NACHFORDERUNG,
    Protokollaktion.DOKUMENT_NICHT_VORHANDEN_ZURUECKGEZOGEN: Protokollschritt.NACHFORDERUNG,
    Protokollaktion.GATE3_OVERRIDE: Protokollschritt.EINORDNUNG,
    Protokollaktion.GATE3_OVERRIDE_ZURUECKGEZOGEN: Protokollschritt.EINORDNUNG,
    Protokollaktion.GATE3_BESTAETIGT: Protokollschritt.EINORDNUNG,
    Protokollaktion.GATE3_UNGUELTIG: Protokollschritt.EINORDNUNG,
    Protokollaktion.LEITFADEN_ANTWORT: Protokollschritt.LEITFADEN,
    Protokollaktion.GATE4_RECHTSBEHELF_GEWAEHLT: Protokollschritt.RECHTSBEHELF,
    Protokollaktion.RECHTSBEHELF_ENTFAELLT: Protokollschritt.RECHTSBEHELF,
    Protokollaktion.BRIEF_ERZEUGT: Protokollschritt.RECHTSBEHELF,
    Protokollaktion.BRIEF_NICHT_ERZEUGT: Protokollschritt.RECHTSBEHELF,
    Protokollaktion.BRIEF_STATUS: Protokollschritt.RECHTSBEHELF,
    Protokollaktion.REFERAT_MARKIERT: Protokollschritt.REFERAT,
    Protokollaktion.STORE_GESCHRIEBEN: Protokollschritt.REFERAT,
    Protokollaktion.ABSCHLUSS_BASIS_EXPORT: Protokollschritt.ABSCHLUSS,
    Protokollaktion.FALL_GESCHLOSSEN: Protokollschritt.ABSCHLUSS,
}

# Which vocabularies `GET /vokabular` exposes, under which key.
VOKABULARE: dict[str, type[Enum]] = {
    "einordnung": Einordnung,
    "zustand": Zustand,
    "rolle": Rolle,
    "typ": Typ,
    "herkunft": Herkunft,
    "dokumenttyp": Dokumenttyp,
    "pflicht": Pflicht,
    "quelle": Quelle,
    "fehlzustand": Fehlzustand,
    "hinweisart": Hinweisart,
    "kanal": Kanal,
    "badge": Badge,
    "ebene": Ebene,
    "anker_status": AnkerStatus,
    "stufe": Stufe,
    "briefquelle": Briefquelle,
    "briefstatus": Briefstatus,
    "nachforderungsstatus": Nachforderungsstatus,
    "empfaenger": Empfaenger,
    "offener_punkt_art": OffenerPunktArt,
    "fallstatus": Fallstatus,
    "leitfadenstatus": Leitfadenstatus,
    "lauftrigger": Lauftrigger,
    "protokollaktion": Protokollaktion,
    "protokollschritt": Protokollschritt,
    # `Ton` is deliberately absent: it is the colour axis every other
    # vocabulary carries, not a vocabulary the UI renders on its own.
}

# --------------------------------------------------------------------------
# precedence rules — also part of the vocabulary, not of any caller
# --------------------------------------------------------------------------

# Worst wins: what a Prüfpunkt's aggregated badge is, given its facts' badges.
BADGE_RANG: dict[Badge, int] = {
    Badge.KREUZPRUEFUNG_FEHLGESCHLAGEN: 0,
    Badge.NICHT_GEFUNDEN: 1,
    Badge.NORMBASIS_FEHLT: 2,
    Badge.ANKER_UNGEPRUEFT: 3,
    Badge.LLM_BEFUND: 4,
    Badge.ANGENOMMEN: 5,
    Badge.VERIFIZIERT: 6,
}

# Worst wins: a Prüfpunkt's aggregated provenance over the facts it used.
HERKUNFT_RANG: dict[Herkunft, int] = {
    Herkunft.STRITTIG: 0,
    Herkunft.FEHLT: 1,
    Herkunft.ANGENOMMEN: 2,
    Herkunft.OVERRIDE: 3,
    Herkunft.GESPRAECH: 4,
    Herkunft.EXPLIZIT: 5,
}


# Erklärungen für die Chips, die auf dem Schirm nicht selbsterklärend sind.
# Die erste Rückfrage aus dem Team (25 Aug, Prüfpfad P1) war „tragend? Tatsache?"
# — die Wörter tragen den Sinn nur für den, der das Schema kennt. Das UI zeigt
# den Satz als Tooltip; es formuliert ihn nie selbst (06 ⑧).
ERKLAERUNG: dict[Enum, str] = {
    Rolle.TRAGEND: "Kann den Fall allein kippen: ist dieser Punkt nicht erfüllt, "
                   "lautet die Einordnung „wahrscheinlich unwirksam\u201c.",
    Rolle.ERGAENZEND: "Hinweis für das Gespräch — ändert die Einordnung nicht.",
    Rolle.GATE: "Vorfrage: muss zuerst passen, sonst wird nicht weitergeprüft.",
    Rolle.ABLEITUNG: "Folgt aus der Einordnung, wird nicht selbst geprüft.",
    Rolle.STRATEGIE: "Nächster Schritt mit der Verbraucherin, keine Rechtsfrage.",
    Typ.FAKT: "Eine Tatsache aus den Unterlagen (Datum, Betrag, ob etwas genannt "
              "ist) — das Programm prüft sie nach Regel.",
    Typ.TEXT: "Hier muss jemand den Sinn einer Klausel lesen. Das Sprachmodell "
              "schlägt vor, die Beraterin prüft (gelber Chip).",
    Typ.WERTUNG: "Einschätzung der Beraterin — das Programm stellt die Frage, "
                 "entscheidet sie aber nicht.",
    Typ.LOOKUP: "Wird in einer Quelle nachgeschlagen, nicht aus dem Fall gelesen.",
    Badge.LLM_BEFUND: "Textverständnis: Das Sprachmodell hat den Sinn der Klausel gelesen "
                      "und schlägt das Ergebnis vor — bitte am Zitat prüfen.",
    # Zustand
    Zustand.WERTUNG: "Das Programm kann diesen Punkt nicht allein entscheiden — die "
                     "Beraterin bewertet, das Ergebnis bleibt bis dahin offen.",
    Zustand.INAKTIV: "Bei dieser Einordnung spielt der Punkt keine Rolle; er wurde "
                     "nicht geprüft.",
    # Herkunft — woher der Wert kommt
    Herkunft.EXPLIZIT: "Der Wert steht so in den Unterlagen; das Zitat daneben ist die "
                       "Stelle.",
    Herkunft.ANGENOMMEN: "Der Wert steht nicht in den Unterlagen. Das Programm hat eine "
                         "ausgewiesene Annahme eingesetzt — bitte im Gespräch bestätigen.",
    Herkunft.STRITTIG: "Zwei Unterlagen sagen Verschiedenes; beide Werte stehen hier, "
                       "die Beraterin entscheidet.",
    Herkunft.FEHLT: "Der Wert steht in keiner vorliegenden Unterlage.",
    Herkunft.GESPRAECH: "Antwort der Verbraucherin aus dem Gesprächsleitfaden.",
    Herkunft.OVERRIDE: "Von der Beraterin gesetzt oder überschrieben — steht so im "
                        "Protokoll.",
    # Badge — was geprüft wurde
    Badge.VERIFIZIERT: "Das Zitat wurde Zeichen für Zeichen im Dokument wiedergefunden.",
    Badge.NICHT_GEFUNDEN: "Das Zitat steht so nicht im Dokument — der Wert ist nicht "
                          "belegt und wird nicht verwendet.",
    Badge.ANKER_UNGEPRUEFT: "Die Gesetzesstelle ist hinterlegt, aber noch von niemandem "
                            "am Originaltext gegengeprüft.",
    # Ankerpruefstand — dieselbe Aussage am Chip der einzelnen Fundstelle
    Ankerpruefstand.GEPRUEFT: "Jemand aus dem Team hat diese Fundstelle im Originaltext "
                              "gelesen und bestätigt.",
    Ankerpruefstand.UNGEPRUEFT: "Der Gesetzestext liegt vor und ist unverändert übernommen "
                                "— gegengelesen am Original hat ihn niemand aus dem Team.",
    Badge.NORMBASIS_FEHLT: "Die genannte Norm liegt nicht in unserer Sammlung der "
                           "Gesetzestexte vor.",
    Badge.KREUZPRUEFUNG_FEHLGESCHLAGEN: "Das Schreiben verweist auf eine Klausel, die sich in den "
                         "vorgelegten AGB so nicht findet.",
    Badge.ANGENOMMEN: "Ein Wert dieses Punkts ist eine ausgewiesene Annahme, kein Beleg.",
    # Radar / Anleitung §7
    Radarhinweis.BEREITS_ABGEMAHNT: "Dieser Klauseltyp war schon Gegenstand einer Abmahnung "
                                    "oder Klage einer Verbraucherzentrale. Das sagt nichts "
                                    "über diesen Anbieter — nur, dass die Klausel bekannt ist.",
    Normrang.WERTUNGSFREI: "Ein Verstoß gegen § 309 oder § 308 BGB gilt ohne Wertung — "
                           "prozessual belastbarer als die Abwägung nach § 307.",
    Verknuepfung.AND: "Diese Stufe hält nur, wenn jeder ihrer Prüfpunkte hält — ein einziger "
                      "nicht erfüllter tragender Punkt reißt sie.",
    Verknuepfung.OR: "Diese Stufe hält schon, wenn einer ihrer Prüfpunkte hält.",
    Baummarker.GERISSEN: "An dieser Stufe ist die Prüfung zum ersten Mal gescheitert — sie trägt "
                         "die Einordnung.",
    # Kanal
    Kanal.VBS: "Virtuelle Beratungsstelle — die Anfrage kam schriftlich über das "
               "Online-Ticket der Verbraucherzentrale.",
}


def erklaerung(wert: Enum) -> str | None:
    return ERKLAERUNG.get(wert)


def label(wert: Enum) -> str:
    """The display string for an enum member."""
    return LABELS[type(wert)][wert][0]


def ton(wert: Enum) -> Ton:
    """The traffic-light tone for an enum member."""
    return LABELS[type(wert)][wert][1]


def schlimmster_badge(badges: list[Badge]) -> Badge:
    return min(badges, key=lambda b: BADGE_RANG[b]) if badges else Badge.VERIFIZIERT


def schlimmste_herkunft(herkuenfte: list[Herkunft]) -> Herkunft:
    if not herkuenfte:
        return Herkunft.FEHLT
    return min(herkuenfte, key=lambda h: HERKUNFT_RANG[h])
