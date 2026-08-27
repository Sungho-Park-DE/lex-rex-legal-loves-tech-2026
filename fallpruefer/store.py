"""The anonymised store and the Muster-Radar (contract §8, 14 §7 „Radar +1").

Two properties decide whether this is usable at all, and both are structural
rather than promised:

* **No identity can be in the record**, because no identity is ever put into
  one — the record is built from a fixed field list, not from the case object
  by exclusion. A field that does not exist cannot leak. `fall_hash` is an
  HMAC, so the same case updates its own row and nobody can walk back from a
  row to a case id.
* **No cluster below `k_min` is reported**, so a count can never be traced to
  one person's complaint. Below the threshold the Radar says how many Anbieter
  it is still holding back, never who they are.

Written at Gate 3 (14 §4 step 9): every confirmed case counts, all Stufen —
which is what makes the count on screen honest when the Referat looks at it.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from fallpruefer import abmahnungen, zeit
from fallpruefer.konfig import WURZEL, konfig
from fallpruefer.fall import Fall
from fallpruefer.schema import Schema

# Every key that may appear in a store record. The writer builds exactly these.
FELDER = (
    "fall_hash", "zeit", "fallgruppe_id", "stufe", "anbieter", "gegner", "branche",
    "einordnung", "gerissene_stufe", "pruefpunkte_nein", "fehlte", "rechtsbehelf",
    "betrag_erhoehung_gerundet", "referat_flag", "kanal", "schema_version",
    # Franz' Anleitung §5 — Schaden je Einzelfall, entstanden und drohend getrennt
    "schaden_entstanden", "schaden_drohend", "schaden_basis",
    # Franz' Anleitung §7 — ids der Abmahnungs-Einträge, deren Klauseltyp hier NEIN steht
    "abgemahnt",
)

# Franz' Anleitung §5: „bei unbefristeten Verträgen wird auf den nächstmöglichen
# Kündigungstermin, hilfsweise 24 Monate gekappt." Die 24 sind keine Setzung:
# § 309 Nr. 9 lit. a BGB erklärt eine Erstlaufzeit von mehr als zwei Jahren für
# unwirksam — länger kann eine Bindung also gar nicht laufen.
SCHADEN_FALLBACK_MONATE = 24

# Was „nächstmöglicher Kündigungstermin" nach Ablauf der Bindung heißt, sagt das
# Gesetz selbst, für beide Wege:
#   · Verlängerungsklausel wirksam → § 309 Nr. 9 lit. b BGB (Fassung seit
#     01.03.2022): nur auf unbestimmte Zeit, „jederzeit mit einer Frist von
#     höchstens einem Monat" kündbar.
#   · Verlängerungsklausel unwirksam → § 306 Abs. 2 BGB, gesetzliche Regel,
#     § 621 Nr. 3 BGB: bei monatlicher Vergütung zum 15. für den Monatsschluss.
# Beide Wege enden bei einem Monat. Die Fassung davor (Art. 229 § 60 S. 2 EGBGB:
# Schuldverhältnisse, die vor dem 01.03.2022 entstanden sind) ließ eine
# stillschweigende Verlängerung bis zu einem Jahr zu.
FAIRE_VERTRAEGE_AB = date(2022, 3, 1)
VERLAENGERUNG_MONATE_NEU = 1
VERLAENGERUNG_MONATE_ALT = 12


def pfad() -> Path:
    return WURZEL / konfig().store_pfad


_GEWARNT = False


def _dev_geheimnis_warnen() -> None:
    global _GEWARNT
    if not _GEWARNT:
        _GEWARNT = True
        import sys

        print(f"⚠️  {konfig().hmac_secret_env} ist nicht gesetzt — fall_hash läuft mit dem "
              "Entwicklungsgeheimnis (Demo ok, Pilot nicht).", file=sys.stderr)


def fall_hash(case_id: str) -> str:
    """HMAC, not a plain hash: a plain SHA of a case id from a known series is
    a rainbow table with four digits of entropy."""
    geheim = os.environ.get(konfig().hmac_secret_env)
    if not geheim:
        # V-34: für die Demo in Ordnung, für einen Piloten nicht — einmal laut
        # sagen statt still auf die Konstante fallen.
        _dev_geheimnis_warnen()
        geheim = "fallpruefer-dev"
    return hmac.new(geheim.encode("utf-8"), case_id.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def _betrag(fall: Fall) -> float | None:
    """The increase per month, rounded to the nearest half euro — enough for a
    magnitude on the Radar, not enough to identify a contract."""
    werte: dict[str, Any] = {}
    for f in fall.fakten:
        if f.feld_id in ("erhoehungsschreiben.alter_betrag", "erhoehungsschreiben.neuer_betrag"):
            werte[f.feld_id] = f.wert
    alt = zeit.parse_betrag(werte.get("erhoehungsschreiben.alter_betrag"))
    neu = zeit.parse_betrag(werte.get("erhoehungsschreiben.neuer_betrag"))
    if alt is None or neu is None:
        return None
    return round((neu - alt) * 2) / 2


def _zahl(wert: Any) -> float | None:
    try:
        return float(str(wert).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _schaden(fall: Fall) -> dict[str, Any]:
    """Der wirtschaftliche Schaden nach Franz' Anleitung §5 — **seine** Formel,
    nicht unsere: `einmaliger Betrag + (wiederkehrender Betrag × Zahl der noch
    gebundenen Perioden)`.

    Zwei Dinge daran sind der eigentliche Punkt und stehen deshalb getrennt im
    Satz: **bereits entstanden** ist verloren, **künftig drohend** ist das, was
    die Beratung noch abwenden kann — „nur Letzterer ist abwendbar und damit
    Grundlage für Beratung und Warnung". Eine Summe aus beidem wäre die Zahl,
    die niemand gebrauchen kann.

    Einen einmaligen Betrag kennt die Fallgruppe Preiserhöhung nicht; er ist
    hier immer 0 und wird nicht erfunden.

    `basis` sagt, **wie** gerechnet wurde, und wird angezeigt: eine gekappte
    Zahl, die aussieht wie eine gemessene, ist eine Behauptung.
    """
    werte: dict[str, Any] = {f.feld_id: f.wert for f in fall.fakten}
    alt_b = zeit.parse_betrag(werte.get("erhoehungsschreiben.alter_betrag"))
    neu_b = zeit.parse_betrag(werte.get("erhoehungsschreiben.neuer_betrag"))
    if alt_b is None or neu_b is None:
        # §5: „Fälle ohne Betragsangabe gelten als unbeziffert, nicht als null."
        return {"entstanden": None, "drohend": None, "basis": "unbeziffert"}

    monatlich = round(neu_b - alt_b, 2)
    heute = zeit.heute()
    ab = zeit.parse_datum(werte.get("erhoehungsschreiben.wirksam_ab"))

    entstanden = 0.0
    if ab is not None and ab < heute:
        entstanden = round(monatlich * max(0, zeit.monate_zwischen(ab, heute)), 2)

    beginn = zeit.parse_datum(werte.get("vertrag.vertragsbeginn"))
    genau = beginn is not None
    if beginn is None:
        # `24` §3.2 hat genau das als Falle notiert: das Vertrags*datum* ist
        # nicht der Vertrags*beginn*. Wir rechnen trotzdem damit, wenn nichts
        # anderes da ist — sagen es aber in `basis`, statt es zu verschweigen.
        beginn = zeit.parse_datum(werte.get("vertrag.datum"))
    laufzeit = _zahl(werte.get("vertrag.laufzeit_monate"))
    start = max(heute, ab) if ab else heute

    if beginn is None:
        # Weder Beginn noch Laufzeit: §5 „hilfsweise 24 Monate" — ab heute,
        # weil der Vertrag auch gestern begonnen haben kann.
        perioden, basis = SCHADEN_FALLBACK_MONATE, "fallback_24"
    else:
        if laufzeit:
            bindung = int(laufzeit)
            basis = "laufzeit" if genau else "laufzeit_vertragsdatum"
        else:
            # Beginn bekannt, Laufzeit nicht: die gesetzliche Obergrenze der
            # Erstlaufzeit ab Beginn ist ehrlicher als 24 Monate ab heute.
            bindung, basis = SCHADEN_FALLBACK_MONATE, "hoechstlaufzeit_24"
        ende = _monate_addieren(beginn, bindung)
        if ende > start:
            perioden = zeit.monate_zwischen(start, ende)
        elif beginn >= FAIRE_VERTRAEGE_AB:
            # Bindung abgelaufen, Vertrag läuft weiter: § 309 Nr. 9 lit. b n.F.
            perioden, basis = VERLAENGERUNG_MONATE_NEU, "verlaengerung_monatlich"
        else:
            perioden, basis = VERLAENGERUNG_MONATE_ALT, "verlaengerung_altrecht"

    return {"entstanden": entstanden,
            "drohend": round(monatlich * max(0, perioden), 2),
            "basis": basis}


def _monate_addieren(d: date, monate: int) -> date:
    """Kalendermonate addieren; der Tag wird auf 28 gekappt, damit der 31. nicht
    in einen Monat fällt, der ihn nicht hat."""
    m = d.month - 1 + monate
    return date(d.year + m // 12, m % 12 + 1, min(d.day, 28))


def schluessel(name: str | None) -> str | None:
    """The form a company name takes *inside* the store.

    Folded, so „FitPoint 24" and „fitpoint 24" are one Anbieter and not two
    clusters of half the size — which would quietly push both under `k_min`.

    It exists as a named function because a reader has to use the same one.
    `anbieter_bestand` originally compared the raw name against the folded
    stored value and therefore matched nothing, ever: every Anbieter came back
    „below the threshold". That is invisible from outside by construction —
    suppressed and empty are required to look identical — so nothing could
    have surfaced it on the screen, and on stage the counter would simply not
    have appeared after Gate 3 with no way to tell a threshold from a bug.
    If every caller has to know the write side's folding, it is not a detail
    of the write side any more.
    """
    return (name or "").strip().lower() or None


def satz_bauen(fall: Fall, schema: Schema | None = None) -> dict[str, Any]:
    pruefung = fall.aktuelle_pruefung()
    anbieter = schluessel(fall.eingang.anbieter)
    satz = {
        "fall_hash": fall_hash(fall.case_id),
        "zeit": zeit.jetzt(),
        "fallgruppe_id": fall.schema_.fallgruppe_id,
        "stufe": fall.fallgruppe.stufe.value if fall.fallgruppe.stufe else None,
        "anbieter": anbieter,
        "gegner": schluessel(fall.eingang.gegner),
        "branche": fall.eingang.branche,
        "einordnung": pruefung.einordnung if pruefung else None,
        "gerissene_stufe": pruefung.gerissene_stufe if pruefung else None,
        "pruefpunkte_nein": sorted(
            e.pruefpunkt_id for e in (pruefung.ergebnisse if pruefung else [])
            if e.zustand.value == "NEIN"
        ),
        "fehlte": sorted({
            f.dokumenttyp.value
            for liste in (pruefung.vollstaendigkeit.values() if pruefung else [])
            for f in liste if f.dokumenttyp
        }),
        "rechtsbehelf": fall.rechtsbehelf.gewaehlt or fall.rechtsbehelf.hauptvorschlag,
        "betrag_erhoehung_gerundet": _betrag(fall),
        **{f"schaden_{k}": v for k, v in _schaden(fall).items()},
        "referat_flag": list(fall.referat_markierung.kriterien),
        "kanal": fall.eingang.kanal.value,
        "schema_version": fall.schema_.version,
    }
    satz["abgemahnt"] = [a.id for a in abmahnungen.treffer(
        satz["fallgruppe_id"], satz["pruefpunkte_nein"])]
    assert set(satz) == set(FELDER), "Store-Satz weicht von der Feldliste ab"
    return satz


def schreiben(fall: Fall, schema: Schema | None = None) -> dict[str, Any]:
    """Append-only, one row per case. A second write for the same case replaces
    its row rather than counting it twice — the Radar counts cases, not saves."""
    satz = satz_bauen(fall, schema)
    p = pfad()
    p.parent.mkdir(parents=True, exist_ok=True)

    zeilen = [
        z for z in (p.read_text(encoding="utf-8").splitlines() if p.exists() else [])
        if z.strip() and json.loads(z).get("fall_hash") != satz["fall_hash"]
    ]
    zeilen.append(json.dumps(satz, ensure_ascii=False))
    p.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return satz


def lesen() -> list[dict[str, Any]]:
    p = pfad()
    if not p.exists():
        return []
    return [json.loads(z) for z in p.read_text(encoding="utf-8").splitlines() if z.strip()]


# --------------------------------------------------------------------------
# Radar
# --------------------------------------------------------------------------


@dataclass
class Cluster:
    anbieter: str
    branche: str | None
    faelle: int
    # Display payload, not store rows: the verdicts carry their tone and the
    # broken Prüfpunkte their titles, because /radar is a surface a human
    # reads (Referat screen) and the UI may not map codes to anything
    # (contract §0). The store rows underneath keep raw P-ids — they are
    # evidence, not display.
    einordnungen: list[dict[str, Any]] = field(default_factory=list)
    pruefpunkte_nein: list[dict[str, Any]] = field(default_factory=list)
    betrag_median: float | None = None
    referat_flags: int = 0
    # Franz' Anleitung §5: Median je Fall, Summe und Fallzahl — und die
    # unbezifferten Fälle als eigene Zahl, nicht als Nullen im Median.
    schaden: dict[str, Any] = field(default_factory=dict)
    fallgruppe_id: str | None = None
    # Anleitung §7: Fälle dieses Clusters, in denen ein bereits abgemahnter
    # Klauseltyp erneut auftritt. Eine Zahl, kein Firmenname des Vorverfahrens.
    wiederholung: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "anbieter": self.anbieter, "branche": self.branche, "faelle": self.faelle,
            "einordnungen": self.einordnungen, "pruefpunkte_nein": self.pruefpunkte_nein,
            "betrag_median": self.betrag_median, "referat_flags": self.referat_flags,
            "schaden": self.schaden, "fallgruppe_id": self.fallgruppe_id,
            "wiederholung": self.wiederholung,
        }


def _schaden_block(gruppe: list[dict]) -> dict[str, Any]:
    """Franz' Anleitung §5 für eine Menge von Fällen.

    Summiert wird **nur innerhalb einer Fallgruppe** und über Fälle
    verschiedener Verbraucher — der Aufrufer stellt das sicher. Unbezifferte
    Fälle stehen als eigene Zahl daneben und gehen in keinen Median ein.
    """
    drohend = [s["schaden_drohend"] for s in gruppe if s.get("schaden_drohend") is not None]
    entstanden = [s["schaden_entstanden"] for s in gruppe
                  if s.get("schaden_entstanden") is not None]
    basen = sorted({s.get("schaden_basis") for s in gruppe if s.get("schaden_basis")})
    return {
        "drohend_median": _median(drohend),
        "drohend_summe": round(sum(drohend), 2) if drohend else None,
        "entstanden_median": _median(entstanden),
        "entstanden_summe": round(sum(entstanden), 2) if entstanden else None,
        "fallzahl": len(drohend),
        "unbeziffert": sum(1 for s in gruppe if s.get("schaden_basis") == "unbeziffert"),
        "gekappt": sum(1 for s in gruppe if s.get("schaden_basis") == "fallback_24"),
        "verlaengert": sum(1 for s in gruppe if (s.get("schaden_basis") or "")
                           .startswith("verlaengerung_")),
        "basen": basen,
    }


def _median(werte: list[float]) -> float | None:
    if not werte:
        return None
    s = sorted(werte)
    m = len(s) // 2
    return s[m] if len(s) % 2 else round((s[m - 1] + s[m]) / 2, 2)


@dataclass
class Bestand:
    """What the store knows about one Anbieter in one Fallgruppe — or refuses
    to say.

    `faelle is None` means the threshold suppressed it, and the caller must
    then show **nothing about other cases at all**. Not „unter der
    Meldeschwelle": that sentence says „there is at least one and fewer than
    k", which at k = 2 is precisely the re-identification the threshold exists
    to prevent. Suppressed and empty have to look the same from outside, or the
    threshold is decoration.
    """

    anbieter: str
    fallgruppe_id: str
    k_min: int
    faelle: int | None = None
    gleicher_pruefpunkt: dict[str, int] = field(default_factory=dict)

    @property
    def ausgewiesen(self) -> bool:
        return self.faelle is not None

    def as_dict(self) -> dict[str, Any]:
        return {"anbieter": self.anbieter, "fallgruppe_id": self.fallgruppe_id,
                "k_min": self.k_min, "ausgewiesen": self.ausgewiesen,
                "faelle": self.faelle, "gleicher_pruefpunkt": self.gleicher_pruefpunkt}


def anbieter_bestand(anbieter: str | None, fallgruppe_id: str | None) -> Bestand:
    """„Wie oft hatten wir das schon?" — for the Fallakte, under the same
    threshold as the Radar.

    The threshold does not protect the case the advisor already has open. It
    protects **the other people being counted**. „3 Fälle" means „two others
    besides this one"; at two it means „one other", and an advisor who knows or
    handles one of them has identified that person's complaint. The reader
    changes between the Radar and the Fallakte, the risk does not — so the rule
    stays one rule, not one rule with an exception.

    The current case is in here only once it has been confirmed at Gate 3,
    because that is when it is written (14 §4 step 9). That is what makes the
    „+1" real rather than staged: before the confirmation the count is the
    background, after it the case is part of it.
    """
    k = konfig().radar
    # The caller holds the display form („FitPoint 24"); the store holds the
    # folded one. Folding here rather than at the call site keeps the store's
    # own convention inside the store — the same reason the threshold itself
    # lives in one place.
    gefaltet = schluessel(anbieter)
    leer = Bestand(anbieter=anbieter or "", fallgruppe_id=fallgruppe_id or "", k_min=k.k_min)
    if not gefaltet or not fallgruppe_id:
        return leer

    gruppe = [s for s in lesen()
              if s.get("anbieter") == gefaltet and s.get("fallgruppe_id") == fallgruppe_id]
    if len(gruppe) < k.k_min:
        return leer

    punkte: dict[str, int] = {}
    for s in gruppe:
        for pid in s.get("pruefpunkte_nein") or []:
            punkte[pid] = punkte.get(pid, 0) + 1
    leer.faelle = len(gruppe)
    leer.gleicher_pruefpunkt = dict(sorted(punkte.items(), key=lambda x: -x[1]))
    return leer



def _einordnung_ton(text: str) -> str:
    """The tone for a verdict text on the radar — derived from the ONE
    label/tone source instead of a second mapping. The store keeps the verdict
    as its display string (identity-free rows carry no enum), so this walks the
    vocabulary and prefix-matches the label; „unklar – es fehlt: …" variants
    match the „unklar – es fehlt …" base label. Unknown text stays grau."""
    from fallpruefer.vokabular import Einordnung, label, ton

    for e in Einordnung:
        basis = label(e).rstrip(" …").rstrip(":").strip()
        if text == label(e) or text.startswith(basis):
            return ton(e).value
    return "grau"


