"""Loading a Prüfschema file (contract §2) — and refusing to load a broken one.

The schema file is the SSOT for the legal layer: parameters, texts, anchors,
roles and conditions all live there, and a Jurist edits that JSON, not code.
The price of that is a real load-time check — contract §1: *unknown primitive
or feld → schema load error*. That check lives here, so a bad Jurist-Edit fails
loudly at startup instead of quietly producing a wrong verdict at runtime.

The models are deliberately permissive (`extra="allow"`): the file is authored
by hand, and a key this build does not read yet must not stop it from loading.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from fallpruefer.konfig import WURZEL
from fallpruefer.normbasis import normbasis
from fallpruefer.primitiven import PRIMITIVE
from fallpruefer.vokabular import (
    Dokumenttyp,
    Hinweisart,
    Pflicht,
    Quelle,
    Rolle,
    Stufe,
    Typ,
    Zustand,
)

# Namespaces a rule may reference besides the Dokumenten-Soll field ids.
OFFENE_NAMESPACES = ("gespraech.", "intake.", "pruefpunkt.", "berechnung.")

# Fields the engine itself supplies once a run is finished — the remedy
# conditions and letter variants read these, not document facts.
ERGEBNIS_FELDER = {"einordnung", "gerissene_stufe", "fehlt_unternehmen", "fehlt_verbraucher", "stufe", "kanal"}

# The rule keys the evaluator actually dispatches on (`evaluator._REIHENFOLGE`)
# plus `sonst`. Kept here because this is where a Jurist-Edit gets checked.
REGEL_SCHLUESSEL = ("FEHLT_wenn", "NEIN_wenn", "WERTUNG_wenn", "JA_wenn", "sonst")
_ZAHL = re.compile(r"-?\d+(?:[.,]\d+)?")


class SchemaFehler(RuntimeError):
    """The schema file cannot be loaded. Contract bug or bad Jurist-Edit.

    `letzte_fassung` carries the version that was serving before the broken
    edit, when there is one — so a caller that only *reads* can keep doing so
    while the person at the editor fixes their typo.
    """

    def __init__(self, meldung: str, letzte_fassung: "Schema | None" = None):
        super().__init__(meldung)
        self.letzte_fassung = letzte_fassung


class Feld(BaseModel):
    model_config = ConfigDict(extra="allow")
    feld_id: str
    typ: str
    pflicht: bool = False
    werte: list[str] | None = None
    # V-23: Anzeigetext je Enum-Wert. Ohne ihn rendert ein in einen Satz
    # interpolierter Enum-Wert seinen rohen Code — „Das Schreiben wertet
    # weiternutzung als Zustimmung" stand so in der Demo-Spur. Kein Fallback
    # auf Titelschreibung o. Ä.: „Weiternutzung" wäre auch nur der Code mit
    # grossem Anfangsbuchstaben, und der Satz braucht eine Beugung, die nur
    # ein Mensch hinschreiben kann.
    wert_labels: dict[str, str] | None = None
    zitat_pflicht: bool = False
    beschreibung: str | None = None
    # R5: kurze Nominalphrase für den Schirm („Stand der AGB"). `beschreibung`
    # ist ein Satz für das Modell und taugt nicht als Beschriftung; ohne
    # `label` stand die feld_id („agb.fassung_datum") vor der Beraterin.
    label: str | None = None


class SollDokument(BaseModel):
    model_config = ConfigDict(extra="allow")
    dokumenttyp: Dokumenttyp
    pflicht: Pflicht
    bedingung: dict | None = None
    gruppe: str | None = None
    quelle: Quelle = Quelle.VERBRAUCHER
    anzeigename: str = ""
    begruendung_satz: str = ""
    beschaffungsweg: str = ""
    felder: list[Feld] = Field(default_factory=list)


class SollGruppe(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    mindestens_eines: list[Dokumenttyp]
    anzeigename: str = ""


class DokumentenSoll(BaseModel):
    model_config = ConfigDict(extra="allow")
    gruppen: list[SollGruppe] = Field(default_factory=list)
    dokumente: list[SollDokument] = Field(default_factory=list)

    def nach_typ(self, typ: Dokumenttyp) -> SollDokument | None:
        return next((d for d in self.dokumente if d.dokumenttyp == typ), None)

    def feld(self, feld_id: str) -> Feld | None:
        for d in self.dokumente:
            for f in d.felder:
                if f.feld_id == feld_id:
                    return f
        return None

    def besitzer(self, feld_oder_typ: str) -> Quelle:
        """Who owns a missing input — drives Nachforderung vs Auskunftsverlangen."""
        typ = feld_oder_typ.split(".", 1)[0]
        for d in self.dokumente:
            if d.dokumenttyp.value == typ:
                return d.quelle
        return Quelle.VERBRAUCHER


class Eingabe(BaseModel):
    model_config = ConfigDict(extra="allow")
    feld: str
    pflicht: bool = False
    oder: str | None = None

    @property
    def felder(self) -> list[str]:
        return [self.feld] + ([self.oder] if self.oder else [])


class Annahme(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    feld: str
    wert: str | int | float | bool
    anzeige: str = ""
    geprueft: bool = False


class Fachpruefung(BaseModel):
    """Wer diesen Prüfpunkt fachlich entschieden hat — pro Prüfpunkt, nie
    schemaweit (V-A1).

    Das schemaweite `geprueft_von` bleibt leer, und das ist keine Nachlässigkeit:
    niemand hat dieses Prüfschema als Ganzes abgenommen. P8b und P14 sind unsere
    eigenen Punkte, die Franz nie vorgelegen haben; ein pauschaler Name über der
    Datei wäre genau die Falschzuschreibung, gegen die der ganze Entwurf gebaut
    ist. Deshalb steht die Zuschreibung an dem einzelnen Punkt, über den
    tatsächlich jemand entschieden hat.

    `vorbehalt` ist der Teil, den man weglassen könnte und nicht darf: Franz hat
    zu P10 die Regel bestätigt und dabei gesagt, dass es die pauschale Zahl, die
    wir implementiert haben, gar nicht gibt. Eine Zuschreibung ohne diesen Satz
    würde unsere Umsetzung mit seinem Namen decken.
    """

    model_config = ConfigDict(extra="allow")
    wer: str
    am: str
    beleg: str
    umfang: str
    vorbehalt: str | None = None


class Pruefpunkt(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    titel: str = ""
    rolle: Rolle
    typ: Typ | None = None
    proposition: str = ""
    eingaben: list[Eingabe] = Field(default_factory=list)
    regel: dict | None = None
    parameter: dict | None = None
    anker: list[dict] = Field(default_factory=list)
    bei_NEIN: dict | None = None
    rechtsbehelf_bei_NEIN: str | None = None
    rechtsbehelf_bei_FEHLT: str | None = None
    wertungsfrage: str | None = None
    leitfaden_frage: dict | None = None
    satz_ja: str | None = None
    # V-F2: ein Satz pro Arm. Ein String gilt für jeden Arm; eine Liste
    # `[{"wenn": <Bedingung>, "satz": "…"}, …]` wird in Reihenfolge geprüft,
    # der erste zutreffende Arm spricht, ein Eintrag ohne `wenn` ist der Rest.
    satz_nein: str | list[dict] | None = None
    fehlt_text: str | list[dict] | None = None
    plain_grund: str | list[dict] | None = None
    pruefumfang_text: str | None = None
    frist: dict | None = None
    betrag: dict | None = None
    berechnung: dict | None = None
    nur_wenn: dict | None = None
    fristen: list[dict] = Field(default_factory=list)
    fehlt_owner: Quelle | None = None
    geprueft: bool | None = None
    geprueft_hinweis: dict | None = None
    geprueft_von: list[Fachpruefung] = Field(default_factory=list)


class Beratungshinweis(BaseModel):
    """Ein Satz an die Beraterin, der ausdrücklich kein Prüfpunkt ist.

    `wenn` ist eine gewöhnliche Bedingung der Regelgrammatik und läuft gegen
    denselben Kontext wie die Rechtsbehelfe — kein zweiter Mechanismus, nur ein
    zweiter Konsument des vorhandenen.

    `geprueft_von` ist dasselbe Modell wie am Prüfpunkt (V-A1), und hier ist es
    wichtiger als dort: diese Sätze stammen zu 100 % von Franz. Ein Hinweis auf
    dem Schirm ohne die Angabe, wer ihn zu verantworten hat, wäre auf genau dem
    Bildschirm die auffälligste Lücke, dessen Zweck die Nachvollziehbarkeit ist.
    """

    model_config = ConfigDict(extra="allow")
    id: str
    art: Hinweisart
    titel: str
    text: str
    wenn: dict | None = None
    anker: list[dict] = Field(default_factory=list)
    geprueft_von: list[Fachpruefung] = Field(default_factory=list)


class Knoten(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    op: str = "AND"
    titel: str = ""
    kinder: list["Knoten | str"] = Field(default_factory=list)
    hinweis: str | None = None


class Rechtsbehelf(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    titel: str
    wenn: dict | None = None
    musterbrief: str | None = None
    empfaenger: str | None = None
    geprueft: bool = False
    kommentar: str | None = None


class Rechtsbehelfe(BaseModel):
    model_config = ConfigDict(extra="allow")
    garantie_pro_zweig: dict[str, list[str]] = Field(default_factory=dict)
    liste: list[Rechtsbehelf] = Field(default_factory=list)
    ranking: str = ""

    def nach_id(self, rid: str) -> Rechtsbehelf | None:
        return next((r for r in self.liste if r.id == rid), None)


class Schema(BaseModel):
    model_config = ConfigDict(extra="allow")
    fallgruppe_id: str
    name: str
    skin: str | None = None
    stufe: Stufe
    version: str
    stand: str
    geprueft_von: list[str] = Field(default_factory=list)
    regelsprache: str = "v1"
    jurist_edit_knoepfe: list[str] = Field(default_factory=list)
    annahmen: list[Annahme] = Field(default_factory=list)
    dokumenten_soll: DokumentenSoll = Field(default_factory=DokumentenSoll)
    baum: Knoten | None = None
    pruefpunkte: list[Pruefpunkt] = Field(default_factory=list)
    aggregation: dict = Field(default_factory=dict)
    rechtsbehelfe: Rechtsbehelfe = Field(default_factory=Rechtsbehelfe)
    beratungshinweise: list[Beratungshinweis] = Field(default_factory=list)
    plain_saetze: dict[str, str] = Field(default_factory=dict)

    def pruefpunkt(self, pid: str) -> Pruefpunkt | None:
        return next((p for p in self.pruefpunkte if p.id == pid), None)

    def hinweis(self, hid: str) -> Beratungshinweis | None:
        return next((h for h in self.beratungshinweise if h.id == hid), None)

    def fachpruefung_stand(self) -> tuple[int, int]:
        """`(bestaetigt, gesamt)` — wie viele Prüfpunkte eine fachliche
        Zuschreibung tragen (V-A1).

        Im Motor gerechnet, damit die Anzeige nicht zählen muss. Der Sinn ist
        die Ehrlichkeit, nicht die Vollständigkeit: die Zahl macht Abwesenheit
        lesbar, ohne jedem einzelnen Punkt ein Negativabzeichen anzuhängen —
        dreizehn rote Marker nebeneinander erziehen zum Wegsehen.
        """
        return (
            sum(1 for p in self.pruefpunkte if p.geprueft_von),
            len(self.pruefpunkte),
        )

    @property
    def nur_rolle(self) -> set[Rolle]:
        rollen = self.aggregation.get("nur_rolle") or ["tragend"]
        return {Rolle(r) for r in rollen}

    def bekannte_felder(self) -> set[str]:
        """Every feld id a rule is allowed to name."""
        felder = {f.feld_id for d in self.dokumenten_soll.dokumente for f in d.felder}
        # `erwartet_wenn_vorhanden` makes absence a legal fact recorded as
        # `<typ>.vorhanden` (contract §0) — synthesised for every Soll type.
        felder |= {f"{d.dokumenttyp.value}.vorhanden" for d in self.dokumenten_soll.dokumente}
        felder |= {a.feld for a in self.annahmen}
        felder |= ERGEBNIS_FELDER
        return felder


# --------------------------------------------------------------------------
# load-time validation
# --------------------------------------------------------------------------


def _felder_in(bedingung, heraus: set[str]) -> None:
    if isinstance(bedingung, dict):
        for schluessel in ("feld", "feld2", "fehlt", "vorhanden", "verifiziert"):
            wert = bedingung.get(schluessel)
            if isinstance(wert, str):
                heraus.add(wert)
        args = bedingung.get("args")
        if isinstance(args, dict):
            for wert in args.values():
                if isinstance(wert, str) and "." in wert:
                    heraus.add(wert)
        for wert in bedingung.values():
            _felder_in(wert, heraus)
    elif isinstance(bedingung, list):
        for wert in bedingung:
            _felder_in(wert, heraus)


def _primitive_in(bedingung, heraus: set[str]) -> None:
    if isinstance(bedingung, dict):
        if isinstance(bedingung.get("prim"), str):
            heraus.add(bedingung["prim"])
        for wert in bedingung.values():
            _primitive_in(wert, heraus)
    elif isinstance(bedingung, list):
        for wert in bedingung:
            _primitive_in(wert, heraus)


def pruefen(s: Schema) -> None:
    fehler: list[str] = []
    ids = {p.id for p in s.pruefpunkte}

    # the tree may only name Prüfpunkte that exist
    def baum_pruefen(k: Knoten) -> None:
        for kind in k.kinder:
            if isinstance(kind, str):
                if kind not in ids:
                    fehler.append(f"Baum-Knoten {k.id} nennt unbekannten Prüfpunkt „{kind}“")
            else:
                baum_pruefen(kind)

    if s.baum:
        baum_pruefen(s.baum)

    bekannt = s.bekannte_felder()
    quellen: list[tuple[str, object]] = [
        *((p.id, p.regel) for p in s.pruefpunkte),
        *((p.id, p.nur_wenn) for p in s.pruefpunkte),
        *((p.id, p.berechnung) for p in s.pruefpunkte),
        *((p.id, p.frist) for p in s.pruefpunkte),
        *((f"soll:{d.dokumenttyp.value}", d.bedingung) for d in s.dokumenten_soll.dokumente),
        *((f"rechtsbehelf:{r.id}", r.wenn) for r in s.rechtsbehelfe.liste),
    ]

    for herkunft, bedingung in quellen:
        genannt: set[str] = set()
        _felder_in(bedingung, genannt)
        for feld in genannt:
            if feld in bekannt or feld.startswith(OFFENE_NAMESPACES):
                continue
            fehler.append(f"{herkunft}: unbekanntes Feld „{feld}“")

        prims: set[str] = set()
        _primitive_in(bedingung, prims)
        for prim in prims:
            if prim not in PRIMITIVE:
                fehler.append(f"{herkunft}: unbekanntes Primitiv „{prim}“")

    for p in s.pruefpunkte:
        for e in p.eingaben:
            for feld in e.felder:
                if feld not in bekannt and not feld.startswith(OFFENE_NAMESPACES):
                    fehler.append(f"{p.id}: eingabe nennt unbekanntes Feld „{feld}“")

    # The Akt-2 beat is a person editing this file in a text editor while the
    # program runs, so the load-time check has to catch the typos a person
    # actually makes. These three all *loaded* before and changed the answer
    # instead: a mis-cased rule key („NEIN_Wenn") was ignored, so the Prüfpunkt
    # silently returned the opposite state; a `sonst` the Zustand enum does not
    # know crashed at runtime, not at load; and a numeric parameter written
    # with quotes („90") turned every comparison against it into „we cannot
    # say", because `int < str` is a TypeError the grammar maps to None.
    for p in s.pruefpunkte:
        for schluessel in (p.regel or {}):
            if schluessel not in REGEL_SCHLUESSEL:
                nah = [k for k in REGEL_SCHLUESSEL if k.lower() == str(schluessel).lower()]
                hinweis = f" — gemeint war wohl „{nah[0]}“" if nah else ""
                fehler.append(f"{p.id}: unbekannter Regel-Schlüssel „{schluessel}“{hinweis}")
        sonst = (p.regel or {}).get("sonst")
        if sonst is not None and sonst not in {z.value for z in Zustand}:
            fehler.append(
                f"{p.id}: „sonst“: {sonst!r} ist kein Zustand "
                f"({', '.join(sorted(z.value for z in Zustand))})"
            )
        for name, wert in (p.parameter or {}).items():
            if isinstance(wert, str) and _ZAHL.fullmatch(wert.strip()):
                fehler.append(
                    f"{p.id}: Parameter „{name}“ ist die Zeichenkette {wert!r} — "
                    "als Zahl schreiben (ohne Anführungszeichen), sonst vergleicht die Regel nicht"
                )

    # `begruendung_satz` is pasted verbatim into the Gate-1 letter
    # (`brief.fehlende_unterlagen_liste`), which may not assess anything
    # (14 §4 step 3). Checked here so the author hears about it when the file
    # loads, not when a Beraterin presses the button.
    from fallpruefer.brief import _NACHFORDERUNG_LINT

    for d in s.dokumenten_soll.dokumente:
        if d.quelle == Quelle.VERBRAUCHER and (t := _NACHFORDERUNG_LINT.search(d.begruendung_satz)):
            fehler.append(
                f"soll:{d.dokumenttyp.value}: „begruendung_satz“ enthält die rechtliche "
                f"Aussage „{t.group(0)}“ — der Satz steht wörtlich im Nachforderungsschreiben"
            )

    # no sentence that reaches the screen may name a Prüfpunkt by its number
    _NUMMER = re.compile(r"\bP\d+\b")
    for p in s.pruefpunkte:
        for feld in ("satz_ja", "satz_nein", "plain_grund", "wertungsfrage",
                     "fehlt_text", "proposition", "pruefumfang_text"):
            wert = getattr(p, feld, None)
            if isinstance(wert, list):
                for arm in wert:
                    if not isinstance(arm, dict) or not isinstance(arm.get("satz"), str):
                        fehler.append(f"{p.id}.{feld}: ein Arm braucht ein `satz`-Feld — {arm!r}")
                wert = " ".join(a.get("satz", "") for a in wert if isinstance(a, dict))
            if isinstance(wert, str) and (treffer := _NUMMER.search(wert)):
                # „P5" is our bookkeeping. An advisor reading „die Belehrung ist
                # fehlerhaft (P5)" learns nothing she did not already see, and a
                # consumer reading it in a letter learns less than nothing. The
                # same rule the evaluator already follows — a test asserts that
                # it names no Prüfpunkt — only the schema sentences were outside
                # it, which is where the numbers actually get typed.
                fehler.append(
                    f"{p.id}.{feld}: nennt „{treffer.group(0)}“ — ein Satz für den Bildschirm "
                    f"benennt die Sache, nicht die Nummer"
                )

    # a gate that switches Prüfpunkte off must say why it did
    ids = {p.id for p in s.pruefpunkte}
    for p in s.pruefpunkte:
        aus = (p.bei_NEIN or {}).get("deaktiviert") or []
        if not aus:
            continue
        unbekannt = [pid for pid in aus if pid not in ids]
        if unbekannt:
            fehler.append(f"{p.id}: „deaktiviert“ nennt {', '.join(unbekannt)} — den/die gibt es nicht")
        if not (p.bei_NEIN or {}).get("text", "").strip():
            # `evaluator.pruefen` copies this text into `inaktiv_grund` of every
            # deactivated Prüfpunkt, and it is the only sentence the screen has
            # for them. Left empty, four points drop out of the trace with no
            # comment and the Fallakte looks like the program forgot something —
            # when in truth it decided they do not apply. That is a legal
            # statement, so it belongs in the file the jurist edits, not in a
            # fallback in the engine.
            fehler.append(
                f"{p.id}: schaltet {', '.join(aus)} ab, ohne in „bei_NEIN.text“ zu sagen warum"
            )

    # a rule may not cite a ground that does not exist
    nb = normbasis()
    for p in s.pruefpunkte:
        for a in p.anker:
            key = a.get("key")
            if key and not nb.kennt(key):
                if nb.modus == "strict":
                    fehler.append(f"{p.id}: Anker „{key}“ fehlt in der Normbasis")
                else:
                    nb.warnungen.append(f"{p.id}: Anker „{key}“ fehlt in der Normbasis")

    if fehler:
        raise SchemaFehler(
            "Prüfschema nicht ladbar:\n  - " + "\n  - ".join(fehler)
        )


# fallgruppe_id -> (mtime_ns, size, Schema). The mtime is part of the key, not
# a side note: „Jurist-Edit" (14 §7 Akt 2) is a person editing this JSON in a
# text editor while the program runs. A cache that never notices the edit turns
# the whole claim — „das Papier und der Code sind dieselbe Datei" — into a
# claim that needs a restart to be true.
_CACHE: dict[str, tuple[int, int, Schema]] = {}


def _stempel(pfad: Path) -> tuple[int, int]:
    st = pfad.stat()
    return st.st_mtime_ns, st.st_size


def schema_laden(fallgruppe_id: str, verzeichnis: Path | None = None) -> Schema:
    v = verzeichnis or (WURZEL / "schemas")
    pfad = v / f"{fallgruppe_id}.json"
    if not pfad.exists():
        raise SchemaFehler(f"Kein Prüfschema für „{fallgruppe_id}“ ({pfad})")

    stempel = _stempel(pfad)
    zwischenstand = _CACHE.get(fallgruppe_id)
    if zwischenstand and zwischenstand[:2] == stempel:
        return zwischenstand[2]

    # A broken edit must not take the running schema down with it: the last
    # good version keeps serving and the error names the file.
    try:
        s = Schema.model_validate(json.loads(pfad.read_text(encoding="utf-8")))
        pruefen(s)
    except Exception as e:
        if zwischenstand:
            raise SchemaFehler(
                f"{pfad.name} ist nicht ladbar — die zuletzt geladene Fassung "
                f"{zwischenstand[2].version} bleibt aktiv. Ursache: {e}",
                letzte_fassung=zwischenstand[2],
            ) from e
        # Cold start inside the same window: there is no last good version to
        # fall back on, but the error still has to be the one every caller
        # type-checks for — a raw JSONDecodeError escapes `except SchemaFehler`
        # and reaches the UI as a bare 500.
        raise SchemaFehler(f"{pfad.name} ist nicht ladbar. Ursache: {e}") from e

    _CACHE[fallgruppe_id] = (*stempel, s)
    return s


def schema_laden_oder_letzte(fallgruppe_id: str, verzeichnis: Path | None = None) -> Schema:
    """Read paths use this: a broken file on disk serves the last good version
    instead of taking every Fallakte view down with it. The one caller that
    must NOT be tolerant is the Jurist-Edit re-run itself — its whole point is
    loading the edited file, so it calls `schema_laden` and surfaces the error
    to the person holding the editor."""
    try:
        return schema_laden(fallgruppe_id, verzeichnis)
    except SchemaFehler as e:
        if e.letzte_fassung is not None:
            return e.letzte_fassung
        raise


def schema_geaendert(fallgruppe_id: str, verzeichnis: Path | None = None) -> bool:
    """Has the file on disk moved since we last read it? Answers the Act-2
    question „muss ich neu prüfen?" without loading anything."""
    v = verzeichnis or (WURZEL / "schemas")
    pfad = v / f"{fallgruppe_id}.json"
    zwischenstand = _CACHE.get(fallgruppe_id)
    if not pfad.exists() or not zwischenstand:
        return False
    return zwischenstand[:2] != _stempel(pfad)


