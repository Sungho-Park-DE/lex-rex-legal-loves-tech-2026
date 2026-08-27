"""Rung 1 of the build ladder (14 §10), asserted.

Definition of done per contract §11 is the golden runner green, plus the three
things the ladder names explicitly: `heute()` drives every displayed date, L0
runs before the adapter, and the generic evaluator produces the trace. The
API-vs-fixture test exists so the Lovable frontend and the backend cannot drift
apart without a red test.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from fallpruefer import ansicht, golden, zeit
from fallpruefer.api import app
from fallpruefer.konfig import WURZEL, konfig
from fallpruefer.pipeline import fall_aus_verzeichnis, fall_speichern
from fallpruefer.schema import schema_laden
from fallpruefer.viewmodel import FallakteAnsicht
from fallpruefer.vokabular import VOKABULARE, Zustand

DREHKREUZ = WURZEL / "demo" / "faelle" / "drehkreuz"
FIXTURE = WURZEL / "demo" / "fixtures" / "drehkreuz_fallakte.json"


@pytest.fixture(scope="module")
def fall():
    f = fall_aus_verzeichnis(DREHKREUZ, "F-2026-0001")
    f.fallgruppe.bestaetigt = True
    fall_speichern(f)
    return f


@pytest.fixture(scope="module")
def schema():
    return schema_laden("preiserhoehung")


# --------------------------------------------------------------------------
# (i) golden
# --------------------------------------------------------------------------


def test_golden_suite_gruen():
    ergebnisse = golden.alle()
    assert ergebnisse, "keine Golden-Dateien gefunden"
    schlecht = [e for e in ergebnisse if not e.gruen]
    assert not schlecht, "\n" + golden.bericht(ergebnisse)


def test_keine_falschen_sicheren_antworten():
    """The one failure mode that costs an advisor their credibility: expected
    „unklar", answered „wirksam"/„wahrscheinlich unwirksam"."""
    assert sum(e.falsche_sichere_antworten for e in golden.alle()) == 0


# --------------------------------------------------------------------------
# (ii) the API answers with exactly the fixture's structure
# --------------------------------------------------------------------------


def _formen(objekt, pfad=""):
    """Every key path, list indices collapsed — i.e. the shape, not the data."""
    if isinstance(objekt, dict):
        for k, v in objekt.items():
            yield from _formen(v, f"{pfad}.{k}")
    elif isinstance(objekt, list):
        for v in objekt:
            yield from _formen(v, f"{pfad}[]")
    else:
        yield pfad


def test_api_fallakte_hat_fixture_struktur(fall):
    klient = TestClient(app)
    antwort = klient.get(f"/faelle/{fall.case_id}")
    assert antwort.status_code == 200, antwort.text

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    # both sides validate against the same model — that alone is not enough,
    # because an optional field could be present on one side only
    FallakteAnsicht.model_validate(fixture)
    assert set(_formen(antwort.json())) == set(_formen(fixture))


def test_fixture_ist_ein_gueltiges_viewmodel():
    FallakteAnsicht.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_vokabular_endpunkt_kennt_alle_vokabulare():
    klient = TestClient(app)
    daten = klient.get("/vokabular").json()
    assert set(daten["vokabulare"]) == set(VOKABULARE)
    for eintraege in daten["vokabulare"].values():
        for e in eintraege:
            assert e["label"] and e["tone"] in ("gruen", "gelb", "rot", "grau")


def test_post_faelle_legt_fall_an():
    klient = TestClient(app)
    anhaenge = [
        {"dateiname": name, "text": (DREHKREUZ / name).read_text(encoding="utf-8")}
        for name in ("schreiben.md", "agb.md", "vertrag.md")
    ]
    ticket = json.loads((DREHKREUZ / "ticket.json").read_text(encoding="utf-8"))
    antwort = klient.post("/faelle", json={
        "freitext": ticket["freitext"], "anhaenge": anhaenge,
        "kanal": "vbs", "anbieter": ticket["anbieter"],
        "identitaet": ticket["identitaet"], "case_id": "F-2026-9001",
    })
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["einordnung"] == "wahrscheinlich unwirksam"
    assert klient.get("/faelle/F-2026-9001").status_code == 200


# --------------------------------------------------------------------------
# (iii) one letter renders
# --------------------------------------------------------------------------


