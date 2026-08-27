"""Templates and placeholders (contract §7) — „Füllen, nicht Formulieren".

No sentence in a letter is generated. A template is fixed text plus
`[PLATZHALTER]` plus variant blocks whose conditions are ordinary rules of the
same grammar the Prüfschema uses, so which paragraphs appear is as auditable
as the verdict itself.

Two hard rules:
  * an unknown or unfillable placeholder is a **render error**, never a blank.
    A letter with a hole in it is worse than no letter.
  * Nachforderung templates may not contain legal statements — a lint blocks
    them outside the document list.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fallpruefer import zeit
from fallpruefer.konfig import WURZEL, konfig
from fallpruefer.vokabular import Briefquelle, Empfaenger

_VARIANTE = re.compile(
    r"[ \t]*<!--\s*variante:\s*([a-z0-9_]+)\s*-->\n?(.*?)\n?[ \t]*<!--\s*/variante\s*-->[ \t]*\n?",
    re.S,
)
_NACHFORDERUNG_LINT = re.compile(
    r"\b(wirksam|unwirksam|zahlen Sie|Anspruch|Widerruf)\b", re.IGNORECASE
)


class BriefFehler(RuntimeError):
    """A placeholder could not be filled, or a lint failed."""


@dataclass
class Vorlage:
    id: str
    titel: str
    koerper: str
    kopf: dict[str, Any] = field(default_factory=dict)

    @property
    def varianten(self) -> list[dict]:
        return self.kopf.get("varianten") or []

    @property
    def quelle(self) -> Briefquelle:
        return Briefquelle(self.kopf.get("quelle", "eigen"))

    @property
    def empfaenger(self) -> Empfaenger:
        return Empfaenger(self.kopf.get("empfaenger", "anbieter"))

    @property
    def geprueft(self) -> bool:
        return bool(self.kopf.get("hausstil_geprueft") and self.kopf.get("geprueft"))


def vorlage_laden(template_id: str, verzeichnis: Path | None = None) -> Vorlage:
    v = verzeichnis or (WURZEL / "templates")
    for pfad in (v / "musterbriefe" / f"{template_id}.md", v / f"{template_id}.md"):
        if pfad.exists():
            return _parsen(pfad)
    raise BriefFehler(f"Kein Template „{template_id}“ unter {v}")


def _parsen(pfad: Path) -> Vorlage:
    roh = pfad.read_text(encoding="utf-8")
    kopf: dict[str, Any] = {}
    koerper = roh
    if roh.startswith("---"):
        teile = roh.split("---", 2)
        if len(teile) >= 3:
            try:
                kopf = json.loads(teile[1])
            except json.JSONDecodeError as e:
                raise BriefFehler(f"{pfad.name}: Front matter ist kein JSON ({e})") from e
            koerper = teile[2].lstrip("\n")
    return Vorlage(
        id=kopf.get("id", pfad.stem), titel=kopf.get("titel", pfad.stem),
        koerper=koerper, kopf=kopf,
    )


# --------------------------------------------------------------------------
# placeholders
# --------------------------------------------------------------------------


def platzhalter_werte(fall, pruefung, kontext, vorlage: "Vorlage | None" = None) -> dict[str, str]:
    """The binding map of contract §7, resolved for this case.

    Identity placeholders are de-tokenised here — one of the exactly two local
    places re-identification is allowed to happen.

    `[FRIST_ENDE]` is per template, not global: the VZ house style read off the
    eight original Musterbriefe (22 §8) sets **14 days for money back** and
    **four weeks for information**, and a single config value gave the
    Auskunftsverlangen — half of the guaranteed pair in the `wirksam` branch —
    the money deadline. A template states its own `frist_tage`; the config
    value stays the default.
    """
    k = konfig()
    ident = fall.eingang.identitaet
    tage = (vorlage.kopf.get("frist_tage") if vorlage else None) or k.antwortfrist_tage
    frist_ende = zeit.tage_addieren(zeit.heute(), int(tage))

    def fakt(feld_id: str) -> str:
        """`anzeige` renders a missing fact as „—", which is right on the
        Fallakte screen and wrong in a letter: the em dash is not the empty
        string, so it slipped past the „never a blank" guard below and went out
        as „von — auf 36,90 €". In a letter a missing fact is a missing
        placeholder, and the letter is refused."""
        s = kontext.anzeige(feld_id)
        return "" if s.strip() in ("—", "-", "–") else s

    werte: dict[str, str] = {
        "[NAME]": ident.name or "",
        "[ANSCHRIFT]": ident.adresse or "",
        "[KUNDENNUMMER]": ident.kundennummer or "",
        "[ANBIETER]": fall.eingang.anbieter or "",
        "[ANBIETER_ANSCHRIFT]": fakt("erhoehungsschreiben.absender_adresse"),
        "[VERTRAGSDATUM]": fakt("vertrag.datum"),
        "[ALTER_BEITRAG]": fakt("erhoehungsschreiben.alter_betrag"),
        "[NEUER_BEITRAG]": fakt("erhoehungsschreiben.neuer_betrag"),
        "[ERHOEHUNG_AB]": fakt("erhoehungsschreiben.wirksam_ab"),
        "[SCHREIBEN_DATUM]": fakt("erhoehungsschreiben.datum"),
        "[HEUTE]": zeit.datum_de(zeit.heute()),
        "[FRIST_ENDE]": zeit.datum_de(frist_ende),
    }

    rueck = _rueckforderung(pruefung)
    if rueck is not None:
        werte["[RUECKFORDERUNG_BETRAG]"] = zeit.betrag_de(rueck)

    # The Nachforderung loop. Consumer side only — a company-side gap is an
    # Auskunftsverlangen at Gate 4 and is never asked of the consumer
    # (contract §2 `vollstaendigkeit`, 14 §4 step 3).
    if pruefung is not None:
        liste = fehlende_unterlagen_liste(
            kontext.schema, pruefung.vollstaendigkeit.get("verbraucher") or []
        )
        if liste:
            werte["[FEHLENDE_UNTERLAGEN_LISTE]"] = liste
    return werte


def basis_platzhalter(fall, pruefung, schema, kontext) -> dict[str, str]:
    """`basis_eintrag.md` — the Abschluss export (contract §7, 14 §4 step 10).

    Deliberately a different set from the letter placeholders: this block goes
    into the advisory's own statistics, not to a company, so it carries the
    Fallgruppe, the verdict and the magnitude — and no identity at all.
    """
    from fallpruefer.vokabular import label

    werte = {
        "[CASE_ID]": fall.case_id,
        "[KANAL]": label(fall.eingang.kanal),
        "[ANBIETER]": fall.eingang.anbieter or "—",
        "[GEGNER]": fall.eingang.gegner or "—",
        "[FALLGRUPPE]": schema.name,
        "[STUFE]": (fall.fallgruppe.stufe or schema.stufe).value,
        "[EINORDNUNG]": pruefung.einordnung or "—",
        "[RECHTSBEHELF]": _rechtsbehelf_titel(fall, schema),
        "[FRISTEN]": _fristen_zeile(pruefung),
        "[SCHADENSHOEHE]": _schadenshoehe(pruefung, kontext),
        "[REFERAT_MARKIERUNG]": _referat_zeile(fall),
        "[SCHEMA_VERSION]": fall.schema_.version or schema.version,
        "[SCHEMA_STAND]": fall.schema_.stand or schema.stand,
        "[HEUTE]": zeit.datum_de(zeit.heute()),
    }
    return werte


def _rechtsbehelf_titel(fall, schema) -> str:
    rid = fall.rechtsbehelf.gewaehlt or fall.rechtsbehelf.hauptvorschlag
    r = schema.rechtsbehelfe.nach_id(rid or "")
    if r is None:
        return "—"
    status = fall.rechtsbehelf.brief.status.value if fall.rechtsbehelf.brief else None
    return f"{r.titel}" + (f" (Schreiben: {status})" if status else "")


def _fristen_zeile(pruefung) -> str:
    teile = [f"{e.frist.name}: {e.frist.wert}" for e in pruefung.ergebnisse if e.frist]
    return " · ".join(teile) if teile else "keine laufende Frist berechnet"


def _schadenshoehe(pruefung, kontext) -> str:
    """Contract §7: the Rückforderung if it was computed, otherwise the monthly
    difference times the months it has been in effect. Never a guess dressed up
    as a figure — if the increase has not taken effect yet, it says so."""
    rueck = _rueckforderung(pruefung)
    if rueck is not None:
        return f"{zeit.betrag_de(rueck)} (zurückgefordert)"

    alt = zeit.parse_betrag(kontext.feld("erhoehungsschreiben.alter_betrag"))
    neu = zeit.parse_betrag(kontext.feld("erhoehungsschreiben.neuer_betrag"))
    if alt is None or neu is None:
        return "nicht berechenbar"
    differenz = round(neu - alt, 2)
    ab = kontext.datum("erhoehungsschreiben.wirksam_ab")
    if ab is None or ab > zeit.heute():
        return f"{zeit.betrag_de(differenz)} pro Monat (Erhöhung noch nicht wirksam)"
    # `monate_zwischen` counts whole months, so an increase effective on the
    # 1st read „noch nicht wirksam" for its first 30 days — a false statement in
    # an artefact that goes into VZ's own statistics, in the very line the
    # Referat reads for „bedeutsame Schadenshöhe". In effect but under a month
    # is one debit, not none.
    monate = zeit.monate_zwischen(ab, zeit.heute())
    if monate <= 0:
        return f"{zeit.betrag_de(differenz)} (erste Abbuchung, seit {zeit.datum_de(ab)} wirksam)"
    return (f"{zeit.betrag_de(round(differenz * monate, 2))} "
            f"({zeit.betrag_de(differenz)} × {monate} Monate)")


def _referat_zeile(fall) -> str:
    from fallpruefer.konfig import konfig as _k

    if not fall.referat_markierung.kriterien:
        return "nicht markiert"
    labels = {kr["id"]: kr["label"] for kr in _k().referat_kriterien}
    return ", ".join(labels.get(k, k) for k in fall.referat_markierung.kriterien)


def _rueckforderung(pruefung) -> float | None:
    for erg in pruefung.ergebnisse if pruefung else []:
        if erg.betrag and erg.betrag.roh is not None:
            return erg.betrag.roh
    return None


def fehlende_unterlagen_liste(schema, fehlt) -> str:
    """`[FEHLENDE_UNTERLAGEN_LISTE]` — anzeigename · Begründungssatz ·
    Beschaffungsweg, one block per missing document (contract §7).

    One block per *document*, not per gap: a document can be missing twice over
    (not filed at all, and a required field of it unfound), and asking the same
    person twice for the same paper is how a form letter loses its reader.
    """
    bloecke: list[str] = []
    gesehen: set[str] = set()
    for el in fehlt:
        if not el.dokumenttyp or el.dokumenttyp.value in gesehen:
            continue
        sd = schema.dokumenten_soll.nach_typ(el.dokumenttyp)
        if not sd:
            continue
        gesehen.add(el.dokumenttyp.value)
        bloecke.append(
            f"- {sd.anzeigename}\n"
            f"  {sd.begruendung_satz}\n"
            f"  Wo Sie es finden: {sd.beschaffungsweg}"
        )
    return "\n".join(bloecke)


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------


def varianten_waehlen(vorlage: Vorlage, kontext) -> list[str]:
    from fallpruefer.regeln import auswerten

    return [v["id"] for v in vorlage.varianten if auswerten(v.get("wenn"), kontext) is True]


def rendern(
    vorlage: Vorlage, werte: dict[str, str], aktive_varianten: list[str],
    lint_nachforderung: bool = False,
) -> str:
    def variante(m: re.Match) -> str:
        vid, block = m.group(1), m.group(2)
        return (block.strip() + "\n\n") if vid in aktive_varianten else ""

    text = _VARIANTE.sub(variante, vorlage.koerper)

    muster = re.compile(konfig().platzhalter_regex)
    fehlend: list[str] = []

    def fuellen(m: re.Match) -> str:
        name = m.group(0)
        if name not in werte or werte[name] == "":
            fehlend.append(name)
            return name
        return werte[name]

    text = muster.sub(fuellen, text)
    if fehlend:
        raise BriefFehler(
            "Platzhalter nicht füllbar: " + ", ".join(sorted(set(fehlend)))
            + " — ein Brief mit Lücke wird nicht ausgegeben."
        )

    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"

    # Deliberately after the substitution: `[FEHLENDE_UNTERLAGEN_LISTE]` pastes
    # each Soll entry's `begruendung_satz` verbatim into a letter addressed to
    # the consumer, so a legal statement can enter through the data as easily
    # as through the template. `schema.pruefen` checks the same words at load
    # time, so this stays a backstop rather than the first line of defence.
    if lint_nachforderung and (treffer := _NACHFORDERUNG_LINT.search(text)):
        raise BriefFehler(
            f"Nachforderungs-Text enthält eine rechtliche Aussage: „{treffer.group(0)}“"
        )
    return text
