"""V-N2 — „hat es nie gegeben" ist etwas anderes als „liegt noch nicht vor".

Franz' Fall 6: eine Verbraucherin hat nie ein Erhöhungsschreiben bekommen, und
ihren Vertrag hat sie auch nicht — sie hat damals auf einem Tablet mit dem
Finger unterschrieben und nie eine Ausfertigung erhalten. Unser Fehlen-Modell
kannte dafür keinen Zustand, also lief beides als „noch nicht eingereicht", und
Gate 1 hat daraus eine Nachforderung **an die Verbraucherin** gemacht.

Das war die einzige Stelle im Programm, an der heute etwas Falsches an einen
Menschen hinausgegangen wäre — kein internes Modellierungsproblem, sondern ein
Brief mit einer unerfüllbaren Bitte darin.

Die Tests fassen den Endpunkt **über HTTP** an, nicht in-process. Genau diese
Sorte Test hat zuletzt den fehlenden Import in `api.py` gefunden, den 259
grüne In-Process-Tests durchgelassen hatten (`21` §0).
"""

from __future__ import annotations

import itertools
import json

import pytest
from fastapi.testclient import TestClient

from fallpruefer.api import app
from fallpruefer.konfig import WURZEL

NORDLICHT = WURZEL / "demo" / "faelle" / "nordlicht_agb_fehlen"

# Der Satz, auf den sich die Feststellung stützt — O-Ton aus Franz' Fall 6,
# derselbe Sachverhalt wie in Fall 3.
AUSSAGE = (
    "Meinen Vertrag finde ich nicht mehr, ich habe damals irgendwas auf einem "
    "Tablet mit dem Finger unterschrieben und nie eine Ausfertigung bekommen."
)


# Ein Fall wird nach jedem Gate auf Platte geschrieben und beim naechsten
# Aufruf von dort geladen. Eine feste case_id ueber mehrere Tests traegt die
# Feststellung des vorherigen Tests mit — genau die Sorte Kopplung, die einen
# Test gruen laesst, der nichts mehr misst.
_ZAEHLER = itertools.count(9801)


@pytest.fixture
def klient():
    return TestClient(app)


@pytest.fixture
def fall_id(klient):
    case_id = f"F-2026-{next(_ZAEHLER)}"
    ticket = json.loads((NORDLICHT / "ticket.json").read_text(encoding="utf-8"))
    antwort = klient.post("/faelle", json={
        "freitext": ticket["freitext"],
        "anhaenge": [{"dateiname": "schreiben.md",
                      "text": (NORDLICHT / "schreiben.md").read_text(encoding="utf-8")}],
        "kanal": "vbs", "anbieter": ticket["anbieter"],
        "identitaet": ticket["identitaet"], "case_id": case_id,
    })
    assert antwort.status_code == 200, antwort.text
    return case_id


# Die Anzeige nennt den Anzeigenamen aus dem Dokumenten-Soll, nicht den Code.
VERTRAG_TEXT = "den Mitgliedsvertrag oder das Anmeldeformular"


def _seite(klient, fall_id, wer: str) -> list[dict]:
    """Die Vollständigkeit, nicht `offene_punkte`: letztere zeigt bewusst nur
    die Verbraucherseite, weil sie die Liste dessen ist, was man die Kundin
    fragt. Der Wechsel der Seite ist genau deshalb dort **nicht** sichtbar —
    er ist es in der Vollständigkeit."""
    sicht = klient.get(f"/faelle/{fall_id}").json()
    return sicht["hero"]["vollstaendigkeit"][wer]


def _dokumenttypen(posten: list[dict]) -> set[str]:
    return {p["dokumenttyp"]["code"] for p in posten if p.get("dokumenttyp")}


def test_ohne_die_feststellung_fordert_gate1_den_vertrag_beim_verbraucher_an(klient, fall_id):
    """Der Ausgangszustand, damit der Test danach etwas misst."""
    antwort = klient.post(f"/faelle/{fall_id}/nachforderung", json={})
    assert antwort.status_code == 200, antwort.text
    assert "vertrag" in antwort.json()["dokumente"]


