"""Sync and async HTTP clients for the Monopigi API."""

from __future__ import annotations

import httpx

from monopigi_sdk.config import DEFAULT_BASE_URL, Config, load_config
from monopigi_sdk.exceptions import AuthError, MonopigiError, NotFoundError, RateLimitError
from monopigi_sdk.models import (
    DocumentsResponse,
    SearchResponse,
    Source,
    StatsResponse,
    UsageResponse,
)


def _resolve_config(token: str, base_url: str) -> tuple[str, str]:
    """Resolve token and base_url from args or stored config."""
    if not token or not base_url:
        cfg: Config = load_config()
        token = token or cfg.token
        base_url = base_url or cfg.base_url
    if not token:
        raise AuthError("No API token provided. Run `monopigi auth login <token>` or pass token= to Client.")
    return token, base_url or DEFAULT_BASE_URL


def _handle_error(resp: httpx.Response) -> None:
    """Raise typed exceptions for HTTP error responses."""
    if resp.status_code == 401:
        raise AuthError("Invalid or missing API token")
    if resp.status_code == 429:
        reset = resp.headers.get("X-RateLimit-Reset", "")
        raise RateLimitError("Daily query quota exceeded", reset_at=reset)
    if resp.status_code == 404:
        try:
            detail = resp.json().get("detail", "Not found") if resp.content else "Not found"
        except (ValueError, KeyError):
            detail = "Not found"
        raise NotFoundError(detail)
    if resp.status_code >= 400:
        raise MonopigiError(f"API error {resp.status_code}: {resp.text}")


def _build_doc_params(limit: int, offset: int, since: str | None) -> dict[str, str | int]:
    """Build query params for document endpoints."""
    params: dict[str, str | int] = {"limit": limit, "offset": offset}
    if since:
        params["since"] = since
    return params


class MonopigiClient:
    """Synchronous client for the Monopigi API.

    Usage:
        with MonopigiClient("mp_live_...") as client:
            results = client.search("hospital procurement")
    """

    def __init__(self, token: str = "", base_url: str = "") -> None:
        token, base_url = _resolve_config(token, base_url)
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )

    def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        resp = self._client.request(method, path, **kwargs)  # type: ignore[arg-type]
        if resp.status_code >= 400:
            _handle_error(resp)
        return resp

    def sources(self) -> list[Source]:
        """List available data sources."""
        resp = self._request("GET", "/v1/sources")
        return [Source(**s) for s in resp.json()]

    def search(self, query: str, limit: int = 100, offset: int = 0) -> SearchResponse:
        """Search across all sources."""
        resp = self._request("GET", "/v1/search", params={"q": query, "limit": limit, "offset": offset})
        return SearchResponse(**resp.json())

    def documents(self, source: str, limit: int = 100, offset: int = 0, since: str | None = None) -> DocumentsResponse:
        """Query documents from a specific source."""
        resp = self._request("GET", f"/v1/{source}/documents", params=_build_doc_params(limit, offset, since))
        return DocumentsResponse(**resp.json())

    def stats(self) -> StatsResponse:
        """Get platform-wide statistics."""
        resp = self._request("GET", "/v1/stats")
        return StatsResponse(**resp.json())

    def usage(self) -> UsageResponse:
        """Get your API usage for today."""
        resp = self._request("GET", "/v1/usage")
        return UsageResponse(**resp.json())

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> MonopigiClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class AsyncMonopigiClient:
    """Async client for the Monopigi API.

    Usage:
        async with AsyncMonopigiClient("mp_live_...") as client:
            results = await client.search("hospital procurement")
    """

    def __init__(self, token: str = "", base_url: str = "") -> None:
        token, base_url = _resolve_config(token, base_url)
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )

    async def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        resp = await self._client.request(method, path, **kwargs)  # type: ignore[arg-type]
        if resp.status_code >= 400:
            _handle_error(resp)
        return resp

    async def sources(self) -> list[Source]:
        """List available data sources."""
        resp = await self._request("GET", "/v1/sources")
        return [Source(**s) for s in resp.json()]

    async def search(self, query: str, limit: int = 100, offset: int = 0) -> SearchResponse:
        """Search across all sources."""
        resp = await self._request("GET", "/v1/search", params={"q": query, "limit": limit, "offset": offset})
        return SearchResponse(**resp.json())

    async def documents(
        self, source: str, limit: int = 100, offset: int = 0, since: str | None = None
    ) -> DocumentsResponse:
        """Query documents from a specific source."""
        resp = await self._request("GET", f"/v1/{source}/documents", params=_build_doc_params(limit, offset, since))
        return DocumentsResponse(**resp.json())

    async def stats(self) -> StatsResponse:
        """Get platform-wide statistics."""
        resp = await self._request("GET", "/v1/stats")
        return StatsResponse(**resp.json())

    async def usage(self) -> UsageResponse:
        """Get your API usage for today."""
        resp = await self._request("GET", "/v1/usage")
        return UsageResponse(**resp.json())

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AsyncMonopigiClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
