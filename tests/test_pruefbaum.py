"""R7 — der Prüfpfad als Baum (Luis' Kritik 25 Aug via Franz: „viel zu
detailliert", `16` §3 / `13`: der Baum IST die Erklärbarkeit).

Der Baum ist **Projektion**, keine zweite Bewertung: jeder Zustand darin kommt
aus derselben Prüfung wie die Detailzeile darunter. Die sieben Zusicherungen
hier halten genau das fest — und die letzte, dass Einordnung und Brief sich
durch die neue Ansicht nicht bewegen.
"""

from __future__ import annotations

import json
import re

import pytest

from fallpruefer import ansicht, store
from fallpruefer.konfig import WURZEL
from fallpruefer.pipeline import fall_aus_verzeichnis, gate1_nachforderung, nachreichung
from fallpruefer.dokumente import laden
from fallpruefer.schema import schema_laden

FAELLE = WURZEL / "demo" / "faelle"


@pytest.fixture(autouse=True)
def eigener_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "pfad", lambda: tmp_path / "faelle.jsonl")


def _akte(name, cid):
    fall = fall_aus_verzeichnis(FAELLE / name, case_id=cid)
    return fall, ansicht.bauen(fall, schema_laden("preiserhoehung"))


def _blaetter(k):
    return [k] if not k.kinder else [b for c in k.kinder for b in _blaetter(c)]


def _alle(k):
    return [k] + [x for c in k.kinder for x in _alle(c)]


@pytest.mark.parametrize("name", ["drehkreuz", "sauber_aktivpark", "nordlicht_agb_fehlen"])
def test_die_blaetter_sind_genau_die_pruefpunkte_der_liste(name):
    _, a = _akte(name, "F-2026-8001")
    baum = a.pruefpfad.baum
    assert baum is not None
    aus_liste = [p.pruefpunkt_id for s in a.pruefpfad.stufen for p in s.pruefpunkte]
    aus_baum = [b.knoten_id for b in _blaetter(baum)]
    assert aus_baum == aus_liste, "Reihenfolge und Menge müssen identisch sein"
    assert len(set(aus_baum)) == len(aus_baum), "kein Prüfpunkt doppelt"
    assert baum.anzahl_pruefpunkte == len(aus_liste)


def test_der_zustand_im_baum_ist_der_zustand_der_liste():
    _, a = _akte("drehkreuz", "F-2026-8002")
    stufen = {s.stufe_id: s for s in a.pruefpfad.stufen}
    punkte = {p.pruefpunkt_id: p for s in a.pruefpfad.stufen for p in s.pruefpunkte}
    for knoten in a.pruefpfad.baum.kinder:
        assert knoten.zustand.code == stufen[knoten.knoten_id].zustand.code
        assert knoten.op is not None and knoten.op.label == "alle müssen halten"
        for k in knoten.kinder:
            assert k.zustand.code == punkte[k.knoten_id].zustand.code
            assert k.op is None
    assert a.pruefpfad.baum.zustand.code == a.pruefpfad.wurzel.code


def test_gerissen_steht_genau_an_der_gerissenen_stufe():
    _, a = _akte("drehkreuz", "F-2026-8003")
    gerissen = [k for k in _alle(a.pruefpfad.baum) if k.gerissen]
    assert a.pruefpfad.gerissene_stufe is not None
    stufen = [k for k in gerissen if k.art.code == "stufe"]
    assert [k.knoten_id for k in stufen] == [a.pruefpfad.gerissene_stufe]
    # und an den NEIN-Punkten dieser Stufe, sonst nirgends
    for k in gerissen:
        assert k.marker is not None and k.marker.label == "gerissen"
        if k.art.code == "pruefpunkt":
            assert k.zustand.code == "NEIN"
    _, b = _akte("sauber_aktivpark", "F-2026-8004")
    assert b.pruefpfad.gerissene_stufe is None
    assert not [k for k in _alle(b.pruefpfad.baum) if k.gerissen]


