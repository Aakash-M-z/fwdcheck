"""Thin SerpApi client with a SQLite cache.

The free SerpApi plan gives 250 searches a month, so every response is cached
by its query parameters. Re-running the same check during development (or in
your demo) costs zero credits.
"""
import hashlib
import json
import sqlite3
import threading
import time

import requests

SERPAPI_URL = "https://serpapi.com/search.json"


class SerpClient:
    def __init__(self, api_key: str, cache_path: str = "serp_cache.sqlite",
                 ttl_seconds: int = 3 * 24 * 3600, timeout: int = 25):
        if not api_key:
            raise ValueError("SERPAPI_KEY is missing. Add it to your .env file.")
        self.api_key = api_key
        self.ttl = ttl_seconds
        self.timeout = timeout
        self._lock = threading.Lock()
        self._db = sqlite3.connect(cache_path, check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, ts REAL, body TEXT)"
        )
        self._db.commit()

    # ---------- low level ----------
    def _key(self, params: dict) -> str:
        return hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()

    def search(self, params: dict) -> tuple[dict, bool]:
        """Run a SerpApi search. Returns (json, from_cache)."""
        key = self._key(params)  # api_key is NOT part of the cache key
        with self._lock:
            row = self._db.execute("SELECT ts, body FROM cache WHERE key=?", (key,)).fetchone()
        if row and time.time() - row[0] < self.ttl:
            return json.loads(row[1]), True

        resp = requests.get(SERPAPI_URL, params={**params, "api_key": self.api_key},
                            timeout=self.timeout)
        data = resp.json()
        if resp.status_code != 200 or "error" in data:
            # "Google hasn't returned any results" is a normal empty result, not a failure
            if "hasn't returned any results" in str(data.get("error", "")):
                return {}, False
            raise RuntimeError(f"SerpApi error: {data.get('error', resp.status_code)}")

        with self._lock:
            self._db.execute("REPLACE INTO cache VALUES (?, ?, ?)",
                             (key, time.time(), json.dumps(data)))
            self._db.commit()
        return data, False

    # ---------- engines ----------
    def web(self, query: str, hl: str = "en") -> tuple[list[dict], bool]:
        """Google web search, India-localized."""
        data, cached = self.search({"engine": "google", "q": query, "gl": "in",
                                    "hl": hl, "num": 10})
        results = []
        for r in data.get("organic_results", []):
            results.append({
                "title": r.get("title", ""),
                "link": r.get("link", ""),
                "snippet": r.get("snippet", ""),
                "source": r.get("source") or r.get("displayed_link", ""),
                "date": r.get("date", ""),
                "engine": "google",
            })
        return results, cached

    def news(self, query: str, hl: str = "en") -> tuple[list[dict], bool]:
        """Google News search. Some results are clusters with nested 'stories'."""
        data, cached = self.search({"engine": "google_news", "q": query, "gl": "in",
                                    "hl": hl})
        results = []

        def add(item):
            src = item.get("source") or {}
            results.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": src.get("name", "") if isinstance(src, dict) else str(src),
                "date": item.get("date", ""),
                "engine": "google_news",
            })

        for r in data.get("news_results", []):
            if r.get("link"):
                add(r)
            for story in r.get("stories", [])[:3]:
                if story.get("link"):
                    add(story)
            if r.get("highlight", {}).get("link"):
                add(r["highlight"])
        return results[:10], cached
