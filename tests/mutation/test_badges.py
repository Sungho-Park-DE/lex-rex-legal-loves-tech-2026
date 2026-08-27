"""Badges und Herkunft — the worst-wins aggregation, pinned.

Contract §5 lists `badge` and `herkunft` as engine-produced per Prüfpunkt but
fixes no precedence for them; the rule was decided while building rung 1 and
written down in `18` §1 #2 (badges) and #4 (provenance), and
`vokabular.BADGE_RANG` / `HERKUNFT_RANG` are its implementation. Nine mutations
of those two tables — and of the empty-list default of `schlimmste_herkunft` —
survived the whole suite, five of them without changing a single demo row,
because nothing anywhere asserted the order.

The two orders below are typed out **by hand from `18` §1**, deliberately not
imported from the module under test: a test that read `BADGE_RANG` to build its
expectation would agree with every mutation of `BADGE_RANG`.

Each order is checked pairwise **in both list orders**, because
`schlimmster_badge` resolves ties by `min`'s first-wins rule: a mutation that
merely makes two ranks equal stays invisible if the worse badge happens to be
listed first.

The end-to-end tests at the bottom use the Drehkreuz case
(`demo/faelle/drehkreuz/`) and derive their expectation from
`schemas/preiserhoehung.json` plus the three documents of the case; the
derivation is written into each test.
"""

from __future__ import annotations

import pytest

from fallpruefer.konfig import WURZEL
from fallpruefer.pipeline import fall_aus_verzeichnis
from fallpruefer.vokabular import (
    Badge,
    Herkunft,
    Zustand,
    schlimmste_herkunft,
    schlimmster_badge,
)

# --------------------------------------------------------------------------
# the two documented orders — hand-copied from 18 §1, worst first
# --------------------------------------------------------------------------

# 18 §1 #2: „Worst-wins über die verwendeten Fakten:
#   kreuzpruefung_fehlgeschlagen > nicht_gefunden > normbasis_fehlt >
#   anker_ungeprueft > llm_befund > angenommen > verifiziert"
BADGE_SCHLIMMSTE_ZUERST = [
    Badge.KREUZPRUEFUNG_FEHLGESCHLAGEN,
    Badge.NICHT_GEFUNDEN,
    Badge.NORMBASIS_FEHLT,
    Badge.ANKER_UNGEPRUEFT,
    Badge.LLM_BEFUND,
    Badge.ANGENOMMEN,
    Badge.VERIFIZIERT,
]

# 18 §1 #4: „Worst-wins über die verwendeten Fakten:
#   strittig > fehlt > angenommen > override > gespraech > explizit;
#   keine Fakten -> fehlt"
HERKUNFT_SCHLIMMSTE_ZUERST = [
    Herkunft.STRITTIG,
    Herkunft.FEHLT,
    Herkunft.ANGENOMMEN,
    Herkunft.OVERRIDE,
    Herkunft.GESPRAECH,
    Herkunft.EXPLIZIT,
]


def _paare(ordnung):
    """Every (worse, better) pair of a worst-first order."""
    for i, schlimmer in enumerate(ordnung):
        for besser in ordnung[i + 1:]:
            yield schlimmer, besser


# --------------------------------------------------------------------------
# the orders themselves
# --------------------------------------------------------------------------


def test_schlimmster_badge_haelt_die_dokumentierte_reihenfolge_paarweise():
    """Both list orders: `min` keeps the first element on a tie, so a mutation
    that only equalises two ranks would otherwise slip through half the time."""
    assert len(set(BADGE_SCHLIMMSTE_ZUERST)) == len(Badge), "Badge-Vokabular hat sich geändert"
    for schlimmer, besser in _paare(BADGE_SCHLIMMSTE_ZUERST):
        assert schlimmster_badge([schlimmer, besser]) is schlimmer, f"{schlimmer} vs {besser}"
        assert schlimmster_badge([besser, schlimmer]) is schlimmer, f"{besser} vs {schlimmer}"


