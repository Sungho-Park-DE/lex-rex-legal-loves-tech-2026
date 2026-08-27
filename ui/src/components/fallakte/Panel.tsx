import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Panel({
  titel,
  aktion,
  children,
  className,
  id,
}: {
  titel: string;
  aktion?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <section
      id={id}
      aria-labelledby={id ? `${id}-titel` : undefined}
      className={cn("rounded border border-border bg-card", className)}
    >
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2.5">
        <h2 id={id ? `${id}-titel` : undefined} className="text-sm font-semibold text-foreground">
          {titel}
        </h2>
        {aktion}
      </header>
      <div className="px-4 py-3 text-sm">{children}</div>
    </section>
  );
}

export function LeerHinweis({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted-foreground">{children}</p>;
}
