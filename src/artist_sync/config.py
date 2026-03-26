"""Application configuration and constants."""

import os
import sys

from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_TRACKS_PER_PLAYLIST: int = 10_000
"""Spotify soft-limit – we split into a new playlist after this many tracks."""

BATCH_ADD_SIZE: int = 100
"""Maximum number of track URIs per playlist-add request (Spotify API limit)."""

ALBUMS_INCLUDE_GROUPS: list[str] = ["album", "single", "appears_on", "compilation"]
"""Default album groups to fetch for each artist."""

SPOTIFY_SCOPES: str = (
    "user-follow-read "
    "playlist-read-private "
    "playlist-modify-public "
    "playlist-modify-private"
)
"""OAuth scopes required by ArtistSync."""

REDIRECT_URI_DEFAULT: str = "http://localhost:8888/callback"


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def load_config() -> dict[str, str]:
    """Load and validate required environment variables.

    Returns a dict with keys: client_id, client_secret, redirect_uri.
    Exits with a helpful message when credentials are missing.
    """
    load_dotenv()

    client_id = os.getenv("SPOTIPY_CLIENT_ID", "")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET", "")
    redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI", REDIRECT_URI_DEFAULT)

    missing: list[str] = []
    if not client_id:
        missing.append("SPOTIPY_CLIENT_ID")
    if not client_secret:
        missing.append("SPOTIPY_CLIENT_SECRET")

    if missing:
        print(
            f"[ERROR] Missing environment variables: {', '.join(missing)}\n"
            "Create a .env file (see .env.example) or export them in your shell.",
            file=sys.stderr,
        )
        sys.exit(1)

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }
