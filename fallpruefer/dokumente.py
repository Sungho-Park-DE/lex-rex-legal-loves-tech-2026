"""Getting document text into the case object — and nothing more.

A PDF is converted to page text *here*, locally, and only that text is ever
handed to the adapter. The PDF itself is never sent to a model (contract §4):
a page image carries the letterhead, the signature and the handwriting, none
of which the extraction needs and all of which L0 could not have tokenised.

Markdown test documents use a tiny convention so a fiction case is one file:
    ---            simple `key: value` front matter (no nesting)
    ---
    <!-- seite 1 -->  … page text …
    <!-- seite 2 -->  … page text …
A file with no page markers is a single page.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from fallpruefer.fall import Dokument, SeiteText
from fallpruefer.vokabular import Dokumenttyp, Quelle

_SEITE = re.compile(r"<!--\s*seite\s+(\d+)\s*-->")


_KOPFZEILE = re.compile(r"^[a-z][a-z0-9_]*:\s*\S")


def _frontmatter(roh: str) -> tuple[dict[str, str], str]:
    """Split off our own `key: value` front matter — and nothing else.

    A leading `---` is also what a PDF-to-markdown converter, a Word paste and
    a page separator produce. Taking the block between the first two `---` on
    faith discarded whole clauses of pasted documents before L0 ever saw them,
    with nothing on screen to say so, so the block counts as front matter only
    when **every** non-empty line in it is one of our keys.
    """
    if not roh.startswith("---"):
        return {}, roh
    teile = roh.split("---", 2)
    if len(teile) < 3:
        return {}, roh
    zeilen = [z for z in teile[1].strip().splitlines() if z.strip()]
    if not zeilen or not all(_KOPFZEILE.match(z.strip()) for z in zeilen):
        return {}, roh
    kopf: dict[str, str] = {}
    for zeile in zeilen:
        k, _, v = zeile.partition(":")
        kopf[k.strip()] = v.strip()
    return kopf, teile[2]


def seiten_aus_text(koerper: str) -> list[SeiteText]:
    if not _SEITE.search(koerper):
        return [SeiteText(nr=1, text_original=koerper.strip())]
    seiten: list[SeiteText] = []
    stuecke = _SEITE.split(koerper)
    # split() gives [vor, nr, text, nr, text, …]
    for i in range(1, len(stuecke), 2):
        seiten.append(SeiteText(nr=int(stuecke[i]), text_original=stuecke[i + 1].strip()))
    return seiten


def aus_markdown(pfad: Path, dok_id: str | None = None) -> Dokument:
    roh = pfad.read_text(encoding="utf-8")
    kopf, koerper = _frontmatter(roh)
    seiten = seiten_aus_text(koerper)
    # `dokumenttyp` in the front matter is the fiction case's *ground truth*,
    # not an input: the document enters as `sonstiges` so that L1 classify_doc
    # actually runs and can be scored against the truth in a golden test.
    bestaetigt = kopf.get("typ_bestaetigt", "").lower() == "true"
    return Dokument(
        dok_id=dok_id or kopf.get("dok_id") or pfad.stem,
        dokumenttyp=Dokumenttyp(kopf["dokumenttyp"]) if bestaetigt else Dokumenttyp.SONSTIGES,
        dokumenttyp_soll=kopf.get("dokumenttyp"),
        dateiname=kopf.get("dateiname") or pfad.name,
        hash=hashlib.sha256(roh.encode("utf-8")).hexdigest()[:16],
        seiten=seiten,
        quelle=Quelle(kopf.get("quelle", "verbraucher")),
        eingegangen=kopf.get("eingegangen", "eingang"),
        typ_bestaetigt=bestaetigt,
        fassung_datum=kopf.get("fassung_datum"),
    )


def aus_pdf(pfad: Path, dok_id: str) -> Dokument:
    """PDF → page text via pymupdf4llm, locally. The bytes stay here."""
    import pymupdf4llm

    seiten_roh = pymupdf4llm.to_markdown(str(pfad), page_chunks=True)
    seiten = [
        SeiteText(nr=i + 1, text_original=(s.get("text") or "").strip())
        for i, s in enumerate(seiten_roh)
    ]
    return Dokument(
        dok_id=dok_id,
        dokumenttyp=Dokumenttyp.SONSTIGES,  # L1 classify_doc decides
        dateiname=pfad.name,
        hash=hashlib.sha256(pfad.read_bytes()).hexdigest()[:16],
        seiten=seiten,
    )


def aus_freitext(text: str, dok_id: str, dateiname: str = "eingabe.txt") -> Dokument:
    """Text as it arrives over the API. If it carries the fiction-file front
    matter, only `fassung_datum` is lifted from it — the document type is
    deliberately NOT (that stays L1's job, with the advisor confirming)."""
    kopf, koerper = _frontmatter(text)
    return Dokument(
        dok_id=dok_id,
        dokumenttyp=Dokumenttyp.SONSTIGES,
        dateiname=dateiname,
        hash=hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        seiten=seiten_aus_text(koerper),
        fassung_datum=kopf.get("fassung_datum"),
    )


def laden(pfad: Path, dok_id: str | None = None) -> Dokument:
    if pfad.suffix.lower() == ".pdf":
        return aus_pdf(pfad, dok_id or pfad.stem)
    return aus_markdown(pfad, dok_id)
