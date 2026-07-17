"""Prompt registry.

System/role prompts live here, one per agent role, kept out of the request path
so they can be reviewed and versioned like any other asset. The single-agent
default mirrors `settings.LLM_SYSTEM_PROMPT`; the supervisor + worker prompts back
the multi-agent orchestrator.

Add a role by adding an entry to PROMPTS. For anything larger than a few lines,
load from a `.md` file next to this module instead of inlining.
"""
from app.core.config import settings

PROMPTS: dict[str, str] = {
    "default": settings.LLM_SYSTEM_PROMPT,
    "assistant": (
        "You are a helpful general assistant embedded in an application. "
        "Be concise and use the available tools when they help."
    ),
    "researcher": (
        "You are a research agent. Use the available tools to gather factual "
        "information, then answer concisely and cite what you used."
    ),
    "supervisor": (
        "You are a router for a team of worker agents. Given the user's request "
        "and the list of workers, reply with ONLY the name of the single best "
        "worker to handle the request. Reply 'finish' if no further work is needed."
    ),
}


def get_prompt(name: str) -> str:
    """Return a role prompt, falling back to the default system prompt."""
    return PROMPTS.get(name, PROMPTS["default"])
