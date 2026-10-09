"""Tool registry for the agent.

Each tool is (1) a JSON schema Claude sees and (2) a Python callable that runs
when Claude asks for it. Add a tool by writing a function and appending an entry
to TOOLS - the agent loop discovers it automatically.

The example tools are intentionally trivial (no I/O) so the template runs with
no extra setup. Replace them with real capabilities: DB queries, external APIs,
computations over your `app.models`.
"""
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, col, select

from app.models import Item, User


@dataclass(frozen=True)
class ToolContext:
    """Request-scoped data available to tools that need application access."""

    session: Session
    user: User


ToolFn = Callable[[dict[str, Any], ToolContext | None], Awaitable[str]]


async def _current_time(_: dict[str, Any], __: ToolContext | None) -> str:
    return datetime.now(UTC).isoformat()


async def _word_count(args: dict[str, Any], _: ToolContext | None) -> str:
    text = str(args.get("text", ""))
    return str(len(text.split()))


def _normalize_search_limit(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        limit = int(value)
    except OverflowError, TypeError, ValueError:
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    return max(1, min(limit, 20))


async def _search_items(args: dict[str, Any], context: ToolContext | None) -> str:
    """Return only items the caller can access; this tool never mutates data."""
    if context is None:
        return "error: item search requires an authenticated request"

    query = str(args.get("query", "")).strip()
    limit = _normalize_search_limit(args.get("limit", 10))
    if limit is None:
        return "error: search limit must be an integer"
    statement = select(Item)
    if not context.user.is_superuser:
        statement = statement.where(Item.owner_id == context.user.id)
    if query:
        escaped_query = (
            query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        statement = statement.where(
            col(Item.title).ilike(f"%{escaped_query}%", escape="\\")
        )
    items = context.session.exec(
        statement.order_by(col(Item.created_at).desc()).limit(limit)
    ).all()
    return json.dumps(
        [
            {
                "id": str(item.id),
                "title": item.title,
                "description": item.description,
                "created_at": item.created_at.isoformat()
                if item.created_at is not None
                else None,
            }
            for item in items
        ]
    )


# schema (shown to Claude)  ->  handler (run on the server)
TOOLS: dict[str, tuple[dict[str, Any], ToolFn]] = {
    "current_time": (
        {
            "name": "current_time",
            "description": "Return the current UTC time in ISO-8601 format.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        _current_time,
    ),
    "word_count": (
        {
            "name": "word_count",
            "description": "Count the words in a piece of text.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to count words in."}
                },
                "required": ["text"],
            },
        },
        _word_count,
    ),
    "search_items": (
        {
            "name": "search_items",
            "description": (
                "Search application items the current user is authorized to view. "
                "Use this to answer questions about saved items; it never changes data."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Optional text to match in item titles.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results, from 1 to 20.",
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
                "required": [],
            },
        },
        _search_items,
    ),
}


def tool_schemas(names: list[str] | None = None) -> list[dict[str, Any]]:
    """Schemas for all tools, or just the named subset (for per-agent tools)."""
    items = TOOLS.items() if names is None else [
        (n, TOOLS[n]) for n in names if n in TOOLS
    ]
    return [schema for _, (schema, _fn) in items]


async def run_tool(
    name: str, args: dict[str, Any], context: ToolContext | None = None
) -> str:
    if name not in TOOLS:
        return f"error: unknown tool {name!r}"
    _, fn = TOOLS[name]
    return await fn(args, context)
