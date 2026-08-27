import { cn } from "@/lib/utils";
import { chipKlasse, punktKlasse, randKlasse, textKlasse } from "@/lib/tone";
import type { BaumKnoten, Vok } from "@/types/viewmodel";

/**
 * K57 — der Prüfpfad als gezeichneter Baum: Wurzel oben, Stufen darunter
 * nebeneinander, Verbindungslinien. **Nur zur Orientierung** — gearbeitet wird
 * weiter in der Detailliste; jeder Kasten und jedes Blatt springt dorthin.
 *
 * Gezeichnet mit CSS-Rahmen, nicht mit einer Bibliothek: ein waagerechter
 * Balken über der Stufenreihe, je ein kurzer senkrechter Stummel nach oben.
 * Kästen statt Kreise, weil der Titel hineinpassen muss.
 *
 * Alles Sichtbare kommt aus dem View Model: Farben aus `tone`, Wörter aus den
 * gelieferten Labels. Gerechnet werden hier nur Anzahlen.
 */

const RANG = ["NEIN", "FEHLT", "WERTUNG", "JA"] as const;

/**
 * Die Kurzzeile eines Kastens: „3× nicht erfüllt", „1× Angabe fehlt", „6 erfüllt".
 * Das Wort ist immer das gelieferte Label des Zustands, den es beschreibt —
 * gezählt wird, formuliert nicht. Eine Stufe ohne Prüfpunkte und eine
 * INAKTIVE Stufe zeigen ihr eigenes Zustandswort.
 */
function kurzzeile(knoten: BaumKnoten): { text: string; tone: Vok["tone"] } | null {
  if (knoten.zustand.code === "INAKTIV" || knoten.kinder.length === 0) {
    return { text: knoten.zustand.label, tone: knoten.zustand.tone };
  }
  for (const code of RANG) {
    const treffer = knoten.kinder.filter((k) => k.zustand.code === code);
    const erstes = treffer[0];
    if (!erstes) continue;
    if (code === "JA" && treffer.length === knoten.kinder.length) {
      return { text: `${treffer.length} ${erstes.zustand.label}`, tone: erstes.zustand.tone };
    }
    if (code !== "JA") {
      return { text: `${treffer.length}× ${erstes.zustand.label}`, tone: erstes.zustand.tone };
    }
  }
  return null;
}

function springe(knotenId: string) {
  const ziel =
    document.getElementById(`pp-${knotenId}`) ?? document.getElementById(`stufe-${knotenId}`);
  if (!ziel) return;
  ziel.closest("details")?.setAttribute("open", "");
  ziel.scrollIntoView({ behavior: "smooth", block: "center" });
}

/**
 * Ein Blatt ist eine **Norm-Pille**: oben die Fundstelle, unten ein Kurzwort.
 * Vier Juristen lesen „§ 308 Nr. 5", nicht einen Prüfpunkt-Titel — beide
 * Zeilen kommen fertig aus dem View Model (K58).
 *
 * Die Rolle steht als **Linie**, nicht als Chip (K55 bleibt): durchgezogener
 * Stummel = trägt die Einordnung, gestrichelt = ergänzender Hinweis. Damit
 * trägt die Zeichnung die Logik und der Text bleibt kurz.
 */
function NormPille({ knoten }: { knoten: BaumKnoten }) {
  const tragend = knoten.rolle?.code === "tragend";
  return (
    <li
      className={cn(
        // Die Wirbelsäule sitzt an der **Pille**, nicht am `ul`. Bei einer
        // zweispaltigen Stufe stand sie vorher nur ganz links, und die Stummel
        // der rechten Spalte hingen im Nichts (Befund `35`, Nachtrag).
        "relative border-l border-foreground/40 pl-3",
        "before:absolute before:left-0 before:top-4 before:w-2.5 before:border-t",
        tragend
          ? "before:border-solid before:border-foreground/40"
          : "before:border-dashed before:border-foreground/40",
      )}
    >
      <button
        type="button"
        onClick={() => springe(knoten.knoten_id)}
        title={knoten.titel}
        className={cn(
          "flex w-full items-start gap-1.5 rounded border bg-background px-1.5 py-1 text-left hover:bg-muted/60",
          knoten.gerissen
            ? cn("border-2", randKlasse(knoten.zustand.tone))
            : "border-foreground/25",
        )}
      >
        <span
          className={cn("mt-1.5 size-2 shrink-0 rounded-full", punktKlasse(knoten.zustand.tone))}
          aria-hidden
        />
        <span className="min-w-0">
          <span
            lang="de"
            className="block hyphens-auto break-words text-sm font-medium leading-tight"
          >
            {knoten.norm_kurz ?? knoten.kurzwort}
          </span>
          {knoten.norm_kurz ? (
            <span
              lang="de"
              className="block hyphens-auto break-words text-sm leading-tight text-muted-foreground"
            >
              {knoten.kurzwort}
            </span>
          ) : null}
        </span>
        {knoten.gerissen ? (
          <span
            className={cn(
              "ml-auto shrink-0 text-sm font-semibold",
              textKlasse(knoten.zustand.tone),
            )}
            aria-hidden
          >
            ✕
          </span>
        ) : null}
      </button>
    </li>
  );
}

/** Ab fünf Pillen wird die Stufe zwei Spalten breit — sonst wächst das
 *  Diagramm über eine Bildschirmhöhe hinaus, und dann ist es keine Übersicht. */
const BREIT_AB = 5;

