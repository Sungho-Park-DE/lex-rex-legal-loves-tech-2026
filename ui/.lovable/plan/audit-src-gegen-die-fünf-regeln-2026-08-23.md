# Audit `src/` gegen die fünf Regeln

Nur Befund, kein Code. Geprüft wurden alle App-Dateien unter `src/` (ohne `src/components/ui/*` — unveränderte shadcn-Primitives — und ohne `src/routeTree.gen.ts`).

## Regel 1 — kein deutsches Label/Verdict/Badge/Norm-Name im Frontend

Teilweise erfüllt: **kein** Verdict-Text, **kein** Badge-Text und **kein** Norm-Name (kein `§`, kein „BGB", kein „Abs.") ist im Frontend geschrieben — Einordnung, Badges und Anker kommen ausschließlich aus dem View-Model. Verletzt ist die Regel dagegen für **statische Struktur- und Bedienbeschriftungen**, die kein Feld im View-Model haben. Vollständige Liste:

- `src/components/fallakte/FallakteHeader.tsx:30-32` — „Fall / Ticket / eingegangen" als Fließtext-Gerüst um View-Model-Werte.
- `src/components/fallakte/FallakteHeader.tsx:40` — Navigationslabel „Referat".
- `src/components/fallakte/FallakteHeader.tsx:43` — Aktionslabel „Fallgruppe bestätigen".
- `src/components/fallakte/FallakteHeader.tsx:58-59` — „Zuordnungsvorschläge" plus Statuswort „bestätigt / nicht bestätigt".
- `src/components/fallakte/HeroCard.tsx:14` — Leerzustand „Nichts offen."
- `src/components/fallakte/HeroCard.tsx:24` — Feldbeschriftung „Weg:".
- `src/components/fallakte/HeroCard.tsx:46` — Abschnittstitel „Einordnung".
- `src/components/fallakte/HeroCard.tsx:56` — erläuternder Text „ohne Nachforderung:".
- `src/components/fallakte/HeroCard.tsx:70` — Abschnittstitel „Vollständigkeit".
- `src/components/fallakte/HeroCard.tsx:72-73` — Listentitel „Verbraucherseite" / „Unternehmensseite".
- `src/components/fallakte/HeroCard.tsx:75-76` — Satz „Verbraucherseite vollständig / unvollständig" wird im Frontend gebildet.
- `src/components/fallakte/HeroCard.tsx:84` — Abschnittstitel „Prüfumfang".
- `src/components/fallakte/OffenePunkte.tsx:8,10,24` — Paneltitel „Offene Punkte", Leerzustand, Beschriftung „Feld:".
- `src/components/fallakte/LaeufeTimeline.tsx:9,11` — Paneltitel „Verlauf der Einordnung", Leerzustand „Noch kein Prüflauf."
- `src/components/fallakte/LaeufeTimeline.tsx:32-33` — „gerissen bei", „aktueller Lauf".
- `src/components/fallakte/NachforderungenPanel.tsx:20,23,28,44` — Paneltitel, „Nachforderung erzeugen", Leerzustand, „als eingegangen markieren".
- `src/components/fallakte/Pruefpfad.tsx:44` — Beschriftung „Wertungsfrage:".
- `src/components/fallakte/Pruefpfad.tsx:50` — Beschriftung „Fehlt:".
- `src/components/fallakte/Pruefpfad.tsx:60` — Satzgerüst „Override auf … durch …".
- `src/components/fallakte/Pruefpfad.tsx:97,103,120,134` — „Prüfpfad", „gerissen bei", „Prüfpunkte", „Ableitungen".
- `src/components/fallakte/LeitfadenPanel.tsx:10,12,16,20` — „Gesprächsleitfaden", „offen", „Keine Fragen hinterlegt.", „Fragen anzeigen".
- `src/components/fallakte/LeitfadenPanel.tsx:35` — „füllt:".
- `src/components/fallakte/MusterbriefPreview.tsx:19,30,78,84,102` — „Musterbrief", „Rechtsbehelf", „Vorlagenquelle", „Platzhalter", „Rechtsbehelf übernehmen".
- `src/components/fallakte/MusterbriefPreview.tsx:46,49` — „(Hauptvorschlag)", „juristisch geprüft" (aus booleschen Flags im Frontend verbalisiert).
- `src/components/fallakte/ReferatPanel.tsx:16,19,39` — „Referat-Markierung", „Markierung aufheben / Für Referat markieren", „Status: markiert / nicht markiert".
- `src/components/fallakte/AbschlussPanel.tsx:16,19,24-25,42` — „Abschluss", „geschlossen / Fall abschließen", „Basis-Export erzeugt / nicht erzeugt", „Fall geschlossen / offen", „Keine Wiedervorlage."
- `src/components/fallakte/ProtokollPanel.tsx:9,11,15` — „Protokoll", „Keine Einträge.", „Einträge anzeigen".
- `src/components/fallakte/DokumentViewer.tsx:21` — Fehlertext „Zitat auf dieser Seite nicht gefunden — der Text weicht vom Zitat ab."
- `src/components/fallakte/DokumentViewer.tsx:66` — „Typ bestätigt / Typ nicht bestätigt" aus einem Boolean gebildet.
- `src/components/fallakte/DokumentViewer.tsx:73,75` — „Seite".
- `src/components/fallakte/AnkerPopover.tsx:19,34` — „Stand", „Quelle öffnen".
- `src/components/fallakte/ZitatLink.tsx:18` — Zitat-Abkürzung „S.".
- `src/components/fallakte/Fusszeile.tsx:13-15` — „Schema-Version", „Stand", „Stichtag", „Normbasis", „Betriebskosten"; auch die Währungsformatierung passiert im Frontend.
- `src/components/referat/RadarView.tsx:14-15` — „Fälle", „Median", „Markierungen".
- `src/components/referat/RadarView.tsx:46` — „Nicht erfüllte Prüfpunkte:".
- `src/components/referat/RadarView.tsx:70,72-74` — „Muster-Radar", „Stand/Fälle/Schwellen/Beschwerden/Beratungen/mindestens … Fälle je Anbieter".
- `src/components/referat/RadarView.tsx:95,97-98` — „Sonstiges" und der Schwellensatz.
- `src/components/referat/RadarView.tsx:103,105` — „Markierte Fälle", „Kein Fall für das Referat markiert."
- `src/routes/faelle.$id.tsx:24-26` — deutsche Titel-/Description-Strings (`head`).
- `src/routes/faelle.$id.tsx:60,68` — „Fall … wird geladen …", „… konnte nicht geladen werden."
- `src/routes/referat.tsx:9-11,32,36` — deutsche Head-Strings, Lade- und Fehlertext.
- `src/routes/index.tsx:9-11` — deutsche Head-Strings.
- `src/routes/__root.tsx:83-87` — deutsche Head-Strings.
- `src/routes/__root.tsx:129,130,137,144,148` — „VZ-I Fall-Prüfer", „Hauptnavigation", „Fallakte", „Referat", „Demo-Modus (Fixtures)".
- `src/lib/api.ts:12,59,68` — „Laden fehlgeschlagen", „Demo-Modus: nicht gespeichert", „Aktion fehlgeschlagen".

