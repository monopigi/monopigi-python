"""Tests for tier awareness: quota tracking, TierError, and has_feature."""

import pytest
from monopigi.client import AsyncMonopigiClient, MonopigiClient
from monopigi.exceptions import TierError
from pytest_httpx import HTTPXMock


@pytest.fixture
def client(api_token, base_url):
    return MonopigiClient(token=api_token, base_url=base_url, max_retries=0)


# --- Tier and quota parsing from headers ---


def test_tier_and_quota_populated_from_headers(client, httpx_mock: HTTPXMock):
    """After a request with rate-limit headers, tier and quota are populated."""
    httpx_mock.add_response(
        json={"total_documents": 50, "sources": {}},
        headers={
            "X-Tier": "pro",
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Remaining": "4999",
            "X-RateLimit-Reset": "1710547200",
        },
    )
    assert client.tier is None
    assert client.quota is None
    client.stats()
    assert client.tier == "pro"
    assert client.quota is not None
    assert client.quota.limit == 5000
    assert client.quota.remaining == 4999
    assert client.quota.reset == "1710547200"


def test_quota_not_set_without_headers(client, httpx_mock: HTTPXMock):
    """Without rate-limit headers, quota stays None."""
    httpx_mock.add_response(json={"total_documents": 10, "sources": {}})
    client.stats()
    assert client.tier is None
    assert client.quota is None


def test_quota_updates_on_subsequent_requests(client, httpx_mock: HTTPXMock):
    """Quota info updates with each request."""
    httpx_mock.add_response(
        json={"total_documents": 10, "sources": {}},
        headers={
            "X-Tier": "free",
            "X-RateLimit-Limit": "5",
            "X-RateLimit-Remaining": "4",
            "X-RateLimit-Reset": "1710547200",
        },
    )
    httpx_mock.add_response(
        json={"total_documents": 10, "sources": {}},
        headers={
            "X-Tier": "free",
            "X-RateLimit-Limit": "5",
            "X-RateLimit-Remaining": "3",
            "X-RateLimit-Reset": "1710547200",
        },
    )
    client.stats()
    assert client.quota.remaining == 4
    client.stats()
    assert client.quota.remaining == 3


# --- TierError on 403 ---


def test_403_tier_error_with_pro_required(client, httpx_mock: HTTPXMock):
    """A 403 with tier info in the detail raises TierError."""
    httpx_mock.add_response(
        status_code=403,
        json={"detail": "This feature requires a Pro subscription. Upgrade at https://monopigi.com/pricing"},
    )
    with pytest.raises(TierError) as exc_info:
        client.search("test")
    assert exc_info.value.required_tier == "pro"
    assert exc_info.value.current_tier == "unknown"  # no tier header yet
    assert "requires pro tier" in str(exc_info.value).lower()


def test_403_tier_error_with_enterprise_required(client, httpx_mock: HTTPXMock):
    """A 403 requiring enterprise tier is parsed correctly."""
    httpx_mock.add_response(
        status_code=403,
        json={"detail": "This feature requires a Enterprise subscription. Upgrade at https://monopigi.com/pricing"},
        headers={"X-Tier": "free"},
    )
    with pytest.raises(TierError) as exc_info:
        client.search("test")
    assert exc_info.value.required_tier == "enterprise"
    assert exc_info.value.current_tier == "free"


def test_403_tier_error_includes_endpoint(client, httpx_mock: HTTPXMock):
    """TierError includes the endpoint path."""
    httpx_mock.add_response(
        status_code=403,
        json={"detail": "This feature requires a Pro subscription."},
    )
    with pytest.raises(TierError) as exc_info:
        client.documents("ted")
    assert "/v1/ted/documents" in exc_info.value.endpoint


# --- has_feature ---


def test_has_feature_returns_false_before_first_request(client):
    """Before any request, has_feature always returns False."""
    assert client.has_feature("metadata") is False
    assert client.has_feature("rag") is False


def test_has_feature_free_tier(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        json={"total_documents": 10, "sources": {}},
        headers={"X-Tier": "free"},
    )
    client.stats()
    assert client.has_feature("metadata") is True
    assert client.has_feature("basic_search") is True
    assert client.has_feature("full_text") is False
    assert client.has_feature("content") is False
    assert client.has_feature("rag") is False


def test_has_feature_pro_tier(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        json={"total_documents": 10, "sources": {}},
        headers={"X-Tier": "pro"},
    )
    client.stats()
    assert client.has_feature("metadata") is True
    assert client.has_feature("full_text") is True
    assert client.has_feature("content") is True
    assert client.has_feature("rag") is False
    assert client.has_feature("mcp") is False


def test_has_feature_enterprise_tier(client, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        json={"total_documents": 10, "sources": {}},
        headers={"X-Tier": "enterprise"},
    )
    client.stats()
    assert client.has_feature("metadata") is True
    assert client.has_feature("full_text") is True
    assert client.has_feature("content") is True
    assert client.has_feature("rag") is True
    assert client.has_feature("mcp") is True
    assert client.has_feature("entities") is True
    assert client.has_feature("similar") is True


# --- Async client tier awareness ---


@pytest.mark.asyncio
async def test_async_tier_and_quota(api_token, base_url, httpx_mock: HTTPXMock):
    """Async client also tracks tier and quota."""
    httpx_mock.add_response(
        json={"total_documents": 50, "sources": {}},
        headers={
            "X-Tier": "pro",
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Remaining": "4998",
            "X-RateLimit-Reset": "1710547200",
        },
    )
    async with AsyncMonopigiClient(token=api_token, base_url=base_url) as client:
        assert client.tier is None
        await client.stats()
        assert client.tier == "pro"
        assert client.quota.remaining == 4998
        assert client.has_feature("full_text") is True
        assert client.has_feature("rag") is False


@pytest.mark.asyncio
async def test_async_403_tier_error(api_token, base_url, httpx_mock: HTTPXMock):
    """Async client raises TierError on 403."""
    httpx_mock.add_response(
        status_code=403,
        json={"detail": "This feature requires a Pro subscription."},
        headers={"X-Tier": "free"},
    )
    async with AsyncMonopigiClient(token=api_token, base_url=base_url, max_retries=0) as client:
        with pytest.raises(TierError) as exc_info:
            await client.search("test")
        assert exc_info.value.required_tier == "pro"
        assert exc_info.value.current_tier == "free"
