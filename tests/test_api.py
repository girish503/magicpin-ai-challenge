from fastapi.testclient import TestClient

from app.main import create_app
from conftest import category_payload, merchant_payload, trigger_payload


def context_body(scope, context_id, payload, version=1):
    return {
        "scope": scope,
        "context_id": context_id,
        "version": version,
        "payload": payload,
        "delivered_at": "2026-04-26T09:45:00Z",
    }


def push_base(client):
    category = category_payload()
    merchant = merchant_payload()
    assert client.post("/v1/context", json=context_body("category", "dentists", category)).status_code == 200
    assert client.post("/v1/context", json=context_body("merchant", "m-1", merchant)).status_code == 200


def push_usable_trigger(client, trigger_id="t-1"):
    payload = trigger_payload(
        trigger_id=trigger_id,
        event_payload={"metric": "views", "delta_pct": -10, "window": "7d"},
    )
    response = client.post("/v1/context", json=context_body("trigger", trigger_id, payload))
    assert response.status_code == 200


def test_health_and_metadata_endpoints():
    client = TestClient(create_app())

    health = client.get("/v1/healthz")
    metadata = client.get("/v1/metadata")

    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "uptime_seconds": health.json()["uptime_seconds"],
        "contexts_loaded": {"category": 0, "merchant": 0, "customer": 0, "trigger": 0},
    }
    assert metadata.status_code == 200
    assert metadata.json()["model"] == "deterministic-no-llm"
    assert "approach" in metadata.json()


def test_valid_context_ingestion_and_stateful_health_counts():
    client = TestClient(create_app())
    push_base(client)

    health = client.get("/v1/healthz").json()

    assert health["contexts_loaded"] == {"category": 1, "merchant": 1, "customer": 0, "trigger": 0}


def test_invalid_context_scope_returns_structured_400():
    client = TestClient(create_app())
    response = client.post(
        "/v1/context",
        json=context_body("unknown", "x", {"anything": True}),
    )

    assert response.status_code == 400
    assert response.json()["reason"] == "invalid_scope"
    assert client.get("/v1/healthz").json()["contexts_loaded"] == {
        "category": 0,
        "merchant": 0,
        "customer": 0,
        "trigger": 0,
    }


def test_invalid_context_payload_is_rejected():
    client = TestClient(create_app())
    response = client.post(
        "/v1/context",
        json=context_body("merchant", "m-1", {"merchant_id": "wrong"}),
    )

    assert response.status_code == 400
    assert response.json()["reason"] == "invalid_context"


def test_context_version_conflict_and_replacement():
    client = TestClient(create_app())
    original = merchant_payload()
    assert client.post("/v1/context", json=context_body("merchant", "m-1", original)).status_code == 200

    duplicate = client.post("/v1/context", json=context_body("merchant", "m-1", original))
    replacement = client.post(
        "/v1/context",
        json=context_body(
            "merchant",
            "m-1",
            {**original, "category_slug": "gyms"},
            version=2,
        ),
    )
    stale = client.post("/v1/context", json=context_body("merchant", "m-1", original))

    assert duplicate.status_code == 409
    assert duplicate.json() == {"accepted": False, "reason": "stale_version", "current_version": 1}
    assert replacement.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["current_version"] == 2


def test_malformed_requests_return_validation_error():
    client = TestClient(create_app())

    missing_field = client.post("/v1/context", json={"scope": "category"})
    invalid_tick = client.post("/v1/tick", json={"now": "not-a-timestamp"})
    invalid_reply = client.post("/v1/reply", json={"conversation_id": "conv-1"})

    assert missing_field.status_code == 422
    assert invalid_tick.status_code == 400
    assert invalid_reply.status_code == 422


def test_tick_returns_action_for_usable_context_and_suppresses_repeat():
    client = TestClient(create_app())
    push_base(client)
    push_usable_trigger(client)

    first = client.post(
        "/v1/tick",
        json={"now": "2026-04-26T10:00:00Z", "available_triggers": ["t-1"]},
    )
    second = client.post(
        "/v1/tick",
        json={"now": "2026-04-26T10:05:00Z", "available_triggers": ["t-1"]},
    )

    assert first.status_code == 200
    assert len(first.json()["actions"]) == 1
    action = first.json()["actions"][0]
    assert action["merchant_id"] == "m-1"
    assert action["send_as"] == "vera"
    assert action["trigger_id"] == "t-1"
    assert action["body"]
    assert action["suppression_key"] == "suppression-t-1"
    assert second.status_code == 200
    assert second.json() == {"actions": []}


def test_tick_abstains_for_placeholder_trigger():
    client = TestClient(create_app())
    push_base(client)
    placeholder = trigger_payload(trigger_id="placeholder", event_payload={"placeholder": True})
    assert client.post(
        "/v1/context",
        json=context_body("trigger", "placeholder", placeholder),
    ).status_code == 200

    response = client.post(
        "/v1/tick",
        json={"now": "2026-04-26T10:00:00Z", "available_triggers": ["placeholder"]},
    )

    assert response.status_code == 200
    assert response.json() == {"actions": []}


def test_reply_flow_uses_conversation_machine():
    client = TestClient(create_app())
    push_base(client)
    push_usable_trigger(client)
    tick = client.post(
        "/v1/tick",
        json={"now": "2026-04-26T10:00:00Z", "available_triggers": ["t-1"]},
    ).json()
    conversation_id = tick["actions"][0]["conversation_id"]

    committed = client.post(
        "/v1/reply",
        json={
            "conversation_id": conversation_id,
            "merchant_id": "m-1",
            "from_role": "merchant",
            "message": "Yes please, go ahead",
            "received_at": "2026-04-26T10:05:00Z",
            "turn_number": 2,
        },
    )
    stopped = client.post(
        "/v1/reply",
        json={
            "conversation_id": conversation_id,
            "merchant_id": "m-1",
            "from_role": "merchant",
            "message": "Stop messaging me",
            "received_at": "2026-04-26T10:06:00Z",
            "turn_number": 4,
        },
    )

    assert committed.status_code == 200
    assert committed.json()["action"] == "send"
    assert committed.json()["body"]
    assert stopped.status_code == 200
    assert stopped.json()["action"] == "end"


def test_reply_unknown_conversation_ends_safely():
    client = TestClient(create_app())

    response = client.post(
        "/v1/reply",
        json={
            "conversation_id": "missing",
            "merchant_id": "m-1",
            "from_role": "merchant",
            "message": "Hello",
            "received_at": "2026-04-26T10:00:00Z",
            "turn_number": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["action"] == "end"
