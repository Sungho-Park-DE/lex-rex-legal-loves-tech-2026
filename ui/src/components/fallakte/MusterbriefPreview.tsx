import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { randKlasse } from "@/lib/tone";
import { cn } from "@/lib/utils";
import type { Musterbrief } from "@/types/viewmodel";

import { Panel } from "./Panel";
import { ToneBadge } from "./ToneBadge";

export function MusterbriefPreview({
  musterbrief,
  onRechtsbehelf,
}: {
  musterbrief: Musterbrief;
  onRechtsbehelf: (id: string) => void;
}) {
  return (
    <Panel
      id="musterbrief"
      titel="Musterbrief"
      aktion={
        <div className="flex flex-wrap items-center gap-2">
          <ToneBadge vok={musterbrief.status} withDot />
          <ToneBadge vok={musterbrief.quelle} />
          <ToneBadge vok={musterbrief.empfaenger} />
        </div>
      }
    >
      <fieldset className="mb-3">
        <legend className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Rechtsbehelf
        </legend>
        <ul className="mt-2 space-y-1">
          {musterbrief.vorschlaege.map((v) => (
            <li key={v.rechtsbehelf_id}>
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="rechtsbehelf"
                  className="mt-1"
                  checked={v.rechtsbehelf_id === musterbrief.rechtsbehelf_id}
                  onChange={() => onRechtsbehelf(v.rechtsbehelf_id)}
                />
                <span>
                  {v.titel}
                  {v.hauptvorschlag ? (
                    <span className="ml-1 text-sm text-muted-foreground">(Hauptvorschlag)</span>
                  ) : null}
                  {v.geprueft ? (
                    <span className="ml-1 text-sm text-muted-foreground">· juristisch geprüft</span>
                  ) : null}
                </span>
              </label>
            </li>
          ))}
        </ul>
      </fieldset>

      <div className={cn("rounded border-2 bg-background", randKlasse(musterbrief.status.tone))}>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-3 py-2">
          <span className="text-sm font-medium">{musterbrief.titel}</span>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              void navigator.clipboard
                .writeText(musterbrief.text)
                .then(() => toast.success("Kopiert"))
                .catch(() => toast.error("Kopieren fehlgeschlagen"));
            }}
          >
            Kopieren
          </Button>
        </div>
        {/*
          Die Höhe hing an `max-h-96` = 384 px = 16,35 Zeilen: der Brief wurde
          **mitten in einer Textzeile** waagerecht abgeschnitten, und darunter
          lagen alle Begründungsabsätze, die Rückforderung und die Frist. Auf
          macOS ist der Overlay-Scrollbalken im Ruhezustand unsichtbar, es sah
          also nicht nach Scrollen aus, sondern nach einem Renderfehler — auf
          einem der vier „nie streichen"-Beats (`35` H5).
          Auch eine schirmbezogene Höhe reichte nicht: der Demobrief ist bei
          1440 957 px hoch, der Platz 676 px. Also **gar keine** Deckelung —
          die Karte wächst mit dem Brief, und wer weiterlesen will, scrollt die
          Seite wie überall sonst. Ein sichtbarer Seiten-Scrollbalken ist besser
          als ein unsichtbarer im Kasten.
        */}
        <pre className="whitespace-pre-wrap px-3 py-3 font-sans text-sm leading-relaxed">
          {musterbrief.text}
        </pre>
        {musterbrief.geprueft ? null : (
          <p className="border-t border-border px-3 py-2 text-sm text-muted-foreground">
            Dieses Schreiben ist juristisch nicht geprüft.
          </p>
        )}
      </div>

      {musterbrief.quelle_url ? (
        <a
          href={musterbrief.quelle_url}
          target="_blank"
          rel="noreferrer"
          className="mt-2 inline-block text-sm underline underline-offset-2"
        >
          Vorlagenquelle
        </a>
      ) : null}

      <details className="mt-3">
        <summary className="cursor-pointer text-sm text-muted-foreground">
          Platzhalter ({Object.keys(musterbrief.platzhalter).length})
        </summary>
        <dl className="mt-2 grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2">
          {Object.entries(musterbrief.platzhalter).map(([k, v]) => (
            <div key={k} className="flex gap-2 text-sm">
              <dt className="text-muted-foreground">{k}</dt>
              <dd className="text-foreground">{v}</dd>
            </div>
          ))}
        </dl>
      </details>

      <div className="mt-3">
        <Button
          size="sm"
          variant="outline"
          onClick={() => onRechtsbehelf(musterbrief.rechtsbehelf_id)}
        >
          Rechtsbehelf übernehmen
        </Button>
      </div>
    </Panel>
  );
}
