import { punktKlasse, zeitFormat } from "@/lib/tone";
import { cn } from "@/lib/utils";
import type { Lauf } from "@/types/viewmodel";

import { Panel, LeerHinweis } from "./Panel";

export function LaeufeTimeline({ laeufe }: { laeufe: Lauf[] }) {
  return (
    <Panel id="laeufe" titel="Verlauf der Einordnung">
      {laeufe.length === 0 ? (
        <LeerHinweis>Noch kein Prüflauf.</LeerHinweis>
      ) : (
        <ol className="space-y-2">
          {laeufe.map((l) => (
            <li
              key={l.run_id}
              className={cn(
                "flex flex-wrap items-start gap-2 rounded border px-3 py-2",
                l.aktuell ? "border-border bg-muted" : "border-transparent",
              )}
            >
              <span
                className={cn(
                  "mt-1.5 size-2.5 shrink-0 rounded-full",
                  punktKlasse(l.einordnung_tone),
                )}
                aria-hidden
              />
              <div className="min-w-0">
                <p className={cn("text-sm", l.aktuell ? "font-medium" : "text-muted-foreground")}>
                  {l.einordnung}
                </p>
                <p className="text-sm text-muted-foreground">
                  {l.trigger.label} · {zeitFormat(l.zeit)}
                  {l.gerissene_stufe
                    ? ` · gerissen bei ${l.gerissene_stufe_titel ?? l.gerissene_stufe}`
                    : ""}
                  {l.aktuell ? " · aktueller Lauf" : ""}
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}
