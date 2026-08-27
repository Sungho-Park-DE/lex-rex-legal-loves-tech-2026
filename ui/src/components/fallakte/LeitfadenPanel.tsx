import { useState, type ReactNode } from "react";
import type { Leitfaden, LeitfadenFrage } from "@/types/viewmodel";

import { ChevronDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Panel, LeerHinweis } from "./Panel";
import { ToneBadge } from "./ToneBadge";
import { cn } from "@/lib/utils";

type Entwurf = Record<string, string | number | boolean>;

function FeldEingabe({
  frage,
  feldId,
  wert,
  onWert,
  mehrfach,
}: {
  frage: LeitfadenFrage;
  feldId: string;
  wert: string | number | boolean | undefined;
  onWert: (wert: string | number | boolean | undefined) => void;
  mehrfach: boolean;
}) {
  const werte = frage.werte?.[feldId];

  function umschlag(inhalt: ReactNode) {
    return mehrfach ? (
      <label className="block">
        <span className="text-muted-foreground">{frage.feld_labels?.[feldId] ?? feldId}</span>
        <div className="mt-0.5">{inhalt}</div>
      </label>
    ) : (
      <>{inhalt}</>
    );
  }

  if (werte && werte.length > 0) {
    return umschlag(
      <Select value={typeof wert === "string" ? wert : ""} onValueChange={(v) => onWert(v)}>
        <SelectTrigger className="h-8 w-full max-w-xs text-sm">
          <SelectValue placeholder="Bitte wählen" />
        </SelectTrigger>
        <SelectContent>
          {werte.map((w) => (
            <SelectItem key={w} value={w}>
              {frage.wert_labels?.[feldId]?.[w] ?? w}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>,
    );
  }

  if (frage.typ === "zahl") {
    return umschlag(
      <Input
        type="number"
        className="h-8 w-full max-w-[10rem] text-sm"
        value={wert === undefined ? "" : String(wert)}
        onChange={(e) => onWert(e.target.value === "" ? undefined : Number(e.target.value))}
      />,
    );
  }

  if (frage.typ === "text") {
    return umschlag(
      <Input
        type="text"
        className="h-8 w-full max-w-xs text-sm"
        value={wert === undefined ? "" : String(wert)}
        onChange={(e) => onWert(e.target.value === "" ? undefined : e.target.value)}
      />,
    );
  }

  // ja_nein, and any mehrfach field without delivered values
  return umschlag(
    <div className="flex gap-2">
      <Button
        type="button"
        size="sm"
        variant={wert === true ? "default" : "outline"}
        onClick={() => onWert(wert === true ? undefined : true)}
      >
        Ja
      </Button>
      <Button
        type="button"
        size="sm"
        variant={wert === false ? "default" : "outline"}
        onClick={() => onWert(wert === false ? undefined : false)}
      >
        Nein
      </Button>
    </div>,
  );
}

function FrageZeile({
  f,
  entwurf,
  onWert,
}: {
  f: LeitfadenFrage;
  entwurf?: Entwurf;
  onWert?: (feldId: string, wert: string | number | boolean | undefined) => void;
}) {
  return (
    <li className="rounded border border-border px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        {/* Kein `pruefpunkt_id`: der Leitfaden ist der Schirm, den die Beraterin
            liest, WÄHREND sie mit der Verbraucherin spricht — dort ist eine
            Nummer Rauschen. Im Prüfpfad (Schritt 4) bleibt sie: das ist die
            Fläche, auf der die Beraterin die Begründung nachprüft, und dort
            ist die Nummer ihr Arbeitsgriff. Entscheidung Sungho, 26. Aug. */}
        <span className="text-sm text-muted-foreground">{f.pruefpunkt_titel}</span>
        <ToneBadge vok={f.status} withDot />
      </div>
      <p className="mt-1 text-sm">{f.text}</p>
      <p className="text-sm text-muted-foreground">{f.grund}</p>
      {f.hinweis ? <p className="text-sm text-muted-foreground">{f.hinweis}</p> : null}
      {onWert ? (
        <div className="mt-2 space-y-2">
          {f.fuellt.map((feldId) => (
            <FeldEingabe
              key={feldId}
              frage={f}
              feldId={feldId}
              wert={entwurf?.[feldId]}
              onWert={(w) => onWert(feldId, w)}
              mehrfach={f.fuellt.length > 1}
            />
          ))}
        </div>
      ) : null}
    </li>
  );
}

export function LeitfadenPanel({
  leitfaden,
  onAntworten,
}: {
  leitfaden: Leitfaden;
  onAntworten?: (antworten: Record<string, string | number | boolean>) => Promise<void>;
}) {
  const offen = leitfaden.offen;
  const rest = leitfaden.fragen.length - offen;
  const [restOffen, setRestOffen] = useState(false);
  const [entwurf, setEntwurf] = useState<Entwurf>({});
  const [laeuft, setLaeuft] = useState(false);

  const offeneFragen = leitfaden.fragen.filter((f) => f.status.code === "offen");
  const restFragen = leitfaden.fragen.filter((f) => f.status.code !== "offen");

  function setzeWert(feldId: string, wert: string | number | boolean | undefined) {
    setEntwurf((alt) => {
      const neu = { ...alt };
      if (wert === undefined || (typeof wert === "number" && Number.isNaN(wert)))
        delete neu[feldId];
      else neu[feldId] = wert;
      return neu;
    });
  }

  const gefuellt = Object.keys(entwurf).length > 0;

  async function uebernehmen() {
    if (!onAntworten || !gefuellt) return;
    setLaeuft(true);
    try {
      await onAntworten(entwurf);
      setEntwurf({});
    } finally {
      setLaeuft(false);
    }
  }

  return (
    <Panel
      id="leitfaden"
      titel="Gesprächsleitfaden"
      aktion={<span className="text-sm text-muted-foreground">{offen} offen</span>}
    >
      {leitfaden.fragen.length === 0 ? (
        <LeerHinweis>Keine Fragen hinterlegt.</LeerHinweis>
      ) : (
        <div className="space-y-4">
          {offeneFragen.length > 0 ? (
            <>
              <ul className="space-y-3">
                {offeneFragen.map((f, i) => (
                  <FrageZeile
                    key={`${f.pruefpunkt_id}-${i}`}
                    f={f}
                    entwurf={entwurf}
                    onWert={setzeWert}
                  />
                ))}
              </ul>
              <Button
                type="button"
                size="sm"
                disabled={!gefuellt || laeuft}
                onClick={() => void uebernehmen()}
              >
                Antworten übernehmen
              </Button>
            </>
          ) : null}

          {restFragen.length > 0 ? (
            <>
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => setRestOffen((v) => !v)}
                aria-expanded={restOffen}
              >
                <ChevronDown
                  className={cn("h-4 w-4 transition-transform", restOffen && "rotate-180")}
                />
                Beantwortete & entfallene anzeigen ({rest})
              </Button>
              {restOffen ? (
                <ul className="space-y-3">
                  {restFragen.map((f, i) => (
                    <FrageZeile key={`${f.pruefpunkt_id}-${i}`} f={f} />
                  ))}
                </ul>
              ) : null}
            </>
          ) : null}
        </div>
      )}
    </Panel>
  );
}
