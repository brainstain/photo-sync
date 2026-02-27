from __future__ import annotations

import requests


class ImmichClient:
    DEFAULT_URL = "https://photosync.michaelgoldstein.co"

    def __init__(self, url: str | None = None, api_key: str = "",
                 album_id: str | None = None) -> None:
        self.url = (url or self.DEFAULT_URL).rstrip("/")
        self.api_key = api_key
        self.album_id = album_id

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key}

    def get_album_items(self, album_name: str | None = None,
                        additional: list[str] | None = None) -> dict:
        """Fetch photos from the configured Immich album.

        The album_name and additional parameters are accepted for interface
        compatibility with the Synology source but are unused; the album is
        determined by self.album_id set at construction time.
        """
        if self.album_id is None:
            # TODO: Determine what photos to sync when no album is configured.
            return {"data": {"list": []}}

        resp = requests.get(
            f"{self.url}/api/albums/{self.album_id}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        return {"data": {"list": data.get("assets", [])}}

    @staticmethod
    def parse_items(items: list[dict]) -> dict[str, str]:
        parsed = {}
        for item in items:
            asset_id = item["id"]
            parsed[asset_id] = asset_id
        return parsed

    def download_item(self, cache_key: str, unit_id: str) -> requests.Response:
        resp = requests.get(
            f"{self.url}/api/assets/{unit_id}/thumbnail",
            headers=self._headers(),
            params={"size": "preview"},
        )
        resp.raise_for_status()
        return resp
