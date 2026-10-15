"""Small Qloo API client with private disk cache and bounded retries."""
import hashlib
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("QLOO_BASE_URL", "https://hackathon.api.qloo.com")
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)


class QlooError(Exception):
    pass


class QlooClient:
    def __init__(self, api_key=None, use_cache=True, max_retries=3):
        self.api_key = api_key or os.getenv("QLOO_API_KEY")
        if not self.api_key or self.api_key.startswith("paste"):
            raise QlooError("QLOO_API_KEY is missing in .env")
        self.use_cache = use_cache
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({"X-Api-Key": self.api_key})

    def _cache_path(self, path, params):
        raw = path + json.dumps(params, sort_keys=True)
        return CACHE_DIR / (hashlib.sha256(raw.encode()).hexdigest()[:24] + ".json")

    def get(self, path, params):
        cache_file = self._cache_path(path, params)
        if self.use_cache and cache_file.exists():
            return json.loads(cache_file.read_text())

        for attempt in range(self.max_retries):
            r = self.session.get(BASE_URL + path, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            if r.status_code >= 400:
                raise QlooError(f"{r.status_code} on {path}: {r.text[:300]}")
            data = r.json()
            if self.use_cache:
                cache_file.write_text(json.dumps(data))
            return data
        raise QlooError(f"Rate limited on {path} after {self.max_retries} tries")

    def search(self, query, types=None, take=5):
        params = {"query": query, "take": take}
        if types:
            params["types"] = types
        return self.get("/search", params).get("results", [])

    def tags(self, query, take=10):
        data = self.get("/v2/tags", {"filter.query": query, "take": take})
        return data.get("results", {}).get("tags", [])

    def insights(self, params):
        data = self.get("/v2/insights", params)
        return data.get("results", {}).get("entities", [])