Einordnung dieser Gruppe: keiner dieser Strings ist ein Verdict, Badge oder Norm-Name; sie sind Panel-Titel, Buttons, Leer-/Ladezustände und Head-Metadaten. Wenn Regel 1 wörtlich gelten soll, müsste das View-Model (bzw. `GET /vokabular`) auch diese Beschriftungen liefern.

## Regel 2 — Farbe nur aus geliefertem `tone`

Verletzt an vier Stellen; sonst erfüllt (alle Ampel-Farben laufen über `src/lib/tone.ts` und ein geliefertes `tone`).

- `src/components/fallakte/DokumentViewer.tsx:20` — „Zitat nicht gefunden"-Hinweis wählt selbst `tone-gelb`, obwohl kein `tone` geliefert wird.
- `src/components/fallakte/DokumentViewer.tsx:30` — die `<mark>`-Hervorhebung setzt selbst `tone-gelb-bg` und `ring-tone-gelb/40`.
- `src/routes/faelle.$id.tsx:67` — Fehlermeldung nutzt selbstgewähltes `text-tone-rot`.
- `src/routes/referat.tsx:35` — Fehlermeldung nutzt selbstgewähltes `text-tone-rot`.

Grenzfall (bewusst so gebaut, keine Ampelfarbe): `src/components/referat/RadarView.tsx:29` verwendet neutrales `bg-muted-foreground/40`, weil das Radar-Payload kein `tone` liefert.

