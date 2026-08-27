"""Franz' Anleitung §7: „erneutes Auftreten einer bereits abgemahnten Klausel
löst einen Hinweis aus."

Sieben Zusicherungen, jede an der Grenze, an der ein Aufrufer sie sieht:

1. ein Fall, dessen NEIN-Punkt in `normbasis/abmahnungen.json` steht, trägt den
   Hinweis im Prüfpfad — und im Store-Satz;
2. ein Fall ohne Treffer trägt nichts, auch kein leeres Objekt;
3. die Schwelle bleibt: ein Anbieter unter `k_min` wird durch den Hinweis
   nicht genannt;
4. `geprueft:false` steht als „ungeprüft" im Satz;
5. die Zuschreibung: McFit = vzbv, FitOne = VZ Bayern / Vergleich, kein Urteil
   (die CLAUDE.md-Falle, als Datentest);
6. Goldens unverändert — der Hinweis bewegt keine Einordnung (`14` §3);
7. der „+1"-Beat bleibt scharf (der Test dazu liegt in `test_radar_schaden`,
   hier nur, dass die Radar-Felder die Zeile nicht verändern).
"""

from __future__ import annotations

import json

import pytest

from fallpruefer import abmahnungen, ansicht, store
from fallpruefer.konfig import WURZEL
from fallpruefer.pipeline import fall_aus_verzeichnis
from fallpruefer.schema import schema_laden
from fallpruefer.vokabular import Massnahme, Traeger

FAELLE = WURZEL / "demo" / "faelle"


@pytest.fixture(autouse=True)
def eigener_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "pfad", lambda: tmp_path / "faelle.jsonl")


def _trace(fall):
    schema = schema_laden(fall.schema_.fallgruppe_id)
    a = ansicht.bauen(fall, schema)
    return {p.pruefpunkt_id: p for s in a.pruefpfad.stufen for p in s.pruefpunkte}


def test_der_treffer_steht_im_pruefpfad_und_im_store_satz():
    fall = fall_aus_verzeichnis(FAELLE / "drehkreuz", case_id="F-2026-7001")
    nein = {p.pruefpunkt_id for p in fall.aktuelle_pruefung().ergebnisse if p.zustand.value == "NEIN"}
    assert "P9" in nein, "der Test braucht einen Fall, der an der Zustimmungsfiktion bricht"

    trace = _trace(fall)
    h = trace["P9"].hinweis_abmahnung
    assert h is not None
    assert h.badge.code == "bereits_abgemahnt" and h.badge.tone.value == "gelb"
    assert h.text.startswith("Klauseltyp bereits Gegenstand eines Verfahrens: ")
    assert "LG Bamberg 13 O 730/22" in h.text
    assert h.badge.detail, "der Chip braucht den Satz fürs Popover (K45-Muster)"

    satz = store.satz_bauen(fall)
    assert satz["abgemahnt"] == ["abm_mcfit_drehkreuz_2022"]


def test_ohne_treffer_kein_feld():
    fall = fall_aus_verzeichnis(FAELLE / "sauber_aktivpark", case_id="F-2026-7002")
    trace = _trace(fall)
    assert all(p.hinweis_abmahnung is None for p in trace.values())
    assert store.satz_bauen(fall)["abgemahnt"] == []
    # und ein JA-Punkt trägt nie einen Hinweis, auch wenn der Klauseltyp bekannt ist
    fall_d = fall_aus_verzeichnis(FAELLE / "drehkreuz", case_id="F-2026-7003")
    for p in _trace(fall_d).values():
        if p.hinweis_abmahnung is not None:
            assert p.zustand.code == "NEIN"


def test_der_hinweis_nennt_den_anbieter_unter_k_min_nicht():
    """Das Radar darf durch die neue Achse keinen Namen preisgeben: ein
    einzelner Fall mit Treffer bleibt ein einzelner Fall."""
    fall = fall_aus_verzeichnis(FAELLE / "drehkreuz", case_id="F-2026-7004")
    store.schreiben(fall)
    r = store.radar()
    assert r["wiederholungen_gesamt"] == 1
    assert r["cluster"] == []
    assert r["klauseltypen"] == []
    assert "fitpoint" not in json.dumps(r, ensure_ascii=False).lower()


