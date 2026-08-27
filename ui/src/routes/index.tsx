import { createFileRoute, redirect } from "@tanstack/react-router";

// The Fall-Prüfer has exactly two screens; / opens the first case file.
export const Route = createFileRoute("/")({
  beforeLoad: () => {
    throw redirect({ to: "/faelle/$id", params: { id: "F-2026-0001" } });
  },
  head: () => {
    const titel = "VZ-I Fall-Prüfer — Fallakte";
    const text =
      "Fall-Prüfer der Verbraucherzentrale: Fallakte mit Einordnung, Prüfpfad und Musterbrief.";
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
});
