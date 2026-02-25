import pytest
from unittest.mock import MagicMock, patch

from immich import ImmichClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """An ImmichClient pointed at the default URL with a test key and album."""
    return ImmichClient(api_key="test-key", album_id="album-123")


@pytest.fixture
def client_no_album():
    """An ImmichClient with no album configured."""
    return ImmichClient(api_key="test-key")


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_default_url(self):
        c = ImmichClient()
        assert c.url == "https://photosync.michaelgoldstein.co"

    def test_custom_url(self):
        c = ImmichClient(url="https://custom.example.com")
        assert c.url == "https://custom.example.com"

    def test_trailing_slash_stripped(self):
        c = ImmichClient(url="https://custom.example.com/")
        assert c.url == "https://custom.example.com"

    def test_none_url_uses_default(self):
        c = ImmichClient(url=None)
        assert c.url == "https://photosync.michaelgoldstein.co"

    def test_api_key_stored(self):
        c = ImmichClient(api_key="my-secret")
        assert c.api_key == "my-secret"

    def test_album_id_stored(self):
        c = ImmichClient(album_id="abc-123")
        assert c.album_id == "abc-123"

    def test_album_id_defaults_to_none(self):
        c = ImmichClient()
        assert c.album_id is None


# ---------------------------------------------------------------------------
# parse_items  (static method — no network calls)
# ---------------------------------------------------------------------------

class TestParseItems:
    def test_empty_list_returns_empty_dict(self):
        assert ImmichClient.parse_items([]) == {}

    def test_single_item(self):
        items = [{"id": "asset-1"}]
        assert ImmichClient.parse_items(items) == {"asset-1": "asset-1"}

    def test_multiple_items(self):
        items = [{"id": "a1"}, {"id": "a2"}, {"id": "a3"}]
        result = ImmichClient.parse_items(items)
        assert result == {"a1": "a1", "a2": "a2", "a3": "a3"}

    def test_duplicate_id_last_wins(self):
        items = [{"id": "a1"}, {"id": "a1"}]
        result = ImmichClient.parse_items(items)
        assert result == {"a1": "a1"}

    def test_returns_dict_type(self):
        assert isinstance(ImmichClient.parse_items([]), dict)


# ---------------------------------------------------------------------------
# get_album_items — no album configured
# ---------------------------------------------------------------------------

class TestGetAlbumItemsNoAlbum:
    def test_returns_empty_list_when_no_album(self, client_no_album):
        result = client_no_album.get_album_items()
        assert result == {"data": {"list": []}}

    def test_does_not_make_http_call_when_no_album(self, client_no_album):
        with patch("immich.requests.get") as mock_get:
            client_no_album.get_album_items()
            mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# get_album_items — album configured
# ---------------------------------------------------------------------------

class TestGetAlbumItems:
    def test_calls_correct_url(self, client):
        with patch("immich.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"assets": []}
            mock_get.return_value = mock_resp

            client.get_album_items()

            mock_get.assert_called_once()
            url = mock_get.call_args.args[0]
            assert url == "https://photosync.michaelgoldstein.co/api/albums/album-123"

    def test_sends_api_key_header(self, client):
        with patch("immich.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"assets": []}
            mock_get.return_value = mock_resp

            client.get_album_items()

            headers = mock_get.call_args.kwargs["headers"]
            assert headers["x-api-key"] == "test-key"

    def test_wraps_assets_in_expected_format(self, client):
        with patch("immich.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "assets": [{"id": "a1"}, {"id": "a2"}]
            }
            mock_get.return_value = mock_resp

            result = client.get_album_items()

            assert result == {"data": {"list": [{"id": "a1"}, {"id": "a2"}]}}

    def test_empty_assets_returns_empty_list(self, client):
        with patch("immich.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"assets": []}
            mock_get.return_value = mock_resp

            result = client.get_album_items()

            assert result == {"data": {"list": []}}

    def test_missing_assets_key_returns_empty_list(self, client):
        with patch("immich.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {}
            mock_get.return_value = mock_resp

            result = client.get_album_items()

            assert result == {"data": {"list": []}}

    def test_calls_raise_for_status(self, client):
        with patch("immich.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"assets": []}
            mock_get.return_value = mock_resp

            client.get_album_items()

            mock_resp.raise_for_status.assert_called_once()

    def test_album_name_param_ignored(self, client):
        """The album_name parameter exists for interface compat but is unused."""
        with patch("immich.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"assets": []}
            mock_get.return_value = mock_resp

            client.get_album_items("ignored-album-name")

            url = mock_get.call_args.args[0]
            assert "album-123" in url
            assert "ignored-album-name" not in url

    def test_additional_param_ignored(self, client):
        """The additional parameter exists for interface compat but is unused."""
        with patch("immich.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"assets": []}
            mock_get.return_value = mock_resp

            client.get_album_items(additional=["thumbnail"])

            # Should still succeed and not pass additional anywhere
            mock_get.assert_called_once()


# ---------------------------------------------------------------------------
# download_item
# ---------------------------------------------------------------------------

class TestDownloadItem:
    def test_calls_correct_url(self, client):
        with patch("immich.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_get.return_value = mock_resp

            client.download_item("cache-key", "asset-456")

            url = mock_get.call_args.args[0]
            assert url == "https://photosync.michaelgoldstein.co/api/assets/asset-456/thumbnail"

    def test_sends_api_key_header(self, client):
        with patch("immich.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_get.return_value = mock_resp

            client.download_item("ck", "uid")

            headers = mock_get.call_args.kwargs["headers"]
            assert headers["x-api-key"] == "test-key"

    def test_requests_preview_size(self, client):
        with patch("immich.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_get.return_value = mock_resp

            client.download_item("ck", "uid")

            params = mock_get.call_args.kwargs["params"]
            assert params["size"] == "preview"

    def test_calls_raise_for_status(self, client):
        with patch("immich.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_get.return_value = mock_resp

            client.download_item("ck", "uid")

            mock_resp.raise_for_status.assert_called_once()

    def test_returns_response_object(self, client):
        with patch("immich.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.content = b"jpeg_bytes"
            mock_get.return_value = mock_resp

            result = client.download_item("ck", "uid")

            assert result.content == b"jpeg_bytes"

    def test_uses_unit_id_not_cache_key_in_url(self, client):
        with patch("immich.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_get.return_value = mock_resp

            client.download_item("my-cache-key", "my-unit-id")

            url = mock_get.call_args.args[0]
            assert "my-unit-id" in url
            assert "my-cache-key" not in url
