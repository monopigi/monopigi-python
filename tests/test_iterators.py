"""Tests for pagination iterators."""

from monopigi.client import MonopigiClient
from pytest_httpx import HTTPXMock


def _doc(source_id: str) -> dict:
    return {"source_id": source_id, "source": "ted", "title": f"Doc {source_id}"}


def test_search_iter_paginates(api_token: str, base_url: str, httpx_mock: HTTPXMock) -> None:
    """search_iter yields all docs across 2 pages."""
    httpx_mock.add_response(
        json={"query": "q", "results": [_doc("1"), _doc("2")], "total": 3, "limit": 2, "offset": 0},
    )
    httpx_mock.add_response(
        json={"query": "q", "results": [_doc("3")], "total": 3, "limit": 2, "offset": 2},
    )
    client = MonopigiClient(token=api_token, base_url=base_url)
    docs = list(client.search_iter("q", page_size=2))
    assert len(docs) == 3
    assert [d.source_id for d in docs] == ["1", "2", "3"]


def test_documents_iter_paginates(api_token: str, base_url: str, httpx_mock: HTTPXMock) -> None:
    """documents_iter yields all docs across 2 pages."""
    httpx_mock.add_response(
        json={"source": "ted", "documents": [_doc("a"), _doc("b")], "total": 3, "limit": 2, "offset": 0},
    )
    httpx_mock.add_response(
        json={"source": "ted", "documents": [_doc("c")], "total": 3, "limit": 2, "offset": 2},
    )
    client = MonopigiClient(token=api_token, base_url=base_url)
    docs = list(client.documents_iter("ted", page_size=2))
    assert len(docs) == 3
    assert [d.source_id for d in docs] == ["a", "b", "c"]


def test_search_iter_stops_at_total(api_token: str, base_url: str, httpx_mock: HTTPXMock) -> None:
    """search_iter stops when offset >= total (single page)."""
    httpx_mock.add_response(
        json={"query": "q", "results": [_doc("1")], "total": 1, "limit": 100, "offset": 0},
    )
    client = MonopigiClient(token=api_token, base_url=base_url)
    docs = list(client.search_iter("q", page_size=100))
    assert len(docs) == 1
    # Only one request should have been made
    assert len(httpx_mock.get_requests()) == 1