def test_nach_der_feststellung_fragt_gate1_den_verbraucher_nicht_mehr(klient, fall_id):
    antwort = klient.post(f"/faelle/{fall_id}/nicht-vorhanden",
                          json={"dokumenttyp": "vertrag", "aussage": AUSSAGE})
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert daten["nicht_vorhanden"] == ["vertrag"]
    assert "vertrag" not in daten["offen_verbraucher"]

    # und der Brief, den Gate 1 erzeugt, bittet auch nicht mehr darum
    n = klient.post(f"/faelle/{fall_id}/nachforderung", json={}).json()
    assert "vertrag" not in n["dokumente"]
    # je angefordertem Dokument ein Block „- <Anzeigename>". Nicht auf das blosse
    # Wort pruefen: „Mitgliedsvertrag (Rueckseite/Anlage)" steht voellig zu Recht
    # weiter im Brief — als Beschaffungsweg fuer die AGB.
    assert f"- {VERTRAG_TEXT}" not in n["text"]
    assert "- die AGB" in n["text"], "die AGB werden weiterhin angefordert"


def test_das_fehlen_verschwindet_nicht_es_wechselt_die_seite(klient, fall_id):
    """Das Dokument fehlt weiter — es ist nur nicht mehr die Verbraucherin,
    die es liefern kann. Ein Posten, der einfach verschwindet, würde den Fall
    vollständiger aussehen lassen, als er ist."""
    klient.post(f"/faelle/{fall_id}/nicht-vorhanden",
                json={"dokumenttyp": "vertrag", "aussage": AUSSAGE})
    assert "vertrag" not in _dokumenttypen(_seite(klient, fall_id, "verbraucher"))
    unternehmen = _seite(klient, fall_id, "unternehmen")
    assert "vertrag" in _dokumenttypen(unternehmen), \
        "der Vertrag ist ganz aus der Vollständigkeit gefallen"
    # und die Verbraucherseite gilt jetzt als abgearbeitet, soweit es ihn betrifft
    assert klient.get(f"/faelle/{fall_id}").json()["hero"]["vollstaendigkeit"][
        "vollstaendig_verbraucherseite"] is False, "die AGB fehlen weiterhin"


def test_die_feststellung_bewegt_kein_urteil(klient, fall_id):
    """Ob eine Erhöhung schon deshalb unwirksam ist, weil sie nie angekündigt
    wurde, ist eine offene juristische Frage (`24` §7 Frage 2 an Franz). Sie
    wird nicht per Code entschieden — hier wechselt nur der Adressat."""
    vorher = klient.get(f"/faelle/{fall_id}").json()["hero"]["einordnung"]["code"]
    antwort = klient.post(f"/faelle/{fall_id}/nicht-vorhanden",
                          json={"dokumenttyp": "vertrag", "aussage": AUSSAGE})
    assert antwort.json()["einordnung"].startswith("unklar")
    assert klient.get(f"/faelle/{fall_id}").json()["hero"]["einordnung"]["code"] == vorher


def test_ohne_aussage_wird_nichts_gespeichert(klient, fall_id):
    """Derselbe Grund, aus dem ein Override einen Grund braucht: ohne den Satz,
    auf den sie sich stützt, ist die Feststellung von einer Vermutung nicht zu
    unterscheiden."""
    antwort = klient.post(f"/faelle/{fall_id}/nicht-vorhanden",
                          json={"dokumenttyp": "vertrag"})
    assert antwort.status_code == 400
    assert "vertrag" in _dokumenttypen(_seite(klient, fall_id, "verbraucher"))


def test_was_in_der_akte_liegt_kann_nicht_nie_existiert_haben(klient, fall_id):
    """Das Erhöhungsschreiben liegt vor. Eine Feststellung dagegen wäre eine
    Aussage gegen die Akte und wird abgelehnt, nicht stillschweigend ignoriert."""
    antwort = klient.post(f"/faelle/{fall_id}/nicht-vorhanden",
                          json={"dokumenttyp": "erhoehungsschreiben", "aussage": AUSSAGE})
    assert antwort.status_code == 400


