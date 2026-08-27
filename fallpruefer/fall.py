"""The case object (contract §4) — `cases/<case_id>.json`.

This file contains the pseudonym map and therefore never leaves the machine.
Re-identification happens in exactly two local places: the advisor display and
the template fill.

Note the shape of `pruefungen[]`: every trigger (initial · nachreichung ·
leitfaden_antwort · override · schema_reload) appends a *new* run rather than
mutating the last one. That is what makes the Nachreichung flip demonstrable —
the old verdict is still there to compare against.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from fallpruefer.vokabular import (
    Badge,
    Briefstatus,
    Dokumenttyp,
    Einordnung,
    Empfaenger,
    Fallstatus,
    Fehlzustand,
    Herkunft,
    Kanal,
    Nachforderungsstatus,
    Quelle,
    Stufe,
    Zustand,
)


class Identitaet(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str | None = None
    adresse: str | None = None
    email: str | None = None
    telefon: str | None = None
    kundennummer: str | None = None
    geburtsdatum: str | None = None


class Eingang(BaseModel):
    model_config = ConfigDict(extra="allow")
    kanal: Kanal = Kanal.VBS
    ticket_nr: str | None = None
    thema: str | None = None
    freitext_original: str = ""
    freitext_pseudonym: str = ""
    anbieter: str | None = None
    anbieter_quelle: str | None = None
    gegner: str | None = None
    branche: str | None = None
    eingegangen_am: str | None = None
    identitaet: Identitaet = Field(default_factory=Identitaet)
    sensible_inhalte_flag: bool = False


class SeiteText(BaseModel):
    nr: int
    text_original: str
    text_pseudonym: str = ""


class Dokument(BaseModel):
    model_config = ConfigDict(extra="allow")
    dok_id: str
    dokumenttyp: Dokumenttyp
    dateiname: str | None = None
    hash: str | None = None
    seiten: list[SeiteText] = Field(default_factory=list)
    quelle: Quelle = Quelle.VERBRAUCHER
    eingegangen: str = "eingang"
    typ_konfidenz: float | None = None
    typ_bestaetigt: bool = False
    nachforderung_id: str | None = None
    fassung_datum: str | None = None

    @property
    def text_pseudonym(self) -> str:
        return "\n".join(s.text_pseudonym for s in self.seiten)

    @property
    def text_original(self) -> str:
        return "\n".join(s.text_original for s in self.seiten)


class Quellenangabe(BaseModel):
    dok_id: str
    seite: int
    zitat_pseudonym: str
    offset: int | None = None


class Faktum(BaseModel):
    model_config = ConfigDict(extra="allow")
    feld_id: str
    wert: Any = None
    dok_id: str | None = None
    herkunft: Herkunft = Herkunft.EXPLIZIT
    annahme_id: str | None = None
    quelle: Quellenangabe | None = None
    verifiziert: bool | None = None
    badge: Badge = Badge.VERIFIZIERT
    llm_run: str | None = None
    von: str | None = None
    zeit: str | None = None


class FallgruppenVorschlag(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    begruendung: str = ""
    zitate: list[Quellenangabe] = Field(default_factory=list)


class Fallgruppenwahl(BaseModel):
    model_config = ConfigDict(extra="allow")
    vorschlaege: list[FallgruppenVorschlag] = Field(default_factory=list)
    gewaehlt: str | None = None
    stufe: Stufe | None = None
    gate2_von: str | None = None
    zeit: str | None = None
    bestaetigt: bool = False
    # No proposal came back (model unreachable, cache miss, taxonomy refusal).
    # The Fallgruppe is then the fallback, not a finding — Gate 2 has to say so
    # rather than let the case be assessed as whatever the default happens to be.
    vorschlag_fehlt: bool = False


class Fristangabe(BaseModel):
    name: str
    wert: str
    stand: str | None = None
    annahmen: list[str] = Field(default_factory=list)


class Betragangabe(BaseModel):
    name: str
    wert: str
    roh: float | None = None
    annahmen: list[str] = Field(default_factory=list)


class Pruefergebnis(BaseModel):
    """Contract §5 — the engine's output per Prüfpunkt."""

    model_config = ConfigDict(extra="allow")
    pruefpunkt_id: str
    zustand: Zustand
    grund: str = ""
    verwendet: list[str] = Field(default_factory=list)
    zitate: list[Quellenangabe] = Field(default_factory=list)
    anker: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    # Three parallel lists of feld_ids with three different meanings:
    #   verwendet         read, and the rule used the value
    #   missing           required and absent — this is what Gate 1 asks for
    #   strittige_felder  present twice, contradicting, therefore unusable
    # The third exists because the second is the wrong home for it: a
    # contradicted field is not missing, and putting it in `missing` would make
    # the tool ask the consumer for a document that is already in the file.
    # Without it the field fell out of the trace entirely — the advisor was
    # asked at Gate 3 to resolve a conflict whose two halves were nowhere.
    strittige_felder: list[str] = Field(default_factory=list)
    owner: Quelle | None = None
    wertungsfrage: str | None = None
    llm_befund: bool = False
    badge: Badge | None = None
    frist: Fristangabe | None = None
    betrag: Betragangabe | None = None
    herkunft: Herkunft = Herkunft.EXPLIZIT
    inaktiv_grund: str | None = None
    override: bool = False


