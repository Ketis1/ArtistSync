# ArtistSync - Spotify Discography Sync

ArtistSync is a command-line tool that automatically synchronizes the complete discography of all artists you follow on Spotify into a series of organized playlists. It scans albums, singles, compilations, and guest appearances, ensuring that every track your favorite artists participated in is collected in one place.

## Features

- **Automatic Artist Discovery**: Fetches all artists you follow on your Spotify account.
- **Complete Discography Scanning**: Scans for albums, singles, compilations, and guest appearances (`appears_on`).
- **Smart Playlist Management**:
  - Groups all artists into a single playlist series (e.g., "Full Collection").
  - Automatically splits into multiple playlists (`Name`, `Name_2`, `Name_3`...) when reaching the 10,000 track limit.
- **Precision Validation**: Checks artist association at the **track level** (ensures tracks from other artists on compilation albums are filtered out).
- **Intelligent Deduplication**: Prevents duplicate tracks using unique Spotify IDs across different releases.
- **Idempotent Sync**: Only adds tracks that are missing from your current playlist series.
- **Dry Run Mode**: Preview statistics without modifying your actual playlists.
- **Progress Tracking**: Real-time progress bar with detailed scanning status for each artist.

## Installation

### Prerequisites

- Python 3.12+
- Spotify Premium account (required for modifying playlists via the API).

### Setup

1. **Configure Spotify Credentials**
   - Create an application in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
   - Set the Redirect URI to: `http://127.0.0.1:8888/callback`.
   - Add your Spotify email to the **User Management** (Authorized Users) section of your app.
   - Copy `.env.example` to `.env` and fill in your `SPOTIPY_CLIENT_ID` and `SPOTIPY_CLIENT_SECRET`.

2. **Install the tool**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -e .
   ```

3. **Login**
   Run the login command to authenticate:
   ```bash
   artist-sync login
   ```
   - This will open a browser for authorization.
   - After success, a `.cache` file will be created.

## Usage

### Basic Sync

Synchronize all followed artists to a playlist named "ArtistSync":

```bash
artist-sync sync "ArtistSync"
```

### Sync with Options

```bash
artist-sync sync "Playlist Name" [OPTIONS]
```

**Available Options:**

- `--dry-run`: Preview statistics without making any changes.
- `--artists-limit <number>`: Process only the first N followed artists (useful for testing).
- `--exclude-compilations`: Skip albums categorized as compilations.
- `--exclude-appears-on`: Skip "appears_on" albums (featuring appearances on other artists' releases).
- `-v, --verbose`: Enable detailed debug logging.

**Examples:**

```bash
# Preview sync for first 3 artists
artist-sync sync "Test" --dry-run --artists-limit 3

# Full sync excluding compilations and featurings
artist-sync sync "Main Collection" --exclude-compilations --exclude-appears-on
```

## How It Works

1. **Discovery**: Fetches every artist you follow (cursor-based pagination).
2. **Scan**: For each artist, it fetches all associated albums from the requested groups.
3. **Track Validation**: For every track in every album, it verifies that the followed artist is actually listed in the track's artist metadata.
4. **Deduplication**: Filters the collected tracks to keep only unique track IDs.
5. **Diffing**: Fetches all existing tracks from your target playlist series (e.g., `Test`, `Test_2`...) and calculates which tracks are missing.
6. **Syncing**: Adds missing tracks in batches, creating and splitting into new playlists as soon as the 10,000 track limit is hit.

## Development

Run tests to verify logic:
```bash
pytest tests/ -v
```

## License
MIT