"""High-level wrapper around the Spotify Web API (via *spotipy*).

Every public method handles pagination transparently and returns plain
Python structures (lists / dicts).  Rate-limit retries are handled by
spotipy itself (HTTP 429 → automatic back-off).
"""

from __future__ import annotations

import logging
from typing import Any

import spotipy

from artist_sync.config import BATCH_ADD_SIZE

logger = logging.getLogger(__name__)


class SpotifyClient:
    """Thin façade over :class:`spotipy.Spotify` with full pagination."""

    def __init__(self, sp: spotipy.Spotify) -> None:
        self._sp = sp
        # Cache current user id (needed for playlist creation)
        self._user_id: str | None = None

    # ------------------------------------------------------------------
    # User
    # ------------------------------------------------------------------

    @property
    def user_id(self) -> str:
        if self._user_id is None:
            me = self._sp.current_user()
            self._user_id = me["id"]
        assert self._user_id is not None
        return self._user_id

    def current_user_display_name(self) -> str:
        """Return display name of the authenticated user."""
        me = self._sp.current_user()
        return me.get("display_name") or me["id"]

    # ------------------------------------------------------------------
    # Followed artists  (cursor-based pagination)
    # ------------------------------------------------------------------

    def get_followed_artists(self) -> list[dict[str, Any]]:
        """Return **all** followed artists (id, name)."""
        artists: list[dict[str, Any]] = []
        after: str | None = None
        limit = 50  # API max

        while True:
            result = self._sp.current_user_followed_artists(
                limit=limit, after=after,
            )
            items = result["artists"]["items"]
            if not items:
                break
            artists.extend(items)
            after = items[-1]["id"]
            # When we got fewer than `limit` items, there are no more pages
            if len(items) < limit:
                break

        logger.info("Fetched %d followed artists", len(artists))
        return artists

    # ------------------------------------------------------------------
    # Artist albums  (offset pagination)
    # ------------------------------------------------------------------

    def get_artist_albums(
        self,
        artist_id: str,
        include_groups: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return all albums for *artist_id* matching *include_groups*."""
        groups = ",".join(include_groups) if include_groups else None
        albums: list[dict[str, Any]] = []
        offset = 0
        limit = 50

        while True:
            result = self._sp.artist_albums(
                artist_id,
                include_groups=groups,
                limit=limit,
                offset=offset,
            )
            items = result.get("items", [])
            if not items:
                break
            albums.extend(items)
            offset += int(len(items))
            if result.get("next") is None:
                break

        return albums

    # ------------------------------------------------------------------
    # Album tracks  (offset pagination)
    # ------------------------------------------------------------------

    def get_album_tracks(self, album_id: str) -> list[dict[str, Any]]:
        """Return all tracks for *album_id*."""
        tracks: list[dict[str, Any]] = []
        offset = 0
        limit = 50

        while True:
            result = self._sp.album_tracks(
                album_id, limit=limit, offset=offset,
            )
            items = result.get("items", [])
            if not items:
                break
            tracks.extend(items)
            offset += len(items)
            if result.get("next") is None:
                break

        return tracks

    # ------------------------------------------------------------------
    # Playlists
    # ------------------------------------------------------------------

    def get_user_playlists(self) -> list[dict[str, Any]]:
        """Return all playlists owned by the current user."""
        playlists: list[dict[str, Any]] = []
        offset = 0
        limit = 50

        while True:
            result = self._sp.current_user_playlists(limit=limit, offset=offset)
            items = result.get("items", [])
            if not items:
                break
            for p in items:
                if p["owner"]["id"] == self.user_id:
                    playlists.append(p)
            offset += len(items)
            if result.get("next") is None:
                break

        return playlists

    def get_playlist_track_ids(self, playlist_id: str) -> set[str]:
        """Return a set of all track IDs currently in *playlist_id*."""
        track_ids: set[str] = set()
        offset = 0
        limit = 100

        while True:
            result = self._sp.playlist_items(
                playlist_id,
                fields="items.track.id,next",
                additional_types=["track"],
                limit=limit,
                offset=offset,
            )
            items = result.get("items", [])
            if not items:
                break
            for item in items:
                track = item.get("track")
                if track and track.get("id"):
                    track_ids.add(track["id"])
            offset += len(items)
            if result.get("next") is None:
                break

        return track_ids

    def create_playlist(self, name: str, public: bool = False) -> dict[str, Any]:
        """Create a new playlist and return its metadata."""
        result = self._sp.user_playlist_create(
            self.user_id, name, public=public,
        )
        logger.info("Created playlist '%s' (id=%s)", name, result["id"])
        return result

    def add_tracks_to_playlist(
        self,
        playlist_id: str,
        track_ids: list[str],
    ) -> None:
        """Add tracks in batches of :data:`BATCH_ADD_SIZE`."""
        uris = [f"spotify:track:{tid}" for tid in track_ids]
        for i in range(0, len(uris), BATCH_ADD_SIZE):
            batch = uris[i : i + BATCH_ADD_SIZE]
            self._sp.playlist_add_items(playlist_id, batch)
            logger.debug(
                "Added batch of %d tracks to playlist %s",
                len(batch),
                playlist_id,
            )
