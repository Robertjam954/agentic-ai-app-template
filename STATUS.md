# Status

Live checklist of what is left to complete for an agentic app built from this
template. Check a box (`[ ]` -> `[x]`) as you finish. Same checkbox format the
portfolio tracking dashboard reads, so this project's status rolls up to the
portfolio board automatically.

> Project: **<name>** · Stage: **<scaffold | agent | product | deploy>**

## 1. Scaffold
- [ ] Renamed project (copier / config), set PROJECT_NAME and secrets
- [ ] Backend boots, `/docs` reachable, DB migrations applied
- [ ] Frontend boots and talks to the API
- [ ] First superuser + auth flow working

## 2. Agent
- [ ] `ANTHROPIC_API_KEY` set; `/api/v1/agents/health` -> configured
- [ ] Real tools added in `backend/app/agents/tools.py` (replace the examples)
- [ ] System prompt / model tuned in settings (`LLM_MODEL`, `LLM_SYSTEM_PROMPT`)
- [ ] `POST /api/v1/agents/chat` returns useful answers on real tasks
- [ ] Frontend surface for the agent (chat panel / action)
- [ ] Tests for the agent loop and each tool

## 3. Product
- [ ] Domain models defined in `app/models.py` + migrations
- [ ] Core routes + frontend screens for the actual use case
- [ ] Guardrails: input validation, rate limiting, cost/step caps
- [ ] Observability: request logging, token/latency metrics

## 4. Deploy
- [ ] Secrets configured in the target environment
- [ ] CI green (lint, types, tests)
- [ ] Deployed (Docker Compose / Traefik per `deployment.md`)
- [ ] README + ARCHITECTURE updated to final state