## Regel 3 — keine Konfidenz, Prozentzahl, Score, Sternebewertung

**Nicht verletzt.** Nirgends in `src/` wird eine Konfidenz, Wahrscheinlichkeit, Punktzahl oder Sternebewertung gerendert. Die einzigen `%`-Werte sind CSS-Breiten der Radar-Balken (`RadarView.tsx:23,30`) und stehen nicht als Text auf dem Bildschirm.

## Regel 4 — kein Fetch im Route-`loader` oder in `createServerFn`

**Nicht verletzt.** Es gibt kein `createServerFn` und keinen `loader` in `src/`. Beide Screens laden im Component über `useQuery` (`src/routes/faelle.$id.tsx:43`, `src/routes/referat.tsx:27`). Das einzige Route-Lifecycle-Hook ist `src/routes/index.tsx:5` — ein reiner Redirect ohne Datenzugriff.

## Regel 5 — kein List-Key, der sich wiederholen kann

Drei Verletzungen:

- `src/components/fallakte/AnkerPopover.tsx:11` — `key={a.key}` ist eine Norm-ID; in den Fixtures kommt `bgb_308_5` mehrfach vor, ein Prüfpunkt kann dieselbe Norm doppelt (z. B. mit unterschiedlichem Stand) tragen.
- `src/components/fallakte/NachforderungenPanel.tsx:39` — `key={d.code}` ist ein Vokabular-Code, der in `dokumente` mehrfach angefordert werden kann.
- `src/components/referat/RadarView.tsx:90` — `key={c.anbieter}` ist nicht eindeutig, weil Cluster je Anbieter **und** Fallgruppe gebildet werden, ein Anbieter also mehrere Cluster haben kann.

Alle anderen Keys sind unbedenklich: echte IDs (`run_id`, `nachforderung.id`, `dok_id`, `rechtsbehelf_id`, `kriterium.id`, `case_id`, `pruefpunkt_id` — Stufen und Ableitungen sind getrennte Listen) oder index-basierte Keys bei Listen ohne stabile ID (`OffenePunkte.tsx:14`, `ProtokollPanel.tsx:19`, `AbschlussPanel.tsx:35`, `HeroCard.tsx:18,61`, `ZitatLink.tsx:30`, `LeitfadenPanel.tsx:24`, `FallakteHeader.tsx:63`).

## Vorgeschlagene Korrekturen (falls gewünscht, separat zu beauftragen)

1. Regel 5 (klein, risikolos): die drei Keys auf index-basierte bzw. kombinierte Keys umstellen.
2. Regel 2 (klein): die vier selbstgewählten Ampelfarben auf neutrale Tokens (`border-border`, `text-muted-foreground`, `bg-accent`) umstellen, bis das Backend dafür einen `tone` liefert.
3. Regel 1 (groß, Backend-abhängig): entscheiden, ob Panel-Titel, Buttons, Leer-/Ladezustände und Head-Texte künftig aus `GET /vokabular` kommen sollen; erst danach im Frontend umstellen.
