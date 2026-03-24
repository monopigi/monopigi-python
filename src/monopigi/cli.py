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

from monopigi.config import DEFAULT_CONFIG_PATH, load_config, save_config
from monopigi.exceptions import MonopigiError
from monopigi.models import OutputFormat, SourceStatus

if TYPE_CHECKING:
    from monopigi.client import MonopigiClient
    from monopigi.models import Document

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

# Client-side overrides for source metadata (until API redeploys)
SOURCE_OVERRIDES = {
    "e_procurement": {"description": "Greek public procurement portal (1M+ contracts/year)"},
}


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
    from monopigi.client import MonopigiClient

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
def auth_login(
    ctx: typer.Context,
    token: str | None = typer.Argument(None, help="Your Monopigi API token (mp_live_...)"),
) -> None:
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
                    data = s.model_dump()
                    overrides = SOURCE_OVERRIDES.get(s.name, {})
                    data.update(overrides)
                    print(json.dumps(data, ensure_ascii=False))
            else:
                table = Table(title="Monopigi Data Sources")
                table.add_column("Name", style="cyan")
                table.add_column("Label")
                table.add_column("Status")
                table.add_column("Description", style="dim")
                for s in result:
                    overrides = SOURCE_OVERRIDES.get(s.name, {})
                    desc = overrides.get("description", s.description)
                    status_style = "green" if s.status == SourceStatus.ACTIVE else "yellow"
                    table.add_row(s.name, s.label, f"[{status_style}]{s.status}[/{status_style}]", desc)
                console.print(table)
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def models(
    fmt: OutputFormat = typer.Option(OutputFormat.TABLE, "--format", "-f", help="Output format"),  # noqa: B008
) -> None:
    """List available LLM models for the /v1/ask endpoint.

    No authentication required.

    Examples:
        monopigi models
        monopigi models --format json
    """
    import httpx

    from monopigi.config import DEFAULT_BASE_URL, load_config

    cfg = load_config(config_path=DEFAULT_CONFIG_PATH)
    base_url = cfg.base_url or DEFAULT_BASE_URL
    try:
        resp = httpx.get(f"{base_url}/v1/models", timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e

    fmt = _resolve_format(fmt)
    model_list = data.get("models", [])

    if fmt in (OutputFormat.JSON, OutputFormat.JSONL):
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif fmt == OutputFormat.CSV:
        writer = csv.DictWriter(sys.stdout, fieldnames=["id", "default"])
        writer.writeheader()
        for m in model_list:
            writer.writerow({"id": m.get("id", ""), "default": m.get("default", False)})
    else:
        table = Table(title="Available LLM Models")
        table.add_column("Model ID", style="cyan")
        table.add_column("Default", justify="center")
        for m in model_list:
            is_default = "[green]yes[/green]" if m.get("default") else ""
            table.add_row(m.get("id", ""), is_default)
        console.print(table)


@app.command()
def search(
    ctx: typer.Context,
    query: str | None = typer.Argument(None, help="Search query"),
    source: str | None = typer.Option(None, "--source", "-s", help="Filter by source (e.g. ted, diavgeia, kimdis)"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max results"),
    fmt: OutputFormat = typer.Option(OutputFormat.TABLE, "--format", "-f", help="Output format"),  # noqa: B008
    fields: str | None = typer.Option(None, "--fields", help="Comma-separated fields to include"),
    cache: bool = typer.Option(False, "--cache", help="Cache results locally (5 min TTL)"),
    count: bool = typer.Option(False, "--count", help="Just print the total count"),
) -> None:
    """Search across all Greek government data sources.

    Pipe-friendly: auto-outputs JSONL when piped. Use with jq, grep, wc.

    Examples:
        monopigi search "hospital"
        monopigi search "δημόσιο νοσοκομείο"
        monopigi search "IT services" --source ted
        monopigi search "procurement" --format jsonl | jq '.title'
        monopigi search "Athens" --count
        monopigi search "hospital" --fields source,title --format csv
    """
    query = _require_arg(ctx, query)
    resolved_source = _resolve_source(source) if source else None
    try:
        with _get_client(cache=cache) as client:
            resp = client.search(query, source=resolved_source, limit=limit)
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
def config_set(
    ctx: typer.Context,
    key: str | None = typer.Argument(None),
    value: str | None = typer.Argument(None),
) -> None:
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
    """Show all config values and file locations."""
    config_file = DEFAULT_CONFIG_PATH.parent / "settings.json"
    auth_cfg = load_config(config_path=DEFAULT_CONFIG_PATH)
    console.print(f"\n[dim]Config file:[/dim] {DEFAULT_CONFIG_PATH}")
    console.print(
        f"[bold]token:[/bold] {auth_cfg.token[:16]}..." if auth_cfg.token else "[bold]token:[/bold] [dim]not set[/dim]"
    )
    console.print(f"[bold]base_url:[/bold] {auth_cfg.base_url}")
    if config_file.exists():
        console.print(f"\n[dim]Settings file:[/dim] {config_file}")
        settings = json.loads(config_file.read_text())
        for k, v in settings.items():
            console.print(f"[bold]{k}:[/bold] {v}")
    console.print()


@config_app.command("edit")
def config_edit() -> None:
    """Open config file in $EDITOR."""
    import os
    import subprocess

    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vi"))
    if not DEFAULT_CONFIG_PATH.exists():
        DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_CONFIG_PATH.write_text('token = ""\nbase_url = "https://api.monopigi.com"\n')
    subprocess.run([editor, str(DEFAULT_CONFIG_PATH)], check=False)


@app.command()
def browse(
    source: str = typer.Argument("", help="Source name (optional — searches all if empty)"),
    query: str = typer.Option("", "--query", "-q", help="Pre-filter query"),
    limit: int = typer.Option(100, "--limit", "-l", help="Max documents to load"),
) -> None:
    """Interactive document browser with live filtering.

    Examples:
        monopigi browse ted
        monopigi browse --query "hospital" --limit 200
    """
    from monopigi.browse import browse_documents

    try:
        with _get_client(cache=True) as client:
            if query:
                resp = client.search(query, source=_resolve_source(source) if source else None, limit=limit)
                docs = [doc.model_dump() for doc in resp.results]
            elif source:
                resp = client.documents(_resolve_source(source), limit=limit)
                docs = [doc.model_dump() for doc in resp.documents]
            else:
                docs = []

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
    from monopigi.pipe import pipe_search

    try:
        with _get_client() as client:
            pipe_search(client, limit=limit)
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def completions() -> None:
    """Show how to install shell tab completions."""
    from monopigi.completions import get_completion_instructions

    console.print(get_completion_instructions())


# -- Enterprise Commands -------------------------------------------------------


@app.command()
def ask(
    question: str = typer.Argument(..., help="Natural language question about Greek government data"),
    limit: int = typer.Option(5, "--limit", "-l", help="Number of source documents to retrieve"),
    model: str = typer.Option("", "--model", "-m", help="LLM model override (e.g. anthropic/claude-sonnet-4-20250514)"),
) -> None:
    """Ask a question about Greek government data (RAG). Enterprise only.

    Examples:
    monopigi ask "What are the largest public contracts in 2025?"
    monopigi ask "How much did the government spend on IT consulting?" --limit 10
    monopigi ask "energy permits in Crete" --model mistral/mistral-large-latest
    """
    try:
        with _get_client() as client:
            result = client.ask(question, limit=limit, model=model or None)
            if _is_pipe():
                print(json.dumps(result, ensure_ascii=False))
            else:
                console.print(f"\n[bold]Question:[/bold] {result.get('question', '')}\n")
                console.print(f"[bold]Answer:[/bold]\n{result.get('answer', 'No answer available.')}\n")
                sources = result.get("sources", [])
                if sources:
                    console.print(f"[dim]Sources ({len(sources)}):[/dim]")
                    for s in sources:
                        src = s.get("source", "")
                        title = s.get("title", "Untitled")
                        sid = s.get("source_id", "")
                        console.print(f"  [{src}] {title} ({sid})")
                if result.get("model"):
                    console.print(f"\n[dim]Model: {result['model']}[/dim]")
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def entity(
    identifier: str = typer.Argument(..., help="Entity identifier (AFM, name, or ADA code)"),
    type: str = typer.Option("afm", "--type", "-t", help="Identifier type: afm, name, or ada"),
    fmt: OutputFormat = typer.Option(OutputFormat.TABLE, "--format", "-f"),  # noqa: B008
) -> None:
    """Look up an entity across all government data sources. Enterprise only.

    Examples:
    monopigi entity 099369820 --type afm
    monopigi entity "ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ" --type name
    monopigi entity ABC946X --type ada
    """
    try:
        with _get_client() as client:
            result = client.entity(identifier, identifier_type=type)
            if _is_pipe() or fmt != OutputFormat.TABLE:
                print(json.dumps(result, ensure_ascii=False, default=str))
            else:
                matches = result.get("matches", [])
                console.print(f"\n[bold]{result.get('identifier_type', 'entity')}:[/bold] {identifier}")
                console.print(f"[bold]Matches:[/bold] {result.get('total', 0)}\n")
                if matches:
                    for m in matches[:20]:
                        title = m.get("title") or "Untitled"
                        console.print(f"  [{m.get('source', '')}] {title}")
                        console.print(f"    [dim]{m.get('source_id', '')} | {m.get('published_at', '—')}[/dim]")
                elif result.get("error"):
                    console.print(f"[red]{result['error']}[/red]")
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def similar(
    source_id: str = typer.Argument(..., help="Source ID of the document to find similar documents for"),
    limit: int = typer.Option(10, "--limit", "-l"),
    fmt: OutputFormat = typer.Option(OutputFormat.TABLE, "--format", "-f"),  # noqa: B008
) -> None:
    """Find documents similar to a given document. Enterprise only.

    Examples:
    monopigi similar "rae:rae_status:V_SDI_R_ANEMO:123"
    monopigi similar "contract:26SYMV018689966" --limit 5
    """
    try:
        with _get_client() as client:
            result = client.similar(source_id, limit=limit)
            docs = result.get("similar", [])
            if _is_pipe() or fmt != OutputFormat.TABLE:
                print(json.dumps(result, ensure_ascii=False, default=str))
            else:
                console.print(f"\n[bold]Similar to:[/bold] {source_id}")
                console.print(f"[bold]Found:[/bold] {len(docs)}\n")
                for d in docs:
                    title = d.get("title") or "Untitled"
                    console.print(f"  [{d.get('source', '')}] {title}")
                    console.print(f"    [dim]{d.get('source_id', '')}[/dim]")
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def content(
    source_id: str = typer.Argument(..., help="Document source ID to download"),
    output: str = typer.Option("", "--output", "-o", help="Output file path (default: print to stdout)"),
) -> None:
    """Download original document content (PDF, XML, JSON). Enterprise only.

    Examples:
    monopigi content "ABC946X" --output decision.pdf
    monopigi content "ted:12345" --output notice.xml
    """
    try:
        with _get_client() as client:
            data = client.content(source_id)
            if output:
                from pathlib import Path

                Path(output).write_bytes(data)
                console.print(f"[green]Saved {len(data)} bytes to {output}[/green]")
            else:
                import sys

                sys.stdout.buffer.write(data)
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


# -- Report Commands -----------------------------------------------------------

report_app = typer.Typer(help="Manage due diligence reports. Pro tier and above.", no_args_is_help=True)
app.add_typer(report_app, name="report")


@report_app.command("create")
def report_create(
    identifier: str = typer.Argument(..., help="Entity identifier (AFM, name, or ADA)"),
    type: str = typer.Option("afm", "--type", "-t", help="Identifier type: afm, name, ada"),
) -> None:
    """Create a new due diligence report."""
    try:
        with _get_client() as client:
            result = client.create_report(identifier, identifier_type=type)
            if _is_pipe():
                print(json.dumps(result, ensure_ascii=False))
            else:
                console.print(f"[green]Report created:[/green] {result.get('id', '')}")
                console.print(f"  Status: {result.get('status', '')}")
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@report_app.command("list")
def report_list(
    limit: int = typer.Option(20, "--limit", "-l"),
) -> None:
    """List your reports."""
    try:
        with _get_client() as client:
            result = client.list_reports(limit=limit)
            if _is_pipe():
                print(json.dumps(result, ensure_ascii=False))
            else:
                items = result.get("items", [])
                if not items:
                    console.print("[dim]No reports found.[/dim]")
                    return
                table = Table(title=f"Reports ({result.get('total', 0)} total)")
                table.add_column("ID", style="cyan", max_width=36)
                table.add_column("Entity")
                table.add_column("Type")
                table.add_column("Status")
                table.add_column("Created")
                for r in items:
                    table.add_row(r["id"], r["entity_identifier"], r["identifier_type"], r["status"], r["created_at"])
                console.print(table)
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@report_app.command("get")
def report_get(
    report_id: str = typer.Argument(..., help="Report ID"),
) -> None:
    """Get a report by ID."""
    try:
        with _get_client() as client:
            result = client.get_report(report_id)
            print(json.dumps(result, indent=2, ensure_ascii=False))
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@report_app.command("pdf")
def report_pdf(
    report_id: str = typer.Argument(..., help="Report ID"),
    output: str = typer.Option("", "--output", "-o", help="Output file path"),
) -> None:
    """Download a report as PDF."""
    try:
        with _get_client() as client:
            data = client.get_report_pdf(report_id)
            path = output or f"report-{report_id}.pdf"
            from pathlib import Path

            Path(path).write_bytes(data)
            console.print(f"[green]Saved to {path}[/green]")
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


# -- Alert Commands ------------------------------------------------------------

alert_app = typer.Typer(help="Manage procurement alerts. Enterprise only.", no_args_is_help=True)
app.add_typer(alert_app, name="alert")


@alert_app.command("create")
def alert_create(
    name: str = typer.Argument(..., help="Alert profile name"),
    query: str = typer.Option("", "--query", "-q", help="Search query filter"),
    source: str = typer.Option("", "--source", "-s", help="Source filter"),
    email: str = typer.Option("", "--email", help="Notification email"),
    webhook: str = typer.Option("", "--webhook", help="Webhook URL"),
) -> None:
    """Create an alert profile."""
    try:
        filters: dict = {}
        if query:
            filters["query"] = query
        if source:
            filters["source"] = source
        kwargs: dict = {}
        if email:
            kwargs["notify_email"] = email
        if webhook:
            kwargs["webhook_url"] = webhook
        with _get_client() as client:
            result = client.create_alert_profile(name, filters, **kwargs)
            if _is_pipe():
                print(json.dumps(result, ensure_ascii=False))
            else:
                console.print(f"[green]Alert profile created:[/green] {result.get('id', '')}")
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@alert_app.command("list")
def alert_list(
    limit: int = typer.Option(20, "--limit", "-l"),
) -> None:
    """List alert profiles."""
    try:
        with _get_client() as client:
            result = client.list_alert_profiles(limit=limit)
            if _is_pipe():
                print(json.dumps(result, ensure_ascii=False))
            else:
                items = result.get("items", [])
                if not items:
                    console.print("[dim]No alert profiles found.[/dim]")
                    return
                table = Table(title=f"Alert Profiles ({result.get('total', 0)} total)")
                table.add_column("ID", style="cyan", max_width=36)
                table.add_column("Name")
                table.add_column("Active")
                table.add_column("Created")
                for a in items:
                    active = "[green]yes[/green]" if a.get("is_active") else "[red]no[/red]"
                    table.add_row(a["id"], a["name"], active, a.get("created_at", ""))
                console.print(table)
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@alert_app.command("delete")
def alert_delete(
    profile_id: str = typer.Argument(..., help="Alert profile ID"),
) -> None:
    """Delete an alert profile."""
    try:
        with _get_client() as client:
            result = client.delete_alert_profile(profile_id)
            console.print(f"[green]Deleted:[/green] {result.get('status', 'ok')}")
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@alert_app.command("deliveries")
def alert_deliveries(
    profile_id: str = typer.Option("", "--profile", "-p", help="Filter by profile ID"),
    limit: int = typer.Option(20, "--limit", "-l"),
) -> None:
    """List alert deliveries."""
    try:
        with _get_client() as client:
            result = client.list_alert_deliveries(profile_id=profile_id or None, limit=limit)
            if _is_pipe():
                print(json.dumps(result, ensure_ascii=False))
            else:
                items = result.get("items", [])
                if not items:
                    console.print("[dim]No deliveries found.[/dim]")
                    return
                table = Table(title=f"Alert Deliveries ({result.get('total', 0)} total)")
                table.add_column("ID", style="cyan", max_width=36)
                table.add_column("Channel")
                table.add_column("Status")
                table.add_column("Delivered")
                for d in items:
                    table.add_row(
                        d["id"], d.get("channel", ""), d.get("delivery_status", ""), d.get("delivered_at", "")
                    )
                console.print(table)
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


# -- Monitor Commands ----------------------------------------------------------

monitor_app = typer.Typer(help="Compliance monitoring — track entities. Enterprise only.", no_args_is_help=True)
app.add_typer(monitor_app, name="monitor")


@monitor_app.command("add")
def monitor_add(
    identifier: str = typer.Argument(..., help="Entity identifier (AFM, name, or ADA code)"),
    type: str = typer.Option("afm", "--type", "-t", help="Identifier type: afm, name, ada"),
    label: str = typer.Option("", "--label", "-l", help="Human-readable label"),
) -> None:
    """Add an entity to monitor.

    Examples:
        monopigi monitor add 099369820 --type afm --label "ACME Corp"
        monopigi monitor add "ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ" --type name
    """
    try:
        with _get_client() as client:
            result = client.add_monitored_entity(identifier, identifier_type=type, label=label or None)
            if _is_pipe():
                print(json.dumps(result, ensure_ascii=False))
            else:
                console.print(f"[green]Monitoring:[/green] {result.get('entity_identifier', '')}")
                console.print(f"  ID: {result.get('id', '')}")
                if result.get("label"):
                    console.print(f"  Label: {result['label']}")
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@monitor_app.command("list")
def monitor_list(
    limit: int = typer.Option(20, "--limit", "-l"),
) -> None:
    """List monitored entities."""
    try:
        with _get_client() as client:
            result = client.list_monitored_entities(limit=limit)
            if _is_pipe():
                print(json.dumps(result, ensure_ascii=False))
            else:
                items = result.get("items", [])
                if not items:
                    console.print("[dim]No monitored entities.[/dim]")
                    return
                table = Table(title=f"Monitored Entities ({result.get('total', 0)} total)")
                table.add_column("ID", style="cyan", max_width=36)
                table.add_column("Identifier")
                table.add_column("Type")
                table.add_column("Label")
                table.add_column("Last Checked")
                for e in items:
                    table.add_row(
                        e["id"],
                        e["entity_identifier"],
                        e["identifier_type"],
                        e.get("label") or "",
                        e.get("last_checked_at") or "never",
                    )
                console.print(table)
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@monitor_app.command("remove")
def monitor_remove(
    entity_id: str = typer.Argument(..., help="Monitored entity ID"),
) -> None:
    """Remove a monitored entity."""
    try:
        with _get_client() as client:
            result = client.remove_monitored_entity(entity_id)
            console.print(f"[green]Removed:[/green] {result.get('status', 'deactivated')}")
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@monitor_app.command("events")
def monitor_events(
    entity_id: str = typer.Option("", "--entity-id", "-e", help="Filter by entity ID"),
    type: str = typer.Option("", "--type", "-t", help="Filter by event type"),
    limit: int = typer.Option(20, "--limit", "-l"),
) -> None:
    """List monitoring events.

    Examples:
        monopigi monitor events
        monopigi monitor events --entity-id abc123 --type new_decision
    """
    try:
        with _get_client() as client:
            result = client.list_entity_events(
                entity_id=entity_id or None,
                event_type=type or None,
                limit=limit,
            )
            if _is_pipe():
                print(json.dumps(result, ensure_ascii=False))
            else:
                items = result.get("items", [])
                if not items:
                    console.print("[dim]No events found.[/dim]")
                    return
                table = Table(title=f"Entity Events ({result.get('total', 0)} total)")
                table.add_column("ID", style="cyan", max_width=36)
                table.add_column("Type")
                table.add_column("Document")
                table.add_column("Summary", max_width=50)
                table.add_column("Detected")
                table.add_column("Ack")
                for ev in items:
                    ack = "[green]yes[/green]" if ev.get("acknowledged_at") else ""
                    table.add_row(
                        ev["id"],
                        ev["event_type"],
                        ev.get("document_source_id", ""),
                        ev.get("summary") or "",
                        ev.get("detected_at", ""),
                        ack,
                    )
                console.print(table)
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@monitor_app.command("report")
def monitor_report(
    entity_id: str = typer.Argument(..., help="Monitored entity ID"),
) -> None:
    """Trigger a health report for a monitored entity.

    Examples:
        monopigi monitor report abc123-def456
    """
    try:
        with _get_client() as client:
            result = client.entity_health_report(entity_id)
            if _is_pipe():
                print(json.dumps(result, ensure_ascii=False))
            else:
                console.print(f"[green]Report requested:[/green] {result.get('report_id', '')}")
                console.print(f"  Entity: {result.get('entity_identifier', '')}")
                console.print(f"  Status: {result.get('status', '')}")
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
