import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";
import { chipKlasse, punktKlasse, randKlasse, textKlasse } from "@/lib/tone";
import type { BaumKnoten, Vok } from "@/types/viewmodel";

/**
 * R7 — der Prüfpfad als Baum (Luis, 25 Aug: „viel zu detailliert").
 *
 * Eingerückt mit CSS-Rahmen wie ein Dateibaum: keine Bibliothek, kein SVG,
 * keine Animation. Der Baum bewertet nichts — jeder Punkt, jedes Wort und
 * jede Farbe kommt aus dem View Model; das UI schreibt hier keinen Satz.
 */
/**
 * Im Baum steht ein Chip **ohne** Popover: die Zeile ist selbst ein Knopf
 * (Sprung in die Detailliste), und ein Popover-Trigger darin wäre ein Knopf
 * im Knopf — ungültiges HTML, das React als Hydration-Fehler meldet. Die
 * Erklärungssätze stehen unverändert an derselben Vokabel in der Detailliste.
 * Label und Farbe kommen geliefert; das UI schreibt hier nichts.
 */
function Chip({ vok }: { vok: Vok }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-2 py-0.5 text-sm leading-5",
        chipKlasse(vok.tone),
      )}
    >
      {vok.label}
    </span>
  );
}

function springe(knotenId: string) {
  const ziel = document.getElementById(`pp-${knotenId}`);
  if (!ziel) return;
  ziel.closest("details")?.setAttribute("open", "");
  ziel.scrollIntoView({ behavior: "smooth", block: "center" });
}

function Punkt({ knoten }: { knoten: BaumKnoten }) {
  const inaktiv = knoten.zustand.code === "INAKTIV";
  return (
    <li className="relative pl-4 before:absolute before:left-0 before:top-3.5 before:h-px before:w-3 before:bg-border">
      <button
        type="button"
        onClick={() => springe(knoten.knoten_id)}
        title={
          inaktiv && knoten.inaktiv_durch
            ? `Gegenstandslos, weil: ${knoten.inaktiv_durch}`
            : undefined
        }
        className={cn(
          "flex w-full flex-wrap items-center gap-2 rounded py-1 pl-2 pr-1 text-left hover:bg-muted/60",
          knoten.gerissen && cn("border-l-2", randKlasse(knoten.zustand.tone)),
          inaktiv && "opacity-60",
        )}
      >
        <span
          className={cn("size-2 shrink-0 rounded-full", punktKlasse(knoten.zustand.tone))}
          aria-hidden
        />
        <span className="text-sm">{knoten.titel}</span>
        {/*
          Umgekehrt zur ersten Fassung (Sungho, 25 Aug): elf der neunzehn Punkte
          sind „tragend", und sie liegen alle in den Stufen, die man aufklappt —
          das Abzeichen stand also fast in jeder sichtbaren Zeile und
          unterschied nichts. Jetzt trägt nur die **Ausnahme** ein Abzeichen:
          ein Punkt, der die Einordnung NICHT trägt (Vorfrage, ergänzend). Das
          Wort kommt wie immer geliefert, nicht von hier.
        */}
        {knoten.rolle && knoten.rolle.code !== "tragend" ? <Chip vok={knoten.rolle} /> : null}
        {knoten.marker ? <Chip vok={knoten.marker} /> : null}
      </button>
    </li>
  );
}

/**
 * Eine Stufe klappt zu. Voreinstellung ist **zu**, außer die Stufe trägt etwas,
 * worüber jemand reden muss (gerissen, oder ein Punkt steht auf NEIN/WERTUNG/
 * FEHLT) — dieselbe Regel wie die Detailliste darunter. Sonst zeigt der Baum
 * siebzehn Zeilen auf einmal und ist wieder das, was er ersetzen sollte.
 * Aufklapp-Grammatik wie überall in dieser Anwendung: Knopf mit rotierendem
 * ChevronDown, nie ein natives `<details>`-Dreieck.
 */
const OFFEN_ZUSTAENDE = ["NEIN", "WERTUNG", "FEHLT"];

/**
 * Aufgeklappt startet eine Stufe nur, wenn sie die Einordnung trägt: gerissen,
 * oder ein **tragender** Punkt steht auf NEIN/WERTUNG/FEHLT. Ergänzende Punkte
 * (S5 § 315, S6 Hinweise) stehen fast immer offen — sie mit aufzuklappen war
 * die zweite Fassung dieses Baums, und sie sah aus wie die erste.
 */
