"""The path from a law student's answer to a gating golden test.

`15` §13 promises Franz' Lösungszettel is a „drop-in path (no code)". It was
not: no ingest existed, the P-ID mapping lived only as a prose table, and the
contract's assumed numbering (P0–P14) matched neither his old nor his new list.

The fix is a pair — `tools/loesungszettel_vorlage.py` generates the form from
the Prüfschema, `tools/loesungszettel.py` reads the same shape back — and these
tests pin the three properties that make the pair worth having:

1. the form can only be filled in the engine's vocabulary, so nothing has to be
   translated afterwards (his numbering and his verdict words both differ from
   ours, in ways that would corrupt the result silently);
2. a half-filled form is refused, loudly, instead of becoming a golden file
   that reports OK for a case nobody checked;
3. the round trip actually produces a golden the runner accepts.
"""

from __future__ import annotations

import json
import re
import sys

import pytest

from fallpruefer import golden
from fallpruefer.konfig import WURZEL
from fallpruefer.schema import schema_laden

sys.path.insert(0, str(WURZEL))
from tools import loesungszettel, loesungszettel_vorlage  # noqa: E402

SEEPARK = "seepark_seite_fehlt"


def _vorlage() -> str:
    return loesungszettel_vorlage.bauen("preiserhoehung", 1)


def _block(vorlage: str) -> str:
    return vorlage[vorlage.index("## Fall 1"):vorlage.index("## Wenn der Fall")]


def _fuellen(block: str, *, kennung: str, stufe: str, dokumente: list[str], einordnung: str,
             gruende: tuple[str, ...] = (), pruefpunkte: tuple[str, ...] = (),
             fehlt: tuple[str, ...] = (), rechtsbehelf: str | None = None,
             kipp: str = "", warum: str = "") -> str:
    b = block.replace("`<kurzer_name_ohne_leerzeichen>`", f"`{kennung}`")
    b = b.replace("**Stufe:** `initial`", f"**Stufe:** `{stufe}`")
    b = b.replace("**Unterlagen:**", f"**Unterlagen:** {', '.join(dokumente)}")
    b = b.replace(f"- [ ] **`{einordnung}`**", f"- [x] **`{einordnung}`**")
    for g in gruende:
        b = b.replace(f"- [ ] Es {g}", f"- [x] Es {g}")
    for p in pruefpunkte:
        b = re.sub(rf"- \[ \] \*\*{p}\*\* —", f"- [x] **{p}** —", b)
    for d in fehlt:
        b = b.replace(f"- [ ] `{d}` —", f"- [x] `{d}` —")
    if rechtsbehelf:
        b = b.replace(f"- [ ] `{rechtsbehelf}` —", f"- [x] `{rechtsbehelf}` —")
    b = b.replace("**Kipp-Punkt:**", f"**Kipp-Punkt:** {kipp}")
    b = b.replace("**Warum:**", f"**Warum:** {warum}")
    return b


def _seepark_zettel() -> str:
    """The Seepark case as Franz would fill it: unklar because a page of the
    Bedingungen is missing, then `wirksam` once it arrives. We derived the same
    answer independently by hand, which is what makes it a usable fixture."""
    v = _vorlage()
    b = _block(v)
    initial = _fuellen(
        b, kennung=SEEPARK, stufe="initial",
        dokumente=["schreiben.md", "vertrag.md", "bedingungen_seite1.md"],
        einordnung="unklar – es fehlt …", gruende=("fehlt eine **Unterlage**",),
        fehlt=("agb",), rechtsbehelf="nachforderung",
    )
    nach = _fuellen(
        b, kennung=SEEPARK, stufe="nachreichung",
        dokumente=["schreiben.md", "vertrag.md", "bedingungen_seite1.md",
                   "bedingungen_seite2_nachgereicht.md"],
        einordnung="wirksam", rechtsbehelf="kuendigung_bei_wirksam",
    )
    return v[:v.index("## Fall 1")] + initial + nach


# --------------------------------------------------------------------------
# the form
# --------------------------------------------------------------------------


