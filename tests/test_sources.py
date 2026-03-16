"""Tests for source-specific typed clients."""

from monopigi_sdk.client import MonopigiClient
from monopigi_sdk.models import DocumentsResponse
from monopigi_sdk.sources import DiavgeiaSource, TedSource
from pytest_httpx import HTTPXMock


def _docs_response(source: str) -> dict:
    return {
        "source": source,
        "documents": [{"source_id": "1", "source": source, "title": "Test"}],
        "total": 1,
        "limit": 100,
        "offset": 0,
    }


def test_ted_notices(api_token: str, base_url: str, httpx_mock: HTTPXMock) -> None:
    """TedSource.notices delegates to client.documents('ted', ...)."""
    httpx_mock.add_response(json=_docs_response("ted"))
    client = MonopigiClient(token=api_token, base_url=base_url)
    resp = client.ted.notices(limit=50)
    assert isinstance(resp, DocumentsResponse)
    assert resp.source == "ted"
    assert len(resp.documents) == 1


def test_diavgeia_decisions(api_token: str, base_url: str, httpx_mock: HTTPXMock) -> None:
    """DiavgeiaSource.decisions delegates to client.documents('diavgeia', ...)."""
    httpx_mock.add_response(json=_docs_response("diavgeia"))
    client = MonopigiClient(token=api_token, base_url=base_url)
    resp = client.diavgeia.decisions(limit=50)
    assert isinstance(resp, DocumentsResponse)
    assert resp.source == "diavgeia"


def test_client_has_source_properties(api_token: str, base_url: str) -> None:
    """MonopigiClient exposes all source-specific properties."""
    client = MonopigiClient(token=api_token, base_url=base_url)
    assert hasattr(client, "ted")
    assert hasattr(client, "diavgeia")
    assert hasattr(client, "elstat")
    assert hasattr(client, "rae")
    assert hasattr(client, "data_gov_gr")
    assert hasattr(client, "mitos")

    # Verify they return source instances
    assert isinstance(client.ted, TedSource)
    assert isinstance(client.diavgeia, DiavgeiaSource)
