import json
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def photos():
    """A Photos instance with __init__ bypassed and request_data mocked."""
    from photosdl import Photos
    instance = Photos.__new__(Photos)
    instance.request_data = MagicMock()
    return instance


# ---------------------------------------------------------------------------
# parse_items  (static method — no network calls)
# ---------------------------------------------------------------------------

class TestParseItems:
    def _item(self, cache_key, unit_id):
        return {"additional": {"thumbnail": {"cache_key": cache_key, "unit_id": unit_id}}}

    def test_empty_list_returns_empty_dict(self):
        from photosdl import Photos
        assert Photos.parse_items([]) == {}

    def test_single_item(self):
        from photosdl import Photos
        result = Photos.parse_items([self._item("ck1", "uid1")])
        assert result == {"ck1": "uid1"}

    def test_multiple_items(self):
        from photosdl import Photos
        items = [self._item("ck1", "uid1"), self._item("ck2", "uid2"), self._item("ck3", "uid3")]
        result = Photos.parse_items(items)
        assert result == {"ck1": "uid1", "ck2": "uid2", "ck3": "uid3"}

    def test_duplicate_cache_key_last_wins(self):
        from photosdl import Photos
        items = [self._item("ck1", "uid1"), self._item("ck1", "uid2")]
        result = Photos.parse_items(items)
        assert result == {"ck1": "uid2"}

    def test_returns_dict_type(self):
        from photosdl import Photos
        assert isinstance(Photos.parse_items([]), dict)


# ---------------------------------------------------------------------------
# get_album_items
# ---------------------------------------------------------------------------

class TestGetAlbumItems:
    def test_calls_request_data(self, photos):
        photos.request_data.return_value = {"data": {"list": []}}
        photos.get_album_items("my-album")
        photos.request_data.assert_called_once()

    def test_uses_correct_api_name(self, photos):
        photos.request_data.return_value = {}
        photos.get_album_items("my-album")
        api_name = photos.request_data.call_args.args[0]
        assert api_name == "SYNO.Foto.Search.Search"

    def test_album_name_serialized_as_json_keyword(self, photos):
        photos.request_data.return_value = {}
        photos.get_album_items("kitchen-dash")
        req_param = photos.request_data.call_args.args[2]
        assert json.loads(req_param["keyword"]) == "kitchen-dash"

    def test_default_additional_is_empty_list(self, photos):
        photos.request_data.return_value = {}
        photos.get_album_items("album")
        req_param = photos.request_data.call_args.args[2]
        assert json.loads(req_param["additional"]) == []

    def test_custom_additional_fields_passed_through(self, photos):
        photos.request_data.return_value = {}
        photos.get_album_items("album", additional=["thumbnail", "resolution"])
        req_param = photos.request_data.call_args.args[2]
        assert json.loads(req_param["additional"]) == ["thumbnail", "resolution"]

    def test_none_additional_treated_as_empty(self, photos):
        photos.request_data.return_value = {}
        photos.get_album_items("album", additional=None)
        req_param = photos.request_data.call_args.args[2]
        assert json.loads(req_param["additional"]) == []

    def test_uses_post_method(self, photos):
        photos.request_data.return_value = {}
        photos.get_album_items("album")
        kwargs = photos.request_data.call_args.kwargs
        assert kwargs.get("method") == "post"

    def test_limit_set_to_500(self, photos):
        photos.request_data.return_value = {}
        photos.get_album_items("album")
        req_param = photos.request_data.call_args.args[2]
        assert req_param["limit"] == "500"

    def test_offset_set_to_0(self, photos):
        photos.request_data.return_value = {}
        photos.get_album_items("album")
        req_param = photos.request_data.call_args.args[2]
        assert req_param["offset"] == "0"

    def test_returns_request_data_result(self, photos):
        expected = {"data": {"list": [{"id": 42}]}}
        photos.request_data.return_value = expected
        assert photos.get_album_items("album") == expected


# ---------------------------------------------------------------------------
# download_item
# ---------------------------------------------------------------------------

class TestDownloadItem:
    def test_calls_request_data(self, photos):
        photos.download_item("ck1", "uid1")
        photos.request_data.assert_called_once()

    def test_uses_correct_api_name(self, photos):
        photos.download_item("ck1", "uid1")
        api_name = photos.request_data.call_args.args[0]
        assert api_name == "SYNO.Foto.Download"

    def test_passes_cache_key(self, photos):
        photos.download_item("my_cache_key", "uid1")
        req_param = photos.request_data.call_args.args[2]
        assert req_param["cache_key"] == "my_cache_key"

    def test_unit_id_serialized_as_json_array(self, photos):
        photos.download_item("ck1", "my_unit_id")
        req_param = photos.request_data.call_args.args[2]
        assert json.loads(req_param["unit_id"]) == ["my_unit_id"]

    def test_uses_get_method(self, photos):
        photos.download_item("ck1", "uid1")
        kwargs = photos.request_data.call_args.kwargs
        assert kwargs.get("method") == "get"

    def test_response_json_is_false(self, photos):
        photos.download_item("ck1", "uid1")
        kwargs = photos.request_data.call_args.kwargs
        assert kwargs.get("response_json") is False

    def test_download_type_is_optimized_jpeg(self, photos):
        photos.download_item("ck1", "uid1")
        req_param = photos.request_data.call_args.args[2]
        assert req_param["download_type"] == "optimized_jpeg"

    def test_returns_response_object(self, photos):
        mock_response = MagicMock()
        mock_response.content = b"jpeg_bytes"
        photos.request_data.return_value = mock_response
        result = photos.download_item("ck1", "uid1")
        assert result.content == b"jpeg_bytes"
