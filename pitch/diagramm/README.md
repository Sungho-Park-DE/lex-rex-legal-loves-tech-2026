# Pitch-Diagramme — die juristische Prüfstruktur als Bild

Zwei Beamer-Folien (1920×1080) für den 27. Aug, gebaut aus **der Analyse von Franz und
Paulina**, nicht aus unserer Programmstruktur. Kein Prüfpunkt-Code, keine P-IDs, keine
Anzeigevokabeln — nur Paragrafen und die Ordnung zwischen ihnen.

| Datei | Folie | Aussage |
|---|---|---|
| `Main.dc.html` | **Jeder Ast muss halten** | Und-Baum: fünf Äste (Anwendungsbereich · Einbeziehung · Inhaltskontrolle · Ausübung · Rechtsfolge), drei ✕ gleichzeitig. „Kein Entscheidungsbaum: es wird kein Pfad gewählt, sondern jeder Ast geprüft." |
| `Bedingt.dc.html` | **Drei Vorfragen entscheiden, was geprüft wird** | § 310 III → anderes Regime · „überhaupt erklärt?" → § 812, der ganze Baum entfällt · § 307 III → nur der Ursprungspreis. Grau = niemand hat es geprüft, und der Baum sagt warum |
| `Schema.dc.html` · `Massstaebe.dc.html` | Backup, Seite 2 | ausführliches Prüfungsschema und die Maßstäbe, die wir selbst setzen mussten — für Rückfragen, nicht für die Bühne |
| `BildA/B/C.dc.html` | Skizzen, Seite 3 | frühe Entwürfe (Kaskade · Sieb · Rangfolge); `BildD/E` sind die Vorstufen der beiden Folien und stehen **nicht** mehr auf dem Canvas |

## Die Bilder, die am 27. an die Wand gehen

`export/` — aus dem Canvas exportiert (26. Aug), **1920×1080, native Beamer-Auflösung**, nachgemessen:

| Datei | Folie | Reihenfolge |
|---|---|---|
| `export/01_jeder_ast_muss_halten.png` | Und-Baum | zuerst — die Struktur |
| `export/02_drei_vorfragen.png` | bedingter Baum | danach — was von ihr wegfällt und warum |

Die Nummerierung folgt der Anordnung auf dem Canvas (`canvas.json`, Seite „Fürs Pitch": Main links,
Bedingt rechts). **Diese PNGs sind das Vorführmaterial** — nicht die `.dc.html`, nicht der Canvas.

⚠️ **1:1 einsetzen, nicht hochskalieren.** Bei einer 1920×1080-Folie sitzt jedes Pixel auf seinem
Pixel; wird das Bild vergrößert, werden die dünnen Rahmen (3–4 px) weich, und genau die tragen die
Aussage. Wird eine größere Fassung gebraucht (4K-Schirm, Druck, PDF-Handout), **nicht in
PowerPoint/Keynote ziehen**, sondern @2x aus der Canvas-Toolbar neu exportieren.

Nach jeder Änderung an einer `.dc.html`: neu seeden, publizieren, **neu exportieren** — sonst zeigt
`export/` einen Stand, den es nicht mehr gibt.

## Neu erzeugen

`pruefbaum-pitch.html` ist erzeugt und **gitignoriert** (2,2 MB). Nach jeder Änderung an einer
`.dc.html` oder an `canvas.json`:

```
node "<design-skill>/seed-canvas.mjs" --template "<design-skill>/payload.template.html" \
  --out pruefbaum-pitch.html --title "Prüfbaum fürs Pitch" \
  --artboard Main.dc.html --artboard Bedingt.dc.html --artboard Schema.dc.html \
  --artboard Massstaebe.dc.html --artboard BildA.dc.html --artboard BildB.dc.html \
  --artboard BildC.dc.html --canvas canvas.json
```

Publiziert unter <https://claude.ai/code/artifact/fe99b0b3-8898-4506-a953-26d0f6bfb579>
(gleiche URL bei jedem Republish). Export als PNG/PDF über die Toolbar des Canvas.

## Wie geprüft wurde, dass nichts überläuft

Nicht am Screenshot, sondern gemessen: headless Chromium rendert die Artboards, ein Skript
zieht die bbox jedes `<text>`, jedes Rahmens und jeder Linie und prüft vier Dinge — Text über
seinem Rahmen, Text von einer fremden Form überdeckt, Rahmen gegen Rahmen, Text über die
Schrägen einer Raute hinaus. Der erste Durchlauf fand elf Befunde (u. a. drei um 10 px
überlappende Paragrafen-Chips, ein ✕ genau auf „§ 305b", das rote § 812-Feld 310 px im
Inhaltskontroll-Panel). Wer die Folien ändert, misst **wieder** — ein skaliertes Bild zu
beschreiben ist keine Messung.
