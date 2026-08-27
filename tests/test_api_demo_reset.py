"""„Demo beenden" — 33 §8 Nr. 8 als Knopf (Sungho, 27. Aug früh).

Der Store vergisst nicht: eine Probe, die Gate 3 fährt, hebt FitPoint 24 auf 3
und verbrennt den Radar-Beat. Der Knopf unter dem Radar sät neu aus und holt
die Schemadatei aus HEAD zurück. Zwei Dinge hält der Test fest: nach dem POST
steht FitPoint wieder bei 2 (die Prüfzahl aus 33 §8), und die Wiederherstellung
fasst genau eine Datei an — nachgewiesen in einem Wegwerf-Repo, nie im echten.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fallpruefer import demo_reset, store
from fallpruefer.api import app


@pytest.fixture(autouse=True)
def umgeleitet(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "pfad", lambda: tmp_path / "faelle.jsonl")


@pytest.fixture
def ohne_git(monkeypatch):
    # der Endpunkt-Test fasst die echte Arbeitskopie nicht an
    monkeypatch.setattr(demo_reset, "schema_wiederherstellen", lambda *a, **k: False)


def test_demo_beenden_setzt_fitpoint_auf_2_zurueck(ohne_git):
    klient = TestClient(app)
    demo_reset.radar_neu_saeen()
    # eine Probe hat Gate 3 gefahren: dritte FitPoint-Zeile im Store
    zeilen = [json.loads(z) for z in store.pfad().read_text(encoding="utf-8").splitlines() if z.strip()]
    dritte = dict(next(z for z in zeilen if z["anbieter"] == demo_reset.FITPOINT))
    dritte["fall_hash"] = store.fall_hash("PROBE-GATE3")
    with store.pfad().open("a", encoding="utf-8") as f:
        f.write(json.dumps(dritte, ensure_ascii=False) + "\n")
    assert sum(1 for s in store.lesen() if s["anbieter"] == demo_reset.FITPOINT) == 3

    antwort = klient.post("/demo/zuruecksetzen")
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert daten["fitpoint_24"] == 2, "33 §8: FitPoint 24 = 2, sonst ist der Beat verbraucht"
    assert daten["radar_zeilen"] == 9
    assert daten["schema_zurueckgesetzt"] is False
    assert "FitPoint 24 = 2" in daten["hinweis"]


def _git(wurzel: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false",
                    *args], cwd=wurzel, check=True, capture_output=True)


def test_schema_wiederherstellen_holt_genau_eine_datei_aus_head(tmp_path):
    wurzel = tmp_path / "repo"
    (wurzel / "schemas").mkdir(parents=True)
    datei = Path("schemas") / "preiserhoehung.json"
    (wurzel / datei).write_text('{"version": "0.7.0"}', encoding="utf-8")
    _git(wurzel, "init", "-q")
    _git(wurzel, "add", str(datei))
    _git(wurzel, "commit", "-q", "-m", "stand")

    assert demo_reset.schema_wiederherstellen(datei, wurzel) is False  # unverändert → nichts zu tun
    (wurzel / datei).write_text('{"version": "0.7.1"}', encoding="utf-8")  # der Bühnen-Edit
    fremd = wurzel / "notiz.md"
    fremd.write_text("fremde Arbeit, bleibt", encoding="utf-8")  # untracked, darf nicht verschwinden

    assert demo_reset.schema_wiederherstellen(datei, wurzel) is True
    assert (wurzel / datei).read_text(encoding="utf-8") == '{"version": "0.7.0"}'
    assert fremd.read_text(encoding="utf-8") == "fremde Arbeit, bleibt"
