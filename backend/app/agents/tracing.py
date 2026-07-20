"""Agent tracing / observability.

A tiny tracer wrapping agent turns and tool calls. It always emits structured
logs (with a run/session id), and — when Sentry is configured — a Sentry span,
so agent activity shows up alongside the app's existing performance data. Sentry
is already initialized in `app.main`; this never re-initializes it.

Design goals: zero required setup (logging works out of the box), graceful no-op
when disabled (`TRACING_ENABLED=false`), and an easy hook point for LangSmith /
OpenTelemetry (see `LANGCHAIN_TRACING_V2` in `.env`) without adding hard deps.
"""
import contextlib
import logging
import time
from collections.abc import Iterator
from typing import Any

from app.core.config import settings

logger = logging.getLogger("app.agents")

try:  # Sentry is a template dependency, but keep tracing importable without it.
    import sentry_sdk
except Exception:  # pragma: no cover
    sentry_sdk = None  # type: ignore


def _sentry_span(op: str, name: str):
    if sentry_sdk is None or not settings.SENTRY_DSN:
        return contextlib.nullcontext()
    try:
        return sentry_sdk.start_span(op=op, name=name)
    except Exception:  # pragma: no cover - version/signature drift -> just log
        return contextlib.nullcontext()


@contextlib.contextmanager
def trace(op: str, name: str, **data: Any) -> Iterator[Any]:
    """Trace one unit of agent work (e.g. op='agent.turn' or 'agent.tool').

    Emits a Sentry span (when configured) and a structured log line with the
    elapsed time. No-ops when TRACING_ENABLED is false.
    """
    if not settings.TRACING_ENABLED:
        yield None
        return
    start = time.monotonic()
    with _sentry_span(op, name) as span:
        if span is not None:
            for k, v in data.items():
                try:
                    span.set_data(k, v)
                except Exception:  # pragma: no cover
                    pass
        try:
            yield span
        finally:
            ms = (time.monotonic() - start) * 1000
            logger.info("%s %s %.0fms %s", op, name, ms, data or "")