def _pruefpunkt_titel(fallgruppe_id: str | None, pid: str) -> str:
    """P-ids say nothing to a human (the F1 evidence line and the loader guard
    follow the same rule); the radar is read by the Referat. Resolution can
    fail — an old row may name a Prüfpunkt a schema edit removed — and then
    the id is still the honest fallback: readable beats wrong."""
    if fallgruppe_id:
        try:
            from fallpruefer.schema import schema_laden

            pp = schema_laden(fallgruppe_id).pruefpunkt(pid)
            if pp is not None:
                return pp.titel
        except Exception:  # noqa: BLE001 — a radar row must not 500 the screen
            pass
    return pid


def _pruefpunkt_norm(fallgruppe_id: str | None, pid: str) -> tuple[str | None, str | None]:
    """Die Fundstelle des Klauseltyps, lang und kurz.

    Team-Rueckmeldung 26. Aug: „Ich wuerde bei den Klauseltypen die Norm
    mitzitieren." Berechtigt — die Zeile nennt bisher nur unseren Titel
    („Transparenzgebot"), und das Referat arbeitet mit Fundstellen. Die Angabe
    liegt ohnehin am Pruefpunkt; sie wurde nur nicht mitgereicht.

    Kurzform ueber `ansicht._norm_kurz`, damit Radarzeile und Baumpille
    dieselbe Schreibweise zeigen (§ 307 I 2, nicht zweimal anders). Lokaler
    Import wie in `_pruefpunkt_titel` — der Radar darf an einer Fundstelle
    nicht scheitern, deshalb dieselbe Fehlerbehandlung.
    """
    if not fallgruppe_id:
        return None, None
    try:
        from fallpruefer.ansicht import _norm_kurz
        from fallpruefer.schema import schema_laden

        pp = schema_laden(fallgruppe_id).pruefpunkt(pid)
        norm = ((pp.anker or [{}])[0] or {}).get("norm") if pp else None
        return norm, _norm_kurz(norm)
    except Exception:  # noqa: BLE001 — eine Fundstelle darf den Schirm nicht 500en
        return None, None