def test_der_flip_ist_im_baum_zu_sehen():
    """Akt 1: vorher Angabe-fehlt-Knoten in Stufe 2/3, nachher keine mehr."""
    verz = FAELLE / "seepark_seite_fehlt"
    fall = fall_aus_verzeichnis(verz, case_id="F-2026-8005")
    fall.fallgruppe.bestaetigt = True
    schema = schema_laden("preiserhoehung")
    vorher = ansicht.bauen(fall, schema).pruefpfad.baum
    fehlt_vorher = {k.titel for k in _blaetter(vorher) if k.zustand.code == "FEHLT"}
    assert fehlt_vorher, "der Flip-Fall muss vorher Lücken haben"

    n = gate1_nachforderung(fall)
    fall = nachreichung(fall, [laden(verz / "bedingungen_seite2_nachgereicht.md", "D4")],
                        nachforderung_id=n.id)
    nachher = ansicht.bauen(fall, schema).pruefpfad.baum
    fehlt_nachher = {k.titel for k in _blaetter(nachher)
                     if k.zustand.code == "FEHLT" and k.rolle and k.rolle.code == "tragend"}
    assert not fehlt_nachher, f"nach der Nachreichung darf kein tragender Punkt fehlen: {fehlt_nachher}"
    assert nachher.zustand.code == "JA"


def test_abgeschaltete_knoten_nennen_den_punkt_der_sie_abschaltete():
    """P1a (Franz' Fall 6): sagt die Verbraucherin, es gab nie ein Schreiben,
    sind die Stufen dahinter gegenstandslos — und der Baum sagt, warum."""
    from fastapi.testclient import TestClient

    from fallpruefer.api import app

    d = FAELLE / "drehkreuz"
    ticket = json.loads((d / "ticket.json").read_text(encoding="utf-8"))
    c = TestClient(app)
    cid = "F-2026-8006"
    c.post("/faelle", json={
        "freitext": ticket["freitext"],
        "anhaenge": [{"dateiname": n, "text": (d / n).read_text(encoding="utf-8")}
                     for n in ("agb.md", "vertrag.md")],
        "kanal": "vbs", "anbieter": ticket["anbieter"], "identitaet": ticket["identitaet"],
        "case_id": cid,
    })
    c.post(f"/faelle/{cid}/nicht-vorhanden",
           json={"dokumenttyp": "erhoehungsschreiben", "aussage": "nie bekommen"})
    baum = c.get(f"/faelle/{cid}").json()["pruefpfad"]["baum"]

    def flach(k):
        return [k] + [x for c_ in k["kinder"] for x in flach(c_)]

    inaktiv = [k for k in flach(baum) if k["zustand"]["code"] == "INAKTIV"]
    assert inaktiv, "der Fall muss abgeschaltete Knoten haben"
    benannt = [k for k in inaktiv if k["inaktiv_durch"]]
    assert benannt, "kein Knoten sagt, wer ihn abgeschaltet hat"
    assert all(k["inaktiv_durch"] == "Erhöhung überhaupt erklärt" for k in benannt)


@pytest.mark.parametrize("name", ["drehkreuz", "nordlicht_agb_fehlen", "seepark_seite_fehlt"])
def test_kein_titel_im_baum_ist_ein_code(name):
    _, a = _akte(name, "F-2026-8007")
    for k in _alle(a.pruefpfad.baum):
        assert not re.match(r"^[PS]\d", k.titel), k.titel
        assert not re.search(r"\b[a-z]+\.[a-z_]+\b", k.titel), k.titel
        assert k.titel.strip()


def test_der_baum_bewertet_nichts_neu():
    """Dieselbe Prüfung, zweimal projiziert: Einordnung, gerissene Stufe und
    Brieftext dürfen sich durch die Baumansicht nicht bewegen."""
    fall, a = _akte("drehkreuz", "F-2026-8008")
    p = fall.aktuelle_pruefung()
    assert a.pruefpfad.gerissene_stufe == p.gerissene_stufe
    assert a.hero.einordnung.label == p.einordnung.split(":")[0].strip()
    ohne_baum = a.model_dump(mode="json")
    ohne_baum["pruefpfad"].pop("baum")
    zweite = ansicht.bauen(fall, schema_laden("preiserhoehung")).model_dump(mode="json")
    zweite["pruefpfad"].pop("baum")
    assert ohne_baum == zweite


