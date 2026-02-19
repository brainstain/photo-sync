import threading
import pytest
from cache import PhotoCache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_items(n, prefix="key", uid_prefix="uid"):
    return {f"{prefix}{i}": f"{uid_prefix}{i}" for i in range(n)}


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestInit:
    def test_default_max_bytes_is_250mb(self):
        cache = PhotoCache()
        assert cache.max_bytes == 250 * 1024 * 1024

    def test_custom_max_bytes(self):
        cache = PhotoCache(max_bytes=1024)
        assert cache.max_bytes == 1024

    def test_starts_empty(self):
        cache = PhotoCache()
        assert cache.all_keys() == []
        assert cache.stats == {
            "indexed": 0, "cached": 0,
            "size_bytes": 0, "max_bytes": 250 * 1024 * 1024,
        }


# ---------------------------------------------------------------------------
# put / get
# ---------------------------------------------------------------------------

class TestPutGet:
    def test_put_and_get_roundtrip(self):
        cache = PhotoCache()
        cache.put("k1", b"image")
        assert cache.get("k1") == b"image"

    def test_get_miss_returns_none(self):
        cache = PhotoCache()
        assert cache.get("missing") is None

    def test_put_replaces_existing_value(self):
        cache = PhotoCache()
        cache.put("k1", b"old")
        cache.put("k1", b"new")
        assert cache.get("k1") == b"new"

    def test_put_tracks_size(self):
        cache = PhotoCache()
        cache.put("k1", b"abc")  # 3 bytes
        assert cache.stats["size_bytes"] == 3

    def test_put_multiple_items_accumulates_size(self):
        cache = PhotoCache()
        cache.put("k1", b"ab")   # 2
        cache.put("k2", b"cde")  # 3  -> total 5
        assert cache.stats["size_bytes"] == 5

    def test_replacing_item_corrects_size(self):
        cache = PhotoCache()
        cache.put("k1", b"abcde")  # 5 bytes
        cache.put("k1", b"ab")     # 2 bytes
        assert cache.stats["size_bytes"] == 2

    def test_item_larger_than_max_not_cached(self):
        cache = PhotoCache(max_bytes=5)
        cache.put("k1", b"x" * 6)
        assert cache.get("k1") is None
        assert cache.stats["size_bytes"] == 0

    def test_item_exactly_max_size_is_cached(self):
        cache = PhotoCache(max_bytes=5)
        cache.put("k1", b"x" * 5)
        assert cache.get("k1") == b"x" * 5


# ---------------------------------------------------------------------------
# LRU eviction
# ---------------------------------------------------------------------------

class TestLRUEviction:
    def test_lru_item_evicted_when_full(self):
        cache = PhotoCache(max_bytes=10)
        cache.put("a", b"x" * 6)  # LRU
        cache.put("b", b"x" * 4)  # total=10
        cache.put("c", b"x" * 4)  # must evict 'a'
        assert cache.get("a") is None
        assert cache.get("b") == b"x" * 4
        assert cache.get("c") == b"x" * 4

    def test_get_promotes_item_to_mru(self):
        cache = PhotoCache(max_bytes=10)
        cache.put("a", b"x" * 5)
        cache.put("b", b"x" * 5)
        cache.get("a")            # 'a' becomes MRU, 'b' becomes LRU
        cache.put("c", b"x" * 5)  # should evict 'b'
        assert cache.get("a") == b"x" * 5
        assert cache.get("b") is None
        assert cache.get("c") == b"x" * 5

    def test_multiple_evictions_to_make_room(self):
        cache = PhotoCache(max_bytes=10)
        cache.put("a", b"x" * 3)
        cache.put("b", b"x" * 3)
        cache.put("c", b"x" * 3)  # total=9
        cache.put("d", b"x" * 8)  # must evict a, b, c
        assert cache.get("a") is None
        assert cache.get("b") is None
        assert cache.get("c") is None
        assert cache.get("d") == b"x" * 8

    def test_size_updated_correctly_after_eviction(self):
        cache = PhotoCache(max_bytes=10)
        cache.put("a", b"x" * 6)
        cache.put("b", b"x" * 6)  # evicts 'a'
        assert cache.stats["size_bytes"] == 6

    def test_cached_count_after_eviction(self):
        cache = PhotoCache(max_bytes=5)
        cache.put("a", b"x" * 3)
        cache.put("b", b"x" * 4)  # evicts 'a'
        assert cache.stats["cached"] == 1


# ---------------------------------------------------------------------------
# sync_index
# ---------------------------------------------------------------------------