class FehlendesElement(BaseModel):
    model_config = ConfigDict(extra="allow")
    dokumenttyp: Dokumenttyp | None = None
    feld_id: str | None = None
    quelle: Quelle = Quelle.VERBRAUCHER
    grund: str = ""
    pruefpunkt_id: str | None = None
    # V-N2: `grund` war bisher Fließtext („nicht eingereicht", „im Dokument
    # nicht gefunden") und damit für eine Fallunterscheidung unbrauchbar.
    # `fehlzustand` ist derselbe Satz als Code; `grund` bleibt der Satz.
    fehlzustand: Fehlzustand = Fehlzustand.NICHT_EINGEREICHT
    # nur bei EXISTIERT_NICHT: der O-Ton, auf den sich die Feststellung stützt
    aussage: str | None = None


class Pruefung(BaseModel):
    model_config = ConfigDict(extra="allow")
    run_id: str
    trigger: str = "initial"
    ausgeloest_durch: str | None = None
    zeit: str | None = None
    schema_version: str = ""
    schema_stand: str = ""
    ergebnisse: list[Pruefergebnis] = Field(default_factory=list)
    baum_zustaende: dict[str, Zustand] = Field(default_factory=dict)
    einordnung: str = ""
    einordnung_code: Einordnung | None = None
    vollstaendigkeit: dict[str, list[FehlendesElement]] = Field(default_factory=dict)
    gerissene_stufe: str | None = None
    pruefumfang: list[str] = Field(default_factory=list)
    # nur IDs (T-H1/T-H6) — die Texte stehen im Schema, wie bei `pruefumfang`
    beratungshinweise: list[str] = Field(default_factory=list)
    plain: list[str] = Field(default_factory=list)
    schema_stopp_text: str | None = None
    gate3: dict | None = None
    aktuell: bool = True

    def ergebnis(self, pid: str) -> Pruefergebnis | None:
        return next((e for e in self.ergebnisse if e.pruefpunkt_id == pid), None)


class NichtVorhanden(BaseModel):
    """Die Feststellung der Beraterin, dass eine Unterlage nie existiert hat.

    Sie lebt am Fall und nicht an der einzelnen Pruefung, weil sie jeden
    weiteren Lauf überdauern muss: „es gab nie ein Erhöhungsschreiben" wird
    durch eine Nachreichung anderer Unterlagen nicht falsch. Zurückgenommen
    wird sie wie ein Override — annotiert, nicht gelöscht.
    """

    model_config = ConfigDict(extra="allow")
    dokumenttyp: Dokumenttyp
    aussage: str
    von: str = "Beraterin"
    zeit: str | None = None
    zurueckgezogen: bool = False


class Override(BaseModel):
    model_config = ConfigDict(extra="allow")
    pruefpunkt_id: str
    neuer_zustand: Zustand
    grund: str
    von: str = "Beraterin"
    zeit: str | None = None
    gilt_fuer_runs: str | None = None
    zurueckgezogen: bool = False