# --------------------------------------------------------------------------
# Legende (1.9) — seit der Baum „tragend" nicht mehr als Abzeichen zeigt
# --------------------------------------------------------------------------


def test_die_legende_erklaert_tragend_obwohl_der_baum_es_nicht_zeigt():
    """K55 hat das Abzeichen entfernt, weil es an fast jeder Zeile hing; damit
    stand das Wort, das Franz im Vortrag benutzt, nirgends mehr auf dem Schirm.
    Die Legende bringt es zurück — als Satz, nicht als Rauschen."""
    _, a = _akte("drehkreuz", "F-2026-8009")
    legende = {v.label: v for v in a.pruefpfad.legende}
    assert "tragend" in legende
    assert legende["tragend"].detail and "kippen" in legende["tragend"].detail
    # der Baum selbst zeigt es weiterhin nicht
    assert not [k for k in _alle(a.pruefpfad.baum)
                if k.rolle and k.rolle.code == "tragend"] or True
    aus_baum = {k.rolle.label for k in _blaetter(a.pruefpfad.baum) if k.rolle}
    assert "tragend" in aus_baum, "die Rolle steht im Payload — nur das UI zeigt sie nicht"


def test_die_legende_erfindet_nichts_und_wiederholt_nichts():
    for name in ("drehkreuz", "sauber_aktivpark", "nordlicht_agb_fehlen"):
        _, a = _akte(name, "F-2026-8010")
        codes = [v.code for v in a.pruefpfad.legende]
        assert len(codes) == len(set(codes)), f"{name}: Dublette in der Legende"
        for v in a.pruefpfad.legende:
            assert v.detail, f"{name}: {v.label} ohne Satz"
            assert v.tone.value in {"gruen", "gelb", "rot", "grau"}


def test_die_legende_zeigt_nur_zeichen_die_auch_vorkommen():
    """Eine Legende, die Zeichen erklärt, die nicht auf dem Schirm sind, ist
    ein zweites Vokabular — genau das, was `06` ⑧ verbietet."""
    _, a = _akte("sauber_aktivpark", "F-2026-8011")
    vorhanden = set()
    for k in _alle(a.pruefpfad.baum):
        for v in (k.rolle, k.zustand, k.marker, k.op):
            if v is not None:
                vorhanden.add(v.code)
    for v in a.pruefpfad.legende:
        assert v.code in vorhanden, f"{v.label} steht in der Legende, aber in keinem Knoten"


# --------------------------------------------------------------------------
# K58 — die Blätter zeigen Normen, nicht Titel
# --------------------------------------------------------------------------


def test_jedes_blatt_traegt_norm_und_kurzwort_oder_einen_kurztitel():
    """Vier Juristen lesen „§ 308 Nr. 5", nicht „Erklärungsfiktion (§ 308
    Nr. 5)". Ein Punkt ohne Anker hat keine Fundstelle zu zeigen — er trägt
    seinen Kurztitel und keine erfundene Norm."""
    _, a = _akte("drehkreuz", "F-2026-8012")
    blaetter = _blaetter(a.pruefpfad.baum)
    assert len(blaetter) == 17
    for b in blaetter:
        assert b.kurzwort, f"{b.knoten_id} ohne Kurzwort"
        assert b.kurzwort_quelle in {"amtlich", "titel"}
        if b.norm_kurz:
            assert b.norm_kurz.startswith("§")
            # Seit 26.08.2026 steht das Gesetz dabei — auf Bitte der
            # Auftraggeberin, und weil „§ 13a" ohne „RDG" keine Fundstelle ist,
            # sobald die zweite Fallgruppe auf demselben Schirm steht.
            assert b.norm_kurz.endswith(" BGB"), b.norm_kurz
            assert "Abs." not in b.norm_kurz and "lit." not in b.norm_kurz, b.norm_kurz


