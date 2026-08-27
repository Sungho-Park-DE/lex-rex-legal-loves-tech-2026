import type { Fachpruefung } from "@/types/viewmodel";

/** Formats an ISO date (e.g. 2026-08-23) as German 23.08.2026. */
function datumKurz(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

/**
 * Shared rendering of a Fachpruefung (expert confirmation) entry.
 * Purely typographic: a left-border attest look, no colour accent.
 */
export function FachpruefungBlock({ eintrag }: { eintrag: Fachpruefung }) {
  return (
    <div className="border-l-2 border-border pl-2">
      <p className="text-sm uppercase tracking-wide text-muted-foreground">Fachlich bestätigt</p>
      <p className="text-sm">
        <span className="font-medium">{eintrag.wer}</span>{" "}
        <span className="text-muted-foreground">
          · {eintrag.beleg} · {datumKurz(eintrag.am)}
        </span>
      </p>
      {eintrag.umfang ? <p className="text-sm">{eintrag.umfang}</p> : null}
      {eintrag.vorbehalt ? (
        <p className="text-sm">
          <span className="font-medium">Vorbehalt:</span> {eintrag.vorbehalt}
        </p>
      ) : null}
    </div>
  );
}

/** Renders a list of Fachpruefung entries, each as its own block. */
export function FachpruefungListe({ eintraege }: { eintraege: Fachpruefung[] }) {
  if (eintraege.length === 0) return null;
  return (
    <ul className="mt-2 space-y-1.5 border-t border-border pt-2">
      {eintraege.map((g, i) => (
        <li key={`${g.wer}-${g.am}-${i}`}>
          <FachpruefungBlock eintrag={g} />
        </li>
      ))}
    </ul>
  );
}
