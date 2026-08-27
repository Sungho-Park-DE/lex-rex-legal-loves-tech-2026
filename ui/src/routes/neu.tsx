import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { demoFaelleQuery, fallAnlegen, istDemoModus } from "@/lib/api";
import { cn } from "@/lib/utils";

// Bühnenauftakt: der Eingang zeigt die vorbereiteten Fälle (GET /demo/faelle),
// die Beraterin wählt einen, das Werkzeug legt ihn an und landet auf der
// Fallakte. Kein Dateidialog — auf der Bühne wird kein Ordner durchsucht.
// Während das Werkzeug liest, läuft /ladevideo.mp4 (fehlt die Datei, steht
// stattdessen eine Textzeile). Weiter geht es erst, wenn BEIDES fertig ist —
// Video zu Ende (oder Esc) UND Antwort da. Ein 409 (unbekanntes Dokument,
// Vorführmodus) erscheint als der Satz aus dem Backend, nicht als Code.
// Über dem Video erscheinen drei Zeilen — die drei Schichten, die der POST
// wirklich durchläuft (L0 lokal, L1 Modell + Zitatprüfung, L2 Regeln), im
// Takt des Videos eingeblendet; der Haken dahinter kommt erst mit der Antwort.
export const Route = createFileRoute("/neu")({
  head: () => {
    const titel = "Neue Anfrage — VZ-I Fall-Prüfer";
    const text =
      "Einen vorbereiteten Fall aus dem Eingang wählen; das Werkzeug liest und ordnet ein.";
    return {
      meta: [
        { title: titel },
        { name: "description", content: text },
        { property: "og:title", content: titel },
        { property: "og:description", content: text },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary" },
      ],
    };
  },
  component: NeueAnfragePage,
});

type Phase = "formular" | "laden" | "fehler";

// Das Intro (public/ladevideo.mp4) ist 12 s lang; die Ladeseite soll 3 s stehen
// (Sungho, 27. Aug) — also vierfaches Tempo statt einer geschnittenen Datei.
const VIDEO_TEMPO = 4;
// Wann die drei Zeilen über dem Video erscheinen (ms nach dem Klick).
const SCHRITT_TAKT = [300, 1200, 2100];

