"""Ladder rung 6 — the Gesprächsleitfaden.

Some of what decides a Prüfpunkt is never on paper: did you actively agree, did
you keep going, how many months have you paid, do you want the money back.
`15` §2 carries those as `leitfaden_frage` on five Prüfpunkte and the engine
already read the fields they fill — nothing produced them, so those rules were
dead. These tests pin what answering does, expectations derived by hand from
`15` §1/§2 and `schemas/preiserhoehung.json`.
"""

from __future__ import annotations

import pytest

from fallpruefer import leitfaden as lf
from fallpruefer.konfig import WURZEL
from fallpruefer.pipeline import _schema_von, fall_aus_verzeichnis, leitfaden_antworten
from fallpruefer.vokabular import Badge, Herkunft

FAELLE = WURZEL / "demo" / "faelle"


def _fall(name: str, case_id: str):
    return fall_aus_verzeichnis(FAELLE / name, case_id)


def _zustand(fall, pruefpunkt_id: str) -> str:
    erg = next(e for e in fall.pruefungen[-1].ergebnisse
               if e.pruefpunkt_id == pruefpunkt_id)
    return erg.zustand.value


def _soll(fall) -> dict:
    d = fall.dokumenten_soll or {}
    return {
        "gefordert": list(d.get("gefordert") or []),
        "fehlt": [f.get("dokumenttyp") for f in (d.get("fehlt") or [])],
    }


# --------------------------------------------------------------------------
# which questions are worth asking
# --------------------------------------------------------------------------


def test_eine_frage_die_die_unterlagen_schon_beantworten_wird_nicht_gestellt():
    """The product is not the list of fourteen questions, it is which two of
    them still decide something.

    Derivation: the Drehkreuz contract carries the AGB-Einbeziehung, so
    `vertrag.agb_einbezogen_hinweis` already has a fact from a document. P2's
    question would ask the consumer something the file answers.
    """
    fall = _fall("drehkreuz", "F-LF1")
    fragen = {f.pruefpunkt_id: f for f in lf.fragen(fall, _schema_von(fall))}
    assert fragen["P2"].status == lf.ERUEBRIGT
    assert all(fragen[p].status == lf.OFFEN for p in ("P0", "P9", "P14", "P13"))


def test_offene_fragen_stehen_vor_den_erledigten():
    fall = _fall("drehkreuz", "F-LF2")
    status = [f.status for f in lf.fragen(fall, _schema_von(fall))]
    assert status == sorted(status, key=lambda s: lf._RANG[s])


def test_ein_strategiepunkt_bleibt_fragbar_obwohl_er_INAKTIV_ist():
    """P13 is `rolle: strategie` and therefore INAKTIV by construction
    (`18` #7) — it decides no verdict. Its answer still decides which remedy is
    proposed first (`rechtsbehelf.py`), so hiding the question because the
    Prüfpunkt is inactive would remove the only thing it is for."""
    fall = _fall("drehkreuz", "F-LF3")
    assert _zustand(fall, "P13") == "INAKTIV"
    frage = next(f for f in lf.fragen(fall, _schema_von(fall))
                 if f.pruefpunkt_id == "P13")
    assert frage.status == lf.OFFEN


# --------------------------------------------------------------------------
# answering
# --------------------------------------------------------------------------


def test_eine_antwort_bewegt_den_pruefpunkt_und_haengt_einen_lauf_an():
    """Derivation P14: `WERTUNG_wenn` is
    `{"feld": "gespraech.monate_erhoeht_gezahlt", "op": ">=", "wert": 6}`.
    Eight months ≥ 6 → WERTUNG. P14 is `ergaenzend`, so the Einordnung itself
    does not move — the Prüfumfang box gains the question instead, which is
    exactly what an ergänzender Punkt is for.
    """
    fall = _fall("drehkreuz", "F-LF4")
    assert _zustand(fall, "P14") == "JA"
    vorher = fall.pruefungen[-1].einordnung

    erg = leitfaden_antworten(fall, {"gespraech.monate_erhoeht_gezahlt": 8})

    assert _zustand(fall, "P14") == "WERTUNG"
    assert erg["einordnung"] == vorher
    assert [p.trigger for p in fall.pruefungen] == ["initial", "leitfaden_antwort"]
    assert fall.pruefungen[-1].aktuell and not fall.pruefungen[0].aktuell


