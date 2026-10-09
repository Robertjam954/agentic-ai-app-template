"""Conversation memory (short-term, multi-turn).

Loads and saves plain text turns for a conversation so the agent has context
across calls. Backed by the `Conversation` / `ConversationMessage` tables when a
DB session is passed; falls back to a process-local dict when it is not (handy
for tests or running the agent loop in isolation).

Only user/assistant *text* turns are persisted — intermediate tool-use blocks are
transient and stay inside a single `run_agent` call. Long-term / retrieval memory
(vectors, summaries) is a deliberate extension point, not built in here.
"""
import uuid
from typing import cast

from anthropic.types import MessageParam
from sqlmodel import Session, col, select

from app.models import Conversation, ConversationMessage, User

# Process-local fallback store, used only when no DB session is provided.
_MEM: dict[str, list[dict[str, str]]] = {}


def ensure_conversation(
    session: Session | None, conversation_id: uuid.UUID, owner: User
) -> None:
    """Create a conversation or verify that it belongs to its caller."""
    if session is None:
        _MEM.setdefault(str(conversation_id), [])
        return
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        session.add(Conversation(id=conversation_id, owner_id=owner.id))
        session.commit()
    elif conversation.owner_id != owner.id:
        raise PermissionError("Conversation does not belong to the current user")


def load_history(
    session: Session | None, conversation_id: uuid.UUID
) -> list[MessageParam]:
    """Return prior turns as Anthropic message params (oldest first)."""
    if session is None:
        return [cast(MessageParam, dict(m)) for m in _MEM.get(str(conversation_id), [])]
    rows = session.exec(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(col(ConversationMessage.created_at))
    ).all()
    return [
        cast(MessageParam, {"role": r.role, "content": r.content}) for r in rows
    ]


def save_message(
    session: Session | None, conversation_id: uuid.UUID, role: str, content: str
) -> None:
    """Append one text turn to the conversation."""
    if session is None:
        _MEM.setdefault(str(conversation_id), []).append(
            {"role": role, "content": content}
        )
        return
    session.add(
        ConversationMessage(
            conversation_id=conversation_id, role=role, content=content
        )
    )
    session.commit()
