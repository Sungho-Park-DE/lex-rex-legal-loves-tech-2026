# Lovable prompt pack — Fall-Prüfer UI

Session working doc (EN), 22 Aug 2026. Paste-ready. Operationalises `analysis/17_lovable_ui_setup.md`
against the view model that now actually exists (`fallpruefer/viewmodel.py`), so nothing here is
speculative: every field name below is emitted by `GET /faelle/{id}` and is present in the fixture.

Where this file and `17` disagree, **this file wins** — it was written after the model existed.
One deliberate difference: `17` §2 describes one two-pane split for the whole screen; the layout
below puts the Einordnung hero + Prüfpfad **full width on top** and the ABBYY-Vantage-style
document/fields split **below** it (§3). Everything else in `17` still holds — settings checklist
(§1), no Supabase, private repo, Plan vs Build modes.

---

## 0. Before the first prompt

1. ~~**Connect GitHub first.**~~ ✅ **erledigt 23 Aug.** Lovable legt den Namen selbst fest, nicht
   wir: das Repo heißt **`Sungho-Park-DE/heartfelt-connect`** (privat, `main`). Auf GitHub NICHT
   umbenennen, solange Lovable die Verbindung hält — der Name ist kosmetisch, die Verbindung nicht.
   Lokal geklont als `~/dev/llt26-ui`, damit der Pfad sagt, worum es geht:

   ```bash
   git clone git@github.com:Sungho-Park-DE/heartfelt-connect.git ~/dev/llt26-ui
   ```
2. ~~Copy the fixtures into the new repo~~ ✅ **erledigt, Commit `02916bb` im UI-Repo.** Alle drei
   liegen unter `public/fixtures/` — die beiden Fallakten und `radar.json`. Sie sind **erzeugt, nicht
   von Hand geschrieben**; nach jeder Änderung an Demodokumenten, Soll-Feldliste oder Schema drüben
   neu erzeugen und hier neu ablegen:

   ```bash
   # im llt26-Repo
   .venv/bin/python tools/demo_fixture.py            # beide Fallakten
   .venv/bin/python -c "import json,sys;sys.path.insert(0,'.');from fallpruefer.store import radar;print(json.dumps(radar(),ensure_ascii=False,indent=2))" > ~/dev/llt26-ui/public/fixtures/radar.json
   ```

   ⚠️ **Gegenprobe fürs Radar:** „fitpoint 24" darf in `cluster` **nicht** vorkommen — der Anbieter
   steht mit zwei Fällen absichtlich einen unter `k_min: 3`, und genau das macht den bestätigten
   Demofall zur „+1". Wer die Ablage neu seedet und dabei Gate 3 auslöst, schiebt ihn darüber und
   der Beat ist still tot. Reparatur: `tools/radar_seed.py --zuruecksetzen && tools/radar_seed.py`.

   <details><summary>Die ursprünglichen Schritte, für den Fall eines Neuaufsetzens</summary>

   ```bash
   git clone git@github.com:Sungho-Park-DE/heartfelt-connect.git ~/dev/llt26-ui
   mkdir -p ~/dev/llt26-ui/public/fixtures/faelle
   cp ~/dev/llt26/demo/fixtures/drehkreuz_fallakte.json \
      ~/dev/llt26-ui/public/fixtures/faelle/F-2026-0001.json
   cp ~/dev/llt26/demo/fixtures/seepark_fallakte.json \
      ~/dev/llt26-ui/public/fixtures/faelle/F-2026-0002.json
   # vokabular.json: start the backend once and save GET /vokabular, or leave it out —
   # the Fallakte fixture already carries every label it needs inline.
   cp ~/dev/llt26/docs/lovable_prompt.md ~/dev/llt26-ui/AGENTS.md   # optional, see §1
   git -C ~/dev/llt26-ui add -A && git -C ~/dev/llt26-ui commit -m "fixtures" && git -C ~/dev/llt26-ui push
   ```

   </details>
3. Paste §1 into Project settings → **Knowledge** (limit 10,000 chars; it is injected into every
   prompt).
4. Do **not** connect Supabase / Lovable Cloud / Auth / Stripe. The backend is local FastAPI and
   no data leaves the machine.

---

## 1. Project Knowledge — paste verbatim

```
# Fall-Prüfer UI — Project Knowledge (v17, 2026-08-26; view model `ansicht_version` 1.14; Gerüst: TanStack Start)

## What this is
Advisor-facing frontend for an internal case-preparation tool at Verbraucherzentrale Bayern
(hackathon prototype). It is ONLY a view layer over a local FastAPI backend. All legal logic,
verdicts, deadlines, letters and labels are computed by the backend and arrive in one view-model
JSON. The UI never decides anything and never computes anything.

## Hard rules — never violate
1. No Supabase, no Lovable Cloud, no auth, no database, no edge functions, no third-party APIs.
   Data comes from (a) `GET ${VITE_API_BASE_URL}/faelle/{id}` and `GET /vokabular`, or (b) when
   `VITE_API_BASE_URL` is unset: `public/fixtures/faelle/{id}.json` — identical shape. Three
   fixtures exist: F-2026-0001 (complete case), F-2026-0002 (arrives incomplete, then flips)
   and F-2026-0003 (still open — Gate 1 asked, nothing came back). Build against the first,
   verify against the other two. `src/lib/api.ts` is the ONLY module that reads
   either source; switching between them is one environment variable, nothing else.
1a. **All data fetching happens in the browser.** This scaffold is TanStack Start and therefore
   has a server side (`src/start.ts`, `src/server.ts`, SSR). Do not use it for our data: no
   route `loader`, no `createServerFn`, no server-side fetch of the view model, no API route
   that proxies the backend. Read the case inside the component (TanStack Query, `useQuery`)
   and let the route render an empty shell on the server. Two reasons, and the first one is
   not a preference: the backend runs on the advisor's own machine and holds the map from
   pseudonym tokens back to real names — a server render that fetches it would put case data
   into a second process that has no business seeing it. And `localhost:8000` does not exist
   from the point of view of any deployed server, so an SSR fetch works locally and breaks
   everywhere else, which is the worst kind of breakage to discover on stage.
2. Never hardcode a German label, verdict text, badge text, Prüfpunkt name or Norm name. Every
   enum arrives as `{code, label, tone}`. Render `label`. Colour by `tone`
   (gruen | gelb | rot | grau). Key logic on `code`. Never map a code to a string in the UI, never
   invent a code, never translate one.
3. The three verdicts are printed exactly as delivered in `hero.einordnung.label`:
   „wirksam" / „wahrscheinlich unwirksam" / „unklar – es fehlt: …". Never rephrase, shorten,
   capitalise differently or translate them.
4. Never show a confidence percentage, probability, score or star rating. Trust is shown only
   through the badge chips the backend delivers.
5. Never use the words "IDP", "AI-powered", "Confidence", "Score" or any marketing phrasing in
   the interface.
6. Exactly two routes: `/faelle/$id` (Fallakte) and `/referat` (Muster-Radar). No dashboard, no
   inbox, no queue, no case list, no login, no landing page, no settings page, no onboarding.
   The scaffold ships `src/routes/index.tsx` as a starter landing page: replace its content with
   a redirect to `/faelle/F-2026-0001`. Do not delete the file and do not build a page there —
   „no landing page" means nobody ever sees one, not that the route file must vanish.
7. The UI never mutates the view model on its own. The only actions are Fallgruppe bestätigen,
   Prüfpunkt überschreiben, Nachforderung erzeugen/markieren, Rechtsbehelf wählen,
   Referat-Markierung, Abschluss — each POSTs to the backend; in fixture mode they are no-ops
   with a toast „Demo-Modus: nicht gespeichert".
8. Do not add features, screens, fields, icons or sample texts that were not asked for. If
   something is unclear, ask in Plan mode instead of inventing.
9. Never build a document queue or inbox, a throughput/duration/waiting-time chart, a per-case
   timer, or a node-graph editor for the rules — not even as a small extra, not even if the
   layout looks like it has room. The first three would make the tool look as if it measures
   advisors, which it must never do; the fourth is a different product.

## Look & feel
It must look like an ordinary German Verwaltungs-/Fachanwendung that advisors already know —
deliberately NOT innovative-looking. shadcn/ui defaults, neutral civic palette, one sans-serif
family, 16 px base size, generous whitespace. No gradients, no hero images, no marketing copy,
no glassmorphism, no decorative animation. The only permitted animation is the Radar „+1" tick.

One 3-state traffic light, used identically on every surface:
  gruen = wirksam / erfüllt   ·   gelb = unklar / Bewertung nötig / Angabe fehlt
  rot   = wahrscheinlich unwirksam / nicht erfüllt   ·   grau = neutral / nicht anwendbar
The colour always comes from the delivered `tone` — never chosen by the component. Colour is
never the only carrier: every state also shows its `label` in words.

Badges are small neutral chips: short icon + `label`. Hovering shows the full label.
Every disclosure control (anything that opens or collapses) uses ONE grammar: a button-like
trigger with a rotating ChevronDown. Never the browser's native `<details>` marker, never a
bare text line that toggles — if it opens, it must look pressable, and nothing that is not
pressable may look like a button. German UI
copy in Sie-Form, sober tone. Code, identifiers and comments in English. JSON keys stay German
exactly as delivered — never camelCase them.

Accessibility: semantic landmarks, visible focus rings, contrast ≥ 4.5:1, everything keyboard
reachable, designed for 1280 px, degrades sensibly on a phone.

## Code conventions
React + TypeScript + Vite + Tailwind + shadcn/ui, and the router this scaffold already has:
**`@tanstack/react-router` with file-based routes**, not react-router-dom (it is not installed —
do not add it). Routes are files under `src/routes/`: `faelle.$id.tsx` and `referat.tsx`, both
under the existing `__root.tsx`. Extend the route tree that is there; do not create a second
one and do not touch `routeTree.gen.ts`, it is generated. TanStack Query is already wired into
the router context — use it, and no other state library. Types in `src/types/viewmodel.ts` mirror the fixture JSON 1:1 with the
German keys unchanged. One small component per panel — FallakteHeader, HeroCard, OffenePunkte,
Pruefpfad, DokumentViewer, FelderPanel, MusterbriefPreview, ReferatPanel, AbschlussPanel,
Fusszeile, RadarView — each receiving its slice of the view model as props. When asked to change
one panel, change only that panel; never refactor or restyle the others.
```

---

## 2. The data — read this before prompting

One case = one JSON object. **Two fixtures, and you need both** — building against only the
first produces a UI that silently cannot render two of the required beats:

