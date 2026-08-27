import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { zeitFormat } from "@/lib/tone";
import type { Nachforderung } from "@/types/viewmodel";

import { Panel, LeerHinweis } from "./Panel";
import { ToneBadge } from "./ToneBadge";

function DokumenteNachreichen({
  id,
  onDokumente,
}: {
  id: string;
  onDokumente: (nachforderungId: string, dateien: File[]) => void;
}) {
  const [dateien, setDateien] = useState<File[]>([]);
  const eingabe = useRef<HTMLInputElement>(null);

  return (
    <form
      className="flex flex-wrap items-center gap-2 border-t border-border px-3 py-2"
      onSubmit={(e) => {
        e.preventDefault();
        onDokumente(id, dateien);
        setDateien([]);
        if (eingabe.current) eingabe.current.value = "";
      }}
    >
      <Input
        ref={eingabe}
        type="file"
        multiple
        aria-label="Unterlagen nachreichen"
        className="h-8 max-w-xs text-sm"
        onChange={(e) => setDateien(Array.from(e.target.files ?? []))}
      />
      <Button size="sm" variant="outline" type="submit" disabled={dateien.length === 0}>
        Unterlagen nachreichen
      </Button>
    </form>
  );
}

export function NachforderungenPanel({
  nachforderungen,
  onErzeugen,
  onMarkieren,
  onDokumente,
}: {
  nachforderungen: Nachforderung[];
  onErzeugen: () => void;
  onMarkieren: (id: string, status: string) => void;
  onDokumente: (nachforderungId: string, dateien: File[]) => void;
}) {
  return (
    <Panel
      id="nachforderungen"
      titel="Nachforderungen"
      aktion={
        <Button size="sm" variant="outline" onClick={onErzeugen}>
          Nachforderung erzeugen
        </Button>
      }
    >
      {nachforderungen.length === 0 ? (
        <LeerHinweis>Keine Nachforderung erzeugt.</LeerHinweis>
      ) : (
        <ul className="space-y-4">
          {nachforderungen.map((n) => (
            <li key={n.id} className="rounded border border-border">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-3 py-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm text-muted-foreground">{n.id}</span>
                  <ToneBadge vok={n.status} withDot />
                  <ToneBadge vok={n.kanal} />
                  {n.dokumente.map((d, di) => (
                    <ToneBadge key={`${d.code}-${di}`} vok={d} />
                  ))}
                  <span className="text-sm text-muted-foreground">{zeitFormat(n.zeit)}</span>
                </div>
                <div className="flex flex-wrap items-center gap-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      void navigator.clipboard
                        .writeText(n.text)
                        .then(() => toast.success("Kopiert"))
                        .catch(() => toast.error("Kopieren fehlgeschlagen"));
                    }}
                  >
                    Kopieren
                  </Button>
                  {n.status.code === "offen" ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => onMarkieren(n.id, "angefordert")}
                    >
                      als angefordert markieren
                    </Button>
                  ) : null}
                </div>
              </div>
              {/* Wie im Musterbrief (`35` H5): keine Deckelung, die den Text
                  mitten in der Zeile kappt — der Nachforderungsbrief wird auf
                  der Bühne vorgelesen und kopiert. */}
              <pre className="whitespace-pre-wrap px-3 py-2 font-sans text-sm leading-relaxed">
                {n.text}
              </pre>
              <p className="px-3 pb-2 text-sm text-muted-foreground">
                Das Werkzeug versendet nichts — den Text kopieren Sie selbst in Ihren Kanal.
              </p>
              <DokumenteNachreichen id={n.id} onDokumente={onDokumente} />
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
