import { Send } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"

type ChatMessage = { role: "user" | "assistant"; content: string }

const API_BASE = import.meta.env.VITE_API_URL ?? ""

/**
 * Minimal chat surface for the agent API. POSTs to /api/v1/agents/chat with the
 * stored access token; the backend persists multi-turn history keyed by the
 * conversation_id it returns, so follow-up messages keep context. Shows a clear
 * message when the agent is not configured (503).
 */
export default function AgentChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function send() {
    const prompt = input.trim()
    if (!prompt || loading) return
    setError(null)
    setInput("")
    setMessages((m) => [...m, { role: "user", content: prompt }])
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/v1/agents/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
        },
        body: JSON.stringify({ prompt, conversation_id: conversationId }),
      })
      if (res.status === 503) {
        throw new Error(
          "Agent not configured — set ANTHROPIC_API_KEY on the backend.",
        )
      }
      if (!res.ok) throw new Error(`Request failed (${res.status})`)
      const data = (await res.json()) as {
        reply: string
        conversation_id: string
      }
      setConversationId(data.conversation_id)
      setMessages((m) => [...m, { role: "assistant", content: data.reply }])
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="mx-auto flex h-[70vh] w-full max-w-2xl flex-col">
      <CardHeader>
        <CardTitle>Agent</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 space-y-3 overflow-y-auto">
        {messages.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Ask the agent anything. The conversation is remembered while you stay
            on this page.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
            <span
              className={`inline-block max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${
                m.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted"
              }`}
            >
              {m.content}
            </span>
          </div>
        ))}
        {loading && (
          <p className="text-sm text-muted-foreground">Thinking…</p>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </CardContent>
      <CardFooter className="gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault()
              void send()
            }
          }}
          placeholder="Message the agent…"
          disabled={loading}
        />
        <Button onClick={() => void send()} disabled={loading || !input.trim()}>
          <Send />
          Send
        </Button>
      </CardFooter>
    </Card>
  )
}
