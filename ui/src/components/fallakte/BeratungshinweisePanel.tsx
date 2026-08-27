import type { Beratungshinweis } from "@/types/viewmodel";

import { AnkerListe } from "./AnkerPopover";
import { FachpruefungListe } from "./FachpruefungBlock";
import { Panel } from "./Panel";
import { ToneBadge } from "./ToneBadge";

export function BeratungshinweisePanel({ hinweise }: { hinweise: Beratungshinweis[] }) {
  if (hinweise.length === 0) return null;

  return (
    <Panel id="beratungshinweise" titel="Beratungshinweise">
      <ul className="space-y-4">
        {hinweise.map((h, i) => (
          <li key={`${h.id}-${i}`} className="rounded border border-border px-3 py-2">
            <div className="flex flex-wrap items-center gap-2">
              <ToneBadge vok={h.art} withDot />
              <h3 className="text-sm font-medium">{h.titel}</h3>
            </div>
            <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed">{h.text}</p>

            <AnkerListe anker={h.anker} />

            {h.geprueft_von.length > 0 ? (
              <FachpruefungListe eintraege={h.geprueft_von} />
            ) : null}
          </li>
        ))}
      </ul>
    </Panel>
  );
}
