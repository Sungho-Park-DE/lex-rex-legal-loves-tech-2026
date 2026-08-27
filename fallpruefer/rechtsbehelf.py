"""Which remedy to propose — a first-class output, not a footnote.

The issuer (VZ Bayern), 19 Aug: finding the letter is the fast part; knowing *which* remedy
applies is the gap. So every branch ships a guaranteed pair (contract §2
`garantie_pro_zweig`), including „wirksam" — a valid increase still leaves the
consumer a Kündigung and a payment under protest, and a tool that goes silent
on the „wirksam" branch is the one an advisor stops trusting.

`gespraech.strategie` only reorders the list. It never removes an option.
"""

from __future__ import annotations

from dataclasses import dataclass

from fallpruefer.regeln import auswerten
from fallpruefer.schema import Rechtsbehelf, Schema


@dataclass
class Vorschlag:
    rechtsbehelf_id: str
    titel: str
    musterbrief: str | None
    geprueft: bool
    hauptvorschlag: bool = False


def waehlen(schema: Schema, einordnung_label: str, kontext) -> list[Vorschlag]:
    garantiert = schema.rechtsbehelfe.garantie_pro_zweig.get(einordnung_label, [])
    treffer_ids: list[str] = []

    for r in schema.rechtsbehelfe.liste:
        if r.wenn is None or auswerten(r.wenn, kontext) is True:
            treffer_ids.append(r.id)

    # the guarantee holds whether or not the `wenn` matched
    reihenfolge = [rid for rid in garantiert if rid in treffer_ids]
    reihenfolge += [rid for rid in garantiert if rid not in reihenfolge]
    reihenfolge += [rid for rid in treffer_ids if rid not in reihenfolge]

    if kontext.feld("gespraech.strategie") == "kuendigen" and "kuendigung_bei_wirksam" in reihenfolge:
        reihenfolge.remove("kuendigung_bei_wirksam")
        reihenfolge.insert(0, "kuendigung_bei_wirksam")

    vorschlaege: list[Vorschlag] = []
    for i, rid in enumerate(reihenfolge):
        r: Rechtsbehelf | None = schema.rechtsbehelfe.nach_id(rid)
        if r is None:
            continue
        vorschlaege.append(Vorschlag(
            rechtsbehelf_id=r.id, titel=r.titel, musterbrief=r.musterbrief,
            geprueft=r.geprueft, hauptvorschlag=(i == 0),
        ))
    return vorschlaege


def template_id(vorschlag: Vorschlag, kanal: str) -> str | None:
    """`musterbrief: "nachforderung_{kanal}"` — vor_ort and telefon share one."""
    if not vorschlag.musterbrief:
        return None
    kanal_datei = "vor_ort" if kanal in ("vor_ort", "telefon") else kanal
    return vorschlag.musterbrief.replace("{kanal}", kanal_datei)
