"""Simple disk-based response cache with TTL."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

DEFAULT_CACHE_DIR = Path.home() / ".monopigi" / "cache"


class DiskCache:
    """Cache API responses to disk as JSON files with a time-to-live."""

    def __init__(self, ttl: int, cache_dir: Path = DEFAULT_CACHE_DIR) -> None:
        self.ttl = ttl
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, method: str, url: str, params: str) -> str:
        raw = f"{method}:{url}:{params}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, method: str, url: str, params: str) -> str | None:
        """Return cached body if present and not expired, else None."""
        key = self._key(method, url, params)
        path = self.cache_dir / f"{key}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        if time.time() - data["ts"] > self.ttl:
            path.unlink()
            return None
        return data["body"]

    def set(self, method: str, url: str, params: str, body: str) -> None:
        """Store a response body in the cache."""
        key = self._key(method, url, params)
        path = self.cache_dir / f"{key}.json"
        path.write_text(json.dumps({"ts": time.time(), "body": body}))