def test_fuenf_monate_reichen_nicht_die_grenze_ist_streng():
    """The same rule at 5 — `>=` means six, not „about half a year"."""
    fall = _fall("drehkreuz", "F-LF5")
    leitfaden_antworten(fall, {"gespraech.monate_erhoeht_gezahlt": 5})
    assert _zustand(fall, "P14") == "JA"


def test_die_antwort_ist_ein_faktum_aus_dem_gespraech_kein_verifiziertes_zitat():
    """What someone says is not a quote checked against a document. The two
    axes carry that: `herkunft: gespraech` and `badge: angenommen` (yellow),
    never `verifiziert` (green)."""
    fall = _fall("drehkreuz", "F-LF6")
    leitfaden_antworten(fall, {"gespraech.weiternutzung_erfolgt": True})
    f = next(x for x in fall.fakten if x.feld_id == "gespraech.weiternutzung_erfolgt")
    assert f.herkunft == Herkunft.GESPRAECH
    assert f.badge == Badge.ANGENOMMEN
    assert f.verifiziert is None
    assert f.wert is True


def test_eine_korrigierte_antwort_ersetzt_die_alte_statt_sie_zu_verdoppeln():
    """A person who corrects themselves has not contradicted the file."""
    fall = _fall("drehkreuz", "F-LF7")
    leitfaden_antworten(fall, {"gespraech.monate_erhoeht_gezahlt": 8})
    leitfaden_antworten(fall, {"gespraech.monate_erhoeht_gezahlt": 2})
    treffer = [x for x in fall.fakten if x.feld_id == "gespraech.monate_erhoeht_gezahlt"]
    assert len(treffer) == 1 and treffer[0].wert == 2
    assert _zustand(fall, "P14") == "JA"


# --------------------------------------------------------------------------
# the conditional Soll
# --------------------------------------------------------------------------


def test_wer_geld_zurueck_will_muss_den_kontoauszug_nachreichen():
    """`15` §2 files the Kontoauszug as `pflicht: bedingt` on
    `{"feld": "gespraech.rueckforderung_gewuenscht", "op": "==", "wert": true}`.
    `soll.py` has always evaluated that condition; nothing ever set the field,
    so the branch was dead. Answering the Leitfaden is what makes a document
    appear in the Gate-1 Nachforderung.
    """
    fall = _fall("drehkreuz", "F-LF8")
    assert "kontoauszug" not in _soll(fall)["gefordert"]

    leitfaden_antworten(fall, {"gespraech.rueckforderung_gewuenscht": True})

    nachher = _soll(fall)
    assert "kontoauszug" in nachher["gefordert"]
    assert "kontoauszug" in nachher["fehlt"]


# --------------------------------------------------------------------------
# the conversation contradicts the file
# --------------------------------------------------------------------------


def test_widerspricht_die_antwort_der_unterlage_wird_markiert_nicht_entschieden():
    """The Drehkreuz contract says the AGB were included; the consumer says
    they never got them. Which of the two is right is a judgement, and
    judgements belong to the advisor at Gate 3 (`18` #9 semantics, reused).

    Derivation: both facts go `strittig`, so `Fallkontext.feld()` returns None
    (`evaluator.py`: a fact with `verifiziert is False` is not a value). P2's
    `WERTUNG_wenn` contains `{"fehlt": "vertrag.agb_einbezogen_hinweis"}`,
    which is then true → P2 moves from JA to WERTUNG.
    """
    fall = _fall("drehkreuz", "F-LF9")
    assert _zustand(fall, "P2") == "JA"
    aus_der_akte = [x for x in fall.fakten
                    if x.feld_id == "vertrag.agb_einbezogen_hinweis"]
    assert [x.wert for x in aus_der_akte] == [True]

    erg = leitfaden_antworten(fall, {"vertrag.agb_einbezogen_hinweis": False})

    assert erg["strittig"] == ["vertrag.agb_einbezogen_hinweis"]
    beide = [x for x in fall.fakten if x.feld_id == "vertrag.agb_einbezogen_hinweis"]
    assert len(beide) == 2
    assert all(x.herkunft == Herkunft.STRITTIG and x.verifiziert is False
               for x in beide), "eine Seite wurde stillschweigend zur Wahrheit erklärt"
    assert _zustand(fall, "P2") == "WERTUNG"


