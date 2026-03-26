"""Tests for sync_engine – track validation, deduplication, diff logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from artist_sync.models import SyncResult
from artist_sync.spotify_client import SpotifyClient
from artist_sync.playlist_manager import PlaylistManager
from artist_sync import sync_engine


# ======================================================================
# Helpers
# ======================================================================

def _make_artist(artist_id: str, name: str = "Artist") -> dict:
    return {"id": artist_id, "name": name}


def _make_track(track_id: str, artist_ids: list[str]) -> dict:
    return {
        "id": track_id,
        "artists": [{"id": aid} for aid in artist_ids],
    }


def _make_album(album_id: str) -> dict:
    return {"id": album_id, "name": f"Album {album_id}"}


# ======================================================================
# Track-artist validation
# ======================================================================

class TestTrackArtistValidation:
    """The sync engine must check artist_id ∈ track.artists for every track."""

    def test_track_with_matching_artist_is_included(self, client: SpotifyClient):
        """Track whose artists list contains our artist → included."""
        client.get_followed_artists = MagicMock(
            return_value=[_make_artist("a1", "Artist1")]
        )
        client.get_artist_albums = MagicMock(
            return_value=[_make_album("alb1")]
        )
        client.get_album_tracks = MagicMock(
            return_value=[_make_track("t1", ["a1", "a2"])]
        )

        pm = MagicMock(spec=PlaylistManager)
        pm.get_all_tracks_from_series.return_value = set()
        pm.add_tracks.return_value = []

        result = sync_engine.sync(
            client=client,
            playlist_manager=pm,
            playlist_name="Test",
        )

        assert result.tracks_found == 1

    def test_track_without_matching_artist_is_excluded(self, client: SpotifyClient):
        """Track whose artists list does NOT contain our artist → excluded."""
        client.get_followed_artists = MagicMock(
            return_value=[_make_artist("a1", "Artist1")]
        )
        client.get_artist_albums = MagicMock(
            return_value=[_make_album("alb1")]
        )
        # Track only has artist "a99" – NOT our followed artist "a1"
        client.get_album_tracks = MagicMock(
            return_value=[_make_track("t1", ["a99"])]
        )

        pm = MagicMock(spec=PlaylistManager)
        pm.get_all_tracks_from_series.return_value = set()
        pm.add_tracks.return_value = []

        result = sync_engine.sync(
            client=client,
            playlist_manager=pm,
            playlist_name="Test",
        )

        assert result.tracks_found == 0

    def test_compilation_album_only_includes_relevant_tracks(
        self, client: SpotifyClient,
    ):
        """A compilation album has many artists – only matching tracks pass."""
        client.get_followed_artists = MagicMock(
            return_value=[_make_artist("a1", "OurArtist")]
        )
        client.get_artist_albums = MagicMock(
            return_value=[_make_album("comp1")]
        )
        client.get_album_tracks = MagicMock(
            return_value=[
                _make_track("t1", ["a1"]),         # ✔ our artist
                _make_track("t2", ["a1", "a5"]),   # ✔ our artist (feat.)
                _make_track("t3", ["a5"]),          # ✖ not our artist
                _make_track("t4", ["a6", "a7"]),    # ✖ not our artist
            ],
        )

        pm = MagicMock(spec=PlaylistManager)
        pm.get_all_tracks_from_series.return_value = set()
        pm.add_tracks.return_value = []

        result = sync_engine.sync(
            client=client,
            playlist_manager=pm,
            playlist_name="Test",
        )

        assert result.tracks_found == 2  # t1 and t2


# ======================================================================
# Deduplication
# ======================================================================

class TestDeduplication:
    """Same track_id from different albums must produce one entry."""

    def test_same_track_across_albums(self, client: SpotifyClient):
        client.get_followed_artists = MagicMock(
            return_value=[_make_artist("a1")]
        )
        client.get_artist_albums = MagicMock(
            return_value=[_make_album("alb1"), _make_album("alb2")]
        )
        # Same track "t1" appears in both albums
        client.get_album_tracks = MagicMock(
            return_value=[_make_track("t1", ["a1"])]
        )

        pm = MagicMock(spec=PlaylistManager)
        pm.get_all_tracks_from_series.return_value = set()
        pm.add_tracks.return_value = []

        result = sync_engine.sync(
            client=client,
            playlist_manager=pm,
            playlist_name="Test",
        )

        assert result.tracks_found == 1  # deduplicated

    def test_same_track_across_artists(self, client: SpotifyClient):
        """Two followed artists on the same track → still one entry."""
        client.get_followed_artists = MagicMock(
            return_value=[_make_artist("a1"), _make_artist("a2")]
        )
        client.get_artist_albums = MagicMock(
            return_value=[_make_album("alb1")]
        )
        # Track has both a1 and a2
        client.get_album_tracks = MagicMock(
            return_value=[_make_track("t1", ["a1", "a2"])]
        )

        pm = MagicMock(spec=PlaylistManager)
        pm.get_all_tracks_from_series.return_value = set()
        pm.add_tracks.return_value = []

        result = sync_engine.sync(
            client=client,
            playlist_manager=pm,
            playlist_name="Test",
        )

        assert result.tracks_found == 1


# ======================================================================
# Diff calculation
# ======================================================================

class TestDiffCalculation:
    """Only tracks NOT already in the playlist should be added."""

    def test_new_tracks_only(self, client: SpotifyClient):
        client.get_followed_artists = MagicMock(
            return_value=[_make_artist("a1")]
        )
        client.get_artist_albums = MagicMock(
            return_value=[_make_album("alb1")]
        )
        client.get_album_tracks = MagicMock(
            return_value=[
                _make_track("t1", ["a1"]),
                _make_track("t2", ["a1"]),
                _make_track("t3", ["a1"]),
            ],
        )

        pm = MagicMock(spec=PlaylistManager)
        pm.get_all_tracks_from_series.return_value = {"t1"}  # already exists
        pm.add_tracks.return_value = ["Test"]

        result = sync_engine.sync(
            client=client,
            playlist_manager=pm,
            playlist_name="Test",
        )

        assert result.tracks_found == 3
        assert result.tracks_already_in_playlist == 1
        assert result.tracks_added == 2

        # Verify add_tracks was called with exactly {t2, t3}
        call_args = pm.add_tracks.call_args
        added_ids = call_args[0][1]  # second positional arg
        assert added_ids == {"t2", "t3"}

    def test_all_existing_means_zero_added(self, client: SpotifyClient):
        """When all tracks already exist, nothing is added."""
        client.get_followed_artists = MagicMock(
            return_value=[_make_artist("a1")]
        )
        client.get_artist_albums = MagicMock(
            return_value=[_make_album("alb1")]
        )
        client.get_album_tracks = MagicMock(
            return_value=[_make_track("t1", ["a1"])]
        )

        pm = MagicMock(spec=PlaylistManager)
        pm.get_all_tracks_from_series.return_value = {"t1"}
        pm.add_tracks.return_value = []

        result = sync_engine.sync(
            client=client,
            playlist_manager=pm,
            playlist_name="Test",
        )

        assert result.tracks_added == 0
        pm.add_tracks.assert_not_called()


# ======================================================================
# Dry run
# ======================================================================

class TestDryRun:
    def test_dry_run_does_not_add(self, client: SpotifyClient):
        client.get_followed_artists = MagicMock(
            return_value=[_make_artist("a1")]
        )
        client.get_artist_albums = MagicMock(
            return_value=[_make_album("alb1")]
        )
        client.get_album_tracks = MagicMock(
            return_value=[_make_track("t1", ["a1"])]
        )

        pm = MagicMock(spec=PlaylistManager)
        pm.get_all_tracks_from_series.return_value = set()

        result = sync_engine.sync(
            client=client,
            playlist_manager=pm,
            playlist_name="Test",
            dry_run=True,
        )

        assert result.tracks_found == 1
        assert result.tracks_added == 0
        pm.add_tracks.assert_not_called()
