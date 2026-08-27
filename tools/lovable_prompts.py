"""`docs/lovable_prompt.md` -> einzelne Textdateien zum Einfügen in Lovable.

Warum das ein Werkzeug ist und keine Handarbeit: Lovable nimmt einen Prompt pro
Eingabe, das Pack ist aber eine Datei. Wer die Prompts einmal von Hand
herauskopiert, hat ab der nächsten Korrektur zwei Fassungen — und die
Abweichung fällt nicht auf, weil beide für sich stimmig aussehen. Genau diese
Klasse Fehler hat das Pack schon zweimal getroffen (C2, und das Gerüst am
23. Aug). Ab jetzt ist das Kopieren ein Befehl.

    .venv/bin/python tools/lovable_prompts.py            # -> ~/Downloads/llt26_lovable_prompts/
    .venv/bin/python tools/lovable_prompts.py --ziel DIR

Erzeugt wird pro Prompt-Zeile der §4-Tabelle eine Datei plus die
Knowledge-Datei aus §1. Die laufende Nummer folgt der Reihenfolge der Tabelle,
nicht der Prompt-Nummer — P11 ist der Polierdurchgang und steht deshalb
zuletzt, obwohl P12 bis P15 eine höhere Nummer tragen.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
PACK = WURZEL / "docs" / "lovable_prompt.md"
STANDARDZIEL = Path.home() / "Downloads" / "llt26_lovable_prompts"

# Der Guardrail-Satz aus §4, der an jeden Build-Prompt gehängt wird. Er steht
# dort als Anweisung an uns; hier wird er tatsächlich angehängt, damit er in
# der Zwischenablage landet und nicht bloß im Dokument.
GUARDRAIL = ("Only change what this prompt names. All labels come from the view model — "
             "do not add strings, do not invent codes.")


def knowledge(text: str) -> str:
    """§1 — der Block zwischen den ersten ``` nach der Überschrift."""
    m = re.search(r"## 1\. Project Knowledge.*?\n```\n(.*?)\n```", text, re.S)
    if not m:
        sys.exit("§1 (Project Knowledge) nicht gefunden — hat sich die Überschrift geändert?")
    return m.group(1).strip() + "\n"


def prompts(text: str) -> list[tuple[str, str, str]]:
    """Die Zeilen der §4-Tabelle als (nummer, modus, prompt)."""
    aus: list[tuple[str, str, str]] = []
    for zeile in text.splitlines():
        m = re.match(r"^\|\s*([PK]\d+)\s*\|\s*(Plan|Build)\s*\|\s*(.*?)\s*\|$", zeile)
        if m:
            nummer, modus, prompt = m.groups()
            # Die Prompts stehen in Anführungszeichen, wenn sie wörtlich sind.
            prompt = prompt.strip().strip("„").strip('"').strip()
            aus.append((nummer, modus, prompt))
    if not aus:
        sys.exit("keine Prompt-Zeilen in §4 gefunden — hat sich das Tabellenformat geändert?")
    return aus


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ziel", type=Path, default=STANDARDZIEL)
    args = p.parse_args()

    text = PACK.read_text(encoding="utf-8")
    args.ziel.mkdir(parents=True, exist_ok=True)

    # Alte Dateien weg, sonst überlebt ein umbenannter Prompt als Leiche und
    # jemand fügt ihn ein.
    alt = sorted(args.ziel.glob("*.txt"))
    for datei in alt:
        datei.unlink()

    kn = args.ziel.parent / "lovable_knowledge.txt"
    kn.write_text(knowledge(text), encoding="utf-8")
    print(f"{kn}  ({len(knowledge(text))} Zeichen — Lovable-Grenze: 10 000)")

    for i, (nummer, modus, prompt) in enumerate(prompts(text), start=1):
        inhalt = prompt if modus == "Plan" else f"{prompt}\n\n{GUARDRAIL}\n"
        ziel = args.ziel / f"{i:02d}_{nummer}_{modus.lower()}.txt"
        ziel.write_text(inhalt if inhalt.endswith("\n") else inhalt + "\n", encoding="utf-8")
        print(f"  {ziel.name:<22} {len(inhalt):>5} Zeichen")

    print(f"\n{len(prompts(text))} Prompts nach {args.ziel}")
    print("Reihenfolge = Reihenfolge der Tabelle: P11 (Politur) steht zuletzt.")


if __name__ == "__main__":
    main()
