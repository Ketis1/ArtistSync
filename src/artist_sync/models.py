"""Data-transfer objects used across the application."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SyncResult:
    """Summary returned after a synchronization run."""

    artists_processed: int = 0
    albums_scanned: int = 0
    tracks_found: int = 0
    tracks_already_in_playlist: int = 0
    tracks_added: int = 0
    playlists_used: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
