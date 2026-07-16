# The agentic layer

This template is the [full-stack FastAPI template](https://github.com/fastapi/full-stack-fastapi-template)
(FastAPI + SQLModel + PostgreSQL + React + Traefik) with a small, provider-clean
agent layer added on top. Everything the base template does still works; the
agent is an optional module that stays dormant until you give it an API key.

## Where it lives

```
backend/app/agents/
  client.py    Anthropic client factory; is_configured() gates the API on the key
  tools.py     tool registry: JSON schema + Python handler per tool
  service.py   the tool-using agent loop (call model -> run tools -> repeat)
backend/app/api/routes/agents.py
               GET  /api/v1/agents/health   -> {"configured": bool}
               POST /api/v1/agents/chat      -> {"reply": str}   (auth required)
```

## Configure

Set in `.env` (top level):

```
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-opus-4-8
```

With no key the app boots normally and the agent endpoints return `503`.

## Add a capability

1. Write an async handler and append a `(schema, handler)` entry to `TOOLS` in
   `backend/app/agents/tools.py`. Real tools can query the DB (`app.models`),
   call external APIs, or run computations.
2. That's it - `service.py` discovers the tool and Claude can call it. No route
   or loop changes needed.

## Extend the loop

`service.py` implements the canonical pattern: send messages, execute requested
tools, feed results back, repeat to a step cap. Natural extensions: streaming
responses, persisted conversation history (a `Conversation` model), per-user
rate/cost limits, or routing to multiple specialized sub-agents.

## Why Anthropic + why this shape

The scaffold keeps provider setup in exactly one place (`client.py`) so swapping
models or providers never touches routes or business logic. See the repo's
`claude-api` guidance for model IDs, tool-use, and pricing.
