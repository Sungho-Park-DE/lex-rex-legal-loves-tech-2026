"""FastAPI — three endpoints, local only.

Local only is a design constraint, not a shortcut (contract §4): the case
object holds the pseudonym map, so the process that holds it must be the one
on the advisor's machine. The frontend is a separate app that talks to this
over localhost; demo day runs both locally.

    POST /faelle                    ticket free text + attachments → L0 → L1 → L2 → case_id
    POST /faelle/{id}/dokumente     a Nachreichung: same case, one more run
    GET  /faelle/{id}               the Fallakte view model (14 §6 screen 1)
    POST /faelle/{id}/fallgruppe    Gate 2 — bestätigen oder wechseln
    POST /faelle/{id}/nachforderung Gate 1 — Text erzeugen / als angefordert markieren
    POST /faelle/{id}/nicht-vorhanden  eine Unterlage hat es nie gegeben (V-N2)
    POST /faelle/{id}/override      Gate 3 — Prüfpunkt überschreiben mit Grund
    POST /faelle/{id}/gate3         Einordnung bestätigt → the case enters the store
    POST /faelle/{id}/rechtsbehelf  Gate 4 — Rechtsbehelf wählen, Schreiben neu füllen
    POST /faelle/{id}/abschluss     Basis-Eintrag, Wiedervorlagen, schließen
    POST /faelle/{id}/neu-pruefen   Prüfschema neu laden und denselben Fall erneut prüfen
    POST /faelle/{id}/referat       FWN flag → visible on the Radar
    GET  /radar                     the Referat view (14 §6 screen 2)
    GET  /vokabular                 every vocabulary as {code, label, tone}
    GET  /demo/faelle               the prepared fiction cases, payload-ready (Bühnenauftakt /neu)
    POST /demo/zuruecksetzen        Demo beenden: Radar neu aussäen, Schemadatei aus HEAD (33 §8 Nr. 8)

`GET /vokabular` exists so the UI never owns a code→string map: the same enum
module that drives the engine drives the labels on screen (06 ⑧).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from fallpruefer import ansicht, demo_reset
from fallpruefer.adapter.cache import CacheFehlt
from fallpruefer.brief import BriefFehler
from fallpruefer.dokumente import aus_freitext
from fallpruefer.fall import Dokument
from fallpruefer.pipeline import (
    abschluss as abschluss_setzen,
)
from fallpruefer.pipeline import (
    brief_status_setzen,
    dokument_nicht_vorhanden,
    fall_anlegen,
    fall_laden,
    fall_speichern,
    gate1_nachforderung,
    gate2_fallgruppe,
    gate3_bestaetigen,
    gate3_override,
    gate4_rechtsbehelf,
    leitfaden_antworten,
    nachforderung_status,
    nachreichung,
    neu_pruefen_nach_schema,
    referat_markieren,
    verarbeiten,
)
from fallpruefer.schema import schema_laden, taxonomie
from fallpruefer.viewmodel import FallakteAnsicht, VokabularAntwort
from fallpruefer.vokabular import Dokumenttyp, Quelle

app = FastAPI(
    title="VZ-I Fall-Prüfer",
    description="Interne Vorbereitung einer Fallakte. Läuft lokal; nichts verlässt die Maschine.",
    version="0.1.0",
)

# Lovable's dev server (8080), Vite's default (5173) and the hosted preview.
# The hosted preview cannot reach localhost anyway — it is fixture-only — but
# the origin is allowed so a mixed-content failure looks like what it is.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://[\w-]+\.lovable\.app$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnhangEingabe(BaseModel):
    """One attachment as markdown/plain text. PDFs are converted to page text
    locally before they get here — the bytes never travel."""

    dateiname: str = "anhang.md"
    text: str
    dokumenttyp: Dokumenttyp | None = None
    quelle: Quelle = Quelle.VERBRAUCHER


class Identitaetseingabe(BaseModel):
    name: str | None = None
    adresse: str | None = None
    email: str | None = None
    telefon: str | None = None
    kundennummer: str | None = None
    geburtsdatum: str | None = None


class FallEingabe(BaseModel):
    freitext: str = ""
    anhaenge: list[AnhangEingabe] = Field(default_factory=list)
    kanal: str = "vbs"
    ticket_nr: str | None = None
    thema: str | None = None
    anbieter: str | None = None
    gegner: str | None = None
    branche: str | None = None
    eingegangen_am: str | None = None
    identitaet: Identitaetseingabe = Field(default_factory=Identitaetseingabe)
    fallgruppe_id: str | None = None
    case_id: str | None = None


class FallAngelegt(BaseModel):
    case_id: str
    fallgruppe_id: str
    stufe: str
    einordnung: str | None = None
    hinweis: str | None = None


# Was die Beraterin liest, wenn das Werkzeug ein Dokument nicht kennt und
# gerade keine Verbindung zum Sprachmodell hat (Vorführmodus, 31 §2). Ehrlich
# über den Grund, ohne Technik — und mit der Zahl, die sonst jemand raten würde.
UNBEKANNTES_DOKUMENT = (
    "Dieses Dokument kennt das Werkzeug noch nicht. Es läuft gerade ohne Verbindung zum "
    "Sprachmodell und liest nur die vorbereiteten Unterlagen. Mit Verbindung dauert das "
    "Lesen eines Dokuments etwa 15 bis 20 Sekunden."
)

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _naechste_id() -> str:
    from fallpruefer.konfig import WURZEL

    vorhanden = sorted((WURZEL / "cases").glob("F-*.json"))
    nummern = [int(p.stem.rsplit("-", 1)[1]) for p in vorhanden if p.stem.rsplit("-", 1)[1].isdigit()]
    return f"F-2026-{max(nummern, default=0) + 1:04d}"


@app.post("/faelle", response_model=FallAngelegt)
def fall_anlegen_endpoint(eingabe: FallEingabe) -> FallAngelegt:
    case_id = eingabe.case_id or _naechste_id()
    if not _ID.match(case_id):
        raise HTTPException(400, "ungültige case_id")

    dokumente: list[Dokument] = []
    for i, anhang in enumerate(eingabe.anhaenge, start=1):
        d = aus_freitext(anhang.text, f"D{i}", anhang.dateiname)
        d.quelle = anhang.quelle
        if anhang.dokumenttyp:
            # the advisor said what it is — L1 does not need to guess
            d.dokumenttyp = anhang.dokumenttyp
            d.typ_bestaetigt = True
        dokumente.append(d)

    ticket: dict[str, Any] = {
        "kanal": eingabe.kanal, "ticket_nr": eingabe.ticket_nr, "thema": eingabe.thema,
        "freitext": eingabe.freitext, "anbieter": eingabe.anbieter, "gegner": eingabe.gegner,
        "branche": eingabe.branche, "eingegangen_am": eingabe.eingegangen_am,
        "identitaet": eingabe.identitaet.model_dump(),
    }

    fall = fall_anlegen(case_id, ticket, dokumente, eingabe.fallgruppe_id)
    try:
        fall = verarbeiten(fall)
    except CacheFehlt as e:
        # Vorführmodus ohne Schlüssel: ein unbekanntes Dokument ist ein
        # erwarteter Zustand, kein Absturz — und der Satz, den die Beraterin
        # sieht, darf keinen Dateipfad tragen. Der Pfad geht ins Log.
        logging.getLogger(__name__).warning("Cache-Miss: %s", e)
        raise HTTPException(409, UNBEKANNTES_DOKUMENT) from e
    except Exception as e:  # noqa: BLE001 — surface the real reason, do not hide it
        raise HTTPException(500, f"{type(e).__name__}: {e}") from e
    fall_speichern(fall)

    pruefung = fall.aktuelle_pruefung()
    schema = schema_laden(fall.schema_.fallgruppe_id)
    return FallAngelegt(
        case_id=fall.case_id,
        fallgruppe_id=fall.schema_.fallgruppe_id,
        stufe=schema.stufe.value,
        einordnung=pruefung.einordnung if pruefung else None,
        hinweis=None if pruefung else "Für diese Fallart sind keine Prüfpunkte hinterlegt.",
    )


class NachreichungEingabe(BaseModel):
    """Documents that arrive after the case was already assessed."""

    anhaenge: list[AnhangEingabe] = Field(default_factory=list)
    nachforderung_id: str | None = None


class NachreichungAngenommen(BaseModel):
    case_id: str
    run_id: str
    neue_dokumente: list[str]
    einordnung_vorher: str | None = None
    einordnung: str | None = None
    gerissene_stufe: str | None = None
    hauptvorschlag: str | None = None


@app.post("/faelle/{case_id}/dokumente", response_model=NachreichungAngenommen)
def dokumente_nachreichen(case_id: str, eingabe: NachreichungEingabe) -> NachreichungAngenommen:
    """The flip (14 §7). The same case runs again with more on file.

    The response deliberately carries the *previous* Einordnung as well: the
    point of a Nachreichung is not the new verdict on its own but that it can
    be held against the old one, and the UI should not have to keep that in
    local state to show it.
    """
    if not _ID.match(case_id):
        raise HTTPException(400, "ungültige case_id")
    fall = fall_laden(case_id)
    if fall is None:
        raise HTTPException(404, f"Fall {case_id} nicht gefunden")
    if not eingabe.anhaenge:
        raise HTTPException(400, "keine Dokumente übergeben")

    vorher = fall.aktuelle_pruefung()
    einordnung_vorher = vorher.einordnung if vorher else None
    vorhandene = len(fall.dokumente)

    dokumente: list[Dokument] = []
    for i, anhang in enumerate(eingabe.anhaenge, start=vorhandene + 1):
        d = aus_freitext(anhang.text, f"D{i}", anhang.dateiname)
        d.quelle = anhang.quelle
        if anhang.dokumenttyp:
            d.dokumenttyp = anhang.dokumenttyp
            d.typ_bestaetigt = True
        dokumente.append(d)

    try:
        fall = nachreichung(fall, dokumente, eingabe.nachforderung_id)
    except CacheFehlt as e:
        # Vorführmodus ohne Schlüssel: ein unbekanntes Dokument ist ein
        # erwarteter Zustand, kein Absturz — und der Satz, den die Beraterin
        # sieht, darf keinen Dateipfad tragen. Der Pfad geht ins Log.
        logging.getLogger(__name__).warning("Cache-Miss: %s", e)
        raise HTTPException(409, UNBEKANNTES_DOKUMENT) from e
    except Exception as e:  # noqa: BLE001 — surface the real reason, do not hide it
        raise HTTPException(500, f"{type(e).__name__}: {e}") from e
    fall_speichern(fall)

    pruefung = fall.aktuelle_pruefung()
    return NachreichungAngenommen(
        case_id=fall.case_id,
        run_id=pruefung.run_id if pruefung else "",
        neue_dokumente=[d.dok_id for d in dokumente],
        einordnung_vorher=einordnung_vorher,
        einordnung=pruefung.einordnung if pruefung else None,
        gerissene_stufe=pruefung.gerissene_stufe if pruefung else None,
        hauptvorschlag=fall.rechtsbehelf.hauptvorschlag,
    )


@app.get("/faelle/{case_id}", response_model=FallakteAnsicht)
def fallakte(case_id: str) -> FallakteAnsicht:
    if not _ID.match(case_id):
        raise HTTPException(400, "ungültige case_id")
    fall = fall_laden(case_id)
    if fall is None:
        raise HTTPException(404, f"Fall {case_id} nicht gefunden")
    # tolerant: mid-Jurist-Edit, a typo in the schema file must not take the
    # Fallakte view down — the last good version keeps serving (18 #40)
    from fallpruefer.schema import schema_laden_oder_letzte

    schema = schema_laden_oder_letzte(fall.schema_.fallgruppe_id)
    try:
        return ansicht.bauen(fall, schema)
    except (ValueError, BriefFehler) as e:
        raise HTTPException(409, str(e)) from e


class FallgruppeEingabe(BaseModel):
    fallgruppe_id: str
    von: str = "Beraterin"


class NachforderungEingabe(BaseModel):
    """Either produce a Nachforderung (no `nachforderung_id`) or set the status
    of one that exists. The tool never sends it either way (14 §8)."""

    dokumenttypen: list[str] | None = None
    kanal: str | None = None
    nachforderung_id: str | None = None
    status: str | None = None
    von: str = "Beraterin"


class NichtVorhandenEingabe(BaseModel):
    dokumenttyp: str
    aussage: str = ""
    zurueckziehen: bool = False
    von: str = "Beraterin"


class OverrideEingabe(BaseModel):
    pruefpunkt_id: str
    neuer_zustand: str | None = None
    grund: str = ""
    zurueckziehen: bool = False
    von: str = "Beraterin"


class RechtsbehelfEingabe(BaseModel):
    rechtsbehelf_id: str
    brief_status: str | None = None
    von: str = "Beraterin"


class LeitfadenEingabe(BaseModel):
    """`antworten` maps a Leitfaden `fuellt` field to the advisor's answer.
    Anything else is refused by `leitfaden._ziele` — this endpoint must not
    become a way to write arbitrary facts into a legal assessment."""

    antworten: dict[str, Any] = Field(default_factory=dict)
    von: str = "Beraterin"


class AbschlussEingabe(BaseModel):
    basis_export: bool = False
    wiedervorlagen: list[str] | None = None
    schliessen: bool = False
    von: str = "Beraterin"


class Gate3Eingabe(BaseModel):
    von: str = "Beraterin"


class ReferatEingabe(BaseModel):
    kriterien: list[str] = Field(default_factory=list)
    notiz: str = ""
    von: str = "Beraterin"


def _fall_oder_404(case_id: str):
    if not _ID.match(case_id):
        raise HTTPException(400, "ungültige case_id")
    fall = fall_laden(case_id)
    if fall is None:
        raise HTTPException(404, f"Fall {case_id} nicht gefunden")
    return fall


def _zustand(fall) -> dict:
    """What every gate answers with: where the case stands now."""
    pruefung = fall.aktuelle_pruefung()
    return {
        "case_id": fall.case_id,
        "run_id": pruefung.run_id if pruefung else None,
        "einordnung": pruefung.einordnung if pruefung else None,
        "gerissene_stufe": pruefung.gerissene_stufe if pruefung else None,
        "hauptvorschlag": fall.rechtsbehelf.hauptvorschlag,
        "gewaehlt": fall.rechtsbehelf.gewaehlt,
        "status": fall.status.value,
    }


@app.post("/faelle/{case_id}/fallgruppe")
def fallgruppe_waehlen(case_id: str, eingabe: FallgruppeEingabe) -> dict:
    """Gate 2. Confirming the proposal and changing it are the same call —
    changing it re-runs the Soll and the Prüfung (14 §4 step 5)."""
    fall = _fall_oder_404(case_id)
    try:
        gate2_fallgruppe(fall, eingabe.fallgruppe_id, eingabe.von)
    except (ValueError, Exception) as e:
        raise HTTPException(400, f"{type(e).__name__}: {e}") from e
    fall_speichern(fall)
    return {**_zustand(fall), "fallgruppe_id": fall.schema_.fallgruppe_id,
            "bestaetigt": fall.fallgruppe.bestaetigt}


@app.post("/faelle/{case_id}/nachforderung")
def nachforderung(case_id: str, eingabe: NachforderungEingabe) -> dict:
    """Gate 1. Without `nachforderung_id` it produces the text; with one it
    records the advisor's „als angefordert markiert"."""
    fall = _fall_oder_404(case_id)
    try:
        if eingabe.nachforderung_id:
            if not eingabe.status:
                raise ValueError("status fehlt.")
            n = nachforderung_status(fall, eingabe.nachforderung_id, eingabe.status, eingabe.von)
        else:
            n = gate1_nachforderung(fall, eingabe.dokumenttypen, eingabe.kanal, eingabe.von)
    except (ValueError, BriefFehler) as e:
        raise HTTPException(409 if isinstance(e, BriefFehler) else 400, str(e)) from e
    fall_speichern(fall)
    return {"case_id": fall.case_id, "id": n.id, "kanal": n.kanal.value,
            "dokumente": [d.value for d in n.dokumente],
            "status": n.status.value, "text": n.text}


