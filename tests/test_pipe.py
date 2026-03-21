"""Tests for pipe enrichment."""

import json
from io import StringIO
from unittest.mock import MagicMock, patch

from monopigi.pipe import pipe_search


def test_pipe_search_reads_stdin() -> None:
    mock_doc = MagicMock()
    mock_doc.model_dump.return_value = {"source": "ted", "title": "Hospital", "source_id": "ted:1"}

    mock_resp = MagicMock()
    mock_resp.results = [mock_doc]

    mock_client = MagicMock()
    mock_client.search.return_value = mock_resp

    stdin = StringIO("hospital\nprocurement\n")
    stdout = StringIO()

    with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
        pipe_search(mock_client, limit=1)

    output = stdout.getvalue()
    lines = [line for line in output.strip().split("\n") if line]
    assert len(lines) == 2  # one result per query line
    parsed = json.loads(lines[0])
    assert parsed["_query"] == "hospital"
    assert parsed["source"] == "ted"
