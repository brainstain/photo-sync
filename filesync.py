import photosdl
import time
import sys
import getopt
import threading
from cache import PhotoCache
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
    url = ''
    port = ''
    username = ''
    password = ''
    max_cache_mb = 250
    sync_interval = 60
    server_port = 5000

    try:
        opts, _ = getopt.getopt(
            argv, "hu:p:U:P:m:i:s:",
            ["username=", "password=", "url=", "port=", "max-cache=", "interval=", "server-port="]
        )
    except getopt.GetoptError:
        print('filesync.py -u <username> -p <password> -U <url> -P <port> '
              '[-m <max_cache_mb>] [-i <sync_interval_sec>] [-s <server_port>]')
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            print('filesync.py -u <username> -p <password> -U <url> -P <port> '
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

    cache = PhotoCache(max_bytes=max_cache_mb * 1024 * 1024)
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
