import { useState } from "react";
import { ChevronDown } from "lucide-react";

import {
  CartesianGrid,
  Cell,
  LabelList,
  ReferenceArea,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { chipKlasse, punktKlasse, textKlasse } from "@/lib/tone";
import type {
  RadarAnsicht,
  RadarCluster,
  RadarKlauseltyp,
  RadarSchaden,
  Tone,
} from "@/types/viewmodel";

function betragFormat(wert: number | null) {
  if (wert === null) return "—";
  return wert.toLocaleString("de-DE", { style: "currency", currency: "EUR" });
}

/** Wie die Zahl zustande kam. Eine gekappte Zahl darf nicht wie eine gemessene aussehen. */
function basisText(s: RadarSchaden) {
  const faelle = (n: number) => (n === 1 ? "Ein Fall" : `${n} Fälle`);
  const teile: string[] = [];
  if (s.gekappt > 0)
    teile.push(`${faelle(s.gekappt)} ohne erkennbare Laufzeit — hilfsweise auf 24 Monate begrenzt`);
  if (s.verlaengert > 0)
    teile.push(
      `${faelle(s.verlaengert)} in der Verlängerung — nur bis zum nächsten Kündigungstermin gerechnet`,
    );
  return teile.length ? teile.join(" · ") + "." : null;
}

function ClusterBar({ cluster, maxFaelle }: { cluster: RadarCluster; maxFaelle: number }) {
  const s = cluster.schaden;
  const hinweis = basisText(s);
  const [berechnungOffen, setBerechnungOffen] = useState(false);

  return (
    <li className="rounded border border-border bg-card px-4 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-base font-semibold">{cluster.anbieter}</h3>
        <p className="text-sm text-muted-foreground">
          {cluster.branche ? `${cluster.branche} · ` : ""}
          {cluster.faelle} Fälle · {cluster.referat_flags} Markierungen
          {cluster.wiederholung > 0
            ? ` · ${cluster.wiederholung} ${cluster.wiederholung === 1 ? "Wiederholung" : "Wiederholungen"}`
            : ""}
        </p>
      </div>

      <div
        className="mt-2 flex h-5 w-full overflow-hidden rounded bg-muted"
        role="img"
        aria-label={cluster.einordnungen.map((e) => `${e.text}: ${e.anzahl}`).join(", ")}
        style={{ maxWidth: `${(cluster.faelle / maxFaelle) * 100}%` }}
      >
        {cluster.einordnungen.map((e, i) => (
          <span
            key={i}
            title={`${e.text}: ${e.anzahl}`}
            className={cn(
              "h-full rounded-none border-r border-card last:border-r-0",
              punktKlasse(e.tone),
            )}
            style={{ width: `${(e.anzahl / cluster.faelle) * 100}%` }}
          />
        ))}
      </div>

      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {cluster.einordnungen.map((e, i) => (
          <li key={i} className={cn("text-sm", textKlasse(e.tone))}>
            {e.text}: {e.anzahl}
          </li>
        ))}
      </ul>

      {cluster.pruefpunkte_nein.length > 0 ? (
        <p className="mt-1 text-sm text-muted-foreground">
          Nicht erfüllte Prüfpunkte:{" "}
          {cluster.pruefpunkte_nein.map((p) => `${p.titel} (${p.anzahl})`).join(", ")}
        </p>
      ) : null}

      <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-1 border-t border-border pt-2 sm:grid-cols-2">
        <div className="flex items-baseline justify-between gap-2">
          <dt
            className="text-sm text-muted-foreground"
            title="Was bis heute schon zu viel gezahlt wurde — verloren, sofern nicht zurückgefordert."
          >
            Schaden bereits entstanden
          </dt>
          <dd className="text-lg font-semibold tabular-nums">
            {betragFormat(s.entstanden_summe)}
            <span className="ml-1 text-sm text-muted-foreground">
              (Median {betragFormat(s.entstanden_median)})
            </span>
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-2">
          <dt
            className="text-sm font-medium"
            title="Was bis zum Ende der Vertragsbindung noch anfällt — und was eine Beratung jetzt noch verhindern kann."
          >
            Schaden noch abwendbar
          </dt>
          <dd className="text-lg font-semibold tabular-nums">
            {betragFormat(s.drohend_summe)}
            <span className="ml-1 text-sm font-normal text-muted-foreground">
              (Median {betragFormat(s.drohend_median)})
            </span>
          </dd>
        </div>
      </dl>
      <div className="mt-1">
        <Button
          variant="outline"
          size="sm"
          className="h-6 px-2 text-sm"
          onClick={() => setBerechnungOffen((v) => !v)}
          aria-expanded={berechnungOffen}
        >
          <ChevronDown
            className={cn("h-3.5 w-3.5 transition-transform", berechnungOffen && "rotate-180")}
          />
          Berechnung
        </Button>
        {berechnungOffen ? (
          <p className="mt-1 text-sm text-muted-foreground">
            aus {s.fallzahl} bezifferten {s.fallzahl === 1 ? "Fall" : "Fällen"}
            {s.unbeziffert > 0
              ? ` · ${s.unbeziffert} ohne Betragsangabe (unbeziffert, nicht null)`
              : ""}
            {hinweis ? ` · ${hinweis}` : ""}
            {" · "}
            <span>
              „bereits entstanden" ist bis heute zu viel gezahlt, „noch abwendbar" ist, was bis zum
              Ende der Bindung noch anfiele — nur Letzteres kann eine Beratung verhindern.
            </span>
          </p>
        ) : null}
      </div>
    </li>
  );
}

/**
 * Der Balken zeigt die **Quote** (Anteil an den Fällen der Fallgruppe), nicht
 * den Abstand zur größten Zeile: bei zwei gleich häufigen Klauseltypen wären
 * zwei volle Balken die Aussage „beide am Maximum", und das ist keine.
 */
function KlauseltypZeile({ z }: { z: RadarKlauseltyp }) {
  const anteil = z.quote ?? (z.grundgesamtheit ? z.betroffenheit / z.grundgesamtheit : 0);
  return (
    <li className="border-t border-border py-2 first:border-t-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <span className="flex flex-wrap items-center gap-2">
          {z.norm_kurz ? (
            <span
              title={z.norm ?? undefined}
              className="inline-flex items-center rounded border border-norm/60 bg-norm-bg px-2 py-0.5 text-xs leading-5 text-norm"
            >
              {z.norm_kurz}
            </span>
          ) : null}
          <span className="text-base font-medium">{z.titel}</span>
          {z.bereits_abgemahnt ? (
            <>
              <span
                className={cn(
                  "inline-flex items-center rounded border px-2 py-0.5 text-xs leading-5",
                  chipKlasse("gelb"),
                )}
              >
                bereits abgemahnt
              </span>
              {z.abmahnung_kurz ? (
                <span className="text-sm text-muted-foreground">
                  {z.abmahnung_kurz}
                  {z.abmahnung_geprueft === false ? " · ungeprüft" : ""}
                </span>
              ) : null}
            </>
          ) : null}
        </span>
        <span className="text-sm text-muted-foreground tabular-nums">
          {z.verbreitung} Verwender · {z.betroffenheit} von {z.grundgesamtheit} Fällen · Median noch
          abwendbar {betragFormat(z.schaden_drohend_median)}
        </span>
      </div>
      <div
        className="mt-1 h-1.5 w-full overflow-hidden rounded bg-muted"
        role="img"
        aria-label={`${Math.round(anteil * 100)} Prozent der Fälle`}
      >
        <span
          className="block h-full bg-foreground/60"
          style={{ width: `${Math.max(2, anteil * 100)}%` }}
        />
      </div>
    </li>
  );
}

/** Anleitung §6: Farbe = Beanstandungsquote, drei Stufen über die Tone-Tokens. */
function quoteTon(quote: number | null): Tone {
  if (quote === null) return "grau";
  if (quote >= 0.66) return "rot";
  if (quote >= 0.33) return "gelb";
  return "gruen";
}

function median(werte: number[]): number {
  const s = [...werte].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  const mitte = s[m] ?? 0;
  const davor = s[m - 1] ?? mitte;
  return s.length % 2 ? mitte : (davor + mitte) / 2;
}

/**
 * Anleitung §6 — die Hauptgrafik: je Klauseltyp Verbreitung (x), Median-
 * Einzelschaden (y), Beanstandungsquote (Farbe). Das obere rechte Feld ist
 * die Prioritätenliste. Unbezifferte Zeilen werden nicht als 0 geplottet (§5),
 * sondern gezählt. Kein Gitter, keine Animation — „UI darf nicht innovativ
 * aussehen".
 */
function Hauptgrafik({ zeilen }: { zeilen: RadarKlauseltyp[] }) {
  const punkte = zeilen
    .filter((z) => z.schaden_drohend_median !== null)
    .map((z) => ({
      ...z,
      x: z.verbreitung,
      y: z.schaden_drohend_median as number,
      ton: quoteTon(z.quote),
    }));
  const unbeziffert = zeilen.length - punkte.length;
  if (zeilen.length === 0) return null;

  const xMed = punkte.length ? median(punkte.map((p) => p.x)) : 0;
  const yMed = punkte.length ? median(punkte.map((p) => p.y)) : 0;
  const xMax = Math.max(1, ...punkte.map((p) => p.x)) + 1;
  const yMax = Math.max(1, ...punkte.map((p) => p.y)) * 1.15;

  return (
    <section className="rounded border border-border bg-card px-4 py-3">
      <h2 className="text-base font-semibold">Verbreitung und Schaden je Klauseltyp</h2>
      {punkte.length > 0 ? (
        <div
          className="mt-2 h-80 w-full"
          role="img"
          aria-label="Verbreitung gegen Median-Schaden je Klauseltyp"
        >
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 32, right: 32, bottom: 32, left: 40 }}>
              <CartesianGrid stroke="transparent" />
              <XAxis
                type="number"
                dataKey="x"
                name="Verbreitung"
                domain={[0, xMax]}
                allowDecimals={false}
                tick={{ fontSize: 14 }}
                label={{
                  value: "Verbreitung (Verwender)",
                  position: "insideBottom",
                  offset: -20,
                  fontSize: 14,
                }}
              />
              <YAxis
                type="number"
                dataKey="y"
                name="Median noch abwendbar"
                domain={[0, yMax]}
                tick={{ fontSize: 14 }}
                tickFormatter={(v: number) => betragFormat(v)}
                width={96}
                label={{
                  value: "Median abwendbar",
                  angle: -90,
                  position: "insideLeft",
                  offset: -24,
                  fontSize: 14,
                }}
              />
              <ReferenceArea
                x1={xMed}
                x2={xMax}
                y1={yMed}
                y2={yMax}
                fill="currentColor"
                fillOpacity={0.06}
                stroke="none"
              />
              <Tooltip
                cursor={false}
                formatter={(wert: number, name: string) =>
                  name === "Median noch abwendbar" ? betragFormat(wert) : wert
                }
                labelFormatter={() => ""}
              />
              <Scatter data={punkte} isAnimationActive={false}>
                {punkte.map((p) => (
                  <Cell key={p.pruefpunkt_id} fill={`var(--tone-${p.ton})`} />
                ))}
                <LabelList dataKey="titel" position="top" fontSize={13} />
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      ) : null}
      <p className="mt-1 text-sm text-muted-foreground">
        Graues Feld oben rechts = Priorität: hohe Verbreitung, hoher Schaden · Farbe =
        Beanstandungsquote (Anteil der Fälle der Fallgruppe)
        {unbeziffert > 0 ? ` · ${unbeziffert} unbeziffert` : ""}
      </p>
      <p className="mt-1 text-sm">
        Die Auswertung bildet das Beratungsaufkommen ab, nicht den Markt.
      </p>
    </section>
  );
}

