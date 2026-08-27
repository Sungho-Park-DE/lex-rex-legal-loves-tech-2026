"""Rungs 2 and 5 of the ladder (14 §10) plus the missing half of 14 §7.

What rung 1 left open and this file pins down:

  * **the pair in every branch** — all three Einordnungen produce a letter.
    „wirksam" without a letter is the branch an advisor stops trusting, and it
    was the one branch nothing in the repo could even reach.
  * **the flip** — a Nachreichung is a second run on the same case, not a new
    case, and it invalidates what the advisor confirmed about the first one.
  * **the Radar** — the store row is built from a fixed field list, and no
    Anbieter below `k_min` is reported.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from fallpruefer import ansicht, golden, store
from fallpruefer.api import app
from fallpruefer.brief import BriefFehler, rendern, vorlage_laden
from fallpruefer.dokumente import laden
from fallpruefer.konfig import WURZEL, konfig
from fallpruefer.pipeline import (
    fall_anlegen,
    gate3_bestaetigen,
    nachreichung,
    referat_markieren,
    verarbeiten,
)
from fallpruefer.schema import schema_laden

FAELLE = WURZEL / "demo" / "faelle"
NORDLICHT = FAELLE / "nordlicht_agb_fehlen"

# Every template the schema's `rechtsbehelfe.liste` can point at, with the
# channel placeholder resolved the way rechtsbehelf.template_id resolves it.
TEMPLATES = [
    "musterbrief_fitness_widerspruch_rueckforderung",
    "musterbrief_fitness_widerspruch",
    "musterbrief_auskunftsverlangen",
    "musterbrief_kuendigung",
    "nachforderung_vbs",
    "nachforderung_vor_ort",
    "nachforderung_video",
]


def _lauf(verzeichnis, dateien, case_id):
    dokumente = [laden(verzeichnis / n, f"D{i}") for i, n in enumerate(dateien, start=1)]
    ticket = json.loads((verzeichnis / "ticket.json").read_text(encoding="utf-8"))
    return verarbeiten(fall_anlegen(case_id, ticket, dokumente))


# --------------------------------------------------------------------------
# the pair in every branch (14 §5, 14 §7)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "verzeichnis,dateien,einordnung,template",
    [
        ("drehkreuz", ["schreiben.md", "agb.md", "vertrag.md"],
         "wahrscheinlich unwirksam", "musterbrief_fitness_widerspruch_rueckforderung"),
        ("nordlicht_agb_fehlen", ["schreiben.md"], "unklar", "nachforderung_vbs"),
        ("sauber_aktivpark", ["schreiben.md", "agb.md", "vertrag.md"],
         "wirksam", "musterbrief_kuendigung"),
    ],
)
def test_jeder_zweig_liefert_ein_schreiben(verzeichnis, dateien, einordnung, template):
    fall = _lauf(FAELLE / verzeichnis, dateien, f"F-TEST-{verzeichnis}")
    pruefung = fall.aktuelle_pruefung()
    assert pruefung.einordnung.startswith(einordnung)

    brief = fall.rechtsbehelf.brief
    assert brief is not None and brief.text, f"{einordnung}: kein Schreiben"
    assert brief.template_id == template
    import re

    assert not re.search(konfig().platzhalter_regex, brief.text), "ungefüllter Platzhalter"
    assert "@@" not in brief.text, "Pseudonym-Token im Schreiben"


def test_jeder_zweig_bietet_zwei_rechtsbehelfe_an():
    """`garantie_pro_zweig` promises a pair, not a single option (14 §5)."""
    schema = schema_laden("preiserhoehung")
    for zweig, ids in schema.rechtsbehelfe.garantie_pro_zweig.items():
        assert ids, f"{zweig} ohne garantierten Rechtsbehelf"
        for rid in ids:
            r = schema.rechtsbehelfe.nach_id(rid)
            assert r is not None, f"{zweig}: {rid} steht nicht in rechtsbehelfe.liste"
            assert r.musterbrief, f"{rid} ohne Musterbrief"


def test_jedes_template_der_liste_existiert_und_ist_ungeprueft():
    for tid in TEMPLATES:
        vorlage = vorlage_laden(tid)
        assert vorlage.koerper.strip(), f"{tid} ist leer"
        # until Paulina's VZ downloads arrive every letter is ours (15 §13)
        assert vorlage.quelle.value == "eigen"
        assert not vorlage.geprueft, f"{tid} behauptet geprüft zu sein"


def test_nachforderung_lint_haelt_rechtliche_aussagen_heraus():
    """The lint is the point of the Nachforderung templates, not an obstacle:
    Gate 1 asks for papers, it does not assess anything (14 §4 step 3)."""
    for tid in ("nachforderung_vbs", "nachforderung_vor_ort", "nachforderung_video"):
        vorlage = vorlage_laden(tid)
        werte = {
            "[NAME]": "X", "[ANBIETER]": "Y", "[HEUTE]": "27.08.2026",
            "[FRIST_ENDE]": "10.09.2026", "[FEHLENDE_UNTERLAGEN_LISTE]": "- ein Dokument",
        }
        assert rendern(vorlage, werte, [], lint_nachforderung=True)

        werte["[FEHLENDE_UNTERLAGEN_LISTE]"] = "- die AGB — die Klausel ist unwirksam"
        with pytest.raises(BriefFehler):
            rendern(vorlage, werte, [], lint_nachforderung=True)


def test_kuendigung_traegt_beide_varianten():
    """Franz' Aufgabe §7 is open; until it is answered both variants ship and
    the clause decides which one appears (15 §13)."""
    ids = {v["id"] for v in vorlage_laden("musterbrief_kuendigung").varianten}
    assert {"sonderkuendigung", "ordentlich"} <= ids


# --------------------------------------------------------------------------
# the flip (14 §7, contract §4 re-run semantics)
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def geflippt(tmp_path_factory):
    """⚠️ Die Umleitung des Stores ist Teil der Vorrichtung, nicht Kosmetik.

    `gate3_bestaetigen` schreibt eine Zeile, und der Store entscheidet über das
    Radar. Ohne Umleitung hob **ein einziger Suite-Lauf** „nordlicht sportclub"
    von 2 auf 3 — also auf `k_min` — und Screen 2 zeigte danach einen Cluster,
    den `tools/radar_seed.py` nie ausgesät hatte. Es wuchs nicht weiter (der
    Store schreibt je `fall_hash` einmal), und genau deshalb war es unauffällig:
    ein einmaliger, dauerhafter Versatz statt eines wachsenden Haufens.

    Bei „fitpoint 24" wäre derselbe Mechanismus der stille Tod des „+1"-Beats
    aus `14` §7 gewesen — der steht mit Absicht bei `k_min - 1`.

    `monkeypatch` ist funktionsweit, diese Vorrichtung modulweit; deshalb von
    Hand sichern und zurücklegen, wie es `test_robustheit` schon vormacht.
    """
    ziel = tmp_path_factory.mktemp("flip") / "faelle.jsonl"
    echt, store.pfad = store.pfad, lambda: ziel
    try:
        fall = _lauf(NORDLICHT, ["schreiben.md"], "F-TEST-flip")
        gate3_bestaetigen(fall)
        return nachreichung(fall, [
            laden(NORDLICHT / "agb_nachgereicht.md"),
            laden(NORDLICHT / "vertrag_nachgereicht.md"),
        ])
    finally:
        store.pfad = echt


def test_nachreichung_haengt_einen_lauf_an_statt_zu_ueberschreiben(geflippt):
    assert [p.run_id for p in geflippt.pruefungen] == ["R-1", "R-2"]
    assert [p.trigger for p in geflippt.pruefungen] == ["initial", "nachreichung"]
    assert [p.aktuell for p in geflippt.pruefungen] == [False, True]
    # the old verdict is still readable — that is what makes the flip showable
    assert geflippt.pruefungen[0].einordnung.startswith("unklar")
    assert geflippt.pruefungen[1].einordnung == "wahrscheinlich unwirksam"


def test_nachreichung_entwertet_die_alte_gate3_bestaetigung(geflippt):
    """What the advisor confirmed was a verdict from fewer documents."""
    assert geflippt.pruefungen[0].gate3["gueltig"] is False
    assert geflippt.pruefungen[0].gate3["ungueltig_durch"] == "R-2"
    assert geflippt.pruefungen[1].gate3 is None


def test_nachreichung_nummeriert_weiter_und_markiert_die_herkunft(geflippt):
    assert [d.dok_id for d in geflippt.dokumente] == ["D1", "D2", "D3"]
    assert [d.eingegangen for d in geflippt.dokumente] == ["eingang", "nachreichung", "nachreichung"]


def test_der_alte_rechtsbehelf_ueberlebt_den_flip_nicht(geflippt):
    """Stage 1 chose „Unterlagen nachfordern". After the flip that is no longer
    on offer, and a case must not show a Nachforderung next to a verdict that
    no longer asks for one."""
    assert geflippt.rechtsbehelf.hauptvorschlag == "widerspruch_rueckforderung"
    assert geflippt.rechtsbehelf.gewaehlt == "widerspruch_rueckforderung"
    assert geflippt.rechtsbehelf.brief.template_id == "musterbrief_fitness_widerspruch_rueckforderung"


def test_api_nachreichung_liefert_beide_einordnungen():
    klient = TestClient(app)
    ticket = json.loads((NORDLICHT / "ticket.json").read_text(encoding="utf-8"))
    angelegt = klient.post("/faelle", json={
        "freitext": ticket["freitext"], "anbieter": ticket["anbieter"],
        "branche": "fitness", "identitaet": ticket["identitaet"],
        "case_id": "F-2026-9401",
        "anhaenge": [{"dateiname": "schreiben.md",
                      "text": (NORDLICHT / "schreiben.md").read_text(encoding="utf-8")}],
    })
    assert angelegt.status_code == 200, angelegt.text

    antwort = klient.post("/faelle/F-2026-9401/dokumente", json={"anhaenge": [
        {"dateiname": n, "text": (NORDLICHT / n).read_text(encoding="utf-8")}
        for n in ("agb_nachgereicht.md", "vertrag_nachgereicht.md")
    ]})
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert daten["einordnung_vorher"].startswith("unklar")
    assert daten["einordnung"] == "wahrscheinlich unwirksam"
    assert daten["gerissene_stufe"] == "S3"
    assert daten["neue_dokumente"] == ["D2", "D3"]
    assert klient.get("/faelle/F-2026-9401").status_code == 200

    assert klient.post("/faelle/F-2026-9401/dokumente", json={"anhaenge": []}).status_code == 400


# --------------------------------------------------------------------------
# store and Radar (contract §8)
# --------------------------------------------------------------------------


@pytest.fixture
def leerer_store(tmp_path, monkeypatch):
    ziel = tmp_path / "faelle.jsonl"
    monkeypatch.setattr(store, "pfad", lambda: ziel)
    return ziel


def test_store_satz_enthaelt_keine_identitaet(leerer_store):
    fall = _lauf(FAELLE / "drehkreuz", ["schreiben.md", "agb.md", "vertrag.md"], "F-TEST-store")
    satz = gate3_bestaetigen(fall)

    assert set(satz) == set(store.FELDER), "der Satz führt Felder, die §8 nicht kennt"
    roh = json.dumps(satz, ensure_ascii=False)
    for geheim in ("Ingeborg", "Maier", "Lindenstraße", "4711-2233", "F-TEST-store"):
        assert geheim not in roh, f"Store-Satz enthält „{geheim}“"
    # the Anbieter is a legal person and is the cluster key (14 §3 whitelist)
    assert satz["anbieter"] == "fitpoint 24"
    assert satz["fall_hash"] != "F-TEST-store"


def test_store_zaehlt_denselben_fall_nur_einmal(leerer_store):
    fall = _lauf(FAELLE / "drehkreuz", ["schreiben.md", "agb.md", "vertrag.md"], "F-TEST-store2")
    gate3_bestaetigen(fall)
    referat_markieren(fall, ["dauerbrenner"])
    assert len(store.lesen()) == 1
    assert store.lesen()[0]["referat_flag"] == ["dauerbrenner"]


def test_radar_weist_keinen_anbieter_unter_k_min_aus(leerer_store):
    k_min = konfig().radar.k_min
    for i in range(k_min - 1):
        fall = _lauf(FAELLE / "drehkreuz", ["schreiben.md", "agb.md", "vertrag.md"], f"F-TEST-r{i}")
        gate3_bestaetigen(fall)

    r = store.radar()
    assert r["cluster"] == [], "Cluster unterhalb der k-Schwelle ausgewiesen"
    assert r["unter_schwelle_anbieter"] == 1
    assert "fitpoint" not in json.dumps(r["cluster"])

    fall = _lauf(FAELLE / "drehkreuz", ["schreiben.md", "agb.md", "vertrag.md"], "F-TEST-rN")
    gate3_bestaetigen(fall)
    r = store.radar()
    assert [c["anbieter"] for c in r["cluster"]] == ["fitpoint 24"]
    assert r["cluster"][0]["faelle"] == k_min


def test_referat_markierung_kennt_nur_die_sechs_fwn_kriterien(leerer_store):
    fall = _lauf(FAELLE / "drehkreuz", ["schreiben.md", "agb.md", "vertrag.md"], "F-TEST-flag")
    gate3_bestaetigen(fall)
    with pytest.raises(ValueError):
        referat_markieren(fall, ["eigene_erfindung"])
    assert not fall.referat_markierung.kriterien


# --------------------------------------------------------------------------
# the golden set covers what the demo shows
# --------------------------------------------------------------------------


def test_golden_deckt_alle_drei_zweige_und_einen_flip_ab():
    dateien = [json.loads(p.read_text(encoding="utf-8"))
               for p in sorted((WURZEL / "tests" / "golden").glob("*.json"))]
    einordnungen = {stufe["erwartet"]["einordnung"].split(":")[0].strip()
                    for d in dateien for stufe in d["stufen"]}
    assert {"wirksam", "wahrscheinlich unwirksam", "unklar – es fehlt …"} <= einordnungen

    mehrstufig = [d for d in dateien if len(d["stufen"]) > 1]
    assert mehrstufig, "kein zweistufiger Golden-Fall — der Flip ist ungetestet"
    zweige = {tuple(s["erwartet"]["einordnung"].split(":")[0].strip() for s in d["stufen"])
              for d in mehrstufig}
    # one flip has to go the other way, or the set only proves that the tool
    # finds faults once it gets enough paper (12 §5, Fall 3b)
    assert any(z[-1] == "wahrscheinlich unwirksam" for z in zweige)
    assert any(z[-1] == "wirksam" for z in zweige)


def test_golden_suite_bleibt_gruen():
    ergebnisse = golden.alle()
    assert len(ergebnisse) >= 4
    schlecht = [e for e in ergebnisse if not e.gruen]
    assert not schlecht, "\n" + golden.bericht(ergebnisse)


# --------------------------------------------------------------------------
# V-23 — ein Enum-Wert ist ein Code, kein Anzeigetext
# --------------------------------------------------------------------------


def test_jedes_enum_feld_hat_fuer_jeden_wert_einen_anzeigetext():
    """`formatieren()` fällt für einen unbekannten Wert auf den Code zurück,
    und das ist richtig — ein Platzhalter wie „(unbekannt)" wäre eine Lüge über
    das, was im Dokument stand. Der Preis ist, dass ein vergessener Anzeigetext
    lautlos als `weiternutzung` auf dem Schirm der Beraterin landet. Genau so
    stand es in der Demo-Spur.
    """
    from fallpruefer.konfig import WURZEL
    from fallpruefer.schema import schema_laden

    for pfad in sorted((WURZEL / "schemas").glob("*.json")):
        if pfad.stem.startswith("_"):
            continue
        schema = schema_laden(pfad.stem)
        for dok in schema.dokumenten_soll.dokumente:
            for feld in dok.felder:
                if feld.typ != "enum" or not feld.werte:
                    continue
                fehlend = [w for w in feld.werte if w not in (feld.wert_labels or {})]
                assert not fehlend, (
                    f"{pfad.stem}/{feld.feld_id}: ohne Anzeigetext rendert der "
                    f"rohe Code auf dem Schirm — {fehlend}"
                )


def test_der_satz_zum_pruefpunkt_zeigt_den_anzeigetext_nicht_den_code():
    """Die Gegenprobe an der Oberfläche, an der es aufgefallen ist: die Spur
    des Demofalls. Ein struktureller Test allein würde grün bleiben, wenn die
    Karte da ist und die Interpolation sie nicht benutzt."""
    from fallpruefer.schema import schema_laden

    fall = _lauf(FAELLE / "drehkreuz", ["schreiben.md", "agb.md", "vertrag.md"], "F-V23-SATZ")
    schema = schema_laden("preiserhoehung")
    sicht = ansicht.bauen(fall, schema)

    codes = {
        w
        for dok in schema.dokumenten_soll.dokumente
        for f in dok.felder
        if f.typ == "enum" and f.werte
        for w in f.werte
        if w not in (f.wert_labels or {}).values()  # „keine" ist beides
    }
    eintraege = [pp for st in sicht.pruefpfad.stufen for pp in st.pruefpunkte]
    p9 = next(pp for pp in eintraege if pp.pruefpunkt_id == "P9")
    assert "die weitere Nutzung" in p9.grund and "weiternutzung" not in p9.grund

    for pp in eintraege:
        for feld in pp.verwendet:
            assert feld.wert_anzeige not in codes, (
                f"{pp.pruefpunkt_id}/{feld.feld_id} zeigt den rohen Code "
                f"„{feld.wert_anzeige}“"
            )


def test_kein_schemasatz_zeigt_seinen_platzhalter_auf_dem_schirm():
    """F2 aus dem Produktreview, und er war groesser als gemeldet.

    `{gespraech.monate_erhoeht_gezahlt}` stand als **roher Token** in allen drei
    Fixtures — nicht erst nach einer Antwort, sondern von Anfang an, weil P14 in
    jedem Demofall JA ist und `Pruefpfad.tsx` die `wertungsfrage`
    zustandsunabhaengig rendert. Der `grund` lief durch `satz()`, die
    gespeicherte `wertungsfrage` nicht.

    Besonders teuer, weil derselbe Bildschirm die Geschichte „interne Sprache
    kommt hier nicht raus" erzaehlt (der Anzeigetext-Waechter aus `21` §0).

    Zwei Haelften, beide noetig: interpolieren **und** die Frage nur dort
    tragen, wo sie offen ist — sonst steht bei JA „hat — Monate gezahlt".
    """
    import re

    from fastapi.testclient import TestClient

    from fallpruefer.api import app

    klient = TestClient(app)
    muster = re.compile(r"\{[a-z_]+\.[a-z_]+\}")

    for name, verzeichnis, dateien, antwort in (
        ("wertung", NORDLICHT, ["schreiben.md"], 8),
        ("ja", NORDLICHT, ["schreiben.md"], None),
    ):
        case_id = f"F-PLATZ-{name}"
        ticket = json.loads((verzeichnis / "ticket.json").read_text(encoding="utf-8"))
        klient.post("/faelle", json={
            "freitext": ticket["freitext"],
            "anhaenge": [{"dateiname": n, "text": (verzeichnis / n).read_text(encoding="utf-8")}
                         for n in dateien],
            "kanal": "vbs", "anbieter": ticket["anbieter"],
            "identitaet": ticket["identitaet"], "case_id": case_id,
        })
        if antwort is not None:
            klient.post(f"/faelle/{case_id}/leitfaden",
                        json={"antworten": {"gespraech.monate_erhoeht_gezahlt": antwort}})

        roh = klient.get(f"/faelle/{case_id}").text
        assert not muster.search(roh), \
            f"{name}: roher Platzhalter im Viewmodel — {muster.findall(roh)[:3]}"

        p14 = next(pp for st in klient.get(f"/faelle/{case_id}").json()["pruefpfad"]["stufen"]
                   for pp in st["pruefpunkte"] if pp["pruefpunkt_id"] == "P14")
        if antwort is None:
            assert p14["zustand"]["code"] == "JA"
            assert p14["wertungsfrage"] is None, "an einem JA-Punkt ist keine Frage offen"
        else:
            assert p14["zustand"]["code"] == "WERTUNG"
            assert "8 Monate" in p14["wertungsfrage"]


def test_die_fixtures_selbst_tragen_keinen_platzhalter():
    """Die Fixtures sind das, was ohne laufendes Backend auf dem Schirm steht —
    und im Fixture-Modus laeuft die Demo-Vorschau. Ein Token, der nur dort
    ueberlebt, waere unsichtbar fuer jeden Test oben."""
    import re

    muster = re.compile(r"\{[a-z_]+\.[a-z_]+\}")
    dateien = sorted((WURZEL / "demo" / "fixtures").glob("*.json"))
    assert dateien, "keine Fixtures gefunden — der Test misst nichts"
    for pfad in dateien:
        treffer = muster.findall(pfad.read_text(encoding="utf-8"))
        assert not treffer, f"{pfad.name}: {sorted(set(treffer))}"
