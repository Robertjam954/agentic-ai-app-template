# The agentic layer

This template is the [full-stack FastAPI template](https://github.com/fastapi/full-stack-fastapi-template)
(FastAPI + SQLModel + PostgreSQL + React + Traefik) with a complete, provider-clean
agent layer added on top. Everything the base template does still works; the agent
stays dormant until you give it an API key. It ships **one part for every component
category** in the portfolio agentic-app prep workflow, so a new project starts with
nothing missing — you replace the examples with real logic.

## Component map

| Category | Where it lives |
|----------|----------------|
| **Infra & DB** | Postgres + SQLModel (`backend/app/models.py`), Alembic (`backend/app/alembic/`), Docker `compose*.yml` + Traefik, config `backend/app/core/config.py`, `.env` |
| **Agents** | single loop `backend/app/agents/service.py`; multi-agent supervisor `backend/app/agents/orchestrator.py` |
| **Tools** | `backend/app/agents/tools.py` (registry + per-agent subsets) |
| **Memory** | `backend/app/agents/memory.py` + `Conversation`/`ConversationMessage` tables (multi-turn; in-memory fallback) |
| **Prompts** | `backend/app/agents/prompts.py` (default + per-role registry) |
| **Frontend** | `frontend/src/components/Agent/AgentChat.tsx` + route `frontend/src/routes/_layout/agent.tsx` + sidebar link |
| **Tracing** | `backend/app/agents/tracing.py` (structured logs always; Sentry spans when `SENTRY_DSN` set; LangSmith/OTel hook) |
| **Provider** | `backend/app/agents/client.py` (Anthropic client factory; `is_configured()` gates the API) |

## API

```
GET  /api/v1/agents/health       -> {"configured": bool}
POST /api/v1/agents/chat         -> {"reply", "conversation_id"}          (auth)
POST /api/v1/agents/orchestrate  -> {"reply", "conversation_id", "worker"} (auth)
```

Pass a `conversation_id` to continue a conversation; omit it to start one (the
response returns the new id). Turns are persisted to the `Conversation` tables.

## Configure

Set in `.env` (top level):

```
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-opus-4-8
TRACING_ENABLED=true          # structured logs; Sentry spans if SENTRY_DSN set
# LANGCHAIN_TRACING_V2=        # optional LangSmith/OTel exporter hook
```

With no key the app boots normally and the agent endpoints return `503`.

## Extend each part

- **Tool:** add a `(schema, handler)` entry to `TOOLS` in `tools.py`; the loop and
  orchestrator discover it automatically. Assign it to a worker via `WORKERS`.
- **Worker agent:** add to `WORKERS` in `orchestrator.py` (role prompt + tool subset);
  add the prompt to `prompts.py`.
- **Memory:** `memory.py` persists text turns; extend with summarization or a
  retrieval/vector store for long-term memory.
- **Prompts:** keep them in `prompts.py` (or load `.md` files) — out of the request path.
- **Tracing:** `tracing.trace(op, name, **data)` wraps any unit of work; wire a
  LangSmith/OTel exporter behind `LANGCHAIN_TRACING_V2` without touching call sites.
- **Frontend:** `AgentChat.tsx` calls `/agents/chat`; add streaming or a conversation
  list as the product grows.

## Why this shape

Provider setup lives in exactly one place (`client.py`) so swapping models or
providers never touches routes or business logic. Prompts, tools, memory, and
tracing are each isolated modules, so a project can deepen or drop any one without
disturbing the others. See the repo's `claude-api` guidance for model IDs, tool-use,
and pricing. For multi-agent patterns beyond the built-in supervisor, `orchestrator.py`
is the swap point for LangGraph or the Microsoft Agent Framework.
