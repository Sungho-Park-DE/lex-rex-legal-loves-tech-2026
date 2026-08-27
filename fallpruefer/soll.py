"""Dokumenten-Soll — which documents this case needs, and what is missing.

Two things this module refuses to blur:

* **field level, not document level.** „AGB liegen vor" is not the same as
  „der Klauseltext liegt vor". A document counts as present only when its
  `pflicht: true` fields are there — otherwise the case is still incomplete
  and the advisor is told exactly which page is missing.
* **owner.** A missing consumer-side document becomes a Nachforderung (Gate 1).
  A missing company-side one becomes an Auskunftsverlangen (Gate 4) and is
  never requested from the consumer. `pflicht: hinweis` items are always
  listed as open and never asked for.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fallpruefer.fall import Fall, FehlendesElement
from fallpruefer.schema import Schema, SollDokument
from fallpruefer.vokabular import Dokumenttyp, Fehlzustand, Pflicht, Quelle


@dataclass
class SollErgebnis:
    gefordert: list[Dokumenttyp] = field(default_factory=list)
    vorhanden: list[Dokumenttyp] = field(default_factory=list)
    fehlt: list[FehlendesElement] = field(default_factory=list)
    relevante_agb_fassung: str | None = None
    # V-N2: Dokumentarten, von denen die Beraterin festgestellt hat, dass es
    # sie nie gab. Steht hier und nicht nur in den `fehlt`-Eintraegen, weil der
    # Evaluator dieselbe Auskunft fuer die *Feld*-Luecken braucht: ein Feld aus
    # einem Dokument, das es nie gab, darf genausowenig beim Verbraucher
    # angefordert werden wie das Dokument selbst.
    nie_vorhanden: set[Dokumenttyp] = field(default_factory=set)

    @property
    def vollstaendig_verbraucherseite(self) -> bool:
        return not any(f.quelle == Quelle.VERBRAUCHER for f in self.fehlt)

    def massgebliche_dokumente(self) -> dict[str, str]:
        """Which document governs, for types that can have several versions."""
        return {"agb": self.relevante_agb_fassung} if self.relevante_agb_fassung else {}

    def as_dict(self) -> dict:
        return {
            "vollstaendig": self.vollstaendig_verbraucherseite,
            "gefordert": [d.value for d in self.gefordert],
            "vorhanden": [d.value for d in self.vorhanden],
            "fehlt": [f.model_dump(mode="json") for f in self.fehlt],
            "relevante_agb_fassung": self.relevante_agb_fassung,
        }


def relevante_agb_fassung(fall: Fall, schema: Schema | None = None) -> str | None:
    """The AGB version that governs (contract §4): the latest whose
    `fassung_datum` is not after the contract date.

    Two things the contract left open, decided here (18 #33):

    * the version date comes from the document's metadata **or from the
      extracted fact** `agb.fassung_datum` — over the API there is no metadata
      (a PDF has no front matter), and a rule that only worked for fiction
      files would have picked the wrong document in the demo;
    * a tie — same date, or no date at all — goes to the document whose
      required fields are actually there. Franz' Fall 3b hands in the missing
      *page* of the same AGB: two documents, one version, and only one of them
      carries the clause.
    """
    from datetime import date as _date

    from fallpruefer.zeit import parse_datum

    agbs = fall.dokumente_vom_typ(Dokumenttyp.AGB)
    if not agbs:
        return None
    if len(agbs) == 1:
        return agbs[0].dok_id

    vertragsdatum = None
    for d in fall.dokumente_vom_typ(Dokumenttyp.VERTRAG):
        for f in fall.fakten:
            if f.feld_id == "vertrag.datum" and f.dok_id == d.dok_id:
                vertragsdatum = parse_datum(f.wert)

    pflicht_felder = {
        sp.feld_id
        for sp in (schema.dokumenten_soll.nach_typ(Dokumenttyp.AGB).felder if schema else [])
        if sp.pflicht
    } if schema and schema.dokumenten_soll.nach_typ(Dokumenttyp.AGB) else set()

    def fassung(d) -> _date | None:
        aus_meta = parse_datum(d.fassung_datum)
        if aus_meta:
            return aus_meta
        return next((parse_datum(f.wert) for f in fall.fakten
                     if f.feld_id == "agb.fassung_datum" and f.dok_id == d.dok_id
                     and f.verifiziert is not False), None)

    def vollstaendigkeit(d) -> int:
        felder = {f.feld_id for f in fall.fakten
                  if f.dok_id == d.dok_id and f.wert is not None and f.verifiziert is not False}
        return len(felder & pflicht_felder) if pflicht_felder else len(felder)

    def nummer(d) -> int:
        return int(d.dok_id[1:]) if d.dok_id[1:].isdigit() else 0

    passend = [d for d in agbs if fassung(d) and vertragsdatum and fassung(d) <= vertragsdatum]
    auswahl = passend or agbs
    beste = max(auswahl, key=lambda d: (fassung(d) or _date.min, vollstaendigkeit(d), nummer(d)))
    return beste.dok_id


def _felder_fehlen(fall: Fall, soll_dok: SollDokument, dok_id: str | None) -> list[str]:
    vorhandene = {
        f.feld_id
        for f in fall.fakten
        if f.wert is not None and f.verifiziert is not False
        and (dok_id is None or f.dok_id in (None, dok_id))
    }
    return [f.feld_id for f in soll_dok.felder if f.pflicht and f.feld_id not in vorhandene]


def auswerten(fall: Fall, schema: Schema, kontext) -> SollErgebnis:
    """`kontext` is the same `Fallkontext` the rules use — the `bedingung` of a
    conditional document is an ordinary condition of the rule grammar."""
    from fallpruefer.regeln import auswerten as bedingung_auswerten

    erg = SollErgebnis(relevante_agb_fassung=relevante_agb_fassung(fall, schema))
    vorhandene_typen = {d.dokumenttyp for d in fall.dokumente}

    # Feststellungen der Beraterin, die jeden Lauf überdauern (V-N2). Eine
    # zurückgezogene zählt nicht mehr, bleibt aber am Fall stehen.
    nie_vorhanden = {
        n.dokumenttyp: n for n in fall.nicht_vorhanden if not n.zurueckgezogen
    }
    erg.nie_vorhanden = set(nie_vorhanden)

    # a group is satisfied by any one of its members ("Klausel in AGB oder Vertrag")
    gruppe_erfuellt = {
        g.id: any(t in vorhandene_typen for t in g.mindestens_eines)
        for g in schema.dokumenten_soll.gruppen
    }

    for sd in schema.dokumenten_soll.dokumente:
        typ = sd.dokumenttyp
        da = typ in vorhandene_typen
        if da:
            erg.vorhanden.append(typ)

        if sd.pflicht == Pflicht.IMMER:
            gefordert = True
        elif sd.pflicht == Pflicht.BEDINGT:
            gefordert = bedingung_auswerten(sd.bedingung, kontext) is True
        else:
            # erwartet_wenn_vorhanden / hinweis are never *requested*
            gefordert = False

        if gefordert:
            erg.gefordert.append(typ)

        if not da:
            if sd.pflicht == Pflicht.HINWEIS:
                # company-side: always listed as open, never asked for
                erg.fehlt.append(FehlendesElement(
                    dokumenttyp=typ, quelle=sd.quelle, grund=sd.begruendung_satz or "Hinweis",
                ))
            elif gefordert and not (sd.gruppe and gruppe_erfuellt.get(sd.gruppe)):
                festgestellt = nie_vorhanden.get(typ)
                if festgestellt is not None:
                    # V-N2: „hat es nie gegeben" ist etwas anderes als „liegt
                    # noch nicht vor". Das Fehlen wandert auf die
                    # Unternehmensseite — dort ist es ein Auskunftsverlangen
                    # (Gate 4), und Gate 1 fragt die Verbraucherin nicht mehr
                    # nach einem Brief, den sie nicht haben kann.
                    erg.fehlt.append(FehlendesElement(
                        dokumenttyp=typ, quelle=Quelle.UNTERNEHMEN,
                        grund="nach Angabe der Verbraucherin nie erhalten",
                        fehlzustand=Fehlzustand.EXISTIERT_NICHT,
                        aussage=festgestellt.aussage,
                    ))
                else:
                    erg.fehlt.append(FehlendesElement(
                        dokumenttyp=typ, quelle=sd.quelle, grund="nicht eingereicht",
                        fehlzustand=Fehlzustand.NICHT_EINGEREICHT,
                    ))
            continue

        # present, but is it complete?
        dok_id = erg.relevante_agb_fassung if typ == Dokumenttyp.AGB else None
        for feld_id in _felder_fehlen(fall, sd, dok_id):
            erg.fehlt.append(FehlendesElement(
                dokumenttyp=typ, feld_id=feld_id, quelle=sd.quelle,
                grund="im Dokument nicht gefunden",
                fehlzustand=Fehlzustand.FELD_FEHLT_IM_DOKUMENT,
            ))

    return erg
