import { useQueryClient } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import { Quote } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { fallQuery, nichtVorhandenSenden } from "@/lib/api";
import { randKlasse, textKlasse } from "@/lib/tone";
import { cn } from "@/lib/utils";
import type { Fehlend, Hero, Lauf } from "@/types/viewmodel";

import { Ampel, ToneBadge } from "./ToneBadge";

/** Same shape as a document quote, without the Fundstelle. */
function AussageZitat({ aussage }: { aussage: string }) {
  return (
    <p className="mt-0.5 inline-flex max-w-full items-start gap-1.5 text-sm text-muted-foreground">
      <Quote className="mt-0.5 size-3 shrink-0" aria-hidden />
      <span>„{aussage}"</span>
    </p>
  );
}

function ExistiertNichtAktion({ posten }: { posten: Fehlend }) {
  const { id } = useParams({ from: "/faelle/$id" });
  const queryClient = useQueryClient();
  const [offen, setOffen] = useState(false);
  const [aussage, setAussage] = useState("");
  const [sendet, setSendet] = useState(false);

  if (!posten.dokumenttyp) return null;
  const dokumenttyp = posten.dokumenttyp;

  async function absenden() {
    if (!aussage.trim()) return;
    setSendet(true);
    try {
      await nichtVorhandenSenden(id, {
        dokumenttyp: dokumenttyp.code,
        aussage: aussage.trim(),
      });
      await queryClient.invalidateQueries({ queryKey: fallQuery(id).queryKey });
      setOffen(false);
      setAussage("");
    } catch (fehler) {
      toast.error(fehler instanceof Error ? fehler.message : String(fehler), {
        duration: 12000,
      });
      return;
    } finally {
      setSendet(false);
    }
  }

  return (
    <Dialog open={offen} onOpenChange={setOffen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="mt-2 h-auto flex-col items-start py-1.5">
          <span className="text-sm font-medium">Existiert nicht</span>
          <span className="text-sm font-normal text-muted-foreground">
            Falls die Verbraucherin sagt, dass es dieses Dokument nie gab.
          </span>
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Existiert nicht</DialogTitle>
          <DialogDescription>
            Die Verbraucherin sagt, dieses Dokument hat es nie gegeben. Der Posten wandert damit von
            der Verbraucher- auf die Unternehmensseite.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span>{posten.was}</span>
          {posten.dokumenttyp ? <ToneBadge vok={posten.dokumenttyp} /> : null}
        </div>
        <Textarea
          value={aussage}
          onChange={(e) => setAussage(e.target.value)}
          required
          aria-label="Aussage der Verbraucherin"
          placeholder="Aussage der Verbraucherin"
          rows={4}
        />
        <DialogFooter>
          <Button type="button" onClick={absenden} disabled={sendet || aussage.trim().length === 0}>
            Absenden
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function FehlendListe({
  titel,
  items,
  mitExistiertNicht = false,
  vollstaendig = false,
}: {
  titel: string;
  items: Fehlend[];
  mitExistiertNicht?: boolean;
  vollstaendig?: boolean;
}) {
  return (
    <div>
      <h4 className="text-sm font-medium text-foreground">{titel}</h4>
      {items.length === 0 ? (
        <p className="mt-1 text-sm text-muted-foreground">
          {vollstaendig ? "Vollständig — nichts offen." : "Nichts offen."}
        </p>
      ) : (
        <ul className="mt-1 space-y-2">
          {items.map((f, i) => {
            const aussage = f.aussage ?? null;
            return (
              <li key={`${f.was}-${i}`} className="text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span>{f.was}</span>
                  {f.dokumenttyp ? <ToneBadge vok={f.dokumenttyp} /> : null}
                  {f.fehlzustand ? <ToneBadge vok={f.fehlzustand} /> : null}
                </div>
                {f.fehlzustand?.code === "existiert_nicht" && aussage ? (
                  <AussageZitat aussage={aussage} />
                ) : null}
                <p className="text-sm text-muted-foreground">{f.grund}</p>
                {/*
                  Die „Weg:"-Zeile ist raus (Sungho, 26. Aug). Sie stand unter
                  jedem fehlenden Posten und sagte der Beraterin, was sie ohnehin
                  tut — der Grund darüber trägt die Karte, der Beschaffungsweg
                  verdoppelte nur die Höhe.

                  `beschaffungsweg` bleibt im Schema und im View Model; die
                  Anweisung „nie als Nachforderung beim Verbraucher" ist nicht
                  gelöscht, sie steht nur nicht mehr auf dem Schirm. Wer sie
                  zurückholen will, braucht genau diese vier Zeilen.
                */}
                {mitExistiertNicht && f.dokumenttyp && f.fehlzustand?.code !== "existiert_nicht" ? (
                  <ExistiertNichtAktion posten={f} />
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export function HeroCard({
  hero,
  laeufe,
  onGate3,
}: {
  hero: Hero;
  laeufe?: Lauf[];
  onGate3: () => void | Promise<void>;
}) {
  const { einordnung, vollstaendigkeit } = hero;
  const [sendetGate3, setSendetGate3] = useState(false);
  const aktuellerLauf = (laeufe ?? []).find((l) => l.aktuell) ?? null;
  const bestaetigt = Boolean(aktuellerLauf?.gate3_bestaetigt && aktuellerLauf?.gate3_gueltig);

  async function gate3() {
    setSendetGate3(true);
    try {
      await onGate3();
    } finally {
      setSendetGate3(false);
    }
  }
  return (
    <section
      aria-labelledby="einordnung-titel"
      className={cn("rounded border-2 bg-card", randKlasse(einordnung.tone))}
    >
      <div className="grid gap-4 px-4 py-4 md:grid-cols-2">
        <div>
          <h2
            id="einordnung-titel"
            className="text-sm font-semibold uppercase tracking-wide text-muted-foreground"
          >
            Einordnung
          </h2>
          <p className="mt-2 flex items-start gap-2">
            <Ampel tone={einordnung.tone} className="mt-1.5" />
            <span className={cn("text-lg font-semibold leading-snug", textKlasse(einordnung.tone))}>
              {einordnung.label}
            </span>
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={bestaetigt || sendetGate3}
              onClick={() => void gate3()}
            >
              Einordnung bestätigen
            </Button>
            {bestaetigt ? (
              <span className="text-sm text-muted-foreground">Einordnung bestätigt</span>
            ) : null}
          </div>
          <div className="mt-3 space-y-2">
            {hero.plain.map((satz, i) => (
              <p key={i} className="text-sm text-foreground">
                {satz}
              </p>
            ))}
          </div>
        </div>

        <div className="space-y-3 md:border-l md:border-border md:pl-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Vollständigkeit
          </h3>
          <FehlendListe
            titel="Verbraucherseite"
            items={vollstaendigkeit.verbraucher}
            mitExistiertNicht
            vollstaendig={vollstaendigkeit.vollstaendig_verbraucherseite}
          />
          <FehlendListe titel="Unternehmensseite" items={vollstaendigkeit.unternehmen} />
        </div>
      </div>

      {hero.pruefumfang.length > 0 ? (
        <div className="border-t border-border px-4 py-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Prüfumfang
          </h3>
          <ul className="mt-2 space-y-2">
            {hero.pruefumfang.map((p) => (
              <li key={p.pruefpunkt_id} className="text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  {/* `pruefpunkt_id` ist der Schluessel (key), keine Anzeige —
                      der Titel steht ohnehin daneben. Bis 26. Aug las die
                      Beraterin hier „P8d · Laufzeit und Verlaengerung". */}
                  <span className="font-medium">{p.titel}</span>
                  <ToneBadge vok={p.zustand} withDot />
                </div>
                <p className="text-sm text-muted-foreground">{p.text}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
