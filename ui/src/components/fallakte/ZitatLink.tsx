import { ArrowLeft, FileSearch, Quote } from "lucide-react";

import { useViewer } from "./viewer-context";
import type { Zitat } from "@/types/viewmodel";

export function ZitatLink({ zitat }: { zitat: Zitat }) {
  const { zeigeZitat } = useViewer();
  return (
    <button
      type="button"
      title="Im Dokument zeigen"
      onClick={() => zeigeZitat(zitat)}
      className="group inline-flex max-w-full items-start gap-1.5 rounded border border-border bg-muted px-2 py-0.5 text-left text-sm text-foreground hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
    >
      <ArrowLeft className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
      <Quote className="mt-0.5 size-3 shrink-0 text-muted-foreground" aria-hidden />
      <span className="flex flex-wrap items-baseline gap-1">
        <span>„{zitat.zitat}"</span>
        <FileSearch
          className="mt-0.5 inline size-3 shrink-0 align-text-bottom text-muted-foreground"
          aria-hidden
        />
        <span className="whitespace-nowrap text-sm text-muted-foreground">
          ({zitat.dok_id}, S. {zitat.seite})
        </span>
      </span>
    </button>
  );
}

export function ZitatListe({ zitate }: { zitate: Zitat[] }) {
  if (zitate.length === 0) return null;
  return (
    <ul className="mt-2 space-y-1">
      {zitate.map((z, i) => (
        <li key={`${z.dok_id}-${z.seite}-${i}`}>
          <ZitatLink zitat={z} />
        </li>
      ))}
    </ul>
  );
}
