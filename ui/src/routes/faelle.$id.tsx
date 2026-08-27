import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState, type MouseEvent } from "react";
import { toast } from "sonner";

import { AbschlussPanel } from "@/components/fallakte/AbschlussPanel";
import { BeratungshinweisePanel } from "@/components/fallakte/BeratungshinweisePanel";
import { DokumentViewer, type ViewerZiel } from "@/components/fallakte/DokumentViewer";
import { FallakteHeader } from "@/components/fallakte/FallakteHeader";
import { Fusszeile } from "@/components/fallakte/Fusszeile";
import { HeroCard } from "@/components/fallakte/HeroCard";
import { LaeufeTimeline } from "@/components/fallakte/LaeufeTimeline";
import { LeitfadenPanel } from "@/components/fallakte/LeitfadenPanel";
import { MusterbriefPreview } from "@/components/fallakte/MusterbriefPreview";
import { ZuordnungsvorschlaegePanel } from "@/components/fallakte/ZuordnungsvorschlaegePanel";
import { LeerHinweis, Panel } from "@/components/fallakte/Panel";
import { NachforderungenPanel } from "@/components/fallakte/NachforderungenPanel";
import { OffenePunkte } from "@/components/fallakte/OffenePunkte";
import { ProtokollPanel } from "@/components/fallakte/ProtokollPanel";
import { Pruefpfad } from "@/components/fallakte/Pruefpfad";
import { ReferatPanel } from "@/components/fallakte/ReferatPanel";
import { StepRail, type StepDef } from "@/components/fallakte/StepRail";
import { ViewerProvider } from "@/components/fallakte/viewer-context";
import { punktKlasse } from "@/lib/tone";
import { cn } from "@/lib/utils";
import {
  aktionSenden,
  dokumenteSenden,
  fallQuery,
  gate3Senden,
  leitfadenSenden,
  neuPruefenSenden,
  referatSenden,
} from "@/lib/api";
import type { Zitat } from "@/types/viewmodel";

