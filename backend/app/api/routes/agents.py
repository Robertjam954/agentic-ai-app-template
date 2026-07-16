"""Agent API routes.

POST /agents/chat runs one tool-using agent turn. Auth-protected like the rest
of the API. Returns 503 when ANTHROPIC_API_KEY is not configured, so the app
still boots and serves everything else without a key.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents import client
from app.agents.service import run_agent
from app.api.deps import CurrentUser

router = APIRouter(prefix="/agents", tags=["agents"])


class ChatRequest(BaseModel):
    prompt: str


class ChatResponse(BaseModel):
    reply: str


@router.get("/health")
def agent_health() -> dict[str, bool]:
    """Report whether the agent is configured (an API key is present)."""
    return {"configured": client.is_configured()}


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, _current_user: CurrentUser) -> ChatResponse:
    if not client.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Agent not configured: set ANTHROPIC_API_KEY.",
        )
    if not body.prompt.strip():
        raise HTTPException(status_code=422, detail="prompt must not be empty")
    reply = await run_agent(body.prompt)
    return ChatResponse(reply=reply)