def test_musterbrief_rendert_ohne_luecke(fall):
    brief = fall.rechtsbehelf.brief
    assert brief is not None and brief.text
    import re

    assert not re.search(konfig().platzhalter_regex, brief.text), "ungefüllter Platzhalter"
    assert "Ingeborg Maier" in brief.text, "Identität wurde nicht re-identifiziert"
    assert "@@" not in brief.text, "Pseudonym-Token im Brief"
    # the variants the broken Prüfpunkte should have pulled in
    for teil in ("Preisanpassungsklausel", "weitere Nutzung des Studios", "zugesicherten Zeitraum"):
        assert teil in brief.text


def test_brief_meldet_luecke_statt_sie_zu_verstecken(fall, schema):
    from fallpruefer.brief import BriefFehler, rendern, vorlage_laden

    vorlage = vorlage_laden("musterbrief_fitness_widerspruch_rueckforderung")
    with pytest.raises(BriefFehler):
        rendern(vorlage, {"[NAME]": "X"}, [])


# --------------------------------------------------------------------------
# the ladder's three "from the first line" requirements
# --------------------------------------------------------------------------


def test_heute_folgt_dem_demo_stichtag(fall):
    assert zeit.heute().isoformat() == konfig().demo_stichtag
    a = ansicht.bauen(fall, schema_laden("preiserhoehung"))
    assert a.fusszeile.stichtag == konfig().demo_stichtag
    assert a.fusszeile.stichtag_modus == "demo"
    frist = next(p.frist for s in a.pruefpfad.stufen for p in s.pruefpunkte if p.frist)
    assert "27.08.2026" in frist.wert  # computed against heute(), not date.today()


def test_l0_laeuft_vor_dem_adapter(fall):
    """The pseudonymised text is what was sent; the original never was."""
    assert fall.pseudonyme, "keine Tokens gebildet"
    assert "Ingeborg Maier" in fall.pseudonyme.values()
    for d in fall.dokumente:
        for s in d.seiten:
            assert "Ingeborg Maier" not in s.text_pseudonym
            assert "4711-2233" not in s.text_pseudonym
    assert "Ingeborg Maier" not in fall.eingang.freitext_pseudonym
    # the Anbieter is a legal person and stays in the clear (contract §4 whitelist)
    assert "FitPoint 24" in fall.dokumente[0].text_pseudonym


def test_l0_rundreise_ist_verlustfrei(fall):
    from fallpruefer.ansicht import _zurueck

    for d in fall.dokumente:
        for s in d.seiten:
            assert _zurueck(s.text_pseudonym, fall.pseudonyme) == s.text_original


def test_jedes_zitat_steht_wirklich_im_dokument(fall):
    """The whole trust layer in one assertion."""
    from fallpruefer.text import enthaelt

    seiten = {(d.dok_id, s.nr): s.text_pseudonym for d in fall.dokumente for s in d.seiten}
    pruefung = fall.aktuelle_pruefung()
    geprueft = 0
    for erg in pruefung.ergebnisse:
        for q in erg.zitate:
            assert enthaelt(seiten[(q.dok_id, q.seite)], q.zitat_pseudonym), q.zitat_pseudonym
            geprueft += 1
    assert geprueft >= 10


def test_evaluator_kennt_keinen_einzigen_pruefpunkt():
    """The claim „second Fallgruppe = one more file" has to hold literally."""
    import re

    for modul in ("evaluator.py", "regeln.py", "ansicht.py", "viewmodel.py"):
        quelltext = (WURZEL / "fallpruefer" / modul).read_text(encoding="utf-8")
        code = "\n".join(
            z for z in quelltext.splitlines()
            if not z.strip().startswith("#")
        )
        treffer = re.findall(r'"P\d+[a-z]?"|\bpreiserhoehung\b|"agb\.|"vertrag\.', code)
        assert not treffer, f"{modul} nennt schemaspezifische Namen: {treffer}"


# --------------------------------------------------------------------------
# the contract's own load-time guarantees
# --------------------------------------------------------------------------


# Felder eines Schemas, die eine Beraterin wirklich liest. Die Liste ist der
# eigentliche Inhalt des Tests darunter: sie zwingt dazu, „was landet auf einem
# Schirm" einmal auszusprechen, statt es je Feld neu zu erraten.
ANZEIGEFELDER_PRUEFPUNKT = (
    "titel", "proposition", "wertungsfrage", "satz_ja", "satz_nein",
    "fehlt_text", "plain_grund", "pruefumfang_text",
)
# Sprache, die es nur im Bauplan gibt. `baum.hinweis` und die `kommentar`-Felder
# stehen bewusst NICHT unter Beobachtung: die liest nur, wer die Datei öffnet.
INTERNE_SPRACHE = {
    "Gate-Nummer": r"Gate\s*\d",
    "Prüfpunkt-ID": r"\bP\d+[a-z]?\b",
    "Stufen-ID": r"\bS\d\b",
    "Zustandscode": r"\b(FEHLT|WERTUNG|INAKTIV|NEIN_wenn|JA_wenn)\b",
}


