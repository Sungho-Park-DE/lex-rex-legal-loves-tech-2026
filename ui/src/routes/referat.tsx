import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";

import { RadarView } from "@/components/referat/RadarView";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { demoZuruecksetzen, istDemoModus, radarQuery } from "@/lib/api";

export const Route = createFileRoute("/referat")({
  head: () => {
    const titel = "Referat — Muster-Radar | VZ-I Fall-Prüfer";
    const text =
      "Muster-Radar: Cluster je Anbieter und Fallgruppe, Schwellenwerte und für das Referat markierte Fälle.";
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
  component: ReferatPage,
});

function ReferatPage() {
  const { data, isPending, error } = useQuery(radarQuery());
  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      {isPending ? (
        <p className="text-sm text-muted-foreground" role="status">
          Radar wird geladen …
        </p>
      ) : error || !data ? (
        <p className="text-sm text-foreground" role="alert">
          Radar konnte nicht geladen werden.
        </p>
      ) : (
        <RadarView radar={data} />
      )}
      <DemoBeenden />
    </div>
  );
}

// Nach jeder Probe (33 §8 Nr. 8): der Store vergisst nicht. Ein Knopf statt
// zwei Befehlen — mit Rückfrage, weil ein Fehlklick während des Auftritts den
// Radar-Beat zurückdrehen würde. Ohne Backend gibt es nichts zurückzusetzen.
function DemoBeenden() {
  const queryClient = useQueryClient();
  const [laeuft, setLaeuft] = useState(false);
  if (istDemoModus) return null;

  async function zuruecksetzen() {
    setLaeuft(true);
    try {
      const antwort = await demoZuruecksetzen();
      toast.success(antwort.hinweis);
      await queryClient.invalidateQueries({ queryKey: ["radar"] });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLaeuft(false);
    }
  }

  return (
    <footer className="mt-12 flex justify-end border-t border-border pt-4">
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button variant="outline" size="sm" disabled={laeuft}>
            Demo beenden
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Demo beenden?</AlertDialogTitle>
            <AlertDialogDescription>
              Der Radar wird neu ausgesät (FitPoint 24 zurück auf 2) und die Schemadatei aus dem
              letzten Stand zurückgeholt. Die Fallakten bleiben.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Abbrechen</AlertDialogCancel>
            <AlertDialogAction onClick={() => void zuruecksetzen()}>Zurücksetzen</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </footer>
  );
}
