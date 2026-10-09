import uuid

from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlmodel import Session

from app.agents import client as agent_client
from app.api.routes import agents
from app.core.config import settings
from tests.utils.user import authentication_token_from_email


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


def test_chat_persists_a_conversation(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch: MonkeyPatch,
) -> None:
    async def fake_run_agent(*_: object, **__: object) -> str:
        return "Hello from the test agent."

    monkeypatch.setattr(agent_client, "is_configured", lambda: True)
    monkeypatch.setattr(agents, "run_agent", fake_run_agent)

    response = client.post(
        f"{settings.API_V1_STR}/agents/chat",
        headers=superuser_token_headers,
        json={"prompt": "Hi"},
    )

    assert response.status_code == 200
    assert response.json()["reply"] == "Hello from the test agent."
    assert uuid.UUID(response.json()["conversation_id"])


def test_chat_hides_other_users_conversations(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch: MonkeyPatch,
) -> None:
    async def fake_run_agent(*_: object, **__: object) -> str:
        return "Hello from the test agent."

    other_headers = authentication_token_from_email(
        client=client, email="other-agent-user@example.com", db=db
    )
    monkeypatch.setattr(agent_client, "is_configured", lambda: True)
    monkeypatch.setattr(agents, "run_agent", fake_run_agent)

    created = client.post(
        f"{settings.API_V1_STR}/agents/chat",
        headers=superuser_token_headers,
        json={"prompt": "private"},
    )
    conversation_id = created.json()["conversation_id"]
    response = client.post(
        f"{settings.API_V1_STR}/agents/chat",
        headers=other_headers,
        json={"prompt": "read it", "conversation_id": conversation_id},
    )

    assert created.status_code == 200
    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"


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


def test_orchestrate_persists_reply(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch: MonkeyPatch,
) -> None:
    async def fake_run_supervised(*_: object, **__: object) -> dict[str, str]:
        return {"worker": "researcher", "reply": "Found it."}

    monkeypatch.setattr(agent_client, "is_configured", lambda: True)
    monkeypatch.setattr(agents, "run_supervised", fake_run_supervised)

    response = client.post(
        f"{settings.API_V1_STR}/agents/orchestrate",
        headers=superuser_token_headers,
        json={"prompt": "Research this"},
    )

    assert response.status_code == 200
    assert response.json()["worker"] == "researcher"
    assert response.json()["reply"] == "Found it."
