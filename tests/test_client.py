"""Tests for Monopigi API client."""

import pytest
from monopigi_sdk.client import MonopigiClient
from monopigi_sdk.exceptions import AuthError, NotFoundError, RateLimitError
from pytest_httpx import HTTPXMock


@pytest.fixture
def client(api_token, base_url):
    return MonopigiClient(token=api_token, base_url=base_url)


def test_client_sets_auth_header(client):
    assert "Authorization" in client._client.headers
    assert client._client.headers["Authorization"].startswith("Bearer mp_live_")


def test_sources(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://api.monopigi.com/v1/sources",
        json=[{"name": "ted", "label": "TED", "status": "active", "description": "EU procurement"}],
    )
    sources = client.sources()
    assert len(sources) == 1
    assert sources[0].name == "ted"


def test_search(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        json={"query": "hospital", "results": [], "total": 0, "limit": 100, "offset": 0},
    )
    resp = client.search("hospital")
    assert resp.query == "hospital"
    assert resp.total == 0


def test_documents(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        json={"source": "ted", "documents": [], "total": 0, "limit": 100, "offset": 0},
    )
    resp = client.documents("ted")
    assert resp.source == "ted"


def test_stats(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(json={"total_documents": 100, "sources": {}})
    resp = client.stats()
    assert resp.total_documents == 100


def test_usage(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        json={
            "tier": "free",
            "daily_quota": 10,
            "daily_used": 3,
            "daily_remaining": 7,
            "reset_at": "2026-03-17T00:00:00Z",
        },
    )
    resp = client.usage()
    assert resp.daily_remaining == 7


def test_401_raises_auth_error(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(status_code=401, json={"detail": "Invalid API key"})
    with pytest.raises(AuthError):
        client.sources()


def test_429_raises_rate_limit_error(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        status_code=429,
        json={"detail": "Rate limit exceeded"},
        headers={"X-RateLimit-Reset": "1710547200"},
    )
    with pytest.raises(RateLimitError):
        client.sources()


def test_404_raises_not_found_error(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(status_code=404, json={"detail": "Unknown source: foo"})
    with pytest.raises(NotFoundError):
        client.documents("foo")
