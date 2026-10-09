"""Privacy-preserving agent API routes."""

from typing import Literal

from anthropic.types import MessageParam
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.agents import client, memory
from app.agents.orchestrator import run_supervised
from app.agents.service import run_agent
from app.agents.tools import ToolContext
from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings

router = APIRouter(prefix="/agents", tags=["agents"])


class TransientMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("context content must not be empty")
        return value.strip()


class ChatRequest(BaseModel):
    """One turn plus client-held context and explicitly selected preferences."""

    prompt: str = Field(min_length=1, max_length=4000)
    context: list[TransientMessage] = Field(default_factory=list, max_length=256)
    preferences_to_save: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("prompt")
    @classmethod
    def prompt_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt must not be empty")
        return value.strip()

    @field_validator("preferences_to_save")
    @classmethod
    def validate_preferences(cls, values: list[str]) -> list[str]:
        for value in values:
            if not value.strip():
                raise ValueError("preferences must not be empty")
            if len(value) > 500:
                raise ValueError("preferences must be at most 500 characters")
        return values


class ChatResponse(BaseModel):
    reply: str


class OrchestrateResponse(ChatResponse):
    worker: str


def _require_configured() -> None:
    if not client.is_configured():
        raise HTTPException(
            status_code=503, detail="Agent not configured: set ANTHROPIC_API_KEY."
        )


def _save_explicit_preferences(
    session: SessionDep, current_user: CurrentUser, preferences: list[str]
) -> None:
    try:
        memory.save_preferences(session, current_user, preferences)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


def _compact_transient_context(
    body: ChatRequest, preference_data: str
) -> list[MessageParam]:
    return memory.compact_context(
        [(message.role, message.content) for message in body.context],
        model=settings.LLM_MODEL,
        output_reserve_tokens=max(
            settings.LLM_MAX_TOKENS, settings.LLM_CONTEXT_OUTPUT_RESERVE_TOKENS
        ),
        fixed_input=(settings.LLM_SYSTEM_PROMPT, body.prompt, preference_data),
        configured_capacity=settings.LLM_CONTEXT_WINDOW_TOKENS,
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
    _save_explicit_preferences(session, current_user, body.preferences_to_save)
    preference_data = memory.preference_data_prompt(
        memory.load_preferences(session, current_user)
    )
    history = _compact_transient_context(body, preference_data)

    reply = await run_agent(
        body.prompt,
        history,
        preference_data=preference_data,
        tool_context=ToolContext(session=session, user=current_user),
    )

    return ChatResponse(reply=reply)


@router.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(
    body: ChatRequest, session: SessionDep, current_user: CurrentUser
) -> OrchestrateResponse:
    """Multi-agent: a supervisor routes the request to a specialized worker."""
    _require_configured()
    _save_explicit_preferences(session, current_user, body.preferences_to_save)
    preference_data = memory.preference_data_prompt(
        memory.load_preferences(session, current_user)
    )
    history = _compact_transient_context(body, preference_data)

    result = await run_supervised(
        body.prompt,
        history,
        preference_data=preference_data,
        tool_context=ToolContext(session=session, user=current_user),
    )

    return OrchestrateResponse(reply=result["reply"], worker=result["worker"])