export function RadarView({ radar }: { radar: RadarAnsicht }) {
  const maxFaelle = Math.max(radar.schwellen.k_min, ...radar.cluster.map((c) => c.faelle));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">Muster-Radar</h1>
          <p className="text-sm text-muted-foreground">
            Stand {radar.stand} · {radar.faelle_gesamt} Fälle · Schwellen:{" "}
            {radar.schwellen.beschwerden} Beschwerden / {radar.schwellen.beratungen} Beratungen ·
            mindestens {radar.schwellen.k_min} Fälle je Anbieter
            {radar.wiederholungen_gesamt > 0
              ? ` · ${radar.wiederholungen_gesamt} ${radar.wiederholungen_gesamt === 1 ? "Fall" : "Fälle"} mit bereits abgemahnter Klausel`
              : ""}
          </p>
          {radar.prueflogik_fassungen?.aktuell ? (
            <p className="text-sm text-muted-foreground">
              Prüflogik {radar.prueflogik_fassungen.aktuell} ·{" "}
              {radar.prueflogik_fassungen.zeilen_aktuell + radar.prueflogik_fassungen.zeilen_aelter}{" "}
              Fälle
              {radar.prueflogik_fassungen.zeilen_aelter > 0
                ? `, davon ${radar.prueflogik_fassungen.zeilen_aelter} mit älterer Fassung (${radar.prueflogik_fassungen.aelteste})`
                : ""}
            </p>
          ) : null}
        </div>
      </div>

      <p className="rounded border border-border bg-muted/40 px-3 py-2 text-sm">
        {radar.geltungsbereich}
      </p>

      <Hauptgrafik zeilen={radar.klauseltypen} />

      <section className="rounded border border-border bg-card px-4 py-3">
        <h2 className="text-base font-semibold">Klauseltypen</h2>
        {radar.klauseltypen.length === 0 ? (
          <p className="mt-2 text-base text-muted-foreground">
            Kein Klauseltyp erreicht die Schwelle von {radar.schwellen.k_min} Verwendern.
          </p>
        ) : (
          <ul className="mt-2">
            {radar.klauseltypen.map((z) => (
              <KlauseltypZeile key={z.pruefpunkt_id} z={z} />
            ))}
          </ul>
        )}
      </section>

      <ul className="space-y-3">
        {radar.cluster.map((c, i) => (
          <ClusterBar key={`${c.anbieter}-${i}`} cluster={c} maxFaelle={maxFaelle} />
        ))}
      </ul>

      <section className="rounded border border-border bg-card px-4 py-3">
        <h2 className="text-base font-semibold">Markierte Fälle</h2>
        {radar.markierte_faelle.length === 0 ? (
          <p className="mt-1 text-base text-muted-foreground">
            Kein Fall für das Referat markiert.
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {radar.markierte_faelle.map((f) => (
              <li key={f.fall_hash} className="text-base">
                {/* Der Motor liefert die Kurzform fertig (`fall_kennung`), die
                    Anzeige schneidet nicht selbst. Das Wort „Fall" davor, damit
                    die Kennung als Kennung lesbar ist und nicht als Rohwert. */}
                <span className="text-sm text-muted-foreground">
                  Fall <span className="font-mono">{f.fall_kennung}</span>
                </span>{" "}
                {f.anbieter ? `· ${f.anbieter} ` : ""}· {f.einordnung}
                {f.zeit ? <span className="text-sm text-muted-foreground"> · {f.zeit}</span> : null}
                {f.wiederholung > 0 ? (
                  <span className="text-sm text-muted-foreground"> · Wiederholung</span>
                ) : null}
                {(f.kriterien_labels ?? f.kriterien).length > 0 ? (
                  <span className="text-sm text-muted-foreground">
                    {" "}
                    ({(f.kriterien_labels ?? f.kriterien).join(", ")})
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded border border-border bg-card px-4 py-3">
        <h2 className="text-base font-semibold">Was nicht angezeigt wird</h2>
        <ul className="mt-2 space-y-1">
          {radar.hinweis.split(/(?<=\.) (?=[A-ZÄÖÜ0-9])/).map((satz, i) => (
            <li key={i} className="text-sm text-muted-foreground">
              {satz}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