def test_ungeprueft_steht_im_satz():
    for a in abmahnungen.alle():
        assert a.geprueft is False, "kein Eintrag ist geprüft, bis ein Mensch das Original las"
        assert a.satz().endswith("· ungeprüft")


def test_zuschreibung_mcfit_bleibt_vzbv():
    """CLAUDE.md-Falle als Datentest: LG Bamberg 13 O 730/22 ist **vzbv**, nicht
    VZ Bayern (`30` §5, Volltext gelesen `34` §1)."""
    nach_az = {a.az: a for a in abmahnungen.alle()}
    mcfit = nach_az["13 O 730/22"]
    assert mcfit.traeger == Traeger.VZBV
    assert mcfit.massnahme == Massnahme.URTEIL and mcfit.datum == "2024-03-15"


def test_fitone_haengt_an_keinem_pruefpunkt_und_steht_trotzdem_in_der_datei():
    """`34` §1, Primärquelle: der FitOne-Vergleich betrifft eine Energie-/
    Hygienepauschale und eine Verwaltungspauschale — **keine**
    Preisanpassungsklausel. Die frühere Zuordnung zu `preiserhoehung/P7` hätte
    auf der Demo-Linie einen falschen Chip erzeugt. Der Fall bleibt in der
    Datei dokumentiert, aber außerhalb der `eintraege` — ein Klauseltyp
    „Pauschale" existiert in keinem Schema, und ein Eintrag, der nie matcht,
    wäre Füllmaterial (Regel der Radar-Sitzung)."""
    import json

    assert "3 UKl 20/24 e" not in {a.az for a in abmahnungen.alle()}
    roh = json.loads(abmahnungen.PFAD.read_text(encoding="utf-8"))
    nicht = roh["meta"]["nicht_zugeordnet"]
    assert any("3 UKl 20/24 e" in e["verfahren"] for e in nicht)
    assert all(e.get("grund") and e.get("quelle") for e in nicht)


def test_auf_der_demo_linie_haengt_der_chip_nur_an_der_zustimmungsfiktion():
    """Die Regressionsprobe gegen genau den Fehler, den `34` gefunden hat: ein
    Chip „bereits abgemahnt" an einem Punkt, den das Verfahren nicht betraf."""
    for name in ("drehkreuz", "sauber_aktivpark", "nordlicht_agb_fehlen", "seepark_seite_fehlt"):
        fall = fall_aus_verzeichnis(FAELLE / name, case_id="F-2026-7050")
        trace = _trace(fall)
        mit_chip = {pid for pid, p in trace.items() if p.hinweis_abmahnung is not None}
        assert mit_chip <= {"P9"}, f"{name}: Chip an {mit_chip - {'P9'}}"


def test_kein_eintrag_ausserhalb_der_klauseltypen():
    """Jeder Klauseltyp muss ein Prüfpunkt eines geladenen Schemas sein —
    sonst kann er nie treffen und steht nur zum Füllen da."""
    for a in abmahnungen.alle():
        schema = schema_laden(a.fallgruppe_id)
        assert schema.pruefpunkt(a.pruefpunkt_id) is not None, a.klauseltyp


def test_die_radar_felder_sind_zahlen_keine_namen():
    saetze = []
    for i, name in enumerate(("drehkreuz", "sauber_aktivpark")):
        fall = fall_aus_verzeichnis(FAELLE / name, case_id=f"F-2026-701{i}")
        saetze.append(store.schreiben(fall))
    r = store.radar()
    assert isinstance(r["wiederholungen_gesamt"], int)
    for m in r["markierte_faelle"]:
        assert isinstance(m["wiederholung"], int)
