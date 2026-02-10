import json
import os
from server.app.services.geodata.base import GeodataProvider
from server.app.services.geodata.fetch_client import fetch


BASE = os.environ.get(
    "GEOBOUNDARIES_API",
    "https://www.geoboundaries.org/api/current/gbOpen/ALL",
)


class GeoBoundariesProvider(GeodataProvider):
    def __init__(self, base_url: str = BASE):
        self.base_url = base_url.rstrip("/")

    def fetch(self, layer: str, params: dict | None = None, headers: dict | None = None) -> bytes:
        iso = (params or {}).get("iso", "").upper() if params else ""
        if layer == "ADM1" and iso:
            return self._fetch_adm(iso, "ADM1", headers)
        if layer == "ADM2" and iso:
            return self._fetch_adm(iso, "ADM2", headers)
        raise ValueError(f"Unsupported layer: {layer} (need iso for ADM1/ADM2)")

    def _fetch_adm(self, iso: str, adm: str, headers: dict | None) -> bytes:
        api_url = f"{self.base_url}/{adm}/"
        data = fetch(api_url, headers=headers or {})
        items = json.loads(data.decode("utf-8"))
        for item in items:
            if item.get("boundaryISO") == iso:
                gj_url = item.get("gjDownloadURL")
                if gj_url:
                    return fetch(gj_url, headers=headers or {})
        raise ValueError(f"geoBoundaries: no {adm} data for {iso}")

    def health(self) -> bool:
        try:
            data = fetch(f"{self.base_url}/ADM1/", timeout=10, retries=1)
            items = json.loads(data.decode("utf-8"))
            return isinstance(items, list) and len(items) > 0
        except Exception:
            return False
