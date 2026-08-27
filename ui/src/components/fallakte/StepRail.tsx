import { cn } from "@/lib/utils";

export interface StepDef {
  id: number;
  name: string;
  anzahl?: number;
  einheit?: { eins: string; viele: string };
}

interface Props {
  schritte: StepDef[];
  aktiv: number;
  onWechsel: (id: number) => void;
}

/** Vertical step rail. Counts only — no tones, no aggregated status. */
export function StepRail({ schritte, aktiv, onWechsel }: Props) {
  return (
    <nav aria-label="Schritte" className="lg:sticky lg:top-4 lg:self-start">
      <ol className="flex flex-wrap gap-1 lg:flex-col lg:flex-nowrap">
        {schritte.map((s) => (
          <li key={s.id}>
            <button
              type="button"
              aria-current={s.id === aktiv ? "step" : undefined}
              onClick={() => onWechsel(s.id)}
              className={cn(
                "w-full rounded border px-3 py-2 text-left text-sm lg:min-w-[13rem]",
                s.id === aktiv
                  ? "border-border bg-muted font-medium text-foreground"
                  : "border-transparent text-muted-foreground hover:bg-muted/50",
              )}
            >
              <span className="mr-2 text-sm text-muted-foreground">{s.id}</span>
              {s.name}
              {typeof s.anzahl === "number"
                ? s.einheit
                  ? ` (${s.anzahl} ${s.anzahl === 1 ? s.einheit.eins : s.einheit.viele})`
                  : ` (${s.anzahl})`
                : ""}
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}
