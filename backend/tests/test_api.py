import json

from fastapi.testclient import TestClient

from magi import app as app_module
from magi.models import Act, ActEvent, CoreStatusEvent, PhaseEvent


def test_discuss_streams_ordered_compact_ndjson_without_private_values(monkeypatch):
    api_key = "sk-test-secret"
    private_reasoning = "provider reasoning_content must stay private"
    monkeypatch.setenv("DEEPSEEK_API_KEY", api_key)

    events = [
        PhaseEvent(phase="OPENING", active_cores=["MELCHIOR-1"]),
        ActEvent(
            id=1,
            seen_through_event_id=0,
            act=Act(core="MELCHIOR-1", kind="POSITION", content="Proceed carefully."),
        ),
        CoreStatusEvent(
            core="MELCHIOR-1",
            status="LISTENING",
            reviewed_through_event_id=1,
        ),
        PhaseEvent(phase="BALLOTING", active_cores=[]),
    ]

    async def fake_deliberate(motion):
        assert motion.question == "Should the pilot proceed?"
        assert motion.quorum == "unanimous"
        for event in events:
            yield event

    monkeypatch.setattr(app_module, "deliberate", fake_deliberate)

    with TestClient(app_module.app) as client:
        response = client.post(
            "/api/discuss",
            json={"question": "Should the pilot proceed?", "quorum": "unanimous"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert response.text.endswith("\n")

    lines = [line for line in response.text.splitlines() if line]
    payloads = [json.loads(line) for line in lines]
    assert [payload["type"] for payload in payloads] == [
        "phase",
        "act",
        "core_status",
        "phase",
    ]
    assert [payload["phase"] for payload in payloads if payload["type"] == "phase"] == [
        "OPENING",
        "BALLOTING",
    ]
    assert all(line == line.strip() for line in lines)
    act_payload = next(payload for payload in payloads if payload["type"] == "act")
    assert act_payload["seen_through_event_id"] == 0
    assert "round" not in act_payload
    assert private_reasoning not in response.text
    assert "reasoning_content" not in response.text
    assert api_key not in response.text


def test_discuss_rejects_two_character_question():
    with TestClient(app_module.app) as client:
        response = client.post("/api/discuss", json={"question": "No"})

    assert response.status_code == 422


def test_discuss_rejects_unknown_decision_policy():
    with TestClient(app_module.app) as client:
        response = client.post(
            "/api/discuss",
            json={"question": "Should the pilot proceed?", "quorum": "plurality"},
        )

    assert response.status_code == 422


def test_discuss_allows_local_development_cors():
    with TestClient(app_module.app) as client:
        response = client.options(
            "/api/discuss",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_discuss_does_not_return_raw_exception_text(monkeypatch):
    private_reasoning = "reasoning_content: do not expose this"
    api_key = "sk-test-secret"

    async def failing_deliberate(motion):
        raise RuntimeError(f"provider failed with {api_key}; {private_reasoning}")
        yield

    monkeypatch.setattr(app_module, "deliberate", failing_deliberate)

    with TestClient(app_module.app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/discuss",
            json={"question": "Should the pilot proceed?"},
        )

    assert api_key not in response.text
    assert "reasoning_content" not in response.text
    assert private_reasoning not in response.text
