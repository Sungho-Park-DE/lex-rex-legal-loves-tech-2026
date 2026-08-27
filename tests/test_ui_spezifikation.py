"""Die UI-Spezifikation gegen das, was sie beschreibt.

Zweimal ist `docs/lovable_prompt.md` hinter dem View Model zurückgeblieben,
ohne dass es jemand bemerkte. Beim ersten Mal (1.0 -> 1.1) stand es zwei
Wochen lang falsch im Repo und wurde erst beim Aufräumen des Registers
gefunden; der Befund lautete beide Male gleich — ein Schlüssel, den die Fixture
liefert, kommt im Pack **null mal** vor, und niemand merkt es, weil das Pack
kein Programm ist und niemand es ausführt.

Die Folge ist nicht kosmetisch: ein Frontend, das gegen ein Pack ohne
`laeufe[]` gebaut wird, kann den Flip nicht zeigen, und der Flip ist einer der
vier Beats aus `14` §7, die nie gekürzt werden. Deshalb läuft das Pack ab jetzt
in der Suite mit.

Die Prüfungen hier sind bewusst grob: sie fragen „kommt der Name überhaupt
vor", nicht „ist die Beschreibung gut". Ein Test, der Prosa bewertet, wird bei
jeder Umformulierung rot und wird dann abgeschaltet.
"""

from __future__ import annotations

import json

import pytest

from fallpruefer.konfig import WURZEL

PACK = WURZEL / "docs" / "lovable_prompt.md"
FIXTUREN = {
    "drehkreuz": WURZEL / "demo" / "fixtures" / "drehkreuz_fallakte.json",
    "seepark": WURZEL / "demo" / "fixtures" / "seepark_fallakte.json",
    "nordlicht": WURZEL / "demo" / "fixtures" / "nordlicht_fallakte.json",
}
TOENE = {"gruen", "gelb", "rot", "grau"}


def _fixture(name: str) -> dict:
    return json.loads(FIXTUREN[name].read_text(encoding="utf-8"))


def _pack() -> str:
    return PACK.read_text(encoding="utf-8")


def test_das_pack_kennt_jeden_schluessel_des_viewmodels():
    """Der Befund, der C2 war: `laeufe[]` und `nachforderungen[]` kamen im Pack
    nicht vor, und ein danach gebautes Frontend hätte den Flip nicht zeigen
    können."""
    pack = _pack()
    daten = _fixture("drehkreuz")

    fehlend = sorted(k for k in daten if k not in pack)
    assert not fehlend, (
        f"docs/lovable_prompt.md nennt diese View-Model-Schlüssel nicht: {fehlend}. "
        "Ein Frontend, das gegen dieses Pack gebaut wird, kennt sie nicht."
    )
    assert daten["ansicht_version"] in pack, (
        f"Das Pack nennt ansicht_version {daten['ansicht_version']} nicht — "
        "es beschreibt eine ältere Fassung des View Models."
    )


@pytest.mark.parametrize("name", sorted(FIXTUREN))
def test_jedes_zitat_ist_per_teilstring_auffindbar(name: str):
    """Klick-zum-Markieren ist die eine Interaktion, die stimmen muss (`14` §6).

    Das Pack schreibt dem Frontend plain `indexOf` vor — kein Fuzzy-Matching,
    keine Regex — und verbietet ausdrücklich, eine ungefähre Trefferstelle zu
    markieren. Diese Prüfung tut genau das, was der Browser täte, und zwar auf
    der ausgelieferten Fixture statt im Generator: `tools/demo_fixture.py`
    prüft dasselbe, aber gegen seine eigene Zwischenrechnung.
    """
    daten = _fixture(name)
    seiten = {
        (dok["dok_id"], seite["nr"]): seite["text_original"]
        for dok in daten["dokumente"]
        for seite in dok["seiten"]
    }

    tot: list[tuple] = []
    gesamt = 0

    def geh(objekt) -> None:
        nonlocal gesamt
        if isinstance(objekt, dict):
            if {"dok_id", "seite", "zitat"} <= set(objekt):
                gesamt += 1
                text = seiten.get((objekt["dok_id"], objekt["seite"]))
                if text is None or objekt["zitat"] not in text:
                    tot.append((objekt["dok_id"], objekt["seite"], objekt["zitat"][:60]))
            for wert in objekt.values():
                geh(wert)
        elif isinstance(objekt, list):
            for wert in objekt:
                geh(wert)

    geh(daten)
    assert gesamt > 0, "keine Zitate in der Fixture — der Test misst nichts"
    assert not tot, (
        f"{len(tot)} von {gesamt} Zitaten sind auf ihrer Seite nicht als Teilstring "
        f"auffindbar; das Frontend zeigte dort 'Zitat nicht im Dokument gefunden': {tot[:3]}"
    )