function traegtEtwas(k: BaumKnoten) {
  return OFFEN_ZUSTAENDE.includes(k.zustand.code) && k.rolle?.code === "tragend";
}

function stufeIstOffen(knoten: BaumKnoten) {
  return knoten.gerissen || knoten.kinder.some(traegtEtwas);
}

function Stufe({ knoten, alleOffen }: { knoten: BaumKnoten; alleOffen: boolean | null }) {
  const soll = stufeIstOffen(knoten);
  const [selbst, setSelbst] = useState(soll);
  // `alleOffen` ist ein **Anstoß**, kein Dauerzustand: der Knopf oben setzt
  // jede Stufe einmal, danach entscheidet sie wieder selbst. Vorher gewann
  // `alleOffen ?? selbst` für immer, und nach einem Druck war jeder einzelne
  // Schalter bis zum Neuladen tot (Befund aus der Publish-Prüfung, `35`) —
  // genau der Rückfall, den das Regiebuch für „Stufe 5 per Klick" braucht.
  useEffect(() => {
    if (alleOffen !== null) setSelbst(alleOffen);
  }, [alleOffen]);
  // Der Jurist-Edit (Akt 2, Regiebuch B3) ändert den Baum unter der laufenden
  // Anzeige: eine Stufe reißt neu. `useState` wertet aber nur beim Montieren
  // aus, und die Schlüssel der Stufen ändern sich dabei nicht — die neu
  // gerissene Stufe blieb deshalb zu, genau im „nie streichen"-Beat (Befund
  // aus der Publish-Prüfung, `35` §2). Nachgezogen wird nur, wenn sich das
  // *Urteil über die Stufe* umdreht: ein Handgriff der Beraterin bleibt sonst
  // stehen, denn jeder Neuabruf liefert neue Objekte bei gleicher Aussage.
  const vorherSoll = useRef(soll);
  useEffect(() => {
    if (vorherSoll.current !== soll) {
      vorherSoll.current = soll;
      setSelbst(soll);
    }
  }, [soll]);
  const offen = selbst;
  const inaktiv = knoten.zustand.code === "INAKTIV";
  // Was die zugeklappte Zeile verschweigt, steht als Zahl daneben — mit dem
  // gelieferten Wort des Zustands, nicht mit einem eigenen.
  // Gezählt wird die Gruppe, deren Wort danebensteht — nicht alle Auffälligen
  // zusammen. Vorher rendete eine Stufe mit 1× „Bewertung nötig" und 2×
  // „Angabe fehlt" den Satz „3× Bewertung nötig" (Befund aus der
  // Publish-Prüfung, `35`); die Zahl war richtig und die Aussage falsch.
  const gruppe = ["NEIN", "FEHLT", "WERTUNG"]
    .map((code) => knoten.kinder.filter((k) => traegtEtwas(k) && k.zustand.code === code))
    .find((g) => g.length > 0);
  const erstes = gruppe?.[0];
  const zusammenfassung =
    !offen && gruppe && erstes ? `${gruppe.length}× ${erstes.zustand.label}` : null;

  return (
    <li className="relative pl-4 before:absolute before:left-0 before:top-3.5 before:h-px before:w-3 before:bg-border">
      <div
        title={
          inaktiv && knoten.inaktiv_durch
            ? `Gegenstandslos, weil: ${knoten.inaktiv_durch}`
            : undefined
        }
        className={cn(
          "flex flex-wrap items-center gap-2 py-1 pl-2",
          knoten.gerissen && cn("border-l-2", randKlasse(knoten.zustand.tone)),
          inaktiv && "opacity-60",
        )}
      >
        <button
          type="button"
          onClick={() => setSelbst((v) => !v)}
          aria-expanded={offen}
          className="flex flex-wrap items-center gap-2 rounded px-1 text-left hover:bg-muted/60"
        >
          <ChevronDown
            className={cn(
              "size-4 shrink-0 text-muted-foreground transition-transform duration-150",
              offen && "rotate-180",
            )}
            aria-hidden
          />
          <span
            className={cn("size-2.5 shrink-0 rounded-full", punktKlasse(knoten.zustand.tone))}
            aria-hidden
          />
          <span className="text-sm font-medium">{knoten.titel}</span>
          {/* „alle müssen halten" steht nur an der Wurzel (Team-Rückmeldung 26 Aug):
              an jeder der sieben Stufen wiederholt war es Rauschen, an der Wurzel
              ist es die Aussage über den ganzen Baum. */}
          <span className="text-sm text-muted-foreground">
            {knoten.anzahl_pruefpunkte}{" "}
            {knoten.anzahl_pruefpunkte === 1 ? "Prüfpunkt" : "Prüfpunkte"}
          </span>
          {zusammenfassung && erstes ? (
            <span className={cn("text-sm", textKlasse(erstes.zustand.tone))}>
              {zusammenfassung}
            </span>
          ) : null}
        </button>
        {knoten.marker ? <Chip vok={knoten.marker} /> : null}
      </div>
      {offen && knoten.kinder.length > 0 ? (
        <ul className="ml-2 border-l border-border">
          {knoten.kinder.map((k) => (
            <Punkt key={k.knoten_id} knoten={k} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

/**
 * Die Zeichenerklärung. Sie steht zu und nimmt eine Zeile — der Baum soll die
 * Übersicht sein, nicht ein Lehrbuch. Jeder Satz kommt aus `legende[].detail`;
 * das UI schreibt keinen, und es sortiert die Liste nicht um.
 */
export function Legende({ eintraege }: { eintraege: Vok[] }) {
  const [offen, setOffen] = useState(false);
  if (eintraege.length === 0) return null;
  return (
    <div className="mt-2 border-t border-border pt-1">
      <button
        type="button"
        onClick={() => setOffen((v) => !v)}
        aria-expanded={offen}
        className="flex items-center gap-1 rounded px-1 text-sm text-muted-foreground hover:bg-muted/60"
      >
        <ChevronDown
          className={cn(
            "size-3.5 shrink-0 transition-transform duration-150",
            offen && "rotate-180",
          )}
          aria-hidden
        />
        Zeichenerklärung
      </button>
      {offen ? (
        <dl className="mt-1 space-y-1 px-1 pb-1">
          {eintraege.map((v) => (
            <div key={v.code} className="flex flex-wrap items-baseline gap-2">
              <dt className="shrink-0">
                <Chip vok={v} />
              </dt>
              <dd className="flex-1 text-sm text-muted-foreground">{v.detail}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}

export function Pruefbaum({
  baum,
  legende = [],
}: {
  baum?: BaumKnoten | null | undefined;
  legende?: Vok[] | undefined;
}) {
  // `null` = jede Stufe entscheidet selbst (Voreinstellung); true/false = der
  // Knopf oben hat alle auf einmal gesetzt.
  const [alleOffen, setAlleOffen] = useState<boolean | null>(null);
  const [stoss, setStoss] = useState(0);
  if (!baum) return null;
  const zeigeAlles = alleOffen !== true;

  return (
    <div className="mb-4 rounded border border-border bg-card px-3 py-2">
      <div className="flex flex-wrap items-center gap-2 py-1">
        <span
          className={cn("size-3.5 shrink-0 rounded-full", punktKlasse(baum.zustand.tone))}
          aria-hidden
        />
        <span className="text-base font-semibold">{baum.titel}</span>
        <Chip vok={baum.zustand} />
        {baum.op ? <span className="text-sm text-muted-foreground">{baum.op.label}</span> : null}
        <span className="ml-auto text-sm text-muted-foreground">
          {baum.anzahl_pruefpunkte} Prüfpunkte
        </span>

        <button
          type="button"
          onClick={() => {
            setAlleOffen(zeigeAlles);
            setStoss((n) => n + 1);
          }}
          className="ml-auto rounded border border-border px-2 py-0.5 text-sm text-muted-foreground hover:bg-muted/60"
        >
          {zeigeAlles ? "alle aufklappen" : "alle zuklappen"}
        </button>
      </div>
      <ul className="ml-2 border-l border-border">
        {baum.kinder.map((k) => (
          <Stufe
            key={`${k.knoten_id}-${stoss}-${String(alleOffen)}`}
            knoten={k}
            alleOffen={alleOffen}
          />
        ))}
      </ul>
      <Legende eintraege={legende} />
    </div>
  );
}
