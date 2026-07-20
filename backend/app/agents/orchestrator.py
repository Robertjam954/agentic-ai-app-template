"""Multi-agent orchestration.

A minimal supervisor/router: given a request, a supervisor picks the best worker
agent, and that worker runs with its own role prompt and tool subset. This mirrors
the common LangGraph supervisor pattern (a router node dispatching to worker nodes
that report back) without pulling in a graph framework — extend `WORKERS`, or swap
this for LangGraph / MS Agent Framework, as a project grows.
"""
from typing import Any

from anthropic.types import MessageParam

from app.agents import prompts, tracing
from app.agents.client import get_client
from app.agents.service import run_agent
from app.core.config import settings

# worker name -> role prompt + tool subset (None = all tools)
WORKERS: dict[str, dict[str, Any]] = {
    "researcher": {"prompt": "researcher", "tools": ["current_time", "word_count"]},
    "assistant": {"prompt": "assistant", "tools": None},
}


async def route(prompt: str) -> str:
    """Ask the supervisor which worker should handle the request."""
    client = get_client()
    names = ", ".join(WORKERS)
    with tracing.trace("agent.route", "supervisor"):
        resp = await client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=16,
            system=prompts.get_prompt("supervisor"),
            messages=[
                {
                    "role": "user",
                    "content": f"Workers: {names}.\nRequest: {prompt}\nWorker:",
                }
            ],
        )
    choice = "".join(b.text for b in resp.content if b.type == "text").strip().lower()
    for name in WORKERS:
        if name in choice:
            return name
    return "assistant"


async def run_supervised(
    prompt: str, history: list[MessageParam] | None = None
) -> dict[str, str]:
    """Route to a worker and run it. Returns the worker name and its reply."""
    worker = await route(prompt)
    spec = WORKERS[worker]
    reply = await run_agent(
        prompt,
        history,
        system_prompt=prompts.get_prompt(spec["prompt"]),
        tool_names=spec["tools"],
    )
    return {"worker": worker, "reply": reply}
