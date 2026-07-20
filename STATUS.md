# Status

Checklist for an agentic app built from this template, one section per component
category (see the portfolio prep workflow). Boxes already checked are what the
template **ships**; the unchecked ones are what you make real for your use case.
Same checkbox format the portfolio dashboard reads, so this rolls up automatically.
If a category truly does not apply, keep the heading and add `- [x] N/A — <reason>`.

> Project: **<name>** · Framework: **FastAPI + Anthropic** · Stage: **<scaffold | build | integrate | deploy>**

## 1. Infra & databases
- [x] Postgres + SQLModel + Alembic migrations
- [x] Docker `compose*.yml` + Traefik; config in `app/core/config.py`; `.env`
- [ ] Renamed project / `PROJECT_NAME` / real secrets set
- [ ] Migrations applied (`alembic upgrade head`), backend `/docs` reachable
- [ ] Vector store (only if retrieval) — else `- [x] N/A`

## 2. Agents
- [x] Single tool-using loop — `app/agents/service.py`
- [x] Multi-agent supervisor/router — `app/agents/orchestrator.py`
- [ ] Real agent roster + routing for your domain (edit `WORKERS`)
- [ ] Step/recursion cap + model/params reviewed (`MAX_STEPS`, `LLM_MODEL`)

## 3. Tools
- [x] Tool registry with per-agent subsets — `app/agents/tools.py`
- [ ] Replace example tools with real capabilities (DB, APIs, compute)
- [ ] Auth/secrets + timeouts for external tools; a test per tool

## 4. Memory
- [x] Multi-turn history persisted — `app/agents/memory.py` + `Conversation`/`ConversationMessage`
- [x] In-memory fallback when no DB session
- [ ] History window / summarization strategy for long chats
- [ ] Long-term / retrieval memory — else `- [x] N/A`

## 5. Prompts
- [x] Prompt registry — `app/agents/prompts.py` (default + per-role)
- [ ] Real system/role prompts for your agents; document variables

## 6. Frontend components
- [x] Chat surface — `components/Agent/AgentChat.tsx` + `/agent` route + sidebar link
- [ ] Streaming / partial output
- [ ] Session UI (list/continue conversations)

## 7. Tracing / observability / eval
- [x] Per-turn + per-tool tracing — `app/agents/tracing.py` (logs always; Sentry spans when `SENTRY_DSN` set)
- [ ] Token / latency / cost metrics surfaced
- [ ] LangSmith / OTel exporter wired (`LANGCHAIN_TRACING_V2`) — else `- [x] N/A`
- [ ] Eval harness / LLM-judge — else `- [x] N/A`

## Cross-cutting
- [x] Auth (JWT) + secrets via `.env`
- [x] Claude PR code-review workflow (`.github/workflows/claude-review.yml`)
- [ ] Deployment configured for the target environment
- [ ] Tests: agent-loop + end-to-end smoke; CI green
- [ ] README + ARCHITECTURE updated to final state