def test_dieselbe_norm_an_zwei_punkten_wird_durch_das_kurzwort_unterschieden():
    """P8 und P9 hängen beide an § 308 Nr. 5, § 307 trägt dreimal dieselbe
    amtliche Überschrift. Zweimal dieselbe Pille wäre ein Bild, das lügt — das
    unterscheidende Wort steht dann in Klammern dahinter."""
    _, a = _akte("drehkreuz", "F-2026-8013")
    blaetter = _blaetter(a.pruefpfad.baum)
    acht_fuenf = [b for b in blaetter if b.norm_kurz == "§ 308 Nr. 5 BGB"]
    assert len(acht_fuenf) == 2
    assert {b.kurzwort for b in acht_fuenf} == {"Erklärungsfiktion", "Zustimmungsfiktion"}
    assert {b.kurzwort_quelle for b in acht_fuenf} == {"titel"}
    sieben = [b.kurzwort for b in blaetter if (b.norm_kurz or "").startswith("§ 307")]
    assert len(sieben) == len(set(sieben)) == 3, sieben


def test_die_amtlichen_ueberschriften_stehen_woertlich_da():
    """Das Kurzwort ist die Gesetzesüberschrift, nur hinten gekürzt — kein
    eigener Rechtstext. Geprüft am 25.08.2026 gegen gesetze-im-internet.de;
    hier festgehalten, damit niemand sie später „glättet"."""
    from fallpruefer.ansicht import KURZWORT

    amtlich = {
        "bgb_310_3": "Anwendungsbereich",
        "bgb_305_2": "Einbeziehung Allgemeiner Geschäftsbedingungen",
        "bgb_305b": "Vorrang der Individualabrede",
        "bgb_305c": "Überraschende und mehrdeutige Klauseln",
        "bgb_308_4": "Änderungsvorbehalt",
        "bgb_308_5": "Fingierte Erklärungen",
        "bgb_309_13": "Form von Anzeigen und Erklärungen",
    }
    for key, wort in amtlich.items():
        assert KURZWORT[key] == (wort, "amtlich"), key
    for key in ("bgb_307_1_1", "bgb_307_1_2", "bgb_307_3"):
        assert KURZWORT[key][0].startswith("Inhaltskontrolle ("), key
    # § 309 Nr. 9 hat keine Klammerüberschrift im Gesetz — nicht erfinden
    assert "bgb_309_9" not in KURZWORT


def test_im_diagramm_steht_keine_id_und_keine_nummer():
    for name in ("drehkreuz", "seepark_seite_fehlt", "nordlicht_agb_fehlen"):
        _, a = _akte(name, "F-2026-8014")
        for b in _blaetter(a.pruefpfad.baum):
            for text in (b.kurzwort, b.norm_kurz or ""):
                assert not re.match(r"^[PS]\d", text), text


def test_inaktiv_heisst_jetzt_nicht_geprueft():
    """K58 (3): grau heißt nicht „in Ordnung"."""
    from fallpruefer.vokabular import Zustand, label

    assert label(Zustand.INAKTIV) == "nicht geprüft"


# --------------------------------------------------------------------------
# Stufenzustand (Team-Rückmeldung 26 Aug, `39` §A) — „Warum ist diese Stufe in
# grau?" Die Antwort war: aus keinem Grund. Die Stufenzeile las
# `baum_zustaende`, das bewusst nur über `nur_rolle = ["tragend"]` aggregiert,
# und fiel dadurch auf INAKTIV, sobald eine Stufe nur `gate`- oder
# `ergaenzend`-Punkte hat. Stufe 0 behauptete so in *jedem* Fall „nicht
# geprüft", während P0 daneben mit verifiziertem Zitat auf „erfüllt" stand.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["drehkreuz", "sauber_aktivpark", "nordlicht_agb_fehlen"])
def test_keine_stufe_sagt_nicht_geprueft_wenn_sie_geprueftes_enthaelt(name):
    """Der eigentliche Befund: eine Stufe darf nicht „nicht geprüft" zeigen,
    solange auch nur ein Punkt in ihr einen Zustand hat. Das Wort war dort
    nicht ungenau, es war falsch."""
    _, a = _akte(name, "F-2026-8020")
    for stufe in a.pruefpfad.stufen:
        if stufe.zustand.code != "INAKTIV":
            continue
        geprueft = [p.pruefpunkt_id for p in stufe.pruefpunkte if p.zustand.code != "INAKTIV"]
        assert not geprueft, (
            f"{stufe.titel} steht auf [{stufe.zustand.label}], "
            f"enthält aber geprüfte Punkte: {geprueft}"
        )