# stem -> (mtime_ns, size, entry). Same discipline as the schema cache, for the
# same reason: taxonomie() is called on every view build, and a half-saved
# Jurist-Edit must not turn every Fallakte request into a JSONDecodeError.
_TAX_CACHE: dict[str, tuple[int, int, dict]] = {}


def taxonomie(verzeichnis: Path | None = None) -> dict[str, dict]:
    """`schemas/_taxonomie.json` is derived at load — the schema file is the
    Stufe SSOT (contract §0), so nothing is maintained twice. A file that does
    not parse keeps its last good entry (and is skipped if it never had one):
    read paths stay up while someone is mid-edit."""
    v = verzeichnis or (WURZEL / "schemas")
    out: dict[str, dict] = {}
    for pfad in sorted(v.glob("*.json")):
        if pfad.stem.startswith("_"):
            continue
        stempel = _stempel(pfad)
        zwischenstand = _TAX_CACHE.get(pfad.stem)
        if zwischenstand and zwischenstand[:2] == stempel:
            eintrag = zwischenstand[2]
        else:
            try:
                roh = json.loads(pfad.read_text(encoding="utf-8"))
                eintrag = {
                    "fallgruppe_id": roh["fallgruppe_id"],
                    "name": roh["name"],
                    "stufe": roh["stufe"],
                    "version": roh.get("version"),
                    "hat_pruefpunkte": bool(roh.get("pruefpunkte")),
                }
                _TAX_CACHE[pfad.stem] = (*stempel, eintrag)
            except Exception:  # noqa: BLE001 — Absicht, siehe unten
                # Breit gefangen, und das ist die Eigenschaft, nicht der Fehler:
                # `taxonomie()` liest JEDE Schemadatei, und ein Tippfehler in
                # irgendeiner darf während des Jurist-Edits (14 §7 Akt 2) nicht
                # die Fallakte mitreißen. Die letzte gute Fassung bedient
                # weiter; wer den Editor offenhält, hört den Fehler vom
                # strikten Ladepfad (`18` #44).
                if zwischenstand is None:
                    continue
                eintrag = zwischenstand[2]
        out[eintrag["fallgruppe_id"]] = eintrag
    return out