@app.post("/faelle/{case_id}/nicht-vorhanden")
def nicht_vorhanden(case_id: str, eingabe: NichtVorhandenEingabe) -> dict:
    """V-N2 — die Beraterin stellt fest, dass es eine Unterlage nie gegeben hat.

    Danach fordert Gate 1 sie nicht mehr bei der Verbraucherin an; das Fehlen
    steht auf der Unternehmensseite. Die `aussage` ist Pflicht: ohne den Satz,
    auf den sich die Feststellung stützt, wäre sie von einer Vermutung nicht zu
    unterscheiden.
    """
    fall = _fall_oder_404(case_id)
    try:
        dokument_nicht_vorhanden(fall, eingabe.dokumenttyp, eingabe.aussage,
                                 eingabe.von, eingabe.zurueckziehen)
    except (ValueError, BriefFehler) as e:
        raise HTTPException(409 if isinstance(e, BriefFehler) else 400, str(e)) from e
    fall_speichern(fall)
    pruefung = fall.aktuelle_pruefung()
    offen = pruefung.vollstaendigkeit if pruefung else {}
    return {
        **_zustand(fall),
        "dokumenttyp": eingabe.dokumenttyp,
        "nicht_vorhanden": [
            n.dokumenttyp.value for n in fall.nicht_vorhanden if not n.zurueckgezogen
        ],
        # das Gegenstück zum Zweck des Endpunkts: was Gate 1 jetzt noch fragt
        "offen_verbraucher": [
            e.dokumenttyp.value for e in offen.get("verbraucher", []) if e.dokumenttyp
        ],
    }