class TestSyncIndex:
    def test_adds_new_keys_to_index(self):
        cache = PhotoCache()
        cache.sync_index({"k1": "u1", "k2": "u2"})
        assert set(cache.all_keys()) == {"k1", "k2"}

    def test_returns_newly_added_keys(self):
        cache = PhotoCache()
        added = cache.sync_index({"k1": "u1", "k2": "u2"})
        assert added == {"k1", "k2"}

    def test_returns_only_net_new_keys_on_second_call(self):
        cache = PhotoCache()
        cache.sync_index({"k1": "u1"})
        added = cache.sync_index({"k1": "u1", "k2": "u2"})
        assert added == {"k2"}

    def test_removes_keys_no_longer_in_album(self):
        cache = PhotoCache()
        cache.sync_index({"k1": "u1", "k2": "u2"})
        cache.sync_index({"k2": "u2"})
        assert "k1" not in cache.all_keys()
        assert "k2" in cache.all_keys()

    def test_evicts_cached_data_for_removed_keys(self):
        cache = PhotoCache()
        cache.sync_index({"k1": "u1"})
        cache.put("k1", b"data")
        cache.sync_index({})
        assert cache.get("k1") is None
        assert cache.stats["size_bytes"] == 0

    def test_no_change_returns_empty_set(self):
        cache = PhotoCache()
        cache.sync_index({"k1": "u1"})
        added = cache.sync_index({"k1": "u1"})
        assert added == set()

    def test_empty_to_empty(self):
        cache = PhotoCache()
        added = cache.sync_index({})
        assert added == set()

    def test_preserves_unit_id(self):
        cache = PhotoCache()
        cache.sync_index({"k1": "uid_abc"})
        assert cache.get_unit_id("k1") == "uid_abc"

    def test_existing_cached_data_preserved_for_kept_keys(self):
        cache = PhotoCache()
        cache.sync_index({"k1": "u1", "k2": "u2"})
        cache.put("k1", b"data")
        cache.sync_index({"k1": "u1", "k2": "u2", "k3": "u3"})
        assert cache.get("k1") == b"data"

    def test_full_replacement(self):
        cache = PhotoCache()
        cache.sync_index({"k1": "u1", "k2": "u2"})
        cache.sync_index({"k3": "u3", "k4": "u4"})
        assert set(cache.all_keys()) == {"k3", "k4"}


# ---------------------------------------------------------------------------
# get_unit_id
# ---------------------------------------------------------------------------

class TestGetUnitId:
    def test_returns_unit_id_for_indexed_key(self):
        cache = PhotoCache()
        cache.sync_index({"k1": "uid_xyz"})
        assert cache.get_unit_id("k1") == "uid_xyz"

    def test_returns_none_for_unknown_key(self):
        cache = PhotoCache()
        assert cache.get_unit_id("nope") is None

    def test_returns_none_after_key_removed(self):
        cache = PhotoCache()
        cache.sync_index({"k1": "u1"})
        cache.sync_index({})
        assert cache.get_unit_id("k1") is None


# ---------------------------------------------------------------------------
# all_keys
# ---------------------------------------------------------------------------

class TestAllKeys:
    def test_empty_cache_returns_empty_list(self):
        cache = PhotoCache()
        assert cache.all_keys() == []

    def test_returns_all_indexed_keys(self):
        cache = PhotoCache()
        cache.sync_index({"k1": "u1", "k2": "u2"})
        assert set(cache.all_keys()) == {"k1", "k2"}

    def test_includes_keys_not_in_data_cache(self):
        cache = PhotoCache(max_bytes=1)
        cache.sync_index({"k1": "u1"})
        # Nothing put in data cache
        assert "k1" in cache.all_keys()

    def test_excludes_removed_keys(self):
        cache = PhotoCache()
        cache.sync_index({"k1": "u1"})
        cache.sync_index({})
        assert cache.all_keys() == []


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_initial_stats(self):
        cache = PhotoCache(max_bytes=1000)
        assert cache.stats == {
            "indexed": 0, "cached": 0, "size_bytes": 0, "max_bytes": 1000
        }

    def test_indexed_count_reflects_index(self):
        cache = PhotoCache()
        cache.sync_index({"k1": "u1", "k2": "u2"})
        assert cache.stats["indexed"] == 2

    def test_cached_count_reflects_data_cache(self):
        cache = PhotoCache()
        cache.put("k1", b"data")
        assert cache.stats["cached"] == 1

    def test_indexed_and_cached_can_differ(self):
        cache = PhotoCache()
        cache.sync_index({"k1": "u1", "k2": "u2"})
        cache.put("k1", b"data")
        s = cache.stats
        assert s["indexed"] == 2
        assert s["cached"] == 1

    def test_size_bytes_decreases_after_eviction(self):
        cache = PhotoCache(max_bytes=10)
        cache.put("a", b"x" * 6)
        cache.put("b", b"x" * 6)  # evicts 'a'
        assert cache.stats["size_bytes"] == 6


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_puts_do_not_raise(self):
        cache = PhotoCache(max_bytes=1024 * 1024)
        errors = []

        def worker(i):
            try:
                cache.put(f"key{i}", b"x" * 100)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []

    def test_concurrent_sync_index_do_not_raise(self):
        cache = PhotoCache()
        errors = []

        def worker(i):
            try:
                cache.sync_index({f"key{i}": f"uid{i}"})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []

    def test_concurrent_get_put_do_not_raise(self):
        cache = PhotoCache(max_bytes=1024)
        cache.put("k", b"initial")
        errors = []

        def reader():
            try:
                for _ in range(100):
                    cache.get("k")
            except Exception as e:
                errors.append(e)

        def writer(i):
            try:
                for _ in range(20):
                    cache.put(f"k{i}", b"x" * 10)
            except Exception as e:
                errors.append(e)

        threads = (
            [threading.Thread(target=reader) for _ in range(5)]
            + [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
