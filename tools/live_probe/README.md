# Live-Probe — die 12 Schritte aus `27` §3 als Skript

Fixture-Modus kann POSTs nicht prüfen (jeder Schreibzugriff wird zu einem Toast). Deshalb
waren Gate 1·2·4 und Abschluss zwei Tage lang 404, während 343 Tests grün waren (`28` F1).
Das hier ist der Test für genau diese Klasse: einmal durch alle Gates, mit Netzlog.

```bash
cd tools/live_probe && bun install && bunx playwright install chromium   # einmalig
cd ~/dev/llt26 && .venv/bin/python tools/demo_start.py                    # Backend HEAD + UI + frischer Fall → druckt F-2026-01xx
cd tools/live_probe && node probe.mjs F-2026-01xx shots                   # Exit 0 = bestanden
cd ~/dev/llt26 && .venv/bin/python tools/radar_seed.py --zuruecksetzen    # Gate 3 hat den Store berührt
```

Bestanden heißt: **alle POSTs 2xx, `/aktionen/` kommt nie vor**, Statuszeile am Ende `wirksam`,
Abschluss „Fall geschlossen". Screenshots je Schritt liegen in `shots/`.

Zwei Fallen, die je zweimal Zeit gekostet haben: ein **alter uvicorn** ohne `--reload` (deshalb
`demo_start.py`, das ihn beendet und HEAD startet) und **mehrdeutige Selektoren** — die
Schrittleiste wird über `nav[aria-label="Schritte"]` angesprochen, Panelknöpfe über
`button:has-text(…)`. Ein Selektorfehler ist kein UI-Defekt. Protokoll-Prüfungen laufen über
`GET /faelle/{id}` (`protokoll[].aktion.code`), nicht über den Bildschirmtext — dort stehen Labels.

## Die Messskripte daneben

`probe.mjs` prüft, ob der **Weg** durchläuft (Gates, POSTs, Konsolenfehler). Die drei hier
prüfen, was auf dem **Schirm** steht. Sie liegen im Repo, weil `pitch/diagramm/README.md`
für Belege festhält: gemessen wird headless, nie an einem skalierten Bild, und wer die Fläche
ändert, misst **wieder**. Ein Beleg, dessen Erzeugung nur in einem Sitzungs-Scratchpad liegt,
ist am 5. Oktober nicht reproduzierbar.

Alle brauchen Backend + UI (`tools/demo_start.py`) und einen **frischen** Fall — gegen einen
Fall, der schon durch `probe.mjs` gelaufen ist, fehlen die Gate-Knöpfe.

| Skript | Aufruf | Sagt |
|---|---|---|
| `messen.mjs` | `node messen.mjs F-2026-01xx [1440\|1920]` | Je Schritt: Breite der Dokumentspalte, Seitenhöhe, **Überlauf-Elemente**, waagerechter Scroll, **kleinste tatsächlich gerenderte Schriftgröße**. Die Zahlen hinter llt26-ui `7cceb0e` (Spalte 36 % → 2 % ab Schritt 4) und `2533dd8` (11 px → 14 px) |
| `b3test.mjs` | `node b3test.mjs F-2026-01xx` | Der **Jurist-Edit als A/B**: Stufen von Hand zuklappen, `frist_min_tage` 30 → 90 und Fassung 0.7.0 → 0.7.1 schreiben, „Prüfschema neu einlesen" drücken, Stufenzustände davor/danach drucken. Die Zahlen hinter llt26-ui `d9d0130` (Stufe 4 `zu` → `AUF`) |
| `belege.mjs` | `node belege.mjs F-2026-01xx` | Schreibt die drei `k60a_*`-Aufnahmen direkt nach `analysis/28_belege/`, 1440×900, bricht ab, wenn das „Demo-Modus"-Badge sichtbar ist. Druckt je Chip, ob der Rahmen `border-dashed` trägt |

⚠️ `b3test.mjs` **verändert das Schema während des Laufs** und schreibt es in `finally` aus
`/tmp/preiserhoehung_b3_backup.json` zurück. Danach trotzdem `git diff -- schemas/` prüfen, und
nicht parallel zu einem Golden-Lauf oder einer anderen Sitzung starten.

### ⚠️ Die Falle: zwei Aufnahmen, ein Bild

In den Zwischenstufen derselben Messung vom 26. Aug waren
`shots/chip_gegengelesen.png` und `shots/chip_ungeprueft.png` **byteidentisch**
(md5 `a51c5131…`), ebenso `13_abschluss_geschlossen.png` und `14_protokoll.png`
(`aaaf330b…`). Gefunden von llt26-ac beim Nachhashen, nicht beim Ansehen.

Das erste Paar ist das ernste: **die zwei Aufnahmen, die den Unterschied zeigen
sollten, waren dasselbe Bild.** Wer daraus einen Schluss zieht, zieht ihn aus
einer Aufnahme zweimal. Der Lauf endet dabei mit Exit 0, die Dateien liegen da,
nur der Inhalt gehört zum falschen Zustand — ein `screenshot`, dessen
Voraussetzung (Popover offen, Seite navigiert) noch nicht eingetreten ist,
fotografiert einfach, was noch auf dem Schirm stand.

`belege.mjs` wehrt sich seit `36ff7ed` mit zwei Nägeln dagegen, und beide sind
nachgemessen:

1. **Warten auf den Satz, nicht auf die Sekunde.** Vor jeder Popover-Aufnahme
   wartet es auf `[data-radix-popper-content-wrapper]:has-text("…")` mit dem
   Satz, der darin stehen *muss* („Fundstelle gegengelesen" bzw.
   „Fundstelle ungeprüft"). Steht er nicht da, bricht es ab, statt die vorherige
   Ansicht zu fotografieren.
2. **Hashvergleich am Ende.** Zwei gleiche Hashes unter den geschriebenen
   Dateien sind Exit 1 mit Namen beider Dateien. Gegenprobe auf dem bekannten
   Paar: der Vergleich meldet dort „würde abbrechen", auf den drei `k60a_*`
   „in Ordnung".

Ein fester `waitForTimeout` vor einem Beleg-`screenshot` ist damit hier ein
Fehler, kein Stil.

`anker.mjs`, `anker2.mjs`, `anker3.mjs` und `weg.mjs` sind Zwischenstufen aus der Messung vom
26. Aug (Chiptext zählen, Popover öffnen, „Weg:"-Zeile nachzählen); sie sind mit `d1ccfff`
mitgegangen. Was von ihnen bleibenswert war, steht in `messen.mjs` und `belege.mjs` —
wer aufräumt, kann die vier löschen.

`zaehl.mjs` ist die **Gegenprobe am DOM** zu `tools/anker_zaehlen.py`: das Python-Skript
zählt die Anker im Fixture, `zaehl.mjs` im laufenden Schirm, und beide müssen dieselbe
Zahl liefern. Auseinanderlaufen ist ein Befund, kein Rauschen — so ist am 26. Aug
aufgefallen, dass eine gemeldete Chipzahl vier Prüfpunkt-Titel mitzählte.