def _anzeigetexte(schema: dict):
    """(Ort, Text) für alles, was aus dem Schema auf einem Schirm landet."""
    soll = schema.get("dokumenten_soll", {})
    for d in soll.get("dokumente", []):
        for f in ("anzeigename", "begruendung_satz", "beschaffungsweg"):
            if d.get(f):
                yield f"dokumenten_soll[{d['dokumenttyp']}].{f}", d[f]
    for g in soll.get("gruppen", []):
        if g.get("anzeigename"):
            yield f"gruppe[{g['id']}].anzeigename", g["anzeigename"]
    for a in schema.get("annahmen", []):
        if a.get("anzeige"):
            yield f"annahme[{a['id']}].anzeige", a["anzeige"]
    for pp in schema.get("pruefpunkte", []):
        for f in ANZEIGEFELDER_PRUEFPUNKT:
            if pp.get(f):
                yield f"{pp['id']}.{f}", pp[f]
        # Der `norm`-String der Datei gewinnt gegen den der Normbasis
        # (`normbasis.aufloesen`: `label = s.get("norm") or e["norm"]`), er ist
        # also die Beschriftung der Normkarte und nicht bloß ein Schlüssel.
        for a in pp.get("anker") or []:
            if a.get("norm"):
                yield f"{pp['id']}.anker[{a.get('key')}].norm", a["norm"]
        for f in ("text", "hinweis"):
            if (pp.get("leitfaden_frage") or {}).get(f):
                yield f"{pp['id']}.leitfaden_frage.{f}", pp["leitfaden_frage"][f]
        if isinstance(pp.get("bei_NEIN"), dict) and pp["bei_NEIN"].get("text"):
            yield f"{pp['id']}.bei_NEIN.text", pp["bei_NEIN"]["text"]

    def knoten(n, pfad="baum"):
        if isinstance(n, dict):
            if n.get("titel"):
                yield f"{pfad}[{n.get('id')}].titel", n["titel"]
            for kind in n.get("kinder", []):
                yield from knoten(kind, pfad)

    yield from knoten(schema.get("baum") or {})
    for r in schema.get("rechtsbehelfe", {}).get("liste", []):
        if r.get("titel"):
            yield f"rechtsbehelf[{r['id']}].titel", r["titel"]
    for h in schema.get("beratungshinweise", []):
        for f in ("titel", "text"):
            if h.get(f):
                yield f"hinweis[{h['id']}].{f}", h[f]
        for a in h.get("anker") or []:
            if a.get("norm"):
                yield f"hinweis[{h['id']}].anker[{a.get('key')}].norm", a["norm"]
    for schluessel, satz in (schema.get("plain_saetze") or {}).items():
        yield f"plain_saetze[{schluessel}]", satz


@pytest.mark.parametrize("pfad", sorted(
    p for p in (WURZEL / "schemas").glob("*.json") if not p.stem.startswith("_")
), ids=lambda p: p.stem)
def test_kein_anzeigetext_verrät_die_interne_bauweise(pfad):
    """Gefunden am ersten echten Bildschirm, nicht in einem Audit.

    `beschaffungsweg` der Kostenkalkulation lautete „Auskunftsverlangen an das
    Studio **(Gate 4)** — …". Das steht als „Weg: …" unter einem offenen Posten
    auf dem Schirm der Beraterin; „Gate 4" ist unsere Gate-Nummerierung, sagt
    ihr nichts und verrät Architektur im Fachtext. Der zweite Halbsatz („nie als
    Nachforderung beim Verbraucher") ist echte Fachanweisung und bleibt.

    Der Fehler war nur am Pixel zu finden — kein Test hat je gefragt, ob ein
    Anzeigesatz die eigene Bauweise ausplaudert. Jetzt fragt einer, über **jedes**
    Schema: eine Prüfpunkt-ID, eine Stufen-ID oder ein Zustandscode in einem Satz,
    den ein Mensch liest, ist derselbe Fehler in einer anderen Verkleidung.
    """
    import re

    schema = json.loads(pfad.read_text(encoding="utf-8"))
    texte = list(_anzeigetexte(schema))

    # Sonst liest „4 passed" wie „vier Schemata geprüft", obwohl der Sammler
    # für zwei davon nichts zurückgibt. `klausel_check` und `kuendigung` sind
    # leere Stufe-C-Platzhalter — dort ist null richtig. Ein Schema **mit**
    # Inhalt, das nichts liefert, wäre dagegen ein kaputter Sammler, und der
    # bliebe grün.
    inhalt = schema.get("pruefpunkte") or schema.get("dokumenten_soll", {}).get("dokumente")
    if inhalt:
        assert texte, f"{pfad.stem} hat Inhalt, liefert aber keinen Anzeigetext"
        assert any(".anker[" in ort for ort, _ in texte), \
            f"{pfad.stem}: kein einziges Anker-Label eingesammelt"
    else:
        assert not texte, f"{pfad.stem} ist ein leerer Platzhalter, liefert aber Text"

    funde = [
        f"{ort}: {name} „{treffer}“ in „{text}“"
        for ort, text in texte
        for name, muster in INTERNE_SPRACHE.items()
        for treffer in re.findall(muster, str(text))
    ]
    assert not funde, "interne Sprache im Anzeigetext:\n" + "\n".join(funde)


