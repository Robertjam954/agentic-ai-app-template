import asyncio
import uuid
from types import SimpleNamespace

import pytest
from sqlmodel import Session

from app.agents import client, memory, orchestrator, service, tracing
from app.agents.tools import ToolContext, run_tool, tool_schemas
from app.core.config import settings
from tests.utils.user import create_random_user


class FakeMessages:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self.responses.pop(0)


def fake_client(*responses: object) -> tuple[SimpleNamespace, FakeMessages]:
    messages = FakeMessages(list(responses))
    return SimpleNamespace(messages=messages), messages


def test_client_configuration_and_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    client.get_client.cache_clear()
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    assert not client.is_configured()
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        client.get_client()

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    assert client.is_configured()
    assert client.get_client() is client.get_client()
    client.get_client.cache_clear()


def test_memory_fallback_and_owner_validation(db: Session) -> None:
    owner = create_random_user(db)
    other_user = create_random_user(db)
    conversation_id = uuid.uuid4()

    memory.ensure_conversation(db, conversation_id, owner)
    memory.save_message(db, conversation_id, "user", "hello")
    assert memory.load_history(db, conversation_id) == [
        {"role": "user", "content": "hello"}
    ]
    with pytest.raises(PermissionError):
        memory.ensure_conversation(db, conversation_id, other_user)

    fallback_id = uuid.uuid4()
    memory.ensure_conversation(None, fallback_id, owner)
    memory.save_message(None, fallback_id, "assistant", "hi")
    assert memory.load_history(None, fallback_id) == [
        {"role": "assistant", "content": "hi"}
    ]


def test_builtin_tools_and_schemas(db: Session) -> None:
    user = create_random_user(db)
    context = ToolContext(session=db, user=user)

    assert asyncio.run(run_tool("word_count", {"text": "one two"}, context)) == "2"
    assert asyncio.run(run_tool("search_items", {}, None)).startswith("error:")
    assert (
        asyncio.run(run_tool("missing", {}, context)) == "error: unknown tool 'missing'"
    )
    assert {schema["name"] for schema in tool_schemas(["word_count", "missing"])} == {
        "word_count"
    }
    assert "T" in asyncio.run(run_tool("current_time", {}, context))


def test_run_agent_returns_text(monkeypatch: pytest.MonkeyPatch) -> None:
    response = SimpleNamespace(
        stop_reason="end_turn",
        content=[
            SimpleNamespace(type="text", text=" hello "),
            SimpleNamespace(type="tool_use"),
            SimpleNamespace(type="text", text="world "),
        ],
    )
    fake, messages = fake_client(response)
    monkeypatch.setattr(service, "get_client", lambda: fake)

    assert asyncio.run(service.run_agent("question")) == "hello world"
    assert messages.calls[0]["messages"] == [{"role": "user", "content": "question"}]


def test_run_agent_executes_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    tool_response = SimpleNamespace(
        stop_reason="tool_use",
        content=[
            SimpleNamespace(
                type="tool_use", id="call-1", name="word_count", input={"text": "a b"}
            )
        ],
    )
    final_response = SimpleNamespace(
        stop_reason="end_turn", content=[SimpleNamespace(type="text", text="2")]
    )
    fake, messages = fake_client(tool_response, final_response)
    monkeypatch.setattr(service, "get_client", lambda: fake)

    assert asyncio.run(service.run_agent("count")) == "2"
    assert messages.calls[1]["messages"][-1]["content"] == [
        {"type": "tool_result", "tool_use_id": "call-1", "content": "2"}
    ]


def test_run_agent_stops_after_tool_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    response = SimpleNamespace(
        stop_reason="tool_use",
        content=[
            SimpleNamespace(type="tool_use", id="id", name="word_count", input={})
        ],
    )
    fake, _ = fake_client(*([response] * service.MAX_STEPS))
    monkeypatch.setattr(service, "get_client", lambda: fake)

    assert asyncio.run(service.run_agent("loop")).startswith("Stopped:")


def test_orchestration_routes_and_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="researcher")]
    )
    fake, _ = fake_client(response)
    monkeypatch.setattr(orchestrator, "get_client", lambda: fake)
    assert asyncio.run(orchestrator.route("find facts")) == "researcher"

    async def fake_route(_: str) -> str:
        return "assistant"

    async def fake_run_agent(*args: object, **kwargs: object) -> str:
        assert args == ("help", None)
        assert kwargs["tool_names"] is None
        return "done"

    monkeypatch.setattr(orchestrator, "route", fake_route)
    monkeypatch.setattr(orchestrator, "run_agent", fake_run_agent)
    assert asyncio.run(orchestrator.run_supervised("help")) == {
        "worker": "assistant",
        "reply": "done",
    }


def test_trace_enabled_and_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TRACING_ENABLED", False)
    with tracing.trace("op", "name") as span:
        assert span is None

    monkeypatch.setattr(settings, "TRACING_ENABLED", True)
    with tracing.trace("op", "name", value=1) as span:
        assert span is None
