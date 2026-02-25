import os
import photosdl
import time
import sys
import getopt
import threading
from cache import PhotoCache
from immich import ImmichClient
from server import create_app

ALBUM = 'kitchen-dash'
ADDITIONAL = ["thumbnail", "resolution", "orientation", "video_convert", "video_meta", "address"]


def sync_loop(phdl, cache, interval):
    while True:
        try:
            items = phdl.get_album_items(ALBUM, additional=ADDITIONAL)
            parsed = phdl.parse_items(items['data']['list'])

            if len(parsed) < 5:
                print(f"Only {len(parsed)} pictures in album, skipping sync")
            else:
                new_keys = cache.sync_index(parsed)
                print(f"Index synced: {len(parsed)} total, {len(new_keys)} new")
                for cache_key in new_keys:
                    unit_id = parsed[cache_key]
                    dl = phdl.download_item(cache_key=cache_key, unit_id=unit_id)
                    cache.put(cache_key, dl.content)
                    print(f"Cached: {cache_key}")
        except Exception as e:
            print(f"Sync error: {e}")

        time.sleep(interval)


def main(argv):
    url = None
    port = None
    username = None
    password = None
    max_cache_mb = None
    sync_interval = None
    server_port = None
    source = None
    immich_url = None
    immich_api_key = None
    immich_album = None

    try:
        opts, _ = getopt.getopt(
            argv, "hu:p:U:P:m:i:s:",
            ["username=", "password=", "url=", "port=", "max-cache=",
             "interval=", "server-port=", "source=",
             "immich-url=", "immich-api-key=", "immich-album="]
        )
    except getopt.GetoptError:
        print('filesync.py --source <synology|immich> [source options] '
              '[-m <max_cache_mb>] [-i <sync_interval_sec>] [-s <server_port>]')
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            print('filesync.py --source <synology|immich> [source options] '
                  '[-m <max_cache_mb>] [-i <sync_interval_sec>] [-s <server_port>]')
            sys.exit()
        elif opt in ("-u", "--username"):
            username = arg
        elif opt in ("-p", "--password"):
            password = arg
        elif opt in ("-U", "--url"):
            url = arg
        elif opt in ("-P", "--port"):
            port = arg
        elif opt in ("-m", "--max-cache"):
            max_cache_mb = int(arg)
        elif opt in ("-i", "--interval"):
            sync_interval = int(arg)
        elif opt in ("-s", "--server-port"):
            server_port = int(arg)
        elif opt == "--source":
            source = arg
        elif opt == "--immich-url":
            immich_url = arg
        elif opt == "--immich-api-key":
            immich_api_key = arg
        elif opt == "--immich-album":
            immich_album = arg

    # Apply environment variable fallbacks (CLI args take precedence).
    # Numeric params use a truthy check so that empty-string values from
    # systemd EnvironmentFile (e.g. PHOTOS_MAX_CACHE=) fall through to
    # the hardcoded default rather than raising ValueError on int('').
    if source is None:
        source = os.environ.get('PHOTOS_SOURCE', 'synology')
    if username is None:
        username = os.environ.get('PHOTOS_USERNAME', '')
    if password is None:
        password = os.environ.get('PHOTOS_PASSWORD', '')
    if url is None:
        url = os.environ.get('PHOTOS_URL', '')
    if port is None:
        port = os.environ.get('PHOTOS_PORT', '')
    if immich_url is None:
        immich_url = os.environ.get('IMMICH_URL')
    if immich_api_key is None:
        immich_api_key = os.environ.get('IMMICH_API_KEY', '')
    if immich_album is None:
        immich_album = os.environ.get('IMMICH_ALBUM')
    if max_cache_mb is None:
        env_val = os.environ.get('PHOTOS_MAX_CACHE')
        max_cache_mb = int(env_val) if env_val else 250
    if sync_interval is None:
        env_val = os.environ.get('PHOTOS_INTERVAL')
        sync_interval = int(env_val) if env_val else 60
    if server_port is None:
        env_val = os.environ.get('PHOTOS_SERVER_PORT')
        server_port = int(env_val) if env_val else 5000

    cache = PhotoCache(max_bytes=max_cache_mb * 1024 * 1024)

    if source == "immich":
        phdl = ImmichClient(url=immich_url, api_key=immich_api_key,
                            album_id=immich_album)
    else:
        phdl = photosdl.Photos(url, port, username, password,
                               secure=True, cert_verify=True, dsm_version=7,
                               debug=True, otp_code=None)

    sync_thread = threading.Thread(
        target=sync_loop, args=(phdl, cache, sync_interval), daemon=True
    )
    sync_thread.start()

    app = create_app(cache, phdl)
    app.run(host="0.0.0.0", port=server_port)


if __name__ == "__main__":
    main(sys.argv[1:])
