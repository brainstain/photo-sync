import pytest
from unittest.mock import MagicMock, patch, call
import filesync
from filesync import sync_loop


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_phdl(num_items=5):
    """Return a mock phdl whose get/parse/download behave sensibly."""
    phdl = MagicMock()
    raw_items = [None] * num_items  # parse_items receives the list
    phdl.get_album_items.return_value = {"data": {"list": raw_items}}
    phdl.parse_items.return_value = {f"key{i}": f"uid{i}" for i in range(num_items)}
    dl = MagicMock()
    dl.content = b"image_data"
    phdl.download_item.return_value = dl
    return phdl


def _run_one_iteration(phdl, cache):
    """Run sync_loop for exactly one iteration by interrupting time.sleep."""
    with patch("filesync.time.sleep", side_effect=KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt):
            sync_loop(phdl, cache, 60)


# ---------------------------------------------------------------------------
# sync_loop — happy path
# ---------------------------------------------------------------------------

class TestSyncLoopHappyPath:
    def test_calls_get_album_items_with_album_name(self):
        cache = MagicMock()
        cache.sync_index.return_value = set()
        phdl = _make_phdl()

        _run_one_iteration(phdl, cache)

        phdl.get_album_items.assert_called_once_with(
            filesync.ALBUM, additional=filesync.ADDITIONAL
        )

    def test_passes_correct_additional_fields(self):
        cache = MagicMock()
        cache.sync_index.return_value = set()
        phdl = _make_phdl()

        _run_one_iteration(phdl, cache)

        _, kwargs = phdl.get_album_items.call_args
        assert kwargs["additional"] == filesync.ADDITIONAL

    def test_calls_parse_items_with_list(self):
        cache = MagicMock()
        cache.sync_index.return_value = set()
        phdl = _make_phdl()

        _run_one_iteration(phdl, cache)

        phdl.parse_items.assert_called_once_with(phdl.get_album_items.return_value["data"]["list"])

    def test_calls_sync_index_with_parsed_items(self):
        cache = MagicMock()
        cache.sync_index.return_value = set()
        phdl = _make_phdl()

        _run_one_iteration(phdl, cache)

        cache.sync_index.assert_called_once_with(phdl.parse_items.return_value)

    def test_downloads_only_newly_added_keys(self):
        cache = MagicMock()
        cache.sync_index.return_value = {"key2"}  # only key2 is new
        phdl = _make_phdl()

        _run_one_iteration(phdl, cache)

        phdl.download_item.assert_called_once_with(cache_key="key2", unit_id="uid2")

    def test_puts_downloaded_content_in_cache(self):
        cache = MagicMock()
        cache.sync_index.return_value = {"key0"}
        phdl = _make_phdl()

        _run_one_iteration(phdl, cache)

        cache.put.assert_called_once_with("key0", b"image_data")

    def test_downloads_all_new_keys(self):
        cache = MagicMock()
        cache.sync_index.return_value = {"key0", "key1", "key2"}
        phdl = _make_phdl()

        _run_one_iteration(phdl, cache)

        assert phdl.download_item.call_count == 3
        assert cache.put.call_count == 3

    def test_no_downloads_when_no_new_keys(self):
        cache = MagicMock()
        cache.sync_index.return_value = set()
        phdl = _make_phdl()

        _run_one_iteration(phdl, cache)

        phdl.download_item.assert_not_called()
        cache.put.assert_not_called()

    def test_sleeps_for_configured_interval(self):
        cache = MagicMock()
        cache.sync_index.return_value = set()
        phdl = _make_phdl()

        with patch("filesync.time.sleep", side_effect=KeyboardInterrupt) as mock_sleep:
            with pytest.raises(KeyboardInterrupt):
                sync_loop(phdl, cache, 120)

        mock_sleep.assert_called_with(120)


# ---------------------------------------------------------------------------
# sync_loop — too few pictures
# ---------------------------------------------------------------------------

