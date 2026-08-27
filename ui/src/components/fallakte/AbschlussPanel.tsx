import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import type { Abschluss } from "@/types/viewmodel";

import { Panel } from "./Panel";

export function AbschlussPanel({
  abschluss,
  onBasisExport,
  onAbschluss,
}: {
  abschluss: Abschluss;
  onBasisExport: () => void;
  onAbschluss: () => void;
}) {
  return (
    <Panel
      id="abschluss"
      titel="Abschluss"
      aktion={
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={onBasisExport}
            disabled={abschluss.basis_export_erzeugt}
          >
            {abschluss.basis_export_erzeugt ? "Basis-Eintrag erzeugt" : "Basis-Eintrag erzeugen"}
          </Button>
          <Button size="sm" variant="outline" onClick={onAbschluss} disabled={abschluss.geschlossen}>
            {abschluss.geschlossen ? "geschlossen" : "Fall abschließen"}
          </Button>
        </div>
      }
    >
      <p className="text-sm text-muted-foreground">
        Basis-Export {abschluss.basis_export_erzeugt ? "erzeugt" : "nicht erzeugt"} ·{" "}
        {abschluss.geschlossen ? "Fall geschlossen" : "Fall offen"}
      </p>
      {abschluss.basis_text ? (
        <div className="mt-2">
          <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded border border-border px-3 py-2 font-sans text-sm leading-relaxed">
            {abschluss.basis_text}
          </pre>
          <Button
            size="sm"
            variant="ghost"
            className="mt-2"
            onClick={() => {
              void navigator.clipboard
                .writeText(abschluss.basis_text ?? "")
                .then(() => toast.success("Kopiert"))
                .catch(() => toast.error("Kopieren fehlgeschlagen"));
            }}
          >
            Kopieren
          </Button>
        </div>
      ) : null}
      {abschluss.wiedervorlagen.length > 0 ? (
        <ul className="mt-2 space-y-1">
          {abschluss.wiedervorlagen.map((w, i) => (
            <li key={i} className="text-sm">
              {w}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">Keine Wiedervorlage.</p>
      )}
    </Panel>
  );
}
