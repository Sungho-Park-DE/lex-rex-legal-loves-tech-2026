import { queryOptions } from "@tanstack/react-query";
import { toast } from "sonner";

import type { FallAnsicht, RadarAnsicht } from "@/types/viewmodel";

const BASE = import.meta.env["VITE_API_BASE_URL"] as string | undefined;

export const istDemoModus = !BASE;

async function holen<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`Laden fehlgeschlagen (${res.status}): ${url}`);
  return (await res.json()) as T;
}

export function fallLaden(caseId: string) {
  return BASE
    ? holen<FallAnsicht>(`${BASE}/faelle/${encodeURIComponent(caseId)}`)
    : holen<FallAnsicht>(`/fixtures/faelle/${encodeURIComponent(caseId)}.json`);
}

export function radarLaden() {
  return BASE ? holen<RadarAnsicht>(`${BASE}/radar`) : holen<RadarAnsicht>(`/fixtures/radar.json`);
}

export function fallQuery(caseId: string) {
  return queryOptions({
    queryKey: ["fall", caseId],
    queryFn: () => fallLaden(caseId),
  });
}

export function radarQuery() {
  return queryOptions({
    queryKey: ["radar"],
    queryFn: () => radarLaden(),
  });
}

export type AktionName =
  | "fallgruppe_bestaetigen"
  | "override"
  | "nachforderung_erzeugen"
  | "nachforderung_markieren"
  | "rechtsbehelf_waehlen"
  | "referat_markieren"
  | "abschluss";

/**
 * Every gate is its own backend route — there is no `/aktionen/` prefix
 * (`fallpruefer/api.py`). Two actions share one route: producing a
 * Nachforderung and marking it as requested differ only in the payload.
 */
const AKTION_PFAD: Record<AktionName, string> = {
  fallgruppe_bestaetigen: "fallgruppe",
  override: "override",
  nachforderung_erzeugen: "nachforderung",
  nachforderung_markieren: "nachforderung",
  rechtsbehelf_waehlen: "rechtsbehelf",
  referat_markieren: "referat",
  abschluss: "abschluss",
};

/**
 * The UI never mutates the view-model itself: every action goes to the backend.
 * Without a backend (fixture mode) nothing is stored and we say so.
 *
 * A failure throws the backend's German `detail` — same pattern as the
 * dedicated calls below, so the caller can decide and then refetch.
 */
export async function aktionSenden(
  caseId: string,
  aktion: AktionName,
  nutzlast: Record<string, unknown> = {},
): Promise<void> {
  if (!BASE) {
    toast("Demo-Modus: nicht gespeichert");
    return;
  }
  const pfad = AKTION_PFAD[aktion];
  const res = await fetch(`${BASE}/faelle/${encodeURIComponent(caseId)}/${pfad}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(nutzlast),
  });
  if (!res.ok) {
    throw new Error(await fehlerText(res));
  }
  toast.success("Gespeichert");
}

/**
 * View model 1.4: the consumer states a document never existed.
 * The backend moves the item from the consumer to the company side.
 */
export async function nichtVorhandenSenden(
  caseId: string,
  nutzlast: { dokumenttyp: string; aussage: string },
): Promise<void> {
  if (!BASE) {
    toast("Demo-Modus: nicht gespeichert");
    return;
  }
  const res = await fetch(`${BASE}/faelle/${encodeURIComponent(caseId)}/nicht-vorhanden`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(nutzlast),
  });
  if (!res.ok) {
    throw new Error(await fehlerText(res));
  }
  toast.success("Gespeichert");
}

/**
 * P13: the advisor hands in documents that arrived for a Nachforderung.
 */
export async function dokumenteSenden(
  caseId: string,
  nachforderungId: string,
  dateien: File[],
): Promise<void> {
  if (!BASE) {
    toast("Demo-Modus: nicht gespeichert");
    return;
  }
  const anhaenge = await Promise.all(
    dateien.map(async (datei) => ({
      dateiname: datei.name,
      text: await datei.text(),
    })),
  );
  const res = await fetch(`${BASE}/faelle/${encodeURIComponent(caseId)}/dokumente`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ anhaenge, nachforderung_id: nachforderungId }),
  });
  if (!res.ok) {
    // The backend answers a document it does not know (Vorführmodus, no model
    // connection) with 409 and a sentence for the advisor — that sentence is the
    // whole point; a bare status code would hide it.
    throw new Error(await fehlerText(res));
  }
  toast.success("Gespeichert");
}

/**
 * P15: the advisor submits all filled guide answers in one atomic request.
 * A non-ok response means nothing was written; the German `detail` is surfaced.
 */
export async function leitfadenSenden(
  caseId: string,
  antworten: Record<string, string | number | boolean>,
): Promise<void> {
  if (!BASE) {
    toast("Demo-Modus: nicht gespeichert");
    return;
  }
  const res = await fetch(`${BASE}/faelle/${encodeURIComponent(caseId)}/leitfaden`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ antworten, von: "Beraterin" }),
  });
  if (!res.ok) {
    let detail = `Aktion fehlgeschlagen (${res.status})`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* keep fallback */
    }
    throw new Error(detail);
  }
  toast.success("Gespeichert");
}

/**
 * Gate 3: the advisor confirms the delivered Einordnung.
 * Same error pattern as leitfadenSenden — the German `detail` is surfaced.
 */
export async function gate3Senden(caseId: string): Promise<void> {
  if (!BASE) {
    toast("Demo-Modus: nicht gespeichert");
    return;
  }
  const res = await fetch(`${BASE}/faelle/${encodeURIComponent(caseId)}/gate3`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ von: "Beraterin" }),
  });
  if (!res.ok) {
    throw new Error(await fehlerText(res));
  }
  toast.success("Gespeichert");
}

/**
 * P8: the advisor marks the case for the Referat with criteria and a note.
 */
export async function referatSenden(
  caseId: string,
  nutzlast: { kriterien: string[]; notiz: string },
): Promise<void> {
  if (!BASE) {
    toast("Demo-Modus: nicht gespeichert");
    return;
  }
  const res = await fetch(`${BASE}/faelle/${encodeURIComponent(caseId)}/referat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(nutzlast),
  });
  if (!res.ok) {
    throw new Error(await fehlerText(res));
  }
  toast.success("Gespeichert");
}

