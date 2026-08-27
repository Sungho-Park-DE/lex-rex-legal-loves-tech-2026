import { useEffect, useRef } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import type { Dokument } from "@/types/viewmodel";

import { ToneBadge } from "./ToneBadge";

export interface ViewerZiel {
  dok_id: string;
  seite: number;
  zitat: string;
}

/**
 * Walk up from `el` to the nearest ancestor that actually scrolls vertically.
 * Used so the highlight is centred inside the viewer pane only — never the
 * whole window (the right-hand step column must not move).
 */
function naechsterScrollContainer(el: HTMLElement | null): HTMLElement | null {
  let node: HTMLElement | null = el?.parentElement ?? null;
  while (node) {
    const sty = getComputedStyle(node);
    const oy = sty.overflowY;
    const scrollable = (oy === "auto" || oy === "scroll") && node.scrollHeight > node.clientHeight;
    if (scrollable) return node;
    node = node.parentElement;
  }
  return null;
}

function zentriereImContainer(el: HTMLElement, container: HTMLElement) {
  const elRect = el.getBoundingClientRect();
  const cRect = container.getBoundingClientRect();
  const elTopRel = elRect.top - cRect.top + container.scrollTop;
  const zielTop = elTopRel - (cRect.height - elRect.height) / 2;
  container.scrollTo({ top: Math.max(0, zielTop), behavior: "smooth" });
}

function SeitenText({ text, treffer }: { text: string; treffer: string | null }) {
  if (!treffer) {
    return <p className="whitespace-pre-wrap text-sm leading-relaxed">{text}</p>;
  }
  const idx = text.indexOf(treffer);
  if (idx === -1) {
    return (
      <>
        <p
          data-zitat-fehlt
          className="mb-2 rounded border border-border bg-muted px-2 py-1 text-sm text-muted-foreground"
        >
          Zitat auf dieser Seite nicht gefunden — der Text weicht vom Zitat ab.
        </p>
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{text}</p>
      </>
    );
  }
  return (
    <p className="whitespace-pre-wrap text-sm leading-relaxed">
      {text.slice(0, idx)}
      <mark className="bg-marker text-marker-foreground ring-1 ring-marker-schwach">
        {text.slice(idx, idx + treffer.length)}
      </mark>
      {text.slice(idx + treffer.length)}
    </p>
  );
}

export function DokumentViewer({
  dokumente,
  ziel,
  onDokumentWechsel,
}: {
  dokumente: Dokument[];
  ziel: ViewerZiel | null;
  onDokumentWechsel: (dokId: string) => void;
}) {
  const aktiv = ziel?.dok_id ?? dokumente[0]?.dok_id ?? "";
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ziel) return;
    const root = rootRef.current;
    if (!root) return;
    // The tab/content for the target document may just have mounted, so wait
    // one frame for the mark (or the "not found" notice) to be in the DOM.
    const raf = requestAnimationFrame(() => {
      const mark = root.querySelector("mark");
      const zielNode = mark ?? root.querySelector("[data-zitat-fehlt]");
      if (!zielNode) return;
      const container = naechsterScrollContainer(zielNode as HTMLElement);
      if (!container) return;
      zentriereImContainer(zielNode as HTMLElement, container);
    });
    return () => cancelAnimationFrame(raf);
  }, [ziel?.dok_id, ziel?.seite, ziel?.zitat]);

  return (
    <div ref={rootRef} className="contents">
      <Tabs value={aktiv} onValueChange={onDokumentWechsel} className="gap-2">
        <p className="text-sm font-medium text-foreground">Dokumente</p>
        <TabsList className="h-auto flex-wrap justify-start">
          {dokumente.map((d) => (
            <TabsTrigger key={d.dok_id} value={d.dok_id} className="text-sm">
              {d.dok_id} · {d.dokumenttyp.label}
            </TabsTrigger>
          ))}
        </TabsList>

        {dokumente.map((d) => (
          <TabsContent key={d.dok_id} value={d.dok_id} className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">{d.dateiname}</span>
              <ToneBadge vok={d.quelle} />
              <ToneBadge vok={d.dokumenttyp} />
              <span className="text-sm text-muted-foreground">
                {d.typ_bestaetigt ? "Typ bestätigt" : "Typ nicht bestätigt"} · {d.eingegangen}
              </span>
            </div>
            {d.seiten.map((s) => (
              <article
                key={s.nr}
                className="rounded border border-border bg-card px-4 py-3"
                aria-label={`${d.dateiname}, Seite ${s.nr}`}
              >
                <p className="mb-2 text-sm text-muted-foreground">Seite {s.nr}</p>
                <SeitenText
                  text={s.text_original}
                  treffer={
                    ziel && ziel.dok_id === d.dok_id && ziel.seite === s.nr ? ziel.zitat : null
                  }
                />
              </article>
            ))}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