@pytest.mark.parametrize("name", sorted(FIXTUREN))
def test_jede_vokabel_traegt_einen_gueltigen_ton(name: str):
    """Die UI koloriert nach `tone` und darf keine Farbe selbst wählen
    (Knowledge-Regel 2). Ein `tone`, den sie nicht kennt, führt zu genau dem —
    die Komponente fällt auf einen eigenen Standard zurück."""
    schlecht: list[str] = []

    def geh(objekt, pfad: str = "") -> None:
        if isinstance(objekt, dict):
            if "code" in objekt and "label" in objekt and objekt.get("tone") not in TOENE:
                schlecht.append(f"{pfad}: {objekt}")
            for schluessel, wert in objekt.items():
                geh(wert, f"{pfad}.{schluessel}")
        elif isinstance(objekt, list):
            for i, wert in enumerate(objekt):
                geh(wert, f"{pfad}[{i}]")

    geh(_fixture(name))
    assert not schlecht, f"Vokabeln ohne gültigen tone: {schlecht[:3]}"


def test_die_zweite_fixture_traegt_die_beats_die_nur_sie_zeigt():
    """Das Pack sagt „gegen F-2026-0001 bauen, gegen F-2026-0002 prüfen", weil
    nur die zweite zwei Läufe und eine Nachforderung hat. Verliert sie das —
    etwa weil jemand sie aus einem anderen Fall neu erzeugt —, wird aus dem
    Prüfschritt eine Formalie, die nichts mehr prüft."""
    flip = _fixture("seepark")

    assert len(flip["laeufe"]) >= 2, "die Flip-Fixture hat keinen zweiten Lauf mehr"
    assert sum(1 for lauf in flip["laeufe"] if lauf["aktuell"]) == 1
    einordnungen = [lauf["einordnung"] for lauf in flip["laeufe"]]
    assert len(set(einordnungen)) >= 2, (
        f"beide Läufe tragen dieselbe Einordnung {einordnungen} — "
        "der Flip ist nur als Paar lesbar und wäre hier keins"
    )
    assert flip["nachforderungen"], "keine Gate-1-Nachforderung mehr in der Flip-Fixture"

    einfach = _fixture("drehkreuz")
    assert len(einfach["laeufe"]) == 1, (
        "die Happy-Path-Fixture hat mehr als einen Lauf — dann prüft der "
        "Ein-Chip-Fall des LaeufeStrip (P12) nichts mehr"
    )


def test_die_dritte_fixture_traegt_den_offenen_fall():
    """F-2026-0003 ist der einzige Fall, in dem die Verbraucherseite offen ist.

    Die anderen beiden sind fertig: `vollstaendigkeit.verbraucher` ist dort
    leer, und damit war alles unerreichbar, was die UI nur an einem offenen
    Fall rendert — der gelbe Hero, die Verbraucher-Posten und vor allem die
    „Existiert nicht"-Aktion (V-N2), deren Gate K6 gerade erst repariert hat,
    ohne dass irgendeine Fixture den Knopf je hätte zeigen können."""
    offen = _fixture("nordlicht")

    assert offen["hero"]["einordnung"]["tone"] == "gelb"
    posten = offen["hero"]["vollstaendigkeit"]["verbraucher"]
    assert posten, "keine offenen Verbraucher-Posten — der offene Fall ist keiner mehr"
    for p in posten:
        assert p["fehlzustand"], "ein offener Posten ohne fehlzustand"
        assert p["fehlzustand"]["code"] != "existiert_nicht", (
            "schon als existiert_nicht markiert — dann ist die Aktion wieder unsichtbar"
        )
    assert offen["nachforderungen"], "keine Gate-1-Nachforderung im offenen Fall"
    assert offen["nachforderungen"][0]["status"]["code"] == "offen", (
        "die Nachforderung ist nicht mehr offen — die Panel-Aktionen hätten nichts zu tun"
    )
    # und die beiden fertigen bleiben fertig, sonst prüft dieser Test bald nichts
    for name in ("drehkreuz", "seepark"):
        assert not _fixture(name)["hero"]["vollstaendigkeit"]["verbraucher"]