class TestSyncLoopTooFewPictures:
    def test_skips_sync_when_fewer_than_5_items(self):
        cache = MagicMock()
        phdl = _make_phdl(num_items=4)

        _run_one_iteration(phdl, cache)

        cache.sync_index.assert_not_called()
        phdl.download_item.assert_not_called()

    def test_syncs_when_exactly_5_items(self):
        cache = MagicMock()
        cache.sync_index.return_value = set()
        phdl = _make_phdl(num_items=5)

        _run_one_iteration(phdl, cache)

        cache.sync_index.assert_called_once()

    def test_still_sleeps_when_skipping(self):
        cache = MagicMock()
        phdl = _make_phdl(num_items=3)

        with patch("filesync.time.sleep", side_effect=KeyboardInterrupt) as mock_sleep:
            with pytest.raises(KeyboardInterrupt):
                sync_loop(phdl, cache, 30)

        mock_sleep.assert_called_with(30)


# ---------------------------------------------------------------------------
# sync_loop — error handling
# ---------------------------------------------------------------------------

class TestSyncLoopErrorHandling:
    def test_continues_after_network_error(self):
        cache = MagicMock()
        cache.sync_index.return_value = set()
        phdl = MagicMock()

        call_count = [0]

        def get_album_items_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ConnectionError("server unreachable")
            return {"data": {"list": []}}

        phdl.get_album_items.side_effect = get_album_items_side_effect
        phdl.parse_items.return_value = {}

        sleep_count = [0]

        def mock_sleep(t):
            sleep_count[0] += 1
            if sleep_count[0] >= 2:
                raise KeyboardInterrupt

        with patch("filesync.time.sleep", side_effect=mock_sleep):
            with pytest.raises(KeyboardInterrupt):
                sync_loop(phdl, cache, 10)

        assert call_count[0] == 2  # ran twice despite first failure

    def test_continues_after_download_error(self):
        cache = MagicMock()
        cache.sync_index.return_value = {"key0"}
        phdl = _make_phdl()
        phdl.download_item.side_effect = OSError("download failed")

        # Should not propagate; the except block catches it
        with patch("filesync.time.sleep", side_effect=KeyboardInterrupt):
            with pytest.raises(KeyboardInterrupt):
                sync_loop(phdl, cache, 60)

    def test_sleeps_even_after_error(self):
        phdl = MagicMock()
        phdl.get_album_items.side_effect = RuntimeError("boom")
        cache = MagicMock()

        with patch("filesync.time.sleep", side_effect=KeyboardInterrupt) as mock_sleep:
            with pytest.raises(KeyboardInterrupt):
                sync_loop(phdl, cache, 60)

        mock_sleep.assert_called_once_with(60)


# ---------------------------------------------------------------------------
# sync_loop — multiple iterations
# ---------------------------------------------------------------------------

class TestSyncLoopMultipleIterations:
    def test_runs_multiple_times(self):
        cache = MagicMock()
        cache.sync_index.return_value = set()
        phdl = _make_phdl()

        sleep_count = [0]

        def mock_sleep(t):
            sleep_count[0] += 1
            if sleep_count[0] >= 3:
                raise KeyboardInterrupt

        with patch("filesync.time.sleep", side_effect=mock_sleep):
            with pytest.raises(KeyboardInterrupt):
                sync_loop(phdl, cache, 60)

        assert phdl.get_album_items.call_count == 3


# ---------------------------------------------------------------------------
# main() — argument parsing
# ---------------------------------------------------------------------------

