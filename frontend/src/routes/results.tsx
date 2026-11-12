import { createFileRoute } from "@tanstack/react-router"

import { ResultsDashboard } from "@/components/Results/ResultsDashboard"

export const Route = createFileRoute("/results")({
  component: ResultsDashboard,
  head: () => ({
    meta: [
      {
        title: "field — clinical note eval",
      },
    ],
    links: [
      { rel: "preconnect", href: "https://fonts.googleapis.com" },
      {
        rel: "preconnect",
        href: "https://fonts.gstatic.com",
        crossOrigin: "anonymous",
      },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600&family=Space+Mono:wght@400;700&display=swap",
      },
    ],
  }),
})