@app.post("/faelle/{case_id}/override")
def override(case_id: str, eingabe: OverrideEingabe) -> dict:
    """Gate 3 — „Prüfpunkt überschreiben mit Grund". The reason is required."""
    fall = _fall_oder_404(case_id)
    try:
        gate3_override(fall, eingabe.pruefpunkt_id, eingabe.neuer_zustand,
                       eingabe.grund, eingabe.von, eingabe.zurueckziehen)
    except (ValueError, BriefFehler) as e:
        raise HTTPException(409 if isinstance(e, BriefFehler) else 400, str(e)) from e
    fall_speichern(fall)
    pruefung = fall.aktuelle_pruefung()
    erg = pruefung.ergebnis(eingabe.pruefpunkt_id) if pruefung else None
    return {**_zustand(fall), "pruefpunkt_id": eingabe.pruefpunkt_id,
            "zustand": erg.zustand.value if erg else None}


@app.post("/faelle/{case_id}/rechtsbehelf")
def rechtsbehelf_waehlen(case_id: str, eingabe: RechtsbehelfEingabe) -> dict:
    """Gate 4 — pick one of the offered remedies; the letter is re-filled."""
    fall = _fall_oder_404(case_id)
    try:
        gate4_rechtsbehelf(fall, eingabe.rechtsbehelf_id, eingabe.von)
        if eingabe.brief_status:
            brief_status_setzen(fall, eingabe.brief_status)
    except (ValueError, BriefFehler) as e:
        raise HTTPException(409 if isinstance(e, BriefFehler) else 400, str(e)) from e
    fall_speichern(fall)
    brief = fall.rechtsbehelf.brief
    return {**_zustand(fall),
            "brief": {"template_id": brief.template_id, "titel": brief.titel,
                      "variante": brief.variante, "status": brief.status.value,
                      "geprueft": brief.geprueft, "text": brief.text} if brief else None}


