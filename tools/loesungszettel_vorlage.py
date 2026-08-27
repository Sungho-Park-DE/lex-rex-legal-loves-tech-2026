"""Generate the Lösungszettel form the law students fill in.

Why a form and not a parser. Franz' two delivered Lösungszettel are one and two
lines of free prose (`data/eingang/franz_runde2_faelle_1_2.pdf`): Fall 1 names
no Einordnung at all, Fall 2 states „Ergebnis unklar, da die AGB fehlen" with
verdict and completeness in one sentence. The task packet asked for four items
in prose and got prose. There is nothing there to parse — and three separate
problems make parsing the wrong goal anyway:

  * **His numbering does not resolve.** He renumbered to 0–16, and his own case
    solutions use the numbers inconsistently (Fall 1 „ehemals 9, jetzt 13" does
    not match his own titles; Fall 4's „Prüfpunkt 11" matches neither list).
    A form that prints our P-IDs with their titles removes the number from the
    exchange entirely.
  * **His verdict words mean something else.** His `wahrscheinlich_unwirksam`
    is defined as „the material does not carry the proof yet" — that is our
    `unklar – es fehlt …`. Ours means a rule actually broke. Translating word
    for word would promote unclear cases to hard verdicts and quietly corrupt
    the one metric built to catch that (`falsche sichere Antworten`).
  * **The runner compares sets, not single points.** „Kippt an Prüfpunkt X"
    cannot fill `gekippte_pruefpunkte`, which is compared by equality.

So the form asks for exactly what the golden file needs, in the vocabulary the
engine already speaks, and it is generated from `schemas/<fallgruppe>.json` so
it cannot drift from the Prüfschema it is about.

    .venv/bin/python tools/loesungszettel_vorlage.py                 # preiserhoehung
    .venv/bin/python tools/loesungszettel_vorlage.py --fallgruppe inkasso
    .venv/bin/python tools/loesungszettel_vorlage.py --faelle 3      # three blank case blocks

Output: `docs/loesungszettel_vorlage.md`. Send that; `tools/loesungszettel.py`
reads it back.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fallpruefer.konfig import WURZEL  # noqa: E402
from fallpruefer.schema import schema_laden  # noqa: E402
from fallpruefer.vokabular import Quelle, Rolle  # noqa: E402

ZIEL = WURZEL / "docs" / "loesungszettel_vorlage.md"

# The three binding verdict strings (14 §5). Printed verbatim so nobody has to
# remember them, with the distinction his vocabulary does not make spelled out.
EINORDNUNGEN = [
    ("wirksam", "Die Erhöhung hält der Prüfung stand."),
    ("wahrscheinlich unwirksam",
     "Ein tragender Prüfpunkt ist **gerissen** — der Mangel steht im vorliegenden Material."),
    ("unklar – es fehlt …",
     "Der Mangel liegt vielleicht vor, **das Material trägt den Nachweis noch nicht**, "
     "oder es braucht eine Bewertung durch die Beraterin."),
]

KOPF = """<!-- ERZEUGT von tools/loesungszettel_vorlage.py — nicht von Hand bearbeiten.
     Neu erzeugen nach jeder Änderung an schemas/{fallgruppe}.json. -->

# Lösungszettel — {name}

**Schema-Fassung {version} · Stand {stand} · Vorlage erzeugt am {heute}**

Hallo Franz,

das hier ersetzt die vier Fragen aus dem Aufgabenpaket. Es ist zum **Ankreuzen**
gedacht — nicht zum Ausformulieren. Der Grund ist praktisch: dein Zettel ist der
Maßstab, gegen den unser Programm getestet wird, und dafür muss er in genau den
Begriffen stehen, die das Programm kennt. Die Nummern aus deiner Liste brauchst
du hier **nicht mehr** — die Prüfpunkte stehen unten mit Titel da.