class TestMainArgParsing:
    """Patch everything that causes I/O so we can exercise just the arg parsing."""

    def _run(self, args):
        with patch("filesync.photosdl.Photos") as mock_phdl_cls, \
             patch("filesync.threading.Thread") as mock_thread_cls, \
             patch("filesync.create_app") as mock_create_app, \
             patch("filesync.PhotoCache") as mock_cache_cls:
            mock_create_app.return_value = MagicMock()
            mock_thread_cls.return_value = MagicMock()
            mock_cache_cls.return_value = MagicMock()
            filesync.main(args)
            return mock_phdl_cls, mock_thread_cls, mock_cache_cls, mock_create_app

    def test_default_cache_size_250mb(self):
        _, _, mock_cache_cls, _ = self._run(["-u", "u", "-p", "p", "-U", "h", "-P", "5001"])
        mock_cache_cls.assert_called_once_with(max_bytes=250 * 1024 * 1024)

    def test_custom_cache_size_via_short_flag(self):
        _, _, mock_cache_cls, _ = self._run(["-u", "u", "-p", "p", "-U", "h", "-P", "1", "-m", "100"])
        mock_cache_cls.assert_called_once_with(max_bytes=100 * 1024 * 1024)

    def test_custom_cache_size_via_long_flag(self):
        _, _, mock_cache_cls, _ = self._run(
            ["-u", "u", "-p", "p", "-U", "h", "-P", "1", "--max-cache", "50"]
        )
        mock_cache_cls.assert_called_once_with(max_bytes=50 * 1024 * 1024)

    def test_credentials_passed_to_phdl(self):
        mock_phdl_cls, _, _, _ = self._run(
            ["-u", "alice", "-p", "secret", "-U", "nas.local", "-P", "5001"]
        )
        mock_phdl_cls.assert_called_once_with(
            "nas.local", "5001", "alice", "secret",
            secure=True, cert_verify=True, dsm_version=7, debug=True, otp_code=None,
        )

    def test_long_form_credentials(self):
        mock_phdl_cls, _, _, _ = self._run(
            ["--username", "bob", "--password", "pw", "--url", "host", "--port", "9000"]
        )
        mock_phdl_cls.assert_called_once_with(
            "host", "9000", "bob", "pw",
            secure=True, cert_verify=True, dsm_version=7, debug=True, otp_code=None,
        )

    def test_default_server_port_5000(self):
        _, _, _, mock_create_app = self._run(["-u", "u", "-p", "p", "-U", "h", "-P", "1"])
        mock_create_app.return_value.run.assert_called_once_with(host="0.0.0.0", port=5000)

    def test_custom_server_port(self):
        _, _, _, mock_create_app = self._run(
            ["-u", "u", "-p", "p", "-U", "h", "-P", "1", "-s", "8080"]
        )
        mock_create_app.return_value.run.assert_called_once_with(host="0.0.0.0", port=8080)

    def test_long_form_server_port(self):
        _, _, _, mock_create_app = self._run(
            ["-u", "u", "-p", "p", "-U", "h", "-P", "1", "--server-port", "9090"]
        )
        mock_create_app.return_value.run.assert_called_once_with(host="0.0.0.0", port=9090)

    def test_invalid_args_exits(self):
        with pytest.raises(SystemExit):
            filesync.main(["--not-a-real-flag"])

    def test_sync_thread_started_as_daemon(self):
        _, mock_thread_cls, _, _ = self._run(["-u", "u", "-p", "p", "-U", "h", "-P", "1"])
        thread_kwargs = mock_thread_cls.call_args.kwargs
        assert thread_kwargs.get("daemon") is True
        mock_thread_cls.return_value.start.assert_called_once()

    def test_sync_thread_targets_sync_loop(self):
        _, mock_thread_cls, _, _ = self._run(["-u", "u", "-p", "p", "-U", "h", "-P", "1"])
        thread_kwargs = mock_thread_cls.call_args.kwargs
        assert thread_kwargs.get("target") is sync_loop

    def test_default_sync_interval_60(self):
        _, mock_thread_cls, _, _ = self._run(["-u", "u", "-p", "p", "-U", "h", "-P", "1"])
        thread_args = mock_thread_cls.call_args.kwargs.get("args", ())
        # args = (phdl, cache, interval)
        assert thread_args[2] == 60

    def test_custom_sync_interval(self):
        _, mock_thread_cls, _, _ = self._run(
            ["-u", "u", "-p", "p", "-U", "h", "-P", "1", "-i", "300"]
        )
        thread_args = mock_thread_cls.call_args.kwargs.get("args", ())
        assert thread_args[2] == 300


# ---------------------------------------------------------------------------
# main() — environment variable fallbacks
# ---------------------------------------------------------------------------

