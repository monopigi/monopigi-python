"""Stdin enrichment utilities -- search each line from stdin."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from monopigi_sdk.client import MonopigiClient


def pipe_search(client: MonopigiClient, limit: int = 3) -> None:
    """Read lines from stdin and search for each one, outputting results as JSONL."""
    for line in sys.stdin:
        query = line.strip()
        if not query:
            continue
        try:
            resp = client.search(query, limit=limit)
            for doc in resp.results:
                result = doc.model_dump()
                result["_query"] = query
                print(json.dumps(result, ensure_ascii=False))
        except Exception:
            print(
                json.dumps({"_query": query, "_error": "search failed"}, ensure_ascii=False),
                file=sys.stderr,
            )