def test_das_laden_verliert_keinen_pruefpunkt(fallgruppe_id="preiserhoehung"):
    """Der Loader lässt nichts unter den Tisch fallen.

    Hiess bis V-T1 `test_schema_laedt_verbatim_aus_dem_contract` und versprach
    im Namen, die Datei sei der `15` §2-Block — geprüft hat er, dass das
    geladene Schema zu der Datei passt, aus der es geladen wurde, was trivial
    wahr ist. **Die echte Identität hält
    `tests/test_kontrakt_identitaet.py::test_das_papier_und_der_code_sind_dieselbe_datei`**,
    byteweise.

    Was hier bleibt, ist trotzdem etwas wert: die Modelle sind `extra="allow"`,
    also fällt ein Prüfpunkt mit einem kaputten Pflichtfeld nicht auf, sondern
    aus — und eine Zählung ist die billigste Art, das zu merken.
    """
    s = schema_laden(fallgruppe_id)
    roh = json.loads((WURZEL / "schemas" / f"{fallgruppe_id}.json").read_text(encoding="utf-8"))
    assert s.version == roh["version"]
    assert [p.id for p in s.pruefpunkte] == [p["id"] for p in roh["pruefpunkte"]]
    assert len(s.dokumenten_soll.dokumente) == len(roh["dokumenten_soll"]["dokumente"])


def test_normbasis_kennt_jeden_anker_jedes_schemas():
    """Every schema, not just the A one.

    This checked `preiserhoehung` alone while it was the only file with rules.
    Inkasso has had fourteen Prüfpunkte since v0.3.0, and an anchor that does
    not resolve renders as `anker_ungeprueft` in dev mode rather than failing —
    so an unresolvable key in a second schema would have reached the screen
    silently.
    """
    import json

    from fallpruefer.konfig import WURZEL
    from fallpruefer.normbasis import normbasis

    nb = normbasis()
    dateien = sorted(WURZEL.glob("schemas/**/*.json"))
    geprueft = 0
    for datei in dateien:
        roh = json.loads(datei.read_text(encoding="utf-8"))
        if not roh.get("fallgruppe_id") or not roh.get("pruefpunkte"):
            continue
        s = schema_laden(roh["fallgruppe_id"])
        geprueft += 1
        for p in s.pruefpunkte:
            for a in p.anker:
                assert nb.kennt(a["key"]), f"{s.fallgruppe_id}/{p.id}: {a['key']}"
    assert geprueft >= 2, "es sollten mindestens zwei Schemata Regeln tragen"


def test_gate_traegt_nie_zur_einordnung_bei(fall, schema):
    """P0/P5 are JA here, but the point is structural: a gate is excluded from
    aggregation whatever it says."""
    from fallpruefer.vokabular import Rolle

    pruefung = fall.aktuelle_pruefung()
    gates = [p.id for p in schema.pruefpunkte if p.rolle == Rolle.GATE]
    assert gates
    for knoten in schema.baum.kinder:
        kinder = [k for k in knoten.kinder if isinstance(k, str)]
        if set(kinder) <= set(gates):
            assert pruefung.baum_zustaende[knoten.id] == Zustand.INAKTIV


# Wer hier steht, ist von einem Menschen im Original gelesen worden. Die Liste
# wächst nur mit einer ausdrücklichen Entscheidung — ein neuer Eintrag ohne
# Änderung dieser Zeile lässt den Test fallen, und genau das ist der Zweck.
BESTAETIGTE_ANKER = {"lg_bamberg_13_o_730_22"}  # Paulina, 26.08.2026 (Runde 4)


