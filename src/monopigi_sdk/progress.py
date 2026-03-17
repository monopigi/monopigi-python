"""Progress bar utilities for long-running operations."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from monopigi_sdk.models import Document


def iter_with_progress(
    documents: Iterator[Document],
    total: int | None = None,
    description: str = "Fetching",
) -> Iterator[Document]:
    """Wrap a document iterator with a Rich progress bar (only on TTY)."""
    if not sys.stdout.isatty():
        yield from documents
        return

    from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task(description, total=total)
        for doc in documents:
            yield doc
            progress.advance(task)
