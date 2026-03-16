"""Monopigi CLI — query Greek government data from the command line."""

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

app = typer.Typer(name="monopigi", help="Query Greek government data from the command line.")
auth_app = typer.Typer(help="Manage API authentication.")
app.add_typer(auth_app, name="auth")

console = Console()


def _get_client() -> MonopigiClient:
    from monopigi_sdk.client import MonopigiClient

    cfg = load_config(config_path=DEFAULT_CONFIG_PATH)
    if not cfg.token:
        console.print("[red]No API token configured.[/red] Run: monopigi auth login <token>")
        raise typer.Exit(1)
    return MonopigiClient(token=cfg.token, base_url=cfg.base_url)


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
) -> None:
    """Search across all Greek government data sources."""
    try:
        with _get_client() as client:
            resp = client.search(query, limit=limit)
            if fmt == OutputFormat.JSON:
                console.print(json.dumps(resp.model_dump(), indent=2, ensure_ascii=False))
            elif fmt == OutputFormat.CSV:
                if resp.results:
                    writer = csv.DictWriter(sys.stdout, fieldnames=list(resp.results[0].model_dump().keys()))
                    writer.writeheader()
                    for doc in resp.results:
                        writer.writerow({k: str(v) if v is not None else "" for k, v in doc.model_dump().items()})
            else:
                table = Table(title=f'Search: "{query}" — {resp.total} results')
                table.add_column("Source", style="cyan")
                table.add_column("Title", max_width=60)
                table.add_column("Date")
                table.add_column("Score")
                for doc in resp.results:
                    table.add_row(
                        doc.source,
                        doc.title or "—",
                        doc.published_at or "—",
                        f"{doc.quality_score:.2f}" if doc.quality_score else "—",
                    )
                console.print(table)
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def documents(
    source: str = typer.Argument(..., help="Source name (e.g. ted, diavgeia)"),
    limit: int = typer.Option(10, "--limit", "-l"),
    since: str | None = typer.Option(None, "--since", help="ISO date, e.g. 2026-01-01"),
    fmt: OutputFormat = typer.Option(OutputFormat.TABLE, "--format", "-f", help="Output format"),  # noqa: B008
) -> None:
    """Query documents from a specific source."""
    try:
        with _get_client() as client:
            resp = client.documents(source, limit=limit, since=since)
            if fmt == OutputFormat.JSON:
                console.print(json.dumps(resp.model_dump(), indent=2, ensure_ascii=False))
            elif fmt == OutputFormat.CSV:
                if resp.documents:
                    writer = csv.DictWriter(sys.stdout, fieldnames=list(resp.documents[0].model_dump().keys()))
                    writer.writeheader()
                    for doc in resp.documents:
                        writer.writerow({k: str(v) if v is not None else "" for k, v in doc.model_dump().items()})
            else:
                table = Table(title=f"{source} — {resp.total} documents")
                table.add_column("ID", style="cyan", max_width=20)
                table.add_column("Title", max_width=50)
                table.add_column("Date")
                table.add_column("URL", style="dim", max_width=40)
                for doc in resp.documents:
                    table.add_row(doc.source_id, doc.title or "—", doc.published_at or "—", doc.source_url or "—")
                console.print(table)
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e


@app.command()
def stats() -> None:
    """Show platform-wide statistics."""
    try:
        with _get_client() as client:
            resp = client.stats()
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
            console.print(f"\n[bold]Tier:[/bold] {resp.tier}")
            console.print(f"[bold]Daily quota:[/bold] {resp.daily_quota}")
            console.print(f"[bold]Used today:[/bold] {resp.daily_used}")
            console.print(f"[bold]Remaining:[/bold] {resp.daily_remaining}")
            console.print(f"[bold]Resets at:[/bold] {resp.reset_at}\n")
    except MonopigiError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
