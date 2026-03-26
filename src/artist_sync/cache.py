"""Simple disk-based cache for Spotify metadata."""

import json
import logging
import os
from pathlib import Path
from typing import Any

from artist_sync.config import CACHE_FILE_NAME

logger = logging.getLogger(__name__)


class AlbumCache:
    """Cache of **album_id -> [track_ids]**.
    
    This avoids expensive :meth:`SpotifyClient.get_album_tracks` calls for 
    already-processed albums.
    """

    def __init__(self, file_path: str = CACHE_FILE_NAME) -> None:
        self.file_path = Path(file_path)
        self._data: dict[str, list[str]] = {}
        self.load()

    def load(self) -> None:
        """Load cache from disk if it exists."""
        if not self.file_path.exists():
            self._data = {}
            return

        try:
            with self.file_path.open("r", encoding="utf-8") as f:
                self._data = json.load(f)
            logger.debug("Loaded %d albums from cache", len(self._data))
        except Exception as exc:
            logger.warning("Failed to load cache (%s). Starting fresh.", exc)
            self._data = {}

    def save(self) -> None:
        """Persist current cache to disk."""
        try:
            with self.file_path.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            logger.debug("Saved %d albums to cache", len(self._data))
        except Exception as exc:
            logger.error("Failed to save cache: %s", exc)

    def get_tracks(self, album_id: str) -> list[str] | None:
        """Return track IDs for *album_id* from cache, or None if not found."""
        return self._data.get(album_id)

    def set_tracks(self, album_id: str, track_ids: list[str]) -> None:
        """Store track IDs for *album_id* in cache."""
        self._data[album_id] = track_ids
