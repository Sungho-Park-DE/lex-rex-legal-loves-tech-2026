"""Seed `store/faelle.jsonl` with synthetic background rows for the Radar.

Why this exists: the store is gitignored (it is written on the advisor's
machine, contract §0), so on a fresh checkout the Radar is empty and the
14 §7 beat — „+1, and the cluster crosses the threshold" — has nothing to
cross. These rows are the advisory's *past* cases, which in a real
installation would already be there.

They are not fabricated case files: a store record has no identities by
construction (contract §8), so a synthetic row is exactly as informative as a
real one and carries nothing that could belong to a person. Every row is
marked `fallgruppe_id: preiserhoehung` with a `fall_hash` derived from a
fiction id, so nothing here collides with a real case.

The seeding leaves FitPoint 24 one case below `k_min`. Confirming the demo
case at Gate 3 is what pushes it over, which is the point of the beat.

Run:  .venv/bin/python tools/radar_seed.py [--zuruecksetzen]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fallpruefer import abmahnungen, store  # noqa: E402
from fallpruefer.konfig import konfig  # noqa: E402
from fallpruefer.schema import schema_laden  # noqa: E402

# Anleitung §4/§7: Prüflogik versioniert. Die Hintergrundzeilen tragen die
# Fassung der Schemadatei, unter der sie „geprüft" wurden — zwei davon bewusst
# eine ältere, damit der Zähler „davon N mit älterer Fassung" auf dem Schirm
# je etwas zu zählen hat (ein Zustand, den keine Fixture zeigt, ist ungeprüft).
AELTERE_FASSUNG = "0.5.0"
AELTERE_ZEILEN = {2, 7}

# (anbieter, branche, einordnung, gerissene_stufe, NEIN-Prüfpunkte, Erhöhung €,
#  bereits gezahlte Monate, noch gebundene Monate)
#
# Die letzten beiden Zahlen tragen Franz' Anleitung §5: bereits **entstandener**
# und künftig **drohender** Schaden werden getrennt ausgewiesen, weil nur der
# zweite abwendbar ist. Sie stehen ausgeschrieben in der Tabelle und werden
# nicht aus dem Index gerechnet — eine erfundene Zahl wird nicht dadurch
# ehrlicher, dass eine Formel sie erzeugt.
#
# `None` bei den gebundenen Monaten heißt: keine Laufzeit erkennbar, §5 kappt
# hilfsweise auf 24 Monate. `0` heißt: die Bindung ist abgelaufen, der Vertrag
# läuft in der Verlängerung — § 309 Nr. 9 lit. b BGB, jederzeit mit höchstens
# einem Monat kündbar, also droht genau eine Periode. Eine Zeile ist bewusst
# **unbeziffert** (Betrag `None`) — §5 verlangt, dass solche Fälle als
# unbeziffert und nicht als null gelten, und ohne ein Beispiel im Bestand ist
# die Regel nie sichtbar. Dasselbe gilt für die Verlängerung: ein Zustand, der
# in keiner Fixture vorkommt, ist von der Anzeigeseite ungeprüft (27 §1).
HINTERGRUND = [
    ("fitpoint 24", "fitness", "wahrscheinlich unwirksam", "S3", ["P6", "P7", "P9"], 7.0, 9, 15),
    ("fitpoint 24", "fitness", "wahrscheinlich unwirksam", "S3", ["P6", "P9"], 6.0, 4, 20),
    ("nordlicht sportclub", "fitness", "wahrscheinlich unwirksam", "S3", ["P6", "P7"], 4.5, 6, 6),
    ("nordlicht sportclub", "fitness", "unklar – es fehlt: die AGB", None, [], None, 0, None),
    ("bodyline gyms", "fitness", "wahrscheinlich unwirksam", "S3", ["P7"], 5.0, 14, 0),
    ("bodyline gyms", "fitness", "wahrscheinlich unwirksam", "S2", ["P3"], 5.5, 2, 22),
    ("bodyline gyms", "fitness", "wahrscheinlich unwirksam", "S3", ["P6", "P7"], 4.5, 7, None),
    ("bodyline gyms", "fitness", "wirksam", None, [], 2.0, 3, 9),
    ("aktivpark fitness", "fitness", "wirksam", None, [], 1.5, 1, 11),
]


# Zwei Hintergrundfälle tragen eine Referat-Markierung: einer in einem Cluster
# über der Schwelle (Anbieter wird genannt), einer darunter (Anbieter bleibt
# weg). Das sind die beiden Zustände, die der Referat-Schirm kennt — und ein
# Feld, das in keiner Fixture je gefüllt war, hat den case_id/fall_hash-Bruch
# zwei Tage lang verdeckt (28 F7, 27 §1 Regel 3).
MARKIERT = {
    5: ["neuigkeitswert", "dauerbrenner"],        # bodyline gyms — Cluster sichtbar
    3: ["schadenshoehe"],              # nordlicht sportclub — unter k_min
}


def satz(i: int, anbieter, branche, einordnung, stufe, nein, betrag,
         monate_bereits=0, monate_gebunden=None) -> dict:
    if betrag is None:
        schaden = {"entstanden": None, "drohend": None, "basis": "unbeziffert"}
    else:
        if monate_gebunden is None:
            gebunden, basis = store.SCHADEN_FALLBACK_MONATE, "fallback_24"
        elif monate_gebunden == 0:
            gebunden, basis = store.VERLAENGERUNG_MONATE_NEU, "verlaengerung_monatlich"
        else:
            gebunden, basis = monate_gebunden, "laufzeit"
        schaden = {
            "entstanden": round(betrag * monate_bereits, 2),
            "drohend": round(betrag * gebunden, 2),
            "basis": basis,
        }
    return {
        "fall_hash": store.fall_hash(f"SEED-{i:03d}"),
        "zeit": f"2026-0{(i % 6) + 2}-1{i % 9}T10:0{i % 6}:00+02:00",
        "fallgruppe_id": "preiserhoehung",
        "stufe": "A",
        "anbieter": anbieter,
        "gegner": None,
        "branche": branche,
        "einordnung": einordnung,
        "gerissene_stufe": stufe,
        "pruefpunkte_nein": nein,
        "fehlte": [] if einordnung != "unklar – es fehlt: die AGB" else ["agb"],
        "rechtsbehelf": (
            "widerspruch_rueckforderung" if einordnung == "wahrscheinlich unwirksam"
            else "nachforderung" if einordnung.startswith("unklar")
            else "kuendigung_bei_wirksam"
        ),
        "betrag_erhoehung_gerundet": betrag,
        "schaden_entstanden": schaden["entstanden"],
        "schaden_drohend": schaden["drohend"],
        "schaden_basis": schaden["basis"],
        "referat_flag": MARKIERT.get(i, []),
        "kanal": "vbs" if i % 3 else "vor_ort",
        "schema_version": AELTERE_FASSUNG if i in AELTERE_ZEILEN
        else schema_laden("preiserhoehung").version,
        # Anleitung §7 — aus denselben NEIN-Punkten gerechnet wie im Motor
        "abgemahnt": [a.id for a in abmahnungen.treffer("preiserhoehung", nein)],
    }


def saeen(zuruecksetzen: bool = False) -> tuple[int, Path]:
    """Die Hintergrundzeilen schreiben; mit `zuruecksetzen` vorher den Store leeren.

    Als Funktion, nicht nur als Skript, weil der Knopf „Demo beenden" (POST
    /demo/zuruecksetzen) dasselbe im laufenden Motor tut — in-process, damit
    ein Test den Store umleiten kann statt den echten zu treffen.
    """
    pfad = store.pfad()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    if zuruecksetzen and pfad.exists():
        pfad.unlink()

    vorhanden = {s["fall_hash"] for s in store.lesen()}
    neu = [satz(i, *args) for i, args in enumerate(HINTERGRUND, start=1)]
    neu = [s for s in neu if s["fall_hash"] not in vorhanden]
    for s in neu:
        assert set(s) == set(store.FELDER), "Seed weicht von der Store-Feldliste ab"

    with pfad.open("a", encoding="utf-8") as f:
        for s in neu:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    return len(neu), pfad


def main() -> None:
    anzahl, pfad = saeen("--zuruecksetzen" in sys.argv)
    k = konfig().radar
    r = store.radar()
    print(f"{anzahl} Hintergrundsätze geschrieben → {pfad}")
    print(f"k_min = {k.k_min}; sichtbare Cluster: "
          f"{[(c['anbieter'], c['faelle']) for c in r['cluster']]}")
    print(f"unter der Schwelle zurückgehalten: {r['unter_schwelle_anbieter']} Anbieter")
    print("FitPoint 24 steht bewusst bei 2 — der bestätigte Demo-Fall ist die +1.")
    f_ = r["prueflogik_fassungen"]
    print(f"Prüflogik {f_['aktuell']}: {f_['zeilen_aktuell']} Zeilen aktuell, "
          f"{f_['zeilen_aelter']} mit älterer Fassung (älteste {f_['aelteste']})")
    print(f"Klauseltypen ausgewiesen: "
          f"{[(z['titel'], z['verbreitung'], z['betroffenheit']) for z in r['klauseltypen']]}"
          f" (+{r['unter_schwelle_klauseltypen']} zurückgehalten)")


if __name__ == "__main__":
    main()
