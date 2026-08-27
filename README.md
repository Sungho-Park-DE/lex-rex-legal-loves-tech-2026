# Fall-Prüfer — LLT26, Challenge VZ-I

**Ein Werkzeug für die Beratung der Verbraucherzentrale Bayern: es prüft einen eingereichten
Fall gegen ein hinterlegtes Prüfschema und legt Einordnung *und* passendes Musterschreiben
zusammen vor — mit jedem Satz zurückverfolgbar auf ein Zitat aus den Unterlagen.**

Legal Loves Tech 2026, München · Track Verbraucherrecht (VZ Bayern) · Pitch 27. August 2026.
Team: Sungho Park (Entwicklung), Paulina & Franz (Jura).

---

## Was das Programm tut

Ein Berater bekommt einen Fall — Vertrag, AGB, Erhöhungsschreiben, oft unvollständig. Heute liest er
das von Hand, gleicht es gegen sein Wissen ab und formuliert einen Brief. Das dauert, und das Ergebnis
hängt davon ab, wer gerade Dienst hat.

Der Fall-Prüfer nimmt dieselben Unterlagen und liefert drei Dinge:

| | |
|---|---|
| **Eine Einordnung** | genau in der Sprache der Ausschreibung: „wirksam" · „wahrscheinlich unwirksam" · „unklar — es fehlt …" |
| **Ein Musterschreiben** | **in jedem Zweig**, auch bei „wirksam" (dann die Sonderkündigung). Verdikt ohne Brief hilft niemandem |
| **Die Begründung** | welcher Prüfpunkt gerissen ist, mit dem wörtlichen Zitat aus dem Dokument und der Norm dazu |

Ist etwas unklar, sagt das Programm **welches Dokument fehlt** und erzeugt die Nachforderung.
Wird es nachgereicht, läuft die Prüfung erneut — und die alte Prüfung bleibt daneben stehen, damit
nachvollziehbar ist, was die neue Unterlage verändert hat.

## Wie es aufgebaut ist — und warum so

**Die Entscheidung fällt kein Sprachmodell.** Das ist die Architektur, nicht eine Vorsichtsmaßnahme.

```
Unterlagen ──▶  L0: Pseudonymisierung   (Namen verlassen den Rechner nie)
                     │
                     ▼
                L1: Adapter  ─── nur drei Aufgaben ───────────────────┐
                     │           Dokumenttyp erkennen · Felder aus    │  jede Ausgabe
                     │           dem Text ziehen · Fallgruppe         │  läuft durch
                     │           vorschlagen                          │  einen Validator
                     ▼                                               ─┘
                L2: Regelwerk  ── deterministisch, dreiwertig ──▶  JA / NEIN / FEHLT / WERTUNG
                     │                                               (aus einer JSON-Regeldatei)
                     ▼
                Einordnung · Frist · Rechtsbehelf · Brief   ← alles Code, kein Modell
```

Was das Modell **nie** tut: die Einordnung fällen, die Frist rechnen, den Rechtsbehelf wählen, den
Brief schreiben, eine Norm zitieren. Es liest Dokumente und schlägt Feldwerte vor; alles danach ist
gewöhnlicher, testbarer Code. Deshalb ist das Ergebnis reproduzierbar, und deshalb kann ein Jurist es
prüfen, ohne ein Sprachmodell prüfen zu müssen.

**Das Prüfschema ist eine Datei, kein Code.** `schemas/preiserhoehung.json` enthält den Prüfbaum,
19 Prüfpunkte, das Unterlagen-Soll und die Rechtsbehelfe. Eine Juristin kann eine Regel ändern —
und das Programm rechnet den Fall neu, während es läuft (`POST /faelle/{id}/neu-pruefen`). Ein
kaputter Zwischenstand nimmt nichts vom Netz: die letzte gültige Fassung bedient weiter.

**Vier Gates.** An vier Stellen entscheidet ein Mensch, nicht das Programm: Nachforderung ·
Fallgruppe bestätigen · Prüfergebnis übersteuern (mit Begründung) · Rechtsbehelf wählen. Jede
Entscheidung landet im Ereignisprotokoll des Falls. Das ist die Spur, auf der die RDG-Argumentation
steht — das Werkzeug berät nicht, es bereitet vor.

## Stand — ehrlich

Was hier läuft, ist der Prüfkern, nicht das fertige Produkt.

**Läuft und ist getestet:** 447 Tests grün (gemessen 26.08., dreimal hintereinander). Fünf Demofälle laufen Ende-zu-Ende durch alle Zweige,
inklusive Nachreichung, mit von Hand hergeleiteten Soll-Ergebnissen. Alle 17 API-Endpunkte, das
Regelwerk, die Briefe, das Radar.

