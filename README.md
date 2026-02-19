# photos-sync

Syncs photos from a Synology NAS album to an in-memory cache and serves them over HTTP.  It is hard coded to pull a specific album.  You can utilize this to power picture dashboards.

## How it works

On startup, `filesync.py` connects to a Synology Photos server and indexes all photos in the `kitchen-dash` album. A background thread periodically re-syncs the index, downloading any newly added photos into an LRU cache. A Flask web server runs in the foreground and serves photos from the cache, fetching from the NAS on a cache miss.

```
Synology NAS
     │
     │  (sync loop, every N seconds)
     ▼
  PhotoCache  ◄──── on cache miss
     │
     ▼
 Flask API  ──► clients
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/files` | Returns a random photo |
| `GET` | `/files/<key>.jpg` | Returns a specific photo by cache key |
| `GET` | `/files/list` | JSON list of all indexed filenames |
| `GET` | `/cache/stats` | Cache utilisation stats |

## Running

```bash
pip install -r requirements.txt
python filesync.py -u <username> -p <password> -U <nas-host> -P <nas-port>
```

### Options

| Flag | Long form | Default | Description |
|------|-----------|---------|-------------|
| `-u` | `--username` | | NAS username |
| `-p` | `--password` | | NAS password |
| `-U` | `--url` | | NAS hostname or IP |
| `-P` | `--port` | | NAS port |
| `-m` | `--max-cache` | `250` | Max cache size in MB |
| `-i` | `--interval` | `60` | Sync interval in seconds |
| `-s` | `--server-port` | `5000` | HTTP server port |

## Docker

```bash
docker build -t photos-sync .
docker run -p 5000:5000 photos-sync \
  -u <username> -p <password> -U <nas-host> -P <nas-port>
```

A pre-built image is published to `ghcr.io` on every push to `main`.

## Development

```bash
pip install -r requirements.txt
pytest tests/ -v
photos-sync -u <username> -p <password> -U <nas-host> -P <nas-port>
```

The test suite mocks all Synology API calls. No NAS connection is required to run tests.
