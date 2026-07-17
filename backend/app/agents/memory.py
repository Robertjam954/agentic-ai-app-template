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
from typing import Any

from sqlmodel import Session, select

from app.models import Conversation, ConversationMessage

# Process-local fallback store, used only when no DB session is provided.
_MEM: dict[str, list[dict[str, str]]] = {}


def ensure_conversation(
    session: Session | None, conversation_id: uuid.UUID, owner_id: uuid.UUID
) -> None:
    """Create the conversation row if it does not exist yet."""
    if session is None:
        _MEM.setdefault(str(conversation_id), [])
        return
    if session.get(Conversation, conversation_id) is None:
        session.add(Conversation(id=conversation_id, owner_id=owner_id))
        session.commit()


def load_history(
    session: Session | None, conversation_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Return prior turns as Anthropic message params (oldest first)."""
    if session is None:
        return [dict(m) for m in _MEM.get(str(conversation_id), [])]
    rows = session.exec(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at)
    ).all()
    return [{"role": r.role, "content": r.content} for r in rows]


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
