"""Monopigi CLI — query Greek government data from the command line.

Pipe-friendly: auto-detects TTY and switches to JSON when piping.
Supports JSONL for streaming with jq, grep, wc.
"""

from __future__ import annotations

import csv
import json
import sys
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

from monopigi_sdk.config import DEFAULT_CONFIG_PATH, load_config, save_config
from monopigi_sdk.exceptions import MonopigiError
from monopigi_sdk.models import OutputFormat, SourceStatus

if TYPE_CHECKING:
    from monopigi_sdk.client import MonopigiClient
    from monopigi_sdk.models import Document

app = typer.Typer(name="monopigi", help="Query Greek government data from the command line.")
auth_app = typer.Typer(help="Manage API authentication.")
app.add_typer(auth_app, name="auth")

console = Console()


def _is_pipe() -> bool:
    """Check if stdout is being piped (not a TTY)."""
    return not sys.stdout.isatty()


def _resolve_format(fmt: OutputFormat) -> OutputFormat:
    """Auto-switch to JSON when piping, unless user explicitly chose a format."""
    if fmt == OutputFormat.TABLE and _is_pipe():
        return OutputFormat.JSONL
    return fmt


def _get_client(cache: bool = False) -> MonopigiClient:
    from monopigi_sdk.client import MonopigiClient

    cfg = load_config(config_path=DEFAULT_CONFIG_PATH)
    if not cfg.token:
        console.print("[red]No API token configured.[/red] Run: monopigi auth login <token>")
        raise typer.Exit(1)
    cache_ttl = 300 if cache else 0
    return MonopigiClient(token=cfg.token, base_url=cfg.base_url, cache_ttl=cache_ttl)


def _filter_fields(doc_dict: dict, fields: str | None) -> dict:
    """Filter a document dict to only include specified fields."""
    if not fields:
        return doc_dict
    field_list = [f.strip() for f in fields.split(",")]
    return {k: v for k, v in doc_dict.items() if k in field_list}


def _output_docs(docs: list[Document], fmt: OutputFormat, fields: str | None, title: str = "") -> None:
    """Output a list of documents in the specified format."""
    fmt = _resolve_format(fmt)

    if fmt == OutputFormat.JSONL:
        for doc in docs:
            print(json.dumps(_filter_fields(doc.model_dump(), fields), ensure_ascii=False))
    elif fmt == OutputFormat.JSON:
        data = [_filter_fields(doc.model_dump(), fields) for doc in docs]
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif fmt == OutputFormat.CSV:
        if docs:
            filtered = [_filter_fields(doc.model_dump(), fields) for doc in docs]
            writer = csv.DictWriter(sys.stdout, fieldnames=list(filtered[0].keys()))
            writer.writeheader()
            for row in filtered:
                writer.writerow({k: str(v) if v is not None else "" for k, v in row.items()})
    else:
        # Rich table
        table = Table(title=title)
        table.add_column("Source", style="cyan")
        table.add_column("Title", max_width=60)
        table.add_column("Date")
        table.add_column("Score")
        for doc in docs:
            table.add_row(
                doc.source,
                doc.title or "—",
                doc.published_at or "—",
                f"{doc.quality_score:.2f}" if doc.quality_score else "—",
            )
        console.print(table)


@auth_app.command("login")
def auth_login(token: str = typer.Argument(..., help="Your Monopigi API token (mp_live_...)")) -> None:
    """Save your API token."""
    save_config(token, config_path=DEFAULT_CONFIG_PATH)
    console.print(f"[green]Token saved.[/green] Authenticated as {token[:16]}...")


@auth_app.command("status")
def auth_status() -> None:
    """Check authentication status."""
    cfg = load_config(config_path=DEFAULT_CONFIG_PATH)
    if cfg.token:
        console.print(f"[green]Authenticated[/green] — token: {cfg.token[:16]}... → {cfg.base_url}")
    else:
        console.print("[yellow]Not configured.[/yellow] Run: monopigi auth login <token>")


@auth_app.command("logout")
def auth_logout() -> None:
    """Remove saved token."""
    if DEFAULT_CONFIG_PATH.exists():
        DEFAULT_CONFIG_PATH.unlink()
        console.print("[green]Token removed.[/green]")
    else:
        console.print("No token to remove.")


