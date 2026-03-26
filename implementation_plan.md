# ArtistSync — Plan implementacji

Aplikacja CLI w Pythonie integrująca się z Spotify API. Synchronizuje **pełną dyskografię** obserwowanych artystów (albumy, single, featuringi, kompilacje) do wskazanych playlist, z walidacją powiązania artysta↔utwór na poziomie tracka.

## User Review Required

> [!IMPORTANT]
> **Wybór technologii:** Projekt oparty na Pythonie 3.12+ z biblioteką `spotipy` (oficjalny wrapper Spotify API). Alternatywą jest ręczny klient HTTP — `spotipy` znacząco upraszcza OAuth i paginację. Czy akceptujesz `spotipy`?

> [!IMPORTANT]
> **Manager pakietów:** Plan zakłada użycie `uv` jako narzędzia do zarządzania projektem i zależnościami. Jeśli wolisz `pip`/`poetry`, daj znać.

> [!WARNING]
> **Spotify API rate limit:** API Spotify ma limit ~180 req/30s. Przy setkach artystów synchronizacja może trwać kilka-kilkanaście minut. System implementuje retry z exponential backoff.

---

## Proposed Changes

### Struktura projektu

```
ArtistSync/
├── pyproject.toml
├── README.md
├── .env.example
├── src/
│   └── artist_sync/
│       ├── __init__.py
│       ├── __main__.py          # entry point
│       ├── cli.py               # CLI (click)
│       ├── config.py            # ustawienia, env vars
│       ├── auth.py              # OAuth 2.0 flow
│       ├── spotify_client.py    # wrapper API Spotify
│       ├── sync_engine.py       # główna logika synchronizacji
│       ├── playlist_manager.py  # zarządzanie playlistami (tworzenie, podział)
│       └── models.py            # dataclasses / DTO
├── tests/
│   ├── __init__.py
│   ├── test_sync_engine.py
│   ├── test_playlist_manager.py
│   └── conftest.py
└── .gitignore
```

---

### Konfiguracja projektu

#### [NEW] [pyproject.toml](file:///f:/ANTIGRAVITY/repos/spotify%20mega%20sync/ArtistSync/pyproject.toml)

Konfiguracja projektu z zależnościami:
- **Runtime:** `spotipy`, `click`, `python-dotenv`, `rich` (logowanie/progress)
- **Dev:** `pytest`, `pytest-mock`
- Python ≥ 3.12, entry point: `artist-sync` → `artist_sync.cli:main`

#### [NEW] [.env.example](file:///f:/ANTIGRAVITY/repos/spotify%20mega%20sync/ArtistSync/.env.example)

Szablon zmiennych środowiskowych:
```
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIPY_REDIRECT_URI=http://localhost:8888/callback
```

---

### Moduł autoryzacji

#### [NEW] [auth.py](file:///f:/ANTIGRAVITY/repos/spotify%20mega%20sync/ArtistSync/src/artist_sync/auth.py)

- Autoryzacja OAuth 2.0 via `spotipy.SpotifyOAuth`
- Scope: `user-follow-read`, `playlist-read-private`, `playlist-modify-public`, `playlist-modify-private`
- Cache tokenu w `.cache` (domyślne zachowanie spotipy)
- Funkcja `get_authenticated_client() → spotipy.Spotify`

---

### Klient API Spotify

#### [NEW] [spotify_client.py](file:///f:/ANTIGRAVITY/repos/spotify%20mega%20sync/ArtistSync/src/artist_sync/spotify_client.py)

Wrapper wokół `spotipy.Spotify` z logiką biznesową:

| Metoda | Opis | Endpoint |
|--------|------|----------|
| `get_followed_artists()` | Pobiera wszystkich obserwowanych artystów (paginacja cursor-based) | `/me/following` |
| `get_artist_albums(artist_id)` | Albumy artysty ze wszystkich grup: `album,single,appears_on,compilation` | `/artists/{id}/albums` |
| `get_album_tracks(album_id)` | Wszystkie utwory z albumu | `/albums/{id}/tracks` |
| `get_playlist_tracks(playlist_id)` | Wszystkie utwory z playlisty | `/playlists/{id}/tracks` |
| `add_tracks_to_playlist(playlist_id, track_uris)` | Batch add (max 100/request) | `/playlists/{id}/tracks` |
| `create_playlist(name)` | Tworzy nową playlistę | `/users/{id}/playlists` |
| `get_user_playlists()` | Listy użytkownika | `/me/playlists` |

Wszystkie metody obsługują paginację. Retry z exponential backoff przy HTTP 429.

---

### Logika synchronizacji

#### [NEW] [sync_engine.py](file:///f:/ANTIGRAVITY/repos/spotify%20mega%20sync/ArtistSync/src/artist_sync/sync_engine.py)

Główny algorytm synchronizacji:

```python
def sync(playlist_name: str) -> SyncResult:
    # 1. Pobierz obserwowanych artystów
    artists = client.get_followed_artists()
    
    # 2. Zbierz wszystkie tracki z walidacją
    all_track_ids: set[str] = set()
    for artist in artists:
        albums = client.get_artist_albums(artist.id)
        for album in albums:
            tracks = client.get_album_tracks(album.id)
            for track in tracks:
                # KLUCZOWE: walidacja na poziomie tracka
                if artist.id in [a['id'] for a in track['artists']]:
                    all_track_ids.add(track['id'])
    
    # 3. Pobierz istniejące tracki z playlist serii
    existing_ids = playlist_manager.get_all_tracks_from_series(playlist_name)
    
    # 4. Oblicz różnicę
    new_ids = all_track_ids - existing_ids
    
    # 5. Dodaj brakujące z podziałem na playlisty
    playlist_manager.add_tracks(playlist_name, new_ids)
```

