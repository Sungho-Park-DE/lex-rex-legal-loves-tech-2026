"""Intake → L0 → L1 → L2 → Fallakte. The tracer bullet of 14 §10 rung 1.

The order here is the architecture:

    L0 runs before the first adapter call, always. Not "usually", not "when the
    ticket has an identity block" — the LLM never sees a name because the code
    path in which it could does not exist.

    L1 (the adapter) proposes: document type, fields with quotes, Fallgruppe.
    Every proposal passes a validator before it becomes a fact.

    L2 (the evaluator) decides. Einordnung, remedy, deadlines and letters are
    computed from the schema file, and no adapter output reaches them except as
    a validated fact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fallpruefer import brief as brief_modul
from fallpruefer import rechtsbehelf as rb_modul
from fallpruefer import zeit
from fallpruefer.adapter import LLMAdapter, adapter_holen, validiere_extraktion, validiere_klassifikation, validiere_vorschlaege
from fallpruefer.evaluator import Fallkontext, pruefen
from fallpruefer.fall import (
    Brief,
    Dokument,
    Eingang,
    Fall,
    Fallgruppenwahl,
    FallgruppenVorschlag,
    Identitaet,
    LLMRun,
    Nachforderung,
    NichtVorhanden,
    Override,
    Rechtsbehelfwahl,
    SchemaRef,
)
from fallpruefer.konfig import WURZEL, konfig
from fallpruefer.l0 import Pseudonymisierer, sensible_inhalte
from fallpruefer.schema import Schema, schema_laden, taxonomie
from fallpruefer.vokabular import (
    Briefstatus,
    Dokumenttyp,
    Fallstatus,
    Kanal,
    Nachforderungsstatus,
    Stufe,
    Zustand,
)

STANDARD_FALLGRUPPE = "preiserhoehung"

# The ticket free text is not an attachment — it is never classified and never
# field-extracted — but the advisor must be able to click a Fallgruppen quote
# and see where it stands. It enters the view model as a pseudo-document.
TICKET_DOK_ID = "T0"


# --------------------------------------------------------------------------
# L0
# --------------------------------------------------------------------------


def pseudonymisieren(fall: Fall) -> Pseudonymisierer:
    k = konfig().pseudonymisierung
    whitelist = tuple(w for w in (fall.eingang.anbieter, fall.eingang.gegner) if w)
    p = Pseudonymisierer(whitelist=whitelist)
    p.aus_identitaet(fall.eingang.identitaet)
    p.aus_text(fall.eingang.freitext_original)
    for d in fall.dokumente:
        for s in d.seiten:
            p.aus_text(s.text_original)

    fall.eingang.freitext_pseudonym = p.anwenden(fall.eingang.freitext_original)
    for d in fall.dokumente:
        for s in d.seiten:
            s.text_pseudonym = p.anwenden(s.text_original)

    fall.pseudonyme = dict(p.karte)
    fall.eingang.sensible_inhalte_flag = sensible_inhalte(
        fall.eingang.freitext_original, k.sensible_keywords
    )
    fall.protokoll("l0_pseudonymisiert", tokens=len(p.karte))
    return p


# --------------------------------------------------------------------------
# L1
# --------------------------------------------------------------------------


def _run_protokollieren(fall: Fall, aufgabe: str, aufruf, dok_id: str | None) -> str:
    run_id = f"R{len(fall.llm_runs) + 1}"
    fall.llm_runs.append(LLMRun(
        id=run_id, aufgabe=aufgabe, modell=aufruf.modell,
        prompt_version=aufruf.prompt_version, dok_id=dok_id,
        aus_cache=aufruf.aus_cache, dauer_ms=aufruf.dauer_ms,
        kosten_cent=aufruf.kosten_cent, zeit=zeit.jetzt(),
    ))
    return run_id


def klassifizieren(fall: Fall, adapter: LLMAdapter) -> None:
    for d in fall.dokumente:
        if d.typ_bestaetigt:
            continue
        klass, aufruf = adapter.classify_doc(d.seiten)
        run_id = _run_protokollieren(fall, "classify_doc", aufruf, d.dok_id)
        typ, muss_bestaetigt_werden = validiere_klassifikation(klass)
        d.dokumenttyp = typ
        d.typ_konfidenz = klass.konfidenz
        d.typ_bestaetigt = not muss_bestaetigt_werden
        fall.protokoll("dokument_klassifiziert", dok_id=d.dok_id, typ=typ.value, run=run_id)


def extrahieren(
    fall: Fall, schema: Schema, adapter: LLMAdapter, nur: list[str] | None = None
) -> list[str]:
    """`nur` restricts extraction to those dok_ids — a Nachreichung re-reads the
    new documents, not the ones already on file. Re-reading them would be
    harmless for the result (facts are keyed by `(feld_id, dok_id)`) but it
    would double the recorded llm_runs and therefore the cost the footer shows."""
    verworfen_gesamt: list[str] = []
    for d in fall.dokumente:
        if nur is not None and d.dok_id not in nur:
            continue
        sd = schema.dokumenten_soll.nach_typ(d.dokumenttyp)
        if not sd or not sd.felder:
            continue
        extraktion, aufruf = adapter.extract_fields(d.seiten, sd.felder, d.dokumenttyp.value)
        run_id = _run_protokollieren(fall, "extract_fields", aufruf, d.dok_id)
        fakten, verworfen = validiere_extraktion(extraktion, sd.felder, d.seiten, d.dok_id, run_id)
        fall.fakten.extend(fakten)
        verworfen_gesamt.extend(f"{d.dok_id}:{v}" for v in verworfen)
    return verworfen_gesamt


def fallgruppe_vorschlagen(fall: Fall, adapter: LLMAdapter) -> None:
    tax = taxonomie()
    doktypen = [d.dokumenttyp.value for d in fall.dokumente]
    vorschlaege, aufruf = adapter.propose_fallgruppe(
        fall.eingang.freitext_pseudonym, doktypen, tax
    )
    _run_protokollieren(fall, "propose_fallgruppe", aufruf, None)
    gueltig = validiere_vorschlaege(vorschlaege, tax, fall.eingang.freitext_pseudonym)
    from fallpruefer.fall import Quellenangabe

    # The free text is where these quotes live, so they point at the ticket
    # pseudo-document the Fallakte view renders alongside the attachments.
    fall.fallgruppe.vorschlaege = [
        FallgruppenVorschlag(
            id=t.fallgruppe_id, begruendung=t.begruendung,
            zitate=[Quellenangabe(dok_id=TICKET_DOK_ID, seite=1, zitat_pseudonym=z)
                    for z in t.zitate],
        )
        for t in gueltig
    ]
    if gueltig and not fall.fallgruppe.gewaehlt:
        fall.fallgruppe.gewaehlt = gueltig[0].fallgruppe_id
        fall.fallgruppe.stufe = Stufe(tax[gueltig[0].fallgruppe_id]["stufe"])


# --------------------------------------------------------------------------
# L2 + letter
# --------------------------------------------------------------------------


def _ergebnis_kontext(fall: Fall, schema: Schema, pruefung) -> Fallkontext:
    """Der Kontext, den alles sieht, was **nach** der Prüfung entscheidet:
    Rechtsbehelfe, Briefvarianten und die Beratungshinweise.

    Bewusst eine Funktion und nicht zweimal derselbe Block: der Sinn der
    Hinweise ist, dass sie gegen genau dieselben Größen bedingen wie die
    Rechtsbehelfe. Zwei Kopien wären zwei Kontexte, die auseinanderlaufen —
    und der Unterschied fiele erst auf, wenn eine Bedingung an der einen
    Stelle greift und an der anderen nicht.
    """
    from fallpruefer.vokabular import label

    k = Fallkontext(fall=fall, schema=schema)
    k.extra.update({
        "einordnung": label(pruefung.einordnung_code) if pruefung.einordnung_code else None,
        "gerissene_stufe": pruefung.gerissene_stufe,
        "fehlt_unternehmen": [
            f.dokumenttyp.value if f.dokumenttyp else f.feld_id
            for f in pruefung.vollstaendigkeit.get("unternehmen", [])
        ],
        # seit V-39 liest `nachforderung` das hier — der frühere Hinweis
        # „no rule reads it yet" stimmt nicht mehr
        "fehlt_verbraucher": [
            f.dokumenttyp.value if f.dokumenttyp else f.feld_id
            for f in pruefung.vollstaendigkeit.get("verbraucher", [])
        ],
        **{
            f"pruefpunkt.{e.pruefpunkt_id}.zustand": e.zustand.value
            for e in pruefung.ergebnisse
        },
        "berechnung.rueckforderung": brief_modul._rueckforderung(pruefung),
    })
    return k


def beratungshinweise(fall: Fall, schema: Schema, pruefung) -> None:
    """Welche Beratungshinweise dieser Fall auslöst (T-H1/T-H6).

    Läuft **unabhängig von der Einordnung**, anders als die Rechtsbehelfe: ein
    Hinweis wie „die Lastschrift nicht zurückgeben" hängt nicht daran, ob die
    Erhöhung am Ende hält — er hängt daran, dass bereits abgebucht wird. Genau
    deshalb ist er kein Prüfpunkt.

    Auf der Prüfung landen nur die IDs; die Texte holt die Projektion aus dem
    Schema. Dieselbe Trennung wie bei `pruefumfang`, und aus demselben Grund:
    eine ältere Prüfung soll den Text zeigen, der heute in der Datei steht,
    nicht eine eingefrorene Kopie.
    """
    from fallpruefer.regeln import auswerten as bedingung_auswerten

    if not schema.beratungshinweise:
        pruefung.beratungshinweise = []
        return

    k = _ergebnis_kontext(fall, schema, pruefung)
    pruefung.beratungshinweise = [
        h.id for h in schema.beratungshinweise
        if h.wenn is None or bedingung_auswerten(h.wenn, k) is True
    ]


def rechtsbehelf_und_brief(fall: Fall, schema: Schema, pruefung) -> None:
    if pruefung.einordnung_code is None:
        # No verdict — a stopped schema or a Stufe-B/C Fallgruppe. Returning
        # early used to leave the *previous* Fallgruppe's remedy and filled
        # Musterbrief on screen, so „Fallart im Programm nicht hinterlegt" was
        # displayed next to a red verdict and a Widerspruch letter from a
        # Prüfung that no longer applies.
        if fall.rechtsbehelf.vorschlaege or fall.rechtsbehelf.brief:
            fall.protokoll("rechtsbehelf_entfaellt",
                           grund=pruefung.schema_stopp_text or "keine Prüfpunkte hinterlegt")
        fall.rechtsbehelf = Rechtsbehelfwahl()
        return
    k = _ergebnis_kontext(fall, schema, pruefung)
    from fallpruefer.vokabular import label

    vorschlaege = rb_modul.waehlen(schema, label(pruefung.einordnung_code), k)
    if not vorschlaege:
        return

    ids = [v.rechtsbehelf_id for v in vorschlaege]
    # A Gate-4 choice survives a re-run only while it is still on offer. After
    # a Nachreichung flips „unklar" to „wahrscheinlich unwirksam", the advisor's
    # earlier „Unterlagen nachfordern" is no longer one of the proposals, and
    # keeping it would leave the case showing a Nachforderung next to a verdict
    # that no longer asks for one (contract §4 re-run semantics).
    #
    # `gate4_von` is what makes it a *choice*: this function writes `gewaehlt`
    # itself on every run (below, as `bisher or haupt`), so reading `gewaehlt`
    # back would treat the program's own first proposal as a decision a person
    # made — and the next run then honours it strictly, letter error included.
    # Only `gate4_rechtsbehelf` sets `gate4_von`, so only that is a human.
    gate4_von = fall.rechtsbehelf.gate4_von
    bisher = (
        fall.rechtsbehelf.gewaehlt
        if gate4_von and fall.rechtsbehelf.gewaehlt in ids
        else None
    )

    # The advisor's own choice is honoured even if it cannot be filled — they
    # get the render error, not a silently different letter. Without a choice,
    # the Hauptvorschlag is the first proposal that actually produces one: a
    # remedy whose letter has a hole in it does not satisfy „ein Paar in jedem
    # Zweig" (14 §5). This is where „unklar" splits — a case that is unclear
    # because a *document* is missing gets the Nachforderung, one that is
    # unclear because a *judgement* is missing does not (18 #39).
    reihenfolge = ([v for v in vorschlaege if v.rechtsbehelf_id == bisher]
                   if bisher else list(vorschlaege))

    brief = None
    genommen = None
    for v in reihenfolge:
        template = rb_modul.template_id(v, fall.eingang.kanal.value)
        if not template:
            continue
        try:
            vorlage = brief_modul.vorlage_laden(template)
            werte = brief_modul.platzhalter_werte(fall, pruefung, k, vorlage)
            varianten = brief_modul.varianten_waehlen(vorlage, k)
            text = brief_modul.rendern(
                vorlage, werte, varianten,
                lint_nachforderung=template.startswith("nachforderung_"),
            )
        except brief_modul.BriefFehler as e:
            fall.protokoll("brief_nicht_erzeugt", rechtsbehelf_id=v.rechtsbehelf_id,
                           template=template, grund=str(e))
            if bisher:
                raise
            continue
        brief = Brief(
            template_id=vorlage.id, titel=vorlage.titel, text=text,
            variante="+".join(varianten) or None,
            quelle=vorlage.quelle.value, quelle_url=vorlage.kopf.get("quelle_url"),
            platzhalter={ph: w for ph, w in werte.items() if ph in vorlage.koerper},
            empfaenger=vorlage.empfaenger, geprueft=vorlage.geprueft,
        )
        genommen = v
        break

    haupt = genommen or vorschlaege[0]
    # `gate4_von` has to be carried over here, not just set in `gate4_rechtsbehelf`:
    # that function sets it and then calls this one, which used to replace the
    # whole `Rechtsbehelfwahl` — so the attribution was erased one line after it
    # was written and was `None` in every running case. It survives exactly as
    # long as the choice does: a remedy that is no longer proposed takes its
    # „wer hat das gewählt" with it.
    fall.rechtsbehelf = Rechtsbehelfwahl(
        hauptvorschlag=haupt.rechtsbehelf_id,
        vorschlaege=ids,
        gewaehlt=bisher or haupt.rechtsbehelf_id,
        gate4_von=gate4_von if bisher else None,
        brief=brief,
    )
    if brief is not None:
        fall.protokoll("brief_erzeugt", template=brief.template_id,
                       varianten=(brief.variante or "").split("+") if brief.variante else [])


# --------------------------------------------------------------------------
# the whole run
# --------------------------------------------------------------------------


def fall_anlegen(
    case_id: str,
    ticket: dict[str, Any],
    dokumente: list[Dokument],
    fallgruppe_id: str | None = None,
) -> Fall:
    ident = Identitaet.model_validate(ticket.get("identitaet") or {})
    eingang = Eingang(
        kanal=Kanal(ticket.get("kanal", "vbs")),
        ticket_nr=ticket.get("ticket_nr"),
        thema=ticket.get("thema"),
        freitext_original=ticket.get("freitext", ""),
        anbieter=ticket.get("anbieter"),
        anbieter_quelle="beraterin" if ticket.get("anbieter") else None,
        gegner=ticket.get("gegner"),
        branche=ticket.get("branche"),
        eingegangen_am=ticket.get("eingegangen_am"),
        identitaet=ident,
    )
    fall = Fall(
        case_id=case_id,
        schema=SchemaRef(fallgruppe_id=fallgruppe_id or STANDARD_FALLGRUPPE),
        # an explicit Fallgruppe is the caller's hint, not a Gate-2
        # confirmation — but it has to win over the model's proposal, which it
        # did not: only `SchemaRef` was set, `fallgruppe.gewaehlt` stayed empty,
        # so `fallgruppe_vorschlagen` overwrote it on every intake
        fallgruppe=Fallgruppenwahl(gewaehlt=fallgruppe_id) if fallgruppe_id else Fallgruppenwahl(),
        stichtag=zeit.heute().isoformat(),
        eingang=eingang,
        dokumente=dokumente,
    )
    for i, d in enumerate(fall.dokumente, start=1):
        if not d.dok_id or not d.dok_id.startswith("D"):
            d.dok_id = f"D{i}"
    return fall


def verarbeiten(
    fall: Fall, adapter: LLMAdapter | None = None, trigger: str = "initial"
) -> Fall:
    adapter = adapter or adapter_holen()

    pseudonymisieren(fall)
    klassifizieren(fall, adapter)

    if not fall.fallgruppe.gewaehlt:
        try:
            fallgruppe_vorschlagen(fall, adapter)
        except Exception as e:  # noqa: BLE001 — a missing proposal must not stop intake
            # …but it must not pass for a proposal either. Swallowed silently,
            # the case fell through to STANDARD_FALLGRUPPE and an Inkasso
            # complaint came back as a Preiserhöhung assessment complete with
            # „das Erhöhungsschreiben fehlt" — a confident answer to a question
            # nobody asked, which is the exact failure this design argues
            # against. Gate 2 is where it gets corrected, so the advisor has to
            # be able to see that nothing was proposed.
            fall.protokoll("fallgruppe_vorschlag_fehlgeschlagen",
                           grund=f"{type(e).__name__}: {e}")
    fallgruppe_id = fall.fallgruppe.gewaehlt or fall.schema_.fallgruppe_id
    fall.fallgruppe.vorschlag_fehlt = not fall.fallgruppe.vorschlaege
    fall.fallgruppe.gewaehlt = fallgruppe_id

    schema = schema_laden(fallgruppe_id)
    fall.schema_ = SchemaRef(
        fallgruppe_id=fallgruppe_id, version=schema.version, stand=schema.stand
    )
    fall.fallgruppe.stufe = schema.stufe

    _verworfen_protokollieren(fall, extrahieren(fall, schema, adapter))

    neu_pruefen(fall, schema, trigger=trigger)
    return fall


def neu_pruefen(
    fall: Fall, schema: Schema, trigger: str = "initial",
    ausgeloest_durch: str | None = None,
):
    """Append a run (contract §4). Every trigger appends rather than mutates:
    the previous verdict stays on file, which is what makes the flip showable
    side by side instead of as a value that quietly changed.

    A new run also invalidates the previous Gate-3 confirmation. What the
    advisor confirmed was a verdict computed from fewer documents; leaving the
    tick in place would turn an audit trail into a claim nobody made.
    """
    from fallpruefer.soll import auswerten as soll_auswerten

    pruefung = pruefen(fall, schema, trigger=trigger)
    pruefung.ausgeloest_durch = ausgeloest_durch
    # `_schema_von` re-reads the file on every gate action, so a run can be
    # decided by a newer version than the one stamped on the case. The store
    # row and the Basis-Eintrag both read `fall.schema_`, and both leave the
    # tool — they must name the version that actually produced the verdict.
    fall.schema_ = SchemaRef(
        fallgruppe_id=schema.fallgruppe_id, version=schema.version, stand=schema.stand
    )
    for p in fall.pruefungen:
        if p.aktuell and p.gate3:
            p.gate3 = {**p.gate3, "gueltig": False, "ungueltig_durch": pruefung.run_id}
            fall.protokoll("gate3_ungueltig", run_id=p.run_id, durch=pruefung.run_id)
        p.aktuell = False
    fall.pruefungen.append(pruefung)
    fall.protokoll("pruefung_gelaufen", run_id=pruefung.run_id, trigger=trigger)
    if pruefung.schema_stopp_text:
        # contract §2/§12: a gate that stops the schema is an event. Without it
        # the one outcome that ends the assessment leaves no line in the audit
        # trail the RDG framing rests on.
        fall.protokoll("schema_stopp", run_id=pruefung.run_id,
                       text=pruefung.schema_stopp_text)

    k = Fallkontext(fall=fall, schema=schema)
    fall.dokumenten_soll = soll_auswerten(fall, schema, k).as_dict()
    rechtsbehelf_und_brief(fall, schema, pruefung)
    beratungshinweise(fall, schema, pruefung)
    return pruefung


def nachreichung(
    fall: Fall,
    dokumente: list[Dokument],
    nachforderung_id: str | None = None,
    adapter: LLMAdapter | None = None,
) -> Fall:
    """The flip (14 §7): documents arrive later, the same case runs again.

    Not a new case and not an edit of the old result — the same case object
    gains documents and a second entry in `pruefungen[]`. L0 runs again over
    the whole case so the new pages are tokenised with the same map; only the
    new documents are classified and read.
    """
    if not dokumente:
        return fall
    adapter = adapter or adapter_holen()

    vergeben = [int(d.dok_id[1:]) for d in fall.dokumente
                if d.dok_id[1:].isdigit() and d.dok_id.startswith("D")]
    naechste = max(vergeben, default=0) + 1
    neue: list[str] = []
    for i, d in enumerate(dokumente, start=naechste):
        d.dok_id = f"D{i}"
        d.eingegangen = "nachreichung"
        d.nachforderung_id = nachforderung_id
        fall.dokumente.append(d)
        neue.append(d.dok_id)

    pseudonymisieren(fall)
    klassifizieren(fall, adapter)

    schema = schema_laden(fall.fallgruppe.gewaehlt or fall.schema_.fallgruppe_id)
    _verworfen_protokollieren(fall, extrahieren(fall, schema, adapter, nur=neue))

    for n in fall.nachforderungen:
        if nachforderung_id and n.id == nachforderung_id:
            n.status = Nachforderungsstatus.EINGEGANGEN
    fall.protokoll("nachreichung_eingegangen", dokumente=neue,
                   nachforderung_id=nachforderung_id)

    neu_pruefen(fall, schema, trigger="nachreichung",
                ausgeloest_durch=nachforderung_id)
    return fall


def fall_aus_verzeichnis(
    verzeichnis: Path, case_id: str, adapter: LLMAdapter | None = None
) -> Fall:
    """Load a fiction case from `demo/faelle/<name>/` — ticket.json + documents."""
    from fallpruefer.dokumente import laden

    ticket = json.loads((verzeichnis / "ticket.json").read_text(encoding="utf-8"))
    dokumente = [
        laden(verzeichnis / name, f"D{i}")
        for i, name in enumerate(ticket.get("anhaenge", []), start=1)
    ]
    fall = fall_anlegen(case_id, ticket, dokumente)
    return verarbeiten(fall, adapter)


# --------------------------------------------------------------------------
# The gates (14 §4). Every one of them writes an event.
#
# The event log is the audit trail the RDG framing rests on (14 §8), so a gate
# that changes the case and leaves no entry is not a shortcut — it is the one
# thing this design cannot afford. Action names are fixed by contract §12.
# --------------------------------------------------------------------------


def _verworfen_protokollieren(fall: Fall, verworfen) -> None:
    """The validator dropping a field is the trust layer doing its job — and it
    used to leave no trace at all: both callers threw `extrahieren`'s return
    value away, so a caught hallucination looked exactly like a document in
    which the value simply is not written. Now it is in the event log, which is
    where „zeigen Sie mir einen Fall, in dem der Prüfer zugeschlagen hat" gets
    its answer."""
    if verworfen:
        fall.protokoll("extraktion_verworfen", felder=sorted(set(verworfen)))


def _schema_von(fall: Fall) -> Schema:
    """Tolerant on purpose: a gate action during a broken Jurist-Edit works
    against the last good version („bleibt aktiv"). Only the schema-reload
    re-run loads strictly — see `neu_pruefen_nach_schema`."""
    from fallpruefer.schema import schema_laden_oder_letzte

    return schema_laden_oder_letzte(fall.fallgruppe.gewaehlt or fall.schema_.fallgruppe_id)


def leitfaden_antworten(
    fall: Fall, antworten: dict, von: str = "Beraterin"
) -> dict:
    """Rung 6 — the Leitfaden answers arrive and the case runs again.

    Not a gate: a gate is a decision the advisor makes about the assessment,
    this is new *input* about the facts. It behaves like a Nachreichung — a new
    entry in `pruefungen[]` with `trigger: leitfaden_antwort`, the previous run
    kept and its Gate-3 confirmation invalidated (`15` §4) — because the
    verdict may genuinely change and the pair has to stay readable.

    It also re-evaluates the Dokumenten-Soll, which is not incidental: „möchten
    Sie zu viel Gezahltes zurück?" flips the Kontoauszug from `pflicht:
    bedingt` to actually required, so answering the Leitfaden can put a new
    item into the Gate-1 Nachforderung.
    """
    from fallpruefer import leitfaden as lf

    schema = _schema_von(fall)
    strittig = lf.antworten(fall, schema, antworten, von=von)
    pruefung = neu_pruefen(fall, schema, trigger="leitfaden_antwort", ausgeloest_durch=von)
    fall.leitfaden = {
        "fragen": [f.model_dump(mode="json") for f in lf.fragen(fall, schema)],
    }
    return {
        "run_id": pruefung.run_id,
        "einordnung": pruefung.einordnung,
        "strittig": strittig,
    }


def gate1_nachforderung(
    fall: Fall,
    dokumenttypen: list[str] | None = None,
    kanal: str | None = None,
    von: str = "Beraterin",
) -> Nachforderung:
    """Gate 1 — the Nachforderung text, filled from the channel template.

    The tool never sends anything (14 §8): this produces a text the advisor
    copies or mails. `status` starts at `offen`; marking it `angefordert` is a
    second call, because „ich habe es abgeschickt" is a statement only a person
    can make.
    """
    schema = _schema_von(fall)
    pruefung = fall.aktuelle_pruefung()
    if pruefung is None:
        raise ValueError("Für diesen Fall liegt keine Prüfung vor.")

    offen = pruefung.vollstaendigkeit.get("verbraucher") or []
    if dokumenttypen is not None:
        gewuenscht = set(dokumenttypen)
        offen = [e for e in offen if e.dokumenttyp and e.dokumenttyp.value in gewuenscht]
    if not offen:
        raise ValueError("Verbraucherseitig ist nichts offen — es gibt nichts nachzufordern.")

    k_kanal = Kanal(kanal) if kanal else fall.eingang.kanal
    vorschlag = rb_modul.Vorschlag(
        rechtsbehelf_id="nachforderung", titel="Unterlagen nachfordern",
        musterbrief="nachforderung_{kanal}", geprueft=False,
    )
    template = rb_modul.template_id(vorschlag, k_kanal.value)
    vorlage = brief_modul.vorlage_laden(template)

    k = Fallkontext(fall=fall, schema=schema)
    werte = brief_modul.platzhalter_werte(fall, pruefung, k, vorlage)
    werte["[FEHLENDE_UNTERLAGEN_LISTE]"] = brief_modul.fehlende_unterlagen_liste(schema, offen)
    text = brief_modul.rendern(vorlage, werte, [], lint_nachforderung=True)

    # one entry per document, like the list in the text: a document can be open
    # twice over (not filed, and a required field of it unfound)
    typen: list = []
    for e in offen:
        if e.dokumenttyp and e.dokumenttyp not in typen:
            typen.append(e.dokumenttyp)

    n = Nachforderung(
        id=f"N{len(fall.nachforderungen) + 1}",
        kanal=k_kanal,
        dokumente=typen,
        text=text,
        markiert_von=von,
        zeit=zeit.jetzt(),
    )
    fall.nachforderungen.append(n)
    fall.protokoll("gate1_nachforderung_erzeugt", nachforderung_id=n.id,
                   kanal=k_kanal.value, dokumente=[d.value for d in n.dokumente])
    return n


def nachforderung_status(
    fall: Fall, nachforderung_id: str, status: str, von: str = "Beraterin"
) -> Nachforderung:
    n = next((x for x in fall.nachforderungen if x.id == nachforderung_id), None)
    if n is None:
        raise ValueError(f"Keine Nachforderung „{nachforderung_id}“ in diesem Fall.")
    n.status = Nachforderungsstatus(status)
    n.markiert_von = von
    n.zeit = zeit.jetzt()
    fall.protokoll("gate1_nachforderung_markiert", nachforderung_id=n.id, status=status)
    return n


def gate2_fallgruppe(fall: Fall, fallgruppe_id: str, von: str = "Beraterin") -> Fall:
    """Gate 2 — the advisor confirms or changes the Fallgruppe.

    Changing it re-runs the Soll and the Prüfung (14 §4 step 5), because a
    different Fallgruppe demands different documents. Confirming the proposed
    one is the same call with the same id.
    """
    if fallgruppe_id not in taxonomie():
        raise ValueError(f"„{fallgruppe_id}“ steht nicht in der Taxonomie.")

    gewechselt = fallgruppe_id != (fall.fallgruppe.gewaehlt or fall.schema_.fallgruppe_id)
    fall.fallgruppe.gewaehlt = fallgruppe_id
    fall.fallgruppe.bestaetigt = True
    fall.fallgruppe.gate2_von = von
    fall.fallgruppe.zeit = zeit.jetzt()

    schema = schema_laden(fallgruppe_id)
    fall.schema_ = SchemaRef(
        fallgruppe_id=fallgruppe_id, version=schema.version, stand=schema.stand
    )
    fall.fallgruppe.stufe = schema.stufe
    fall.protokoll("gate2_fallgruppe_gewaehlt", fallgruppe_id=fallgruppe_id,
                   gewechselt=gewechselt)

    if gewechselt:
        neu_pruefen(fall, schema, trigger="fallgruppe_gewechselt")
    return fall


def dokument_nicht_vorhanden(
    fall: Fall,
    dokumenttyp: str,
    aussage: str = "",
    von: str = "Beraterin",
    zurueckziehen: bool = False,
) -> Fall:
    """V-N2 — die Beraterin stellt fest, dass es eine Unterlage nie gegeben hat.

    Das Fehlen-Modell kannte bis hierher nur „liegt noch nicht vor", und Gate 1
    hat daraus eine Nachforderung an die Verbraucherin gemacht. Franz' Fall 6
    ist der Fall, in dem das falsch wird: es gab nie ein Erhöhungsschreiben.
    Danach wandert der Posten auf die Unternehmensseite — Auskunftsverlangen
    statt Nachforderung.

    Drei Dinge, die diese Funktion bewusst **nicht** tut:

    * Sie bewegt kein Urteil. Ob eine Erhöhung schon deshalb unwirksam ist,
      weil sie nie angekündigt wurde, ist eine juristische Frage, die offen
      ist (`24` §7 Frage 2 an Franz) — sie wird nicht per Code entschieden.
    * Sie legt kein Dokument an. „Nicht vorhanden" ist eine Aussage über die
      Welt, kein Ersatzdokument, und das Soll bleibt unerfüllt.
    * Sie glaubt es nicht von selbst. `aussage` ist Pflicht, weil die
      Feststellung sonst nicht von einer Vermutung zu unterscheiden wäre —
      derselbe Grund, aus dem ein Override einen Grund braucht.
    """
    from fallpruefer.vokabular import label

    schema = _schema_von(fall)
    typ = Dokumenttyp(dokumenttyp)

    vorhanden = next(
        (n for n in fall.nicht_vorhanden if n.dokumenttyp == typ and not n.zurueckgezogen),
        None,
    )
    if zurueckziehen:
        if vorhanden is None:
            raise ValueError(f"Für {label(typ)} liegt keine solche Feststellung vor.")
        vorhanden.zurueckgezogen = True
        fall.protokoll("dokument_nicht_vorhanden_zurueckgezogen", dokumenttyp=typ.value)
    else:
        if not aussage.strip():
            raise ValueError(
                "Ohne die Aussage, auf die sie sich stützt, wird die Feststellung "
                "nicht gespeichert."
            )
        if typ in {d.dokumenttyp for d in fall.dokumente}:
            raise ValueError(
                f"{label(typ)} liegt in diesem Fall vor — eine Feststellung, "
                f"dass es das Dokument nie gab, wäre eine Aussage gegen die Akte."
            )
        if vorhanden is not None:
            vorhanden.zurueckgezogen = True
        fall.nicht_vorhanden.append(NichtVorhanden(
            dokumenttyp=typ, aussage=aussage.strip(), von=von, zeit=zeit.jetzt(),
        ))
        fall.protokoll("dokument_als_nicht_vorhanden_markiert",
                       dokumenttyp=typ.value, aussage=aussage.strip())

    neu_pruefen(fall, schema, trigger="nicht_vorhanden")
    return fall


def gate3_override(
    fall: Fall,
    pruefpunkt_id: str,
    neuer_zustand: str | None = None,
    grund: str = "",
    von: str = "Beraterin",
    zurueckziehen: bool = False,
) -> Fall:
    """Gate 3 — „Prüfpunkt überschreiben mit Grund".

    `grund` is not optional and not a formality: an override without a stated
    reason is exactly the thing the audit trail exists to prevent. Overrides
    persist across later runs until withdrawn (contract §4).
    """
    schema = _schema_von(fall)
    if schema.pruefpunkt(pruefpunkt_id) is None:
        raise ValueError(f"„{pruefpunkt_id}“ gibt es in diesem Prüfschema nicht.")

    vorhanden = next(
        (o for o in fall.overrides if o.pruefpunkt_id == pruefpunkt_id and not o.zurueckgezogen),
        None,
    )
    if zurueckziehen:
        if vorhanden is None:
            raise ValueError(f"Für {pruefpunkt_id} liegt kein aktiver Override vor.")
        vorhanden.zurueckgezogen = True
        fall.protokoll("gate3_override_zurueckgezogen", pruefpunkt_id=pruefpunkt_id)
    else:
        if not grund.strip():
            raise ValueError("Ein Override ohne Grund wird nicht gespeichert.")
        if neuer_zustand is None:
            raise ValueError("neuer_zustand fehlt.")
        if vorhanden is not None:
            vorhanden.zurueckgezogen = True
        fall.overrides.append(Override(
            pruefpunkt_id=pruefpunkt_id, neuer_zustand=Zustand(neuer_zustand),
            grund=grund.strip(), von=von, zeit=zeit.jetzt(),
            gilt_fuer_runs=f"ab R-{len(fall.pruefungen) + 1}",
        ))
        fall.protokoll("gate3_override", pruefpunkt_id=pruefpunkt_id,
                       neuer_zustand=neuer_zustand, grund=grund.strip())

    neu_pruefen(fall, schema, trigger="override")
    return fall


def gate4_rechtsbehelf(fall: Fall, rechtsbehelf_id: str, von: str = "Beraterin") -> Fall:
    """Gate 4 — the advisor picks one of the offered remedies, and the letter
    is re-rendered for it. Only what was offered can be picked: the guarantee
    per branch (14 §5) is the list, not a suggestion box."""
    schema = _schema_von(fall)
    pruefung = fall.aktuelle_pruefung()
    if pruefung is None:
        raise ValueError("Für diesen Fall liegt keine Prüfung vor.")
    if rechtsbehelf_id not in fall.rechtsbehelf.vorschlaege:
        raise ValueError(
            f"„{rechtsbehelf_id}“ wurde für diesen Fall nicht vorgeschlagen "
            f"({', '.join(fall.rechtsbehelf.vorschlaege) or 'keine Vorschläge'})."
        )
    fall.rechtsbehelf.gewaehlt = rechtsbehelf_id
    fall.rechtsbehelf.gate4_von = von
    fall.protokoll("gate4_rechtsbehelf_gewaehlt", rechtsbehelf_id=rechtsbehelf_id)
    rechtsbehelf_und_brief(fall, schema, pruefung)
    beratungshinweise(fall, schema, pruefung)
    # Contract §8: „written at Gate 3 confirmation (and updated at Gate 4/flag)".
    # Only an already-confirmed case is updated — writing here otherwise would
    # let an unconfirmed run into the corpus, which is what the Gate-3 rule
    # exists to prevent. Without this the store froze `rechtsbehelf` on the
    # Gate-3 value, so „welche Rechtsbehelfe brauchen die Beraterinnen
    # wirklich?" — the evaluation the Referat expects — read the program's
    # first proposal rather than the advisor's choice.
    if pruefung.gate3:
        from fallpruefer import store

        store.schreiben(fall)
    return fall


def brief_status_setzen(fall: Fall, status: str) -> Fall:
    """The letter's own status — `entwurf` → `uebergeben`. The tool does not
    send it; this records that the advisor handed it over (14 §4 step 10)."""
    if fall.rechtsbehelf.brief is None:
        raise ValueError("Für diesen Fall wurde kein Schreiben erzeugt.")
    fall.rechtsbehelf.brief.status = Briefstatus(status)
    fall.protokoll("brief_status", template=fall.rechtsbehelf.brief.template_id, status=status)
    return fall


def abschluss(
    fall: Fall,
    basis_export: bool = False,
    wiedervorlagen: list[str] | None = None,
    schliessen: bool = False,
    von: str = "Beraterin",
) -> Fall:
    """Step 10 — Basis-Eintrag, Wiedervorlagen, close.

    „Basis-Eintrag erzeugen" produces a copyable block, nothing more: the
    integration stance is „standalone erstmal, Anbindung später" (14 §8), and
    a written export would be a claim we have not earned.
    """
    schema = _schema_von(fall)
    pruefung = fall.aktuelle_pruefung()
    if pruefung is None:
        raise ValueError("Für diesen Fall liegt keine Prüfung vor.")

    if basis_export:
        k = Fallkontext(fall=fall, schema=schema)
        vorlage = brief_modul.vorlage_laden("basis_eintrag")
        werte = brief_modul.basis_platzhalter(fall, pruefung, schema, k)
        fall.abschluss.basis_text = brief_modul.rendern(vorlage, werte, [])
        fall.abschluss.basis_export_erzeugt = True
        fall.protokoll("abschluss_basis_export")

    if wiedervorlagen is not None:
        fall.abschluss.wiedervorlagen = list(wiedervorlagen)

    if schliessen:
        fall.abschluss.geschlossen = True
        fall.status = Fallstatus.GESCHLOSSEN
        # Contract §12: the log names roles, never advisors — it is oversight
        # evidence and must not become Leistungskontrolle (14 §8, § 87 BetrVG).
        # `von` reaches `abschluss.von` for the Akte; it does not reach the log.
        fall.protokoll("fall_geschlossen")
    return fall


def neu_pruefen_nach_schema(fall: Fall) -> Fall:
    """Akt 2 (14 §7): the Prüfschema file was edited, the case runs again.

    This is the whole „Jurist-Edit" beat — the Volljurist changes a parameter,
    a role or a condition in the JSON, and the same case comes back with a
    different answer and no code deployed.

    Deliberately strict: this is the one call whose job is reading the edited
    file, so a broken edit raises here (and only here) instead of silently
    re-running against the old version — the person at the editor is the one
    who has to hear about the typo.
    """
    schema = schema_laden(fall.fallgruppe.gewaehlt or fall.schema_.fallgruppe_id)
    fall.schema_ = SchemaRef(
        fallgruppe_id=schema.fallgruppe_id, version=schema.version, stand=schema.stand
    )
    fall.protokoll("schema_geladen", version=schema.version, stand=schema.stand)
    neu_pruefen(fall, schema, trigger="schema_reload")
    return fall


# --------------------------------------------------------------------------
# Gate 3 confirmation and the Referat flag — the two actions that feed the Radar
# --------------------------------------------------------------------------


def gate3_bestaetigen(fall: Fall, von: str = "Beraterin") -> dict:
    """Step 6 of 14 §4. The advisor confirms the Einordnung — and only then
    does the case enter the anonymised store (contract §8).

    Confirmation is the honest trigger: an unconfirmed run is a proposal, and
    a Radar built from proposals would count the program's opinions rather
    than the advisory's findings.
    """
    from fallpruefer import store

    pruefung = fall.aktuelle_pruefung()
    if pruefung is None:
        raise ValueError("Für diesen Fall liegt keine Prüfung vor.")
    pruefung.gate3 = {"aktion": "bestaetigt", "von": von, "zeit": zeit.jetzt(), "gueltig": True}
    fall.protokoll("gate3_bestaetigt", run_id=pruefung.run_id)
    satz = store.schreiben(fall)
    fall.protokoll("store_geschrieben", fall_hash=satz["fall_hash"])
    return satz


def referat_markieren(
    fall: Fall, kriterien: list[str], notiz: str = "", von: str = "Beraterin"
) -> dict:
    """Step 9. Nothing is ticked automatically (14 §4) — the criteria come from
    the advisor. The store row is updated so the flag shows up on the Radar.

    Gate 3 first. `store.py` states the invariant („every **confirmed** case
    counts") and `gate3_bestaetigen` gives the reason: an unconfirmed run is a
    proposal, and a Radar built from proposals counts the program's opinions
    rather than the advisory's findings. This path wrote a row — and a Radar
    +1 — with Gate 3 never pressed, which is the one way an unconfirmed
    Einordnung could enter the corpus. 14 §4 puts Gate 3 at step 6 and the flag
    at step 9, so in the workflow the order already holds; now the code says so.
    """
    from fallpruefer import store

    pruefung = fall.aktuelle_pruefung()
    if pruefung is None or not pruefung.gate3:
        raise ValueError(
            "Die Einordnung ist noch nicht bestätigt (Gate 3) — "
            "erst bestätigen, dann für das Referat markieren."
        )

    erlaubt = {k["id"] for k in konfig().referat_kriterien}
    unbekannt = [k for k in kriterien if k not in erlaubt]
    if unbekannt:
        raise ValueError(f"unbekannte Kriterien: {', '.join(unbekannt)} — "
                         "die sechs FWN-Kriterien stehen in config.json")
    fall.referat_markierung.kriterien = list(kriterien)
    fall.referat_markierung.notiz = notiz
    fall.referat_markierung.von = von
    fall.referat_markierung.zeit = zeit.jetzt()
    fall.protokoll("referat_markiert", kriterien=kriterien)
    return store.schreiben(fall)


def fall_speichern(fall: Fall) -> Path:
    pfad = WURZEL / "cases" / f"{fall.case_id}.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(
        json.dumps(fall.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return pfad


def fall_laden(case_id: str) -> Fall | None:
    pfad = WURZEL / "cases" / f"{case_id}.json"
    if not pfad.exists():
        return None
    return Fall.model_validate(json.loads(pfad.read_text(encoding="utf-8")))
