"""Tool registry for the agent.

Each tool is (1) a JSON schema Claude sees and (2) a Python callable that runs
when Claude asks for it. Add a tool by writing a function and appending an entry
to TOOLS - the agent loop discovers it automatically.

The example tools are intentionally trivial (no I/O) so the template runs with
no extra setup. Replace them with real capabilities: DB queries, external APIs,
computations over your `app.models`.
"""
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable

ToolFn = Callable[[dict[str, Any]], Awaitable[str]]


async def _current_time(_: dict[str, Any]) -> str:
    return datetime.now(UTC).isoformat()


async def _word_count(args: dict[str, Any]) -> str:
    text = str(args.get("text", ""))
    return str(len(text.split()))


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
}


def tool_schemas() -> list[dict[str, Any]]:
    return [schema for schema, _ in TOOLS.values()]


async def run_tool(name: str, args: dict[str, Any]) -> str:
    if name not in TOOLS:
        return f"error: unknown tool {name!r}"
    _, fn = TOOLS[name]
    return await fn(args)
