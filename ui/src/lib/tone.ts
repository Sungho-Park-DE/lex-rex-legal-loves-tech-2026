import type { Tone } from "@/types/viewmodel";

const CHIP: Record<Tone, string> = {
  gruen: "border-tone-gruen/70 bg-tone-gruen-bg text-tone-gruen",
  gelb: "border-tone-gelb/70 bg-tone-gelb-bg text-tone-gelb",
  rot: "border-tone-rot/70 bg-tone-rot-bg text-tone-rot",
  grau: "border-tone-grau/70 bg-tone-grau-bg text-tone-grau",
};

const DOT: Record<Tone, string> = {
  gruen: "bg-tone-gruen",
  gelb: "bg-tone-gelb",
  rot: "bg-tone-rot",
  grau: "bg-tone-grau",
};

const TEXT: Record<Tone, string> = {
  gruen: "text-tone-gruen",
  gelb: "text-tone-gelb",
  rot: "text-tone-rot",
  grau: "text-tone-grau",
};

const BORDER: Record<Tone, string> = {
  gruen: "border-tone-gruen/70",
  gelb: "border-tone-gelb/70",
  rot: "border-tone-rot/70",
  grau: "border-tone-grau/70",
};

export function chipKlasse(tone: Tone) {
  return CHIP[tone] ?? CHIP.grau;
}
export function punktKlasse(tone: Tone) {
  return DOT[tone] ?? DOT.grau;
}
export function textKlasse(tone: Tone) {
  return TEXT[tone] ?? TEXT.grau;
}
export function randKlasse(tone: Tone) {
  return BORDER[tone] ?? BORDER.grau;
}

/** ISO timestamp -> de-DE. Already-formatted German strings pass through. */
export function zeitFormat(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
