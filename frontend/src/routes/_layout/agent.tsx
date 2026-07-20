import { createFileRoute } from "@tanstack/react-router"

import AgentChat from "@/components/Agent/AgentChat"

export const Route = createFileRoute("/_layout/agent")({
  component: AgentChat,
  head: () => ({
    meta: [
      {
        title: "Agent - FastAPI Template",
      },
    ],
  }),
})
