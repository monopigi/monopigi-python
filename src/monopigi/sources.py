"""Source-specific typed clients with domain-specific fields."""

from __future__ import annotations

from typing import TYPE_CHECKING

from monopigi.models import DocumentsResponse

if TYPE_CHECKING:
    from monopigi.client import AsyncMonopigiClient, MonopigiClient


# -- Sync source clients -------------------------------------------------------


class TedSource:
    """Typed client for TED EU procurement data."""

    def __init__(self, client: MonopigiClient) -> None:
        self._client = client

    def search(self, query: str = "", limit: int = 100, offset: int = 0) -> DocumentsResponse:
        return self._client.documents("ted", limit=limit, offset=offset)

    def notices(self, limit: int = 100, since: str | None = None) -> DocumentsResponse:
        return self._client.documents("ted", limit=limit, since=since)


class DiavgeiaSource:
    """Typed client for Diavgeia government transparency decisions."""

    def __init__(self, client: MonopigiClient) -> None:
        self._client = client

    def decisions(self, limit: int = 100, since: str | None = None) -> DocumentsResponse:
        return self._client.documents("diavgeia", limit=limit, since=since)


class ElstatSource:
    def __init__(self, client: MonopigiClient) -> None:
        self._client = client

    def datasets(self, limit: int = 100) -> DocumentsResponse:
        return self._client.documents("elstat", limit=limit)


class RaeSource:
    def __init__(self, client: MonopigiClient) -> None:
        self._client = client

    def permits(self, limit: int = 100) -> DocumentsResponse:
        return self._client.documents("rae", limit=limit)


class DataGovGrSource:
    def __init__(self, client: MonopigiClient) -> None:
        self._client = client

    def datasets(self, limit: int = 100) -> DocumentsResponse:
        return self._client.documents("data_gov_gr", limit=limit)


class MitosSource:
    def __init__(self, client: MonopigiClient) -> None:
        self._client = client

    def organizations(self, limit: int = 100) -> DocumentsResponse:
        return self._client.documents("mitos", limit=limit)

    def services(self, limit: int = 100) -> DocumentsResponse:
        return self._client.documents("mitos", limit=limit)


class KimdisSource:
    """Typed client for KIMDIS Greek public procurement data."""

    def __init__(self, client: MonopigiClient) -> None:
        self._client = client

    def contracts(self, limit: int = 100, since: str | None = None) -> DocumentsResponse:
        return self._client.documents("kimdis", limit=limit, since=since)


class GeodataSource:
    """Typed client for Greek geospatial data (OGC WFS + ESRI)."""

    def __init__(self, client: MonopigiClient) -> None:
        self._client = client

    def layers(self, limit: int = 100) -> DocumentsResponse:
        return self._client.documents("geodata", limit=limit)


# -- Async source clients ------------------------------------------------------


class AsyncTedSource:
    """Async typed client for TED EU procurement data."""

    def __init__(self, client: AsyncMonopigiClient) -> None:
        self._client = client

    async def search(self, query: str = "", limit: int = 100, offset: int = 0) -> DocumentsResponse:
        return await self._client.documents("ted", limit=limit, offset=offset)

    async def notices(self, limit: int = 100, since: str | None = None) -> DocumentsResponse:
        return await self._client.documents("ted", limit=limit, since=since)


class AsyncDiavgeiaSource:
    """Async typed client for Diavgeia government transparency decisions."""

    def __init__(self, client: AsyncMonopigiClient) -> None:
        self._client = client

    async def decisions(self, limit: int = 100, since: str | None = None) -> DocumentsResponse:
        return await self._client.documents("diavgeia", limit=limit, since=since)


class AsyncElstatSource:
    def __init__(self, client: AsyncMonopigiClient) -> None:
        self._client = client

    async def datasets(self, limit: int = 100) -> DocumentsResponse:
        return await self._client.documents("elstat", limit=limit)


class AsyncRaeSource:
    def __init__(self, client: AsyncMonopigiClient) -> None:
        self._client = client

    async def permits(self, limit: int = 100) -> DocumentsResponse:
        return await self._client.documents("rae", limit=limit)


class AsyncDataGovGrSource:
    def __init__(self, client: AsyncMonopigiClient) -> None:
        self._client = client

    async def datasets(self, limit: int = 100) -> DocumentsResponse:
        return await self._client.documents("data_gov_gr", limit=limit)


class AsyncMitosSource:
    def __init__(self, client: AsyncMonopigiClient) -> None:
        self._client = client

    async def organizations(self, limit: int = 100) -> DocumentsResponse:
        return await self._client.documents("mitos", limit=limit)

    async def services(self, limit: int = 100) -> DocumentsResponse:
        return await self._client.documents("mitos", limit=limit)


class AsyncKimdisSource:
    """Async typed client for KIMDIS Greek public procurement data."""

    def __init__(self, client: AsyncMonopigiClient) -> None:
        self._client = client

    async def contracts(self, limit: int = 100, since: str | None = None) -> DocumentsResponse:
        return await self._client.documents("kimdis", limit=limit, since=since)


class AsyncGeodataSource:
    """Async typed client for Greek geospatial data."""

    def __init__(self, client: AsyncMonopigiClient) -> None:
        self._client = client

    async def layers(self, limit: int = 100) -> DocumentsResponse:
        return await self._client.documents("geodata", limit=limit)