def test_die_vorlage_kommt_aus_dem_schema_und_kann_nicht_veralten():
    """Every Prüfpunkt, Unterlagenart and Rechtsbehelf on the form is read from
    the schema file. A Jurist-Edit that adds a Prüfpunkt changes the form the
    next time it is generated — nobody has to remember to update it."""
    from fallpruefer.vokabular import Rolle

    schema = schema_laden("preiserhoehung")
    v = _vorlage()
    # Everything the advisor actually answers. `ableitung` (P12, the legal
    # consequences) and `strategie` (P13, „what does the person want next") are
    # derived by the engine and are not questions for a Lösungszettel.
    befragbar = [p for p in schema.pruefpunkte
                 if p.rolle in (Rolle.TRAGEND, Rolle.ERGAENZEND, Rolle.GATE)]
    assert len(befragbar) == 17  # 14 + P8c (§ 309 Nr. 13 lit. b) + P8d (Laufzeit aus P8 gelöst), 24 Aug; + P1a (Fall 6, V-G1), 25 Aug
    for p in befragbar:
        assert f"**{p.id}** — {p.titel}" in v, p.id
    for p in schema.pruefpunkte:
        if p.rolle in (Rolle.ABLEITUNG, Rolle.STRATEGIE):
            assert f"**{p.id}**" not in v, f"{p.id} gehört nicht auf den Zettel"
    for d in schema.dokumenten_soll.dokumente:
        assert d.anzeigename in v, d.dokumenttyp.value
    for r in schema.rechtsbehelfe.liste:
        assert f"`{r.id}`" in v, r.id
    assert schema.version in v and schema.stand in v


def test_die_vorlage_fragt_keine_nummer_und_druckt_unsere_drei_woerter():
    """Two of his three problems disappear by construction. His numbering is
    inconsistent even against his own list, so the form asks for P-IDs; and his
    `wahrscheinlich_unwirksam` means our `unklar`, so the form prints our three
    strings verbatim with the distinction spelled out."""
    v = _vorlage()
    assert "**`wirksam`**" in v
    assert "**`wahrscheinlich unwirksam`**" in v
    assert "**`unklar – es fehlt …`**" in v
    # his fourth word must not appear as an option anywhere
    assert not re.search(r"^\s*-\s*\[ \]\s*\*\*`unwirksam`\*\*", v, re.M)
    # and the form asks for the full set, not the one point the case turns on
    assert "Bitte **alle** ankreuzen" in v


# --------------------------------------------------------------------------
# reading it back
# --------------------------------------------------------------------------


def test_ein_ausgefuellter_zettel_wird_ein_gating_golden(tmp_path):
    quelle = tmp_path / "zettel.md"
    quelle.write_text(_seepark_zettel(), encoding="utf-8")

    dateien, fehler = loesungszettel.lesen(quelle, "preiserhoehung")
    assert not fehler, fehler
    daten = dateien[SEEPARK]

    assert daten["geprueft"] is True and daten["gating"] is True
    assert daten["fall_verzeichnis"] == f"demo/faelle/{SEEPARK}"
    assert [s["name"] for s in daten["stufen"]] == ["initial", "nachreichung"]
    assert [s["erwartet"]["einordnung"] for s in daten["stufen"]] == [
        "unklar – es fehlt …", "wirksam"
    ]


def test_die_unternehmensseite_kommt_aus_dem_schema_nicht_vom_zettel(tmp_path):
    """`fehlt` always carries what the company owes — a `pflicht: hinweis`
    document is open in every case by design (18 #29). Asking a law student for
    it would be asking for a property of the Dokumenten-Soll, so the tool fills
    it from the schema and the file says which rows came from where."""
    quelle = tmp_path / "zettel.md"
    quelle.write_text(_seepark_zettel(), encoding="utf-8")
    daten = loesungszettel.lesen(quelle, "preiserhoehung")[0][SEEPARK]

    erste = daten["stufen"][0]["erwartet"]["fehlt"]
    assert {"dokumenttyp": "agb", "quelle": "verbraucher"} in erste          # von ihm
    assert {"dokumenttyp": "kostenkalkulation", "quelle": "unternehmen"} in erste  # aus dem Schema
    # and it stays there once the consumer side is closed
    zweite = daten["stufen"][1]["erwartet"]["fehlt"]
    assert zweite == [{"dokumenttyp": "kostenkalkulation", "quelle": "unternehmen"}]
    assert "Dokumenten-Soll" in daten["kommentar"]