def test_kein_anker_behauptet_geprueft_ohne_namen_und_datum():
    """Der Wächter von früher hieß „alle Anker sind noch ungeprüft" und verbot
    die Bestätigung ganz. Er verbietet sie nicht mehr — er verlangt ihre
    Herkunft: `geprueft: true` nur, wenn die Normbasis sagt, **wer** das
    Original gelesen hat und **wann**. Was er weiterhin verhindert, ist das,
    wofür er gebaut wurde: dass eine Fundstelle still auf „geprüft" kippt und
    so auf eine Folie kommt.
    """
    from fallpruefer.normbasis import normbasis

    nb = normbasis()
    s = schema_laden("preiserhoehung")
    bestaetigt = set()
    for p in s.pruefpunkte:
        for a in p.anker:
            if not a.get("geprueft"):
                continue
            e = nb.gesetze.get(a["key"]) or nb.rechtsprechung.get(a["key"]) or {}
            assert e.get("geprueft_von"), f"{p.id}/{a['key']}: geprueft ohne Namen"
            assert e.get("geprueft_am"), f"{p.id}/{a['key']}: geprueft ohne Datum"
            bestaetigt.add(a["key"])
    assert bestaetigt == BESTAETIGTE_ANKER, (
        "Die Menge der bestätigten Anker hat sich geändert — das ist eine "
        f"Entscheidung, kein Nebeneffekt. Gefunden: {sorted(bestaetigt)}"
    )


# --------------------------------------------------------------------------
# the live adapter
# --------------------------------------------------------------------------


def test_cache_enthaelt_keine_identitaeten():
    """What was recorded is what was sent. If a name is in the cache file, a
    name went to the provider — so this asserts on the artefact, not on the
    code path that produced it."""
    import re

    geheim = ("Ingeborg", "Maier", "Lindenstraße", "4711-2233",
              "i.maier@example.de", "089 1234567")
    dateien = sorted((WURZEL / "cache" / "llm").glob("*.json"))
    assert dateien, "keine Cache-Dateien — tools/drehkreuz_cache.py laufen lassen"
    mit_tokens = 0
    for pfad in dateien:
        roh = json.dumps(json.loads(pfad.read_text(encoding="utf-8"))["eingabe"],
                         ensure_ascii=False)
        for wort in geheim:
            assert wort not in roh, f"{pfad.name} enthält „{wort}“"
        mit_tokens += bool(re.search(r"@@[A-Z]+_\d+@@", roh))
    # not every document carries an identity (the AGB carry none), so tokens are
    # asserted across the set — the per-file rule is the negative one above
    assert mit_tokens, "kein einziger Cache-Eintrag trägt Pseudonym-Tokens"


def test_ohne_api_key_laeuft_der_cache_adapter():
    import os

    from fallpruefer.adapter import CacheAdapter, adapter_holen, live_moeglich

    if os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("API-Key gesetzt — der Live-Adapter ist hier korrekt")
    assert not live_moeglich()
    assert isinstance(adapter_holen(), CacheAdapter)


@pytest.mark.skipif(
    not __import__("os").environ.get("ANTHROPIC_API_KEY"),
    reason="kein ANTHROPIC_API_KEY — Live-Lauf wird übersprungen",
)
def test_live_ergibt_dieselbe_einordnung_wie_der_cache():
    """Contract §9 replay. A recording is only worth having if replaying it
    lands on the same Einordnung and the same per-Prüfpunkt states — otherwise
    the demo shows something the live system would not have said."""
    from fallpruefer.adapter.anthropic_adapter import AnthropicAdapter
    from fallpruefer.adapter.cache_adapter import CacheAdapter

    def lauf(adapter):
        f = fall_aus_verzeichnis(DREHKREUZ, "F-2026-0001", adapter)
        p = f.aktuelle_pruefung()
        return p.einordnung, {e.pruefpunkt_id: e.zustand.value for e in p.ergebnisse}, f

    cache_einordnung, cache_zustaende, _ = lauf(CacheAdapter())
    live_einordnung, live_zustaende, live_fall = lauf(AnthropicAdapter(cache_lesen=False))

    assert live_einordnung == cache_einordnung
    assert live_zustaende == cache_zustaende
    assert all(not r.aus_cache for r in live_fall.llm_runs), "es lief nichts live"
    assert sum(r.kosten_cent for r in live_fall.llm_runs) > 0
