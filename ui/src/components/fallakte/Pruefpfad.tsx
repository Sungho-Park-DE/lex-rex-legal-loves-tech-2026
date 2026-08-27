import { useState } from "react";
import { ChevronDown, Maximize2, RefreshCw } from "lucide-react";

import { chipKlasse, randKlasse } from "@/lib/tone";
import { cn } from "@/lib/utils";
import type { Pruefpunkt as PruefpunktTyp, Pruefpfad as PruefpfadTyp } from "@/types/viewmodel";

import { AnkerListe } from "./AnkerPopover";
import { FachpruefungListe } from "./FachpruefungBlock";
import { Panel } from "./Panel";
import { Pruefbaum } from "./Pruefbaum";
import { PruefdiagrammVollbild } from "./PruefdiagrammVollbild";
import { ToneBadge } from "./ToneBadge";
import { ZitatLink, ZitatListe } from "./ZitatLink";
import { Button } from "@/components/ui/button";

function Kennzahl({ titel, wert, annahmen }: { titel: string; wert: string; annahmen: string[] }) {
  return (
    <p className="mt-1 text-sm text-muted-foreground">
      {titel}: <span className="text-foreground">{wert}</span>
      {annahmen.length > 0 ? ` — ${annahmen.join("; ")}` : ""}
    </p>
  );
}