class Nachforderung(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    kanal: Kanal = Kanal.VBS
    dokumente: list[Dokumenttyp] = Field(default_factory=list)
    text: str = ""
    status: Nachforderungsstatus = Nachforderungsstatus.OFFEN
    markiert_von: str | None = None
    zeit: str | None = None


class Brief(BaseModel):
    model_config = ConfigDict(extra="allow")
    template_id: str
    titel: str = ""
    text: str = ""
    variante: str | None = None
    quelle: str = "eigen"
    quelle_url: str | None = None
    platzhalter: dict[str, str] = Field(default_factory=dict)
    status: Briefstatus = Briefstatus.ENTWURF
    empfaenger: Empfaenger = Empfaenger.ANBIETER
    geprueft: bool = False


class Rechtsbehelfwahl(BaseModel):
    model_config = ConfigDict(extra="allow")
    hauptvorschlag: str | None = None
    vorschlaege: list[str] = Field(default_factory=list)
    gewaehlt: str | None = None
    gate4_von: str | None = None
    brief: Brief | None = None


class ReferatMarkierung(BaseModel):
    model_config = ConfigDict(extra="allow")
    kriterien: list[str] = Field(default_factory=list)
    notiz: str = ""
    von: str | None = None
    zeit: str | None = None
    evidenz: dict[str, Any] = Field(default_factory=dict)


class Abschluss(BaseModel):
    model_config = ConfigDict(extra="allow")
    basis_export_erzeugt: bool = False
    basis_text: str | None = None
    wiedervorlagen: list[str] = Field(default_factory=list)
    geschlossen: bool = False


# Contract §12: the log is oversight evidence and must not become
# Leistungskontrolle — it names roles, never advisors. The guard is code
# rather than a review checklist because `von` is threaded through every
# gate function and had already reached one `protokoll()` call.
VERBOTENE_LOG_DETAILS = ("von", "akteur", "name", "benutzer", "bearbeiter")


class Ereignis(BaseModel):
    zeit: str
    akteur: str = "Beraterin"
    aktion: str
    details: dict[str, Any] = Field(default_factory=dict)


class LLMRun(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    aufgabe: str
    modell: str
    prompt_version: str
    dok_id: str | None = None
    cache_datei: str | None = None
    aus_cache: bool = True
    dauer_ms: int = 0
    kosten_cent: float = 0.0
    zeit: str | None = None


class SchemaRef(BaseModel):
    fallgruppe_id: str
    version: str = ""
    stand: str = ""


class Fall(BaseModel):
    model_config = ConfigDict(extra="allow")
    case_id: str
    schema_: SchemaRef = Field(alias="schema")
    status: Fallstatus = Fallstatus.OFFEN
    stichtag: str | date | None = None
    eingang: Eingang = Field(default_factory=Eingang)
    pseudonyme: dict[str, str] = Field(default_factory=dict)
    dokumente: list[Dokument] = Field(default_factory=list)
    fakten: list[Faktum] = Field(default_factory=list)
    fallgruppe: Fallgruppenwahl = Field(default_factory=Fallgruppenwahl)
    dokumenten_soll: dict[str, Any] = Field(default_factory=dict)
    nachforderungen: list[Nachforderung] = Field(default_factory=list)
    pruefungen: list[Pruefung] = Field(default_factory=list)
    overrides: list[Override] = Field(default_factory=list)
    nicht_vorhanden: list[NichtVorhanden] = Field(default_factory=list)
    leitfaden: dict[str, Any] = Field(default_factory=dict)
    rechtsbehelf: Rechtsbehelfwahl = Field(default_factory=Rechtsbehelfwahl)
    referat_markierung: ReferatMarkierung = Field(default_factory=ReferatMarkierung)
    abschluss: Abschluss = Field(default_factory=Abschluss)
    ereignisse: list[Ereignis] = Field(default_factory=list)
    llm_runs: list[LLMRun] = Field(default_factory=list)

    def dokument(self, dok_id: str) -> Dokument | None:
        return next((d for d in self.dokumente if d.dok_id == dok_id), None)

    def dokumente_vom_typ(self, typ: Dokumenttyp) -> list[Dokument]:
        return [d for d in self.dokumente if d.dokumenttyp == typ]

    def aktuelle_pruefung(self) -> Pruefung | None:
        return next((p for p in reversed(self.pruefungen) if p.aktuell), None)

    def protokoll(self, aktion: str, **details: Any) -> None:
        from fallpruefer.zeit import jetzt

        verboten = sorted(set(details) & set(VERBOTENE_LOG_DETAILS))
        if verboten:
            raise ValueError(
                f"protokoll({aktion!r}): {', '.join(verboten)} benennt eine Person. "
                "Das Ereignisprotokoll führt Rollen, keine Namen (Kontrakt §12)."
            )
        self.ereignisse.append(Ereignis(zeit=jetzt(), aktion=aktion, details=details))
