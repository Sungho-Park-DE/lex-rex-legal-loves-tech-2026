"""Text normalisation — one definition, used everywhere a quote is compared.

Contract §4: quotes are verified against `text_pseudonym`, normalised by
whitespace collapse, soft hyphen removal, unified quotation marks and NFC.
The LLM adapter's validator, the cross-check primitives and the highlight
fallback all have to agree on what "the same span" means, so they all call
this. The *displayed* quote keeps the original characters — only the
comparison is normalised.
"""

from __future__ import annotations

import re
import unicodedata

_WEICHTRENN = "­"  # soft hyphen
_ANFUEHRUNG = {
    "„": '"', "“": '"', "”": '"', "»": '"', "«": '"', "‟": '"', "″": '"',
    "‚": "'", "‘": "'", "’": "'", "›": "'", "‹": "'",
}
_STRICHE = {"–": "-", "—": "-", "‐": "-", "‑": "-", "−": "-"}
_LEER = re.compile(r"\s+")


def normalisieren(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s).replace(_WEICHTRENN, "")
    for alt, neu in {**_ANFUEHRUNG, **_STRICHE}.items():
        s = s.replace(alt, neu)
    return _LEER.sub(" ", s).strip()


def enthaelt(haystack: str | None, nadel: str | None) -> bool:
    """Substring match in normalised space. This is the whole verification
    rule — no fuzzy matching, no edit distance. A quote either stands in the
    document or it does not."""
    n = normalisieren(nadel)
    return bool(n) and n in normalisieren(haystack)
