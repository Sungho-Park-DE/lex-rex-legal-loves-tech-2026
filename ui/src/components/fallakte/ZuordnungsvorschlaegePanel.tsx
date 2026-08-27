import { Panel } from "./Panel";
import { ToneBadge } from "./ToneBadge";
import { ZitatListe } from "./ZitatLink";
import type { FallgruppeVorschlag, Zitat } from "@/types/viewmodel";

export function ZuordnungsvorschlaegePanel({
  vorschlaege,
  bestaetigt,
  beleg,
}: {
  vorschlaege: FallgruppeVorschlag[];
  bestaetigt: boolean;
  beleg?: Zitat | null;
}) {
  if (vorschlaege.length === 0) return null;
  return (
    <Panel
      titel={`Zuordnungsvorschläge (${vorschlaege.length})`}
      aktion={
        <span className="text-sm text-muted-foreground">
          {bestaetigt ? "bestätigt" : "nicht bestätigt"}
        </span>
      }
    >
      <ul className="space-y-3">
        {vorschlaege.map((v, i) => (
          <li key={`${v.fallgruppe.code}-${i}`} className="text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{v.fallgruppe.label}</span>
              <ToneBadge vok={v.stufe} />
            </div>
            <p className="mt-0.5 text-muted-foreground">{v.begruendung}</p>
            <ZitatListe zitate={v.zitate} />
            {/* 1.14: Der Vorschlag entsteht aus dem Freitext — das Modell sieht
                die Dokumente nicht. Erst nach Gate 2 liegt der Satz aus dem
                Erhoehungsschreiben vor, auf den sich das Studio beruft. Kein
                Ersatz fuer `null`: dann faellt die Zeile weg. */}
            {i === 0 && beleg ? (
              <div className="mt-1">
                <p className="text-sm text-muted-foreground">Beleg aus den Unterlagen:</p>
                <ZitatListe zitate={[beleg]} />
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </Panel>
  );
}