export const Route = createFileRoute("/faelle/$id")({
  head: ({ params }) => {
    const titel = `Fallakte ${params.id} — VZ-I Fall-Prüfer`;
    const text =
      "Fallakte mit Dokumentenansicht, Einordnung, Prüfpfad und Musterbrief für die Verbraucherberatung.";
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
  component: FallaktePage,
});

function FallaktePage() {
  const { id } = Route.useParams();
  const { data, isPending, error, refetch } = useQuery(fallQuery(id));
  const [ziel, setZiel] = useState<ViewerZiel | null>(null);
  const [schritt, setSchritt] = useState(1);
  const [zielPruefpunkt, setZielPruefpunkt] = useState<string | null>(null);
  const schrittRef = useRef<HTMLDivElement>(null);

  // Die Dokumentspalte trägt 36 % der Bildbreite und war auf allen achtzehn
  // Aufnahmen der Publish-Prüfung zu 97–99,8 % leer (`35` §2): unterhalb des
  // Ticket-Texts steht dort nichts mehr, während Schritt 4 für 1080 px Schirm
  // 5830 px Seitenhöhe braucht. Ab Schritt 4 wird gelesen, was das Programm
  // gefunden hat — nicht mehr im Dokument geblättert. Also: bis Schritt 3
  // offen, danach zu. `null` heißt „folge dem Schritt"; sobald jemand selbst
  // schaltet, gilt seine Wahl — bis er den Schritt wechselt.
  const [dokSpalte, setDokSpalte] = useState<boolean | null>(null);
  const dokOffen = dokSpalte ?? schritt <= 3;
  useEffect(() => setDokSpalte(null), [schritt]);

  const zeigeZitat = useCallback((z: Zitat) => {
    setZiel({ dok_id: z.dok_id, seite: z.seite, zitat: z.zitat });
    // Ein Klick auf ein Zitat verlangt das Dokument — sonst zeigt der
    // Klick-auf-die-Fundstelle-Beat auf eine eingeklappte Spalte.
    setDokSpalte(true);
  }, []);

  const onDokumentWechsel = useCallback((dokId: string) => {
    setZiel({ dok_id: dokId, seite: 0, zitat: "" });
  }, []);

  const senden = async (
    aktion: Parameters<typeof aktionSenden>[1],
    nutzlast?: Record<string, unknown>,
  ) => {
    try {
      await aktionSenden(id, aktion, nutzlast);
    } catch (fehler) {
      toast.error(fehler instanceof Error ? fehler.message : String(fehler));
      return;
    }
    await refetch();
  };

  const neuPruefen = async () => {
    try {
      await neuPruefenSenden(id);
    } catch (fehler) {
      toast.error(fehler instanceof Error ? fehler.message : String(fehler), {
        duration: 12000,
      });
      return;
    }
    await refetch();
  };

  const pruefpunktIds = data
    ? [
        ...data.pruefpfad.stufen.flatMap((st) => st.pruefpunkte.map((p) => p.pruefpunkt_id)),
        ...data.pruefpfad.ableitungen.map((p) => p.pruefpunkt_id),
      ]
    : [];

  const offenePunkteKlick = (ev: MouseEvent<HTMLDivElement>) => {
    const eintrag = (ev.target as HTMLElement).closest("li");
    if (!eintrag) return;
    const text = eintrag.textContent ?? "";
    const treffer = pruefpunktIds.find((pid) => text.includes(pid));
    if (!treffer) return;
    setZielPruefpunkt(treffer);
    setSchritt(4);
  };

  useEffect(() => {
    if (schritt !== 4 || !zielPruefpunkt) return;
    const wurzel = schrittRef.current;
    if (!wurzel) return;
    const eintrag = Array.from(wurzel.querySelectorAll("li")).find((li) =>
      (li.querySelector("span")?.textContent ?? "").startsWith(zielPruefpunkt),
    );
    if (!eintrag) return;
    let eltern = eintrag.parentElement;
    while (eltern) {
      if (eltern instanceof HTMLDetailsElement) eltern.open = true;
      eltern = eltern.parentElement;
    }
    eintrag.scrollIntoView({ block: "center" });
    setZielPruefpunkt(null);
  }, [schritt, zielPruefpunkt, data]);

  if (isPending) {
    return (
      <p className="px-4 py-6 text-sm text-muted-foreground" role="status">
        Fall {id} wird geladen …
      </p>
    );
  }

  if (error || !data) {
    return (
      <p className="px-4 py-6 text-sm text-foreground" role="alert">
        Fall {id} konnte nicht geladen werden.
      </p>
    );
  }

  const schritte: StepDef[] = [
    { id: 1, name: "Einordnung" },
    { id: 2, name: "Offene Punkte & Gespräch", anzahl: data.offene_punkte.length },
    {
      id: 3,
      name: "Unterlagen",
      anzahl: data.nachforderungen.length,
      einheit: { eins: "Nachforderung", viele: "Nachforderungen" },
    },
    { id: 4, name: "Prüfpfad" },
    { id: 5, name: "Musterbrief" },
    { id: 6, name: "Abschluss" },
  ];

  return (
    <ViewerProvider value={{ zeigeZitat }}>
      <div className="mx-auto max-w-[1600px]">
        <FallakteHeader
          kopf={data.kopf}
          onBestaetigen={() =>
            void senden("fallgruppe_bestaetigen", { fallgruppe_id: data.kopf.fallgruppe.code })
          }
        />

        <div
          aria-label="Aktuelle Einordnung"
          className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-4 py-2"
        >
          <span className="flex items-center gap-2 text-sm font-medium">
            <span
              className={cn(
                "size-2.5 shrink-0 rounded-full",
                punktKlasse(data.hero.einordnung.tone),
              )}
              aria-hidden
            />
            {data.hero.einordnung.label}
          </span>
          <span className="flex flex-wrap items-center gap-2">
            {data.laeufe.map((l) => (
              <span
                key={l.run_id}
                title={l.einordnung}
                className={cn(
                  "inline-flex items-center gap-1 rounded border border-border px-1.5 text-sm leading-5",
                  l.aktuell ? "text-foreground" : "text-muted-foreground",
                )}
              >
                <span
                  className={cn("size-1.5 shrink-0 rounded-full", punktKlasse(l.einordnung_tone))}
                  aria-hidden
                />
                {l.trigger.label}
              </span>
            ))}
          </span>
        </div>

        <div
          className={cn(
            "grid gap-4 px-4 py-4",
            dokOffen
              ? "lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)_auto]"
              : "lg:grid-cols-[auto_minmax(0,1fr)_auto]",
          )}
        >
          <section aria-label="Dokumente" className="lg:sticky lg:top-4 lg:self-start">
            {dokOffen ? (
              <>
                <button
                  type="button"
                  onClick={() => setDokSpalte(false)}
                  aria-expanded
                  aria-controls="dokumentspalte"
                  className="mb-2 hidden rounded border border-border px-2 py-0.5 text-sm text-muted-foreground hover:bg-muted/60 lg:block"
                >
                  Dokumente einklappen
                </button>
                <div
                  id="dokumentspalte"
                  className="lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto lg:pr-1"
                >
                  <DokumentViewer
                    dokumente={data.dokumente}
                    ziel={ziel}
                    onDokumentWechsel={onDokumentWechsel}
                  />
                </div>
              </>
            ) : (
              <button
                type="button"
                onClick={() => setDokSpalte(true)}
                aria-expanded={false}
                aria-controls="dokumentspalte"
                className="rounded border border-border px-2 py-1 text-sm text-muted-foreground hover:bg-muted/60 lg:[writing-mode:vertical-rl]"
              >
                Dokumente ({data.dokumente.length})
              </button>
            )}
          </section>

          <div className="space-y-4" ref={schrittRef}>
            {schritt === 1 ? (
              <>
                <HeroCard
                  hero={data.hero}
                  laeufe={data.laeufe}
                  onGate3={async () => {
                    try {
                      await gate3Senden(id);
                    } catch (fehler) {
                      toast.error(fehler instanceof Error ? fehler.message : String(fehler));
                      return;
                    }
                    await refetch();
                  }}
                />
                <LaeufeTimeline laeufe={data.laeufe} />
                <ZuordnungsvorschlaegePanel
                  vorschlaege={data.kopf.fallgruppe_vorschlaege}
                  bestaetigt={data.kopf.fallgruppe_bestaetigt}
                  beleg={data.kopf.fallgruppe_beleg}
                />
              </>
            ) : null}

            {schritt === 2 ? (
              <>
                <div onClick={offenePunkteKlick}>
                  <OffenePunkte punkte={data.offene_punkte} />
                </div>
                <LeitfadenPanel
                  leitfaden={data.leitfaden}
                  onAntworten={async (antworten) => {
                    try {
                      await leitfadenSenden(id, antworten);
                    } catch (fehler) {
                      toast.error(fehler instanceof Error ? fehler.message : String(fehler));
                      throw fehler;
                    }
                    await refetch();
                  }}
                />
                <BeratungshinweisePanel hinweise={data.beratungshinweise ?? []} />
              </>
            ) : null}

            {schritt === 3 ? (
              <NachforderungenPanel
                nachforderungen={data.nachforderungen}
                onErzeugen={() => void senden("nachforderung_erzeugen")}
                onMarkieren={(nid, status) =>
                  void senden("nachforderung_markieren", { nachforderung_id: nid, status })
                }
                onDokumente={async (nid, dateien) => {
                  try {
                    await dokumenteSenden(id, nid, dateien);
                  } catch (fehler) {
                    toast.error(fehler instanceof Error ? fehler.message : String(fehler), {
                      duration: 12000,
                    });
                    return;
                  }
                  await refetch();
                }}
              />
            ) : null}

            {schritt === 4 ? (
              <Pruefpfad pruefpfad={data.pruefpfad} onNeuPruefen={() => void neuPruefen()} />
            ) : null}

            {schritt === 5 ? (
              data.musterbrief ? (
                <MusterbriefPreview
                  musterbrief={data.musterbrief}
                  onRechtsbehelf={(rid) =>
                    void senden("rechtsbehelf_waehlen", { rechtsbehelf_id: rid })
                  }
                />
              ) : (
                <Panel id="musterbrief" titel="Musterbrief">
                  <LeerHinweis>Für diese Einordnung liegt kein Schreiben vor.</LeerHinweis>
                </Panel>
              )
            ) : null}

            {schritt === 6 ? (
              <>
                <ReferatPanel
                  referat={data.referat}
                  onMarkieren={async (nutzlast) => {
                    try {
                      await referatSenden(id, nutzlast);
                    } catch (fehler) {
                      toast.error(fehler instanceof Error ? fehler.message : String(fehler));
                      return;
                    }
                    await refetch();
                  }}
                />
                <AbschlussPanel
                  abschluss={data.abschluss}
                  onBasisExport={() => void senden("abschluss", { basis_export: true })}
                  onAbschluss={() => void senden("abschluss", { schliessen: true })}
                />
                <ProtokollPanel protokoll={data.protokoll} />
              </>
            ) : null}
          </div>

          <StepRail schritte={schritte} aktiv={schritt} onWechsel={setSchritt} />
        </div>

        <Fusszeile fusszeile={data.fusszeile} />
      </div>
    </ViewerProvider>
  );
}