function PruefpunktRow({ p }: { p: PruefpunktTyp }) {
  const verwendetZitatKeys = new Set(
    p.verwendet
      .filter((v) => v.zitat)
      .map((v) => `${v.zitat!.dok_id}|${v.zitat!.seite}|${v.zitat!.zitat}`),
  );
  const duplikatFreieZitate = p.zitate.filter(
    (z) => !verwendetZitatKeys.has(`${z.dok_id}|${z.seite}|${z.zitat}`),
  );

  return (
    <li
      id={`pp-${p.pruefpunkt_id}`}
      className={cn("rounded border px-3 py-2", randKlasse(p.zustand.tone))}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">
          {p.pruefpunkt_id} · {p.titel}
        </span>
        <ToneBadge vok={p.zustand} withDot />
        <ToneBadge vok={p.rolle} />
        {p.normrang ? <ToneBadge vok={p.normrang} /> : null}
        {p.typ ? <ToneBadge vok={p.typ} /> : null}
        <ToneBadge vok={p.herkunft} />
        {p.badge ? <ToneBadge vok={p.badge} /> : null}
        {p.owner ? <ToneBadge vok={p.owner} /> : null}
        {p.hinweis_abmahnung ? (
          <>
            <ToneBadge vok={p.hinweis_abmahnung.badge} detail={p.hinweis_abmahnung.text} />
            {p.hinweis_abmahnung.quelle_url ? (
              <a
                href={p.hinweis_abmahnung.quelle_url}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-muted-foreground underline"
              >
                Quelle
              </a>
            ) : null}
          </>
        ) : null}
      </div>

      {p.proposition ? <p className="mt-1 text-sm text-muted-foreground">{p.proposition}</p> : null}
      {p.grund ? <p className="mt-1 text-sm">{p.grund}</p> : null}
      {p.inaktiv_grund ? (
        <p className="mt-1 text-sm text-muted-foreground">{p.inaktiv_grund}</p>
      ) : null}
      {p.wertungsfrage && p.wertungsfrage !== p.grund ? (
        <p className="mt-1 text-sm">
          <span className="text-sm uppercase tracking-wide text-muted-foreground">
            Wertungsfrage:{" "}
          </span>
          {p.wertungsfrage}
        </p>
      ) : null}
      {p.frist ? (
        <Kennzahl titel={p.frist.name} wert={p.frist.wert} annahmen={p.frist.annahmen} />
      ) : null}
      {p.betrag ? (
        <Kennzahl titel={p.betrag.name} wert={p.betrag.wert} annahmen={p.betrag.annahmen} />
      ) : null}
      {p.override ? (
        <p className="mt-1 text-sm text-muted-foreground">
          Override auf {p.override.neuer_zustand.label} durch {p.override.von}: {p.override.grund}
        </p>
      ) : null}

      {p.verwendet.length > 0 ? (
        <ul className="mt-2 space-y-1.5 border-t border-border pt-2">
          {p.verwendet.map((v, index) => {
            const mehrfach = p.verwendet.filter((x) => x.feld_id === v.feld_id).length > 1;
            return (
              <li
                key={`${v.feld_id}-${index}`}
                className={cn(
                  "rounded px-2 py-1 text-sm",
                  mehrfach && cn("border border-dashed", chipKlasse(v.herkunft.tone)),
                )}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-muted-foreground">{v.feld_label ?? v.feld_id}</span>
                  <span className="font-medium text-foreground">{v.wert_anzeige}</span>
                  <ToneBadge vok={v.herkunft} />
                  {v.badge ? <ToneBadge vok={v.badge} /> : null}
                </div>
                {v.annahme_anzeige ? (
                  <p className="text-muted-foreground">{v.annahme_anzeige}</p>
                ) : null}
                {v.zitat ? (
                  <div className="mt-0.5">
                    <ZitatLink zitat={v.zitat} />
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}

      {p.geprueft_von && p.geprueft_von.length > 0 ? (
        <FachpruefungListe eintraege={p.geprueft_von} />
      ) : null}

      <ZitatListe zitate={duplikatFreieZitate} />
      <AnkerListe anker={p.anker} />
    </li>
  );
}

export function Pruefpfad({
  pruefpfad,
  onNeuPruefen,
}: {
  pruefpfad: PruefpfadTyp;
  onNeuPruefen?: () => void;
}) {
  const [vollbild, setVollbild] = useState(false);
  return (
    <Panel
      id="pruefpfad"
      titel="Prüfpfad"
      aktion={
        <div className="flex items-center gap-2">
          {pruefpfad.baum ? (
            <button
              type="button"
              onClick={() => setVollbild(true)}
              title="Die Prüflogik als Baum, auf dem ganzen Schirm"
              className="inline-flex items-center gap-1 rounded border border-border px-2 py-0.5 text-sm text-muted-foreground hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              <Maximize2 className="size-3.5" aria-hidden />
              Diagramm
            </button>
          ) : null}
          <ToneBadge vok={pruefpfad.wurzel} withDot />
          {pruefpfad.gerissene_stufe ? (
            <span className="text-sm text-muted-foreground">
              gerissen bei {pruefpfad.gerissene_stufe_titel ?? pruefpfad.gerissene_stufe}
            </span>
          ) : null}
          {onNeuPruefen ? (
            <Button variant="outline" size="sm" onClick={onNeuPruefen}>
              <RefreshCw className="size-3.5" />
              Prüfschema neu einlesen
            </Button>
          ) : null}
        </div>
      }
    >
      <PruefdiagrammVollbild
        baum={pruefpfad.baum}
        offen={vollbild}
        onSchliessen={() => setVollbild(false)}
      />

      <p className="mb-1 text-sm uppercase tracking-wide text-muted-foreground">Übersicht</p>
      <Pruefbaum baum={pruefpfad.baum} legende={pruefpfad.legende} />

      <p className="mb-1 text-sm uppercase tracking-wide text-muted-foreground">Details</p>
      <div className="space-y-2">
        {pruefpfad.stufen.map((s) => (
          <details
            key={s.stufe_id}
            className="group rounded border border-border"
            // dieselbe Regel wie im Baum darüber: offen nur, wo ein **tragender**
            // Punkt offen oder gerissen ist — sonst widersprechen sich Übersicht
            // und Liste, und S5/S6 stehen in jedem Fall aufgeklappt da.
            open={s.pruefpunkte.some(
              (p) =>
                ["NEIN", "WERTUNG", "FEHLT"].includes(p.zustand.code) && p.rolle.code === "tragend",
            )}
          >
            <summary
              id={`stufe-${s.stufe_id}`}
              className="flex cursor-pointer list-none flex-wrap items-center gap-2 px-3 py-2"
            >
              <span className="text-sm font-medium">{s.titel}</span>
              {s.pruefpunkte.some((p) => p.rolle.code === "tragend") ? (
                <ToneBadge vok={s.zustand} withDot />
              ) : null}
              <span className="text-sm text-muted-foreground">
                {s.pruefpunkte.length} {s.pruefpunkte.length === 1 ? "Prüfpunkt" : "Prüfpunkte"}
              </span>
              <ChevronDown
                className="ml-auto size-4 shrink-0 text-muted-foreground transition-transform duration-150 group-open:rotate-180"
                aria-hidden
              />
            </summary>
            <ul className="space-y-2 border-t border-border px-3 py-2">
              {s.pruefpunkte.map((p) => (
                <PruefpunktRow key={p.pruefpunkt_id} p={p} />
              ))}
            </ul>
          </details>
        ))}

        {pruefpfad.ableitungen.length > 0 ? (
          <details className="group rounded border border-border">
            <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-sm font-medium">
              Ableitungen ({pruefpfad.ableitungen.length})
              <ChevronDown
                className="ml-auto size-4 shrink-0 text-muted-foreground transition-transform duration-150 group-open:rotate-180"
                aria-hidden
              />
            </summary>
            <ul className="space-y-2 border-t border-border px-3 py-2">
              {pruefpfad.ableitungen.map((p) => (
                <PruefpunktRow key={p.pruefpunkt_id} p={p} />
              ))}
            </ul>
          </details>
        ) : null}
      </div>
    </Panel>
  );
}
