"""The generic rule engine — contract §2 aggregation, §5 check result.

No Prüfpunkt is named anywhere in this file. It walks whatever tree the schema
declares, evaluates whatever conditions the schema wrote, and aggregates by
whatever roles the schema says count. A second Fallgruppe is a second JSON
file, and a Jurist-Edit is a text edit — both claims hold literally because
this module refuses to know anything specific.

Order of operations matters and is not arbitrary:

  1. Annahmen fill gaps that the schema declares safe to assume (always
     displayed as „angenommen", never silently).
  2. Gates run first — one of them can stop the schema outright, another can
     deactivate a whole Stufe. A Prüfpunkt that a gate switched off must never
     be evaluated, let alone counted.
  3. tragend + ergaenzend Prüfpunkte.
  4. Aggregation → Einordnung.
  5. Ableitungen last, because their `nur_wenn` reads the Einordnung.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from fallpruefer import zeit
from fallpruefer.fall import (
    Betragangabe,
    Fall,
    FehlendesElement,
    Fristangabe,
    Pruefergebnis,
    Pruefung,
    Quellenangabe,
)
from fallpruefer.normbasis import normbasis
from fallpruefer.primitiven import PRIMITIVE
from fallpruefer.regeln import auswerten as bedingung_auswerten
from fallpruefer.schema import Knoten, Pruefpunkt, Schema
from fallpruefer.soll import SollErgebnis, auswerten as soll_auswerten
from fallpruefer.vokabular import (
    Badge,
    Dokumenttyp,
    Einordnung,
    Fehlzustand,
    Herkunft,
    Quelle,
    Rolle,
    Typ,
    Zustand,
    schlimmste_herkunft,
    schlimmster_badge,
)

_PLATZHALTER = re.compile(r"\{([a-zA-Z0-9_.]+)\}")
_AUSDRUCK = re.compile(r"^([a-z_]+)\((.*)\)$")


# --------------------------------------------------------------------------
# the context every condition and primitive sees
# --------------------------------------------------------------------------


@dataclass
class Fallkontext:
    fall: Fall
    schema: Schema
    extra: dict[str, Any] = field(default_factory=dict)
    parameter_block: dict | None = None
    # dokumenttyp -> dok_id, for types where several versions can be on file
    # and one of them governs. Which one governs is a Soll question (`soll.py`);
    # the engine only honours the answer.
    relevante_dokumente: dict[str, str] = field(default_factory=dict)

    # -- fact lookup --------------------------------------------------------

    def _faktum(self, name: str):
        kandidaten = [f for f in self.fall.fakten if f.feld_id == name]
        if not kandidaten:
            return None
        massgeblich = self.relevante_dokumente.get(name.split(".", 1)[0])
        if massgeblich:
            passend = [f for f in kandidaten if f.dok_id == massgeblich]
            if passend:
                return passend[-1]
        return kandidaten[-1]

    def feld(self, name: str) -> Any:
        if name in self.extra:
            return self.extra[name]
        if name == "heute":
            # A Frist that runs against the calendar needs the calendar. It
            # goes through `zeit.heute()` like every other displayed date, so
            # `stichtag_modus: demo` pins it with everything else — a rule that
            # read the wall clock directly would be the one date on screen that
            # disagrees with the rest of the Fallakte.
            #
            # Not decoration: `schemas/inkasso.json` P6 (Widerrufsfrist) is the
            # first rule that measures against today, and without this the
            # argument resolved to None, the JA arm went null, and the point
            # fell through to `sonst: NEIN` — „die Frist ist abgelaufen", in
            # every case. A wrong answer, not a missing one.
            return zeit.heute()
        if name.startswith(("pruefpunkt.", "berechnung.")):
            return None
        if name.endswith(".vorhanden"):
            return self.dok_vorhanden(name.rsplit(".", 1)[0])
        f = self._faktum(name)
        if f is None or f.verifiziert is False:
            return None
        return f.wert

    def datum(self, name: str) -> date | None:
        return zeit.parse_datum(self.feld(name))

    def verifiziert(self, name: str) -> bool:
        f = self._faktum(name)
        return bool(f and f.verifiziert is not False and f.wert is not None)

    def herkunft(self, name: str) -> Herkunft | None:
        f = self._faktum(name)
        return f.herkunft if f else None

    def badge(self, name: str) -> Badge | None:
        f = self._faktum(name)
        return f.badge if f else None

    def quelle(self, name: str) -> Quellenangabe | None:
        f = self._faktum(name)
        return f.quelle if f else None

    def dok_vorhanden(self, typ: str) -> bool:
        try:
            dt = Dokumenttyp(typ)
        except ValueError:
            return False
        return bool(self.fall.dokumente_vom_typ(dt))

    def dok_existiert_nicht(self, typ: str) -> bool:
        """V-G1: die Verbraucherin hat gesagt, dieses Dokument gab es nie —
        `fall.nicht_vorhanden`, nicht zurückgezogen. Ein Dokument, das trotzdem
        in der Akte liegt, schlägt die Aussage."""
        try:
            dt = Dokumenttyp(typ)
        except ValueError:
            return False
        if self.fall.dokumente_vom_typ(dt):
            return False
        return any(n.dokumenttyp == dt and not n.zurueckgezogen for n in self.fall.nicht_vorhanden)

    def dok_text(self, typ: str) -> str:
        try:
            dt = Dokumenttyp(typ)
        except ValueError:
            return ""
        return "\n".join(d.text_pseudonym or d.text_original for d in self.fall.dokumente_vom_typ(dt))

    def parameter(self, name: str) -> Any:
        return (self.parameter_block or {}).get(name)

    def fundstellen_treffer(self, fundstellen: list[str]) -> list[tuple[str, bool]]:
        return normbasis().treffer(fundstellen)

    # -- display ------------------------------------------------------------

    def anzeige(self, feld_id: str) -> str:
        wert = self.feld(feld_id)
        return formatieren(wert, self.schema, feld_id)


def formatieren(wert: Any, schema: Schema | None = None, feld_id: str | None = None) -> str:
    """Render a fact for a human. Dates German, amounts German, bools words."""
    if wert is None:
        return "—"
    if isinstance(wert, bool):
        return "ja" if wert else "nein"
    if isinstance(wert, date):
        return zeit.datum_de(wert)
    if isinstance(wert, list):
        return ", ".join(formatieren(w) for w in wert) if wert else "—"
    spec = schema.dokumenten_soll.feld(feld_id) if (schema and feld_id) else None
    if spec and spec.wert_labels and isinstance(wert, str):
        # V-23 — vor allen typ-Zweigen, weil ein Enum-Wert sonst als str
        # durchfaellt und als Code auf dem Schirm landet
        return spec.wert_labels.get(wert, wert)
    if spec and spec.typ == "betrag":
        return zeit.betrag_de(wert)
    if spec and spec.typ == "datum":
        return zeit.datum_de(wert)
    if spec and spec.typ == "zahl":
        return f"{wert:g}"
    if isinstance(wert, float):
        return zeit.betrag_de(wert)
    return str(wert)


def satz(vorlage: str | list | None, k: Fallkontext, zitat: str = "") -> str:
    """Substitute `{feld_id}` (and `{zitat}`) into a schema sentence.

    V-F2: `vorlage` may be a list of arms `[{"wenn": …, "satz": …}]` — one
    sentence per arm of a Prüfpunkt, because a point with two NEIN-arms
    (P8: Fiktion ohne Frist/Hinweis · Widerspruchsfrist zu kurz) cannot be
    explained by one sentence without lying about one of them. The first arm
    whose `wenn` holds speaks; an arm without `wenn` is the fallback."""
    if isinstance(vorlage, list):
        vorlage = _arm_waehlen(vorlage, k)
    if not vorlage:
        return ""

    def ersetzen(m: re.Match) -> str:
        name = m.group(1)
        if name == "zitat":
            return zitat
        if name in k.extra:
            return formatieren(k.extra[name])
        return k.anzeige(name)

    return _PLATZHALTER.sub(ersetzen, vorlage)


def _arm_waehlen(arme: list, k: Fallkontext) -> str | None:
    rest = None
    for arm in arme:
        if not isinstance(arm, dict):
            continue
        if arm.get("wenn") is None:
            rest = rest or arm.get("satz")
            continue
        try:
            if bedingung_auswerten(arm["wenn"], k) is True:
                return arm.get("satz")
        except Exception:  # noqa: BLE001 — ein kaputter Arm schweigt, der Rest spricht
            continue
    return rest


# --------------------------------------------------------------------------
# Annahmen
# --------------------------------------------------------------------------


def annahmen_anwenden(fall: Fall, schema: Schema, k: Fallkontext) -> None:
    """Fill a declared gap — and label it. `annahmen[]` is law-student
    territory: the engine only executes what the schema says is safe."""
    from fallpruefer.fall import Faktum

    for a in schema.annahmen:
        if k.feld(a.feld) is not None:
            continue
        wert: Any = a.wert
        if isinstance(a.wert, str) and (m := _AUSDRUCK.match(a.wert.strip())):
            name, roh_args = m.group(1), m.group(2)
            if name not in PRIMITIVE:
                continue
            teile = [t.strip() for t in roh_args.split(",") if t.strip()]
            args: dict[str, Any] = {}
            if teile:
                args["feld"] = teile[0]
            if len(teile) > 1:
                args["tage"] = int(teile[1]) if teile[1].lstrip("-").isdigit() else teile[1]
            wert = PRIMITIVE[name](k, args)
        if wert is None:
            continue
        fall.fakten.append(Faktum(
            feld_id=a.feld, wert=wert, herkunft=Herkunft.ANGENOMMEN,
            annahme_id=a.id, badge=Badge.ANGENOMMEN, verifiziert=None,
        ))


# --------------------------------------------------------------------------
# one Prüfpunkt
# --------------------------------------------------------------------------

_REIHENFOLGE = [
    ("FEHLT_wenn", Zustand.FEHLT),
    ("NEIN_wenn", Zustand.NEIN),
    ("WERTUNG_wenn", Zustand.WERTUNG),
    ("JA_wenn", Zustand.JA),
]


def _pflichteingaben_fehlen(p: Pruefpunkt, k: Fallkontext) -> list[str]:
    fehlend: list[str] = []
    for e in p.eingaben:
        if not e.pflicht:
            continue
        if not any(k.verifiziert(f) for f in e.felder):
            fehlend.append(e.feld)
    return fehlend


def _felder_der_bedingung(bedingung) -> list[str]:
    """Die Feld-IDs, die eine `FEHLT_wenn`-Bedingung über `fehlt` oder
    `verifiziert` benennt, in Reihenfolge, ohne Dubletten. `dok_fehlt` nennt
    einen Dokumenttyp, kein Feld — den meldet der Punkt über `fehlt_owner`."""
    aus: list[str] = []

    def gehen(b) -> None:
        if isinstance(b, dict):
            for k_, v in b.items():
                if k_ in ("fehlt", "verifiziert") and isinstance(v, str) and v not in aus:
                    aus.append(v)
                elif k_ in ("alle", "eine"):
                    for c in v or []:
                        gehen(c)
                elif k_ == "nicht":
                    gehen(v)
    gehen(bedingung)
    return aus


def pruefpunkt_auswerten(p: Pruefpunkt, k: Fallkontext, schema: Schema) -> Pruefergebnis:
    k.parameter_block = p.parameter
    zustand: Zustand | None = None

    regel = p.regel or {}
    for schluessel, kandidat in _REIHENFOLGE:
        if schluessel in regel and bedingung_auswerten(regel[schluessel], k) is True:
            zustand = kandidat
            break

    fehlend: list[str] = []
    if zustand is None:
        fehlend = _pflichteingaben_fehlen(p, k)
        if fehlend:
            zustand = Zustand.FEHLT
        else:
            zustand = Zustand(regel.get("sonst", "JA"))

    if zustand == Zustand.FEHLT and not fehlend:
        # V-F1: ein FEHLT aus `FEHLT_wenn` meldet nur, was die Bedingung selbst
        # vermisst — nicht jede abwesende optionale Eingabe des Punkts. Sonst
        # fordert eine gerissene Kreuzprüfung (P2 im Störfall) einen Vertrag
        # nach, der als D3 in der Akte liegt. Pflichteingaben zuerst; dann die
        # Felder, die die Bedingung mit `fehlt`/`verifiziert` benennt; ein
        # `.vorhanden`-Feld auf False zählt weiterhin als fehlend.
        benannt = _felder_der_bedingung(regel.get("FEHLT_wenn"))
        fehlend = _pflichteingaben_fehlen(p, k) or [
            e.feld for e in p.eingaben
            if (e.feld in benannt and k.feld(e.feld) is None)
            or (e.feld.endswith(".vorhanden") and k.feld(e.feld) is False)
        ]

    erg = _ergebnis_bauen(p, k, schema, zustand, fehlend)
    k.parameter_block = None
    return erg


def _ergebnis_bauen(
    p: Pruefpunkt, k: Fallkontext, schema: Schema, zustand: Zustand, fehlend: list[str]
) -> Pruefergebnis:
    verwendet: list[str] = []
    strittige: list[str] = []
    zitate: list[Quellenangabe] = []
    badges: list[Badge] = []
    herkuenfte: list[Herkunft] = []

    for e in p.eingaben:
        for feld in e.felder:
            if k.feld(feld) is None:
                # A field that is merely absent contributes nothing. A field
                # whose fact exists but was *rejected* — two verified quotes
                # contradicting each other — has to reach the trace anyway:
                # otherwise the row says „fehlt" in a neutral chip and the
                # reason the input could not be used is nowhere on screen.
                widerspruch = k._faktum(feld)
                if widerspruch is not None and widerspruch.verifiziert is False:
                    if h := widerspruch.herkunft:
                        herkuenfte.append(h)
                    if b := widerspruch.badge:
                        badges.append(b)
                    # …and name it. The badge alone says „something here is
                    # contradicted"; only the feld_id says *what*, and the
                    # advisor has to resolve exactly that at Gate 3.
                    seiten = [f for f in k.fall.fakten
                              if f.feld_id == feld and f.herkunft == Herkunft.STRITTIG]
                    if len(seiten) > 1 and feld not in strittige:
                        strittige.append(feld)
                continue
            verwendet.append(feld)
            if (q := k.quelle(feld)) and q not in zitate:
                zitate.append(q)
            if b := k.badge(feld):
                badges.append(b)
            if h := k.herkunft(feld):
                herkuenfte.append(h)
            break

    erstes_zitat = zitate[0].zitat_pseudonym if zitate else ""

    if zustand == Zustand.JA:
        grund = satz(p.satz_ja, k, erstes_zitat) or p.proposition
    elif zustand == Zustand.NEIN:
        grund = satz(p.satz_nein, k, erstes_zitat) or satz(p.plain_grund, k, erstes_zitat) or p.proposition
    elif zustand == Zustand.WERTUNG:
        grund = satz(p.wertungsfrage, k, erstes_zitat) or p.proposition
    elif zustand == Zustand.FEHLT:
        grund = satz(p.fehlt_text, k, erstes_zitat) or _fehlt_satz(fehlend, schema)
    else:
        grund = ""

    owner = p.fehlt_owner
    if zustand == Zustand.FEHLT and owner is None and fehlend:
        owner = schema.dokumenten_soll.besitzer(fehlend[0])

    # Ein Befund, den die Beraterin prüfen soll, existiert nur, wenn das Modell
    # etwas gelesen hat. Steht der Punkt auf FEHLT, gibt es nichts zu prüfen —
    # das Badge wäre eine Aufforderung ins Leere (Team-Rückfrage 25 Aug).
    llm_befund = p.typ == Typ.TEXT and zustand != Zustand.FEHLT
    if llm_befund:
        badges.append(Badge.LLM_BEFUND)
    badge = schlimmster_badge(badges) if badges else None

    return Pruefergebnis(
        pruefpunkt_id=p.id,
        zustand=zustand,
        grund=grund,
        verwendet=verwendet,
        strittige_felder=strittige,
        zitate=zitate,
        anker=[a["key"] for a in p.anker if a.get("key")],
        missing=fehlend,
        owner=owner,
        # F2, zwei Haelften. (a) Interpolieren wie beim `grund` oben — ohne das
        # stand `{gespraech.monate_erhoeht_gezahlt}` als roher Token in **allen
        # drei** Fixtures auf dem Schirm. (b) Nur tragen, wo die Frage auch
        # offen ist: eine Wertungsfrage an einem JA-Punkt ist keine Frage, und
        # `Pruefpfad.tsx` rendert sie zustandsunabhaengig — bei JA ohne Antwort
        # ergaebe die Interpolation „hat — Monate gezahlt".
        wertungsfrage=(
            satz(p.wertungsfrage, k, erstes_zitat) or None
            if zustand in (Zustand.WERTUNG, Zustand.FEHLT, Zustand.INAKTIV)
            else None
        ),
        llm_befund=llm_befund,
        badge=badge,
        herkunft=schlimmste_herkunft(herkuenfte),
        frist=_frist(p, k),
        betrag=_betrag(p, k),
    )


def _fehlt_satz(fehlend: list[str], schema: Schema) -> str:
    namen = [_lesbar(f, schema) for f in fehlend]
    return "Es fehlt: " + ", ".join(namen) if namen else "Es fehlt eine Angabe."


def _lesbar(feld_oder_typ: str, schema: Schema) -> str:
    """Name a missing input the way the advisor would say it."""
    # `<typ>.vorhanden` is about the document itself, not a field in it
    if feld_oder_typ.endswith(".vorhanden"):
        feld_oder_typ = feld_oder_typ.rsplit(".", 1)[0]
    sd = None
    typ = feld_oder_typ.split(".", 1)[0]
    for d in schema.dokumenten_soll.dokumente:
        if d.dokumenttyp.value == typ:
            sd = d
            break
    if "." not in feld_oder_typ:
        return sd.anzeigename if sd else feld_oder_typ
    spec = schema.dokumenten_soll.feld(feld_oder_typ)
    if spec and spec.beschreibung:
        return spec.beschreibung
    # R5: nie die feld_id — „Erhöhungsschreiben (grundlage_genannt)" stand so
    # in der Einordnung. Das Dokument bleibt genannt, weil die Lücke mit einem
    # Papier geschlossen wird, nicht mit einem Feld.
    if sd and spec and spec.label:
        return f"{sd.anzeigename}: {spec.label}"
    if spec and spec.label:
        return spec.label
    if sd:
        return f"{sd.anzeigename} ({feld_oder_typ.split('.', 1)[1]})"
    return feld_oder_typ


def _plural(typ: str, schema: Schema) -> bool:
    """„die AGB … liegen vor" vs. „der Vertrag … liegt vor" — der Anzeigename
    trägt den Artikel, und der sagt die Zahl."""
    name = _lesbar(typ, schema).strip().lower()
    return name.startswith("die agb") or name.startswith("die unterlagen")


def _lesbare_luecken(eintraege: list[FehlendesElement], schema: Schema) -> list[str]:
    """Name gaps the way an advisor would say them out loud.

    One entry per document, because that is how the gap will be closed — the
    consumer sends a paper, not a field. A document that never arrived is named
    by its `anzeigename`; a document that is on file but has several required
    fields unfound is named „… — liegt vor, aber unvollständig", which is the distinction
    Franz' Fall 3 turns on („nicht Unterlage fehlt, sondern Unterlage
    unvollständig"); a single missing field is named as itself, so the precise
    case („die Seite mit Ziffer 5.2") does not get blurred into the general one.
    """
    gruppen: dict[str, list[FehlendesElement]] = {}
    einzeln: list[FehlendesElement] = []
    for e in eintraege:
        if e.dokumenttyp:
            gruppen.setdefault(e.dokumenttyp.value, []).append(e)
        else:
            einzeln.append(e)

    namen: list[str] = []

    def hinzu(name: str) -> None:
        if name and name not in namen:
            namen.append(name)

    for typ, gruppe in gruppen.items():
        if any(e.feld_id is None for e in gruppe):
            hinzu(_lesbar(typ, schema))          # the document never arrived
        elif len(gruppe) > 1:
            # V-29: „(unvollständig)" in Klammern liest sich nicht vor — der
            # Satz muss laut gesagt werden können. Die Unterscheidung bleibt
            # (Franz' Fall 3: nicht „Unterlage fehlt", sondern „liegt vor, aber
            # unvollständig"), nur als Nebensatz statt als Klammer.
            hinzu(f"{_lesbar(typ, schema)} — liegen vor, aber unvollständig"
                  if _plural(typ, schema) else
                  f"{_lesbar(typ, schema)} — liegt vor, aber unvollständig")
        else:
            hinzu(_lesbar(gruppe[0].feld_id, schema))
    for e in einzeln:
        if e.feld_id:
            hinzu(_lesbar(e.feld_id, schema))
    return namen


def _frist(p: Pruefpunkt, k: Fallkontext) -> Fristangabe | None:
    if not p.frist:
        return None
    name = p.frist.get("prim")
    if name not in PRIMITIVE:
        return None
    wert = PRIMITIVE[name](k, p.frist.get("args") or {})
    if wert is None:
        return None
    anzeige = (p.frist.get("anzeige") or "{wert}").replace("{wert}", str(wert))
    anzeige = anzeige.replace("{stichtag}", zeit.datum_de(zeit.heute()))
    annahmen = [
        a.anzeige for a in k.schema.annahmen
        if any(a.feld == arg for arg in (p.frist.get("args") or {}).values())
    ]
    return Fristangabe(
        name=p.frist.get("name", "Frist"), wert=anzeige,
        stand=zeit.heute().isoformat(), annahmen=annahmen,
    )


def _betrag(p: Pruefpunkt, k: Fallkontext) -> Betragangabe | None:
    if not p.betrag:
        return None
    roh = None
    if p.berechnung and (name := p.berechnung.get("prim")) in PRIMITIVE:
        roh = PRIMITIVE[name](k, p.berechnung.get("args") or {})
    name = p.betrag.get("name", "Betrag")
    if roh is None:
        return Betragangabe(
            name=name, wert="noch nicht berechenbar", roh=None,
            annahmen=["die Grundlage dafür liegt noch nicht vor"],
        )
    anzeige = (p.betrag.get("anzeige") or "{betrag}").replace("{betrag}", f"{roh:.2f}".replace(".", ","))
    return Betragangabe(name=name, wert=satz(anzeige, k), roh=roh)


# --------------------------------------------------------------------------
# tree aggregation
# --------------------------------------------------------------------------


def _knoten_zustand(
    knoten: Knoten, ergebnisse: dict[str, Pruefergebnis], schema: Schema,
    zustaende: dict[str, Zustand],
) -> Zustand:
    aktive: list[Zustand] = []
    for kind in knoten.kinder:
        if isinstance(kind, str):
            pp = schema.pruefpunkt(kind)
            erg = ergebnisse.get(kind)
            if pp is None or erg is None or pp.rolle not in schema.nur_rolle:
                continue
            if erg.zustand == Zustand.INAKTIV:
                continue
            aktive.append(erg.zustand)
        else:
            z = _knoten_zustand(kind, ergebnisse, schema, zustaende)
            if z != Zustand.INAKTIV:
                aktive.append(z)

    if not aktive:
        z = Zustand.INAKTIV
    elif knoten.op.upper() == "OR":
        z = (Zustand.JA if Zustand.JA in aktive
             else Zustand.WERTUNG if Zustand.WERTUNG in aktive
             else Zustand.FEHLT if Zustand.FEHLT in aktive
             else Zustand.NEIN)
    else:
        z = (Zustand.NEIN if Zustand.NEIN in aktive
             else Zustand.FEHLT if Zustand.FEHLT in aktive
             else Zustand.WERTUNG if Zustand.WERTUNG in aktive
             else Zustand.JA)
    zustaende[knoten.id] = z
    return z


# --------------------------------------------------------------------------
# the run
# --------------------------------------------------------------------------


def pruefen(fall: Fall, schema: Schema, trigger: str = "initial", run_nr: int | None = None) -> Pruefung:
    k = Fallkontext(fall=fall, schema=schema)
    annahmen_anwenden(fall, schema, k)
    soll = soll_auswerten(fall, schema, k)
    k.relevante_dokumente = soll.massgebliche_dokumente()

    ergebnisse: dict[str, Pruefergebnis] = {}
    deaktiviert: dict[str, str] = {}
    stopp_text: str | None = None
    gates_offen: list[Pruefergebnis] = []

    # 1) gates — they decide what the rest of the schema is even allowed to say
    for p in schema.pruefpunkte:
        if p.rolle == Rolle.GATE:
            ergebnisse[p.id] = pruefpunkt_auswerten(p, k, schema)

    # Gate 3 reaches the gates too. „Das ist hier gar kein Fall dieses Schemas"
    # has to move the schema, not just recolour one chip — so an override that
    # targets a gate is applied *before* `bei_NEIN` is read. At this point
    # `ergebnisse` holds nothing but gates, so this pass can only touch them;
    # every other Prüfpunkt is still overridden after step 2, as before.
    _overrides_anwenden(fall, ergebnisse, schema, k)

    for p in schema.pruefpunkte:
        if p.rolle != Rolle.GATE:
            continue
        erg = ergebnisse[p.id]
        if erg.zustand == Zustand.NEIN and p.bei_NEIN:
            if p.bei_NEIN.get("schema_stopp"):
                stopp_text = p.bei_NEIN.get("text", "")
            for pid in p.bei_NEIN.get("deaktiviert", []):
                deaktiviert[pid] = p.bei_NEIN.get("text", "")
        elif erg.zustand in (Zustand.FEHLT, Zustand.WERTUNG):
            # A gate asks a Vorfrage — „gilt dieses Schema hier überhaupt?",
            # „ist die Klausel kontrollfähig?". Left unanswered it must not
            # collapse into „kein Problem", which is the rule the three-valued
            # grammar applies everywhere else (module docstring) and the one
            # place it was not applied. It only downgrades a *hard* verdict:
            # a case that is already „unklar" names the document the advisor
            # has to request, and that is the more useful sentence.
            gates_offen.append(erg)

    # 1b) V-G1 — tragende Punkte, die andere abschalten dürfen („ohne Erklärung
    # entfällt der Rechtsgrund", P1a): sie laufen vor dem Rest, damit ihr
    # `bei_NEIN.deaktiviert` greift wie das eines Gates. `schema_stopp` bleibt
    # den Gates vorbehalten. Ein solcher Punkt bleibt tragend — sein NEIN
    # reißt die Stufe und trägt die Einordnung, ein Gate täte das nicht.
    for p in schema.pruefpunkte:
        if p.rolle == Rolle.GATE or not (p.bei_NEIN or {}).get("deaktiviert"):
            continue
        if p.id in deaktiviert:
            continue
        erg = pruefpunkt_auswerten(p, k, schema)
        ergebnisse[p.id] = erg
        if erg.zustand == Zustand.NEIN:
            for pid in p.bei_NEIN.get("deaktiviert", []):
                deaktiviert[pid] = p.bei_NEIN.get("text", "")
                # ein schon gelaufenes Gate (P0) wird ebenfalls gegenstandslos —
                # sonst hielte seine offene Vorfrage das Urteil auf „unklar"
                if pid in ergebnisse:
                    gates_offen[:] = [g for g in gates_offen if g.pruefpunkt_id != pid]
                    ergebnisse[pid] = Pruefergebnis(
                        pruefpunkt_id=pid, zustand=Zustand.INAKTIV,
                        grund=deaktiviert[pid], inaktiv_grund=deaktiviert[pid],
                        herkunft=Herkunft.FEHLT,
                    )

    # 2) the Prüfpunkte that carry the Einordnung, plus the ergänzende ones
    for p in schema.pruefpunkte:
        if p.rolle in (Rolle.GATE, Rolle.ABLEITUNG, Rolle.STRATEGIE) or p.id in ergebnisse:
            continue
        if p.id in deaktiviert:
            ergebnisse[p.id] = Pruefergebnis(
                pruefpunkt_id=p.id, zustand=Zustand.INAKTIV,
                grund=deaktiviert[p.id], inaktiv_grund=deaktiviert[p.id],
                wertungsfrage=satz(p.wertungsfrage, k, "") or None,
                herkunft=Herkunft.FEHLT,
            )
            continue
        ergebnisse[p.id] = pruefpunkt_auswerten(p, k, schema)

    _overrides_anwenden(fall, ergebnisse, schema, k)

    # 3) aggregate
    zustaende: dict[str, Zustand] = {}
    wurzel = _knoten_zustand(schema.baum, ergebnisse, schema, zustaende) if schema.baum else Zustand.INAKTIV
    zustaende["root"] = wurzel

    gerissene = _gerissene_stufe(schema, zustaende)
    vollstaendigkeit = _vollstaendigkeit(soll, ergebnisse, schema)
    einordnung_code, einordnung_text = _einordnung(
        wurzel, ergebnisse, schema, stopp_text, vollstaendigkeit, gates_offen
    )

    # 4) Ableitungen — their `nur_wenn` reads the Einordnung, so they run last
    k.extra.update({
        "einordnung": einordnung_code.value if einordnung_code else None,
        "gerissene_stufe": gerissene,
        "fehlt_unternehmen": [f.dokumenttyp.value if f.dokumenttyp else f.feld_id
                              for f in vollstaendigkeit.get("unternehmen", [])],
        "fehlt_verbraucher": [f.dokumenttyp.value if f.dokumenttyp else f.feld_id
                              for f in vollstaendigkeit.get("verbraucher", [])],
    })
    if einordnung_code:
        # the *rendered* verdict is what the remedy conditions compare against
        k.extra["einordnung"] = _basis_label(einordnung_code)

    for p in schema.pruefpunkte:
        if p.rolle not in (Rolle.ABLEITUNG, Rolle.STRATEGIE):
            continue
        if p.rolle == Rolle.STRATEGIE and not p.regel:
            ergebnisse[p.id] = Pruefergebnis(
                pruefpunkt_id=p.id, zustand=Zustand.INAKTIV, herkunft=Herkunft.FEHLT,
                grund="Wird im Gesprächsleitfaden gefragt.",
                inaktiv_grund=None,
            )
            continue
        if p.nur_wenn is not None and bedingung_auswerten(p.nur_wenn, k) is not True:
            ergebnisse[p.id] = Pruefergebnis(
                pruefpunkt_id=p.id, zustand=Zustand.INAKTIV, herkunft=Herkunft.FEHLT,
                grund="Diese Ableitung greift bei dieser Einordnung nicht.",
                inaktiv_grund="greift bei dieser Einordnung nicht",
            )
            continue
        erg = pruefpunkt_auswerten(p, k, schema) if p.regel else _ableitung(p, k, schema)
        ergebnisse[p.id] = erg

    reihenfolge = [p.id for p in schema.pruefpunkte]
    nummer = run_nr if run_nr is not None else len(fall.pruefungen) + 1

    return Pruefung(
        run_id=f"R-{nummer}",
        trigger=trigger,
        zeit=zeit.jetzt(),
        schema_version=schema.version,
        schema_stand=schema.stand,
        ergebnisse=[ergebnisse[pid] for pid in reihenfolge if pid in ergebnisse],
        baum_zustaende=zustaende,
        einordnung=einordnung_text,
        einordnung_code=einordnung_code,
        vollstaendigkeit=vollstaendigkeit,
        gerissene_stufe=gerissene,
        pruefumfang=_pruefumfang(ergebnisse, schema),
        plain=_plain(einordnung_code, ergebnisse, schema, gerissene, vollstaendigkeit, k),
        schema_stopp_text=stopp_text,
    )


def _ableitung(p: Pruefpunkt, k: Fallkontext, schema: Schema) -> Pruefergebnis:
    erg = _ergebnis_bauen(p, k, schema, Zustand.JA, [])
    erg.grund = satz(p.satz_ja, k) or p.proposition or p.titel
    if erg.betrag:
        erg.grund = f"{erg.grund} — {erg.betrag.name}: {erg.betrag.wert}"
    return erg


def _overrides_anwenden(fall: Fall, ergebnisse: dict[str, Pruefergebnis], schema: Schema, k: Fallkontext) -> None:
    """Gate 3. An override persists across later runs unless withdrawn — the
    advisor should not have to re-decide the same question after a Nachreichung."""
    for o in fall.overrides:
        if o.zurueckgezogen or o.pruefpunkt_id not in ergebnisse:
            continue
        erg = ergebnisse[o.pruefpunkt_id]
        erg.zustand = o.neuer_zustand
        erg.grund = o.grund
        erg.herkunft = Herkunft.OVERRIDE
        erg.override = True


def _gerissene_stufe(schema: Schema, zustaende: dict[str, Zustand]) -> str | None:
    if not schema.baum:
        return None
    for kind in schema.baum.kinder:
        if isinstance(kind, str):
            continue
        if zustaende.get(kind.id) == Zustand.NEIN:
            return kind.id
    return None


def _basis_label(code: Einordnung) -> str:
    from fallpruefer.vokabular import label

    return label(code)


def _gate_luecke(gates: list[Pruefergebnis], schema: Schema) -> str:
    """Name what an unanswered gate still needs, the way the advisor would."""
    namen: list[str] = []
    for erg in gates:
        if erg.zustand == Zustand.WERTUNG and erg.wertungsfrage:
            eintrag = f"Bewertung durch die Beraterin zu „{erg.wertungsfrage}“"
        else:
            eintrag = ", ".join(_lesbar(m, schema) for m in erg.missing)
        if eintrag and eintrag not in namen:
            namen.append(eintrag)
    return " · ".join(namen)


def _einordnung(
    wurzel: Zustand, ergebnisse: dict[str, Pruefergebnis], schema: Schema, stopp_text: str | None,
    vollstaendigkeit: dict[str, list[FehlendesElement]] | None = None,
    gates_offen: list[Pruefergebnis] | None = None,
) -> tuple[Einordnung | None, str]:
    if stopp_text:
        return None, stopp_text
    if wurzel in (Zustand.NEIN, Zustand.JA) and gates_offen:
        # The Vorfrage is still open, so neither hard answer can be given: if a
        # gate turns out NEIN the schema stops or the Inhaltskontrolle falls
        # away, and the Prüfpunkte underneath it become moot. Downgrade to
        # „unklar" and name the gate's own gap — never the other way round.
        luecke = _gate_luecke(gates_offen, schema)
        return Einordnung.UNKLAR, "unklar – es fehlt: " + (luecke or "eine Vorfrage")
    if wurzel == Zustand.NEIN:
        return Einordnung.WAHRSCHEINLICH_UNWIRKSAM, "wahrscheinlich unwirksam"
    if wurzel == Zustand.JA:
        return Einordnung.WIRKSAM, "wirksam"
    if wurzel == Zustand.FEHLT:
        # „unklar – es fehlt: <named inputs, grouped by owner>" (14 §5). What
        # belongs in the verdict is what the verdict actually turned on: gaps
        # under a *tragend* Prüfpunkt, plus consumer documents that never
        # arrived. A company-side `pflicht: hinweis` item is always open by
        # design and would otherwise stand in every unklar verdict forever.
        je_owner: dict[str, list[FehlendesElement]] = {"verbraucher": [], "unternehmen": []}
        for owner, liste in (vollstaendigkeit or {}).items():
            for e in liste:
                pp = schema.pruefpunkt(e.pruefpunkt_id) if e.pruefpunkt_id else None
                tragend = pp is not None and pp.rolle in schema.nur_rolle
                if tragend or (e.pruefpunkt_id is None and owner == "verbraucher"):
                    je_owner.setdefault(owner, []).append(e)

        vom_verbraucher = _lesbare_luecken(je_owner.get("verbraucher", []), schema)
        vom_unternehmen = _lesbare_luecken(je_owner.get("unternehmen", []), schema)
        teile = [", ".join(vom_verbraucher)] if vom_verbraucher else []
        if vom_unternehmen:
            teile.append("vom Unternehmen: " + ", ".join(vom_unternehmen))
        return Einordnung.UNKLAR, "unklar – es fehlt: " + (" · ".join(teile) or "eine Angabe")
    if wurzel == Zustand.WERTUNG:
        fragen: list[str] = []
        for erg in ergebnisse.values():
            pp = schema.pruefpunkt(erg.pruefpunkt_id)
            if erg.zustand != Zustand.WERTUNG or not pp or pp.rolle not in schema.nur_rolle:
                continue
            if erg.wertungsfrage and erg.wertungsfrage not in fragen:
                fragen.append(erg.wertungsfrage)
        frage = fragen[0] if fragen else "der offenen Bewertungsfrage"
        return Einordnung.UNKLAR, f"unklar – es fehlt: Bewertung durch die Beraterin zu „{frage}“"
    if not any(p.rolle in schema.nur_rolle for p in schema.pruefpunkte):
        # Stufe B/C: the Fallgruppe is known and its Dokumenten-Soll runs, but
        # no Prüfschema is on file. „unklar – es fehlt: eine anwendbare Prüfung"
        # reads as a finding about the case; there is none. The view falls back
        # to the Stufe limitation sentence (14 §2), which is the honest one.
        return None, ""
    # a tragend Prüfpunkt exists but every one of them is INAKTIV
    return Einordnung.UNKLAR, "unklar – es fehlt: eine anwendbare Prüfung"


def _vollstaendigkeit(
    soll: SollErgebnis, ergebnisse: dict[str, Pruefergebnis], schema: Schema
) -> dict[str, list[FehlendesElement]]:
    """Independent of the Einordnung (contract §2): every FEHLT across *all*
    Prüfpunkte including ergaenzend, plus required documents that never made it
    to a Prüfpunkt — grouped by who has to supply them."""
    aus: dict[str, list[FehlendesElement]] = {"verbraucher": [], "unternehmen": []}
    gesehen: set[tuple] = set()

    def hinzu(el: FehlendesElement) -> None:
        if el.feld_id and el.feld_id.endswith(".vorhanden"):
            el.feld_id = None  # this is the document, not a field inside it
        # V-N2: ein Feld aus einem Dokument, das es nach Feststellung der
        # Beraterin nie gab, wandert mit dem Dokument auf die
        # Unternehmensseite. Ohne das hier bliebe die Nachforderung bestehen —
        # nur eine Ebene tiefer und deshalb unsichtbarer: das Dokument stuende
        # richtig beim Unternehmen und `vertrag.datum` weiter beim Verbraucher.
        if el.dokumenttyp in soll.nie_vorhanden:
            el.quelle = Quelle.UNTERNEHMEN
            el.fehlzustand = Fehlzustand.EXISTIERT_NICHT
        schluessel = (el.dokumenttyp, el.feld_id, el.quelle)
        if schluessel in gesehen:
            return
        gesehen.add(schluessel)
        aus[el.quelle.value].append(el)

    for el in soll.fehlt:
        hinzu(el)

    for erg in ergebnisse.values():
        if erg.zustand != Zustand.FEHLT:
            continue
        besitzer = erg.owner or Quelle.VERBRAUCHER
        for m in erg.missing:
            typ = m.split(".", 1)[0]
            try:
                dt = Dokumenttyp(typ)
            except ValueError:
                dt = None
            hinzu(FehlendesElement(
                dokumenttyp=dt,
                feld_id=m if ("." in m and not m.endswith(".vorhanden")) else None,
                quelle=besitzer,
                grund=_lesbar(m, schema),
                pruefpunkt_id=erg.pruefpunkt_id,
            ))
    return aus


def _pruefumfang(ergebnisse: dict[str, Pruefergebnis], schema: Schema) -> list[str]:
    aus: list[str] = []
    for p in schema.pruefpunkte:
        erg = ergebnisse.get(p.id)
        if not erg or erg.zustand not in (Zustand.WERTUNG, Zustand.FEHLT, Zustand.INAKTIV):
            continue
        if p.pruefumfang_text or p.wertungsfrage or erg.inaktiv_grund:
            aus.append(p.id)
    return aus


def _plain(
    code: Einordnung | None, ergebnisse: dict[str, Pruefergebnis], schema: Schema,
    gerissene: str | None, vollstaendigkeit: dict[str, list[FehlendesElement]], k: Fallkontext,
) -> list[str]:
    """The 1–3 plain-German sentences. Template from the trace, never generated
    prose (14 §5): an LLM may only polish this, and only under a no-new-facts
    check."""
    if code is None:
        return []
    vorlage = schema.plain_saetze.get(_basis_label(code), "")
    if not vorlage:
        return []
    haupt = _hauptpruefpunkt(ergebnisse, schema, gerissene)
    grund = ""
    if haupt:
        pp = schema.pruefpunkt(haupt)
        grund = satz(pp.plain_grund, k) if pp else ""
    # `grund` is an internal reason („nicht eingereicht"), not something to say
    # to a person. The plain sentence names the documents, consumer side first,
    # and falls back to the company side only when nothing is open here.
    fehlende = _lesbare_luecken(vollstaendigkeit.get("verbraucher", []), schema)
    if not fehlende:
        fehlende = _lesbare_luecken(vollstaendigkeit.get("unternehmen", []), schema)
    liste = _aufzaehlung(fehlende) if fehlende else "eine Angabe"
    text = (vorlage
            .replace("{plain_grund_hauptpruefpunkt}", grund)
            .replace("{fehlende_liste_plain}", liste))
    return [t.strip() + "" for t in [satz(text, k)] if t.strip()]


def _aufzaehlung(teile: list[str]) -> str:
    """„A, B und C" — und ein Komma vor dem „und", wenn ein Glied selbst eines
    enthält.

    Der Satz, den die Beraterin am Telefon vorliest, hieß vorher „die AGB, die
    bei Vertragsschluss galten und den Mitgliedsvertrag" — das Relativsatzkomma
    lässt das „und" wie eine Fortsetzung des Relativsatzes lesen. Die amtliche
    Regelung erlaubt das Komma vor „und" ausdrücklich, wo es der Deutlichkeit
    dient; hier tut es das.
    """
    if len(teile) <= 1:
        return teile[0] if teile else ""
    # nur, wenn das Glied **unmittelbar vor** dem „und" selbst ein Komma hat —
    # bei „A, x, B und C" ist nichts mehrdeutig, dort waere das Komma falsch
    komma = "," if "," in teile[-2] else ""
    return ", ".join(teile[:-1]) + komma + " und " + teile[-1]


def _hauptpruefpunkt(
    ergebnisse: dict[str, Pruefergebnis], schema: Schema, gerissene: str | None
) -> str | None:
    """Not defined in the contract — our rule: the first NEIN tragend Prüfpunkt
    (schema order) inside the Stufe that broke. It is the one the letter and
    the plain sentence lead with, so it must be deterministic."""
    kandidaten = [p.id for p in schema.pruefpunkte
                  if p.rolle in schema.nur_rolle
                  and ergebnisse.get(p.id)
                  and ergebnisse[p.id].zustand == Zustand.NEIN]
    if not kandidaten:
        return None
    if gerissene and schema.baum:
        for kind in schema.baum.kinder:
            if isinstance(kind, Knoten) and kind.id == gerissene:
                in_stufe = [pid for pid in kandidaten if pid in kind.kinder]
                if in_stufe:
                    return in_stufe[0]
    return kandidaten[0]
