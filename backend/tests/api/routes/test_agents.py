from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import inspect
from sqlmodel import Session, select

from app.agents import client as agent_client
from app.api.routes import agents
from app.core.config import settings
from app.models import UserPreference


def test_agent_health_reports_configuration(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(agent_client, "is_configured", lambda: False)

    response = client.get(f"{settings.API_V1_STR}/agents/health")

    assert response.status_code == 200
    assert response.json() == {"configured": False}


def test_chat_requires_authentication(client: TestClient) -> None:
    response = client.post(f"{settings.API_V1_STR}/agents/chat", json={"prompt": "Hi"})

    assert response.status_code == 401


def test_chat_uses_transient_context_without_persisting_a_transcript(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_run_agent(*args: object, **_: object) -> str:
        captured["history"] = args[1]
        return "Hello from the test agent."

    monkeypatch.setattr(agent_client, "is_configured", lambda: True)
    monkeypatch.setattr(agents, "run_agent", fake_run_agent)

    response = client.post(
        f"{settings.API_V1_STR}/agents/chat",
        headers=superuser_token_headers,
        json={
            "prompt": "Hi",
            "context": [{"role": "user", "content": "private patient detail"}],
        },
    )

    assert response.status_code == 200
    assert response.json() == {"reply": "Hello from the test agent."}
    assert captured["history"] == [
        {"role": "user", "content": "private patient detail"}
    ]
    assert db.exec(select(UserPreference)).all() == []
    table_names = inspect(db.connection()).get_table_names()
    assert "conversation" not in table_names
    assert "conversationmessage" not in table_names


def test_chat_rejects_unconfigured_and_blank_prompts(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(agent_client, "is_configured", lambda: False)
    unconfigured = client.post(
        f"{settings.API_V1_STR}/agents/chat",
        headers=superuser_token_headers,
        json={"prompt": "Hi"},
    )

    monkeypatch.setattr(agent_client, "is_configured", lambda: True)
    blank = client.post(
        f"{settings.API_V1_STR}/agents/chat",
        headers=superuser_token_headers,
        json={"prompt": "  "},
    )

    assert unconfigured.status_code == 503
    assert blank.status_code == 422


def test_orchestrate_uses_transient_context_and_explicit_preferences(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_run_supervised(*args: object, **kwargs: object) -> dict[str, str]:
        captured["history"] = args[1]
        captured["preference_data"] = kwargs["preference_data"]
        return {"worker": "researcher", "reply": "Found it."}

    monkeypatch.setattr(agent_client, "is_configured", lambda: True)
    monkeypatch.setattr(agents, "run_supervised", fake_run_supervised)

    response = client.post(
        f"{settings.API_V1_STR}/agents/orchestrate",
        headers=superuser_token_headers,
        json={
            "prompt": "Research this",
            "context": [{"role": "assistant", "content": "Earlier answer"}],
            "preferences_to_save": ["Use citations"],
        },
    )

    assert response.status_code == 200
    assert response.json()["worker"] == "researcher"
    assert response.json()["reply"] == "Found it."
    assert "conversation_id" not in response.json()
    assert captured["history"] == [{"role": "assistant", "content": "Earlier answer"}]
    assert "Use citations" in str(captured["preference_data"])
    assert db.exec(
        select(UserPreference).where(UserPreference.text == "Use citations")
    ).one()


def test_chat_saves_only_explicit_preferences_in_a_deduplicated_batch(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch: MonkeyPatch,
) -> None:
    async def fake_run_agent(*_: object, **__: object) -> str:
        return "Done."

    monkeypatch.setattr(agent_client, "is_configured", lambda: True)
    monkeypatch.setattr(agents, "run_agent", fake_run_agent)

    response = client.post(
        f"{settings.API_V1_STR}/agents/chat",
        headers=superuser_token_headers,
        json={
            "prompt": "Do not persist this chat prompt",
            "preferences_to_save": [
                "Use concise answers",
                " use   concise answers ",
                "Use bullet points",
            ],
        },
    )

    assert response.status_code == 200
    assert {preference.text for preference in db.exec(select(UserPreference)).all()} == {
        "Use concise answers",
        "Use bullet points",
    }