def test_das_erzeugte_golden_laeuft_gegen_die_engine(tmp_path):
    """The whole point: a form filled by hand becomes a test the engine runs.
    Seepark is the counter-proof case — it flips *to* `wirksam` — so this also
    pins that a Lösungszettel can express a two-stage case."""
    quelle = tmp_path / "zettel.md"
    quelle.write_text(_seepark_zettel(), encoding="utf-8")
    ziel = tmp_path / "golden"
    ziel.mkdir()
    dateien, _ = loesungszettel.lesen(quelle, "preiserhoehung")
    (ziel / f"{SEEPARK}.json").write_text(
        json.dumps(dateien[SEEPARK], ensure_ascii=False, indent=2), encoding="utf-8")

    erg = golden.lauf(ziel / f"{SEEPARK}.json")
    assert erg.gruen, "\n" + golden.bericht([erg])
    assert erg.gating and erg.falsche_sichere_antworten == 0


def test_ein_duenner_zettel_sieht_nicht_aus_wie_ein_voller(tmp_path):
    """A Lösungszettel that only states the Einordnung passes one comparison
    and reports OK — which reads exactly like a case that passed all eight.
    The coverage count is the difference between „green" and „checked"."""
    quelle = tmp_path / "zettel.md"
    quelle.write_text(_seepark_zettel(), encoding="utf-8")
    ziel = tmp_path / "golden"
    ziel.mkdir()
    dateien, _ = loesungszettel.lesen(quelle, "preiserhoehung")
    (ziel / f"{SEEPARK}.json").write_text(
        json.dumps(dateien[SEEPARK], ensure_ascii=False, indent=2), encoding="utf-8")

    aus_zettel = golden.lauf(ziel / f"{SEEPARK}.json")
    von_hand = golden.lauf(WURZEL / "tests" / "golden" / f"{SEEPARK}.json")

    zettel_deckung = sum(n for _, n in aus_zettel.abdeckung)
    hand_deckung = sum(n for _, n in von_hand.abdeckung)
    assert zettel_deckung < hand_deckung, (zettel_deckung, hand_deckung)
    assert f"{zettel_deckung}/" in golden.bericht([aus_zettel])


# --------------------------------------------------------------------------
# what it refuses
# --------------------------------------------------------------------------


@pytest.mark.parametrize(("kaputt", "erwartet"), [
    (lambda t: t.replace("- [x] **`unklar – es fehlt …`**", "- [ ] **`unklar – es fehlt …`**"),
     "keine Einordnung angekreuzt"),
    (lambda t: re.sub(r"\*\*Unterlagen:\*\*.*", "**Unterlagen:**", t),
     "keine Unterlagen genannt"),
    (lambda t: t.replace("- [x] **P6** —", "- [x] **P99** —").replace(
        "- [ ] **P6** —", "- [x] **P99** —"),
     "ist kein Prüfpunkt dieses Schemas"),
    (lambda t: t.replace("- [x] `agb` —", "- [x] `quittung` —"),
     "ist keine Unterlagenart dieses Schemas"),
])
def test_ein_halb_ausgefuellter_zettel_wird_abgelehnt(kaputt, erwartet, tmp_path):
    """Nothing is written when anything is wrong. A golden file that is
    silently thin is worse than no golden file — it reports OK for a case
    nobody checked, and it does so in the suite that gates the build."""
    quelle = tmp_path / "zettel.md"
    quelle.write_text(kaputt(_seepark_zettel()), encoding="utf-8")

    dateien, fehler = loesungszettel.lesen(quelle, "preiserhoehung")
    assert any(erwartet in f for f in fehler), fehler


def test_ein_widerspruch_im_zettel_wird_benannt(tmp_path):
    """The check that matters most, because it is the one his own vocabulary
    invites: `wahrscheinlich unwirksam` means a rule actually broke. Ticking it
    without naming a broken Prüfpunkt is what „the proof is not there yet"
    looks like — and that is `unklar`."""
    v = _vorlage()
    zettel = v[:v.index("## Fall 1")] + _fuellen(
        _block(v), kennung="test_fall", stufe="initial", dokumente=["schreiben.md"],
        einordnung="wahrscheinlich unwirksam",
    )
    quelle = tmp_path / "zettel.md"
    quelle.write_text(zettel, encoding="utf-8")

    _, fehler = loesungszettel.lesen(quelle, "preiserhoehung")
    assert any("ohne einen einzigen gerissenen Prüfpunkt" in f for f in fehler), fehler
    assert any("ist es „unklar“" in f for f in fehler)
