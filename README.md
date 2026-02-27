# photos-sync

Syncs photos from a photo server (Synology NAS or Immich) to an in-memory cache and serves them over HTTP. You can utilize this to power picture dashboards.

## How it works

On startup, `filesync.py` connects to a photo source and indexes all photos in the configured album. A background thread periodically re-syncs the index, downloading any newly added photos into an LRU cache. A Flask web server runs in the foreground and serves photos from the cache, fetching from the source on a cache miss.

```
Photo source (Synology NAS or Immich)
     │
     │  (sync loop, every N seconds)
     ▼
  PhotoCache  ◄──── on cache miss
     │
     ▼
 Flask API  ──► clients
```

## Sources

### Synology (default)

Connects to a Synology Photos server using DSM 7 credentials.

### Immich

Connects to an [Immich](https://immich.app) server using an API key and syncs photos from a specific album. The album ID must be supplied at startup — find it in the Immich web UI URL when browsing the album (e.g. `https://your-server/albums/3f2a1b4c-…`).

Default server URL: `https://photosync.michaelgoldstein.co`

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

# Synology source (default)
python filesync.py -u <username> -p <password> -U <nas-host> -P <nas-port>

# Immich source
python filesync.py --source immich --immich-api-key <key> --immich-album <album-id>
```

### General options

| Flag | Long form | Env var | Default | Description |
|------|-----------|---------|---------|-------------|
| | `--source` | `PHOTOS_SOURCE` | `synology` | Photo source: `synology` or `immich` |
| `-m` | `--max-cache` | `PHOTOS_MAX_CACHE` | `250` | Max cache size in MB |
| `-i` | `--interval` | `PHOTOS_INTERVAL` | `60` | Sync interval in seconds |
| `-s` | `--server-port` | `PHOTOS_SERVER_PORT` | `5000` | HTTP server port |

### Synology options (`--source synology`)

| Flag | Long form | Env var | Default | Description |
|------|-----------|---------|---------|-------------|
| `-u` | `--username` | `PHOTOS_USERNAME` | | NAS username |
| `-p` | `--password` | `PHOTOS_PASSWORD` | | NAS password |
| `-U` | `--url` | `PHOTOS_URL` | | NAS hostname or IP |
| `-P` | `--port` | `PHOTOS_PORT` | | NAS port |

### Immich options (`--source immich`)

| Flag | Long form | Env var | Default | Description |
|------|-----------|---------|---------|-------------|
| | `--immich-url` | `IMMICH_URL` | `https://photosync.michaelgoldstein.co` | Immich server URL |
| | `--immich-api-key` | `IMMICH_API_KEY` | | Immich API key |
| | `--immich-album` | `IMMICH_ALBUM` | | Album ID to sync (required for sync) |

The Immich album ID is the UUID visible in the URL when browsing an album in the Immich web UI.

## Docker

```bash
docker build -t photos-sync .

# Synology source
docker run -p 5000:5000 photos-sync \
  -u <username> -p <password> -U <nas-host> -P <nas-port>

# Immich source
docker run -p 5000:5000 photos-sync \
  --source immich --immich-api-key <key> --immich-album <album-id>
```

A pre-built image is published to `ghcr.io` on every push to `main`.

## LXC / Proxmox

Pre-built LXC templates are published as GitHub Release assets whenever a `v*.*.*` tag is pushed.

### Download

```
https://github.com/<owner>/<repo>/releases/download/<tag>/rootfs.tar.xz
https://github.com/<owner>/<repo>/releases/download/<tag>/meta.tar.xz
```

### Import into Proxmox

On the Proxmox host, download both files and create the container (adjust VMID, storage, and network as needed):

```bash
wget https://github.com/<owner>/<repo>/releases/download/<tag>/rootfs.tar.xz
wget https://github.com/<owner>/<repo>/releases/download/<tag>/meta.tar.xz

pct create 200 rootfs.tar.xz \
  --ostype ubuntu \
  --hostname photos-sync \
  --memory 512 \
  --rootfs local-lvm:8 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 1
```

### Configure

Start the container and edit the environment file:

```bash
pct start 200
pct enter 200
nano /etc/default/photos-sync
```

Set variables for your chosen source. For Synology:

```bash
PHOTOS_SOURCE=synology
PHOTOS_USERNAME=your-nas-username
PHOTOS_PASSWORD=your-nas-password
PHOTOS_URL=192.168.1.100
PHOTOS_PORT=5001
```

For Immich:

```bash
PHOTOS_SOURCE=immich
IMMICH_URL=https://photosync.michaelgoldstein.co
IMMICH_API_KEY=your-api-key
IMMICH_ALBUM=3f2a1b4c-0000-0000-0000-000000000000
```

All environment variables and their defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `PHOTOS_SOURCE` | `synology` | Photo source: `synology` or `immich` |
| `PHOTOS_MAX_CACHE` | `250` | Max cache size in MB |
| `PHOTOS_INTERVAL` | `60` | Sync interval in seconds |
| `PHOTOS_SERVER_PORT` | `5000` | HTTP server port |
| `PHOTOS_USERNAME` | | Synology NAS username |
| `PHOTOS_PASSWORD` | | Synology NAS password |
| `PHOTOS_URL` | | Synology NAS hostname or IP |
| `PHOTOS_PORT` | | Synology NAS port |
| `IMMICH_URL` | `https://photosync.michaelgoldstein.co` | Immich server URL |
| `IMMICH_API_KEY` | | Immich API key |
| `IMMICH_ALBUM` | | Immich album ID to sync |

### Start the service

```bash
systemctl start photos-sync
systemctl status photos-sync

# Follow logs
journalctl -u photos-sync -f
```

The service starts automatically on boot. After editing `/etc/default/photos-sync`:

```bash
systemctl restart photos-sync
```

## Development

```bash
pip install -r requirements.txt
pytest tests/ -v
python filesync.py -u <username> -p <password> -U <nas-host> -P <nas-port>
```

The test suite mocks all external API calls. No NAS or Immich connection is required to run tests.
