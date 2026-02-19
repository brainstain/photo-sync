import pytest
from unittest.mock import MagicMock, patch
from cache import PhotoCache
from server import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cache():
    return PhotoCache()


@pytest.fixture
def phdl():
    mock = MagicMock()
    dl = MagicMock()
    dl.content = b"fake_jpeg"
    mock.download_item.return_value = dl
    return mock


@pytest.fixture
def app(cache, phdl):
    return create_app(cache, phdl)


@pytest.fixture
def client(app):
    app.config["TESTING"] = True
    return app.test_client()


def _seed_cache(cache, keys):
    """Index and populate the cache with dummy data for a list of keys."""
    cache.sync_index({k: f"uid_{k}" for k in keys})
    for k in keys:
        cache.put(k, f"data_{k}".encode())


# ---------------------------------------------------------------------------
# GET /files  (random)
# ---------------------------------------------------------------------------

class TestRandomFile:
    def test_returns_404_when_no_photos(self, client):
        resp = client.get("/files")
        assert resp.status_code == 404

    def test_returns_200_when_photos_exist(self, client, cache):
        _seed_cache(cache, ["k1"])
        resp = client.get("/files")
        assert resp.status_code == 200

    def test_returns_jpeg_content_type(self, client, cache):
        _seed_cache(cache, ["k1"])
        resp = client.get("/files")
        assert resp.content_type == "image/jpeg"

    def test_cache_hit_does_not_call_download(self, client, cache, phdl):
        _seed_cache(cache, ["k1"])
        client.get("/files")
        phdl.download_item.assert_not_called()

    def test_cache_miss_triggers_download(self, client, cache, phdl):
        cache.sync_index({"k1": "uid1"})  # indexed but not cached
        resp = client.get("/files")
        assert resp.status_code == 200
        phdl.download_item.assert_called_once_with(cache_key="k1", unit_id="uid1")

    def test_cache_miss_stores_result_in_cache(self, client, cache, phdl):
        cache.sync_index({"k1": "uid1"})
        client.get("/files")
        assert cache.get("k1") == b"fake_jpeg"

    def test_uses_random_choice(self, client, cache):
        _seed_cache(cache, ["k1", "k2"])
        with patch("server.random.choice", return_value="k1") as mock_choice:
            resp = client.get("/files")
        assert resp.status_code == 200
        mock_choice.assert_called_once()

    def test_response_contains_expected_data(self, client, cache):
        cache.sync_index({"k1": "uid1"})
        cache.put("k1", b"my_image_bytes")
        resp = client.get("/files")
        assert resp.data == b"my_image_bytes"


# ---------------------------------------------------------------------------
# GET /files/list
# ---------------------------------------------------------------------------

class TestListFiles:
    def test_returns_200(self, client):
        resp = client.get("/files/list")
        assert resp.status_code == 200

    def test_empty_index_returns_empty_list(self, client):
        resp = client.get("/files/list")
        assert resp.json == []

    def test_returns_filenames_with_jpg_extension(self, client, cache):
        cache.sync_index({"k1": "u1", "k2": "u2"})
        resp = client.get("/files/list")
        assert set(resp.json) == {"k1.jpg", "k2.jpg"}

    def test_includes_indexed_but_uncached_files(self, client, cache):
        cache.sync_index({"k1": "u1"})
        # Nothing put in the data cache
        assert "k1.jpg" in client.get("/files/list").json

    def test_excludes_removed_keys(self, client, cache):
        cache.sync_index({"k1": "u1"})
        cache.sync_index({})
        assert client.get("/files/list").json == []


# ---------------------------------------------------------------------------
# GET /files/<cache_key>
# ---------------------------------------------------------------------------

class TestGetFile:
    def test_returns_200_for_known_key(self, client, cache):
        _seed_cache(cache, ["k1"])
        assert client.get("/files/k1").status_code == 200

    def test_accepts_jpg_extension(self, client, cache):
        _seed_cache(cache, ["k1"])
        assert client.get("/files/k1.jpg").status_code == 200

    def test_strips_jpg_extension(self, client, cache):
        _seed_cache(cache, ["k1"])
        resp_with = client.get("/files/k1.jpg")
        resp_without = client.get("/files/k1")
        assert resp_with.data == resp_without.data

    def test_returns_jpeg_content_type(self, client, cache):
        _seed_cache(cache, ["k1"])
        assert client.get("/files/k1.jpg").content_type == "image/jpeg"

    def test_returns_correct_file_data(self, client, cache):
        cache.sync_index({"k1": "u1"})
        cache.put("k1", b"specific_bytes")
        assert client.get("/files/k1.jpg").data == b"specific_bytes"

    def test_returns_404_for_unknown_key(self, client):
        assert client.get("/files/nope.jpg").status_code == 404

    def test_cache_hit_does_not_call_download(self, client, cache, phdl):
        _seed_cache(cache, ["k1"])
        client.get("/files/k1.jpg")
        phdl.download_item.assert_not_called()

    def test_cache_miss_triggers_download(self, client, cache, phdl):
        cache.sync_index({"k1": "uid1"})  # indexed, not cached
        resp = client.get("/files/k1.jpg")
        assert resp.status_code == 200
        phdl.download_item.assert_called_once_with(cache_key="k1", unit_id="uid1")

    def test_cache_miss_stores_download_in_cache(self, client, cache, phdl):
        cache.sync_index({"k1": "uid1"})
        client.get("/files/k1.jpg")
        assert cache.get("k1") == b"fake_jpeg"

    def test_second_request_is_cache_hit(self, client, cache, phdl):
        cache.sync_index({"k1": "uid1"})
        client.get("/files/k1.jpg")
        client.get("/files/k1.jpg")
        assert phdl.download_item.call_count == 1

    def test_download_name_header_contains_key(self, client, cache):
        _seed_cache(cache, ["k1"])
        resp = client.get("/files/k1.jpg")
        disposition = resp.headers.get("Content-Disposition", "")
        assert "k1.jpg" in disposition


# ---------------------------------------------------------------------------
# GET /cache/stats
# ---------------------------------------------------------------------------

class TestCacheStats:
    def test_returns_200(self, client):
        assert client.get("/cache/stats").status_code == 200

    def test_returns_all_expected_fields(self, client):
        data = client.get("/cache/stats").json
        assert {"indexed", "cached", "size_bytes", "max_bytes"} <= set(data)

    def test_reflects_current_state(self, client, cache):
        _seed_cache(cache, ["k1", "k2"])
        data = client.get("/cache/stats").json
        assert data["indexed"] == 2
        assert data["cached"] == 2

    def test_size_bytes_reflects_data_in_cache(self, client, cache):
        cache.sync_index({"k1": "u1"})
        cache.put("k1", b"abc")  # 3 bytes
        data = client.get("/cache/stats").json
        assert data["size_bytes"] == 3

    def test_max_bytes_matches_cache_config(self, phdl):
        small_cache = PhotoCache(max_bytes=512)
        app = create_app(small_cache, phdl)
        app.config["TESTING"] = True
        resp = app.test_client().get("/cache/stats")
        assert resp.json["max_bytes"] == 512
