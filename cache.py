import threading
from collections import OrderedDict


class PhotoCache:
    DEFAULT_MAX_BYTES = 250 * 1024 * 1024  # 250 MB

    def __init__(self, max_bytes=DEFAULT_MAX_BYTES):
        self.max_bytes = max_bytes
        self._data = OrderedDict()  # cache_key -> bytes (LRU order)
        self._index = {}            # cache_key -> unit_id (all known photos)
        self._size = 0
        self._lock = threading.Lock()

    def sync_index(self, items):
        """Atomically update the index from a fresh {cache_key: unit_id} dict.

        Removes entries no longer present (and evicts from cache).
        Returns the set of newly added cache_keys.
        """
        with self._lock:
            new_keys = set(items.keys())
            old_keys = set(self._index.keys())

            for key in old_keys - new_keys:
                self._index.pop(key, None)
                if key in self._data:
                    self._size -= len(self._data.pop(key))

            added = new_keys - old_keys
            for key in added:
                self._index[key] = items[key]

            return added

    def get_unit_id(self, cache_key):
        with self._lock:
            return self._index.get(cache_key)

    def all_keys(self):
        with self._lock:
            return list(self._index.keys())

    def get(self, cache_key):
        with self._lock:
            if cache_key in self._data:
                self._data.move_to_end(cache_key)
                return self._data[cache_key]
            return None

    def put(self, cache_key, data):
        size = len(data)
        if size > self.max_bytes:
            return  # single item too large to cache
        with self._lock:
            if cache_key in self._data:
                self._size -= len(self._data.pop(cache_key))
            while self._size + size > self.max_bytes and self._data:
                _, evicted = self._data.popitem(last=False)  # evict LRU
                self._size -= len(evicted)
            self._data[cache_key] = data
            self._data.move_to_end(cache_key)
            self._size += size

    @property
    def stats(self):
        with self._lock:
            return {
                "indexed": len(self._index),
                "cached": len(self._data),
                "size_bytes": self._size,
                "max_bytes": self.max_bytes,
            }
