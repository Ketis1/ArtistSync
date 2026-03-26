"""Spotify OAuth 2.0 authentication."""

from __future__ import annotations

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from artist_sync.config import SPOTIFY_SCOPES, load_config


def get_authenticated_client() -> spotipy.Spotify:
    """Create and return an authenticated Spotify client.

    On first run the user will be redirected to a browser to authorize.
    The token is cached in ``.cache`` and auto-refreshed on subsequent calls.
    """
    cfg = load_config()

    auth_manager = SpotifyOAuth(
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        redirect_uri=cfg["redirect_uri"],
        scope=SPOTIFY_SCOPES,
        open_browser=True,
    )

    client = spotipy.Spotify(auth_manager=auth_manager)
    return client