def _klauseltypen(saetze: list[dict], k_min: int) -> tuple[list[dict], int]:
    """Franz' Anleitung §6 — die Achse, die dem Referat fehlt.

    Unser Radar zählt bisher **Anbieter**. Die Frage des Referats ist aber die
    andere: *welcher Klauseltyp* verbreitet sich. Der Prüfpunkt ist unser
    Klauseltyp — er ist genau die Merkmalsbeschreibung, an der eine Klausel
    scheitert, und wir speichern ihn ohnehin je Fall.

    §3 verlangt, die drei Zahlen **getrennt** auszuweisen, weil sie
    verschiedene Dinge sagen: **Verbreitung** = wie viele Verwender,
    **Betroffenheit** = wie viele Verbraucher, **Quote** = Anteil der Fälle
    dieser Fallgruppe. Eine Zahl allein lädt zur falschen Lesart ein.

    Die k_min-Schwelle gilt hier auf der **Verbreitung**: eine Zeile
    „Klauseltyp X: 1 Verwender" ist neben der sichtbaren Anbieterliste ein
    Fingerabdruck. Zurückgehaltene Zeilen werden gezählt, nicht angedeutet.
    """
    je_punkt: dict[tuple[str | None, str], dict[str, Any]] = {}
    gesamt_je_fg: dict[str | None, int] = {}
    for s in saetze:
        fg = s.get("fallgruppe_id")
        gesamt_je_fg[fg] = gesamt_je_fg.get(fg, 0) + 1
        for pid in s.get("pruefpunkte_nein") or []:
            e = je_punkt.setdefault((fg, pid), {"faelle": 0, "anbieter": set(), "drohend": []})
            e["faelle"] += 1
            if s.get("anbieter"):
                e["anbieter"].add(s["anbieter"])
            if s.get("schaden_drohend") is not None:
                e["drohend"].append(s["schaden_drohend"])

    zeilen: list[dict] = []
    zurueckgehalten = 0
    for (fg, pid), e in je_punkt.items():
        if len(e["anbieter"]) < k_min:
            zurueckgehalten += 1
            continue
        gesamt = gesamt_je_fg.get(fg) or 0
        # §7: „erneutes Auftreten einer bereits abgemahnten Klausel" — der
        # Klauseltyp ist der Schlüssel, nicht der Verwender.
        vorverfahren = abmahnungen.fuer_pruefpunkt(fg, pid)
        norm, norm_kurz = _pruefpunkt_norm(fg, pid)
        zeilen.append({
            "pruefpunkt_id": pid,
            "titel": _pruefpunkt_titel(fg, pid),
            "norm": norm,
            "norm_kurz": norm_kurz,
            "fallgruppe_id": fg,
            "verbreitung": len(e["anbieter"]),
            "betroffenheit": e["faelle"],
            "quote": round(e["faelle"] / gesamt, 2) if gesamt else None,
            "grundgesamtheit": gesamt,
            "schaden_drohend_median": _median(e["drohend"]),
            "bereits_abgemahnt": bool(vorverfahren),
            "abmahnung_kurz": vorverfahren[0].kurz() if vorverfahren else None,
            "abmahnung_geprueft": vorverfahren[0].geprueft if vorverfahren else None,
        })
    zeilen.sort(key=lambda z: (-z["betroffenheit"], -z["verbreitung"], z["titel"]))
    return zeilen, zurueckgehalten