def test_die_feststellung_laesst_sich_zuruecknehmen(klient, fall_id):
    klient.post(f"/faelle/{fall_id}/nicht-vorhanden",
                json={"dokumenttyp": "vertrag", "aussage": AUSSAGE})
    antwort = klient.post(f"/faelle/{fall_id}/nicht-vorhanden",
                          json={"dokumenttyp": "vertrag", "zurueckziehen": True})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["nicht_vorhanden"] == []
    assert "vertrag" in _dokumenttypen(_seite(klient, fall_id, "verbraucher"))


def test_die_feststellung_ueberlebt_eine_nachreichung(klient, fall_id):
    """„Es gab nie einen Vertrag" wird nicht dadurch falsch, dass die AGB
    eintreffen. Sie lebt am Fall, nicht an der einzelnen Prüfung."""
    klient.post(f"/faelle/{fall_id}/nicht-vorhanden",
                json={"dokumenttyp": "vertrag", "aussage": AUSSAGE})
    antwort = klient.post(f"/faelle/{fall_id}/dokumente", json={"anhaenge": [
        {"dateiname": "agb_nachgereicht.md",
         "text": (NORDLICHT / "agb_nachgereicht.md").read_text(encoding="utf-8")},
    ]})
    assert antwort.status_code == 200, antwort.text
    assert "vertrag" not in _dokumenttypen(_seite(klient, fall_id, "verbraucher"))


def test_das_protokoll_haelt_fest_wer_das_festgestellt_hat_und_warum(klient, fall_id):
    """Die Feststellung nimmt der Verbraucherin eine Bitte ab und richtet sie
    an das Unternehmen — sie gehört in die Spur, mit dem O-Ton darin."""
    klient.post(f"/faelle/{fall_id}/nicht-vorhanden",
                json={"dokumenttyp": "vertrag", "aussage": AUSSAGE})
    protokoll = klient.get(f"/faelle/{fall_id}").json()["protokoll"]
    zeilen = [e for e in protokoll
              if e["aktion"]["code"] == "dokument_als_nicht_vorhanden_markiert"]
    assert len(zeilen) == 1
    eintrag = zeilen[0]
    assert eintrag["aktion"]["label"] and eintrag["schritt"]["code"] == "nachforderung"
    assert "Tablet" in eintrag["beschreibung"], "der O-Ton steht nicht in der Spur"


def test_die_absage_nennt_die_unterlage_beim_namen_nicht_beim_code(klient, fall_id):
    """R3 — der 400-Satz landet unverändert auf dem Schirm der Beraterin.

    Er sagte `agb` und `erhoehungsschreiben`, also den Enum-Code aus
    `vokabular.Dokumenttyp`, weil die Meldung `typ.value` interpolierte. Dieselbe
    Klasse Fehler wie V-23 (ein Enum rendert seinen rohen Code) und wie „(Gate 4)"
    im `beschaffungsweg`: richtig gebaut, nie angesehen. Der Wächter prüft die
    Meldung, nicht den Aufruf — der Aufruf war nie kaputt.
    """
    from fallpruefer.vokabular import Dokumenttyp, label

    antwort = klient.post(f"/faelle/{fall_id}/nicht-vorhanden",
                          json={"dokumenttyp": "erhoehungsschreiben", "aussage": AUSSAGE})
    assert antwort.status_code == 400
    satz = antwort.json()["detail"]
    assert label(Dokumenttyp.ERHOEHUNGSSCHREIBEN) in satz, satz
    codes = {d.value for d in Dokumenttyp} - {label(d) for d in Dokumenttyp}
    assert not [c for c in codes if c in satz], f"Code statt Anzeigename: {satz}"

    zurueck = klient.post(f"/faelle/{fall_id}/nicht-vorhanden",
                          json={"dokumenttyp": "kontoauszug", "zurueckziehen": True})
    assert zurueck.status_code == 400
    satz = zurueck.json()["detail"]
    assert label(Dokumenttyp.KONTOAUSZUG) in satz, satz
