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

app = typer.Typer(
    name="monopigi",
    help="Query Greek government data from the command line.",
    invoke_without_command=True,
    no_args_is_help=True,
)
auth_app = typer.Typer(help="Manage API authentication.", no_args_is_help=True)
app.add_typer(auth_app, name="auth")

console = Console()


def _require_arg(ctx: typer.Context, value: str | None) -> str:
    """Show help and exit if a required argument is missing."""
    if value is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)
    return value


SOURCE_ALIASES = {"e_procurement": "kimdis", "eprocurement": "kimdis"}


def _resolve_source(source: str) -> str:
    """Resolve source aliases (e.g., e_procurement → kimdis)."""
    return SOURCE_ALIASES.get(source, source)


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
        raw = json.dumps(data, indent=2, ensure_ascii=False)
        if sys.stdout.isatty():
            from rich.json import JSON as RichJSON

            console.print(RichJSON(raw))
        else:
            print(raw)
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
def auth_login(ctx: typer.Context, token: str | None = typer.Argument(None, help="Your Monopigi API token (mp_live_...)")) -> None:
    """Save your API token."""
    token = _require_arg(ctx, token)
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
    ctx: typer.Context,
    query: str | None = typer.Argument(None, help="Search query"),
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
    query = _require_arg(ctx, query)
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
    ctx: typer.Context,
    source: str | None = typer.Argument(None, help="Source name (e.g. ted, diavgeia)"),
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
    source = _resolve_source(_require_arg(ctx, source))
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
                raw = json.dumps(resp.model_dump(), indent=2, ensure_ascii=False)
                print(raw)
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
                raw = json.dumps(resp.model_dump(), ensure_ascii=False)
                print(raw)
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
    ctx: typer.Context,
    source: str | None = typer.Argument(None, help="Source name"),
    path: str | None = typer.Argument(None, help="Output file path"),
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
            source = _resolve_source(_require_arg(ctx, source))
            path = _require_arg(ctx, path)
            count = client.export(source, path, format=fmt, since=since, limit=limit)
            console.print(f"[green]Exported {count} documents to {path}[/green]")
    except (MonopigiError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def watch(
    ctx: typer.Context,
    query: str | None = typer.Argument(None, help="Search query"),
    interval: int = typer.Option(60, "--interval", "-i", help="Poll interval in seconds"),
    fmt: OutputFormat = typer.Option(OutputFormat.TABLE, "--format", "-f", help="Output format"),  # noqa: B008
) -> None:
    """Watch for new results in real-time. Ctrl+C to stop.

    Examples:
        monopigi watch "hospital procurement" --interval 30
        monopigi watch "tender" -i 10 --format jsonl | tee new_tenders.jsonl
    """
    import time

    query = _require_arg(ctx, query)
    seen_ids: set[str] = set()
    console.print(f"[dim]Watching for '{query}' every {interval}s... (Ctrl+C to stop)[/dim]")
    try:
        with _get_client(cache=False) as client:
            while True:
                resp = client.search(query, limit=100)
                new_docs = [doc for doc in resp.results if doc.source_id not in seen_ids]
                for doc in new_docs:
                    seen_ids.add(doc.source_id)
                if new_docs:
                    _output_docs(
                        new_docs,
                        fmt,
                        fields=None,
                        title=f"[{time.strftime('%H:%M:%S')}] {len(new_docs)} new",
                    )
                time.sleep(interval)
    except KeyboardInterrupt:
        console.print(f"\n[dim]Stopped. Saw {len(seen_ids)} unique documents.[/dim]")


@app.command()
def diff(
    ctx: typer.Context,
    source: str | None = typer.Argument(None, help="Source name"),
    since: str | None = typer.Option(None, "--since", help="ISO date (default: last check)"),
    fmt: OutputFormat = typer.Option(OutputFormat.TABLE, "--format", "-f", help="Output format"),  # noqa: B008
) -> None:
    """Show new documents since last check.

    Examples:
        monopigi diff ted
        monopigi diff diavgeia --since 2026-03-15
    """
    source = _resolve_source(_require_arg(ctx, source))
    import time

    last_check_file = DEFAULT_CONFIG_PATH.parent / "last_check.json"

    if not since and last_check_file.exists():
        data = json.loads(last_check_file.read_text())
        since = data.get(source)

    try:
        with _get_client() as client:
            resp = client.documents(source, limit=100, since=since)
            if resp.documents:
                _output_docs(
                    resp.documents,
                    fmt,
                    fields=None,
                    title=f"{source} — {len(resp.documents)} new since {since or 'beginning'}",
                )
            else:
                console.print(f"[dim]No new documents in {source} since {since or 'beginning'}[/dim]")

        # Save current timestamp
        last_check_file.parent.mkdir(parents=True, exist_ok=True)
        existing = json.loads(last_check_file.read_text()) if last_check_file.exists() else {}
        existing[source] = time.strftime("%Y-%m-%d")
        last_check_file.write_text(json.dumps(existing))
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


# -- Config sub-commands -------------------------------------------------------

config_app = typer.Typer(help="Manage CLI configuration.", no_args_is_help=True)
app.add_typer(config_app, name="config")

VALID_CONFIG_KEYS = {"base_url", "default_format", "default_source", "cache_ttl"}


@config_app.command("set")
def config_set(ctx: typer.Context, key: str | None = typer.Argument(None), value: str | None = typer.Argument(None)) -> None:
    """Set a config value.

    Keys:
        base_url         API base URL (default: https://api.monopigi.com)
        default_format   Output format: table, json, jsonl, csv (default: table)
        default_source   Default source for documents/diff/export commands
        cache_ttl        Cache TTL in seconds (default: 300)
    """
    key = _require_arg(ctx, key)
    value = _require_arg(ctx, value)
    if key not in VALID_CONFIG_KEYS:
        console.print(f"[red]Unknown key: {key}[/red]. Valid: {', '.join(sorted(VALID_CONFIG_KEYS))}")
        raise typer.Exit(1)
    config_file = DEFAULT_CONFIG_PATH.parent / "settings.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(config_file.read_text()) if config_file.exists() else {}
    existing[key] = value
    config_file.write_text(json.dumps(existing, indent=2))
    console.print(f"[green]{key}[/green] = {value}")


@config_app.command("get")
def config_get(ctx: typer.Context, key: str | None = typer.Argument(None)) -> None:
    """Get a config value."""
    key = _require_arg(ctx, key)
    config_file = DEFAULT_CONFIG_PATH.parent / "settings.json"
    if not config_file.exists():
        console.print("[dim]No settings configured.[/dim]")
        return
    settings = json.loads(config_file.read_text())
    value = settings.get(key, "[dim]not set[/dim]")
    console.print(f"{key} = {value}")


@config_app.command("list")
def config_list() -> None:
    """Show all config values."""
    config_file = DEFAULT_CONFIG_PATH.parent / "settings.json"
    auth_cfg = load_config(config_path=DEFAULT_CONFIG_PATH)
    console.print(
        f"[bold]token:[/bold] {auth_cfg.token[:16]}..." if auth_cfg.token else "[bold]token:[/bold] [dim]not set[/dim]"
    )
    console.print(f"[bold]base_url:[/bold] {auth_cfg.base_url}")
    if config_file.exists():
        settings = json.loads(config_file.read_text())
        for k, v in settings.items():
            console.print(f"[bold]{k}:[/bold] {v}")


@app.command()
def browse(
    source: str = typer.Argument("", help="Source name (optional — searches all if empty)"),
    query: str = typer.Option("", "--query", "-q", help="Pre-filter query"),
    limit: int = typer.Option(100, "--limit", "-l", help="Max documents to load"),
) -> None:
    """Interactive document browser with live filtering. Requires: pip install monopigi-sdk[fuzzy]

    Examples:
        monopigi browse ted
        monopigi browse --query "hospital" --limit 200
    """
    try:
        from monopigi_sdk.browse import browse_documents, check_textual

        check_textual()
    except ImportError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    try:
        with _get_client(cache=True) as client:
            if source:
                resp = client.documents(source, limit=limit)
                docs = [doc.model_dump() for doc in resp.documents]
            elif query:
                resp = client.search(query, limit=limit)
                docs = [doc.model_dump() for doc in resp.results]
            else:
                resp = client.search("", limit=limit)
                docs = [doc.model_dump() for doc in resp.results]
            browse_documents(docs, source=source)
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def pipe(
    limit: int = typer.Option(3, "--limit", "-l", help="Max results per query"),
) -> None:
    """Read queries from stdin, search each, output JSONL. Great for data enrichment.

    Examples:
        echo "hospital" | monopigi pipe
        cat company_names.txt | monopigi pipe --limit 5
        monopigi documents ted -f jsonl | jq -r '.title' | monopigi pipe
    """
    from monopigi_sdk.pipe import pipe_search

    try:
        with _get_client() as client:
            pipe_search(client, limit=limit)
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def completions() -> None:
    """Show how to install shell tab completions."""
    from monopigi_sdk.completions import get_completion_instructions

    console.print(get_completion_instructions())
