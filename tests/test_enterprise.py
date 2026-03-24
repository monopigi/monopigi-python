"""Tests for enterprise SDK client methods (reports, alerts, monitoring, models)."""

from __future__ import annotations

import pytest
from monopigi.client import MonopigiClient
from pytest_httpx import HTTPXMock

BASE = "https://api.monopigi.com"


@pytest.fixture
def client(api_token: str, base_url: str) -> MonopigiClient:
    return MonopigiClient(token=api_token, base_url=base_url, max_retries=0)


# -- Models (no auth) ---------------------------------------------------------


def test_models_no_auth(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """client.models() calls GET /v1/models and returns the JSON payload."""
    payload = {
        "models": [
            {"id": "anthropic/claude-sonnet-4-20250514", "default": True},
            {"id": "mistral/mistral-large-latest", "default": False},
        ]
    }
    httpx_mock.add_response(url=f"{BASE}/v1/models", json=payload)

    result = client.models()

    assert result == payload
    req = httpx_mock.get_requests()[0]
    assert req.method == "GET"
    assert req.url.path == "/v1/models"


# -- Reports (Pro+) -----------------------------------------------------------


def test_create_report(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """client.create_report() sends POST /v1/reports with correct body."""
    response_payload = {"id": "rpt-001", "status": "pending", "entity_identifier": "123", "identifier_type": "afm"}
    httpx_mock.add_response(url=f"{BASE}/v1/reports", method="POST", json=response_payload)

    result = client.create_report("123", "afm")

    assert result == response_payload
    req = httpx_mock.get_requests()[0]
    assert req.method == "POST"
    assert req.url.path == "/v1/reports"
    import json

    body = json.loads(req.content)
    assert body == {"entity_identifier": "123", "identifier_type": "afm"}


def test_get_report(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """client.get_report() calls GET /v1/reports/{id}."""
    report_id = "rpt-001"
    payload = {"id": report_id, "status": "completed", "entity_identifier": "123"}
    httpx_mock.add_response(url=f"{BASE}/v1/reports/{report_id}", json=payload)

    result = client.get_report(report_id)

    assert result == payload
    req = httpx_mock.get_requests()[0]
    assert req.method == "GET"
    assert req.url.path == f"/v1/reports/{report_id}"


def test_list_reports(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """client.list_reports() calls GET /v1/reports with pagination params."""
    payload = {"items": [{"id": "rpt-001", "status": "completed"}], "total": 1}
    httpx_mock.add_response(json=payload)

    result = client.list_reports()

    assert result == payload
    req = httpx_mock.get_requests()[0]
    assert req.method == "GET"
    assert req.url.path == "/v1/reports"
    assert "limit=20" in str(req.url)
    assert "offset=0" in str(req.url)


# -- Alerts (Enterprise) ------------------------------------------------------


def test_create_alert_profile(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """client.create_alert_profile() sends POST with name, filters, and extra kwargs."""
    response_payload = {"id": "alert-001", "name": "IT Tenders", "is_active": True}
    httpx_mock.add_response(url=f"{BASE}/v1/alerts/profiles", method="POST", json=response_payload)

    filters = {"keywords": ["software", "IT"], "sources": ["ted"]}
    result = client.create_alert_profile("IT Tenders", filters, notify_email="test@example.com")

    assert result == response_payload
    req = httpx_mock.get_requests()[0]
    assert req.method == "POST"
    assert req.url.path == "/v1/alerts/profiles"
    import json

    body = json.loads(req.content)
    assert body["name"] == "IT Tenders"
    assert body["filters"] == filters
    assert body["notify_email"] == "test@example.com"


def test_list_alert_profiles(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """client.list_alert_profiles() calls GET /v1/alerts/profiles."""
    payload = {"items": [{"id": "alert-001", "name": "IT Tenders"}], "total": 1}
    httpx_mock.add_response(json=payload)

    result = client.list_alert_profiles()

    assert result == payload
    req = httpx_mock.get_requests()[0]
    assert req.method == "GET"
    assert req.url.path == "/v1/alerts/profiles"


def test_update_alert_profile(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """client.update_alert_profile() uses PUT (not PATCH)."""
    profile_id = "alert-001"
    response_payload = {"id": profile_id, "name": "Updated Name", "is_active": False}
    httpx_mock.add_response(url=f"{BASE}/v1/alerts/profiles/{profile_id}", method="PUT", json=response_payload)

    result = client.update_alert_profile(profile_id, name="Updated Name", is_active=False)

    assert result == response_payload
    req = httpx_mock.get_requests()[0]
    assert req.method == "PUT"
    assert req.url.path == f"/v1/alerts/profiles/{profile_id}"
    import json

    body = json.loads(req.content)
    assert body["name"] == "Updated Name"
    assert body["is_active"] is False


def test_delete_alert_profile(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """client.delete_alert_profile() sends DELETE /v1/alerts/profiles/{id}."""
    profile_id = "alert-001"
    httpx_mock.add_response(url=f"{BASE}/v1/alerts/profiles/{profile_id}", method="DELETE", json={"status": "deleted"})

    result = client.delete_alert_profile(profile_id)

    assert result == {"status": "deleted"}
    req = httpx_mock.get_requests()[0]
    assert req.method == "DELETE"
    assert req.url.path == f"/v1/alerts/profiles/{profile_id}"


def test_list_alert_deliveries(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """client.list_alert_deliveries() calls GET /v1/alerts/deliveries."""
    payload = {"items": [{"id": "del-001", "channel": "email", "delivery_status": "sent"}], "total": 1}
    httpx_mock.add_response(json=payload)

    result = client.list_alert_deliveries()

    assert result == payload
    req = httpx_mock.get_requests()[0]
    assert req.method == "GET"
    assert req.url.path == "/v1/alerts/deliveries"


def test_list_alert_deliveries_with_profile_filter(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """Passing profile_id adds it as a query parameter."""
    payload = {"items": [], "total": 0}
    httpx_mock.add_response(json=payload)

    client.list_alert_deliveries(profile_id="alert-001")

    req = httpx_mock.get_requests()[0]
    assert "profile_id=alert-001" in str(req.url)


# -- Compliance monitoring (Enterprise) ----------------------------------------


def test_add_monitored_entity(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """client.add_monitored_entity() sends POST /v1/monitor/entities."""
    response_payload = {"id": "mon-001", "entity_identifier": "099369820", "identifier_type": "afm", "label": "ACME"}
    httpx_mock.add_response(url=f"{BASE}/v1/monitor/entities", method="POST", json=response_payload)

    result = client.add_monitored_entity("099369820", identifier_type="afm", label="ACME")

    assert result == response_payload
    req = httpx_mock.get_requests()[0]
    assert req.method == "POST"
    assert req.url.path == "/v1/monitor/entities"
    import json

    body = json.loads(req.content)
    assert body == {"entity_identifier": "099369820", "identifier_type": "afm", "label": "ACME"}


def test_add_monitored_entity_no_label(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """Without a label, the label field is omitted from the request body."""
    httpx_mock.add_response(
        url=f"{BASE}/v1/monitor/entities",
        method="POST",
        json={"id": "mon-002", "entity_identifier": "123"},
    )

    client.add_monitored_entity("123")

    import json

    body = json.loads(httpx_mock.get_requests()[0].content)
    assert "label" not in body


def test_list_monitored_entities(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """client.list_monitored_entities() calls GET /v1/monitor/entities."""
    payload = {"items": [{"id": "mon-001", "entity_identifier": "099369820"}], "total": 1}
    httpx_mock.add_response(json=payload)

    result = client.list_monitored_entities()

    assert result == payload
    req = httpx_mock.get_requests()[0]
    assert req.method == "GET"
    assert req.url.path == "/v1/monitor/entities"


def test_remove_monitored_entity(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """client.remove_monitored_entity() sends DELETE /v1/monitor/entities/{id}."""
    entity_id = "mon-001"
    httpx_mock.add_response(
        url=f"{BASE}/v1/monitor/entities/{entity_id}", method="DELETE", json={"status": "deactivated"}
    )

    result = client.remove_monitored_entity(entity_id)

    assert result == {"status": "deactivated"}
    req = httpx_mock.get_requests()[0]
    assert req.method == "DELETE"
    assert req.url.path == f"/v1/monitor/entities/{entity_id}"


def test_list_entity_events(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """client.list_entity_events() calls GET /v1/monitor/events."""
    payload = {
        "items": [{"id": "evt-001", "event_type": "new_decision", "summary": "New decision found"}],
        "total": 1,
    }
    httpx_mock.add_response(json=payload)

    result = client.list_entity_events()

    assert result == payload
    req = httpx_mock.get_requests()[0]
    assert req.method == "GET"
    assert req.url.path == "/v1/monitor/events"


def test_list_entity_events_with_filters(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """Optional filters are passed as query parameters."""
    httpx_mock.add_response(json={"items": [], "total": 0})

    client.list_entity_events(entity_id="mon-001", event_type="new_contract", since="2026-01-01")

    req = httpx_mock.get_requests()[0]
    url_str = str(req.url)
    assert "entity_id=mon-001" in url_str
    assert "event_type=new_contract" in url_str
    assert "since=2026-01-01" in url_str


def test_acknowledge_event(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """client.acknowledge_event() sends POST /v1/monitor/events/{id}/acknowledge."""
    event_id = "evt-001"
    response_payload = {"id": event_id, "acknowledged_at": "2026-03-24T12:00:00Z"}
    httpx_mock.add_response(
        url=f"{BASE}/v1/monitor/events/{event_id}/acknowledge", method="POST", json=response_payload
    )

    result = client.acknowledge_event(event_id)

    assert result == response_payload
    req = httpx_mock.get_requests()[0]
    assert req.method == "POST"
    assert req.url.path == f"/v1/monitor/events/{event_id}/acknowledge"


def test_entity_health_report(client: MonopigiClient, httpx_mock: HTTPXMock) -> None:
    """client.entity_health_report() calls GET /v1/monitor/entities/{id}/report."""
    entity_id = "mon-001"
    response_payload = {
        "report_id": "hr-001",
        "entity_identifier": "099369820",
        "status": "generating",
        "risk_score": None,
    }
    httpx_mock.add_response(url=f"{BASE}/v1/monitor/entities/{entity_id}/report", json=response_payload)

    result = client.entity_health_report(entity_id)

    assert result == response_payload
    req = httpx_mock.get_requests()[0]
    assert req.method == "GET"
    assert req.url.path == f"/v1/monitor/entities/{entity_id}/report"
