"""Tool-using agent loop.

Sends the conversation to Claude, executes any tools it requests, feeds the
results back, and repeats until Claude returns a final text answer (or a step
cap is hit). This is the core agentic pattern - extend it with memory, streaming,
or multi-agent routing as needed.
"""
from typing import Any

from anthropic.types import MessageParam

from app.agents import tools
from app.agents.client import get_client
from app.core.config import settings

MAX_STEPS = 6


async def run_agent(prompt: str, history: list[MessageParam] | None = None) -> str:
    """Run one agent turn and return the final text reply."""
    client = get_client()
    messages: list[MessageParam] = list(history or [])
    messages.append({"role": "user", "content": prompt})

    for _ in range(MAX_STEPS):
        response = await client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=settings.LLM_MAX_TOKENS,
            system=settings.LLM_SYSTEM_PROMPT,
            tools=tools.tool_schemas(),
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            return "".join(
                block.text for block in response.content if block.type == "text"
            ).strip()

        # Record the assistant turn, then run each requested tool and reply.
        messages.append({"role": "assistant", "content": response.content})
        tool_results: list[dict[str, Any]] = []
        for block in response.content:
            if block.type == "tool_use":
                result = await tools.run_tool(block.name, dict(block.input))
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
        messages.append({"role": "user", "content": tool_results})

    return "Stopped: reached the maximum number of tool-use steps."
