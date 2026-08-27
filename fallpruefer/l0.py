"""L0 — deterministic pseudonymisation, before any LLM sees anything.

Contract 14 §3 / 15 §4. Identities become tokens; facts stay. Dates, amounts
and clause wording are the substance of the case and are never touched — only
who someone is. The map lives in the case object and is never passed to any
LLM call; re-identification happens locally in exactly two places, the advisor
display and the template fill.

Token syntax `@@TYP_N@@` is deliberately distinct from letter placeholders
`[GROSSBUCHSTABEN]` so a leaked token can never be mistaken for an unfilled
placeholder, and so a regex for one never matches the other.

Rollout note (14 §3): local NER later. Today the sources are the ticket's
structured fields plus a short list of unambiguous regexes — a generic
name/address matcher would produce false positives on clause text, which is
the one thing that must survive intact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from fallpruefer.fall import Identitaet

TOKEN = re.compile(r"@@[A-Z]+_\d+@@")

_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}[ ]?[A-Z0-9]{1,4}\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_TELEFON = re.compile(r"(?<![\d.])(?:\+49[ /-]?|0)\d{2,5}[ /-]?\d{3,9}(?![\d.])")
_KUNDENNR = re.compile(
    r"(?:Kunden(?:nummer|nr\.?)|Mitglieds(?:nummer|nr\.?)|Vertragsnummer)[:\s]*([A-Z0-9][A-Z0-9/-]{3,})",
    re.IGNORECASE,
)
_GEBURTSDATUM = re.compile(r"(?:geb\.|geboren am)[:\s]*(\d{1,2}\.\d{1,2}\.\d{4})")


@dataclass
class Pseudonymisierer:
    """Builds a token map and applies it. Same input → same tokens, always."""

    whitelist: tuple[str, ...] = ()
    karte: dict[str, str] = field(default_factory=dict)  # token -> Klartext
    _rueck: dict[str, str] = field(default_factory=dict)  # Klartext -> token
    _zaehler: dict[str, int] = field(default_factory=dict)

    def token_fuer(self, typ: str, klartext: str) -> str:
        klartext = klartext.strip()
        if klartext in self._rueck:
            return self._rueck[klartext]
        self._zaehler[typ] = self._zaehler.get(typ, 0) + 1
        token = f"@@{typ}_{self._zaehler[typ]}@@"
        self.karte[token] = klartext
        self._rueck[klartext] = token
        return token

    # -- building the map ---------------------------------------------------

    def aus_identitaet(self, ident: Identitaet) -> None:
        """The ticket's structured fields are the reliable source — a name we
        were *told* beats a name we guessed out of running text."""
        if ident.name:
            self.token_fuer("PERSON", ident.name)
            teile = ident.name.split()
            if len(teile) >= 2:
                # „Frau Maier" and „I. Maier" must not survive just because the
                # full name did not appear literally. Each surface form gets its
                # OWN token: the map is token → the exact string that stood
                # there, so de-tokenising restores the document character for
                # character. Sharing one token across forms would put a first
                # name into a sentence that never had one, and a quote carrying
                # the short form would stop being findable in text_original.
                self.token_fuer("PERSON", teile[-1])
                self.token_fuer("PERSON", f"{teile[0][0]}. {teile[-1]}")
        if ident.adresse:
            # one token per component, so the round trip is exact whether the
            # document writes the address on one line or three
            for teil in re.split(r"[,\n]", ident.adresse):
                teil = teil.strip()
                if len(teil) >= 4:
                    self.token_fuer("ADRESSE", teil)
        if ident.email:
            self.token_fuer("EMAIL", ident.email)
        if ident.telefon:
            self.token_fuer("TELEFON", ident.telefon)
        if ident.kundennummer:
            self.token_fuer("KUNDENNR", ident.kundennummer)
        if ident.geburtsdatum:
            self.token_fuer("GEBURTSDATUM", ident.geburtsdatum)

    def aus_text(self, text: str) -> None:
        for treffer in _IBAN.findall(text):
            self.token_fuer("IBAN", treffer)
        for treffer in _EMAIL.findall(text):
            self.token_fuer("EMAIL", treffer)
        for treffer in _KUNDENNR.findall(text):
            self.token_fuer("KUNDENNR", treffer)
        for treffer in _GEBURTSDATUM.findall(text):
            self.token_fuer("GEBURTSDATUM", treffer)
        for treffer in _TELEFON.findall(text):
            if sum(c.isdigit() for c in treffer) >= 7:
                self.token_fuer("TELEFON", treffer)

    # -- applying it --------------------------------------------------------

    def anwenden(self, text: str) -> str:
        """Longest first, so „Lindenstraße 12" is replaced before „12" could be."""
        if not text:
            return text
        for klartext in sorted(self._rueck, key=len, reverse=True):
            if self._ist_whitelist(klartext):
                continue
            token = self._rueck[klartext]
            if re.fullmatch(r"[\w.äöüÄÖÜß-]+", klartext):
                text = re.sub(rf"(?<!\w){re.escape(klartext)}(?!\w)", token, text)
            else:
                text = text.replace(klartext, token)
        return text

    def zurueck(self, text: str) -> str:
        """De-tokenise for the advisor display and the template fill."""
        if not text:
            return text
        for token, klartext in self.karte.items():
            text = text.replace(token, klartext)
        return text

    def _ist_whitelist(self, klartext: str) -> bool:
        return any(w and w.strip() and w.strip() == klartext for w in self.whitelist)


def sensible_inhalte(text: str, keywords: list[str]) -> bool:
    """Art. 9 DSGVO tripwire — an advisor notice, never an automatic action."""
    unten = text.lower()
    return any(k.lower() in unten for k in keywords)