def test_schlimmste_herkunft_haelt_die_dokumentierte_reihenfolge_paarweise():
    assert len(set(HERKUNFT_SCHLIMMSTE_ZUERST)) == len(Herkunft), "Herkunft-Vokabular hat sich geändert"
    for schlimmer, besser in _paare(HERKUNFT_SCHLIMMSTE_ZUERST):
        assert schlimmste_herkunft([schlimmer, besser]) is schlimmer, f"{schlimmer} vs {besser}"
        assert schlimmste_herkunft([besser, schlimmer]) is schlimmer, f"{besser} vs {schlimmer}"


# --------------------------------------------------------------------------
# M4 — the empty-list default
# --------------------------------------------------------------------------


def test_ohne_verwendete_fakten_ist_die_herkunft_fehlt():
    """18 §1 #4, last clause: „keine Fakten -> `fehlt`".

    A Prüfpunkt that read no fact at all has nothing documented, so its trace
    row must say „nicht belegt" (gelb) and not „im Dokument belegt" (grün).
    `explizit` here would be the engine claiming a document proves a point for
    which no document was ever read."""
    assert schlimmste_herkunft([]) is Herkunft.FEHLT


# --------------------------------------------------------------------------
# M7 / M8 / M9 / M10 / M11 — the badge pairs, one test per decided relation
# --------------------------------------------------------------------------


def test_llm_befund_ueberstimmt_ein_verifiziertes_zitat():
    """Contract §2 note (iii) — „für `typ: text` Prüfpunkte trägt das Ergebnis
    `llm_befund: true`" — and the §4 example renders exactly that combination
    as `{"pruefpunkt_id": "P6", "zustand": "JA", "llm_befund": true,
    "badge": "llm_befund"}`: a text judgement whose inputs are verified quotes
    still shows the yellow „bitte prüfen" chip, never a green one. If
    `verifiziert` could win here the chip would vanish from every `typ: text`
    Prüfpunkt (P4/P6/P7) that also has one verified fact."""
    assert schlimmster_badge([Badge.VERIFIZIERT, Badge.LLM_BEFUND]) is Badge.LLM_BEFUND


def test_eine_annahme_ueberstimmt_ein_verifiziertes_zitat():
    """18 §1 #2 (`angenommen` before `verifiziert`) and 18 §3 #22: P10 carries
    `badge: angenommen`, not `verifiziert`, because its Zugangsdatum comes from
    the `zugang_plus_3` Annahme. An assumption that presents itself as read off
    the document is the one thing the Fristenrechnung must not do."""
    assert schlimmster_badge([Badge.VERIFIZIERT, Badge.ANGENOMMEN]) is Badge.ANGENOMMEN


def test_llm_befund_ist_schlimmer_als_eine_annahme():
    """18 §1 #2, `llm_befund` before `angenommen`. Latent in the current schema
    (no `typ: text` Prüfpunkt reads a field an Annahme fills), which is exactly
    why it needs a unit test: it goes live with the first Annahme on a clause
    field or with the second Fallgruppe."""
    assert schlimmster_badge([Badge.LLM_BEFUND, Badge.ANGENOMMEN]) is Badge.LLM_BEFUND
    assert schlimmster_badge([Badge.ANGENOMMEN, Badge.LLM_BEFUND]) is Badge.LLM_BEFUND


def test_kreuzpruefung_fehlgeschlagen_schlaegt_jeden_anderen_badge():
    """18 §1 #2 puts `kreuzpruefung_fehlgeschlagen` at the head of the order:
    a letter citing a Ziffer that is not in the AGB is the worst thing the
    trust layer can find, so it wins over everything, in any list order."""
    for anderer in Badge:
        if anderer is Badge.KREUZPRUEFUNG_FEHLGESCHLAGEN:
            continue
        assert schlimmster_badge(
            [anderer, Badge.KREUZPRUEFUNG_FEHLGESCHLAGEN]
        ) is Badge.KREUZPRUEFUNG_FEHLGESCHLAGEN, anderer
        assert schlimmster_badge(
            [Badge.KREUZPRUEFUNG_FEHLGESCHLAGEN, anderer]
        ) is Badge.KREUZPRUEFUNG_FEHLGESCHLAGEN, anderer