@app.post("/faelle/{case_id}/abschluss")
def abschluss(case_id: str, eingabe: AbschlussEingabe) -> dict:
    """Step 10 — Basis-Eintrag erzeugen, Wiedervorlagen, schließen."""
    fall = _fall_oder_404(case_id)
    try:
        abschluss_setzen(fall, eingabe.basis_export, eingabe.wiedervorlagen,
                         eingabe.schliessen, eingabe.von)
    except (ValueError, BriefFehler) as e:
        raise HTTPException(409 if isinstance(e, BriefFehler) else 400, str(e)) from e
    fall_speichern(fall)
    return {**_zustand(fall), "basis_text": fall.abschluss.basis_text,
            "wiedervorlagen": fall.abschluss.wiedervorlagen,
            "geschlossen": fall.abschluss.geschlossen}


@app.post("/faelle/{case_id}/neu-pruefen")
def neu_pruefen(case_id: str) -> dict:
    """Akt 2 (14 §7) — the Prüfschema was edited in a text editor; the same
    case runs again against it. No restart, no deploy, no code."""
    fall = _fall_oder_404(case_id)
    vorher = fall.aktuelle_pruefung()
    davor = vorher.einordnung if vorher else None
    version_davor = fall.schema_.version
    try:
        neu_pruefen_nach_schema(fall)
    except Exception as e:  # noqa: BLE001 — a broken edit must say what broke
        raise HTTPException(409, f"{type(e).__name__}: {e}") from e
    fall_speichern(fall)
    return {**_zustand(fall), "einordnung_vorher": davor,
            "schema_version_vorher": version_davor,
            "schema_version": fall.schema_.version,
            "schema_stand": fall.schema_.stand}


