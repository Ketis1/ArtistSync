"""Shared fixtures for ArtistSync tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from artist_sync.spotify_client import SpotifyClient


@pytest.fixture
def mock_sp() -> MagicMock:
    """Return a mock spotipy.Spotify instance."""
    return MagicMock()


@pytest.fixture
def client(mock_sp: MagicMock) -> SpotifyClient:
    """Return a SpotifyClient wrapping the mock."""
    return SpotifyClient(mock_sp)
