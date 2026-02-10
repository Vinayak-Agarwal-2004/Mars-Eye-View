import os
from server.app.services.geodata.base import GeodataProvider
from server.app.services.geodata.fetch_client import fetch


DEFAULT_URL = os.environ.get(
    "NATURAL_EARTH_WORLD_URL",
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson",
)


class NaturalEarthProvider(GeodataProvider):
    def __init__(self, world_url: str = DEFAULT_URL):
        self.world_url = world_url

    def fetch(self, layer: str, params: dict | None = None, headers: dict | None = None) -> bytes:
        if layer == "world":
            return fetch(self.world_url, headers=headers or {})
        raise ValueError(f"Unsupported layer: {layer}")

    def health(self) -> bool:
        try:
            data = fetch(self.world_url, timeout=15, retries=1)
            return len(data) > 100 and data[:1] == b"{"
        except Exception:
            return False