@app.post("/faelle/{case_id}/gate3")
def gate3(case_id: str, eingabe: Gate3Eingabe) -> dict:
    """Gate 3 — the advisor confirms the Einordnung, and the case counts."""
    fall = _fall_oder_404(case_id)
    try:
        satz = gate3_bestaetigen(fall, eingabe.von)
    except (ValueError, BriefFehler) as e:
        raise HTTPException(409, str(e)) from e
    fall_speichern(fall)
    return {"case_id": fall.case_id, "gespeichert": True, "fall_hash": satz["fall_hash"]}


@app.post("/faelle/{case_id}/leitfaden")
def leitfaden(case_id: str, eingabe: LeitfadenEingabe) -> dict:
    """Rung 6 — the Gesprächsleitfaden answers. Appends a run, so the verdict
    before and after the conversation stay side by side."""
    from fallpruefer.leitfaden import LeitfadenFehler

    fall = _fall_oder_404(case_id)
    if not eingabe.antworten:
        raise HTTPException(400, "keine Antworten übergeben")
    try:
        ergebnis = leitfaden_antworten(fall, eingabe.antworten, eingabe.von)
    except LeitfadenFehler as e:
        raise HTTPException(400, str(e)) from e
    except (ValueError, BriefFehler) as e:
        raise HTTPException(409, str(e)) from e
    fall_speichern(fall)
    return {"case_id": fall.case_id, **ergebnis}


