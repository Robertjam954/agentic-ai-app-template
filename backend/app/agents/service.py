"""Tool-using agent loop.

Sends the conversation to Claude, executes any tools it requests, feeds the
results back, and repeats until Claude returns a final text answer (or a step
cap is hit). This is the core agentic pattern. It accepts an optional per-agent
system prompt and tool subset (used by the multi-agent orchestrator) and traces
each turn and tool call. Conversation memory is layered on at the API route, which
loads history and passes it in.

`execute_agent` returns the reply plus the tool trajectory. The local eval
runner (`python -m app.evals`) uses that, and can pass a scripted `client` so
cases run without an API key. `run_agent` stays the text-only wrapper.
"""

from dataclasses import dataclass
from typing import Any, cast

from anthropic.types import MessageParam

from app.agents import tools, tracing
from app.agents.client import get_client
from app.core.config import settings

MAX_STEPS = 6


@dataclass(frozen=True)
class ToolCall:
    """One tool the model asked for, and the string the handler returned."""

    name: str
    tool_input: dict[str, Any]
    output: str


@dataclass(frozen=True)
class AgentRun:
    """Final reply and the tool calls made while producing it.

    `stop_reason` is the provider stop reason (`end_turn`, …) or `max_steps`
    when the loop hits `MAX_STEPS` still inside tool use.
    """

    reply: str
    tool_calls: tuple[ToolCall, ...]
    stop_reason: str


async def run_agent(
    prompt: str,
    history: list[MessageParam] | None = None,
    *,
    system_prompt: str | None = None,
    tool_names: list[str] | None = None,
    client: Any | None = None,
) -> str:
    """Run one agent turn and return the final text reply.

    - `history`: prior turns (from memory) prepended to the conversation.
    - `system_prompt`: role prompt; defaults to the app system prompt.
    - `tool_names`: restrict to this tool subset; defaults to all tools.
    - `client`: model client. Unset uses the Anthropic client. The eval runner
      passes a scripted client so a case can run offline.
    """
    return (
        await execute_agent(
            prompt,
            history,
            system_prompt=system_prompt,
            tool_names=tool_names,
            client=client,
        )
    ).reply


async def execute_agent(
    prompt: str,
    history: list[MessageParam] | None = None,
    *,
    system_prompt: str | None = None,
    tool_names: list[str] | None = None,
    client: Any | None = None,
) -> AgentRun:
    """Same loop as `run_agent`, but keep the tool trajectory for eval gates."""
    active: Any = client if client is not None else get_client()
    system = system_prompt or settings.LLM_SYSTEM_PROMPT
    schemas = tools.tool_schemas(tool_names)
    messages: list[MessageParam] = list(history or [])
    messages.append({"role": "user", "content": prompt})
    tool_calls: list[ToolCall] = []

    for _ in range(MAX_STEPS):
        with tracing.trace("agent.turn", settings.LLM_MODEL, tools=len(schemas)):
            response: Any = await active.messages.create(
                model=settings.LLM_MODEL,
                max_tokens=settings.LLM_MAX_TOKENS,
                system=system,
                tools=schemas,
                messages=messages,
            )

        if response.stop_reason != "tool_use":
            reply = "".join(
                block.text for block in response.content if block.type == "text"
            ).strip()
            return AgentRun(
                reply=reply,
                tool_calls=tuple(tool_calls),
                stop_reason=str(response.stop_reason),
            )

        # Record the assistant turn, then run each requested tool and reply.
        messages.append({"role": "assistant", "content": response.content})
        tool_results: list[dict[str, Any]] = []
        for block in response.content:
            if block.type == "tool_use":
                tool_input = dict(block.input)
                with tracing.trace("agent.tool", block.name):
                    result = await tools.run_tool(block.name, tool_input)
                tool_calls.append(
                    ToolCall(name=block.name, tool_input=tool_input, output=result)
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
        messages.append(cast(MessageParam, {"role": "user", "content": tool_results}))

    return AgentRun(
        reply="Stopped: reached the maximum number of tool-use steps.",
        tool_calls=tuple(tool_calls),
        stop_reason="max_steps",
    )
