"""Anthropic client factory.

Keeps provider setup in one place so routes/services never construct clients
directly. If ANTHROPIC_API_KEY is unset, `is_configured()` is False and the API
layer returns 503 instead of failing deep in a request.
"""
from functools import lru_cache

from anthropic import AsyncAnthropic

from app.core.config import settings


def is_configured() -> bool:
    return bool(settings.ANTHROPIC_API_KEY)


@lru_cache
def get_client() -> AsyncAnthropic:
    if not is_configured():
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set - configure it to use the agent."
        )
    return AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