| Fixture | Case | What only this one shows |
|---|---|---|
| `F-2026-0001.json` | fitness-studio price increase, everything present | the happy path: „wahrscheinlich unwirksam", one run, no Nachforderung |
| `F-2026-0002.json` | the same schema, but the AGB arrives **incomplete** | **the flip** — `laeufe[]` with two entries („unklar – es fehlt …" → **`wirksam`**), a Gate-1 entry in `nachforderungen[]`, the green verdict and the Kündigung letter |
| `F-2026-0003.json` | the ticket arrives with ONLY the Erhöhungsschreiben; Gate 1 has asked, nothing has come back | **the open case** — the only fixture with a yellow hero, consumer-side `vollstaendigkeit.verbraucher` items (each with `fehlzustand`), an OPEN `nachforderungen[]` entry whose action buttons have something real to do, and the only place the „Existiert nicht" action (P16d) renders at all — the other two have no open consumer-side item to attach it to |

Build every panel against F-2026-0001, then check it against F-2026-0002 **and F-2026-0003** before calling it done.
A panel that renders one and breaks on the other is not finished. Field reference:

```
FallakteAnsicht      ansicht_version · case_id · kopf · hero · offene_punkte · pruefpfad ·
                     musterbrief? · nachforderungen[] · laeufe[] · leitfaden ·
                     referat · abschluss · dokumente[] · protokoll[] · fusszeile
Vokabel              {code, label, tone}                      tone ∈ gruen|gelb|rot|grau
Zitat                {dok_id, seite, zitat, feld_id?}         the click-to-highlight unit

kopf                 case_id · ticket_nr? · thema? · kanal:Vokabel · anbieter? · gegner? ·
                     eingegangen_am? · status:Vokabel · fallgruppe:Vokabel · stufe:Vokabel ·
                     fallgruppe_bestaetigt:bool · fallgruppe_vorschlag_fehlt:bool ·
                     fallgruppe_vorschlaege[] · fallgruppe_beleg?:Zitat ·
                     schema_stopp_text? · hinweis?
                     (1.14) `fallgruppe_beleg` ist das **verifizierte** Zitat aus
                     dem Erhoehungsschreiben, das die bestaetigte Fallgruppe
                     traegt — es steht erst NACH Gate 2 da. Die Zitate in
                     `fallgruppe_vorschlaege[]` stammen dagegen aus dem Freitext:
                     der Vorschlag entsteht, bevor ein Dokument gelesen ist.
                     Beide anzeigen, den Beleg unter dem Vorschlag. Ist er
                     `null`, faellt die Zeile weg — nichts ersatzweise zeigen.
hero                 einordnung{code,label,label_basis,tone} · vollstaendigkeit · plain[] ·
                     pruefumfang[{pruefpunkt_id,titel,zustand,text}]
vollstaendigkeit     verbraucher[] · unternehmen[] · vollstaendig_verbraucherseite:bool
  posten             was · grund · quelle:Vokabel · dokumenttyp?:Vokabel · feld_id? ·
                     felder[] · pruefpunkt_id? · beschaffungsweg? · fehlzustand?:Vokabel ·
                     aussage?
                     `fehlzustand` ist eine ANDERE Achse als `quelle`: quelle sagt, bei wem
                     etwas fehlt, fehlzustand sagt warum. `existiert_nicht` („nach Angabe
                     nicht vorhanden") trägt `aussage` — den O-Ton der Verbraucherin, als
                     Zitat zu zeigen, nie zu einer Kategorie eingedampft.
  Fachpruefung       wer · am · beleg · umfang · vorbehalt?
                     Wer diese Bewertung fachlich bestätigt hat. Leer bei allem, was
                     niemand bestätigt hat — heute 6 von 18 (Stand 24 Aug spät; die Fusszeile zählt selbst, diese Zahl hier ist nur Orientierung). **`vorbehalt` ist der Punkt:**
                     zu P10 wurde die Regel bestätigt UND gesagt, dass die pauschale Zahl,
                     die wir implementiert haben, so gar nicht existiert. Wer nur `wer`
                     rendert, lässt die Bestätigung die Umsetzung mitdecken.
offene_punkte[]      art:Vokabel · text · pruefpunkt_id? · pruefpunkt_titel? ·
                     quelle?:Vokabel · feld_id? · feld_label?
                     (1.13) `pruefpunkt_id` und `feld_id` sind **Schluessel, keine
                     Anzeige** — sie dienen dem Sprung in die Detailzeile. Auf dem
                     Schirm steht `pruefpunkt_titel` bzw. `feld_label`. Fehlt der
                     Titel, steht **nichts** da: die rohe ID ist hier kein Rueckfall,
                     sonst kommt sie zurueck (sie stand bis 26. Aug als „P8d" neben
                     der Frage der Beraterin).
pruefpfad            wurzel:Vokabel · gerissene_stufe? · gerissene_stufe_titel? · stufen[] · ableitungen[TraceEintrag] ·
                     baum?:BaumKnoten · legende[Vokabel]
  BaumKnoten         knoten_id · art:Vokabel (wurzel|stufe|pruefpunkt) · titel · op?:Vokabel ·
                     zustand:Vokabel · rolle?:Vokabel · gerissen:bool · marker?:Vokabel ·
                     inaktiv_durch? · anzahl_pruefpunkte · norm_kurz? · kurzwort? ·
                     kurzwort_quelle? · kinder[BaumKnoten]
                     (1.11) `gerissene_stufe` ist die **Kennung** (S2) und bleibt es — die Regeln
                     und die Goldens lesen sie. Angezeigt wird **`gerissene_stufe_titel`**
                     (Stufe 2 — Einbeziehung), im Panelkopf und in der Lauf-Zeile. Die UI
                     uebersetzt S2 nie selbst; faellt der Titel aus, steht die Kennung da.
                     (1.10, K58) Das Diagramm zeigt **Normen statt Titel**: `norm_kurz` ist die
                     Fundstelle in Kurzform („§ 307 I 2", „§ 309 Nr. 13 b"), `kurzwort` die
                     amtliche Überschrift der Norm — wörtlich, nur hinten gekürzt; wo zwei
                     Punkte dieselbe Überschrift trügen, steht das unterscheidende Wort in
                     Klammern („Inhaltskontrolle (Transparenz)"). `kurzwort_quelle` ist
                     „amtlich" oder „titel". Nichts davon selbst formulieren oder kürzen.
                     (1.8, R7) Derselbe Prüfpfad als Baum — dieselben Zustände wie die Liste,
                     KEINE zweite Bewertung. `op` trägt das Label („alle müssen halten"),
                     `marker` das Wort „gerissen", `inaktiv_durch` den **Titel** des Punktes,
                     dessen Nichterfüllung diesen Knoten gegenstandslos gemacht hat. Blätter und
                     Reihenfolge sind identisch mit `stufen[].pruefpunkte[]` — nie selbst sortieren.
  legende[]          (1.9) Die Zeichen, die im Baum vorkommen **und** einen Erklärungssatz haben,
                     als fertige Vokabeln mit `detail`: „tragend" (steht im Baum bewusst NICHT
                     als Abzeichen, K55), „ergänzend", „Vorfrage", „alle müssen halten",
                     „gerissen", „Bewertung nötig", „nicht anwendbar". In gelieferter Reihenfolge
                     rendern, Satz verbatim, nie einen eigenen dazuschreiben.
  stufen[]           stufe_id · titel · zustand:Vokabel · pruefpunkte[TraceEintrag]
  TraceEintrag       pruefpunkt_id · titel · proposition · zustand:Vokabel · rolle:Vokabel ·
                     … · geprueft_von[Fachpruefung]
                     typ?:Vokabel · herkunft:Vokabel · badge?:Vokabel · grund ·
                     zitate[Zitat] · anker[] · verwendet[] · fehlt[str] · owner?:Vokabel ·
                     wertungsfrage? · llm_befund:bool · frist? · betrag? · override? ·
                     inaktiv_grund? · hinweis_abmahnung? · normrang?:Vokabel
  AbmahnungHinweis   badge:Vokabel · text · geprueft:bool · quelle_url?
                     (1.7, Franz' Anleitung §7) Nur gesetzt, wenn der Punkt NEIN steht UND
                     derselbe Klauseltyp schon Gegenstand einer Abmahnung/Klage einer
                     Verbraucherzentrale war. `badge` ist der Chip („bereits abgemahnt",
                     gelb, mit `detail` für das Popover), `text` der ganze Satz — Verwender
                     des Vorverfahrens, Gericht, Az., Maßnahme, Datum, Träger, Prüfstand.
                     Er endet mit „· ungeprüft", solange `geprueft:false`; das UI kürzt
                     ihn nicht und schreibt keinen eigenen. Sagt nichts über DIESEN
                     Anbieter — nur, dass die Klausel bekannt ist.
                     `normrang` (1.7, Anleitung §2): Chip „wertungsfrei" (grau, `detail` für
                     das Popover) an Punkten, deren Anker in § 309 / § 308 BGB liegt. Die
                     Zeilen einer Stufe kommen bereits in Rangfolge (NEIN zuerst: 309 > 308 >
                     307 > sonst, tragend vor ergänzend) — **nicht umsortieren**.
  anker[]            key · label · ebene:Vokabel · status?:Vokabel · geprueft:bool ·
                     pruefstand:Vokabel · aufgeloest:bool · kernaussage? · text? ·
                     url? · stand?
                     (1.15) `pruefstand` ist `geprueft` als Wort: „Fundstelle
                     gegengelesen" (grün) bzw. „Fundstelle ungeprüft" (grau), mit
                     `detail` für das Popover. Der Chip zeigt **dieses** Label —
                     das UI schreibt kein eigenes „ungeprüft" mehr.
  verwendet[]        feld_label? · feld_id · wert_anzeige · herkunft:Vokabel · badge:Vokabel ·
                     verifiziert?:bool · zitat?:Zitat · annahme_anzeige?
  frist / betrag     {name, wert, stand?, annahmen[]}
musterbrief          rechtsbehelf_id · titel · text (plain text, render in <pre>/monospace-ish
                     block, preserve line breaks) · status:Vokabel · template_id · variante? ·
                     quelle:Vokabel · quelle_url? · empfaenger:Vokabel · platzhalter{} ·
                     geprueft:bool · vorschlaege[{rechtsbehelf_id,titel,hauptvorschlag,geprueft}]
nachforderungen[]    id · kanal:Vokabel · dokumente[Vokabel] · text · status:Vokabel · zeit?
                     Gate 1. `text` is what the advisor copies; the tool never sends anything, so
                     `status` is a statement the advisor makes, not something the program observed.
laeufe[]             run_id · trigger:Vokabel · zeit?
                     ⚠️ seit 1.5 ist `trigger` eine Vokabel — `trigger.label` rendern
                     ⚠️ seit 1.6 kann jede Vokabel `detail: string|null` tragen (Rolle, Typ) — als `title`-Tooltip auf dem Chip zeigen, nie selbst formulieren
                     („Ersteingang", „nach Nachreichung", …), nie mehr den rohen Code. · einordnung · einordnung_tone · gerissene_stufe? · gerissene_stufe_titel? ·
                     aktuell · gate3_bestaetigt · gate3_gueltig
                     The verdict history. `trigger` ∈ initial | nachreichung | schema_reload.
                     THE FLIP IS ONLY LEGIBLE AS A PAIR — see the note below.
beratungshinweise[]  id · art:Vokabel · titel · text · anker[] · geprueft_von[Fachpruefung]
                     Sätze der Juristen, die bewusst KEIN Prüfpunkt sind — Rat an die
                     Beraterin, keine Feststellung zum Fall. Der gelieferte `art.tone`
                     trennt: gelb = betrifft DIESEN Fall (abraten oder argumentieren),
                     grau = gilt generell, nicht hier. Leere Liste ist der Normalfall.
referat              kriterien[{id,label,angehakt,evidenz?}] · notiz · markiert · hinweis?
abschluss            basis_export_erzeugt · basis_text? · wiedervorlagen[] · geschlossen
dokumente[]          dok_id · dokumenttyp:Vokabel · dateiname? · quelle:Vokabel · eingegangen ·
                     typ_bestaetigt:bool · seiten[{nr, text_original}]
leitfaden            fragen[] · offen
  fragen[]           pruefpunkt_id · pruefpunkt_titel · text · typ · fuellt[] · werte{} ·
                     feld_labels{} · wert_labels{} ·
                     hinweis? · status:Vokabel · grund · antwort{} · zustand?:Vokabel
                     (1.12) `fuellt` und die Codes in `werte` sind Schluessel und werden
                     **nie gerendert**. Fuellt eine Frage mehrere Felder (typ `mehrfach`),
                     ist die Beschriftung je Eingabe `feld_labels[feld_id]` und der
                     Optionstext `wert_labels[feld_id][code]`. Fehlt ein Label, steht die
                     ID da — das ist eine Luecke im Schema, keine Erlaubnis.
                     Der Gesprächsleitfaden (14 §4 Schritt 7) — KEIN eigener Screen, ein
                     Panel auf der Fallakte. Bereits sortiert: was die Einordnung noch
                     bewegen kann, steht vorn. Die Reihenfolge NICHT verändern.
                     **`status` ist der Punkt, nicht die Liste**: offen · beantwortet ·
                     „steht in den Unterlagen" · entfällt. Ein Panel, das alle Fragen
                     gleich darstellt, wirft genau das weg. `grund` ist der fertige
                     Halbsatz dazu. `typ` (ja_nein · zahl · mehrfach · text) steuert das
                     Eingabefeld und wird NIE angezeigt; bei `mehrfach` stehen die
                     erlaubten Werte in `werte[feld_id]`.
                     ⚠️ `typ` steht an der FRAGE, `fuellt` an den FELDERN — eine Frage
                     kann mehrere Felder unterschiedlichen Typs füllen (P13 fragt in
                     einem Satz nach der Strategie *und* nach der Rückforderung).
                     Regel: pro Feld in `fuellt` → steht es in `werte`, wird es eine
                     Auswahl aus genau diesen Werten; steht es nicht darin, gilt der
                     `typ` der Frage, und bei `mehrfach` heißt das ja/nein. Niemals
                     eigene Werte erfinden.
protokoll[]          zeit · akteur · aktion:Vokabel · schritt?:Vokabel · beschreibung
                     Das Ereignisprotokoll (Kontrakt §12) — der Audit-Trail, auf dem die
                     RDG- und AI-Act-Argumentation ruht. `akteur` ist IMMER eine Rolle
                     („Beraterin"), nie ein Name: das Protokoll ist Aufsichtsnachweis und
                     darf keine Leistungskontrolle werden. `beschreibung` ist fertig
                     gerendert — nie selbst aus Codes zusammensetzen.
                     `aktion.tone` ist hier NICHT die Urteils-Ampel: nur grau und gelb
                     kommen vor. gelb = „diese Zeile muss beim Nachlesen erklärt werden"
                     (Überschreibung, Verworfenes, überholte Bestätigung).
fusszeile            … · fachpruefung_bestaetigt · fachpruefung_gesamt (heute 3 / 16)
fusszeile            disclaimer · ki_hinweis · schema_version · schema_stand · stand · stichtag ·
                     stichtag_modus · betriebskosten_cent · normbasis_modus?
```

Three things worth knowing before you design:

- `anker[].geprueft:false` means no law student has confirmed the citation yet. Those cards must
  render **grey / muted with a „ungeprüft" marker** — they must be visibly weaker than a checked
  one. Almost every anchor is `false` right now; that is correct, not a bug.
- `badge` is `null` on Prüfpunkte that used no facts (nothing was verified) → show no chip.
- `zustand` and `rolle` are different axes. `rolle: gate` Prüfpunkte are preliminary questions
  that never change the verdict; `rolle: ergaenzend` ones feed the Prüfumfang box only.
- **`laeufe[]` is not history furniture — it is the demo's central beat.** A case can arrive
  incomplete („unklar – es fehlt …"), the advisor requests the missing document, it is handed in,
  and the verdict *changes*. That change is only meaningful if both verdicts are on screen at
  once. Never collapse `laeufe[]` to the current entry, and never keep run state in the frontend:
  the backend already carries it, including whether an earlier Gate-3 confirmation still holds
  (`gate3_gueltig: false` = someone confirmed a verdict that a later document invalidated).

**The backend is not read-only.** Every button below has a real endpoint; nothing is client-side
state. After any POST, re-fetch `GET /faelle/{id}` and re-render from the response — never patch
the view model locally, or the screen and the audit trail drift apart.

```
POST /faelle/{id}/fallgruppe    {fallgruppe_id*, von}                Gate 2 (re-runs the Prüfung)
POST /faelle/{id}/nachforderung {dokumenttypen, kanal, nachforderung_id, status, von}   Gate 1
POST /faelle/{id}/override      {pruefpunkt_id*, neuer_zustand, grund, zurueckziehen, von}  Gate 3
POST /faelle/{id}/gate3         {von}                                Gate 3 confirm
POST /faelle/{id}/rechtsbehelf  {rechtsbehelf_id*, brief_status, von}                   Gate 4
POST /faelle/{id}/abschluss     {basis_export, wiedervorlagen, schliessen, von}
POST /faelle/{id}/dokumente     {anhaenge, nachforderung_id}         the Nachreichung → the flip
POST /faelle/{id}/leitfaden     {antworten: {feld_id: wert}, von}    Antworten aus dem Gespräch
POST /faelle/{id}/referat       {kriterien, notiz, von}
GET  /radar                                                          the Muster-Radar
```

`von` is the advisor's name and is optional (it defaults). `*` = required. A rejected action
returns a 4xx with a German `detail` string — show it, do not swallow it.

⚠️ **These paths are the whole list. There is no `/faelle/{id}/aktionen/…` prefix and no generic
action dispatcher** — every gate is its own route, and a helper that builds a URL from a button
name posts into the void. This is not hypothetical: the generated `api.ts` shipped exactly such a
helper, and Gate 1, Gate 2, Gate 4 and Abschluss were 404 in live mode for two days while fixture
mode (which replaces every write with a toast) showed them working. Found 24 Aug in the first
complete live probe (`analysis/28` F1), fixed the same day. If a generic sender is convenient,
it must carry an explicit action → route table:

| Button | action | route | body |
|---|---|---|---|
| „Fallgruppe bestätigen" | `fallgruppe_bestaetigen` | `/fallgruppe` | `{fallgruppe_id}` — **required**; send back `kopf.fallgruppe.code`, which the backend reads as „confirmed" and does **not** re-run |
| „Nachforderung erzeugen" | `nachforderung_erzeugen` | `/nachforderung` | `{}` |
| „als angefordert markieren" | `nachforderung_markieren` | `/nachforderung` | `{nachforderung_id, status}` |
| „Rechtsbehelf übernehmen" | `rechtsbehelf_waehlen` | `/rechtsbehelf` | `{rechtsbehelf_id}` |
| „Für Referat markieren" | `referat_markieren` | `/referat` | `{kriterien, notiz}` |
| „Fall abschließen" | `abschluss` | `/abschluss` | `{schliessen: true}` — **every field of `AbschlussEingabe` defaults to false, so an empty body is a 200 that does nothing.** The button's label is „close", so it sends `schliessen` and nothing else; „Basis-Eintrag erzeugen" is a separate action and needs its own control before `basis_export` may be sent |
| Gate-3-Überschreiben | `override` | `/override` | `{pruefpunkt_id, neuer_zustand, grund}` |

And the two rules that the same bug broke a second time: **every** sender surfaces the German
`detail` on a 4xx (not just the status code), and **every** sender refetches `GET /faelle/{id}`
on success. A path fix without the refetch produces „it works but the screen does not move".

### `GET /radar` — the Referat screen's payload

Its own shape, not a slice of the Fallakte. Reference:

```
radar               stand · faelle_gesamt · schwellen{beschwerden,beratungen,k_min} ·
                    cluster[] · klauseltypen[] · unter_schwelle_anbieter ·
                    unter_schwelle_klauseltypen · markierte_faelle[] · hinweis ·
                    geltungsbereich · wiederholungen_gesamt · prueflogik_fassungen
prueflogik_fassungen fallgruppe_id? · aktuell? · zeilen_aktuell · zeilen_aelter · aelteste?
                    (Anleitung §4/§7) Fassung der Prüflogik, unter der die Zeilen liefen —
                    eine Kopfzeile, keine Spalte.
cluster[]           anbieter · branche? · faelle · fallgruppe_id? · einordnungen[] ·
                    pruefpunkte_nein[{titel,anzahl}] · betrag_median? · referat_flags ·
                    schaden · wiederholung
  schaden           drohend_median? · drohend_summe? · entstanden_median? ·
                    entstanden_summe? · fallzahl · unbeziffert · gekappt · basen[]
klauseltypen[]      pruefpunkt_id · titel · fallgruppe_id? · verbreitung ·
                    betroffenheit · quote? · grundgesamtheit · schaden_drohend_median? ·
                    bereits_abgemahnt:bool · abmahnung_kurz? · abmahnung_geprueft?
markierte_faelle[]  fall_hash · fall_kennung · anbieter? · einordnung · kriterien[] ·
                    kriterien_labels[] · zeit · wiederholung
```

**Three rules that come from a lawyer, not from us** — Franz' Anleitung „Einordnung und
Auswertung der Fälle" (24 Aug, `data/eingang/franz_anleitung_mustererkennung.pdf`). Breaking
them produces a screen that is *plausible and wrong*, which is the only kind of wrong that
survives a demo:

1. **`entstanden` and `drohend` never add up to one number.** §5: only the second is
   preventable, and that is what an Erstberatung is about. There is deliberately no total.
2. **`unbeziffert` is not zero.** §5. A case without an amount is counted in `unbeziffert`
   and stays out of every median and sum — `fallzahl` means the *quantified* cases.
   `gekappt` counts the cases whose horizon fell back to 24 months; show that, because a
   capped number must not look like a measured one.
3. **`verbreitung` (how many Verwender) and `betroffenheit` (how many Fälle) are two
   numbers and never one.** §3. Pulling them together says something about the market that
   nobody knows — which is also why `geltungsbereich` is rendered next to the figures and
   not in a footnote.

`markierte_faelle[].kriterien` are **codes** (`bedeutsame_schadenshoehe`) and never go on screen;
render `kriterien_labels` — same rule as everywhere else, the UI does not turn codes into words.
Same for the identifier: **`fall_hash` is not for the screen, `fall_kennung` is.** The short
form comes from the engine because slicing a hash is a transformation too, and a bare
`68fee120` read like debug output. Render it with a static label in front (Fall …) and leave
the sentence in `hinweis` standing — it says the identifier is a pseudonym, not a name.

4. **`wiederholung` / `bereits_abgemahnt` (Anleitung §7).** A case whose broken Prüfpunkt is a
   clause type a Verbraucherzentrale has already taken to court counts as a *Wiederholung*.
   `klauseltypen[].abmahnung_kurz` is the one line to show („VZ Bayern · Vergleich 21.02.2025")
   and `abmahnung_geprueft:false` means it renders with the „ungeprüft" marker like every
   unconfirmed anchor. None of this names the provider of the current case.

`betrag_median` is the median *monthly increase* and is nullable — it is not a Schaden and
must not be labelled as one. `klauseltypen` and `cluster` are both gated by `k_min`
(clauses on the number of Verwender, providers on the number of Fälle); the two
`unter_schwelle_*` counters say how many rows were withheld, and the screen says so too.

---

## 3. Layout

> **Stand 24 Aug:** Die Massengenerierung hat statt der untenstehenden Voll-Breite-Stapelung ein
> dauerhaftes Zwei-Spalten-Layout gebaut (Dokument links, Fallpanel rechts) — akzeptiert, weil das
> ständig sichtbare Dokument der Verifikationsgeschichte dient. **P18** ersetzt den langen Scroll
> der rechten Seite durch Schritte mit einer Leiste am rechten Rand; der erste echte
> Bildschirm-Durchgang hat gezeigt, dass eine Spalte mit ~12 Panels untereinander die
> Konzentration verliert, und auf der Bühne ist Scrollposition keine Erzählung. Die Skizze unten
> beschreibt die inhaltliche Reihenfolge, nicht mehr die physische Anordnung.

```
┌─ FallakteHeader ─────────────────────────────────────────────────────────────┐
│ Fallgruppe · Stufe-Badge · Anbieter · Ticket-Nr        [Fallgruppe bestätigen]│
├─ HeroCard (full width) ──────────────────────────────────────────────────────┤
│  ┌ Einordnung ──────────────┐  ┌ Vollständigkeit ─────────────────────────┐  │
│  │ ● wahrscheinlich unwirksam│  │ Verbraucherseite: —                      │  │
│  │   (traffic light + text)  │  │ Unternehmensseite: Kostenkalkulation     │  │
│  └───────────────────────────┘  └──────────────────────────────────────────┘  │
│  1–3 Sätze in einfacher Sprache (hero.plain)                                  │
│  Prüfumfang: geprüft / NICHT geprüft (hero.pruefumfang)                       │
├─ OffenePunkte ───────────────────────────────────────────────────────────────┤
├─ Pruefpfad (full width, collapsible) ────────────────────────────────────────┤
│  Stufe S0 … S6 → Prüfpunkte: zustand-chip · titel · grund · badge · Zitate    │
│  · Norm-Karten (anker) · verwendete Felder                                    │
├─ Verification station (two panes, below the trace) ──────────────────────────┤
│ ┌── DokumentViewer (left, ~55%) ────┐ ┌── FelderPanel (right, ~45%) ───────┐ │
│ │ tabs: D1 Erhöhungsschreiben ·     │ │ per Prüfpunkt / per Dokument:      │ │
│ │       D2 AGB · D3 Vertrag         │ │  feld_id · wert_anzeige            │ │
│ │ page nav (seiten[].nr)            │ │  herkunft-chip · badge-chip        │ │
│ │ page text as wrapped plain text   │ │  ▸ click a row → highlight         │ │
│ │ <mark> highlight of the active    │ │                                    │ │
│ │ zitat                              │ │                                    │ │
│ └───────────────────────────────────┘ └────────────────────────────────────┘ │
├─ MusterbriefPreview ─── ReferatPanel ─── AbschlussPanel ─────────────────────┤
├─ Fusszeile ──────────────────────────────────────────────────────────────────┤
└──────────────────────────────────────────────────────────────────────────────┘
```

**Click-to-highlight** (the one interaction that must be right): every `Zitat` object anywhere on
the page — in `pruefpfad…zitate[]`, in `verwendet[].zitat`, in `kopf.fallgruppe_vorschlaege[].zitate[]`
— is clickable. Clicking it: (1) scrolls to the verification station, (2) switches the viewer to
`dok_id`, (3) switches to page `seite`, (4) highlights the **plain substring** `zitat` inside that
page's `text_original`. Plain `indexOf`, no fuzzy matching, no regex. If the substring is not
found, show „Zitat nicht im Dokument gefunden" and highlight nothing — never fake a highlight,
never highlight an approximate match.

---

## 4. Prompt sequence — one concern per prompt

Append this guardrail line to every Build prompt:
`Only change <X>. Do not touch <Y>. All labels come from the view model — do not add strings.`

**Zielgerät: Desktop, sonst nichts** (Entscheidung 25 Aug, Register §D D9). Die Anwendung läuft am Schreibtisch und über einen Beamer. Prompts verlangen **keine** Telefon-/Tablet-Anpassung, keine Touch-Gesten und keine Rastervarianten unter 1024 px; geprüft wird bei 1440×900 (und 1920×1080 für die Bühne). Bestehende `sm:`-Klassen bleiben, neue werden nicht gebaut.

| # | Mode | Prompt |
|---|---|---|
| P0 | Plan | „Read `public/fixtures/faelle/F-2026-0001.json` **and `F-2026-0002.json`** (the second one carries `laeufe[]` with two verdicts and a `nachforderungen[]` entry; the types must cover both). Propose the component tree, `src/types/viewmodel.ts` (German keys unchanged, 1:1 with the JSON) and the two routes `/faelle/:id` and `/referat`. Do not write code. List every assumption you would otherwise make." |
| P1 | Build | „Scaffold only. Add the two routes as **files in the existing `src/routes/` tree** — `faelle.$id.tsx` and `referat.tsx` under the `__root.tsx` that is already there. Do not add react-router-dom, do not create a second router, do not edit `routeTree.gen.ts`. Both routes fetch **in the component with TanStack Query**, never in a route `loader` and never via `createServerFn` (see rule 1a). Then `src/lib/api.ts` (if `import.meta.env.VITE_API_BASE_URL` is set, fetch `${base}/faelle/${id}`; otherwise fetch `/fixtures/faelle/${id}.json`, defaulting `id` to `F-2026-0001` — so the flip fixture is reachable as `/faelle/F-2026-0002` without a rebuild), `src/types/viewmodel.ts`, the design tokens (traffic light gruen/gelb/rot/grau + neutral civic palette, 16 px base), a `<Vokabel>` chip component that takes `{code,label,tone}` and renders `label` coloured by `tone`, and the page shell in the section order Header → Laeufe → Hero → OffenePunkte → Nachforderung → Pruefpfad → VerificationStation → Musterbrief → Referat → Abschluss → Fusszeile, each as an empty placeholder card. No panel content yet. **Nullability, gegen die Fixtures gemessen — nicht aus dem Beispiel ableiten, ein Feld kann in beiden Fixtures gefüllt und trotzdem optional sein:** `musterbrief` ist `Musterbrief | null` (ein Fall ohne Rechtsbehelf — Stufe B/C oder gestopptes Schema — hat keinen Brief; beide Fixtures haben einen, der Absturz käme erst gegen das echte Backend) · `TraceEintrag.badge`, `TraceEintrag.typ`, `TraceEintrag.override`, `VerwendetesFeld.verifiziert`, `Anker.text`, `Anker.status`, `Anker.kernaussage`, `Nachforderung.zeit`, `Referat.hinweis`, `Fusszeile.normbasis_modus`, `Dokument.dateiname`, `LeitfadenFrage.zustand`, `LeitfadenFrage.hinweis`, `Kopf.gegner`, `Abschluss.basis_text` sind alle nullable. **Und die Formen, die man aus einem leeren Array nicht erraten kann:** `abschluss.wiedervorlagen` ist `string[]` (keine Objekte) · `leitfaden.werte` ist `Record<string, string[]>` — pro Feld die erlaubten Werte, nicht ein Wert · `TraceEintrag.override` ist `{neuer_zustand: Vokabel; grund: string; von: string; zeit: string}` · `radar.markierte_faelle[]` ist `{fall_hash: string; anbieter: string | null; einordnung: string; kriterien: string[]; zeit: string}` — **`fall_hash`, nicht `case_id`**, und `anbieter` ist `null`, wenn der Cluster dieses Anbieters unter `k_min` liegt: dann in dieser Zeile gar keinen Anbieter zeigen, nicht „ohne Namen". `Fehlend.felder` ist `string[]` und `leitfaden.antwort` ist `Record<string, unknown>`." |
| P2 | Build | FallakteHeader from `kopf`. Fallgruppe + Stufe chip + Anbieter + Ticket-Nr + a „Fallgruppe bestätigen" button (disabled when `fallgruppe_bestaetigt`). |
| P3 | Build | HeroCard from `hero`: Einordnung traffic light (large, `label` verbatim) beside Vollständigkeit (two labelled lists), then `plain[]` as paragraphs, then the Prüfumfang box listing `pruefumfang[]` as „NICHT geprüft"-style rows. |
| P4 | Build | OffenePunkte from `offene_punkte[]`: one row per item, `art` chip + `text`, linking to its `pruefpunkt_id` in the trace. |
| P5 | Build | Pruefpfad from `pruefpfad`: one collapsible group per `stufen[]` entry (header = `titel` + `zustand` chip; the `gerissene_stufe` group is marked (open-by-default was revised by K21: since the step rail, all groups start collapsed)). Inside, one row per Prüfpunkt: `zustand` chip, `titel`, `rolle`/`typ` chips, `badge` chip if present, `grund`, then on expand — `proposition`, `zitate[]` as clickable quote chips, `anker[]` as Norm cards (`label`, `ebene`, `kernaussage`, collapsible `text`, `url` link, muted when `geprueft:false`), `verwendet[]` as a compact table, `wertungsfrage`, `frist`, `betrag`. `zustand.code === "INAKTIV"` renders muted with `inaktiv_grund`. Hide the Stufe-header zustand chip when the group contains no Prüfpunkt with `rolle.code === "tragend"` — S0/S5/S6 are INAKTIV only because gates and ergänzende Punkte never aggregate, and printing their INAKTIV label there misleads; keep the chip on every Stufe that has tragend children (a gate-deactivated S3 must still show it). |
| P6 | Build | The verification station: `DokumentViewer` (tabs per `dokumente[]`, page switcher over `seiten[]`, `text_original` as wrapped plain text) + `FelderPanel` (rows from `verwendet[]` across the trace, grouped by document: `feld_id`, `wert_anzeige`, `herkunft` chip, `badge` chip). Wire click-to-highlight exactly as described in §3 of the prompt pack. Then the five Details aus dem **beigefügten Bildschirmfoto** einer ABBYY-Vantage-Verifikationsstation (dem Prompt als Bild angehängt — das llt26-Repo ist von hier aus nicht sichtbar, also niemals auf einen Pfad dorthin verweisen): **(a)** jedes `Zitat` der offenen Seite blass im Seitentext markieren, nicht nur das angeklickte, und das aktive kräftig — ein Blick zeigt dann, wie viel des Dokuments gelesen wurde; **(b)** links vom Viewer eine Seiten-Leiste, ein Eintrag je `dokumente[].seiten[]`, damit ein später eingegangenes Dokument als späteres sichtbar ist; **(c)** über dem Feldpanel ein Schrittzähler „Offene Punkte: N" aus `offene_punkte[]` mit Vor/Zurück, der beim Schritt zum jeweiligen Prüfpunkt scrollt und ihn aufklappt; **(d)** darunter eine stehende Statuszeile, die die Badges der Spur auszählt (Beispiel: alle Zitate verifiziert · 3 LLM-Befunde · 1 Annahme) — ausschließlich aus den gelieferten `badge`-Labels gebaut, nie aus eigenen Worten; **(e)** ein rotes `*` an Zeilen, deren Feld im Dokumenten-Soll `pflicht` ist. Zwei Zeilen mit demselben `feld_id` und verschiedenem `wert_anzeige` sind kein Fehler, sondern ein `strittig`-Feld, das beide Seiten zeigt: beide rendern, nie zusammenfassen. |
| P7 | Build | MusterbriefPreview from `musterbrief`: title, `quelle` chip, `status` chip, `empfaenger`, the letter `text` in a bordered block preserving line breaks, a „Kopieren" button, and `vorschlaege[]` as selectable remedy options with the `hauptvorschlag` preselected. Add a visible „nicht juristisch geprüft" marker when `geprueft` is false. |
| P8 | Build | ReferatPanel (`kriterien[]` as checkboxes with `evidenz` shown inline, never auto-ticked; `notiz` textarea; `hinweis` as a note) and AbschlussPanel (`basis_export_erzeugt`, `basis_text` in a copyable block, `wiedervorlagen[]`, „Fall schließen"). |
| P9 | Build | Fusszeile from `fusszeile`: disclaimer · KI-Hinweis · Schema-Version + Stand · Stand/Stichtag (+ „Demo-Stichtag" marker when `stichtag_modus === "demo"`) · Betriebskosten in €. Small, muted, always visible. |
| P10 | Build | `/referat` Muster-Radar from `public/fixtures/radar.json` (**generate it, do not invent it**: start the backend, run `tools/radar_seed.py --zuruecksetzen && tools/radar_seed.py` once, then save `GET /radar` to that path — the seed deliberately leaves the demo provider one case below the threshold so confirming the case on stage is the „+1"): cluster bars per Anbieter/Fallgruppe, threshold markers, a „+1" tick animation, a „Sonstiges" bucket, list of flagged cases. |
| P12 | Build | **LaeufeStrip from `laeufe[]` — the flip.** One chip per run, in order, `einordnung` coloured by `einordnung_tone`, `trigger` as a small caption („Ersteingang" / „nach Nachreichung" / „nach Regeländerung"), the `aktuell: true` one emphasised and the others muted but **still readable — never hide or collapse them**. When a run has `gate3_bestaetigt: true` and `gate3_gueltig: false`, mark it „Bestätigung überholt". With one entry the strip renders as a single chip; do not special-case it away. |
| P13 | Build | **NachforderungPanel from `nachforderungen[]`** (hide the section when the list is empty): per entry the `kanal` chip, the requested `dokumente[]` as chips, `text` in a bordered block preserving line breaks, a „Kopieren" button, and a „als angefordert markieren" button that POSTs `{nachforderung_id, status}` to `/faelle/{id}/nachforderung`. Say visibly that the tool sends nothing itself. Add an „Unterlagen nachreichen" control that POSTs to `/faelle/{id}/dokumente` and then re-fetches — that POST is what produces the second entry in `laeufe[]`. |
| P14 | Build | **ProtokollPanel from `protokoll[]` — der Audit-Trail.** Ein Knopf „Ereignisprotokoll" in der Fusszeile öffnet einen Dialog mit einer Tabelle: Zeit · Schritt (`schritt.label`) · Ereignis (`aktion.label`) · Beschreibung. Zeilen mit `aktion.tone === "gelb"` bekommen einen dezenten Marker und einen Filter „nur auffällige Zeilen"; ein Zähler „Gesamt: N" unten links; ein „Kopieren"-Knopf, der die Tabelle als Text in die Zwischenablage legt. Keine Diagramme, keine Dauer-, Durchsatz- oder Wartezeitmetriken, keine Personennamen — das Protokoll führt Rollen. Nichts wird gesendet. |
| P15 | Build | **LeitfadenPanel from `leitfaden`.** Eine Liste in der gelieferten Reihenfolge — nicht umsortieren, nicht gruppieren. Pro Frage: `status`-Chip (`label`, Farbe aus `tone`), `text` als Frage, `grund` klein darunter, `pruefpunkt_titel` als Verweis in den Prüfpfad, `hinweis` als Notiz. Eingabefeld nach `typ`: ja_nein = zwei Knöpfe, zahl = Zahlenfeld, text = einzeiliges Feld, mehrfach = Auswahl aus `werte[feld_id]`. Fragen mit `status.code !== "offen"` erscheinen eingeklappt und ausgegraut, mit `antwort` bzw. `grund` sichtbar — **nie ausblenden**. Ein Kopf „N von M Fragen offen" aus `offen`. Ein Knopf „Antworten übernehmen" schickt ALLE ausgefüllten Antworten in EINER Anfrage an `POST /faelle/{id}/leitfaden`; der Stapel ist atomar, ein 400 mit deutschem `detail` heißt „nichts wurde geschrieben" — den Text anzeigen und die Eingaben stehen lassen. Danach `GET /faelle/{id}` neu holen: die Antwort kann die Einordnung ändern, also erscheint ein neuer Eintrag in `laeufe[]` — **und sie kann Prüfpunkte abschalten.** Eine Antwort auf eine Gate-Frage setzt andere Prüfpunkte auf `zustand.code === "INAKTIV"`; die stehen dann mit ihrem `inaktiv_grund` im Prüfpfad und dürfen dort **nicht verschwinden**, sonst sieht der Schirm aus, als hätte das Programm etwas vergessen. Beispiel aus dem Inkasso-Schema: die Antwort „im Ladengeschäft geschlossen“ schaltet vier Widerrufspunkte ab, alle vier tragen denselben Satz. Der Satz kommt fertig aus dem Backend; bei einem Gate ist `inaktiv_grund` nie leer. |
| P11 | Build | Polish pass: badge hover text, keyboard/focus, 1280 px and phone check. Change no data handling. |

Do not ask for "the whole Fallakte screen" in one prompt. Check the GitHub diff after every Build
prompt; revert via version history if it touched other panels.

---

## 4a. Korrekturprompts (K) — nach einer Massengenerierung

Lovable hat P0 nicht befolgt und statt eines Plans **alles auf einmal gebaut** (`1e2633d`).
Das Gerüst taugt, die Befunde sind lokal — also nicht zurückrollen, sondern gezielt korrigieren.
Vier Stichproben, drei daneben: nicht die drei Befunde sind die Nachricht, sondern die Quote.
Deshalb prüft **K4 den Rest**, statt ihn zu glauben.

| # | Mode | Prompt |
|---|---|---|
| K1 | Build | „In `src/components/referat/RadarView.tsx`: delete the function `toneFuerEinordnung` and every call to it. It maps a German verdict string to a colour, which rule 2 forbids — and the wording of the `unklar` verdict is still an open decision, so the colours would go wrong silently the day it changes. The radar payload carries **no** tone: `cluster[].einordnungen` is a plain `Record<verdictText, count>`. So render the split **without** the traffic light — verdict text plus count, neutral bars — until the backend delivers a tone for it. Do not pick a palette of your own, do not order the segments by severity, do not abbreviate the verdict texts. Only change RadarView.tsx." |
| K2 | Build | „In `src/components/fallakte/AnkerPopover.tsx`: use `anker[].geprueft`, which is currently read nowhere. `false` means no lawyer has confirmed this citation against the original yet, and **every** anchor in this build is `false`. Render those visibly weaker than a confirmed one — muted trigger plus a short marker „ungeprüft" — so an unconfirmed source cannot look like a confirmed one. `true` renders as it does today, with no extra badge. This is the one statement the trust framing rests on: the screen currently claims the opposite of what the engine says. Only change AnkerPopover.tsx." |
| K3 | Build | „In `src/components/fallakte/Pruefpfad.tsx`, the list over `p.verwendet` uses `key={v.feld_id}`. That key is **not unique**: a contested field appears twice with the same `feld_id` and different `wert_anzeige` — the engine reports both sides on purpose (`strittige_felder`), because the Prüfpunkt went to WERTUNG precisely because they disagree. Use `key={`${v.feld_id}-${index}`}` and keep both rows. Never deduplicate by `feld_id`, never keep only the last one, never merge the values. When a `feld_id` occurs more than once, mark the group visibly as contradictory using the delivered `herkunft` label — do not write a sentence of your own. Only change Pruefpfad.tsx." |
| P16 | Build | **`geprueft_von` und `fehlzustand` (View Model 1.4).** (a) Im Prüfpfad, pro Prüfpunkt: ist `geprueft_von` nicht leer, eine Zeile „Fachlich bestätigt: <wer> · <beleg> (<am>)" mit `umfang` darunter; ist `vorbehalt` gesetzt, steht er **direkt daneben und gleich stark**, nie kleiner und nie hinter einem Aufklappen — er schränkt genau die Bestätigung ein, neben der er steht. Ist die Liste leer: **nichts rendern**, kein „ungeprüft"-Abzeichen erfinden. (b) In der Fusszeile aus `fachpruefung_bestaetigt`/`fachpruefung_gesamt` ein Satz wie „<n> von <m> Prüfpunkten fachlich bestätigt" — die Zahlen kommen fertig, nicht selbst zählen. (c) Bei jedem Vollständigkeits-Posten mit `fehlzustand` den gelieferten Chip zeigen; bei `fehlzustand.code === "existiert_nicht"` zusätzlich `aussage` als Zitat darunter, in derselben Form wie ein Dokumentzitat, nur ohne Fundstelle. (d) An jedem offenen Posten der Verbraucherseite eine Sekundäraktion „Existiert nicht" mit der Unterzeile „Die Verbraucherin sagt, dieses Dokument hat es nie gegeben." — sie POSTet `{dokumenttyp, aussage}` an `/faelle/{id}/nicht-vorhanden` (Freitext ist Pflicht, ohne ihn kein Absenden) und danach wird neu geladen. Der Posten wandert dabei von der Verbraucher- auf die Unternehmensseite: **sag das auf dem Schirm**, sonst sieht die Beraterin nur, dass etwas verschwunden ist. |
| K8 | Build | „Same family as K7, found by scanning every field that is empty in both fixtures and filled only by an action: `src/types/viewmodel.ts` declares `Wiedervorlage {titel, datum, grund}` — an invented object shape. The backend sends `abschluss.wiedervorlagen` as **`string[]`**, plain lines like „2026-09-15: Frist Widerspruch". `AbschlussPanel.tsx` renders `{w.datum} — {w.titel} ({w.grund})`, which for a string is three `undefined`s. Both fixtures carry an empty list, so nothing has broken yet — but Abschluss is step 10 of the demo, and the first Wiedervorlage entered on stage renders as „undefined — undefined (undefined)". Change the type to `string[]` and render each entry as the plain line it is. Change nothing else." |
| P17 | Build | „Two changes for view model 1.5. **(a)** `laeufe[].trigger` is now a `{code,label,tone}` Vokabel — in `LaeufeTimeline.tsx` render `lauf.trigger.label` instead of the raw string, and update the type. **(b)** New panel `BeratungshinweisePanel` from `beratungshinweise[]`, placed between LeitfadenPanel and MusterbriefPreview; hide the whole section when the list is empty. Per entry: the `art` chip (delivered label and tone), `titel` as heading, `text` as body, `anker[]` with the same muted-plus-„ungeprüft" treatment as everywhere, and `geprueft_von[]` with the same block as the Prüfpfad uses — `vorbehalt` beside the attribution at equal weight, never collapsed. These are sentences a lawyer wrote for the advisor, NOT findings about the case: do not mix them into the Prüfpfad, do not colour anything beyond the delivered tones, and when `titel` is phrased as a question, keep it a question. Only add the new panel, the trigger rendering, and the two types." |
| P18 | Build | „Restructure the Fallakte from one long scroll into **steps with a right-hand rail**, without touching any panel internally. Layout: the document viewer stays as the always-visible left pane exactly as it is; the header stays; add a slim **always-visible status line** directly under the header carrying the current `hero.einordnung` (dot + label, delivered tone) and the `laeufe[]` chips in miniature — this line is never hidden, because the verdict can change while the user is on another step (a Nachreichung flips it) and the change must be visible at the moment it happens. The right side becomes ONE step at a time, chosen via a vertical rail of buttons on the far right: 1 „Einordnung" (HeroCard + LaeufeTimeline), 2 „Offene Punkte & Gespräch" (OffenePunkte + LeitfadenPanel + BeratungshinweisePanel), 3 „Unterlagen" (NachforderungenPanel), 4 „Prüfpfad" (Pruefpfad), 5 „Musterbrief" (MusterbriefPreview), 6 „Abschluss" (ReferatPanel + AbschlussPanel + ProtokollPanel). Rail buttons show the step name plus a plain count where the data has one („Offene Punkte (4)", „Unterlagen (1)") — counts only, **no status dots and no colours on the rail**: aggregating a step into a colour would be the UI deciding something. Step state is plain component state, no new route (rule 6 stands). Cross-step links keep working: clicking an Offener Punkt with a `pruefpunkt_id` switches to step 4 and opens that Prüfpunkt; a Zitat click always works because the viewer is always there. The Fusszeile stays at the bottom, always visible. Do not modify any panel component — only the page composition in faelle.$id.tsx plus one new StepRail component." |
| P19 | Build | „Design-token pass, two concerns, no component logic. **(1) The citation highlight gets its own token — classic German Textmarker-Gelb — instead of borrowing anything.** Add to `src/styles.css`: light mode `--marker: oklch(0.92 0.18 102)` (luminous highlighter yellow) with mark text `oklch(0.22 0.02 260)` (near-black — the Textmarker effect is dark text on luminous yellow), plus a faint variant `--marker-schwach: oklch(0.97 0.09 102)` for the every-quote shading of P6(a); dark mode `--marker: oklch(0.42 0.10 100)` with light text. Use it in `DokumentViewer.tsx`: the active `<mark>` gets the full marker (currently `bg-accent` — a pale grey, nearly invisible for the one interaction that must be right), the passive all-quotes shading gets `--marker-schwach`. The marker is deliberately NOT `tone-gelb`: the traffic light says „unclear/action needed", the marker says „this is the cited passage" — two meanings, two colours. **(2) Contrast pass on the tone tokens — everything is too pale.** In `src/styles.css` light mode: darken the text tones (`--tone-gruen` 0.44→0.40 L, `--tone-gelb` 0.48→0.42, `--tone-rot` 0.48→0.44, `--tone-grau` 0.45→0.40) and strengthen the chip backgrounds (all `--tone-*-bg` from 0.96 L to 0.93 and roughly double the chroma, e.g. gelb-bg 0.05→0.09). In `src/lib/tone.ts` raise the chip border opacity from `/40` to `/70`. Check that chip text on chip bg stays ≥ 4.5:1. Change only styles.css, tone.ts and the two mark styles in DokumentViewer.tsx." |
| K32 | Build | „Three small dedups in `src/components/fallakte/Pruefpfad.tsx`, all found by walking the deployed screen. **(1)** Delete the raw `Fehlt: {feld_ids}`-line (it prints `vertrag.datum` — a raw field id; the human sentence naming what is missing is already delivered and rendered right above it). **(2)** Hide the „WERTUNGSFRAGE:" line when `wertungsfrage` is string-identical to the `grund` already shown — the same sentence currently prints twice in a row on WERTUNG points. **(3)** In the Prüfpunkt's standalone `zitate[]` chip list, skip any Zitat that is object-identical (`dok_id`+`seite`+`zitat`) to one already rendered inside a `verwendet[]` row of the same Prüfpunkt — the same quote currently appears as two adjacent chips. All three are presentation dedups of delivered content; nothing is reworded. Only change Pruefpfad.tsx." |
| K31 | Build | „Norm chips and citation chips now wear the same grey — two different kinds (a passage from the case documents vs. a statute) need different clothes, and for statutes the German convention is blue. **(1)** In `src/styles.css` add a structural token pair: light mode `--norm: oklch(0.40 0.15 262)` (unmistakably blue text) and `--norm-bg: oklch(0.92 0.06 262)` (a visibly blue-tinted field, NOT near-white — the first attempt used 0.95 L / 0.03 chroma and was indistinguishable from the grey `bg-muted` beside it), dark mode `--norm: oklch(0.78 0.11 262)` / `--norm-bg: oklch(0.30 0.06 262)`; the chip border uses solid `--norm` at `/60`, not `/40`, registered like the tone tokens. This is a component-class colour like link blue, not a state tone — the traffic light stays untouched. **(2)** In `src/components/fallakte/AnkerPopover.tsx` the trigger chip uses them: verified (`geprueft: true`) → solid border in `--norm`/40, `--norm-bg` background, text `--norm`; unverified → same family but dashed border and reduced opacity, keeping the „· ungeprüft" marker and the chevron exactly as they are. Citations stay grey. Change only styles.css and AnkerPopover.tsx." |
| K30 | Build | „Typographic hierarchy in the Vollständigkeit block of `src/components/fallakte/HeroCard.tsx` — three fixes, no colours. **(1)** The section header and its two sub-headers currently share one style (uppercase muted), flattening three levels into one: keep „VOLLSTÄNDIGKEIT" as the uppercase section label, but render „Verbraucherseite" / „Unternehmensseite" in normal case `text-sm font-medium text-foreground` — a sub-heading, not a sibling. **(2)** Inside an item, `grund` and the Weg line are two identical muted lines: keep `grund` as muted body text, and give the Weg line a `font-medium` „Weg:" prefix (same prefix pattern as the Vorbehalt in K28) so „why we need it" and „where to get it" stop reading as one paragraph. **(3)** Delete the floating „Verbraucherseite vollständig/unvollständig." sentence at the block's bottom — it duplicates the list state above and, sitting under Unternehmensseite, mis-attaches itself; instead, when `vollstaendig_verbraucherseite` is true render the Verbraucherseite empty state as „Vollständig — nichts offen." (one sentence, delivered-flag-driven, in place of the current „Nichts offen."). Only change HeroCard.tsx." |
| K29 | Build | „Revise the citation chip in `src/components/fallakte/ZitatLink.tsx` — the K27 marker-yellow background reads as warning-family and floods panels with yellow blobs when a Prüfpunkt has several citations. The marker yellow stays ONLY where the result lands (the in-document highlight); the chip is a button, not a result. Restyle to the app's established chip grammar, exactly like the anchor chips: rounded `border border-border bg-muted` container, hover `bg-accent`, visible focus ring; inside, in this order: **an `ArrowLeft` (size-4, muted) as the very first element** — on the demo layout it physically points at the document pane where the highlight will appear —, then the quote icon and the quote text (wrapping allowed), then a **`FileSearch` (size-3, muted) at the end**, and the `(D1, S. 1)` reference as a muted suffix after it. Both icons on all breakpoints, no responsive swap. No marker background, no dotted underline, `title=\"Im Dokument zeigen\"` stays. One file recolours every citation." |
| K28 | Build | „The Fachprüfung attribution renders as two similar prose paragraphs in two places (Pruefpfad.tsx and BeratungshinweisePanel.tsx) — extract ONE shared component `FachpruefungBlock.tsx` and use it in both. Structure, purely typographic (no colours beyond neutral — a coloured accent here would be the UI choosing a signal): a `border-l-2 border-border pl-2` container (the attest look); first line a tiny muted uppercase label „Fachlich bestätigt", second line `wer` in `font-medium` followed by muted `· beleg · date` with `am` formatted German (`23.08.2026`, not the raw ISO `2026-08-23`); `umfang` as normal small body text; `vorbehalt`, when present, at the **same size** with a `font-medium` „Vorbehalt:" prefix — never smaller, never collapsed (it limits exactly the confirmation above it). Replace the two inline renderings with the component; content identical. Only add FachpruefungBlock.tsx and swap it into the two files." |
| K27 | Build | „`src/components/fallakte/ZitatLink.tsx` — the citation chip is THE core interaction (click → the document viewer jumps to the page and highlights the passage), but its dotted underline reads like a glossary term, not like „show me in the document". Fix by reusing the app's own metaphor instead of adding explanation: the in-document highlight is Textmarker yellow, so the chip becomes a **faint marker**: background `--marker-schwach`, normal foreground text, rounded, no dotted underline; on hover the background strengthens to the full `--marker` with `--marker-foreground` text — the visual sentence is „this passage is highlighted; click to see it highlighted in the original". Keep the quote icon at the start, keep the `(D1, S. 1)` reference as a muted suffix outside the marker background, and add a small **`FileSearch` icon (size-3, muted)** at the end of the chip — the static cue for „locate in the document", visible before any hover. Do NOT use `ExternalLink` for this: that icon already means „opens an external URL" on the norm cards, and a citation stays inside the app. Add `title=\"Im Dokument zeigen\"` and keep the whole thing a real button with visible focus ring. Only change ZitatLink.tsx — every place that renders citations uses this component, so one file recolours them all." |
| K25 | Build | „Move the Zuordnungsvorschläge out of the header — restyling did not fix it because the position was the problem: the header states the case's identity, while the proposals are assessment evidence (the model's two suggestions with reasoning and quotes). **(1)** In `src/components/fallakte/FallakteHeader.tsx` delete the whole Zuordnungsvorschläge disclosure; the header keeps the title, the chips, the id line and the conditional „Fallgruppe bestätigen" button — nothing else. **(2)** New component `ZuordnungsvorschlaegePanel.tsx`: a normal Panel card (same as every other panel) titled „Zuordnungsvorschläge (N)" with the „bestätigt / nicht bestätigt" note as muted text in the header row, the content exactly as it renders today (fallgruppe label + stufe chip, `begruendung`, `zitate` as ZitatLink). **(3)** Render it in step 1 (Einordnung) after LaeufeTimeline in `faelle.$id.tsx`. Gate-2 button and its evidence then live one step apart at most, instead of the evidence hiding in the header furniture." |
| K33 | Build | „`src/components/referat/RadarView.tsx` + `src/types/viewmodel.ts` — der Radar-Payload trägt drei neue Blöcke, und alle drei sind juristische Vorgaben, keine Kosmetik (Quelle: §2, Abschnitt `GET /radar`). **(1) `geltungsbereich`** als eigener Kasten **über** den Zahlen, nicht als Fußnote — der Satz sagt, dass die Auswertung das Beratungsaufkommen abbildet und nicht den Markt. **(2) `cluster[].schaden`**: „Bereits entstanden" und „Noch abwendbar" als **zwei** Werte nebeneinander, je Summe mit dem Median klein daneben; darunter eine Zeile „aus N bezifferten Fällen", die `unbeziffert` nennt, falls > 0 („unbeziffert, nicht null"), und `gekappt` als Satz ausschreibt („hilfsweise auf 24 Monate begrenzt"). **Keine Gesamtsumme aus beidem bilden.** Der alte Kopfzeilen-Wert „Median 4,75 €" verschwindet aus der Kopfzeile: er ist die monatliche Erhöhung und kein Schaden. **(3) `klauseltypen`** als eigener Abschnitt **über** den Anbieter-Clustern: je Zeile Titel, dann `verbreitung` Verwender · `betroffenheit` von `grundgesamtheit` Fällen · Median noch abwendbar, darunter ein dünner Balken, dessen Breite die **`quote`** ist (nicht der Abstand zur größten Zeile — bei zwei gleich häufigen Typen wären zwei volle Balken die Aussage „beide am Maximum", und das ist keine). Darunter `unter_schwelle_klauseltypen` als Satz. **(4)** `markierte_faelle` rendert `fall_hash` (die ersten acht Zeichen, monospace) statt eines Links — es gibt keine `case_id`, die Auswertungsebene ist pseudonymisiert; `anbieter` kann `null` sein, dann diese Angabe weglassen statt einen Platzhalter zu setzen. `betrag_median`, `branche` und alle `schaden`-Zahlen sind nullable — „—" statt Absturz. Nur diese zwei Dateien ändern." |
| K34 | Build | „`src/lib/api.ts` — two senders still swallow the backend's German `detail` on a 4xx and show only „Aktion fehlgeschlagen (409)": `nichtVorhandenSenden` (line ~110) and, until adef205, `dokumenteSenden`. Make `nichtVorhandenSenden` throw `new Error(await fehlerText(res))` exactly like `gate3Senden`/`referatSenden`/`aktionSenden`, and in `src/components/fallakte/HeroCard.tsx` wrap the `await nichtVorhandenSenden(...)` in `absenden()` with `try { … } catch (fehler) { toast.error(fehler instanceof Error ? fehler.message : String(fehler), { duration: 12000 }); return; }` before the existing `finally`. The backend answers a document it does not know with 409 and a full sentence for the advisor (Vorführmodus without model connection) — that sentence is the whole point; a status code hides it. Only change api.ts and the one call site in HeroCard.tsx." |
| K35 | Build | „`src/components/referat/RadarView.tsx` + `src/types/viewmodel.ts`: `markierte_faelle[]` now carries `kriterien_labels: string[]` next to `kriterien: string[]`. The `kriterien` are **codes** (`schadenshoehe`, `neuigkeitswert`) and must never be rendered; the screen showed „(neuigkeitswert, dauerbrenner)" with underscores. Add `kriterien_labels: string[]` to `MarkierterFall` and render `f.kriterien_labels.join(\", \")` in the parenthesis (fall back to `f.kriterien` only if `kriterien_labels` is missing, so an old fixture still renders). Same rule as everywhere: the UI does not turn codes into words. Only change those two files." |
| K36 | Build | „`src/components/fallakte/AbschlussPanel.tsx` + the wiring in `faelle.$id.tsx`: the panel renders `basis_text` and the line „Basis-Export erzeugt/nicht erzeugt", but no control produces it — the only button is „Fall abschließen", which deliberately sends `{schliessen: true}` and nothing else. Add a second outline button **„Basis-Eintrag erzeugen"** (left of „Fall abschließen") that calls a new prop `onBasisExport`, wired in the route as `void senden(\"abschluss\", { basis_export: true })` — the existing `senden` helper already refetches. Disable it with the static caption „Basis-Eintrag erzeugt" once `abschluss.basis_export_erzeugt` is true. Under the rendered `basis_text` add a „Kopieren" button (same clipboard pattern as MusterbriefPreview) — 14 §4 step 10 calls it a copyable summary, „exportierbar in Ihr Kategoriensystem", no API claim. Never let one button do both things. Only change AbschlussPanel.tsx and the one prop in faelle.$id.tsx." |
| K37 | Build | „Three null paths the fixtures cannot show (Inkasso has two Unterlagenarten without a `dokumenttyp`, and a Stufe-B/C case has no letter). (1) `src/types/viewmodel.ts`: `FallAnsicht.musterbrief` becomes `Musterbrief | null`; in `faelle.$id.tsx` render, when it is null, a `Panel` titled „Musterbrief" with the `LeerHinweis` „Für diese Einordnung liegt kein Schreiben vor." instead of mounting `MusterbriefPreview`. (2) `Posten.dokumenttyp` becomes `Vok | null`; in `HeroCard.tsx` render the `ToneBadge` for it only when present (lines ~77 and ~127) and do **not** offer the „Existiert nicht" action on a Posten without `dokumenttyp` (line ~46 posts its code — there is none to post). (3) Delete the phantom field `aussage` from the `Fehlzustand` interface — the backend never sends it there; `aussage` lives on the Posten and stays. Do not invent placeholder labels for a missing dokumenttyp; show nothing. Only change viewmodel.ts, HeroCard.tsx and the one branch in faelle.$id.tsx." |
| K38 | Build | „`src/components/fallakte/LeitfadenPanel.tsx`: a question with **more than one** field in `fuellt` renders one input per field with no caption — P13 shows a select **and** a Ja/Nein pair side by side and nobody can tell which answers what. When `fuellt.length > 1`, put a small muted caption above each input with that field's id, in the same muted style Pruefpfad.tsx uses for `feld_id` (established grammar — a field id is data, not an invented label). Single-field questions stay exactly as they are. Only change LeitfadenPanel.tsx." |
| K39 | Build | „`src/components/fallakte/StepRail.tsx` + the `schritte` array in `faelle.$id.tsx`: the rail says „Unterlagen (1)" while the case has four documents — the number counts Nachforderungen, and the label does not say so. Extend `StepDef` with an optional `einheit?: { eins: string; viele: string }` and render the count as „(1 Nachforderung)" / „(2 Nachforderungen)" when `einheit` is set; pass `einheit: { eins: \"Nachforderung\", viele: \"Nachforderungen\" }` for step 3 only. Step 2 keeps its bare count. Only change StepRail.tsx and the one array entry." |
| K40 | Build | „**Only after Sungho's C3 decision (Akt 2 from the UI).** `faelle.$id.tsx` + `api.ts`: add `neuPruefenSenden(caseId)` posting to `/faelle/{id}/neu-pruefen` with an empty body (same error pattern as gate3Senden), and one outline button **„Prüfschema neu einlesen"** in the Prüfpfad panel header (Schritt 4) that calls it and then refetches — the schema file is edited in a plain text editor beside the screen; this button is only the trigger. After success the header line and `laeufe[]` change by themselves (a new run with trigger `schema_geaendert`). Show the German `detail` on a 4xx: a broken edit is answered with a sentence naming what broke, and that sentence is part of the beat. Only change api.ts, the Prüfpfad panel header and its wiring." |
| K41 | Build | „`src/components/referat/RadarView.tsx` — the Referat screen says the same thing four times, and the repetition (not the density) is what makes it hard to read. Delete three **static** explanations; touch no number and no payload field. **(1)** The two-line subtitle under the heading „Klauseltypen" („Verbreitung (wie viele Verwender) und Betroffenheit (wie viele Fälle) stehen getrennt …") — every row already prints „3 Verwender · 4 von 9 Fällen". **(2)** The line „{n} weitere Klauseltypen stehen bei weniger als {k} Verwendern und werden nicht ausgewiesen" — the footer `radar.hinweis` already carries exactly that sentence. **(3)** The whole „Sonstiges" panel („{n} Anbieter unter der Schwelle von {k} Fällen — nicht einzeln ausgewiesen") — same sentence, same footer. The footer `radar.hinweis` stays as the ONE place where suppression is stated. Additionally **(4)** put the per-cluster methodology line (the one built in `schadenSatz`: „aus 4 bezifferten Fällen · Ein Fall ohne erkennbare Laufzeit … · Ein Fall in der Verlängerung …") behind a collapsible trigger labelled „Berechnung", closed by default, in the established grammar (button-like trigger + rotating ChevronDown, never a native <details>). Do not shorten or reword any sentence that comes from the payload (`geltungsbereich`, `hinweis`, cluster texts) — only delete the three static ones and collapse the fourth. Only change RadarView.tsx." |
| K42 | Build | „`src/components/referat/RadarView.tsx` — the footer renders `radar.hinweis` as one grey four-sentence paragraph, and it reads as a legal disclaimer nobody looks at. It is not decoration: it is the only place that says what the screen does NOT show (how many Anbieter and Klauseltypen are withheld under the k-threshold, why a marked case carries no company name, and that the dataset holds no names, no free text, no document text). Same information, better structure: render it as a small panel titled **„Was nicht angezeigt wird"** (a static structural label, allowed) containing the sentences of `radar.hinweis` as a `<ul>`, one sentence per `<li>`, each in the existing muted footnote style. Split the delivered string on a period followed by a space and a capital letter **or a digit** (a sentence can start with a number, e.g. „2 Klauseltypen …" — splitting on capitals alone glues it to the previous one, measured at the pixel 25 Aug), keep every character otherwise — the number of sentences varies (two of them are conditional), so never hardcode four items, never reword, never drop the trailing period. `radar.geltungsbereich` stays exactly where and as it is. Do not add an icon, a colour or a warning tone: this is a scope note, not an alert. Only change RadarView.tsx." |
| K43 | Build | „Type scale for the Referat screen ONLY — it is the one screen shown on a projector to a room (the Fallakte is a desk screen for the advisor and stays exactly as it is; do not open any file under `src/components/fallakte/`). Today `RadarView.tsx` renders almost everything at `text-xs` and `text-sm`, which is unreadable from four metres. Raise every step by one, mechanically, and change nothing else: `text-xs` → `text-sm`, `text-sm` → `text-base`, `text-base` → `text-xl` (the „Muster-Radar" heading), and the two money figures per cluster („Bereits entstanden" / „Noch abwendbar", currently `text-sm font-medium tabular-nums`) → `text-lg font-semibold tabular-nums` so the euro amounts carry the row. In `src/routes/referat.tsx` widen the page container from `max-w-4xl` to `max-w-5xl` so the longer lines do not wrap more than before. Keep every colour, token, border, bar height, spacing utility and every string exactly as it is — this is a size pass, not a redesign; the numbers, labels and sentences all stay identical. Only change RadarView.tsx and the one container class in referat.tsx." |
| K44 | Build | „View model 1.6: `Vok` gains an optional `detail?: string \| null` — a one-sentence explanation the backend sends for chips whose word alone does not carry („tragend", „Tatsache", …). In `ToneBadge.tsx` use it as the fallback for the `title` tooltip: `title={detail ?? vok.detail ?? undefined}`. Add the field to the `Vok` interface. Nothing else changes; chips without `detail` render exactly as before. Only change viewmodel.ts and ToneBadge.tsx." — **direkt committet 25 Aug** (zwei Zeilen; die erste Team-Rückfrage „was heißt tragend / Tatsache?" hat den Tooltip verlangt) |
| K45 | Build | „`src/components/fallakte/ToneBadge.tsx`: chips whose `vok.detail` is set become **clickable and open a popover** with that sentence — the same `Popover`/`PopoverTrigger`/`PopoverContent` from `@/components/ui/popover` that `AnkerPopover.tsx` already uses for statute chips, same `text-sm` content style, width `w-80`. Trigger = the chip itself (keep its look; add `cursor-pointer` and a subtle affordance: a small `Info` icon from lucide-react, `size-3`, muted, after the label). Keep the `title` attribute as well so mouse users still get the hover. Chips **without** `detail` render exactly as today: no icon, no popover, not clickable. The popover shows only the delivered `detail` string — no heading, no extra text, the UI never writes an explanation itself. Works on touch (click/tap), because the tooltip alone does not. Only change ToneBadge.tsx." |
| K46 | Build | „`ToneBadge.tsx`: the `Info` affordance is too small to be noticed — `size-3 opacity-70` → `size-4 opacity-90`. Nothing else." — **direkt committet 25 Aug** (eine Klasse; Sungho am Pixel: „zu klein") |
| K47 | Build | „Franz' Anleitung §7 — *bereits abgemahnte Klausel* (view model 1.7). **(1)** `src/types/viewmodel.ts`: add `hinweis_abmahnung?: { badge: Vok; text: string; geprueft: boolean; quelle_url: string | null } | null` to `Pruefpunkt`/`TraceEintrag`; add `wiederholung: number` to `RadarCluster` and `MarkierterFall`, `bereits_abgemahnt: boolean`, `abmahnung_kurz: string | null`, `abmahnung_geprueft: boolean | null` to `RadarKlauseltyp`, and `wiederholungen_gesamt: number` to `RadarAnsicht`. **(2)** `src/components/fallakte/Pruefpfad.tsx`, in `PruefpunktRow`'s chip line after the existing chips: when `p.hinweis_abmahnung` is set, render `<ToneBadge vok={p.hinweis_abmahnung.badge} detail={p.hinweis_abmahnung.text} />` — the K45 popover pattern, the delivered `text` is the popover content, verbatim, no heading. When `quelle_url` is set, add a plain external link „Quelle" (`text-xs`, muted, `target=_blank rel=noreferrer`) right after the chip. Nothing when the field is null/undefined. **(3)** `src/components/referat/RadarView.tsx`: in `KlauseltypZeile`, when `z.bereits_abgemahnt`, append a chip with the static label „bereits abgemahnt" in the existing gelb chip style (`chipKlasse("gelb")`) followed by `z.abmahnung_kurz` as muted `text-sm`; if `z.abmahnung_geprueft === false` append „· ungeprüft" in the same muted style. In `ClusterBar`'s meta line append ` · {cluster.wiederholung} Wiederholung(en)` only when `cluster.wiederholung > 0` (singular „1 Wiederholung"). In „Markierte Fälle" append ` · Wiederholung` (muted) when `f.wiederholung > 0`. In the header line after the Schwellen text append ` · {radar.wiederholungen_gesamt} Fälle mit bereits abgemahnter Klausel` only when > 0. Do not invent any other sentence; do not colour anything from a code; do not touch the store, api.ts or fixtures. Only change viewmodel.ts, Pruefpfad.tsx, RadarView.tsx." — **direkt committet 25 Aug** (llt26-ui `af8c94b`, Pixel `28_belege/k47_abmahnung_popover.png`) |
| K48 | Build | „Anleitung §6 — Hauptgrafik. `src/components/referat/RadarView.tsx`: above the „Klauseltypen" list add a recharts `ScatterChart` (recharts is already in package.json) over `radar.klauseltypen`: x = `verbreitung` (axis label „Verbreitung (Verwender)"), y = `schaden_drohend_median` (axis label „Median noch abwendbar (€)", tick formatter de-DE currency), each point labelled with `titel` (LabelList), fill colour by `quote` in three steps through the existing tone helper in `src/lib/tone.ts` — `quote >= 0.5` → gelb… no: use exactly `quote >= 0.66 → rot`, `>= 0.33 → gelb`, else `gruen`, looked up via the tone helper, never a colour literal. Rows with `schaden_drohend_median === null` are NOT plotted; count them and render „n unbeziffert" (singular „1 unbeziffert") as muted text under the chart — §5: unbeziffert is not zero. Shade the upper-right quadrant (above the median of x and the median of y of the plotted points) with a faint `bg-muted` ReferenceArea and caption it „Priorität: hohe Verbreitung, hoher Schaden". Under the chart, verbatim, one line: „Die Auswertung bildet das Beratungsaufkommen ab, nicht den Markt." Axis labels German, 16 px base, no grid lines, no animation (`isAnimationActive={false}`), height 320. If `klauseltypen` is empty render nothing for the chart. Only change RadarView.tsx." — **direkt committet 25 Aug** (llt26-ui `af8c94b`, Pixel `28_belege/k48_hauptgrafik.png`) |
| K49 | Build | „Anleitung §4/§7 — Versionierung. `src/types/viewmodel.ts`: add `prueflogik_fassungen: { fallgruppe_id: string | null; aktuell: string | null; zeilen_aktuell: number; zeilen_aelter: number; aelteste: string | null }` to `RadarAnsicht`. `src/components/referat/RadarView.tsx`: under the existing header meta line add one muted `text-sm` line: „Prüflogik {aktuell} · {zeilen_aktuell + zeilen_aelter} Fälle, davon {zeilen_aelter} mit älterer Fassung ({aelteste})" — omit the „, davon …" part when `zeilen_aelter === 0`, render nothing when `aktuell` is null. No further explanation text. Only change viewmodel.ts and RadarView.tsx." — **direkt committet 25 Aug** (llt26-ui `af8c94b`, Pixel `28_belege/k49_referat_prueflogik_wiederholung.png`) |
| K50 | Build | „Anleitung §2 — `normrang`. `src/types/viewmodel.ts`: add `normrang?: Vok | null` to `Pruefpunkt`/`TraceEintrag`. `src/components/fallakte/Pruefpfad.tsx`: in `PruefpunktRow`'s chip line render `<ToneBadge vok={p.normrang} />` after the `rolle` chip when set (it carries `detail`, so the K45 popover opens by itself). Do **not** reorder `pruefpunkte[]` — they arrive in the delivered order, which now is the Rangfolge. Only change viewmodel.ts and Pruefpfad.tsx." — **direkt committet 25 Aug** (llt26-ui `af8c94b`, Pixel `28_belege/k47_abmahnung_popover.png`) |
| K51 | Build | „R5 — `VerwendetesFeld.feld_label` (view model 1.7). `src/types/viewmodel.ts`: add `feld_label?: string | null` to `VerwendetesFeld`. `src/components/fallakte/Pruefpfad.tsx`: in the `p.verwendet` rows render `v.feld_label ?? v.feld_id` where `v.feld_id` is shown today (the muted caption). Keep `feld_id` as the React key and for the `mehrfach` duplicate check — it is the identifier, the label is the caption. Nothing else changes; do not invent a label when `feld_label` is null. Only change viewmodel.ts and Pruefpfad.tsx.“ — **direkt committet 25 Aug** (llt26-ui `6f77715`, Pixel `28_belege/k51_feld_label.png`) |
| K52 | Build | „R7 — der Prüfpfad bekommt einen Baum (view model 1.8). **(1)** `src/types/viewmodel.ts`: `export interface BaumKnoten { knoten_id: string; art: Vok; titel: string; op: Vok | null; zustand: Vok; rolle: Vok | null; gerissen: boolean; marker: Vok | null; inaktiv_durch: string | null; anzahl_pruefpunkte: number; kinder: BaumKnoten[] }` und `baum?: BaumKnoten | null` in `Pruefpfad`. **(2)** Neue Datei `src/components/fallakte/Pruefbaum.tsx`: ein eingerückter Baum in drei Ebenen, gerendert aus `baum` — Wurzelzeile (grosser Tone-Punkt über `punktKlasse(zustand.tone)`, `titel`, `zustand` als `ToneBadge`, rechts klein grau `{anzahl_pruefpunkte} Prüfpunkte`), darunter je Stufe eine Zeile (Tone-Punkt · `titel` · `op.label` klein grau · `{anzahl_pruefpunkte} Prüfpunkte`), darunter je Prüfpunkt **eine** Zeile (Tone-Punkt · `titel` · `rolle` als ToneBadge nur wenn `rolle.code === \"tragend\"`). Verbindungslinien **nur mit CSS**: linkes `border-l border-border` am Kind-Container plus ein kurzer `border-t`-Stummel je Zeile (Dateibaum-Optik) — **keine Bibliothek, kein SVG, kein Chart, keine Animation, keine Kreise-und-Pfeile**. `gerissen === true`: die Zeile bekommt einen roten linken Balken (`border-l-2` in der gelieferten Tone-Klasse) und rechts `marker.label` als ToneBadge — den Text NIE selbst schreiben. `zustand.code === \"INAKTIV\"`: Zeile `opacity-60`, und wenn `inaktiv_durch` gesetzt ist, ein `title`-Attribut `Gegenstandslos, weil: {inaktiv_durch}`. Jede Prüfpunktzeile ist ein `<button>`, das `document.getElementById(\`pp-\${knoten_id}\`)` sucht, das umgebende `<details>` öffnet (`el.closest(\"details\")?.setAttribute(\"open\", \"\")`) und `scrollIntoView({behavior: \"smooth\", block: \"center\"})` aufruft. Keine `pruefpunkt_id` je sichtbar, keine Farbe aus einem String, keine eigene Beschriftung. **(3)** `Pruefpfad.tsx` rendert `<Pruefbaum baum={pruefpfad.baum} />` ganz oben im Panel, wenn `pruefpfad.baum` gesetzt ist, sonst nichts. Mobil dieselbe Struktur, dünnere Einrückung, **keine horizontale Scrollleiste**. Only change: `types/viewmodel.ts`, neu `components/fallakte/Pruefbaum.tsx`, `components/fallakte/Pruefpfad.tsx`.“ — **direkt committet 25 Aug** (llt26-ui `6f77715`, Pixel `28_belege/k52_baum_drehkreuz.png`) |
| K53 | Build | „R7 Teil 2 — die Detailliste im Prüfpfad wird zur Zweitansicht. In `src/components/fallakte/Pruefpfad.tsx`: (a) jede Stufe rendert `<details open={s.pruefpunkte.some((p) => [\"NEIN\", \"WERTUNG\", \"FEHLT\"].includes(p.zustand.code))}>` — Stufen, in denen nichts offen oder gerissen ist, starten zu (das ersetzt K21s uniformes Zu für diese Stelle; Ableitungen bleiben zu). (b) Das `<summary>` jeder Stufe bekommt `id={\`stufe-\${s.stufe_id}\`}`, jede Prüfpunktzeile `id={\`pp-\${p.pruefpunkt_id}\`}` — das sind die Sprungziele des Baums aus K52, sie erscheinen nirgends als Text. (c) Über der Liste eine kleine graue Zeile `Details` als Überschrift, damit Baum und Liste nicht wie zwei gleichrangige Panels wirken. Nichts anderes ändern.“ — **direkt committet 25 Aug** (llt26-ui `6f77715`, Pixel `28_belege/k53_sprung_in_die_liste.png`) |
| K54 | Build | „R7 Nachbesserung (Sungho am Pixel: „alles auf einmal, zu komplex“) — die Stufen im Prüfbaum klappen zu. In `src/components/fallakte/Pruefbaum.tsx`: jede Stufenzeile wird ein Aufklapp-Knopf mit rotierendem `ChevronDown` (K17-Grammatik, nie ein natives `<details>`-Dreieck), `aria-expanded`; die Prüfpunkte darunter rendern nur, wenn offen. **Voreinstellung offen nur dort, wo die Stufe die Einordnung trägt**: `gerissen === true` oder ein Kind mit `rolle.code === \"tragend\"` und `zustand.code` in NEIN/WERTUNG/FEHLT — ergänzende Punkte (§ 315, Hinweise) klappen zu, sonst sieht der Baum aus wie die Liste, die er ersetzen soll. Eine zugeklappte Stufe zeigt zusätzlich „{n}× {zustand.label des ersten auffälligen Kindes}“ in dessen Ton — Zahl gerechnet, Wort geliefert. In der Wurzelzeile rechts ein kleiner Knopf „alle aufklappen“ / „alle zuklappen“, der alle Stufen auf einmal setzt. `Pruefpfad.tsx` bekommt dieselbe Öffnungsregel wie der Baum (statt „irgendein offener Zustand“), damit Übersicht und Liste nicht widersprechen. Only change: Pruefbaum.tsx, Pruefpfad.tsx.“ — **direkt committet 25 Aug** (llt26-ui `HEAD`, Pixel `28_belege/k54_baum_zugeklappt.png`, `k54_baum_seepark_ruhig.png`, `k54_baum_alle_auf.png`) |
| K55 | Build | „R7, zweite Nachbesserung (Sungho: „tragend hängt an fast jeder Zeile“) — im **Prüfbaum** (`Pruefbaum.tsx`) das Rollen-Abzeichen umdrehen: `knoten.rolle` wird gerendert, wenn `rolle.code !== \"tragend\"`, sonst gar nichts. Grund: elf der neunzehn Prüfpunkte sind tragend und liegen genau in den Stufen, die aufgeklappt starten — das Abzeichen stand also in fast jeder sichtbaren Zeile und unterschied nichts. Jetzt trägt nur die Ausnahme eines („Vorfrage“, „ergänzend“), und die Aussage ist die nützlichere: **dieser Punkt trägt die Einordnung nicht.** Das Wort kommt weiter aus `rolle.label`, nie aus dem UI. Die Detailliste unter dem Baum bleibt unverändert — dort steht der Chip zwischen anderen Chips und hat sein Popover. Only change: Pruefbaum.tsx.“ — **direkt committet 25 Aug** (llt26-ui `HEAD`, Pixel `28_belege/k55_baum_nur_ausnahmen.png`: 0 „tragend“, 2 „Vorfrage“, 4 „ergänzend“) |
| K56 | Build | „R7, Zeichenerklärung (view model 1.9). Folge aus K55: seit „tragend“ kein Abzeichen mehr ist, steht das Wort nirgends mehr auf dem Schirm — es wird aber im Vortrag benutzt. **(1)** `src/types/viewmodel.ts`: `legende?: Vok[]` in `Pruefpfad`. **(2)** `Pruefbaum.tsx` bekommt unter dem Baum eine Zeile „Zeichenerklärung“ — ein Aufklapp-Knopf in der bekannten Chevron-Grammatik, **zu voreingestellt**; offen rendert er `legende` als Definitionsliste: links der Chip (geliefertes Label, gelieferter Ton), rechts `detail` **verbatim**. Reihenfolge wie geliefert, kein eigener Satz, kein Zeichen, das nicht in der Liste steht. **(3)** `Pruefpfad.tsx` reicht `legende={pruefpfad.legende}` durch. Only change: viewmodel.ts, Pruefbaum.tsx, Pruefpfad.tsx.“ — **direkt committet 25 Aug** (llt26-ui `HEAD`, Pixel `28_belege/k56_zeichenerklaerung.png`: 7 Einträge, „tragend“ erklärt) |
| K57 | Build | „R7, dritte Fassung (Sungho, 25 Aug sehr spät): der Prüfpfad steht oben als **Diagramm** — Wurzel-Kasten, darunter die Stufen als Kästen mit Verbindungslinien, **nur zur Orientierung**; gearbeitet wird weiter in der Detailliste. Neue `src/components/fallakte/Pruefdiagramm.tsx`, gezeichnet mit CSS-Rahmen (keine Bibliothek, kein SVG, kein Chart). Kästen im Raster `repeat(auto-fit,minmax(175px,1fr))` — sieben nebeneinander bräuchten 1.400 px, der Prüfpfad hat 613. Je Kasten: Tone-Punkt · Titel (bis 3 Zeilen) · Kurzzeile aus gelieferten Wörtern und gerechneten Zahlen („3× nicht erfüllt“, „2× Angabe fehlt“, „6 erfüllt“, INAKTIV zeigt sein eigenes Label „nicht anwendbar“); gerissene Stufe roter Rahmen + gelieferter Chip. Hängende Blattliste nur unter Stufen mit tragendem offenem Punkt und darin nur diese Punkte — „alle aufklappen“ zeigt alle. Klick auf Kasten oder Blatt springt in die Detailzeile (`pp-`/`stufe-`) und öffnet sie. Umschalter **Diagramm | Liste** im Panelkopf, Voreinstellung Diagramm, Wahl in `localStorage` (try/catch, Ausfall = Diagramm). Zeichenerklärung (K56) bleibt darunter. Only change: neue Pruefdiagramm.tsx, Pruefpfad.tsx, Pruefbaum.tsx (Legende exportiert).“ — **direkt committet 25 Aug** (llt26-ui `HEAD`, Pixel `28_belege/k57_diagramm_*.png`) |
| K58 | Build | „Die Blätter im Prüfdiagramm werden **Norm-Pillen**: oben `norm_kurz` (Fundstelle, z. B. „§ 307 I 2“), darunter `kurzwort` (amtliche Überschrift der Norm). Die **Rolle** wird zur **Linie** statt zum Chip — Blatt-Stummel durchgezogen bei `rolle.code === \"tragend\"`, gestrichelt sonst. Pillen hängen unter **jeder** Stufe, ab fünf Pillen wird die Stufe zwei Spalten breit. Am gerissenen Punkt ein ✕ im gelieferten Ton. Höchstens ein Chip je Knoten; Zähler bleiben in den Stufen-Kurzzeilen. Reihenfolge wie geliefert. Only change: Pruefdiagramm.tsx, types/viewmodel.ts.“ — **direkt committet 25 Aug** (llt26-ui `a687ed5`, Pixel `28_belege/k58_diagramm_normen.png`, `k58_vollbild_*.png`) |
| K59 | Build | „Der Prüfpfad zeigt im Panel **nur die Liste**. Das kleine Diagramm daneben entfällt (Sungho: bringt in der Panelbreite nichts), ebenso der Umschalter Diagramm|Liste und die `localStorage`-Wahl aus K57. Statt dessen ein Knopf **„Diagramm“** (Maximize2) in der Panelkopfleiste, der `PruefdiagrammVollbild` öffnet — Esc und ✕ schließen. `Pruefdiagramm.tsx` bleibt unverändert und wird nur noch vom Vollbild gerendert. Only change: Pruefpfad.tsx.“ — **direkt committet 25 Aug** (llt26-ui `6dcadab`, Pixel `28_belege/k59_panel_nur_liste.png`) |
| K60 | Build | „**View Model 1.15 — der Anker-Chip schreibt sein Wort nicht mehr selbst.** `src/types/viewmodel.ts`: `Anker` bekommt `pruefstand: Vok` (immer gesetzt). `src/components/fallakte/AnkerPopover.tsx`: der Trigger hängt heute den **im Frontend getippten** deutschen Text „· ungeprüft" an, sobald `geprueft` false ist — das verstößt gegen Regel 1 (kein deutsches Label im Frontend) und, schlimmer, das Wort hat kein Objekt: „§ 305b BGB · ungeprüft" lässt sich als „ob es diesen Paragrafen gibt, ist ungeprüft" lesen, also als das Gegenteil dessen, was gemeint ist. **(1)** Den getippten String ersatzlos löschen und statt dessen `anker.pruefstand.label` rendern — geliefert wird „Fundstelle ungeprüft" bzw. „Fundstelle gegengelesen". **(2)** Das Label steht jetzt an **beiden** Zuständen, nicht nur am ungeprüften: es gibt genau einen gegengelesenen Anker im Bestand (LG Bamberg 13 O 730/22 an der Zustimmungsfiktion), und er ist der einzige Grund, aus dem die grauen überhaupt als Präzision statt als Pauschalzweifel lesbar sind — ohne den sichtbaren Gegenpol wirken 20 graue Chips wie „nichts hier ist belastbar". **(3)** Die Farbe kommt wie überall aus dem gelieferten `pruefstand.tone` über `src/lib/tone.ts`, **nicht** aus dem Boolean; die K31-Behandlung (blaue Norm-Chips, gestrichelter Rand und reduzierte Deckkraft am ungeprüften) und der K18-Chevron bleiben unverändert und hängen weiter an `geprueft`. **(4)** Im Popover den Satz `anker.pruefstand.detail` als Erklärzeile zeigen, wörtlich, ohne Überschrift — er sagt, was „ungeprüft" meint („Der Gesetzestext liegt vor und ist unverändert übernommen — gegengelesen am Original hat ihn niemand aus dem Team."). Erfinde keine eigene Formulierung und kürze keine der beiden: die Auftraggeberin liest diesen Chip. Only change viewmodel.ts and AnkerPopover.tsx." — **direkt committet 26 Aug** (llt26-ui `9628c93`, nicht ueber Lovable). **Eine bewusste Abweichung beim Bauen:** die Farbe des Markers kommt aus `pruefstand.tone` ueber `textKlasse()`, der **Chiprahmen** bleibt unveraendert bei K31 (blau, an `geprueft`) — Rahmen = Komponentenfarbe, Marker = gelieferter Zustand; zwei Farbachsen im selben Chip waeren Rauschen. `RadarView.tsx:193` haengt weiter „· ungeprueft" an den Abmahnungs-Chip und bleibt so: dort steht das Objekt im Satz daneben (Gericht, Az., Datum), die Zweideutigkeit entsteht nicht, und Franz erklaert den Chip in Akt 2 B7 laut. tsc sauber, Build gruen, Lint unveraendert (19 vorbestehende Fehler). ⚠️ **Am selben Tag zur Hälfte überholt (Sungho, llt26-ui `6efb7f1`): der Chiptext ist wieder raus.** Gemessen wurde, was den Ausschlag gab — auf Schritt 4 trug **fast jeder** Anker-Chip dasselbe Wort, und ein Wort, das fast überall steht, unterscheidet nichts mehr; ⚠️ **die genaue Zahl ist strittig und darf so lange nicht auf eine Folie:** llt26-b5 zählte am laufenden Programm erst 20 Chips (19 mit Wort), nach einer korrigierten DOM-Zählung 17 (16 mit Wort); eine unabhängige Zählung im **Fixture** (`drehkreuz_fallakte.json`, Anker auf Prüfpfad-Zeilen ohne `inaktiv_grund`) ergibt **20 Instanzen, 19 verschiedene Fundstellen, genau eine `geprueft`** — also weder 17 noch 16. Woher die Differenz kommt, ist offen (vermutlich Fixture gegen frisch angelegten Fall). Unstrittig und für die Entscheidung ausreichend: **genau ein Anker im Bestand ist gegengelesen, alle übrigen nicht** — das ist der Befund, der das Wort überflüssig machte; es drängt die Norm an den Rand, und die soll die Beraterin lesen. Der Nachsatz „auch der grüne", den `6efb7f1` zunächst nur mitnahm, ohne ihn zu begründen, ist auf Nachfrage **ausdrücklich bestätigt** worden — Grund: zu viel Text auf der UI. Damit gilt hier nicht K55 („die Ausnahme spricht"), sondern eine eigene Regel: **der Chip trägt nur die Fundstelle.** Dieselbe Linie unmittelbar danach auch bei der „Weg:"-Zeile (`4326d30`). **Was von K60 steht und bleibt:** `Anker.pruefstand`, das Enum `Ankerpruefstand`, View Model 1.15 und der ganze Popover-Block — der Prüfstand ist nicht weg, er steht im Popover statt im Chip, und der Rahmen (gestrichelt/durchgezogen) trägt ihn weiter auf dem Schirm. ⚠️ **Bekannte Schwäche, offen:** für die Anker-Chips gibt es **keine Zeichenerklärung** (K55/K56 haben die für den *Baum* gebaut) — wer die Legende nicht kennt, liest den gestrichelten Rahmen nicht. Bühnenfolge deshalb angepasst: nicht mehr auf die Chips zeigen, sondern einen **aufklicken** (`33` §2, llt26 `866fb6a`). **Pixelbeleg auf dem Stand nach `6efb7f1`/`4326d30`** (1440×900, frischer Fall, kein Demo-Badge): `analysis/28_belege/k60a_ankerchip_ohne_wort.png` (die Chipreihe ohne Wort, gestrichelt vs. durchgezogen nebeneinander) · `k60a_popover_geprueft.png` · `k60a_popover_ungeprueft.png`. Die `k60_*`-Serie von `9628c93` zeigt den abgelösten Stand und bleibt als solcher stehen |
| K26 | Build | „`src/components/referat/RadarView.tsx` + `src/types/viewmodel.ts` — the radar payload changed shape and now delivers what the screen was missing. `cluster[].einordnungen` is now an **ordered list** `Array<{text: string; anzahl: number; tone: Tone}>` — colour each bar segment and each count entry by the delivered `tone` through the existing helper in `src/lib/tone.ts` (the grey-bars workaround from K1 is obsolete: the backend now says the colour). `cluster[].pruefpunkte_nein` is now `Array<{titel: string; anzahl: number}>` — render „Nicht erfüllte Prüfpunkte: Symmetrie- und Kostenweitergabegebot (2), …" from the delivered titles; no P-ids exist in the payload anymore. And format `betrag_median` German: `(4.75).toLocaleString(\"de-DE\", {style: \"currency\", currency: \"EUR\"})` → „4,75 €" — the current raw `4.75 €` is the wrong decimal separator for a German Fachanwendung. Update the two types, change nothing else." |
| K24 | Build | „`src/components/fallakte/FallakteHeader.tsx` — the „Zuordnungsvorschläge (2) · bestätigt" line is a native `<details>` summary with the browser triangle: small, muted, and the only disclosure in the app that does not speak the established grammar. Convert it to the K17 pattern: a small **outline Button** labelled „Zuordnungsvorschläge (2) · bestätigt" (keep both the count and the bestätigt/nicht-bestätigt note as they are) with a `ChevronDown` that rotates 180° on open, toggling via `useState`; the proposal list below renders conditionally, content unchanged. **And one sentence for the record, applying everywhere:** every disclosure control in this app uses the chevron grammar (rotating ChevronDown, button-like trigger) — native `<details>` markers are never used. Only change FallakteHeader.tsx." |
| K23 | Build | „Two removals in `src/components/fallakte/FallakteHeader.tsx`. **(1)** Delete the „Referat" link — the root navigation already carries Fallakte/Referat on every page, and a second one inside the case header is duplication. **(2)** Render the „Fallgruppe bestätigen" button **only when `kopf.fallgruppe_bestaetigt` is false**; when true render nothing in its place — no disabled button, no caption: the „· bestätigt" note in the Zuordnungsvorschläge summary line directly below already says it. Same pattern as the Gate-3 button: an action control exists while the action is pending, not as a permanent fixture. Change nothing else in the file." |
| K22 | Build | „Rebuild `src/components/fallakte/ProtokollPanel.tsx` as the **table** P14 specified — the generation built stacked chip rows instead, and the grey chips read as buttons (chips are this UI's disclosure grammar now) while a log entry is not clickable. Four columns exactly: Zeit (short, `dd.MM. HH:mm`) · Schritt (`schritt.label`, plain muted text, em-dash when null) · Ereignis (`aktion.label`, plain text) · Beschreibung (plain text, `[overflow-wrap:anywhere]` so long technical strings like template ids wrap inside the cell instead of widening the table; the table itself sits in an `overflow-x-auto` container). No chips anywhere in the table. Rows whose `aktion.tone === \"gelb\"` get a subtle left border accent in the delivered tone — that is the one colour use. Above the table: a small filter toggle „nur auffällige Zeilen" (shows only the gelb rows) and a „Kopieren" button that copies the table as plain text lines (Zeit⇥Schritt⇥Ereignis⇥Beschreibung). Below: „Gesamt: N". Keep the collapsed-by-default behaviour of the panel with the same chevron-button grammar as K17. The `akteur` column stays out of the table per P14 — it is always the role and would repeat „Beraterin" on every row. Only change ProtokollPanel.tsx." |
| K21 | Build | „In `src/components/fallakte/Pruefpfad.tsx` remove the `open={s.stufe_id === pruefpfad.gerissene_stufe}` default so **every** Stufe group starts collapsed — a deliberate revision of P5: with the step rail the advisor clicks into the Prüfpfad step actively, and a uniform closed state reads calmer than one pre-opened group among closed ones. The gerissene Stufe keeps everything that marks it (the red chip on its row, the „gerissen bei …" note in the panel header) — only the auto-open goes. Change nothing else." |
| K20 | Build | „The Gate-3/Referat chain is dead end to end — three connected fixes. **(1) HeroCard gets the missing Gate-3 button**: „Einordnung bestätigen" next to the verdict, POSTing `{von: \"Beraterin\"}` to `/faelle/{id}/gate3` (new function in api.ts), then refetch. The current run's `gate3_bestaetigt`/`gate3_gueltig` come in `laeufe[]` (the entry with `aktuell: true`): when confirmed and still valid, render the button disabled with the static caption „Einordnung bestätigt" beside it. This button is what makes a case count on the Radar — without it the „+1" beat cannot be triggered from the screen at all. **(2) ReferatPanel becomes writable per P8**: the checkboxes are currently `readOnly` mirrors — make them local draft state initialised from the delivered `angehakt`, add a textarea for `notiz` initialised from `referat.notiz`, and the „Für Referat markieren" button POSTs `{kriterien: [checked ids], notiz}` — right now it sends no payload at all, so the backend has nothing to mark. „Markierung aufheben" posts `{kriterien: [], notiz}`. On a 4xx show the German `detail` (the backend answers 409 with a sentence when Gate 3 has not happened yet — show it, do not swallow it). **(3) Wire both through api.ts** with the same error pattern as leitfadenSenden. Only change HeroCard.tsx, ReferatPanel.tsx, api.ts and the wiring in faelle.$id.tsx." |
| K19 | Build | „`src/components/fallakte/Pruefpfad.tsx` — the Stufe rows are `<details>` elements, but the summary's flex styling removed the browser's disclosure triangle, so they read as static cards; nothing says the Prüfpunkte with their quotes and norm cards are inside. Same grammar as the anchor chips: add a `ChevronDown` (size-4, muted) at the right end of each Stufe summary row, rotating 180° when the group is open — `<details>` has no data-state, so key the rotation on the `details[open]` selector (`group-open:rotate-180` with `group` on the details element). Apply the same chevron to the „Ableitungen" summary and remove its native marker (`list-none`) so all disclosure rows in the panel speak one language. Keep the default-open behaviour of the `gerissene_stufe` group and everything else unchanged. Only change Pruefpfad.tsx." |
| K18 | Build | „Two small affordance fixes. **(1) `src/components/fallakte/AnkerPopover.tsx`** — the anchor chip („§ 286 BGB · ungeprüft") opens a popover with the norm text, but nothing says so: it looks identical to the non-clickable ToneBadge chips, and users only discover the popover by accident. Add a small `ChevronDown` (size-3, muted) inside the trigger chip after the label, for both the geprueft and ungeprüft variants, rotating 180° while the popover is open (Radix sets `data-state=\"open\"` on the trigger — key the rotation on that). Keep the dashed/muted ungeprüft styling exactly as it is. **(2) `src/components/fallakte/LeitfadenPanel.tsx`** — the select for a `werte` field uses `placeholder={feldId}`, so until a value is chosen the raw field id `gespraech.strategie` stands on screen. Replace the placeholder with the static label „Bitte wählen" (a structural caption, like a panel title). Change nothing else in either file." |
| P20 | Build | „The answering half of P15, still missing from `src/components/fallakte/LeitfadenPanel.tsx` — the panel is read-only while the backend endpoint is live and tested. Per **open** question render an input under the question text, chosen per field in `fuellt`: if the field appears in `werte`, a select over exactly those values; otherwise by the question's `typ` — `ja_nein` two outline buttons Ja/Nein (a `mehrfach` question's field without `werte` is also Ja/Nein), `zahl` a number input, `text` a single-line input. A question with several fields in `fuellt` gets one input per field (P13 fills a select AND a Ja/Nein). Inputs are local draft state; nothing fires per keystroke. One button under the list — „Antworten übernehmen", disabled while no input is filled — POSTs ALL filled answers in ONE request to `/faelle/{id}/leitfaden` as `{antworten: {feld_id: wert}, von: \"Beraterin\"}`; numbers as numbers, Ja/Nein as booleans. **The batch is atomic**: a 400 means nothing was written — show the German `detail` from the response body and keep the drafts; on success clear the drafts and refetch (the verdict can change, `laeufe[]` gets a new entry, and answered questions move out of the open list by themselves). In fixture mode the button is a no-op with the demo toast like every action. Only change LeitfadenPanel.tsx and the one call in api.ts plus its wiring in faelle.$id.tsx." |
| K17 | Build | „Three fixes in `src/components/fallakte/LeitfadenPanel.tsx`. **(1) The disclosure button is dead**: the `<Button>` sits inside a `<summary>`, and an interactive element inside a summary swallows the click, so the `<details>` never toggles. Replace the details/summary with a `useState` toggle — the Button itself flips the state, the non-open list renders conditionally below it, chevron rotates with the state. **(2) Delete the `füllt: …` output.** P15 is explicit: `fuellt` is keyed on, never rendered — `gespraech.zustimmung_aktiv_belegt` is a raw field id on an advisor screen. **(3) Remove the naked `f.zustand` chip** next to the status chip: „offen" beside „nicht erfüllt" reads as a contradiction (one is the question state, the other the Prüfpunkt state, but nothing on screen says so), and P15 never asked for it. Keep the status chip, the `pruefpunkt_id · titel` reference, `text`, `grund` and `hinweis` exactly as they are. Only change LeitfadenPanel.tsx." |
| K16 | Build | „`src/components/fallakte/LeitfadenPanel.tsx` collapses ALL questions behind a plain `<details>` summary („5 Fragen anzeigen") — weak affordance, and a P15 deviation: P15 says questions with `status.code === \"offen\"` are the content and render **directly visible**, while only the non-open ones (beantwortet / steht in den Unterlagen / entfällt) appear collapsed and greyed, never hidden. Since the step layout, the panel sits inside step 2 — the advisor has already clicked her way to it, and hiding its main content behind a second click is double wrapping. Fix: render the open questions expanded, in the delivered order; below them one clearly button-styled disclosure (outline Button look, chevron) labelled „Beantwortete & entfallene anzeigen (N)" with N computed as `fragen.length` minus the delivered `offen` count — both numbers are delivered, do not count states yourself beyond that subtraction. Inside, the non-open questions render as they do today (greyed, with `grund`). Keep the „N offen" header chip. Only change LeitfadenPanel.tsx." |
| K15 | Build | „Two pieces of P7 that were never built in `src/components/fallakte/MusterbriefPreview.tsx` (the audit trail shows they are missing, not removed): **(1) a „Kopieren" button for the letter** — copy `musterbrief.text` to the clipboard with the same toast pattern the Nachforderung panel uses; the letter is what the advisor pastes into her own channel, and right now the only way is manual text selection inside a scrolling `<pre>`. **(2) the „nicht juristisch geprüft" marker on the letter itself** — when `musterbrief.geprueft` is false, a visible line directly at the letter block (not hidden in a details element): „Dieses Schreiben ist juristisch nicht geprüft." In every demo case `geprueft` is false, so this marker shows on every letter — that is correct and deliberate: the trust framing depends on the tool saying what has not been reviewed. Do not confuse it with `vorschlaege[].geprueft`, which is already rendered per remedy option. Only change MusterbriefPreview.tsx." |
| K14 | Build | „`src/components/fallakte/MusterbriefPreview.tsx:62-63` renders `musterbrief.template_id` and `musterbrief.variante` as visible text. **Delete the whole line, do not wrap it.** Two reasons. These are raw internal identifiers (`musterbrief_fitness_widerspruch_rueckforderung`, `preisgarantie+intransparent+keine_senkungspflicht+…`) — the same family as the raw trigger code that was just removed from the Verlauf: they mean nothing to an advisor, and P7 never asked for them (rule 8). And because they contain no break points they currently overflow the card into the step rail. The audit purpose they might serve is already covered: the Protokoll carries „Musterschreiben erzeugt" with template and variants. Keep `titel`, the `quelle`/`status` chips, `empfaenger`, the letter text, Kopieren, the geprüft marker and `vorschlaege[]` exactly as they are. Only change MusterbriefPreview.tsx." |
| K13 | Build | „In `src/components/fallakte/DokumentViewer.tsx` the viewer stacks all pages of a document and the highlight lands on the right page — but nothing scrolls it into view. A quote on page 2 or lower highlights below the fold and the user has to hunt for it, which defeats the one interaction that must be right. Fix inside the component: when `ziel` changes and a `<mark>` is rendered, scroll it into view within the left pane — `useEffect` on `ziel`, a ref on the mark (or `querySelector(\"mark\")` inside the component root), `scrollIntoView({ block: \"center\", behavior: \"smooth\" })`. When the quote is NOT found on the target page, scroll to that page's header instead so the „Zitat auf dieser Seite nicht gefunden"-notice is what becomes visible — never leave the pane where it was, and never scroll the whole window (the right column must not move; scroll only the viewer pane). Only change DokumentViewer.tsx." |
| K12 | Build | „`src/lib/api.ts` sends the Nachreichung as **multipart FormData** with binary files under a `dateien` key. The backend endpoint `POST /faelle/{id}/dokumente` takes a **JSON body** — `{anhaenge: [{dateiname: string, text: string}], nachforderung_id: string}` — a pydantic model, so multipart is answered with 422. The demo documents are plain-text/markdown files, so read each picked file with `await file.text()` and POST `Content-Type: application/json` with `{anhaenge: dateien.map(f => ({dateiname: f.name, text: inhalt}))}` plus the `nachforderung_id`. Do not send `dokumenttyp` or `quelle` — the backend classifies and defaults those itself. This is the button the flip runs on: in fixture mode it is a no-op either way, so the defect only appears against the live backend, which is exactly where it must not. Only change the upload function in api.ts." |
| K11 | Build | „`src/components/fallakte/Pruefpfad.tsx` renders the delivered `zustand` chip on **every** Stufe header. P5 has a rule this build skipped: **hide the Stufe-header chip when the group contains no Prüfpunkt with `rolle.code === \"tragend\"`**; keep it on every Stufe that has tragend children. On the open case that means S0 („Anwendungsbereich", one gate), S5 („Ausübung materiell", one ergänzend) and the „Hinweise" group (two ergänzend) currently all print „nicht anwendbar" — which reads as a legal statement about those steps, when in truth those groups are INAKTIV only because gates and ergänzende Punkte never aggregate into a Stufe result. The rows inside the groups keep their own chips unchanged; only the header chip of a no-tragend group disappears. Do not key on the stufe_id (a schema edit can move Prüfpunkte between Stufen) — key on the delivered `rolle.code` of the group's children. Only change Pruefpfad.tsx. Do NOT answer that this is already in place: at the current HEAD the summary renders `<ToneBadge vok={s.zustand} withDot />` unconditionally (line 143) and the string `tragend` does not occur anywhere in the file — verify with a search before answering, and make the change." |
| K10 | Build | „`src/components/fallakte/NachforderungenPanel.tsx` is missing the half of P13 that the demo turns on, and its one button does the wrong step. The status vocabulary is a sequence: `offen` → `angefordert` → `eingegangen`. (1) The button is labelled „als eingegangen markieren" for every status — but `eingegangen` is not something the advisor declares by clicking, it happens when documents actually arrive. Correct behaviour: when `status.code === \"offen\"`, the button says „als angefordert markieren" and POSTs `{nachforderung_id, status: \"angefordert\"}`; for any other status show no status button. (2) Add a „Kopieren" button that copies `n.text` — the letter is what the advisor pastes into her own channel. (3) Under the letter, one static line: „Das Werkzeug versendet nichts — den Text kopieren Sie selbst in Ihren Kanal." (4) **Add the „Unterlagen nachreichen" control** — per Nachforderung, a file input plus a submit that POSTs to `/faelle/{id}/dokumente` with `{nachforderung_id}` and then refetches. In fixture mode it is a no-op with the demo toast like every other action. This control is how the verdict flip is triggered live; without it the flip cannot be shown from the screen at all. Only change NachforderungenPanel.tsx and the wiring for its two new callbacks in faelle.$id.tsx and api.ts." |
| K9 | Build | „Two small fixes, found on the first real screen. (1) `src/components/fallakte/HeroCard.tsx:168` renders `ohne Nachforderung: {einordnung.label_basis}`. Delete the whole block (lines 166-170). `label_basis` is the generic base wording of the verdict category — „unklar – es fehlt …" — not „the verdict as it would stand without a Nachforderung"; the invented prefix asserts a comparison the data does not contain, and on the open case it prints the confusing line „ohne Nachforderung: unklar – es fehlt …" directly under the real verdict. (2) `src/components/fallakte/FallakteHeader.tsx:42` — the „Fallgruppe bestätigen" button is always enabled. Disable it when `kopf.fallgruppe_bestaetigt` is true (all three fixtures have it true, so today it should render disabled everywhere). Change nothing else in either file." |
| K7 | Build | „`src/types/viewmodel.ts` declares `Override` as `{wert, begruendung, akteur, zeit}`. Three of those four keys do not exist. The backend sends `{neuer_zustand: Vokabel, grund: string, von: string, zeit: string}` — the guessed names come from the first generation, before the field list was corrected. `Pruefpfad.tsx:60` reads `p.override.wert.label`, `p.override.akteur` and `p.override.begruendung`, so the line renders three `undefined`s, and `.wert.label` throws outright. Both fixtures have `override: null` everywhere, which is why nothing has broken yet — but Gate 3 („Prüfpunkt überschreiben mit Grund") is a live action in the demo, and the first override on stage hits exactly this line. Fix the interface and the three reads. Change nothing else." |
| K6 | Build | „In `src/components/fallakte/HeroCard.tsx` the „Existiert nicht" action is gated on `mitExistiertNicht && !f.fehlzustand`. Measured against both fixtures, **that gate is never open**: the engine sets `fehlzustand` on every open item, `nicht_eingereicht` by default. The action therefore renders in no case at all, and the whole point of it — never asking a consumer for a document that never existed — is unreachable from the screen. The condition is inverted: show it while the item is **not yet** `existiert_nicht`, i.e. `mitExistiertNicht && f.fehlzustand?.code !== \"existiert_nicht\"`. Second, smaller: `f.fehlzustand?.aussage` is always `undefined`, because `fehlzustand` is a `{code,label,tone}` Vokabel and carries no `aussage`; the fallback `?? f.aussage` is what actually works. Drop the first half of that expression rather than leaving a read that cannot succeed. Change nothing else." |
| K5 | Build | „In `src/components/fallakte/Pruefpfad.tsx:73` the contested-field container picks its own colour: `border-destructive/50 bg-destructive/5`. Two problems. `destructive` is shadcn's red and not this app's traffic light — `--tone-rot` already exists and `src/lib/tone.ts` hands it out, so the screen now carries two reds that do not match. And rule 2 says colour comes only from a delivered `tone`, never from the component: the colour here happens to be right (the delivered `herkunft` of both rows is `strittig`, whose tone is `rot`), but it is right by accident. Take the tone from the data — use the `herkunft.tone` of the rows in that group through the existing helper in `src/lib/tone.ts`. Then the day the backend gives `strittig` a different tone, the border follows on its own. Change nothing else in the file; the key fix `${v.feld_id}-${index}` and keeping both rows are correct and stay." |
| K4 | Plan | „Do not write code. Audit the whole `src/` against these five rules and list every violation with file and line: (1) no German label, verdict, badge or Norm name is written in the frontend — every visible string comes from the view model; (2) no colour is chosen by a component — colour comes only from a delivered `tone`; (3) no confidence, percentage, score or star rating anywhere; (4) no data is fetched in a route `loader` or a `createServerFn` — all fetching happens in the component; (5) no list key is a value that can repeat. For each violation give the file, the line and the one-sentence reason. If a rule is not violated anywhere, say so explicitly." |

## 5. Local run

The scaffold uses **bun** (`bun.lock`, `bunfig.toml`), not npm — mixing the two produces a second
lockfile that Lovable then fights with on its next build.

```bash
cd ~/dev/llt26-ui && bun install
echo 'VITE_API_BASE_URL=http://localhost:8000' > .env.local   # omit the file → fixture mode
bun run dev            # port: read it off the line the dev server prints
```

Backend, in the other repo:

```bash
cd ~/dev/llt26 && .venv/bin/uvicorn fallpruefer.api:app --reload --port 8000
```

CORS is open for **any** `localhost`/`127.0.0.1` port and for `*.lovable.app`
(`allow_origin_regex` in `fallpruefer/api.py`), so whichever port the dev server picks works
without touching the backend.
The Lovable-hosted preview is **fixture-only** — an HTTPS preview page reaching `localhost:8000`
is blocked or prompted depending on the browser; do not design around it. Demo day = `bun run dev`
locally against the local backend.

Sync discipline, same as the backend repo: `git pull` before editing `llt26-ui` locally,
`git push` before the next Lovable prompt, never push while a Lovable build is running.