/**
 * C3 / Akt 2: re-read the Prüfschema after the jurist edited the schema file
 * in a plain text editor beside the screen. Empty body, same error pattern
 * as gate3Senden — the backend answers a broken edit with a German sentence.
 */
export async function neuPruefenSenden(caseId: string): Promise<void> {
  if (!BASE) {
    toast("Demo-Modus: nicht gespeichert");
    return;
  }
  const res = await fetch(`${BASE}/faelle/${encodeURIComponent(caseId)}/neu-pruefen`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!res.ok) {
    throw new Error(await fehlerText(res));
  }
  toast.success("Gespeichert");
}

/** Reads the German `detail` from a failed response body. */
async function fehlerText(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    /* keep fallback */
  }
  return `Aktion fehlgeschlagen (${res.status})`;
}

/** Ticket fields as they stand in a `ticket.json` from the Eingang. */
export type NeuerFallTicket = {
  kanal?: string;
  ticket_nr?: string | null;
  thema?: string | null;
  anbieter?: string | null;
  branche?: string | null;
  eingegangen_am?: string | null;
  freitext?: string;
  identitaet?: Record<string, string | null>;
};

export type DemoAnhang = { dateiname: string; text: string };

/** One prepared case as `GET /demo/faelle` lists it — payload-ready. */
export type DemoFall = NeuerFallTicket & {
  fall: string;
  nr: number;
  anhaenge: DemoAnhang[];
  vorbereitet: boolean;
  hinweis?: string | null;
};

/** The Eingang on stage: the prepared cases, not a file picker. */
export function demoFaelleQuery() {
  return queryOptions({
    queryKey: ["demo-faelle"],
    queryFn: () =>
      BASE ? holen<DemoFall[]>(`${BASE}/demo/faelle`) : Promise.resolve<DemoFall[]>([]),
  });
}

/**
 * Bühnenauftakt (/neu): create the case from a prepared entry — the same
 * payload `tools/demo_start.py` sends, field for field, so the prepared cache
 * answers instead of a live model. Returns the backend's case id; the caller
 * navigates there.
 */
export async function fallAnlegen(
  ticket: NeuerFallTicket,
  anhaenge: DemoAnhang[],
): Promise<string> {
  if (!BASE) {
    throw new Error("Ohne Backend (VITE_API_BASE_URL) kann kein Fall angelegt werden.");
  }
  const res = await fetch(`${BASE}/faelle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      freitext: ticket.freitext ?? "",
      anhaenge,
      kanal: ticket.kanal ?? "vbs",
      ticket_nr: ticket.ticket_nr ?? null,
      thema: ticket.thema ?? null,
      anbieter: ticket.anbieter ?? null,
      branche: ticket.branche ?? null,
      eingegangen_am: ticket.eingegangen_am ?? null,
      identitaet: ticket.identitaet ?? {},
    }),
  });
  if (!res.ok) {
    // 409 carries the advisor-facing sentence for an unknown document
    // (Vorführmodus) — that sentence is the error message, not a status code.
    throw new Error(await fehlerText(res));
  }
  const body = (await res.json()) as { case_id: string };
  return body.case_id;
}

export type DemoZurueckgesetzt = {
  radar_zeilen: number;
  fitpoint_24: number;
  schema_zurueckgesetzt: boolean;
  hinweis: string;
};

/**
 * Demo beenden (33 §8 Nr. 8 as a button): the store does not forget — a
 * rehearsal that ran Gate 3 lifts FitPoint 24 to 3 and burns the Radar beat.
 * The backend re-seeds the Radar and restores the schema file from HEAD; the
 * answer carries the check number a person otherwise counts by hand.
 */
export async function demoZuruecksetzen(): Promise<DemoZurueckgesetzt> {
  if (!BASE) {
    throw new Error("Ohne Backend (VITE_API_BASE_URL) gibt es nichts zurückzusetzen.");
  }
  const res = await fetch(`${BASE}/demo/zuruecksetzen`, { method: "POST" });
  if (!res.ok) {
    throw new Error(await fehlerText(res));
  }
  return (await res.json()) as DemoZurueckgesetzt;
}