**Kluczowe cechy:**
- ✅ Walidacja `artist_id in track.artists` — nie zakłada, że album = artysta
- ✅ Deduplikacja po `track_id` via `set`
- ✅ Idempotentność — dodaje tylko brakujące
- ✅ Progress bar via `rich` (liczba artystów, albumów)

---

### Zarządzanie playlistami

#### [NEW] [playlist_manager.py](file:///f:/ANTIGRAVITY/repos/spotify%20mega%20sync/ArtistSync/src/artist_sync/playlist_manager.py)

| Funkcja | Opis |
|---------|------|
| `parse_playlist_input(url_or_id)` | Ekstrakcja ID z URL lub zwrócenie surowego ID |
| `find_series_playlists(name)` | Znajduje `Nazwa`, `Nazwa_2`, `Nazwa_3`… wśród playlist użytkownika |
| `get_all_tracks_from_series(name)` | Zbiera track IDs ze wszystkich playlist serii |
| `add_tracks(name, track_ids)` | Dodaje tracki z podziałem: max ~10000/playlista, tworzenie nowych `_2`, `_3`… |
| `ensure_playlist_exists(name)` | Sprawdza/tworzy playlistę |

**Mechanizm podziału:**
```
playlist: "MyMusic"      → 0-9999 tracks
playlist: "MyMusic_2"    → 10000-19999 tracks
playlist: "MyMusic_3"    → 20000-29999 tracks
```

---

### Modele danych

#### [NEW] [models.py](file:///f:/ANTIGRAVITY/repos/spotify%20mega%20sync/ArtistSync/src/artist_sync/models.py)

```python
@dataclass
class SyncResult:
    artists_processed: int
    albums_scanned: int
    tracks_found: int          # unikalne tracki po walidacji
    tracks_already_in_playlist: int
    tracks_added: int
    playlists_used: list[str]  # nazwy użytych playlist
    errors: list[str]
```

---

### Konfiguracja

#### [NEW] [config.py](file:///f:/ANTIGRAVITY/repos/spotify%20mega%20sync/ArtistSync/src/artist_sync/config.py)

- Ładowanie `.env` via `python-dotenv`
- Stałe: `MAX_TRACKS_PER_PLAYLIST = 10_000`, `BATCH_SIZE = 100`
- Walidacja wymaganych zmiennych

---

### CLI

#### [NEW] [cli.py](file:///f:/ANTIGRAVITY/repos/spotify%20mega%20sync/ArtistSync/src/artist_sync/cli.py)

Komendy Click:

```
artist-sync login          # autoryzacja, test połączenia
artist-sync sync <PLAYLIST> # synchronizacja (URL lub ID)
  --dry-run                # pokaż co zostanie dodane bez dodawania
```

- `<PLAYLIST>` — URL playlisty Spotify **lub** nazwa nowej playlisty do stworzenia
- Kolorowy output via `rich`: progress bar, podsumowanie `SyncResult`

---

### Obsługa błędów i rate limiting

Zaimplementowane w `spotify_client.py`:

```python
@retry(
    retry=retry_if_exception_type(SpotifyException),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    stop=stop_after_attempt(5)
)
def _api_call(self, func, *args, **kwargs):
    ...
```

- **HTTP 429:** retry z `Retry-After` header
- **Błędy sieciowe:** retry z exponential backoff (1s → 2s → 4s → … max 60s)
- **Logowanie:** `logging` + `rich.logging.RichHandler`

---

## Verification Plan

### Testy jednostkowe

Uruchomienie: `uv run pytest tests/ -v`

#### [NEW] [test_sync_engine.py](file:///f:/ANTIGRAVITY/repos/spotify%20mega%20sync/ArtistSync/tests/test_sync_engine.py)

- **test_track_artist_validation**: mock tracka z wieloma artystami → tylko tracki z właściwym artystą przechodzą filtr
- **test_deduplication**: ten sam track_id z różnych albumów → 1 wynik
- **test_diff_calculation**: mock istniejących tracków → poprawna różnica

#### [NEW] [test_playlist_manager.py](file:///f:/ANTIGRAVITY/repos/spotify%20mega%20sync/ArtistSync/tests/test_playlist_manager.py)

- **test_parse_url**: URL Spotify → poprawny ID
- **test_series_naming**: sprawdzenie konwencji `Nazwa`, `Nazwa_2`, `Nazwa_3`
- **test_split_tracks_into_playlists**: 15000 tracków → 2 playlisty

### Test manualny (wymaga konta Spotify)

> [!NOTE]
> Do testów integracyjnych potrzebne jest konto Spotify Developer z zarejestrowaną aplikacją. Użytkownik powinien:
> 1. Utworzyć aplikację na https://developer.spotify.com/dashboard
> 2. Ustawić Redirect URI: `http://localhost:8888/callback`
> 3. Skopiować Client ID i Secret do `.env`

**Kroki testu:**
1. `artist-sync login` → sprawdź czy autoryzacja się powiedzie i wyświetli nazwę użytkownika
2. `artist-sync sync "Test Playlist" --dry-run` → sprawdź czy wyświetli listę artystów i liczbę tracków bez dodawania
3. `artist-sync sync "Test Playlist"` → sprawdź czy playlista zostanie utworzona z trackami
4. Ponowne `artist-sync sync "Test Playlist"` → sprawdź idempotentność (0 nowych tracków)
