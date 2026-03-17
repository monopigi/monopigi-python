"""Tests for progress bar utilities."""

from unittest.mock import MagicMock

from monopigi_sdk.progress import iter_with_progress


def test_iter_with_progress_yields_all() -> None:
    """Progress wrapper should yield all items."""
    items = [MagicMock() for _ in range(5)]
    result = list(iter_with_progress(iter(items), total=5))
    assert len(result) == 5


def test_iter_with_progress_no_total() -> None:
    """Works without total (spinner mode)."""
    items = [MagicMock() for _ in range(3)]
    result = list(iter_with_progress(iter(items)))
    assert len(result) == 3