def test_normbasis_fehlt_ist_schlimmer_als_ein_ungepruefter_anker():
    """18 §1 #2, `normbasis_fehlt` before `anker_ungeprueft`. The distinction is
    substantive: a norm we do not carry at all (rot, §6) outranks a Fundstelle
    that is merely not resolved in dev mode (neutral)."""
    assert schlimmster_badge(
        [Badge.ANKER_UNGEPRUEFT, Badge.NORMBASIS_FEHLT]
    ) is Badge.NORMBASIS_FEHLT
    assert schlimmster_badge(
        [Badge.NORMBASIS_FEHLT, Badge.ANKER_UNGEPRUEFT]
    ) is Badge.NORMBASIS_FEHLT


# --------------------------------------------------------------------------
# M12 / M13 / M16 — the provenance pairs
# --------------------------------------------------------------------------


def test_eine_annahme_ueberstimmt_einen_belegten_wert():
    """18 §1 #4, `angenommen` before `explizit`. Same damage as the badge case
    on the provenance axis: P10's assumed Zugangsdatum must not report itself
    as „im Dokument belegt" while the Vorlaufzeit-Frist is built on it."""
    assert schlimmste_herkunft([Herkunft.EXPLIZIT, Herkunft.ANGENOMMEN]) is Herkunft.ANGENOMMEN


def test_ein_override_ist_schlimmer_als_gespraech_und_beleg():
    """18 §1 #4, `override` before `gespraech` and `explizit`. Dead today (an
    override is set on the Pruefergebnis, never on a Faktum) and alive the
    moment Gate 3 may set a *field*: a Beraterin-set value would then outrank a
    verified quote and the row would read „im Dokument belegt"."""
    assert schlimmste_herkunft([Herkunft.GESPRAECH, Herkunft.OVERRIDE]) is Herkunft.OVERRIDE
    assert schlimmste_herkunft([Herkunft.EXPLIZIT, Herkunft.OVERRIDE]) is Herkunft.OVERRIDE


def test_fehlt_ist_schlimmer_als_jede_vorhandene_herkunft_ausser_strittig():
    """18 §1 #4 puts `fehlt` second, behind `strittig` only — so a mixed
    Prüfpunkt with one missing input reports „nicht belegt", not the provenance
    of whichever sibling happened to be there."""
    for besser in (Herkunft.ANGENOMMEN, Herkunft.OVERRIDE, Herkunft.GESPRAECH, Herkunft.EXPLIZIT):
        assert schlimmste_herkunft([besser, Herkunft.FEHLT]) is Herkunft.FEHLT, besser
        assert schlimmste_herkunft([Herkunft.FEHLT, besser]) is Herkunft.FEHLT, besser
    assert schlimmste_herkunft([Herkunft.FEHLT, Herkunft.STRITTIG]) is Herkunft.STRITTIG


# --------------------------------------------------------------------------
# the same rules where the advisor actually sees them
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def drehkreuz():
    """The Drehkreuz case, run through the pipeline; `{pruefpunkt_id: ergebnis}`.

    Cache-only (no ANTHROPIC_API_KEY), and `fall_aus_verzeichnis` writes
    nothing to `store/`."""
    fall = fall_aus_verzeichnis(WURZEL / "demo" / "faelle" / "drehkreuz", "F-MUT-BADGES")
    return {e.pruefpunkt_id: e for e in fall.aktuelle_pruefung().ergebnisse}


