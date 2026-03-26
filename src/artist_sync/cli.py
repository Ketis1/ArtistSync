"""Command-line interface for ArtistSync."""

from __future__ import annotations

import logging
import sys

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from artist_sync.auth import get_authenticated_client
from artist_sync.config import ALBUMS_INCLUDE_GROUPS
from artist_sync.playlist_manager import PlaylistManager
from artist_sync.spotify_client import SpotifyClient
from artist_sync import sync_engine

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console)],
    )


# ======================================================================
# Main group
# ======================================================================

@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """ArtistSync – sync all tracks from your followed Spotify artists."""
    _setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


# ======================================================================
# login
# ======================================================================

@main.command()
def login() -> None:
    """Authenticate with Spotify and verify the connection."""
    console.print("[bold]Authenticating with Spotify …[/bold]")
    try:
        sp = get_authenticated_client()
        client = SpotifyClient(sp)
        name = client.current_user_display_name()
        console.print(f"[green]✔ Logged in as:[/green] [bold]{name}[/bold]")
    except Exception as exc:
        console.print(f"[red]✖ Authentication failed:[/red] {exc}")
        sys.exit(1)


# ======================================================================
# sync
# ======================================================================

@main.command()
@click.argument("playlist")
@click.option("--dry-run", is_flag=True, help="Show what would be added without modifying playlists.")
@click.option(
    "--include-groups",
    default=None,
    help=(
        "Comma-separated album groups to fetch. "
        f"Default: {','.join(ALBUMS_INCLUDE_GROUPS)}"
    ),
)
@click.option(
    "--exclude-compilations",
    is_flag=True,
    help="Exclude compilation albums.",
)
@click.option(
    "--exclude-appears-on",
    is_flag=True,
    help="Exclude 'appears_on' albums (featurings on other artists' releases).",
)
@click.option(
    "--artists-limit",
    type=int,
    default=None,
    help="Limit the number of artists to process (useful for testing).",
)
def sync(
    playlist: str,
    dry_run: bool,
    include_groups: str | None,
    exclude_compilations: bool,
    exclude_appears_on: bool,
    artists_limit: int | None,
) -> None:
    """Synchronize followed artists' tracks into PLAYLIST.

    PLAYLIST can be a Spotify playlist URL, a playlist ID, or a name for a
    new playlist to create.
    """
    # Resolve include_groups
    if include_groups:
        groups = [g.strip() for g in include_groups.split(",")]
    else:
        groups = list(ALBUMS_INCLUDE_GROUPS)

    if exclude_compilations and "compilation" in groups:
        groups.remove("compilation")
    if exclude_appears_on and "appears_on" in groups:
        groups.remove("appears_on")

    console.print(f"[bold]Album groups:[/bold] {', '.join(groups)}")
    if dry_run:
        console.print("[yellow]⚠ DRY RUN – no playlists will be modified[/yellow]")

    # Authenticate
    sp = get_authenticated_client()
    client = SpotifyClient(sp)
    pm = PlaylistManager(client)

    console.print(
        f"[bold]Logged in as:[/bold] {client.current_user_display_name()}"
    )

    # Run sync
    result = sync_engine.sync(
        client=client,
        playlist_manager=pm,
        playlist_name=playlist,
        dry_run=dry_run,
        include_groups=groups,
        artists_limit=artists_limit,
    )

    # Print summary table
    _print_result(result, dry_run)

    if result.errors:
        console.print(f"\n[yellow]⚠ {len(result.errors)} error(s) occurred:[/yellow]")
        for err in result.errors[:10]:
            console.print(f"  • {err}")
        if len(result.errors) > 10:
            console.print(f"  … and {len(result.errors) - 10} more")


def _print_result(result, dry_run: bool) -> None:
    table = Table(title="Sync Summary", show_header=False, border_style="bright_blue")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Artists processed", str(result.artists_processed))
    table.add_row("Albums scanned", str(result.albums_scanned))
    table.add_row("Unique tracks found", str(result.tracks_found))
    table.add_row("Already in playlists", str(result.tracks_already_in_playlist))

    label = "Tracks to add" if dry_run else "Tracks added"
    style = "green" if result.tracks_added > 0 else "dim"
    table.add_row(label, f"[{style}]{result.tracks_added}[/{style}]")

    if result.playlists_used:
        table.add_row("Playlists used", ", ".join(result.playlists_used))

    console.print()
    console.print(table)