function StufenKasten({ knoten }: { knoten: BaumKnoten }) {
  const breit = knoten.kinder.length >= BREIT_AB;
  // Die hängende Liste zeigt normalerweise nur, worüber jemand reden muss —
  // die Punkte, die die Einordnung tragen und offen oder gerissen sind. Alle
  // sechs Punkte einer Stufe untereinander wären wieder die Liste, die das
  // Diagramm ersetzen soll. „alle aufklappen" zeigt sie trotzdem.
  // K58 (2): die Pillen sind kurz genug — sie hängen jetzt unter **jeder**
  // Stufe. Damit zeigt das Diagramm die vollständige Prüflogik, was es soll.
  const blaetter = knoten.kinder;
  const kurz = kurzzeile(knoten);
  const inaktiv = knoten.zustand.code === "INAKTIV";
  return (
    <li
      className={cn(
        // Jede Rasterzeile trägt ihren **eigenen** Balken (`before`, waagerecht
        // über die ganze Zelle) und daran den Stummel zum Kasten (`after`).
        // Vorher gab es nur einen Balken ganz oben am `ul` und an jedem Kasten
        // einen Stummel nach oben — in der zweiten und dritten Rasterzeile
        // zeigte der ins Leere bzw. in die Pillenliste der Zeile darüber, und
        // Stufe 3 las sich als Kind von Stufe 1 (Befund `35`, Nachtrag).
        "relative flex flex-col",
        // Die 6 px über die Zelle hinaus überbrücken `gap-x-3` — sonst hat der
        // Balken zwischen zwei Kästen eine Lücke und sieht gestrichelt aus.
        "before:absolute before:-top-4 before:-left-1.5 before:-right-1.5 before:h-px before:bg-foreground/40",
        "after:absolute after:-top-4 after:left-1/2 after:h-4 after:w-px after:bg-foreground/40",
        breit && "sm:col-span-2",
      )}
    >
      <button
        type="button"
        onClick={() => springe(knoten.knoten_id)}
        title={
          inaktiv && knoten.inaktiv_durch
            ? `Gegenstandslos, weil: ${knoten.inaktiv_durch}`
            : knoten.titel
        }
        className={cn(
          "flex w-full flex-col gap-1 rounded border bg-card px-2 py-2 text-left hover:bg-muted/60",
          knoten.gerissen
            ? cn("border-2", randKlasse(knoten.zustand.tone))
            : "border-foreground/25",
          inaktiv && "opacity-70",
        )}
      >
        <span className="flex items-start gap-1.5">
          <span
            className={cn(
              "mt-1.5 size-2.5 shrink-0 rounded-full",
              punktKlasse(knoten.zustand.tone),
            )}
            aria-hidden
          />
          <span
            lang="de"
            className="line-clamp-3 hyphens-auto break-words text-base font-medium leading-snug"
          >
            {knoten.titel}
          </span>
        </span>
        <span className="flex flex-wrap items-center gap-1">
          {kurz ? <span className={cn("text-sm", textKlasse(kurz.tone))}>{kurz.text}</span> : null}
          {knoten.marker ? (
            <span
              className={cn(
                "inline-flex items-center rounded border px-1.5 text-sm leading-5",
                chipKlasse(knoten.marker.tone),
              )}
            >
              {knoten.marker.label}
            </span>
          ) : null}
        </span>
      </button>
      {blaetter.length > 0 ? (
        <ul
          className={cn(
            "ml-2 mt-1 pl-1.5",
            breit ? "grid grid-cols-2 gap-x-3 gap-y-0.5" : "space-y-0.5",
          )}
        >
          {blaetter.map((k) => (
            <NormPille key={k.knoten_id} knoten={k} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export function Pruefdiagramm({ baum }: { baum: BaumKnoten }) {
  return (
    <div className="mb-3">
      <div>
        <div className="flex justify-center">
          <div className="relative flex max-w-[420px] flex-col gap-1 rounded border border-foreground/25 bg-card px-3 py-2 after:absolute after:-bottom-3 after:left-1/2 after:h-3 after:w-px after:bg-foreground/40">
            <span className="flex items-center gap-2">
              <span
                className={cn("size-3.5 shrink-0 rounded-full", punktKlasse(baum.zustand.tone))}
                aria-hidden
              />
              <span className="text-lg font-semibold">{baum.titel}</span>
              <span
                className={cn(
                  "inline-flex items-center rounded border px-2 py-0.5 text-sm leading-5",
                  chipKlasse(baum.zustand.tone),
                )}
              >
                {baum.zustand.label}
              </span>
            </span>
            <span className="flex items-center gap-2 text-sm text-muted-foreground">
              {baum.op ? <span>{baum.op.label}</span> : null}
              <span>{baum.anzahl_pruefpunkte} Prüfpunkte</span>
            </span>
          </div>
        </div>

        {/*
          Sieben Kästen nebeneinander bräuchten 1.400 px; der Prüfpfad hat 613.
          Also ein Raster statt einer Reihe: gleich hohe Zeilen, keine Lücken,
          nichts, was man wegscrollen muss — die Übersicht muss in einem Blick
          liegen, sonst ist sie keine. Der waagerechte Balken oben und die
          Stummel an jedem Kasten halten die Baum-Lesart.
        */}
        <ul className="mt-4 grid items-start gap-x-3 gap-y-8 pt-4 [grid-template-columns:repeat(auto-fit,minmax(175px,1fr))]">
          {baum.kinder.map((k) => (
            <StufenKasten key={k.knoten_id} knoten={k} />
          ))}
        </ul>
      </div>
    </div>
  );
}
