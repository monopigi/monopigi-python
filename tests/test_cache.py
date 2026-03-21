"""Tests for the disk cache module and client cache integration."""

from __future__ import annotations

import pytest
from monopigi.cache import DiskCache
from monopigi.client import MonopigiClient
from pytest_httpx import HTTPXMock


@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path / "cache"


@pytest.fixture
def cache(cache_dir):
    return DiskCache(ttl=60, cache_dir=cache_dir)


class TestDiskCache:
    def test_cache_miss_returns_none(self, cache: DiskCache) -> None:
        assert cache.get("GET", "https://api.example.com/v1/search", "{}") is None

    def test_cache_hit_returns_body(self, cache: DiskCache) -> None:
        cache.set("GET", "https://api.example.com/v1/search", "{}", '{"results": []}')
        result = cache.get("GET", "https://api.example.com/v1/search", "{}")
        assert result == '{"results": []}'

    def test_cache_expired_returns_none(self, cache_dir, monkeypatch) -> None:
        import time as time_mod

        import monopigi.cache as cache_mod

        cache = DiskCache(ttl=10, cache_dir=cache_dir)
        cache.set("GET", "https://api.example.com/v1/search", "{}", '{"results": []}')
        # Capture real time, then patch to return a value 20s in the future
        future = time_mod.time() + 20
        monkeypatch.setattr(cache_mod.time, "time", lambda: future)
        result = cache.get("GET", "https://api.example.com/v1/search", "{}")
        assert result is None


class TestClientCacheIntegration:
    def test_client_uses_cache(self, api_token, base_url, httpx_mock: HTTPXMock, tmp_path) -> None:
        """Two identical requests should only hit the network once."""
        httpx_mock.add_response(
            json={"query": "hospital", "results": [], "total": 0, "limit": 100, "offset": 0},
        )
        cache_dir = tmp_path / "cache"
        client = MonopigiClient(token=api_token, base_url=base_url, cache_ttl=300)
        # Override the cache dir so we don't pollute the real one
        client._cache = DiskCache(ttl=300, cache_dir=cache_dir)

        resp1 = client.search("hospital")
        resp2 = client.search("hospital")

        assert resp1.query == "hospital"
        assert resp2.query == "hospital"
        # Only one HTTP request should have been made
        assert len(httpx_mock.get_requests()) == 1