**Ausdrücklich ungeprüft, und im Programm auch so beschriftet:**

- **33 von 34 Fundstellen tragen `geprueft: false`.** Wir haben die Gesetzestexte von
  gesetze-im-internet.de geholt, aber kein Jurist hat sie gegen den Fall abgenommen. **Eine
  Ausnahme seit dem 26.08.:** LG Bamberg 13 O 730/22 steht auf `geprueft: true`, weil Paulina das
  Urteil im Original gelesen hat — mit Namen und Datum in der Datei. Ein Test lässt keine zweite
  Bestätigung still nachrücken: `geprueft: true` ohne `geprueft_von` und `geprueft_am` fällt durch,
  und die Menge der bestätigten Anker ist festgeschrieben.
- **Alle Musterschreiben sind unsere eigenen** (`quelle: eigen`) und tragen auf dem Bildschirm den
  Vermerk „nicht juristisch geprüft". Die Musterbrief-Sammlung der VZ enthält für eine
  Preiserhöhung im gewöhnlichen Dauerschuldverhältnis kein Schreiben — deshalb bleibt dieser
  Vermerk stehen. Das ist der Vertrauensrahmen, wie er gedacht ist.
- **Die Demofälle sind Fiktion**, von uns und von Franz geschrieben. Keine echten Beratungsakten.
- Zweite Fallgruppe (Inkasso): Unterlagen-Soll und 14 Prüfpunkte liegen vor, 13 davon mit
  Regel; die Fallgruppe ist Stufe B und steht nicht auf der Demolinie.

Der Datenkontrakt — Schemadatei, Regelgrammatik, Fallobjekt, Prüfergebnis, Golden-Tests — steht in
[`analysis/15_data_contract.md`](analysis/15_data_contract.md). Dieses Repository ist der Einreichungsstand
vom 27. August 2026 (Team **Lex Rex**); die internen Arbeitsdokumente sind nicht enthalten.

## Loslegen

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python -m pytest tests/ -q                        # 452 passed, 2 skipped (Stand 27.08.)
.venv/bin/uvicorn fallpruefer.api:app --reload --port 8000  # API auf :8000
```

Ohne `ANTHROPIC_API_KEY` läuft alles aus dem mitgelieferten Cache — vollständig offline, ohne
stille Fehler. Der Schlüssel schaltet nur die Dokumentenerkennung live.

```bash
.venv/bin/python tools/radar_seed.py --zuruecksetzen && .venv/bin/python tools/radar_seed.py
```

Einmal pro Rechner vor der Demo: `store/` ist gitignored, sonst ist das Radar leer.

## Oberfläche (`ui/`)

React/Vite (TanStack Start); spricht ausschließlich mit dem lokalen Backend.

```bash
cd ui && bun install
echo 'VITE_API_BASE_URL=http://localhost:8000' > .env.local
bun run dev            # http://localhost:8080
```

`/neu` legt einen der vorbereiteten Fälle an und führt zur Fallakte, `/referat` ist der Muster-Radar.
Alles zusammen startet `.venv/bin/python tools/demo_start.py --ohne-fall` (Backend im Cache-Modus,
Radar-Saat, UI).

## Wo was liegt

| Ordner | Inhalt |
|---|---|
| `fallpruefer/` | Das Programm. `regeln`/`evaluator` = Regelwerk · `l0` = Pseudonymisierung · `adapter/` = die einzige Stelle mit einem Sprachmodell · `pipeline` = Gates und Nachreichung · `api` = FastAPI |
| `schemas/` | Die Prüfschemata als Daten. `preiserhoehung.json` ist das laufende |
| `normbasis/` | Gesetzestexte und Rechtsprechung, aus denen zitiert wird — alle `geprueft: false` |
| `templates/` | Musterschreiben und Nachforderungen, mit Platzhaltern |
| `demo/faelle/` | Die fiktiven Fälle · `tests/golden/` die von Hand hergeleiteten Soll-Ergebnisse |
| `analysis/15_data_contract.md` | Der Datenkontrakt — die einzige Arbeitsdatei in diesem Stand |
| `cache/llm/` | Die vorbereiteten Modellantworten zu den Demofällen (pseudonymisiert) — deshalb läuft alles ohne Schlüssel |
| `pitch/diagramm/` | Die zwei Beamer-Folien (Und-Baum, Vorfragen) als Design-Artboards |
| `ui/` | Die Oberfläche (React/Vite): Fallakte, Muster-Radar, Bühnenauftakt `/neu` |

`cases/` und `store/` sind gitignored: ein Fallobjekt enthält die Pseudonym-Zuordnung, und die
verlässt diesen Rechner nicht.
