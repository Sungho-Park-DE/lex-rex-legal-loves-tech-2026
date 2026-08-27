import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ChevronDown, ExternalLink } from "lucide-react";

import { textKlasse } from "@/lib/tone";
import type { Anker } from "@/types/viewmodel";

export function AnkerListe({ anker }: { anker: Anker[] }) {
  if (anker.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {anker.map((a, i) => (
        <Popover key={`${a.key}-${i}`}>
          <PopoverTrigger
            className={
              a.geprueft
                ? "group inline-flex items-center gap-1 rounded border border-norm/60 bg-norm-bg px-2 py-0.5 text-sm text-norm hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring data-[state=open]:bg-accent"
                : "group inline-flex items-center gap-1 rounded border border-dashed border-norm/40 bg-norm-bg/50 px-2 py-0.5 text-sm text-norm/70 hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring data-[state=open]:bg-accent"
            }
          >
            {/*
              Der Chip trägt nur noch die Fundstelle selbst (Sungho, 26. Aug).
              Neunzehn von zwanzig Chips sagten „· Fundstelle ungeprüft" — ein
              Wort, das in fast jeder Zeile steht, unterscheidet nichts mehr
              und drängt die Norm an den Rand. Dieselbe Entscheidung wie K55
              im Baum: die Regel bleibt stumm, die Ausnahme spricht.

              Der Prüfstand ist damit nicht weg, nur nicht mehr im Chiptext:
              der gestrichelte Rahmen und die gedämpfte Farbe stehen weiter
              an jeder ungeprüften Fundstelle (`a.geprueft` oben), und das
              Popover nennt Wort und Erklärung beim Namen.
            */}
            {a.label}
            <ChevronDown className="size-3 text-norm/60 transition-transform duration-150 group-data-[state=open]:rotate-180" />
          </PopoverTrigger>
          <PopoverContent className="max-h-80 w-96 overflow-y-auto text-sm">
            <p className="font-medium">{a.label}</p>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {a.ebene.label}
              {a.stand ? ` · Stand ${a.stand}` : ""}
            </p>
            {a.pruefstand ? (
              <p className="mt-2 text-sm">
                <span className={`font-medium ${textKlasse(a.pruefstand.tone)}`}>
                  {a.pruefstand.label}
                </span>
                {a.pruefstand.detail ? (
                  <span className="text-muted-foreground"> — {a.pruefstand.detail}</span>
                ) : null}
              </p>
            ) : null}
            {a.kernaussage ? <p className="mt-2">{a.kernaussage}</p> : null}
            {a.text ? (
              <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                {a.text}
              </p>
            ) : null}
            {a.url ? (
              <a
                href={a.url}
                target="_blank"
                rel="noreferrer"
                className="mt-3 inline-flex items-center gap-1 text-sm underline underline-offset-2"
              >
                Quelle öffnen <ExternalLink className="size-3" aria-hidden />
              </a>
            ) : null}
          </PopoverContent>
        </Popover>
      ))}
    </div>
  );
}
