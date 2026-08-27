import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { Referat } from "@/types/viewmodel";

import { Panel } from "./Panel";

export function ReferatPanel({
  referat,
  onMarkieren,
}: {
  referat: Referat;
  onMarkieren: (nutzlast: { kriterien: string[]; notiz: string }) => void | Promise<void>;
}) {
  const [angehakt, setAngehakt] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(referat.kriterien.map((k) => [k.id, k.angehakt])),
  );
  const [notiz, setNotiz] = useState(referat.notiz ?? "");
  const [sendet, setSendet] = useState(false);

  async function senden(kriterien: string[]) {
    setSendet(true);
    try {
      await onMarkieren({ kriterien, notiz });
    } finally {
      setSendet(false);
    }
  }

  const gewaehlt = referat.kriterien.filter((k) => angehakt[k.id]).map((k) => k.id);

  return (
    <Panel
      id="referat"
      titel="Referat-Markierung"
      aktion={
        <Button
          size="sm"
          variant="outline"
          disabled={sendet}
          onClick={() => void senden(referat.markiert ? [] : gewaehlt)}
        >
          {referat.markiert ? "Markierung aufheben" : "Für Referat markieren"}
        </Button>
      }
    >
      <ul className="space-y-1.5">
        {referat.kriterien.map((k) => (
          <li key={k.id} className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              id={`referat-${k.id}`}
              className="mt-1"
              checked={angehakt[k.id] ?? false}
              onChange={(e) => setAngehakt((alt) => ({ ...alt, [k.id]: e.target.checked }))}
            />
            <label htmlFor={`referat-${k.id}`}>
              {k.label}
              {k.evidenz ? (
                <span className="ml-1 text-sm text-muted-foreground">— {k.evidenz}</span>
              ) : null}
            </label>
          </li>
        ))}
      </ul>
      <Textarea
        className="mt-3"
        value={notiz}
        onChange={(e) => setNotiz(e.target.value)}
        aria-label="Notiz"
        rows={3}
      />
      <p className="mt-2 text-sm text-muted-foreground">{referat.hinweis}</p>
      <p className="mt-1 text-sm text-muted-foreground">
        Status: {referat.markiert ? "markiert" : "nicht markiert"}
      </p>
    </Panel>
  );
}
