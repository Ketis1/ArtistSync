"""Playlist series management (creation, splitting, track retrieval)."""

from __future__ import annotations

import logging
import re
from typing import Any

from artist_sync.config import MAX_TRACKS_PER_PLAYLIST
from artist_sync.spotify_client import SpotifyClient

logger = logging.getLogger(__name__)


def parse_playlist_input(url_or_id: str) -> str:
    """Extract a Spotify playlist ID from a URL or return the raw ID.

    Accepted formats:
    - ``https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M``
    - ``https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=...``
    - ``spotify:playlist:37i9dQZF1DXcBWIGoYBM5M``
    - ``37i9dQZF1DXcBWIGoYBM5M``  (raw ID)
    """
    # URL format
    m = re.search(r"playlist[/:]([A-Za-z0-9]+)", url_or_id)
    if m:
        return m.group(1)
    # Assume raw ID (or a plain name – handled upstream)
    return url_or_id.strip()


class PlaylistManager:
    """Manages a *series* of playlists: ``Name``, ``Name_2``, …"""

    def __init__(self, client: SpotifyClient) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Series discovery
    # ------------------------------------------------------------------

    def find_series_playlists(
        self, base_name: str,
    ) -> list[dict[str, Any]]:
        """Return all user playlists belonging to the series *base_name*.

        A playlist belongs to the series if its name equals ``base_name`` or
        matches the pattern ``base_name_N`` where *N* is an integer ≥ 2.
        Results are sorted by index.
        """
        pattern = re.compile(
            rf"^{re.escape(base_name)}(?:_(\d+))?$",
        )
        all_playlists = self._client.get_user_playlists()

        matched: list[tuple[int, dict[str, Any]]] = []
        for pl in all_playlists:
            m = pattern.match(pl["name"])
            if m:
                idx = int(m.group(1)) if m.group(1) else 1
                matched.append((idx, pl))

        matched.sort(key=lambda x: x[0])
        return [pl for _, pl in matched]

    # ------------------------------------------------------------------
    # Track collection from series
    # ------------------------------------------------------------------

    def get_all_tracks_from_series(self, base_name: str) -> set[str]:
        """Collect every track ID across all playlists in the series."""
        playlists = self.find_series_playlists(base_name)
        all_ids: set[str] = set()

        for pl in playlists:
            ids = self._client.get_playlist_track_ids(pl["id"])
            all_ids.update(ids)
            logger.info(
                "Playlist '%s': %d tracks",
                pl["name"],
                len(ids),
            )

        logger.info(
            "Total existing tracks in series '%s': %d",
            base_name,
            len(all_ids),
        )
        return all_ids

    # ------------------------------------------------------------------
    # Adding tracks (with series splitting)
    # ------------------------------------------------------------------

    def add_tracks(
        self,
        base_name: str,
        track_ids: set[str],
    ) -> list[str]:
        """Add *track_ids* to the playlist series, creating new playlists as needed.

        Returns the list of playlist names that were used/created.
        """
        if not track_ids:
            return []

        ids_to_add = list(track_ids)
        playlists = self.find_series_playlists(base_name)
        used_names: list[str] = []

        # Determine the current last playlist and its track count
        if playlists:
            last_pl = playlists[-1]
            last_count = self._get_playlist_track_count(last_pl["id"])
            next_index = len(playlists) + 1
        else:
            # No playlists exist yet – create the first one
            last_pl = self._client.create_playlist(base_name)
            last_count = 0
            next_index = 2

        cursor = 0

        while cursor < len(ids_to_add):
            space = MAX_TRACKS_PER_PLAYLIST - last_count
            if space <= 0:
                # Current playlist is full → create next one
                new_name = f"{base_name}_{next_index}"
                last_pl = self._client.create_playlist(new_name)
                last_count = 0
                next_index += 1
                space = MAX_TRACKS_PER_PLAYLIST

            batch = ids_to_add[cursor : (cursor + space)]
            self._client.add_tracks_to_playlist(last_pl["id"], batch)

            pl_name = last_pl["name"]
            if pl_name not in used_names:
                used_names.append(pl_name)
            logger.info(
                "Added %d tracks to '%s'",
                len(batch),
                pl_name,
            )

            last_count = int(last_count + len(batch))
            cursor += len(batch)

        return used_names

    def ensure_playlist_exists(self, base_name: str) -> dict[str, Any]:
        """Return the first playlist in the series, creating it if necessary."""
        playlists = self.find_series_playlists(base_name)
        if playlists:
            return playlists[0]
        return self._client.create_playlist(base_name)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_playlist_track_count(self, playlist_id: str) -> int:
        """Return the number of tracks currently in a playlist."""
        return len(self._client.get_playlist_track_ids(playlist_id))