**Bitte pro Fall einen Block. Nichts weglassen: ein leeres Feld ist eine
Aussage („weiß ich noch nicht"), ein fehlendes Feld ist eine Lücke, die wir
nicht von einem Versehen unterscheiden können.**

Format: `[x]` zum Ankreuzen, Text hinter dem Doppelpunkt. Die Zeilen mit `<!--`
sind Kommentare für uns, die kannst du stehen lassen.

---
"""

HINWEIS_ZWEI_ZETTEL = """
## Wenn der Fall eine Nachreichung hat

Dann **zwei Blöcke** für denselben Fall: einen für den Stand bei Eingang
(`Stufe: initial`) und einen für den Stand danach (`Stufe: nachreichung`), mit
den nachgereichten Unterlagen in der Dateiliste. Genau dieser Wechsel ist der
interessante Teil — er zeigt, dass sich die Einordnung mit den Unterlagen
ändert und nicht mit unserer Laune.
"""


def _ankreuzliste(zeilen: list[str]) -> str:
    return "\n".join(f"- [ ] {z}" for z in zeilen)


def block(schema, nummer: int | None = None) -> str:
    titel = f"## Fall {nummer}" if nummer else "## Fall <Nr>"

    pruefbar = [p for p in schema.pruefpunkte if p.rolle in (Rolle.TRAGEND, Rolle.ERGAENZEND)]
    gates = [p for p in schema.pruefpunkte if p.rolle == Rolle.GATE]
    verbraucher = [d for d in schema.dokumenten_soll.dokumente if d.quelle == Quelle.VERBRAUCHER]
    unternehmen = [d for d in schema.dokumenten_soll.dokumente if d.quelle != Quelle.VERBRAUCHER]
    rechtsbehelfe = schema.rechtsbehelfe.liste

    einordnung = "\n".join(
        f"- [ ] **`{code}`**\n      <!-- {erklaerung} -->" for code, erklaerung in EINORDNUNGEN
    )
    pp = _ankreuzliste([f"**{p.id}** — {p.titel}" for p in pruefbar])
    gate_liste = _ankreuzliste([f"**{p.id}** — {p.titel}" for p in gates])
    verb = _ankreuzliste([f"`{d.dokumenttyp.value}` — {d.anzeigename}" for d in verbraucher])
    unt = "\n".join(
        f"- `{d.dokumenttyp.value}` — {d.anzeigename}" for d in unternehmen
    ) or "- (keine)"
    rb = _ankreuzliste([f"`{r.id}` — {r.titel}" for r in rechtsbehelfe]) or "- [ ] (noch keine hinterlegt)"

    return f"""{titel}

**Fall-Kennung:** `<kurzer_name_ohne_leerzeichen>`
**Stufe:** `initial`   <!-- oder `nachreichung`, siehe unten -->
<!-- Dateinamen, mit Komma getrennt. -->
**Unterlagen:**

### 1. Einordnung — genau eine

{einordnung}

**Wenn `unklar` — woran liegt es?** (auch beides möglich)

- [ ] Es fehlt eine **Unterlage** (siehe 3.)
- [ ] Es braucht eine **Bewertung durch die Beraterin**

**Bewertungsfrage:**   <!-- nur wenn oben angekreuzt -->

### 2. Welche Prüfpunkte sind NICHT erfüllt?

Bitte **alle** ankreuzen, die auf `nein` stehen — nicht nur den, an dem der Fall
kippt. Unser Programm vergleicht die vollständige Menge; ein Punkt, den wir
kreuzen und du nicht, ist genauso ein Befund wie umgekehrt.

{pp}

<!-- Einer von den oben angekreuzten. -->
**Kipp-Punkt:**
**Warum:**

<!-- Vorfragen. Die zählen bei uns nie zur Einordnung, sie schalten die Prüfung
     an oder ab. Nur ankreuzen, wenn sie NICHT erfüllt sind: -->
{gate_liste}

### 3. Welche Unterlagen fehlen?

Nur, was die **ratsuchende Person** noch beibringen müsste:

{verb}

<!-- Was das Unternehmen schuldet, tragen wir selbst ein — das steht immer offen
     und ist kein Befund über diesen Fall:
{unt}
-->

### 4. Welcher Rechtsbehelf passt?

{rb}

<!-- §§ und Aktenzeichen, mit Komma getrennt. -->
**Fundstellen:**

### 5. Anmerkung (frei)



---
"""


def bauen(fallgruppe_id: str, anzahl: int) -> str:
    # The real clock, deliberately not `zeit.heute()`. That one is pinned to
    # `demo_stichtag` (14 §5) because every date the *engine* shows has to be
    # reproducible — but this is a letter to a person, and dating it 27.08. in
    # August would just be wrong.
    from fallpruefer.zeit import datum_de, heute

    schema = schema_laden(fallgruppe_id)
    kopf = KOPF.format(
        fallgruppe=fallgruppe_id, name=schema.name, version=schema.version,
        stand=schema.stand, heute=datum_de(heute()),
    )
    bloecke = "\n".join(block(schema, i) for i in range(1, anzahl + 1))
    return kopf + "\n" + bloecke + HINWEIS_ZWEI_ZETTEL


def _kurz(p: Path) -> str:
    try:
        return str(p.relative_to(WURZEL))
    except ValueError:
        return str(p)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fallgruppe", default="preiserhoehung")
    p.add_argument("--faelle", type=int, default=1)
    p.add_argument("--ziel", type=Path, default=None)
    a = p.parse_args()

    text = bauen(a.fallgruppe, a.faelle)
    ziel = a.ziel or ZIEL
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(text, encoding="utf-8")
    print(f"{_kurz(ziel)} — {len(text.splitlines())} Zeilen, "
          f"{a.faelle} Fallblock(e), Schema {a.fallgruppe}")


if __name__ == "__main__":
    main()