def test_dieselbe_antwort_wie_die_unterlage_ist_kein_widerspruch():
    fall = _fall("drehkreuz", "F-LF10")
    erg = leitfaden_antworten(fall, {"vertrag.agb_einbezogen_hinweis": True})
    assert erg["strittig"] == []
    assert _zustand(fall, "P2") == "JA"


# --------------------------------------------------------------------------
# the whitelist — this endpoint must not become fact injection
# --------------------------------------------------------------------------


def test_ein_feld_das_keine_leitfaden_frage_fuellt_wird_abgewiesen():
    fall = _fall("drehkreuz", "F-LF11")
    with pytest.raises(lf.LeitfadenFehler, match="kein Leitfaden-Feld"):
        leitfaden_antworten(fall, {"agb.preisklausel_text": "was ich gern hätte"})
    assert not any(x.herkunft == Herkunft.GESPRAECH for x in fall.fakten)


@pytest.mark.parametrize("feld,wert", [
    ("gespraech.monate_erhoeht_gezahlt", "viele"),
    ("gespraech.weiternutzung_erfolgt", "vielleicht"),
    ("gespraech.strategie", "auswandern"),
])
def test_ein_wert_der_nicht_zum_fragetyp_passt_wird_abgewiesen(feld, wert):
    """Refused, not coerced — the same rule the adapter's validator follows:
    a value the schema cannot use is not a value."""
    fall = _fall("drehkreuz", "F-LF12")
    with pytest.raises(lf.LeitfadenFehler):
        leitfaden_antworten(fall, {feld: wert})


def test_eine_mehrfachantwort_akzeptiert_nur_die_vorgesehenen_werte():
    fall = _fall("drehkreuz", "F-LF13")
    leitfaden_antworten(fall, {"gespraech.strategie": "kuendigen"})
    f = next(x for x in fall.fakten if x.feld_id == "gespraech.strategie")
    assert f.wert == "kuendigen"


def test_eine_abgewiesene_antwort_hinterlaesst_keinen_lauf():
    """A rejected answer must not append a run: the audit trail would then
    carry an assessment nobody asked for."""
    fall = _fall("drehkreuz", "F-LF14")
    vorher = len(fall.pruefungen)
    with pytest.raises(lf.LeitfadenFehler):
        leitfaden_antworten(fall, {"gespraech.strategie": "auswandern"})
    assert len(fall.pruefungen) == vorher


def test_eine_abgewiesene_antwort_schreibt_auch_die_gueltige_daneben_nicht():
    """Half-applied input is the one failure mode a case file must not have.

    A batch with one good and one bad answer used to leave the good one
    written as a fact and logged as an event, while the rejection stopped the
    re-run — so the case carried a `gespraech` fact that no assessment had
    used, and the verdict on screen was computed without it. Found by asking
    what happens between the first and the second answer of a batch.
    """
    fall = _fall("drehkreuz", "F-LF15")
    with pytest.raises(lf.LeitfadenFehler):
        leitfaden_antworten(fall, {
            "gespraech.monate_erhoeht_gezahlt": 8,      # gültig
            "gespraech.strategie": "auswandern",        # ungültig
        })
    assert not [x for x in fall.fakten if x.herkunft == Herkunft.GESPRAECH]
    assert not [e for e in fall.ereignisse if e.aktion == "leitfaden_antwort"]
    assert [p.trigger for p in fall.pruefungen] == ["initial"]
