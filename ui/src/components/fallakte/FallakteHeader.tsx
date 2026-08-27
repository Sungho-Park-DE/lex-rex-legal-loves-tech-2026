import { Button } from "@/components/ui/button";
import { zeitFormat } from "@/lib/tone";
import type { Kopf } from "@/types/viewmodel";

import { ToneBadge } from "./ToneBadge";

export function FallakteHeader({
  kopf,
  onBestaetigen,
}: {
  kopf: Kopf;
  onBestaetigen: () => void;
}) {
  return (
    <header className="border-b border-border bg-card">
      <div className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-base font-semibold text-foreground">
              {kopf.fallgruppe.label}
            </h1>
            <ToneBadge vok={kopf.stufe} />
            <ToneBadge vok={kopf.status} />
            <ToneBadge vok={kopf.kanal} />
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Fall {kopf.case_id} · Ticket {kopf.ticket_nr} · {kopf.thema} · {kopf.anbieter}
            {kopf.gegner ? ` / ${kopf.gegner}` : ""} · eingegangen{" "}
            {zeitFormat(kopf.eingegangen_am)}
          </p>
        </div>
        {kopf.fallgruppe_bestaetigt ? null : (
          <Button size="sm" variant="outline" onClick={onBestaetigen}>
            Fallgruppe bestätigen
          </Button>
        )}
      </div>

      {kopf.schema_stopp_text || kopf.hinweis ? (
        <div className="border-t border-border px-4 py-2 text-sm">
          {kopf.schema_stopp_text ? <p>{kopf.schema_stopp_text}</p> : null}
          {kopf.hinweis ? <p className="text-muted-foreground">{kopf.hinweis}</p> : null}
        </div>
      ) : null}
    </header>
  );
}