@app.post("/faelle/{case_id}/referat")
def referat(case_id: str, eingabe: ReferatEingabe) -> dict:
    """Step 9 — the FWN flag. Nothing is ticked automatically (14 §4)."""
    fall = _fall_oder_404(case_id)
    try:
        satz = referat_markieren(fall, eingabe.kriterien, eingabe.notiz, eingabe.von)
    except (ValueError, BriefFehler) as e:
        raise HTTPException(409 if isinstance(e, BriefFehler) else 400, str(e)) from e
    fall_speichern(fall)
    return {"case_id": fall.case_id, "kriterien": satz["referat_flag"],
            "fall_hash": satz["fall_hash"]}


@app.get("/radar")
def radar() -> dict:
    """Screen 2 (14 §6): clusters, thresholds, flagged cases.

    Reads only `store/faelle.jsonl`. It has no access to a case object and
    therefore no way to show a name even if someone asked it to.
    """
    from fallpruefer import store

    return store.radar()


@app.get("/vokabular", response_model=VokabularAntwort)
def vokabular() -> VokabularAntwort:
    return VokabularAntwort.bauen()


@app.get("/fallgruppen")
def fallgruppen() -> dict[str, dict]:
    """The taxonomy, derived from the schema files at load (contract §0)."""
    return taxonomie()


@app.get("/schema/{fallgruppe_id}")
def schema_stand(fallgruppe_id: str) -> dict:
    """Has the Prüfschema file moved since we last read it? The Act-2 button
    („neu prüfen") is only worth showing when it has."""
    from fallpruefer.schema import SchemaFehler, schema_geaendert

    geaendert = schema_geaendert(fallgruppe_id)
    fehler: str | None = None
    try:
        s = schema_laden(fallgruppe_id)
    except SchemaFehler as e:
        # a broken file is an answer, not an outage: the UI shows the error
        # next to the „neu prüfen" button instead of losing the whole panel
        if e.letzte_fassung is None:
            raise HTTPException(409, str(e)) from e
        s, fehler = e.letzte_fassung, str(e)
    return {"fallgruppe_id": s.fallgruppe_id, "name": s.name, "stufe": s.stufe.value,
            "version": s.version, "stand": s.stand, "geaendert": geaendert,
            "fehler": fehler,
            "jurist_edit_knoepfe": s.jurist_edit_knoepfe}


# --- Bühnenauftakt: die vorbereiteten Fälle ---------------------------------

# Bühnenreihenfolge: „Fall 01" ist der Fall, der auf der Bühne läuft (33 §2).
# Was hier nicht steht, folgt alphabetisch dahinter.
DEMO_REIHENFOLGE = ("drehkreuz", "seepark_seite_fehlt", "nordlicht_agb_fehlen",
                    "sauber_aktivpark", "stoerfall_kraftwerk")