def _kriterien_labels(codes: list[str] | None) -> list[str]:
    """Der Referat-Schirm liest Kriterien als Wörter, nicht als Codes —
    `bedeutsame_schadenshoehe` ist kein Wort, und genau so stand es bis heute
    unter „Markierte Fälle". Quelle ist dieselbe Liste, aus der das
    Referat-Panel der Fallakte seine Häkchen baut (`referat_kriterien` in der
    Konfiguration); ein unbekannter Code bleibt als er selbst lesbar, statt zu
    verschwinden."""
    labels = {k["id"]: k["label"] for k in konfig().referat_kriterien}
    return [labels.get(c, c) for c in (codes or [])]


def _prueflogik_fassungen(saetze: list[dict]) -> dict[str, Any]:
    """Franz' Anleitung §4/§7: „Prüflogik und Katalog werden versioniert, damit
    Zeitreihen vergleichbar bleiben." Der Store trägt `schema_version` seit der
    ersten Zeile; hier wird sie erstmals ausgewiesen. `aktuell` ist die Fassung
    der Schemadatei der häufigsten Fallgruppe — die Datei, die ein Mensch
    editiert (14 §6). Wer sie ändert, hebt `version` selbst; das Programm
    zählt nur, wie viele Zeilen noch unter einer älteren Fassung liefen."""
    fg_zaehler: dict[str, int] = {}
    for s_ in saetze:
        if s_.get("fallgruppe_id"):
            fg_zaehler[s_["fallgruppe_id"]] = fg_zaehler.get(s_["fallgruppe_id"], 0) + 1
    if not fg_zaehler:
        return {"fallgruppe_id": None, "aktuell": None, "zeilen_aktuell": 0,
                "zeilen_aelter": 0, "aelteste": None}
    fg = max(fg_zaehler, key=lambda x: fg_zaehler[x])
    try:
        from fallpruefer.schema import schema_laden

        aktuell = schema_laden(fg).version
    except Exception:  # noqa: BLE001 — a radar row must not 500 the screen
        aktuell = None
    fassungen = [s_.get("schema_version") for s_ in saetze
                 if s_.get("fallgruppe_id") == fg and s_.get("schema_version")]
    aelter = [v for v in fassungen if v != aktuell]
    return {
        "fallgruppe_id": fg,
        "aktuell": aktuell,
        "zeilen_aktuell": sum(1 for v in fassungen if v == aktuell),
        "zeilen_aelter": len(aelter),
        "aelteste": min(aelter, key=_versionsschluessel) if aelter else None,
    }


