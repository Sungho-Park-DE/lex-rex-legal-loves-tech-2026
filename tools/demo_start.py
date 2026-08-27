"""Demo-Start — ein Befehl statt der Checkliste aus `27` §3.

Warum das existiert: am 24. Aug hat zweimal ein **alter** uvicorn auf :8000
gedient — einmal sechs Stunden hinter dem letzten Motor-Commit — und beide
Male hat eine Live-Probe erst gegen den falschen Stand geprüft. Auf der Bühne
prüft niemand `ps -o lstart=` gegen `git log`. Dieses Skript tut, was die
Checkliste verlangt, in der Reihenfolge, in der sie es verlangt, und sagt am
Ende, wo die Fallakte liegt.

  1. alte Prozesse auf :8000 / :8080 beenden
  2. Backend auf HEAD starten, warten bis es antwortet
  3. Radar zurücksetzen und neu seeden (FitPoint 24 auf 2 — der „+1"-Beat)
  4. UI (`bun run dev`) starten, sofern `~/dev/llt26-ui` da ist
  5. einen frischen Fall aus `demo/faelle/<fall>/` anlegen — ohne die
     Nachreichungsdatei, die kommt in Schritt 5 der Vorführung
  6. URL, Nachreichungsdatei und die zwei Bühnenregeln drucken

Und der Modus, laut gesagt: `adapter/__init__.py` geht live, sobald
ANTHROPIC_API_KEY in der Shell steht, die uvicorn startet — auf der Bühne wäre
ein Cache-Miss dann ein Netzaufruf über das Veranstaltungs-WLAN, mit Sekunden
Verzögerung und womöglich anderen Werten als im Golden. `--modus cache`
(Voreinstellung) startet das Backend OHNE Schlüssel im Prozess: ein Miss ist
dann ein sichtbarer Fehler, kein stiller Aufruf; davor prüft der Trockenlauf
von tools/live_diff.py, dass jeder Cache-Eintrag der vier Demofälle da ist.
`--modus live` verlangt den Schlüssel und sagt, was das heißt.

Run:  .venv/bin/python tools/demo_start.py [--modus cache|live] [--fall seepark_seite_fehlt] [--ohne-ui]

Nur Vorbereitung: das Skript fasst weder Schema noch Cache noch Golden an.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
UI = Path.home() / "dev" / "llt26-ui"
BACKEND = "http://localhost:8000"
FRONTEND = "http://localhost:8080"
LOGS = WURZEL / "store" / "demo_logs"

# Die Datei, die in Schritt 5 nachgereicht wird — je Fall die Seite, die dem
# Fall fehlt. Sie darf NICHT mit angelegt werden, sonst gibt es keinen Flip.
NACHREICHUNG = {
    "seepark_seite_fehlt": "bedingungen_seite2_nachgereicht.md",
    "nordlicht_agb_fehlen": None,  # die AGB kommen aus dem Ticket-Verzeichnis nicht mit
}


def _pids_auf(port: int) -> list[int]:
    out = subprocess.run(["lsof", "-tnP", f"-iTCP:{port}", "-sTCP:LISTEN"],
                         capture_output=True, text=True).stdout.split()
    return [int(p) for p in out if p.isdigit()]


def _beenden(port: int, name: str) -> None:
    pids = _pids_auf(port)
    if not pids:
        print(f"  :{port} frei")
        return
    for pid in pids:
        start = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)],
                               capture_output=True, text=True).stdout.strip()
        print(f"  :{port} {name} PID {pid} (gestartet {start}) → beendet")
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGTERM)
    for _ in range(20):
        if not _pids_auf(port):
            return
        time.sleep(0.25)
    for pid in _pids_auf(port):
        os.kill(pid, signal.SIGKILL)


def _head() -> str:
    return subprocess.run(["git", "log", "-1", "--format=%h %ci %s"], cwd=WURZEL,
                          capture_output=True, text=True).stdout.strip()


def _warten(url: str, sekunden: int = 25) -> bool:
    for _ in range(sekunden * 4):
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.25)
    return False


def _naechste_id() -> str:
    """F-2026-01xx: die Serie der Live-Fälle, getrennt von den Fixtures (000x)
    und den Testfällen (9xxx)."""
    vorhanden = sorted((WURZEL / "cases").glob("F-2026-01*.json"))
    nummern = [int(p.stem.rsplit("-", 1)[1]) for p in vorhanden]
    return f"F-2026-{max(nummern, default=100) + 1:04d}"


def _fall_anlegen(fall: str) -> dict:
    verz = WURZEL / "demo" / "faelle" / fall
    ticket = json.loads((verz / "ticket.json").read_text(encoding="utf-8"))
    ausgeschlossen = NACHREICHUNG.get(fall)
    dateien = [n for n in ticket["anhaenge"] if n != ausgeschlossen]
    nutzlast = {
        "freitext": ticket["freitext"],
        "anhaenge": [{"dateiname": n, "text": (verz / n).read_text(encoding="utf-8")}
                     for n in dateien],
        "kanal": ticket.get("kanal", "vbs"),
        "ticket_nr": ticket.get("ticket_nr"),
        "thema": ticket.get("thema"),
        "anbieter": ticket.get("anbieter"),
        "branche": ticket.get("branche"),
        "eingegangen_am": ticket.get("eingegangen_am"),
        "identitaet": ticket.get("identitaet", {}),
        "case_id": _naechste_id(),
    }
    req = urllib.request.Request(f"{BACKEND}/faelle", data=json.dumps(nutzlast).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fall", default="seepark_seite_fehlt",
                    help="Verzeichnis unter demo/faelle/ (Standard: der Flip-Fall)")
    ap.add_argument("--modus", choices=("cache", "live"), default="cache",
                    help="cache: Backend ohne Schlüssel, Miss = Fehler (Voreinstellung) · "
                         "live: Schlüssel nötig, Miss = Netzaufruf")
    ap.add_argument("--ohne-ui", action="store_true", help="kein bun run dev")
    ap.add_argument("--ohne-fall", action="store_true", help="keinen neuen Fall anlegen")
    ap.add_argument("--nur-fall", action="store_true",
                    help="NUR einen weiteren Fall am laufenden Backend anlegen — nichts beenden, "
                         "nichts starten, Radar nicht anfassen (Regiebuch §8: drehkreuz neben "
                         "dem Seepark-Fall)")
    args = ap.parse_args()

    if args.nur_fall:
        if not (WURZEL / "demo" / "faelle" / args.fall / "ticket.json").exists():
            print(f"kein Fall demo/faelle/{args.fall}/ticket.json", file=sys.stderr)
            return 2
        try:
            antwort = _fall_anlegen(args.fall)
        except Exception as e:  # noqa: BLE001
            print(f"Backend auf {BACKEND} antwortet nicht ({e}) — erst demo_start.py ohne --nur-fall",
                  file=sys.stderr)
            return 1
        print(f"Fall angelegt: {antwort['case_id']} ({args.fall}) → {FRONTEND}/faelle/{antwort['case_id']}")
        return 0

    if not (WURZEL / "demo" / "faelle" / args.fall / "ticket.json").exists():
        print(f"kein Fall demo/faelle/{args.fall}/ticket.json", file=sys.stderr)
        return 2
    LOGS.mkdir(parents=True, exist_ok=True)

    print(f"HEAD  {_head()}")
    umgebung = dict(os.environ)
    if args.modus == "cache":
        for schluessel in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
            umgebung.pop(schluessel, None)
        print("Modus CACHE — kein Schlüssel im Backend-Prozess; ein Cache-Miss ist ein Fehler,"
              " kein Netzaufruf")
        vorab = subprocess.run([sys.executable, str(WURZEL / "tools" / "live_diff.py")],
                               cwd=WURZEL, capture_output=True, text=True)
        erste = (vorab.stdout.strip().splitlines() or ["(keine Ausgabe)"])[0]
        if vorab.returncode != 0:
            print("  Preflight FEHLGESCHLAGEN — ein Demofall hat keinen vollständigen Cache:",
                  file=sys.stderr)
            print((vorab.stderr or vorab.stdout).strip()[-600:], file=sys.stderr)
            return 1
        print(f"  Preflight: {erste}")
    else:
        # Die Entscheidung vom 24. Aug (Sungho): die Vorfuehrung laeuft nicht live.
        # Sie steht in config.json (llm.nur_cache) — eine Quelle, kein Schalter hier.
        sys.path.insert(0, str(WURZEL))
        from fallpruefer.konfig import konfig
        if konfig().llm.nur_cache:
            print("--modus live ist abgewaehlt: config.json llm.nur_cache = true (Entscheidung 24 Aug,"
                  " Register C3). Zum Umschalten die Konfiguration aendern, nicht dieses Skript.",
                  file=sys.stderr)
            return 2
        if not (umgebung.get("ANTHROPIC_API_KEY") or umgebung.get("ANTHROPIC_AUTH_TOKEN")):
            print("--modus live ohne ANTHROPIC_API_KEY — nichts gestartet", file=sys.stderr)
            return 2
        print("Modus LIVE — ein Cache-Miss geht ins Netz (≈ 8 s je Aufruf, ≈ 1 min je neuem Fall)")
    print("1 · alte Prozesse")
    _beenden(8000, "uvicorn")
    if not args.ohne_ui:
        _beenden(8080, "vite")

    print("2 · Backend")
    log = (LOGS / "uvicorn.log").open("w")
    subprocess.Popen([str(WURZEL / ".venv" / "bin" / "uvicorn"), "fallpruefer.api:app",
                      "--port", "8000"], cwd=WURZEL, stdout=log, stderr=subprocess.STDOUT,
                     start_new_session=True, env=umgebung)
    if not _warten(f"{BACKEND}/vokabular"):
        print(f"  Backend antwortet nicht — siehe {LOGS / 'uvicorn.log'}", file=sys.stderr)
        return 1
    print(f"  läuft auf {BACKEND}  (Log: {LOGS / 'uvicorn.log'})")

    print("3 · Radar")
    seed = subprocess.run([sys.executable, str(WURZEL / "tools" / "radar_seed.py"),
                           "--zuruecksetzen"], cwd=WURZEL, capture_output=True, text=True)
    for zeile in seed.stdout.strip().splitlines()[-2:]:
        print("  " + zeile)
    if seed.returncode != 0:
        print(seed.stderr, file=sys.stderr)
        return 1

    if not args.ohne_ui:
        print("4 · UI")
        if not UI.exists():
            print(f"  {UI} fehlt — Backend läuft, UI nicht gestartet")
        else:
            env = (UI / ".env.local")
            if not env.exists() or "VITE_API_BASE_URL" not in env.read_text(encoding="utf-8"):
                env.write_text(f"VITE_API_BASE_URL={BACKEND}\n", encoding="utf-8")
                print(f"  {env} geschrieben (sonst Fixture-Modus!)")
            uilog = (LOGS / "vite.log").open("w")
            subprocess.Popen(["bun", "run", "dev"], cwd=UI, stdout=uilog,
                             stderr=subprocess.STDOUT, start_new_session=True)
            if _warten(FRONTEND + "/", 30):
                print(f"  läuft auf {FRONTEND}  (Log: {LOGS / 'vite.log'})")
            else:
                print(f"  UI antwortet nicht — siehe {LOGS / 'vite.log'}", file=sys.stderr)

    if not args.ohne_fall:
        print("5 · frischer Fall")
        antwort = _fall_anlegen(args.fall)
        cid = antwort["case_id"]
        print(f"  {cid}  →  {antwort['einordnung']}")
        print()
        print(f"  {FRONTEND}/faelle/{cid}")
        nach = NACHREICHUNG.get(args.fall)
        if nach:
            desktop = Path.home() / "Desktop" / "AGB_Seite2_Seepark.md"
            quelle = desktop if desktop.exists() else WURZEL / "demo" / "faelle" / args.fall / nach
            print(f"  Nachreichung (Schritt 5): {quelle}")

    print()
    print('  Bühnenregeln: kein „Demo-Modus"-Badge im Browser · Gate 3 nie auf FitPoint 24'
          f' · Backend im Modus {args.modus.upper()}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