@app.command()
def sources() -> None:
    """List available data sources."""
    try:
        with _get_client() as client:
            result = client.sources()
            if _is_pipe():
                for s in result:
                    print(json.dumps(s.model_dump(), ensure_ascii=False))
            else:
                table = Table(title="Monopigi Data Sources")
                table.add_column("Name", style="cyan")
                table.add_column("Label")
                table.add_column("Status")
                table.add_column("Description", style="dim")
                for s in result:
                    status_style = "green" if s.status == SourceStatus.ACTIVE else "yellow"
                    table.add_row(s.name, s.label, f"[{status_style}]{s.status}[/{status_style}]", s.description)
                console.print(table)
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max results"),
    fmt: OutputFormat = typer.Option(OutputFormat.TABLE, "--format", "-f", help="Output format"),  # noqa: B008
    fields: str | None = typer.Option(None, "--fields", help="Comma-separated fields to include"),
    cache: bool = typer.Option(False, "--cache", help="Cache results locally (5 min TTL)"),
    count: bool = typer.Option(False, "--count", help="Just print the total count"),
) -> None:
    """Search across all Greek government data sources.

    Pipe-friendly: auto-outputs JSONL when piped. Use with jq, grep, wc.

    Examples:
        monopigi search "hospital" --format jsonl | jq '.title'
        monopigi search "procurement" --fields source,title --format csv
        monopigi search "Athens" --count
        monopigi search "hospital" --cache | grep diavgeia
    """
    try:
        with _get_client(cache=cache) as client:
            resp = client.search(query, limit=limit)
            if count:
                print(resp.total)
            else:
                _output_docs(resp.results, fmt, fields, title=f'Search: "{query}" — {resp.total} results')
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def documents(
    source: str = typer.Argument(..., help="Source name (e.g. ted, diavgeia)"),
    limit: int = typer.Option(10, "--limit", "-l"),
    since: str | None = typer.Option(None, "--since", help="ISO date, e.g. 2026-01-01"),
    fmt: OutputFormat = typer.Option(OutputFormat.TABLE, "--format", "-f", help="Output format"),  # noqa: B008
    fields: str | None = typer.Option(None, "--fields", help="Comma-separated fields to include"),
    cache: bool = typer.Option(False, "--cache", help="Cache results locally (5 min TTL)"),
    count: bool = typer.Option(False, "--count", help="Just print the total count"),
) -> None:
    """Query documents from a specific source.

    Examples:
        monopigi documents ted --format jsonl | jq 'select(.quality_score > 0.9)'
        monopigi documents diavgeia --since 2026-01-01 --fields title,source_url --format csv
        monopigi documents ted --count
    """
    try:
        with _get_client(cache=cache) as client:
            resp = client.documents(source, limit=limit, since=since)
            if count:
                print(resp.total)
            else:
                _output_docs(resp.documents, fmt, fields, title=f"{source} — {resp.total} documents")
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def stats() -> None:
    """Show platform-wide statistics."""
    try:
        with _get_client() as client:
            resp = client.stats()
            if _is_pipe():
                print(json.dumps(resp.model_dump(), indent=2, ensure_ascii=False))
            else:
                console.print(f"\n[bold]Total documents:[/bold] {resp.total_documents:,}\n")
                if resp.sources:
                    table = Table(title="Sources")
                    table.add_column("Source", style="cyan")
                    table.add_column("Documents", justify="right")
                    table.add_column("Last Updated")
                    table.add_column("Avg Quality", justify="right")
                    for name, info in resp.sources.items():
                        table.add_row(
                            name,
                            f"{info.documents:,}",
                            info.last_updated or "—",
                            f"{info.avg_quality:.2f}" if info.avg_quality else "—",
                        )
                    console.print(table)
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def usage() -> None:
    """Show your API usage for today."""
    try:
        with _get_client() as client:
            resp = client.usage()
            if _is_pipe():
                print(json.dumps(resp.model_dump(), ensure_ascii=False))
            else:
                console.print(f"\n[bold]Tier:[/bold] {resp.tier}")
                console.print(f"[bold]Daily quota:[/bold] {resp.daily_quota}")
                console.print(f"[bold]Used today:[/bold] {resp.daily_used}")
                console.print(f"[bold]Remaining:[/bold] {resp.daily_remaining}")
                console.print(f"[bold]Resets at:[/bold] {resp.reset_at}\n")
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def export(
    source: str = typer.Argument(..., help="Source name"),
    path: str = typer.Argument(..., help="Output file path"),
    fmt: str = typer.Option("json", "--format", "-f", help="json, csv, parquet"),
    since: str | None = typer.Option(None, "--since"),
    limit: int | None = typer.Option(None, "--limit", "-l"),
) -> None:
    """Export documents from a source to a file.

    Examples:
        monopigi export ted tenders.json
        monopigi export diavgeia decisions.csv -f csv --since 2026-01-01
        monopigi export ted tenders.parquet -f parquet
    """
    try:
        with _get_client() as client:
            count = client.export(source, path, format=fmt, since=since, limit=limit)
            console.print(f"[green]Exported {count} documents to {path}[/green]")
    except (MonopigiError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
