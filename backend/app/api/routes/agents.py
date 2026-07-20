"""Agent API routes.

- POST /agents/chat        one tool-using turn, with persisted multi-turn memory
- POST /agents/orchestrate route to a specialized worker agent (multi-agent)
- GET  /agents/health      whether the agent is configured

Auth-protected. Returns 503 when ANTHROPIC_API_KEY is not configured, so the app
still boots and serves everything else without a key. When a conversation_id is
provided (or minted), turns are saved to the Conversation tables and replayed on
the next call.
"""
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents import client, memory
from app.agents.orchestrator import run_supervised
from app.agents.service import run_agent
from app.api.deps import CurrentUser, SessionDep

router = APIRouter(prefix="/agents", tags=["agents"])


class ChatRequest(BaseModel):
    prompt: str
    conversation_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: uuid.UUID


class OrchestrateResponse(ChatResponse):
    worker: str


def _require_configured() -> None:
    if not client.is_configured():
        raise HTTPException(
            status_code=503, detail="Agent not configured: set ANTHROPIC_API_KEY."
        )


@router.get("/health")
def agent_health() -> dict[str, bool]:
    """Report whether the agent is configured (an API key is present)."""
    return {"configured": client.is_configured()}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest, session: SessionDep, current_user: CurrentUser
) -> ChatResponse:
    _require_configured()
    if not body.prompt.strip():
        raise HTTPException(status_code=422, detail="prompt must not be empty")

    conversation_id = body.conversation_id or uuid.uuid4()
    memory.ensure_conversation(session, conversation_id, current_user.id)
    history = memory.load_history(session, conversation_id)

    reply = await run_agent(body.prompt, history)

    memory.save_message(session, conversation_id, "user", body.prompt)
    memory.save_message(session, conversation_id, "assistant", reply)
    return ChatResponse(reply=reply, conversation_id=conversation_id)


@router.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(
    body: ChatRequest, session: SessionDep, current_user: CurrentUser
) -> OrchestrateResponse:
    """Multi-agent: a supervisor routes the request to a specialized worker."""
    _require_configured()
    if not body.prompt.strip():
        raise HTTPException(status_code=422, detail="prompt must not be empty")

    conversation_id = body.conversation_id or uuid.uuid4()
    memory.ensure_conversation(session, conversation_id, current_user.id)
    history = memory.load_history(session, conversation_id)

    result = await run_supervised(body.prompt, history)

    memory.save_message(session, conversation_id, "user", body.prompt)
    memory.save_message(session, conversation_id, "assistant", result["reply"])
    return OrchestrateResponse(
        reply=result["reply"], conversation_id=conversation_id, worker=result["worker"]
    )
