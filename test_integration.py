"""Acceptance scenario 1 from SPEC.md: sender -> recipient -> result."""

from __future__ import annotations

import os

os.environ.setdefault("RELAY_DATABASE_URL", "sqlite:////tmp/agent-relay-test.db")

from fastapi.testclient import TestClient

import main
from database import Base, engine


def _register(client: TestClient, name: str) -> tuple[str, dict[str, str]]:
    data = client.post("/api/v1/agents", json={"name": name}).json()
    return data["agent_id"], {"Authorization": f"Bearer {data['token']}"}


def test_task_flow_end_to_end():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(main.app) as client:
        _, sender = _register(client, "sender")
        recipient_id, recipient = _register(client, "recipient")

        sent = client.post("/api/v1/tasks", headers=sender, json={"to": recipient_id, "input": "hi"})
        assert sent.status_code == 201
        task_id = sent.json()["task_id"]
        assert sent.json()["status"] == "queued"

        claim = client.post("/api/v1/tasks/claim", headers=recipient, json={"wait_seconds": 0})
        assert claim.status_code == 200
        assert client.get(f"/api/v1/tasks/{task_id}", headers=sender).json()["status"] == "processing"

        done = client.post(
            f"/api/v1/tasks/{task_id}/complete",
            headers=recipient,
            json={"claim_token": claim.json()["claim_token"], "output": "HI"},
        )
        assert done.status_code == 200

        final = client.get(f"/api/v1/tasks/{task_id}", headers=sender).json()
        assert final["status"] == "completed"
        assert final["output"] == "HI"


def test_dashboard_heading():
    with TestClient(main.app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "<h1>Agent Relay v2</h1>" in response.text
