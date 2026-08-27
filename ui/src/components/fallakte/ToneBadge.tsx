import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { chipKlasse, punktKlasse } from "@/lib/tone";
import { cn } from "@/lib/utils";
import { Info } from "lucide-react";
import type { Vok } from "@/types/viewmodel";

interface Props {
  vok: Vok;
  detail?: string | null;
  className?: string;
  withDot?: boolean;
}

/** Renders vok.label, coloured by vok.tone. Never maps codes to text. */
export function ToneBadge({ vok, detail, className, withDot = false }: Props) {
  const text = detail ?? vok.detail ?? null;

  if (!text) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-sm leading-5",
          chipKlasse(vok.tone),
          className,
        )}
      >
        {withDot ? (
          <span className={cn("size-2 shrink-0 rounded-full", punktKlasse(vok.tone))} aria-hidden />
        ) : null}
        {vok.label}
      </span>
    );
  }

  return (
    <Popover>
      <PopoverTrigger
        className={cn(
          "inline-flex cursor-pointer items-center gap-1.5 rounded border px-2 py-0.5 text-sm leading-5",
          chipKlasse(vok.tone),
          className,
        )}
        title={text}
      >
        {withDot ? (
          <span className={cn("size-2 shrink-0 rounded-full", punktKlasse(vok.tone))} aria-hidden />
        ) : null}
        {vok.label}
        <Info className="size-4 shrink-0 opacity-90" aria-hidden />
      </PopoverTrigger>
      <PopoverContent className="w-80 text-sm">{text}</PopoverContent>
    </Popover>
  );
}

export function Ampel({ tone, className }: { tone: Vok["tone"]; className?: string }) {
  return (
    <span
      className={cn("inline-block size-3.5 shrink-0 rounded-full", punktKlasse(tone), className)}
      aria-hidden
    />
  );
}
