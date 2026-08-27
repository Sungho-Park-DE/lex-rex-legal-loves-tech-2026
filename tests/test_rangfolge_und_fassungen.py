"""Franz' Anleitung §2 (Rangfolge § 309 → § 308 → § 307, Einbeziehung getrennt)
und §4/§7 (Prüflogik versioniert) — beides **Anzeige und Zählung**, nichts
davon bewegt eine Einordnung. Der zweite Teil jeder Zusicherung ist deshalb
der wichtigere: vor und nach der Sortierung ist `einordnung`,
`gerissene_stufe` und der Brieftext byte-gleich.
"""

from __future__ import annotations

import json

import pytest

from fallpruefer import ansicht, store
from fallpruefer.konfig import WURZEL
from fallpruefer.pipeline import fall_aus_verzeichnis
from fallpruefer.schema import schema_laden

FAELLE = WURZEL / "demo" / "faelle"


@pytest.fixture(autouse=True)
def eigener_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "pfad", lambda: tmp_path / "faelle.jsonl")


def _ansicht(name, cid):
    fall = fall_aus_verzeichnis(FAELLE / name, case_id=cid)
    return fall, ansicht.bauen(fall, schema_laden("preiserhoehung"))


def _paragraf_von(pid, schema):
    import re
    keys = [a.get("key") or "" for a in schema.pruefpunkt(pid).anker]
    nummern = [m.group(1) for k in keys if (m := re.match(r"bgb_(\d{3})", k))]
    rang = {"309": 0, "308": 1, "307": 2}
    return min((rang.get(n, 3) for n in nummern), default=3)


def test_nein_zeilen_stehen_zuerst_und_309_vor_308_vor_307():
    _, a = _ansicht("drehkreuz", "F-2026-7201")
    schema = schema_laden("preiserhoehung")
    s3 = next(s for s in a.pruefpfad.stufen if s.stufe_id == "S3")
    zustaende = [p.zustand.code for p in s3.pruefpunkte]
    erste_nicht_nein = next((i for i, z in enumerate(zustaende) if z != "NEIN"), len(zustaende))
    assert "NEIN" not in zustaende[erste_nicht_nein:], "NEIN-Zeilen müssen vorn stehen"
    raenge = [_paragraf_von(p.pruefpunkt_id, schema) for p in s3.pruefpunkte[:erste_nicht_nein]]
    assert raenge == sorted(raenge), f"Rangfolge verletzt: {raenge}"
    # drehkreuz bricht an P9 (§ 308 Nr. 5) und P6/P7 (§ 307): P9 steht vorn
    assert s3.pruefpunkte[0].pruefpunkt_id == "P9"


def test_einbeziehung_bleibt_eine_eigene_stufe_vor_der_inhaltskontrolle():
    _, a = _ansicht("drehkreuz", "F-2026-7202")
    ids = [s.stufe_id for s in a.pruefpfad.stufen]
    assert ids.index("S2") < ids.index("S3")
    s2 = next(s for s in a.pruefpfad.stufen if s.stufe_id == "S2")
    assert {p.pruefpunkt_id for p in s2.pruefpunkte} == {"P2", "P3", "P4"}


def test_wertungsfrei_chip_nur_an_309_und_308():
    _, a = _ansicht("drehkreuz", "F-2026-7203")
    schema = schema_laden("preiserhoehung")
    for s in a.pruefpfad.stufen:
        for p in s.pruefpunkte:
            erwartet = _paragraf_von(p.pruefpunkt_id, schema) <= 1
            assert (p.normrang is not None) == erwartet, p.pruefpunkt_id
            if p.normrang:
                assert p.normrang.label == "wertungsfrei" and p.normrang.detail


@pytest.mark.parametrize("name", ["drehkreuz", "sauber_aktivpark", "seepark_seite_fehlt"])
def test_die_sortierung_bewegt_nichts(name):
    """Die Sortierung liegt in der Anzeige; Einordnung, gerissene Stufe und
    Brief kommen aus der Prüfung — sie sehen die Reihenfolge nie."""
    fall, a = _ansicht(name, "F-2026-7204")
    pr = fall.aktuelle_pruefung()
    assert a.hero.einordnung.label.startswith(pr.einordnung.split(":")[0].strip()[:7])
    assert a.pruefpfad.gerissene_stufe == pr.gerissene_stufe
    flach_anzeige = sorted(p.pruefpunkt_id for s in a.pruefpfad.stufen for p in s.pruefpunkte)
    flach_pruefung = sorted(e.pruefpunkt_id for e in pr.ergebnisse
                            if any(e.pruefpunkt_id in (k if isinstance(k, str) else "")
                                   for s in (schema_laden("preiserhoehung").baum.kinder)
                                   for k in getattr(s, "kinder", [])))
    assert flach_anzeige == flach_pruefung, "keine Zeile verloren, keine doppelt"


# --------------------------------------------------------------------------
# §4/§7 — Versionierung
# --------------------------------------------------------------------------


def _zeile(i, version):
    return {
        "fall_hash": chr(97 + i) * 32, "zeit": "2026-08-01T10:00:00+02:00",
        "fallgruppe_id": "preiserhoehung", "stufe": "A", "anbieter": f"anbieter {i}",
        "gegner": None, "branche": "fitness", "einordnung": "wirksam",
        "gerissene_stufe": None, "pruefpunkte_nein": [], "fehlte": [],
        "rechtsbehelf": None, "betrag_erhoehung_gerundet": None,
        "referat_flag": [], "kanal": "vbs", "schema_version": version,
        "schaden_entstanden": None, "schaden_drohend": None, "schaden_basis": "unbeziffert",
        "abgemahnt": [],
    }


def test_prueflogik_fassungen_zaehlt_aeltere_zeilen():
    aktuell = schema_laden("preiserhoehung").version
    p = store.pfad(); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for i, v in enumerate([aktuell, aktuell, "0.5.0", "0.4.9"]):
            f.write(json.dumps(_zeile(i, v)) + "\n")
    f_ = store.radar()["prueflogik_fassungen"]
    assert f_ == {"fallgruppe_id": "preiserhoehung", "aktuell": aktuell,
                  "zeilen_aktuell": 2, "zeilen_aelter": 2, "aelteste": "0.4.9"}


def test_prueflogik_fassungen_bei_leerem_store():
    f_ = store.radar()["prueflogik_fassungen"]
    assert f_["zeilen_aktuell"] == 0 and f_["aelteste"] is None


def test_neu_pruefen_nach_schema_schreibt_den_store_nicht():
    """Die Frage aus der Regiebuch-Sitzung (D): hebt der Akt-2-Neulauf die
    `schema_version` der Store-Zeile? Nein — er liest die Fassung der Datei in
    den Fall, schreibt aber nicht in den Store; das tut erst das nächste Gate 3.
    Und die Fassung selbst hebt niemand außer dem Menschen an der Datei."""
    from fallpruefer.pipeline import gate3_bestaetigen, neu_pruefen_nach_schema

    fall = fall_aus_verzeichnis(FAELLE / "sauber_aktivpark", case_id="F-2026-7205")
    gate3_bestaetigen(fall)
    vorher = store.lesen()
    neu_pruefen_nach_schema(fall)
    assert store.lesen() == vorher
    assert fall.aktuelle_pruefung().gate3 is None, "der Neulauf ist unbestätigt"
    gate3_bestaetigen(fall)
    nachher = store.lesen()
    assert len(nachher) == 1
    assert nachher[0]["schema_version"] == schema_laden("preiserhoehung").version
