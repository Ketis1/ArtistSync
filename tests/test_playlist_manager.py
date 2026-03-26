"""Tests for playlist_manager – URL parsing, series naming, track splitting."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from artist_sync.playlist_manager import PlaylistManager, parse_playlist_input
from artist_sync.spotify_client import SpotifyClient


# ======================================================================
# parse_playlist_input
# ======================================================================

class TestParsePlaylistInput:
    def test_full_url(self):
        url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        assert parse_playlist_input(url) == "37i9dQZF1DXcBWIGoYBM5M"

    def test_url_with_query_params(self):
        url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc123"
        assert parse_playlist_input(url) == "37i9dQZF1DXcBWIGoYBM5M"

    def test_spotify_uri(self):
        uri = "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"
        assert parse_playlist_input(uri) == "37i9dQZF1DXcBWIGoYBM5M"

    def test_raw_id(self):
        assert parse_playlist_input("37i9dQZF1DXcBWIGoYBM5M") == "37i9dQZF1DXcBWIGoYBM5M"

    def test_strips_whitespace(self):
        assert parse_playlist_input("  37i9dQ  ") == "37i9dQ"


# ======================================================================
# Series naming
# ======================================================================

class TestSeriesNaming:
    def _make_playlist(self, name: str, pid: str = "id1") -> dict:
        return {"id": pid, "name": name, "owner": {"id": "user1"}}

    def test_finds_base_playlist(self, client: SpotifyClient):
        client.get_user_playlists = MagicMock(
            return_value=[self._make_playlist("MyMusic", "p1")]
        )
        pm = PlaylistManager(client)
        result = pm.find_series_playlists("MyMusic")
        assert len(result) == 1
        assert result[0]["name"] == "MyMusic"

    def test_finds_numbered_playlists_in_order(self, client: SpotifyClient):
        client.get_user_playlists = MagicMock(
            return_value=[
                self._make_playlist("MyMusic_3", "p3"),
                self._make_playlist("MyMusic", "p1"),
                self._make_playlist("MyMusic_2", "p2"),
            ],
        )
        pm = PlaylistManager(client)
        result = pm.find_series_playlists("MyMusic")
        assert [p["name"] for p in result] == ["MyMusic", "MyMusic_2", "MyMusic_3"]

    def test_ignores_unrelated_playlists(self, client: SpotifyClient):
        client.get_user_playlists = MagicMock(
            return_value=[
                self._make_playlist("MyMusic", "p1"),
                self._make_playlist("OtherPlaylist", "p2"),
                self._make_playlist("MyMusic_2", "p3"),
                self._make_playlist("MyMusicExtra", "p4"),  # NOT in series
            ],
        )
        pm = PlaylistManager(client)
        result = pm.find_series_playlists("MyMusic")
        assert len(result) == 2  # only MyMusic and MyMusic_2

    def test_empty_series(self, client: SpotifyClient):
        client.get_user_playlists = MagicMock(return_value=[])
        pm = PlaylistManager(client)
        result = pm.find_series_playlists("MyMusic")
        assert result == []


# ======================================================================
# Track splitting
# ======================================================================

class TestTrackSplitting:
    def test_adds_to_existing_playlist(self, client: SpotifyClient):
        """Tracks fit in the existing playlist → no new playlist created."""
        client.get_user_playlists = MagicMock(
            return_value=[
                {"id": "p1", "name": "Test", "owner": {"id": "user1"}},
            ],
        )
        # Existing playlist has 5 tracks
        client.get_playlist_track_ids = MagicMock(return_value=set(range(5)))
        client.add_tracks_to_playlist = MagicMock()
        client.create_playlist = MagicMock()

        pm = PlaylistManager(client)
        used = pm.add_tracks("Test", {"t1", "t2", "t3"})

        assert "Test" in used
        client.create_playlist.assert_not_called()

    def test_creates_new_playlist_when_full(self, client: SpotifyClient):
        """When first playlist is full, a new one (_2) is created."""
        client.get_user_playlists = MagicMock(
            return_value=[
                {"id": "p1", "name": "Test", "owner": {"id": "user1"}},
            ],
        )
        # Existing playlist is at max capacity
        from artist_sync.config import MAX_TRACKS_PER_PLAYLIST
        client.get_playlist_track_ids = MagicMock(
            return_value=set(range(MAX_TRACKS_PER_PLAYLIST)),
        )
        client.add_tracks_to_playlist = MagicMock()
        new_pl = {"id": "p2", "name": "Test_2", "owner": {"id": "user1"}}
        client.create_playlist = MagicMock(return_value=new_pl)

        pm = PlaylistManager(client)
        used = pm.add_tracks("Test", {"t1", "t2"})

        client.create_playlist.assert_called_once_with("Test_2")
        assert "Test_2" in used

    def test_no_tracks_returns_empty(self, client: SpotifyClient):
        pm = PlaylistManager(client)
        used = pm.add_tracks("Test", set())
        assert used == []