def _versionsschluessel(v: str) -> tuple:
    return tuple(int(t) if t.isdigit() else t for t in v.split("."))


def radar() -> dict[str, Any]:
    saetze = lesen()
    k = konfig().radar
    nach_anbieter: dict[str, list[dict]] = {}
    for s in saetze:
        if s.get("anbieter"):
            nach_anbieter.setdefault(s["anbieter"], []).append(s)

    cluster: list[Cluster] = []
    zurueckgehalten = 0
    for anbieter, gruppe in nach_anbieter.items():
        if len(gruppe) < k.k_min:
            zurueckgehalten += 1
            continue
        fg_zaehler: dict[str, int] = {}
        for s_ in gruppe:
            if s_.get("fallgruppe_id"):
                fg_zaehler[s_["fallgruppe_id"]] = fg_zaehler.get(s_["fallgruppe_id"], 0) + 1
        haupt_fg = max(fg_zaehler, key=lambda x: fg_zaehler[x]) if fg_zaehler else None
        einordnungen: dict[str, int] = {}
        punkte: dict[str, int] = {}
        punkt_titel: dict[str, str] = {}
        for s in gruppe:
            schluessel = (s.get("einordnung") or "").split(":")[0].strip()
            einordnungen[schluessel] = einordnungen.get(schluessel, 0) + 1
            for pid in s.get("pruefpunkte_nein") or []:
                punkte[pid] = punkte.get(pid, 0) + 1
                if pid not in punkt_titel:
                    punkt_titel[pid] = _pruefpunkt_titel(s.get("fallgruppe_id"), pid)
        cluster.append(Cluster(
            anbieter=anbieter,
            branche=next((s.get("branche") for s in gruppe if s.get("branche")), None),
            faelle=len(gruppe),
            einordnungen=[
                {"text": text, "anzahl": n, "tone": _einordnung_ton(text)}
                for text, n in sorted(einordnungen.items(), key=lambda x: -x[1])
            ],
            pruefpunkte_nein=[
                {"titel": punkt_titel[pid], "anzahl": n}
                for pid, n in sorted(punkte.items(), key=lambda x: -x[1])
            ],
            betrag_median=_median([s["betrag_erhoehung_gerundet"] for s in gruppe
                                   if s.get("betrag_erhoehung_gerundet") is not None]),
            referat_flags=sum(1 for s in gruppe if s.get("referat_flag")),
            fallgruppe_id=haupt_fg,
            # §5: summiert wird nur innerhalb einer Fallgruppe
            schaden=_schaden_block([s for s in gruppe
                                    if s.get("fallgruppe_id") == haupt_fg]),
            wiederholung=sum(1 for s in gruppe if s.get("abgemahnt")),
        ))
    cluster.sort(key=lambda c: (-c.faelle, c.anbieter))

    # A flagged case is meant to be listed individually (14 §4 step 9), so the
    # list itself stays — but naming the Anbieter of a case whose cluster the
    # k_min gate just suppressed contradicts, two lines lower, the notice that
    # says it does not. Below the threshold the row keeps everything the
    # Referat needs to click through and drops the one field that identifies.
    klauseltypen, kt_zurueckgehalten = _klauseltypen(saetze, k.k_min)
    ueber_schwelle = {a for a, g in nach_anbieter.items() if len(g) >= k.k_min}
    markierte = [s for s in saetze if s.get("referat_flag")]
    markierte_unter_schwelle = sum(
        1 for s in markierte if s.get("anbieter") not in ueber_schwelle)
    return {
        "stand": zeit.datum_de(zeit.heute()),
        "faelle_gesamt": len(saetze),
        "schwellen": {
            "beschwerden": k.schwelle_beschwerden,
            "beratungen": k.schwelle_beratungen,
            "k_min": k.k_min,
        },
        "cluster": [c.as_dict() for c in cluster],
        "klauseltypen": klauseltypen,
        "unter_schwelle_klauseltypen": kt_zurueckgehalten,
        "unter_schwelle_anbieter": zurueckgehalten,
        "markierte_faelle": [
            {"fall_hash": s["fall_hash"],
             # Die Kurzform, mit der der Fall auf dem Schirm steht. Sie kommt
             # von hier und nicht aus einem `slice()` in der Anzeige: eine
             # abgeschnittene Kennung ist eine Umformung, und die Anzeige formt
             # nichts um (27 §2). Roh gerendert las sich `68fee120` wie eine
             # Debugausgabe (35, R6-Familie) — der Satz in `hinweis` sagt jetzt
             # dazu, was es ist: ein Pseudonym, kein Name.
             "fall_kennung": s["fall_hash"][:8],
             "anbieter": s.get("anbieter") if s.get("anbieter") in ueber_schwelle else None,
             "einordnung": s.get("einordnung"), "kriterien": s.get("referat_flag"),
             "kriterien_labels": _kriterien_labels(s.get("referat_flag")),
             "zeit": (s.get("zeit") or "")[:10],
             "wiederholung": len(s.get("abgemahnt") or [])}
            for s in markierte
        ],
        # §7, als Zahl über alles: wie viele Fälle im Bestand tragen einen
        # Klauseltyp, der schon einmal abgemahnt wurde.
        "wiederholungen_gesamt": sum(1 for s in saetze if s.get("abgemahnt")),
        # §4/§7 Versionierung — siehe _prueflogik_fassungen
        "prueflogik_fassungen": _prueflogik_fassungen(saetze),
        "hinweis": (
            f"Anbieter mit weniger als {k.k_min} Fällen werden nicht einzeln ausgewiesen "
            f"({zurueckgehalten} zurückgehalten)."
            + (
                f" Bei {'einem markierten Fall' if markierte_unter_schwelle == 1 else str(markierte_unter_schwelle) + ' markierten Fällen'}"
                " ist aus demselben Grund kein Anbieter genannt."
                if markierte_unter_schwelle else ""
            )
            + (f" {kt_zurueckgehalten} Klauseltypen werden aus demselben Grund nicht"
               " ausgewiesen." if kt_zurueckgehalten else "")
            + " Beträge sind gerundet; der Datensatz enthält keine Namen, keine Freitexte"
            " und keine Dokumenttexte."
            + (" Statt eines Namens trägt jeder markierte Fall eine pseudonyme Kennung —"
               " sie erlaubt das Wiederfinden, ohne eine Person zu nennen."
               if markierte else "")
        ),
        # Franz' Anleitung §4: „Jede Auswertung weist aus, dass sie das
        # Beratungsaufkommen abbildet, nicht den Markt." Der Satz gehört an die
        # Zahlen und nicht in eine Fußnote — er ist der Unterschied zwischen
        # einer Statistik und einer Behauptung über die Branche.
        "geltungsbereich": (
            "Diese Auswertung bildet das Beratungsaufkommen der Verbraucherzentrale ab,"
            " nicht den Markt. Sie zeigt, was hier ankommt — nicht, wie verbreitet eine"
            " Klausel tatsächlich ist."
        ),
    }
