import json
import os
import time
from datetime import datetime, timezone

import requests

TOKEN_TTL = 3600
ACLED_URL = "https://acleddata.com/api/cast/read"
ACLED_AUTH_URL = "https://acleddata.com/oauth/token"


class AcledService:
    def __init__(self):
        self.email = os.getenv("ACLED_EMAIL", "")
        self.key = os.getenv("ACLED_KEY", "")
        self.token = None
        self.token_expiry = 0
        self.cast_cache = {}
        self.cache_file = "data/live/cast_forecasts.json"
        self.load_cache()

    def load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    self.cast_cache = json.load(f)
            except Exception as e:
                print(f"[ACLED] Cache load failed: {e}")

    def _save_cache(self):
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, "w") as f:
                json.dump(self.cast_cache, f)
        except Exception as e:
            print(f"[ACLED] Cache save failed: {e}")

    def _get_token(self):
        if self.token and time.time() < self.token_expiry:
            return self.token
        try:
            resp = requests.post(
                ACLED_AUTH_URL,
                data={
                    "username": self.email,
                    "password": self.key,
                    "grant_type": "password",
                    "client_id": "acled",
                },
                timeout=30,
            )
            resp.raise_for_status()
            self.token = resp.json().get("access_token")
            self.token_expiry = time.time() + TOKEN_TTL
            return self.token
        except Exception as e:
            print(f"[ACLED] Auth failed: {e}")
            return None

    def _cache_key(self, country: str, year: int) -> str:
        return f"{country}:{year}"

    def get_forecast(self, country: str, admin1: str = None, year: int = None):
        target_year = year or datetime.now(timezone.utc).year
        cache_key = self._cache_key(country, target_year)

        if cache_key in self.cast_cache:
            data = self.cast_cache[cache_key]
            if admin1:
                return [x for x in data if x.get("admin1") == admin1]
            return data

        return self._fetch_live_cast(country, target_year)

    def _fetch_live_cast(self, country: str, year: int) -> list:
        token = self._get_token()
        if not token:
            return []

        try:
            resp = requests.get(
                ACLED_URL,
                params={"year": str(year), "country": country, "limit": 1000},
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])

            if data:
                self.cast_cache[self._cache_key(country, year)] = data
                self._save_cache()
            return data
        except Exception as e:
            print(f"[ACLED] Fetch error: {e}")
            return []