function NeueAnfragePage() {
  const navigate = useNavigate();
  const { data: faelle, isPending, error } = useQuery(demoFaelleQuery());
  const [gewaehlt, setGewaehlt] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("formular");
  const [fehler, setFehler] = useState<string | null>(null);
  const [caseId, setCaseId] = useState<string | null>(null);
  const [videoFertig, setVideoFertig] = useState(false);
  const [videoFehlt, setVideoFehlt] = useState(false);
  const [schritt, setSchritt] = useState(0);

  const fall = faelle?.find((f) => f.fall === gewaehlt) ?? null;
  const vorbereitet = faelle?.filter((f) => f.vorbereitet).length ?? 0;

  function anlegen() {
    if (!fall) return;
    setPhase("laden");
    setVideoFertig(false);
    setCaseId(null);
    setSchritt(0);
    fallAnlegen(fall, fall.anhaenge)
      .then(setCaseId)
      .catch((e: Error) => {
        setFehler(e.message);
        setPhase("fehler");
      });
  }

  // Esc überspringt das Video (Probe); die Antwort bleibt Bedingung.
  useEffect(() => {
    if (phase !== "laden") return;
    const taste = (e: KeyboardEvent) => {
      if (e.key === "Escape") setVideoFertig(true);
    };
    window.addEventListener("keydown", taste);
    return () => window.removeEventListener("keydown", taste);
  }, [phase]);

  useEffect(() => {
    if (phase !== "laden") return;
    const timer = SCHRITT_TAKT.map((ms, i) => window.setTimeout(() => setSchritt(i + 1), ms));
    return () => timer.forEach((t) => window.clearTimeout(t));
  }, [phase]);

  useEffect(() => {
    if (phase === "laden" && caseId && videoFertig) {
      void navigate({ to: "/faelle/$id", params: { id: caseId } });
    }
  }, [phase, caseId, videoFertig, navigate]);

  if (phase === "laden") {
    const schritte = [
      "Pseudonymisiert — lokal, vor jedem Modellaufruf",
      `${fall?.anhaenge.length ?? 0} Unterlagen gelesen — das Modell; jedes Zitat wörtlich geprüft — der Code`,
      "Prüfschema angewandt, Brief gefüllt — Regeln, kein Modell",
    ];
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background px-6">
        <div className="relative">
          <ol className="absolute left-4 top-4 z-10 space-y-1 rounded-md border border-border bg-background/90 px-3 py-2 text-sm text-foreground">
            {schritte.slice(0, schritt).map((text) => (
              <li key={text} className="flex gap-2">
                <span className="w-3 text-muted-foreground">{caseId ? "✓" : "…"}</span>
                <span>{text}</span>
              </li>
            ))}
          </ol>
          {videoFehlt ? (
            <p className="animate-pulse text-lg text-foreground">Die Unterlagen werden gelesen …</p>
          ) : (
            <video
              src="/ladevideo.mp4"
              autoPlay
              muted
              playsInline
              onLoadedMetadata={(e) => {
                e.currentTarget.playbackRate = VIDEO_TEMPO;
              }}
              onEnded={() => setVideoFertig(true)}
              onError={() => {
                setVideoFehlt(true);
                setVideoFertig(true);
              }}
              className="max-h-[72vh] w-auto max-w-[86vw] rounded-md border border-border"
            />
          )}
        </div>
        <p className="max-w-xl text-center text-xs text-muted-foreground">
          {videoFertig && !caseId
            ? "Die Unterlagen werden gelesen …"
            : "Vorführmodus — vorbereitete Unterlagen. Mit Modellverbindung dauert das Lesen etwa 15–20 Sekunden je Dokument."}
        </p>
      </div>
    );
  }

  const identitaet = fall?.identitaet ?? {};

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col gap-4 bg-background px-6 py-10">
      <header>
        <h1 className="text-xl font-semibold text-foreground">Neue Anfrage</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {faelle ? `Eingang: ${faelle.length} Fälle, ${vorbereitet} davon vorbereitet. ` : ""}
          Einen wählen — das Werkzeug legt den Fall an und liest die Unterlagen.
        </p>
      </header>

      {phase === "fehler" && fehler ? (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-foreground">
          {fehler}
        </div>
      ) : null}

      {istDemoModus ? (
        <p className="text-sm text-muted-foreground">
          Ohne Backend (VITE_API_BASE_URL) gibt es keinen Eingang und keinen neuen Fall.
        </p>
      ) : null}
      {isPending && !istDemoModus ? (
        <p className="text-sm text-muted-foreground">Eingang wird geladen …</p>
      ) : null}
      {error ? <p className="text-sm text-destructive">{error.message}</p> : null}

      <ul role="radiogroup" aria-label="Vorbereitete Fälle" className="space-y-2">
        {faelle?.map((f) => (
          <li key={f.fall}>
            <button
              type="button"
              role="radio"
              aria-checked={gewaehlt === f.fall}
              disabled={!f.vorbereitet}
              onClick={() => setGewaehlt(f.fall)}
              className={cn(
                "w-full rounded-md border px-4 py-3 text-left text-sm",
                gewaehlt === f.fall ? "border-primary bg-accent" : "border-border",
                !f.vorbereitet && "cursor-not-allowed opacity-50",
              )}
            >
              <p className="font-medium text-foreground">
                Fall {String(f.nr).padStart(2, "0")} · {f.anbieter ?? f.fall}
              </p>
              <p className="text-muted-foreground">
                {f.ticket_nr ?? "—"}
                {f.eingegangen_am ? ` · ${f.eingegangen_am.slice(0, 10)}` : ""}
                {` · ${f.anhaenge.length} Anhänge`}
                {f.vorbereitet ? "" : " · nicht vorbereitet (Modellverbindung nötig)"}
              </p>
            </button>
          </li>
        ))}
      </ul>

      <div>
        <Button onClick={anlegen} disabled={!fall || istDemoModus}>
          Fall anlegen und Unterlagen lesen
        </Button>
      </div>

      {fall ? (
        <section className="rounded-md border border-border px-4 py-3 text-sm">
          {identitaet["name"] ? (
            <p className="text-muted-foreground">
              {identitaet["name"]}
              {identitaet["kundennummer"] ? ` · Kd-Nr. ${identitaet["kundennummer"]}` : ""}
            </p>
          ) : null}
          {fall.freitext ? (
            <blockquote className="mt-2 border-l-2 border-border pl-3 text-muted-foreground">
              {fall.freitext}
            </blockquote>
          ) : null}
          <ul className="mt-3 space-y-1 text-foreground">
            {fall.anhaenge.map((a) => (
              <li
                key={a.dateiname}
                className="flex justify-between rounded-md border border-border px-3 py-1.5"
              >
                <span>{a.dateiname}</span>
                <span className="text-muted-foreground">
                  {(a.text.length / 1024).toFixed(1)} kB
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
