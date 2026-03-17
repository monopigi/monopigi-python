"""Tests for bulk export."""

import csv
import json
from pathlib import Path

import pytest
from monopigi_sdk.client import MonopigiClient
from pytest_httpx import HTTPXMock


def _doc(source_id: str) -> dict:
    return {"source_id": source_id, "source": "ted", "title": f"Doc {source_id}"}


def _mock_single_page(httpx_mock: HTTPXMock) -> None:
    """Mock a count query (limit=1) followed by a single page of 2 documents."""
    # First call: count query with limit=1
    httpx_mock.add_response(
        json={
            "source": "ted",
            "documents": [_doc("1")],
            "total": 2,
            "limit": 1,
            "offset": 0,
        },
    )
    # Second call: full page fetch
    httpx_mock.add_response(
        json={
            "source": "ted",
            "documents": [_doc("1"), _doc("2")],
            "total": 2,
            "limit": 100,
            "offset": 0,
        },
    )


def test_export_json(api_token: str, base_url: str, httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    """Export to JSON writes valid JSON file."""
    _mock_single_page(httpx_mock)
    client = MonopigiClient(token=api_token, base_url=base_url)
    out = tmp_path / "out.json"
    count = client.export("ted", str(out), format="json")
    assert count == 2
    data = json.loads(out.read_text())
    assert len(data) == 2
    assert data[0]["source_id"] == "1"


def test_export_csv(api_token: str, base_url: str, httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    """Export to CSV writes valid CSV file."""
    _mock_single_page(httpx_mock)
    client = MonopigiClient(token=api_token, base_url=base_url)
    out = tmp_path / "out.csv"
    count = client.export("ted", str(out), format="csv")
    assert count == 2
    with open(out) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["source_id"] == "1"


def test_export_invalid_format(api_token: str, base_url: str, httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    """Export with unsupported format raises ValueError."""
    _mock_single_page(httpx_mock)
    client = MonopigiClient(token=api_token, base_url=base_url)
    out = tmp_path / "out.xyz"
    with pytest.raises(ValueError, match="Unsupported format"):
        client.export("ted", str(out), format="xyz")
