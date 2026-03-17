"""Sync and async HTTP clients for the Monopigi API."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from monopigi_sdk.cache import DiskCache
from monopigi_sdk.config import DEFAULT_BASE_URL, Config, load_config
from monopigi_sdk.exceptions import AuthError, MonopigiError, NotFoundError, RateLimitError
from monopigi_sdk.models import (
    Document,
    DocumentsResponse,
    SearchResponse,
    Source,
    StatsResponse,
    UsageResponse,
)

if TYPE_CHECKING:
    from monopigi_sdk.sources import (
        AsyncDataGovGrSource,
        AsyncDiavgeiaSource,
        AsyncElstatSource,
        AsyncMitosSource,
        AsyncRaeSource,
        AsyncTedSource,
        DataGovGrSource,
        DiavgeiaSource,
        ElstatSource,
        MitosSource,
        RaeSource,
        TedSource,
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

    def __init__(
        self,
        token: str = "",
        base_url: str = "",
        max_retries: int = 3,
        cache_ttl: int | None = None,
    ) -> None:
        token, base_url = _resolve_config(token, base_url)
        self._max_retries = max_retries
        self._cache: DiskCache | None = DiskCache(cache_ttl) if cache_ttl else None
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )

    def _request_with_retry(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        """Make a request with automatic retry on 429 rate-limit responses."""
        resp: httpx.Response | None = None
        for attempt in range(self._max_retries + 1):
            resp = self._client.request(method, path, **kwargs)  # type: ignore[arg-type]
            if resp.status_code == 429 and attempt < self._max_retries:
                reset = resp.headers.get("X-RateLimit-Reset", "")
                wait = max(1, int(reset) - int(time.time())) if reset.isdigit() else 60
                wait = min(wait, 300)  # cap at 5 min
                time.sleep(wait)
                continue
            if resp.status_code >= 400:
                _handle_error(resp)
            return resp
        assert resp is not None
        _handle_error(resp)
        raise AssertionError("unreachable")  # pragma: no cover

    def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        if self._cache is not None:
            cache_params = json.dumps(kwargs.get("params", {}), sort_keys=True)
            url = str(self._client.base_url) + path
            cached = self._cache.get(method, url, cache_params)
            if cached is not None:
                return httpx.Response(200, text=cached)
            resp = self._request_with_retry(method, path, **kwargs)
            self._cache.set(method, url, cache_params, resp.text)
            return resp
        return self._request_with_retry(method, path, **kwargs)

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

    # -- Pagination iterators --------------------------------------------------

    def search_iter(self, query: str, page_size: int = 100) -> Iterator[Document]:
        """Iterate through all search results, auto-paginating."""
        offset = 0
        while True:
            resp = self.search(query, limit=page_size, offset=offset)
            yield from resp.results
            offset += page_size
            if offset >= resp.total:
                break

    def documents_iter(self, source: str, page_size: int = 100, since: str | None = None) -> Iterator[Document]:
        """Iterate through all documents from a source, auto-paginating."""
        offset = 0
        while True:
            resp = self.documents(source, limit=page_size, offset=offset, since=since)
            yield from resp.documents
            offset += page_size
            if offset >= resp.total:
                break

    # -- Bulk export -----------------------------------------------------------

    def export(
        self,
        source: str,
        path: str,
        format: str = "json",
        since: str | None = None,
        limit: int | None = None,
    ) -> int:
        """Export documents from a source to a file. Returns number of documents exported.

        Formats: json, csv, parquet (requires polars)
        """
        from monopigi_sdk.progress import iter_with_progress

        # First get total count
        resp = self.documents(source, limit=1, since=since)
        total = resp.total

        # Then iterate with progress
        raw_iter = self.documents_iter(source, since=since)
        docs = list(iter_with_progress(raw_iter, total=total, description=f"Exporting {source}"))
        if limit:
            docs = docs[:limit]

        data = [doc.model_dump() for doc in docs]

        if format == "json":
            import json as _json

            Path(path).write_text(_json.dumps(data, indent=2, ensure_ascii=False))
        elif format == "csv":
            import csv

            if data:
                with open(path, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows({k: str(v) if v is not None else "" for k, v in row.items()} for row in data)
        elif format == "parquet":
            import polars as pl

            pl.DataFrame(data).write_parquet(path)
        else:
            raise ValueError(f"Unsupported format: {format}. Use json, csv, or parquet.")

        return len(docs)

    # -- Source-specific typed clients ------------------------------------------

    @property
    def ted(self) -> TedSource:
        from monopigi_sdk.sources import TedSource

        return TedSource(self)

    @property
    def diavgeia(self) -> DiavgeiaSource:
        from monopigi_sdk.sources import DiavgeiaSource

        return DiavgeiaSource(self)

    @property
    def elstat(self) -> ElstatSource:
        from monopigi_sdk.sources import ElstatSource

        return ElstatSource(self)

    @property
    def rae(self) -> RaeSource:
        from monopigi_sdk.sources import RaeSource

        return RaeSource(self)

    @property
    def data_gov_gr(self) -> DataGovGrSource:
        from monopigi_sdk.sources import DataGovGrSource

        return DataGovGrSource(self)

    @property
    def mitos(self) -> MitosSource:
        from monopigi_sdk.sources import MitosSource

        return MitosSource(self)

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

    def __init__(
        self,
        token: str = "",
        base_url: str = "",
        max_retries: int = 3,
        cache_ttl: int | None = None,
    ) -> None:
        token, base_url = _resolve_config(token, base_url)
        self._max_retries = max_retries
        self._cache: DiskCache | None = DiskCache(cache_ttl) if cache_ttl else None
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )

    async def _request_with_retry(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        """Make a request with automatic retry on 429 rate-limit responses."""
        resp: httpx.Response | None = None
        for attempt in range(self._max_retries + 1):
            resp = await self._client.request(method, path, **kwargs)  # type: ignore[arg-type]
            if resp.status_code == 429 and attempt < self._max_retries:
                reset = resp.headers.get("X-RateLimit-Reset", "")
                wait = max(1, int(reset) - int(time.time())) if reset.isdigit() else 60
                wait = min(wait, 300)  # cap at 5 min
                await asyncio.sleep(wait)
                continue
            if resp.status_code >= 400:
                _handle_error(resp)
            return resp
        assert resp is not None
        _handle_error(resp)
        raise AssertionError("unreachable")  # pragma: no cover

    async def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        if self._cache is not None:
            cache_params = json.dumps(kwargs.get("params", {}), sort_keys=True)
            url = str(self._client.base_url) + path
            cached = self._cache.get(method, url, cache_params)
            if cached is not None:
                return httpx.Response(200, text=cached)
            resp = await self._request_with_retry(method, path, **kwargs)
            self._cache.set(method, url, cache_params, resp.text)
            return resp
        return await self._request_with_retry(method, path, **kwargs)

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

    # -- Pagination iterators --------------------------------------------------

    async def search_iter(self, query: str, page_size: int = 100) -> AsyncIterator[Document]:
        """Iterate through all search results, auto-paginating."""
        offset = 0
        while True:
            resp = await self.search(query, limit=page_size, offset=offset)
            for doc in resp.results:
                yield doc
            offset += page_size
            if offset >= resp.total:
                break

    async def documents_iter(
        self, source: str, page_size: int = 100, since: str | None = None
    ) -> AsyncIterator[Document]:
        """Iterate through all documents from a source, auto-paginating."""
        offset = 0
        while True:
            resp = await self.documents(source, limit=page_size, offset=offset, since=since)
            for doc in resp.documents:
                yield doc
            offset += page_size
            if offset >= resp.total:
                break

    # -- Source-specific typed clients ------------------------------------------

    @property
    def ted(self) -> AsyncTedSource:
        from monopigi_sdk.sources import AsyncTedSource

        return AsyncTedSource(self)

    @property
    def diavgeia(self) -> AsyncDiavgeiaSource:
        from monopigi_sdk.sources import AsyncDiavgeiaSource

        return AsyncDiavgeiaSource(self)

    @property
    def elstat(self) -> AsyncElstatSource:
        from monopigi_sdk.sources import AsyncElstatSource

        return AsyncElstatSource(self)

    @property
    def rae(self) -> AsyncRaeSource:
        from monopigi_sdk.sources import AsyncRaeSource

        return AsyncRaeSource(self)

    @property
    def data_gov_gr(self) -> AsyncDataGovGrSource:
        from monopigi_sdk.sources import AsyncDataGovGrSource

        return AsyncDataGovGrSource(self)

    @property
    def mitos(self) -> AsyncMitosSource:
        from monopigi_sdk.sources import AsyncMitosSource

        return AsyncMitosSource(self)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AsyncMonopigiClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