class TestMainEnvVarFallbacks:
    """Env vars are used when no CLI arg is supplied; CLI args always win."""

    def _run(self, args, env=None):
        with patch("filesync.photosdl.Photos") as mock_phdl_cls, \
             patch("filesync.threading.Thread") as mock_thread_cls, \
             patch("filesync.create_app") as mock_create_app, \
             patch("filesync.PhotoCache") as mock_cache_cls, \
             patch.dict("os.environ", env or {}, clear=False):
            mock_create_app.return_value = MagicMock()
            mock_thread_cls.return_value = MagicMock()
            mock_cache_cls.return_value = MagicMock()
            filesync.main(args)
            return mock_phdl_cls, mock_thread_cls, mock_cache_cls, mock_create_app

    def test_credentials_from_env_vars(self):
        mock_phdl_cls, _, _, _ = self._run([], env={
            "PHOTOS_USERNAME": "envuser",
            "PHOTOS_PASSWORD": "envpass",
            "PHOTOS_URL": "nas.local",
            "PHOTOS_PORT": "5001",
        })
        mock_phdl_cls.assert_called_once_with(
            "nas.local", "5001", "envuser", "envpass",
            secure=True, cert_verify=True, dsm_version=7, debug=True, otp_code=None,
        )

    def test_cli_args_override_env_vars(self):
        mock_phdl_cls, _, _, _ = self._run(
            ["-u", "cliuser", "-p", "clipass", "-U", "cli.host", "-P", "9000"],
            env={
                "PHOTOS_USERNAME": "envuser",
                "PHOTOS_PASSWORD": "envpass",
                "PHOTOS_URL": "env.host",
                "PHOTOS_PORT": "1111",
            }
        )
        mock_phdl_cls.assert_called_once_with(
            "cli.host", "9000", "cliuser", "clipass",
            secure=True, cert_verify=True, dsm_version=7, debug=True, otp_code=None,
        )

    def test_max_cache_from_env_var(self):
        _, _, mock_cache_cls, _ = self._run(
            ["-u", "u", "-p", "p", "-U", "h", "-P", "1"],
            env={"PHOTOS_MAX_CACHE": "500"}
        )
        mock_cache_cls.assert_called_once_with(max_bytes=500 * 1024 * 1024)

    def test_interval_from_env_var(self):
        _, mock_thread_cls, _, _ = self._run(
            ["-u", "u", "-p", "p", "-U", "h", "-P", "1"],
            env={"PHOTOS_INTERVAL": "120"}
        )
        thread_args = mock_thread_cls.call_args.kwargs.get("args", ())
        assert thread_args[2] == 120

    def test_server_port_from_env_var(self):
        _, _, _, mock_create_app = self._run(
            ["-u", "u", "-p", "p", "-U", "h", "-P", "1"],
            env={"PHOTOS_SERVER_PORT": "8080"}
        )
        mock_create_app.return_value.run.assert_called_once_with(host="0.0.0.0", port=8080)

    def test_cli_max_cache_overrides_env_var(self):
        _, _, mock_cache_cls, _ = self._run(
            ["-u", "u", "-p", "p", "-U", "h", "-P", "1", "-m", "100"],
            env={"PHOTOS_MAX_CACHE": "999"}
        )
        mock_cache_cls.assert_called_once_with(max_bytes=100 * 1024 * 1024)

    def test_empty_env_var_falls_back_to_default_max_cache(self):
        _, _, mock_cache_cls, _ = self._run(
            ["-u", "u", "-p", "p", "-U", "h", "-P", "1"],
            env={"PHOTOS_MAX_CACHE": ""}
        )
        mock_cache_cls.assert_called_once_with(max_bytes=250 * 1024 * 1024)

    def test_empty_env_var_falls_back_to_default_interval(self):
        _, mock_thread_cls, _, _ = self._run(
            ["-u", "u", "-p", "p", "-U", "h", "-P", "1"],
            env={"PHOTOS_INTERVAL": ""}
        )
        thread_args = mock_thread_cls.call_args.kwargs.get("args", ())
        assert thread_args[2] == 60

    def test_empty_env_var_falls_back_to_default_server_port(self):
        _, _, _, mock_create_app = self._run(
            ["-u", "u", "-p", "p", "-U", "h", "-P", "1"],
            env={"PHOTOS_SERVER_PORT": ""}
        )
        mock_create_app.return_value.run.assert_called_once_with(host="0.0.0.0", port=5000)

    def test_hardcoded_defaults_when_no_env_or_cli(self):
        _, mock_thread_cls, mock_cache_cls, mock_create_app = self._run(
            ["-u", "u", "-p", "p", "-U", "h", "-P", "1"]
        )
        mock_cache_cls.assert_called_once_with(max_bytes=250 * 1024 * 1024)
        thread_args = mock_thread_cls.call_args.kwargs.get("args", ())
        assert thread_args[2] == 60
        mock_create_app.return_value.run.assert_called_once_with(host="0.0.0.0", port=5000)
