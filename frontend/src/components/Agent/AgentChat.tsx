import { Plus, Send } from "lucide-react"
import { useState } from "react"

import { AgentsService, ApiError } from "@/client"
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

export default function AgentChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [preference, setPreference] = useState("")
  const [preferencesToSave, setPreferencesToSave] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function queuePreference() {
    const text = preference.trim()
    if (!text) return
    setPreferencesToSave((saved) =>
      saved.some(
        (value) => value.toLocaleLowerCase() === text.toLocaleLowerCase(),
      )
        ? saved
        : [...saved, text],
    )
    setPreference("")
  }

  async function send() {
    const prompt = input.trim()
    if (!prompt || loading) return
    setError(null)
    setInput("")
    setMessages((m) => [...m, { role: "user", content: prompt }])
    setLoading(true)
    try {
      const data = await AgentsService.chat({
        requestBody: {
          prompt,
          context: messages,
          preferences_to_save: preferencesToSave,
        },
      })
      setPreferencesToSave([])
      setMessages((m) => [...m, { role: "assistant", content: data.reply }])
    } catch (error) {
      if (error instanceof ApiError && error.status === 503) {
        setError("Agent not configured — set ANTHROPIC_API_KEY on the backend.")
      } else {
        setError(
          error instanceof Error ? error.message : "Something went wrong",
        )
      }
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
            Ask the agent anything. Conversation context stays in this browser
            and is not saved by the server.
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={m.role === "user" ? "text-right" : "text-left"}
          >
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
        {loading && <p className="text-sm text-muted-foreground">Thinking…</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </CardContent>
      <CardFooter className="flex-col gap-3">
        <div className="w-full rounded-md border p-3">
          <p className="text-sm font-medium">Save a preference</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Only save preferences you want used in future conversations. Do not
            include patient, health, or other personal data.
          </p>
          <div className="mt-2 flex gap-2">
            <Input
              aria-label="Preference to save"
              value={preference}
              onChange={(e) => setPreference(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault()
                  queuePreference()
                }
              }}
              placeholder="For example: I prefer concise answers"
              disabled={loading}
            />
            <Button
              type="button"
              variant="secondary"
              onClick={queuePreference}
              disabled={loading || !preference.trim()}
            >
              <Plus />
              Save preference
            </Button>
          </div>
          {preferencesToSave.length > 0 && (
            <p className="mt-2 text-xs text-muted-foreground">
              {preferencesToSave.length} preference
              {preferencesToSave.length === 1 ? "" : "s"} will be saved with
              your next request.
            </p>
          )}
        </div>
        <div className="flex w-full gap-2">
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
          <Button
            onClick={() => void send()}
            disabled={loading || !input.trim()}
          >
            <Send />
            Send
          </Button>
        </div>
      </CardFooter>
    </Card>
  )
}
