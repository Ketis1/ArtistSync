"""Core synchronization logic.

Orchestrates the full flow: fetch artists → fetch albums → fetch tracks →
validate artist↔track → deduplicate → diff with existing → add new.
"""

from __future__ import annotations

import logging

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from artist_sync.config import ALBUMS_INCLUDE_GROUPS
from artist_sync.models import SyncResult
from artist_sync.playlist_manager import PlaylistManager
from artist_sync.spotify_client import SpotifyClient

logger = logging.getLogger(__name__)


def _build_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    )


def sync(
    client: SpotifyClient,
    playlist_manager: PlaylistManager,
    playlist_name: str,
    *,
    dry_run: bool = False,
    include_groups: list[str] | None = None,
    artists_limit: int | None = None,
) -> SyncResult:
    """Run the full synchronization and return a :class:`SyncResult`.

    Parameters
    ----------
    client:
        Authenticated Spotify API client.
    playlist_manager:
        Playlist series manager.
    playlist_name:
        Base name for the target playlist series.
    dry_run:
        If ``True``, compute the diff but do **not** modify any playlists.
    include_groups:
        Album groups to fetch (default: all four groups).
    artists_limit:
        If set, only process the first *N* followed artists (useful for
        testing with large libraries).
    """
    groups = include_groups or ALBUMS_INCLUDE_GROUPS
    result = SyncResult()

    # ------------------------------------------------------------------
    # 1. Fetch followed artists
    # ------------------------------------------------------------------
    logger.info("Fetching followed artists …")
    artists = client.get_followed_artists()

    if artists_limit and artists_limit < len(artists):
        logger.info("Limiting to %d artists (of %d)", artists_limit, len(artists))
        artists = artists[:artists_limit]

    result.artists_processed = len(artists)

    # ------------------------------------------------------------------
    # 2. Collect tracks with artist↔track validation
    # ------------------------------------------------------------------
    all_track_ids: set[str] = set()

    with _build_progress() as progress:
        task = progress.add_task(
            "Scanning artists…",
            total=len(artists),
        )

        for artist in artists:
            artist_id: str = artist["id"]
            artist_name: str = artist.get("name", artist_id)

            progress.update(task, description=f"[bold blue]{artist_name}")

            try:
                albums = client.get_artist_albums(artist_id, groups)
            except Exception as exc:
                msg = f"Error fetching albums for {artist_name}: {exc}"
                logger.warning(msg)
                result.errors.append(msg)
                progress.advance(task)
                continue

            for album in albums:
                result.albums_scanned += 1
                album_id: str = album["id"]

                try:
                    tracks = client.get_album_tracks(album_id)
                except Exception as exc:
                    msg = f"Error fetching tracks for album {album_id}: {exc}"
                    logger.warning(msg)
                    result.errors.append(msg)
                    continue

                for track in tracks:
                    track_id = track.get("id")
                    if not track_id:
                        continue
                    # KEY REQUIREMENT: validate artist at track level
                    track_artist_ids = {a["id"] for a in track.get("artists", [])}
                    if artist_id in track_artist_ids:
                        all_track_ids.add(track_id)

            progress.advance(task)

    result.tracks_found = len(all_track_ids)
    logger.info("Unique tracks after validation & dedup: %d", len(all_track_ids))

    # ------------------------------------------------------------------
    # 3. Diff with existing playlist content
    # ------------------------------------------------------------------
    logger.info("Fetching existing tracks from playlist series '%s' …", playlist_name)
    existing_ids = playlist_manager.get_all_tracks_from_series(playlist_name)
    result.tracks_already_in_playlist = len(existing_ids)

    new_ids = all_track_ids - existing_ids
    logger.info("New tracks to add: %d", len(new_ids))

    # ------------------------------------------------------------------
    # 4. Add (unless dry-run)
    # ------------------------------------------------------------------
    if dry_run:
        logger.info("[DRY RUN] Would add %d tracks. No changes made.", len(new_ids))
        result.tracks_added = 0
    else:
        if new_ids:
            used = playlist_manager.add_tracks(playlist_name, new_ids)
            result.playlists_used = used
        result.tracks_added = len(new_ids)

    return result
