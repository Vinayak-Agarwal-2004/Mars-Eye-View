"""
WikipediaFetcher: Implements pipeline from ingestion_engine/wiki.md
Fetches Wikipedia pages by title, geosearch, or best-match for map/panel integration.
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import quote

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "data" / "interactions" / "cache" / "wikipedia"
BASE_URL = "https://en.wikipedia.org/w/api.php"
REST_BASE = "https://en.wikipedia.org/api/rest_v1"
USER_AGENT = "GDELT-Streamer/1.0 (https://github.com/gdelt-streamer; map visualization)"


class WikipediaFetcher:
    def __init__(self, use_disk_cache: bool = True):
        self.base_url = BASE_URL
        self.rest_base = REST_BASE
        self._memory_cache: Dict[str, Any] = {}
        self.use_disk_cache = use_disk_cache
        if use_disk_cache:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, *parts) -> str:
        return ":".join(str(p) for p in parts)

    def _get_cached(self, key: str) -> Optional[Any]:
        if key in self._memory_cache:
            return self._memory_cache[key]
        if self.use_disk_cache:
            f = CACHE_DIR / f"{hash(key) % (2**32):08x}.json"
            if f.exists():
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    self._memory_cache[key] = data
                    return data
                except Exception:
                    pass
        return None

    def _set_cached(self, key: str, data: Any) -> None:
        self._memory_cache[key] = data
        if self.use_disk_cache:
            try:
                f = CACHE_DIR / f"{hash(key) % (2**32):08x}.json"
                f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

    def _get(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[Dict]:
        h = {"User-Agent": USER_AGENT}
        if headers:
            h.update(headers)
        try:
            r = requests.get(url, params=params, headers=h, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    def get_by_title(self, title: str) -> Optional[Dict]:
        if not title or not title.strip():
            return None
        key = self._cache_key("title", title.strip())
        cached = self._get_cached(key)
        if cached is not None:
            if cached.get("_missing"):
                return None
            return cached

        params = {
            "action": "query",
            "format": "json",
            "titles": title.strip(),
            "prop": "info|extracts|pageimages",
            "inprop": "url",
            "exintro": True,
            "explaintext": True,
            "pithumbsize": 500,
        }
        data = self._get(self.base_url, params=params)
        if not data or "query" not in data or "pages" not in data["query"]:
            return None
        pages = data["query"]["pages"]
        page = next(iter(pages.values()))
        if page.get("pageid") == -1 or "missing" in page:
            self._set_cached(key, {"_missing": True})
            return None
        out = {
            "title": page.get("title", ""),
            "pageid": page.get("pageid"),
            "fullurl": page.get("fullurl", f"https://en.wikipedia.org/wiki/{quote(title)}"),
            "extract": page.get("extract", ""),
            "thumbnail": (page.get("thumbnail") or {}).get("source") if page.get("thumbnail") else None,
        }
        self._set_cached(key, out)
        return out

    def get_by_geosearch(self, lat: float, lon: float, radius: int = 10000, limit: int = 5) -> List[Dict]:
        key = self._cache_key("geo", round(lat, 4), round(lon, 4), radius, limit)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        params = {
            "action": "query",
            "list": "geosearch",
            "format": "json",
            "gscoord": f"{lat}|{lon}",
            "gsradius": radius,
            "gslimit": limit,
        }
        data = self._get(self.base_url, params=params)
        if not data or "query" not in data or "geosearch" not in data["query"]:
            result = []
        else:
            result = data["query"]["geosearch"]
        self._set_cached(key, result)
        return result

    def get_best_match(self, place_name: str, lat: Optional[float] = None, lon: Optional[float] = None) -> Optional[Dict]:
        if not place_name or not place_name.strip():
            return None
        result = self.get_by_title(place_name.strip())
        if result:
            return result
        if lat is not None and lon is not None:
            geo = self.get_by_geosearch(lat, lon, limit=5)
            if geo:
                return self.get_by_title(geo[0]["title"])
        return None

    def get_mobile_sections(self, title: str) -> Optional[Dict]:
        if not title or not title.strip():
            return None
        key = self._cache_key("mobile", title.strip())
        cached = self._get_cached(key)
        if cached is not None:
            if cached.get("_missing"):
                return None
            return cached

        encoded = quote(title.strip().replace(" ", "_"))
        url = f"{self.rest_base}/page/mobile-sections/{encoded}"
        data = self._get(url)
        if not data:
            self._set_cached(key, {"_missing": True})
            return None
        self._set_cached(key, data)
        return data
