import { useState } from "react";
import type { ProtokollEintrag } from "@/types/viewmodel";

import { ChevronDown } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { randKlasse } from "@/lib/tone";

import { Panel, LeerHinweis } from "./Panel";

/** ISO timestamp -> dd.MM. HH:mm (short, no year). */
function zeitKurz(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ProtokollPanel({ protokoll }: { protokoll: ProtokollEintrag[] }) {
  const [offen, setOffen] = useState(false);
  const [nurAuffaellig, setNurAuffaellig] = useState(false);

  const zeilen = nurAuffaellig
    ? protokoll.filter((e) => e.aktion.tone === "gelb")
    : protokoll;

  function kopieren() {
    const text = zeilen
      .map((e) =>
        [
          zeitKurz(e.zeit),
          e.schritt?.label ?? "—",
          e.aktion.label,
          e.beschreibung,
        ].join("\t"),
      )
      .join("\n");
    void navigator.clipboard
      .writeText(text)
      .then(() => toast.success("Kopiert"))
      .catch(() => toast.error("Kopieren fehlgeschlagen"));
  }

  return (
    <Panel id="protokoll" titel="Protokoll">
      {protokoll.length === 0 ? (
        <LeerHinweis>Keine Einträge.</LeerHinweis>
      ) : (
        <>
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={() => setOffen((v) => !v)}
            aria-expanded={offen}
          >
            <ChevronDown
              className={cn(
                "h-4 w-4 transition-transform",
                offen && "rotate-180",
              )}
            />
            {protokoll.length} Einträge anzeigen
          </Button>

          {offen ? (
            <div className="mt-3 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={nurAuffaellig}
                    onChange={(e) => setNurAuffaellig(e.target.checked)}
                  />
                  nur auffällige Zeilen
                </label>
                <Button size="sm" variant="ghost" onClick={kopieren}>
                  Kopieren
                </Button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-sm text-muted-foreground">
                      <th className="whitespace-nowrap px-2 py-1 font-medium">Zeit</th>
                      <th className="px-2 py-1 font-medium">Schritt</th>
                      <th className="px-2 py-1 font-medium">Ereignis</th>
                      <th className="px-2 py-1 font-medium">Beschreibung</th>
                    </tr>
                  </thead>
                  <tbody>
                    {zeilen.map((e, i) => (
                      <tr
                        key={i}
                        className={cn(
                          "border-b border-border align-top",
                          e.aktion.tone === "gelb" &&
                            cn("border-l-4", randKlasse("gelb")),
                        )}
                      >
                        <td className="whitespace-nowrap px-2 py-1.5 text-sm text-muted-foreground">
                          {zeitKurz(e.zeit)}
                        </td>
                        <td className="px-2 py-1.5 text-muted-foreground">
                          {e.schritt?.label ?? "—"}
                        </td>
                        <td className="px-2 py-1.5">{e.aktion.label}</td>
                        <td
                          className="px-2 py-1.5"
                          style={{ overflowWrap: "anywhere" }}
                        >
                          {e.beschreibung}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <p className="text-sm text-muted-foreground">Gesamt: {zeilen.length}</p>
            </div>
          ) : null}
        </>
      )}
    </Panel>
  );
}