def test_P11_ohne_kostenkalkulation_meldet_keine_belegte_herkunft(drehkreuz):
    """Derivation, by hand:

    P11 (`schemas/preiserhoehung.json`) has exactly one eingabe,
    `kostenkalkulation.vorhanden` (`pflicht: false`), and the regel
    `{"WERTUNG_wenn": {"dok_vorhanden": "kostenkalkulation"}, "sonst": "FEHLT"}`.
    `demo/faelle/drehkreuz/ticket.json` lists three attachments — schreiben.md,
    agb.md, vertrag.md — and no Kostenkalkulation, so `dok_vorhanden` is false
    and the Prüfpunkt is FEHLT (P11's own `pruefumfang_text` says as much:
    „dazu fehlt die Kostenkalkulation des Studios").

    `<typ>.vorhanden` is a statement about the document, not a field inside one,
    so no Faktum carries it and the Prüfpunkt used no fact at all. 18 §1 #4:
    no facts -> `fehlt`. 18 §1 #3: no facts -> no badge (`null`) — „Zitat
    verifiziert" next to a FEHLT would be a lie."""
    p11 = drehkreuz["P11"]
    assert p11.zustand is Zustand.FEHLT
    assert p11.herkunft is Herkunft.FEHLT
    assert p11.badge is None


def test_P6_traegt_llm_befund_obwohl_alle_zitate_verifiziert_sind(drehkreuz):
    """Derivation, by hand:

    P6 is `typ: text`, so contract §2 note (iii) gives the result
    `llm_befund: true` and the engine adds `Badge.LLM_BEFUND` to the pot. Its
    three eingaben — `agb.nennt_anlass`, `agb.nennt_voraussetzungen`,
    `agb.nennt_umfang` — are all read from Ziffer 5.2 of `agb.md` („Der
    Betreiber ist berechtigt, den monatlichen Beitrag anzupassen. …"), which
    names neither Anlass nor Voraussetzungen nor Umfang; per §2 note (i) a
    `false` value still carries the examined span, so those facts are
    `verifiziert` and contribute `Badge.VERIFIZIERT`.

    Worst-wins over {verifiziert, verifiziert, verifiziert, llm_befund}
    (18 §1 #2) -> `llm_befund`. That is 18 §3 #21's „three LLM findings flagged
    for the advisor" beat; a green chip here would delete it silently.

    The state follows the same three facts: all three false + the clause span
    verified fires `NEIN_wenn` -> NEIN."""
    p6 = drehkreuz["P6"]
    assert p6.zustand is Zustand.NEIN
    assert p6.llm_befund is True
    assert p6.badge is Badge.LLM_BEFUND


def test_P10_traegt_die_annahme_und_nicht_das_verifizierte_zitat(drehkreuz):
    """Derivation, by hand:

    P10 is `typ: fakt` (so no `llm_befund` in the pot) and reads six fields of
    the Erhöhungsschreiben plus `agb.kuendigungsrecht_bei_erhoehung`.
    `demo/faelle/drehkreuz/schreiben.md` is dated „München, 20.07.2026" and
    names no date of receipt anywhere, so `erhoehungsschreiben.zugang` cannot
    be extracted and the schema's `annahmen` entry `zugang_plus_3`
    (`"wert": "datum_plus(erhoehungsschreiben.datum, 3)"`) fills it — an
    assumed value, i.e. `herkunft: angenommen` / `badge: angenommen`. The other
    inputs are read off the letter and the AGB, i.e. `explizit`/`verifiziert`.

    Worst-wins (18 §1 #2 and #4) over {verifiziert…, angenommen} and
    {explizit…, angenommen} -> `angenommen` on both axes. This is 18 §3 #22
    verbatim, and it is what keeps the Vorlaufzeit — the one number a
    Widerspruchsbrief depends on — from presenting itself as documented."""
    p10 = drehkreuz["P10"]
    assert p10.llm_befund is False
    assert p10.badge is Badge.ANGENOMMEN
    assert p10.herkunft is Herkunft.ANGENOMMEN
