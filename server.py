import io
import random
from flask import Flask, send_file, jsonify, abort


def create_app(cache, phdl):
    app = Flask(__name__)

    def _fetch_and_cache(cache_key):
        unit_id = cache.get_unit_id(cache_key)
        if unit_id is None:
            return None
        dl = phdl.download_item(cache_key=cache_key, unit_id=unit_id)
        cache.put(cache_key, dl.content)
        return dl.content

    def _serve(cache_key):
        data = cache.get(cache_key)
        if data is None:
            print(f"cache miss for {cache_key}")
            data = _fetch_and_cache(cache_key)
        if data is None:
            abort(404)
        return send_file(io.BytesIO(data), mimetype="image/jpeg",
                         download_name=f"{cache_key}.jpg")

    @app.get("/files")
    def random_file():
        keys = cache.all_keys()
        if not keys:
            abort(404, description="No photos available")
        return _serve(random.choice(keys))

    @app.get("/files/list")
    def list_files():
        return jsonify([f"{k}.jpg" for k in cache.all_keys()])

    @app.get("/files/<cache_key>")
    def get_file(cache_key):
        cache_key = cache_key.removesuffix(".jpg")
        if cache.get_unit_id(cache_key) is None:
            abort(404, description=f"Photo '{cache_key}' not found")
        return _serve(cache_key)

    @app.get("/cache/stats")
    def cache_stats():
        return jsonify(cache.stats)

    return app
