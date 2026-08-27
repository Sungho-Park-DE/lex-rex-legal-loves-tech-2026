import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { X } from "lucide-react";

import type { BaumKnoten } from "@/types/viewmodel";

import { Pruefdiagramm } from "./Pruefdiagramm";

/**
 * Die Struktur allein, auf dem ganzen Schirm.
 *
 * Warum eigen und nicht einfach das Panel breiter: im Prüfpfad hat das Raster
 * drei Spalten, die sieben Stufen brechen also auf drei Zeilen um, und die
 * Verbindungsstummel der zweiten und dritten Zeile zeigen dann nach oben in die
 * Pillenliste der Zeile darüber statt auf die Wurzel. Bei voller Breite greift
 * `repeat(auto-fit, minmax(175px, 1fr))` und legt alle sieben Stufen in **eine**
 * Reihe — erst dort liest sich die Zeichnung als das, was sie ist.
 *
 * „Nichts anderes, nur die Struktur": kein Dokument, keine Schrittleiste, keine
 * Detailliste, keine Zeichenerklärung. Ein Knopf zum Schließen, sonst nichts.
 *
 * Die Größe stellt sich selbst ein: der Inhalt wird auf einer festen
 * Bühnenbreite gesetzt und danach so skaliert, dass er in beide Richtungen
 * genau hineinpasst — auf einem 1920er Beamer wird er dadurch größer, nicht
 * kleiner. Ein Klick auf eine Pille schließt das Vollbild und springt in die
 * Detailzeile dahinter (der Klick des Diagramms läuft zuerst).
 */
// Sieben Stufen belegen **acht** Rasterspalten, weil die Inhaltskontrolle mit
// ihren sechs Punkten zwei breit ist. `minmax(175px, 1fr)` mit `gap-x-3`
// braucht dafür 8·175 + 7·12 = 1484 px. Darunter bricht die Reihe (bei 1400
// nachgemessen: zwei Rasterzeilen), darüber wird nur der Maßstab kleiner —
// 1500 ist also die schmalstmögliche Bühne, auf der die Stufen in **einer**
// Reihe stehen, und genau darum geht es in dieser Ansicht.
const BUEHNENBREITE = 1500;
const RAND = 32;

export function PruefdiagrammVollbild({
  baum,
  offen,
  onSchliessen,
}: {
  baum: BaumKnoten | null | undefined;
  offen: boolean;
  onSchliessen: () => void;
}) {
  const buehne = useRef<HTMLDivElement>(null);
  const inhalt = useRef<HTMLDivElement>(null);
  const schliessen = useRef<HTMLButtonElement>(null);
  const [faktor, setFaktor] = useState(1);

  const messen = useCallback(() => {
    const b = buehne.current;
    const i = inhalt.current;
    if (!b || !i) return;
    const hoehe = i.scrollHeight;
    if (hoehe <= 0) return;
    const platzB = b.clientWidth - 2 * RAND;
    const platzH = b.clientHeight - 2 * RAND;
    setFaktor(Math.min(platzB / BUEHNENBREITE, platzH / hoehe));
  }, []);

  useLayoutEffect(() => {
    if (!offen) return;
    messen();
    // Der erste Messwert entsteht vor dem Layout der Pillen; ein zweiter Lauf
    // im nächsten Frame trifft die endgültige Höhe.
    const id = window.requestAnimationFrame(messen);
    return () => window.cancelAnimationFrame(id);
  }, [offen, messen, baum]);

  useEffect(() => {
    if (!offen) return;
    const beobachter = new ResizeObserver(messen);
    if (inhalt.current) beobachter.observe(inhalt.current);
    window.addEventListener("resize", messen);
    return () => {
      beobachter.disconnect();
      window.removeEventListener("resize", messen);
    };
  }, [offen, messen]);

  useEffect(() => {
    if (!offen) return;
    schliessen.current?.focus();
    const taste = (e: KeyboardEvent) => {
      if (e.key === "Escape") onSchliessen();
    };
    window.addEventListener("keydown", taste);
    // Der Schirm dahinter darf nicht mitscrollen, solange das Vollbild steht.
    const vorher = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", taste);
      document.body.style.overflow = vorher;
    };
  }, [offen, onSchliessen]);

  if (!offen || !baum) return null;

  return (
    <div
      ref={buehne}
      role="dialog"
      aria-modal="true"
      aria-label="Prüfstruktur, große Ansicht"
      className="fixed inset-0 z-50 overflow-hidden bg-background"
    >
      <button
        ref={schliessen}
        type="button"
        onClick={onSchliessen}
        aria-label="Große Ansicht schließen"
        className="absolute right-4 top-4 z-10 inline-flex items-center gap-1.5 rounded border border-border bg-background px-2.5 py-1 text-sm text-muted-foreground hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      >
        <X className="size-4" aria-hidden />
        Schließen
      </button>

      <div className="flex h-full w-full items-center justify-center">
        <div
          // `shrink-0`, sonst staucht der Flex-Container die Bühne auf die
          // Fensterbreite, das Raster rechnet mit 1440 statt 1500 und die
          // Stufen brechen auf zwei Zeilen — auf dem Laptop nachgemessen,
          // genau der Zustand, den diese Ansicht vermeiden soll. Erst
          // skalieren, dann passt es.
          className="shrink-0"
          // Ein Klick auf eine Stufe oder Pille springt in die Detailzeile —
          // die liegt hinter dem Vollbild, also muss es sich dabei schließen.
          onClick={(e) => {
            if ((e.target as HTMLElement).closest("button")) onSchliessen();
          }}
          style={{
            width: BUEHNENBREITE,
            transform: `scale(${faktor})`,
            transformOrigin: "center center",
          }}
        >
          <div ref={inhalt}>
            <Pruefdiagramm baum={baum} />
          </div>
        </div>
      </div>
    </div>
  );
}
