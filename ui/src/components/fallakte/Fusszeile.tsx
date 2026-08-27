import type { Fusszeile as FusszeileTyp } from "@/types/viewmodel";

export function Fusszeile({ fusszeile }: { fusszeile: FusszeileTyp }) {
  const kosten = (fusszeile.betriebskosten_cent / 100).toLocaleString("de-DE", {
    style: "currency",
    currency: "EUR",
  });
  return (
    <footer className="border-t border-border px-4 py-4 text-sm leading-relaxed text-muted-foreground">
      <p className="flex items-start gap-2 rounded border-2 border-warnung bg-warnung-bg px-3 py-2 text-sm font-medium text-foreground">
        <span aria-hidden className="shrink-0 font-bold text-warnung">
          !
        </span>
        <span>{fusszeile.disclaimer}</span>
      </p>
      <p className="mt-2">{fusszeile.ki_hinweis}</p>
      {typeof fusszeile.fachpruefung_bestaetigt === "number" &&
      typeof fusszeile.fachpruefung_gesamt === "number" ? (
        <p className="mt-1">
          {fusszeile.fachpruefung_bestaetigt} von {fusszeile.fachpruefung_gesamt} Prüfpunkten
          fachlich bestätigt
        </p>
      ) : null}
      <p className="mt-1">
        Schema-Version {fusszeile.schema_version} (Stand {fusszeile.schema_stand}) · Stand{" "}
        {fusszeile.stand} · Stichtag {fusszeile.stichtag} ({fusszeile.stichtag_modus}) · Normbasis{" "}
        {fusszeile.normbasis_modus} · Betriebskosten {kosten}
      </p>
    </footer>
  );
}
