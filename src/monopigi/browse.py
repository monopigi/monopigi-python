"""Interactive document browser using Textual TUI."""

from __future__ import annotations

HAS_TEXTUAL = False

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.widgets import DataTable, Footer, Header, Input

    HAS_TEXTUAL = True
except ImportError:
    pass


def check_textual() -> None:
    """Raise a helpful error if textual is not installed."""
    if not HAS_TEXTUAL:
        raise ImportError("Interactive browse requires 'textual'. Install with: pip install monopigi-sdk[fuzzy]")


if HAS_TEXTUAL:
    from typing import ClassVar

    class DocumentBrowser(App):  # type: ignore[misc]
        """Interactive TUI for browsing Monopigi documents."""

        TITLE = "Monopigi Document Browser"
        BINDINGS: ClassVar[list[Binding]] = [
            Binding("q", "quit", "Quit"),
            Binding("escape", "quit", "Quit"),
        ]

        def __init__(self, documents: list[dict], source: str = "") -> None:
            super().__init__()
            self._documents = documents
            self._source = source

        def compose(self) -> ComposeResult:
            yield Header()
            yield Input(
                placeholder="Type source name or filter text... (e.g. ted, hospital, diavgeia)",
                id="filter",
            )
            yield DataTable()
            yield Footer()

        def on_mount(self) -> None:
            table = self.query_one(DataTable)
            table.add_columns("Source", "Title", "Date", "Score")
            if not self._documents:
                table.add_row("—", "No documents loaded. Type a source name above to search.", "—", "—")
            else:
                self._populate_table(table, "")

        def on_input_changed(self, event: Input.Changed) -> None:
            table = self.query_one(DataTable)
            table.clear()
            self._populate_table(table, event.value.lower())

        def _populate_table(self, table: DataTable, filter_text: str) -> None:
            for doc in self._documents:
                title = doc.get("title") or "\u2014"
                source_lower = (doc.get("source") or "").lower()
                if filter_text and filter_text not in title.lower() and filter_text not in source_lower:
                    continue
                table.add_row(
                    doc.get("source", "\u2014"),
                    title[:80],
                    doc.get("published_at") or "\u2014",
                    f"{doc.get('quality_score', 0):.2f}" if doc.get("quality_score") else "\u2014",
                )


def browse_documents(documents: list[dict], source: str = "") -> None:
    """Launch the interactive document browser."""
    check_textual()
    app = DocumentBrowser(documents, source)
    app.run()
