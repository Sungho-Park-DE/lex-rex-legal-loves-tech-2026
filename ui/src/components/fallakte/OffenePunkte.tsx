import type { OffenerPunkt } from "@/types/viewmodel";

import { Panel, LeerHinweis } from "./Panel";
import { ToneBadge } from "./ToneBadge";

export function OffenePunkte({ punkte }: { punkte: OffenerPunkt[] }) {
  return (
    <Panel id="offene-punkte" titel="Offene Punkte">
      {punkte.length === 0 ? (
        <LeerHinweis>Keine offenen Punkte.</LeerHinweis>
      ) : (
        <ul className="space-y-3">
          {punkte.map((p, i) => (
            <li key={i}>
              <div className="flex flex-wrap items-center gap-2">
                <ToneBadge vok={p.art} withDot />
                {p.quelle ? <ToneBadge vok={p.quelle} /> : null}
                {/* 1.13: `pruefpunkt_id` ist der Schluessel, `pruefpunkt_titel` die
                    Anzeige. Kein Rueckfall auf die ID — bis 26. Aug stand hier „P8d". */}
                {p.pruefpunkt_titel ? (
                  <span className="text-sm text-muted-foreground">{p.pruefpunkt_titel}</span>
                ) : null}
              </div>
              <p className="mt-1">{p.text}</p>
              {p.feld_label ? (
                <p className="text-sm text-muted-foreground">Feld: {p.feld_label}</p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