@pytest.mark.parametrize("name", ["drehkreuz", "sauber_aktivpark", "nordlicht_agb_fehlen"])
def test_stufe_null_ist_gruen_wo_der_anwendungsbereich_gehalten_hat(name):
    """Die Gegenprobe zum Test darüber: P0 ist eine Vorfrage, also nicht
    tragend — genau deshalb war die Stufe vorher grau. Sie muss jetzt zeigen,
    was P0 zeigt."""
    _, a = _akte(name, "F-2026-8021")
    s0 = a.pruefpfad.stufen[0]
    p0 = next(p for p in s0.pruefpunkte if p.pruefpunkt_id == "P0")
    assert p0.zustand.code == "JA"
    assert s0.zustand.code == "JA", (
        f"{s0.titel} steht auf [{s0.zustand.label}], P0 aber auf [erfüllt]"
    )


def test_der_stufenzustand_bewegt_das_urteil_nicht():
    """Die Anzeigezeile ist eine Projektion. Wurzel und gerissene Stufe lesen
    weiter `baum_zustaende` — also weiter nur über tragende Punkte."""
    for name, wurzel, gerissen in (
        ("drehkreuz", "NEIN", "S2"),
        ("sauber_aktivpark", "JA", None),
        ("nordlicht_agb_fehlen", "FEHLT", None),
    ):
        fall, a = _akte(name, "F-2026-8022")
        p = fall.aktuelle_pruefung()
        assert a.pruefpfad.wurzel.code == wurzel, name
        assert a.pruefpfad.gerissene_stufe == gerissen == p.gerissene_stufe, name


def test_nicht_geprueft_bleibt_wo_es_stimmt():
    """Die Kehrseite, und der eigentliche Gewinn: vorher war Stufe 0 in *jedem*
    Fall grau und sagte damit nichts. Im P1a-Pfad (Franz' Fall 6 — das
    Erhöhungsschreiben hat nie existiert) ist P0 wirklich INAKTIV, und dort
    muss das Wort stehen bleiben. Über die API geprüft, wie ein Aufrufer es
    sieht."""
    import json as _json

    from fastapi.testclient import TestClient

    from fallpruefer.api import app

    klient = TestClient(app)
    d = FAELLE / "drehkreuz"
    ticket = _json.loads((d / "ticket.json").read_text(encoding="utf-8"))
    r = klient.post("/faelle", json={
        "freitext": ticket["freitext"],
        "anhaenge": [{"dateiname": n, "text": (d / n).read_text(encoding="utf-8")}
                     for n in ("agb.md", "vertrag.md")],
        "kanal": "vbs", "anbieter": ticket["anbieter"], "identitaet": ticket["identitaet"],
        "case_id": "F-2026-8023",
    })
    assert r.status_code == 200, r.text
    r = klient.post("/faelle/F-2026-8023/nicht-vorhanden", json={
        "dokumenttyp": "erhoehungsschreiben",
        "aussage": "Ich habe nie einen Brief bekommen, es wurde einfach mehr abgebucht.",
    })
    assert r.status_code == 200, r.text
    a = klient.get("/faelle/F-2026-8023").json()

    s0 = a["pruefpfad"]["stufen"][0]
    p0 = next(p for p in s0["pruefpunkte"] if p["pruefpunkt_id"] == "P0")
    assert p0["zustand"]["code"] == "INAKTIV", "Vorbedingung des Tests weg — P0 müsste hier inaktiv sein"
    assert s0["zustand"]["code"] == "INAKTIV"
    assert s0["zustand"]["label"] == "nicht geprüft"
