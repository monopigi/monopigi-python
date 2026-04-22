"""Tests for Monopigi API client."""

import pytest
from pytest_httpx import HTTPXMock

from monopigi.client import AsyncMonopigiClient, MonopigiClient
from monopigi.exceptions import AuthError, NotFoundError, RateLimitError


@pytest.fixture
def client(api_token, base_url):
    return MonopigiClient(token=api_token, base_url=base_url, max_retries=0)


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


def test_sync_context_manager(api_token: str, base_url: str, httpx_mock: HTTPXMock) -> None:
    """Sync client works as a context manager and closes the connection."""
    httpx_mock.add_response(
        json={"query": "test", "results": [], "total": 0, "limit": 10, "offset": 0},
    )
    with MonopigiClient(token=api_token, base_url=base_url) as client:
        resp = client.search("test", limit=10)
        assert resp.total == 0
    # After exiting, the underlying httpx client should be closed
    assert client._client.is_closed


@pytest.mark.asyncio
async def test_async_context_manager(api_token: str, base_url: str, httpx_mock: HTTPXMock) -> None:
    """Async client works as an async context manager and closes the connection."""
    httpx_mock.add_response(
        json={"query": "test", "results": [], "total": 0, "limit": 10, "offset": 0},
    )
    async with AsyncMonopigiClient(token=api_token, base_url=base_url) as client:
        resp = await client.search("test", limit=10)
        assert resp.total == 0
    assert client._client.is_closed


@pytest.mark.asyncio
async def test_async_sources(api_token: str, base_url: str, httpx_mock: HTTPXMock) -> None:
    """Async client can fetch sources."""
    httpx_mock.add_response(
        json=[{"name": "ted", "label": "TED", "status": "active", "description": "EU procurement"}],
    )
    async with AsyncMonopigiClient(token=api_token, base_url=base_url) as client:
        sources = await client.sources()
        assert len(sources) == 1
        assert sources[0].name == "ted"


# --- Rate-limit retry tests ---


def test_429_auto_retries(api_token: str, base_url: str, httpx_mock: HTTPXMock, monkeypatch) -> None:
    """Client retries on 429 and succeeds when the next response is 200."""
    monkeypatch.setattr("monopigi.client.time.sleep", lambda _: None)
    # First response: 429, second response: 200
    httpx_mock.add_response(
        status_code=429,
        json={"detail": "Rate limit exceeded"},
        headers={"X-RateLimit-Reset": "0"},
    )
    httpx_mock.add_response(
        json=[{"name": "ted", "label": "TED", "status": "active", "description": "EU procurement"}],
    )
    client = MonopigiClient(token=api_token, base_url=base_url, max_retries=3)
    sources = client.sources()
    assert len(sources) == 1
    assert len(httpx_mock.get_requests()) == 2


def test_429_exhausts_retries(api_token: str, base_url: str, httpx_mock: HTTPXMock, monkeypatch) -> None:
    """Client raises RateLimitError after exhausting all retries."""
    monkeypatch.setattr("monopigi.client.time.sleep", lambda _: None)
    # 4 responses: all 429 (1 initial + 3 retries)
    for _ in range(4):
        httpx_mock.add_response(
            status_code=429,
            json={"detail": "Rate limit exceeded"},
            headers={"X-RateLimit-Reset": "0"},
        )
    client = MonopigiClient(token=api_token, base_url=base_url, max_retries=3)
    with pytest.raises(RateLimitError):
        client.sources()
    assert len(httpx_mock.get_requests()) == 4