class DemoAnhang(BaseModel):
    dateiname: str
    text: str


class DemoFall(BaseModel):
    """One prepared case from `demo/faelle/`, shaped like `POST /faelle` wants it."""

    fall: str
    nr: int
    ticket_nr: str | None = None
    anbieter: str | None = None
    branche: str | None = None
    thema: str | None = None
    kanal: str = "vbs"
    eingegangen_am: str | None = None
    freitext: str = ""
    identitaet: dict[str, str | None] = Field(default_factory=dict)
    anhaenge: list[DemoAnhang] = Field(default_factory=list)
    vorbereitet: bool
    hinweis: str | None = None


@app.get("/demo/faelle", response_model=list[DemoFall])
def demo_faelle_auflisten() -> list[DemoFall]:
    """The prepared fiction cases, payload-ready for `POST /faelle`.

    The UI's /neu screen lists them instead of opening a file picker — on
    stage nobody browses a Desktop folder. `anhaenge` are exactly the files
    the ticket names; a Nachreichung file (seepark's page 2) is not in that
    list and so stays out, which is what makes the flip possible later.
    `vorbereitet` means a golden exists for the case: the suite replays it
    cache-only, so a green suite proves the case runs without a key. The two
    Franz cases have no cache yet and would answer 409 (`UNBEKANNTES_DOKUMENT`).
    """
    from fallpruefer.konfig import WURZEL

    verz = WURZEL / "demo" / "faelle"
    namen = [p.name for p in verz.iterdir() if (p / "ticket.json").is_file()]
    rest = sorted(n for n in namen if n not in DEMO_REIHENFOLGE)
    geordnet = [n for n in DEMO_REIHENFOLGE if n in namen] + rest
    faelle: list[DemoFall] = []
    for nr, name in enumerate(geordnet, start=1):
        ticket = json.loads((verz / name / "ticket.json").read_text(encoding="utf-8"))
        faelle.append(DemoFall(
            fall=name, nr=nr,
            ticket_nr=ticket.get("ticket_nr"), anbieter=ticket.get("anbieter"),
            branche=ticket.get("branche"), thema=ticket.get("thema"),
            kanal=ticket.get("kanal", "vbs"), eingegangen_am=ticket.get("eingegangen_am"),
            freitext=ticket.get("freitext", ""), identitaet=ticket.get("identitaet", {}),
            anhaenge=[DemoAnhang(dateiname=n, text=(verz / name / n).read_text(encoding="utf-8"))
                      for n in ticket.get("anhaenge", [])],
            vorbereitet=(WURZEL / "tests" / "golden" / f"{name}.json").is_file(),
            hinweis=ticket.get("hinweis"),
        ))
    return faelle


class DemoZurueckgesetzt(BaseModel):
    radar_zeilen: int
    fitpoint_24: int
    schema_zurueckgesetzt: bool
    hinweis: str


@app.post("/demo/zuruecksetzen", response_model=DemoZurueckgesetzt)
def demo_zuruecksetzen() -> DemoZurueckgesetzt:
    """Demo beenden — 33 §8 Nr. 8 als Knopf statt als Merksatz.

    Der Store vergisst nicht: eine Probe mit Gate 3 hebt FitPoint 24 auf 3 und
    verbrennt den Radar-Beat. Hier: Radar neu aussäen (FitPoint zurück auf 2)
    und die Schemadatei des Bühnen-Edits aus HEAD zurückholen. Fallakten
    bleiben — sie stören nichts. Die Antwort trägt die Prüfzahl, die sonst
    jemand vor dem Auftritt per Einzeiler nachzählt.
    """
    zeilen, fitpoint = demo_reset.radar_neu_saeen()
    schema = demo_reset.schema_wiederherstellen()
    hinweis = (f"Radar neu ausgesät: {zeilen} Zeilen, FitPoint 24 = {fitpoint}. "
               + ("Schemadatei aus HEAD zurückgeholt." if schema else "Schemadatei war unverändert."))
    return DemoZurueckgesetzt(radar_zeilen=zeilen, fitpoint_24=fitpoint,
                              schema_zurueckgesetzt=schema, hinweis=hinweis)
