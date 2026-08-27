"""Zählt die Anker je Demofall — in allen drei Einheiten, die auseinanderfallen.

Warum das existiert: am 26. Aug ist dieselbe Zahl **dreimal** korrigiert worden,
und jedes Mal war keine der beiden Angaben falsch — sie meinten Verschiedenes.

  1. „19 von 20"  zählte Prüfpunkt-Titel als Chips mit (kaputter DOM-Filter)
  2. „17 von 17"  war richtig, galt aber nur für **seepark** und wurde als
                  allgemeine Zahl gemeldet — drehkreuz trägt 20
  3. „18" vs „19" waren beide richtig, in verschiedenen **Einheiten**:
                  18 Fundstellen (keys) sind 19 Chiptexte (labels)

Die Lehre steht in `33` §2 und im `28_belege`-README: eine Zahl ohne ihren Fall
und ohne ihre Einheit ist keine Zahl. Dieses Skript gibt beides immer mit aus,
damit die nächste Messung nicht wieder daneben zählt.

Gezählt wird, was Schritt 4 aufgeklappt rendert: alle `anker[]` auf
Prüfpfad-Zeilen **ohne** `inaktiv_grund` (Stufen + Ableitungen).

  Instanzen   Chips auf dem Schirm, Dubletten mitgezählt
  Fundstellen verschiedene `key` — das, was die Normbasis kennt
  Chiptexte   verschiedene `label` — **das, was jemand auf der Bühne mitzählt**

Fundstellen und Chiptexte fallen auseinander, wenn eine Schemazeile den Namen
aus der Normbasis überschreibt (`normbasis.py:63`, `label = s.get("norm") or
e["norm"]`). Das ist gewollt — ein Prüfpunkt darf enger zitieren als die Norm
heißt —, aber derselbe Anker steht dann unter zwei Texten da.

Run:  .venv/bin/python tools/anker_zaehlen.py
      .venv/bin/python tools/anker_zaehlen.py demo/fixtures/drehkreuz_fallakte.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent


def anker_der_aktiven_zeilen(fallakte: dict) -> list[dict]:
    """Die Anker, die Schritt 4 aufgeklappt zeigt — inaktive Zeilen zählen nicht."""
    pfad = fallakte["pruefpfad"]
    zeilen: list[dict] = []
    for stufe in pfad.get("stufen", []):
        zeilen += stufe.get("pruefpunkte", [])
    zeilen += pfad.get("ableitungen", [])
    return [a for z in zeilen if not z.get("inaktiv_grund") for a in (z.get("anker") or [])]


def zaehlen(pfad: Path) -> dict:
    anker = anker_der_aktiven_zeilen(json.loads(pfad.read_text(encoding="utf-8")))
    keys = Counter(a["key"] for a in anker)
    texte: defaultdict[str, set[str]] = defaultdict(set)
    for a in anker:
        texte[a["key"]].add(a["label"])
    return {
        "fall": pfad.stem.replace("_fallakte", ""),
        "instanzen": len(anker),
        "fundstellen": len(keys),
        "chiptexte": len({a["label"] for a in anker}),
        "geprueft": sum(1 for a in anker if a.get("geprueft")),
        "mehrfach": {k: sorted(texte[k]) for k, n in keys.items() if n > 1},
    }


def main(argv: list[str]) -> int:
    dateien = [Path(p) for p in argv[1:]] or sorted((WURZEL / "demo" / "fixtures").glob("*_fallakte.json"))
    if not dateien:
        print("keine Fixturen gefunden", file=sys.stderr)
        return 1

    print(f"{'Fall':12} {'Instanzen':>9} {'Fundstellen':>12} {'Chiptexte':>10} {'geprueft':>9}")
    befunde = []
    for datei in dateien:
        z = zaehlen(datei)
        print(
            f"{z['fall']:12} {z['instanzen']:9} {z['fundstellen']:12} {z['chiptexte']:10} {z['geprueft']:9}"
        )
        for key, labels in z["mehrfach"].items():
            hinweis = f"  {z['fall']}: {key} mehrfach"
            if len(labels) > 1:
                hinweis += f" — und unter {len(labels)} verschiedenen Texten: {labels}"
                befunde.append(hinweis)
            else:
                hinweis += f" — derselbe Text {labels[0]!r}"
            print(hinweis)

    if befunde:
        print(
            "\nDeshalb ist 'verschiedene' ohne Einheit keine Zahl: oben unterscheiden sich\n"
            "Fundstellen und Chiptexte. Wer auf der Buehne mitzaehlt, zaehlt Chiptexte."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
