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
| **Tools** | `backend/app/agents/tools.py` (registry + per-agent subsets + request-scoped access) |
| **Memory** | `backend/app/agents/memory.py`; browser-held transient context plus explicit `UserPreference` records |
| **Prompts** | `backend/app/agents/prompts.py` (default + per-role registry) |
| **Frontend** | `frontend/src/components/Agent/AgentChat.tsx` + route `frontend/src/routes/_layout/agent.tsx` + sidebar link |
| **Tracing** | `backend/app/agents/tracing.py` (structured logs always; Sentry spans when `SENTRY_DSN` set; LangSmith/OTel hook) |
| **Provider** | `backend/app/agents/client.py` (Anthropic client factory; `is_configured()` gates the API) |

## API

```
GET  /api/v1/agents/health       -> {"configured": bool}
POST /api/v1/agents/chat         -> {"reply"}                              (auth)
POST /api/v1/agents/orchestrate  -> {"reply", "worker"}                    (auth)
```

Both endpoints accept `context`, an array of `{role, content}` turns retained by
the client and sent again for each request. The backend never persists it,
transcripts, messages, or conversation IDs. It retains the supplied context until
the selected model's context window is nearly full, then drops only the oldest
turns needed to reserve completion tokens. Capacity comes from the model registry
(`claude-*` defaults) or the `LLM_CONTEXT_WINDOW_TOKENS` override; the completion
reserve is `LLM_CONTEXT_OUTPUT_RESERVE_TOKENS` (at least `LLM_MAX_TOKENS`). A
separate `preferences_to_save` array accepts up to 20 explicit preference strings
(each at most 500 characters); it is batch-deduplicated in one transaction and is
the only agent data stored in the local database.

The UI keeps the preference control separate from chat text and warns users never
to save patient, health, or other personal data. Preference values are provided to
the model as escaped, untrusted data in a fixed trust boundary—not as instructions.

## Configure

Set in `.env` (top level):

```
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-opus-4-8
LLM_CONTEXT_WINDOW_TOKENS= # optional override for an unregistered model
LLM_CONTEXT_OUTPUT_RESERVE_TOKENS=4096
TRACING_ENABLED=true          # structured logs; Sentry spans if SENTRY_DSN set
# LANGCHAIN_TRACING_V2=        # optional LangSmith/OTel exporter hook
```

With no key the app boots normally and the agent endpoints return `503`.

## Extend each part

- **Tool:** add a `(schema, handler)` entry to `TOOLS` in `tools.py`; the loop and
  orchestrator discover it automatically. Handlers receive an optional
  `ToolContext` with the authenticated user and database session for
  authorization-aware application capabilities. Assign a tool to a worker via
  `WORKERS`.
- **Worker agent:** add to `WORKERS` in `orchestrator.py` (role prompt + tool subset);
  add the prompt to `prompts.py`.
- **Memory:** transient context must stay client-held. `memory.py` persists only
  explicitly selected `UserPreference` text. Do not add transcript, conversation,
  message, or patient-data persistence.
- **Prompts:** keep them in `prompts.py` (or load `.md` files) — out of the request path.
- **Tracing:** `tracing.trace(op, name, **data)` wraps any unit of work; wire a
  LangSmith/OTel exporter behind `LANGCHAIN_TRACING_V2` without touching call sites.
- **Frontend:** `AgentChat.tsx` calls `/agents/chat`; preserve the explicit
  preference control and privacy warning when adding streaming or UI features.

## Why this shape

Provider setup lives in exactly one place (`client.py`) so swapping models or
providers never touches routes or business logic. Prompts, tools, memory, and
tracing are each isolated modules, so a project can deepen or drop any one without
disturbing the others. See the repo's `claude-api` guidance for model IDs, tool-use,
and pricing. For multi-agent patterns beyond the built-in supervisor, `orchestrator.py`
is the swap point for LangGraph or the Microsoft Agent Framework.
