#!/usr/bin/env python3
"""
eBird API v2 data source for Beijing bird watching.

API docs: https://documenter.getpostman.com/view/664302/S1ENwy59
Requires free API key from https://ebird.org/api/keygen
"""
import csv
import io
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


class EBirdSource:
    """Fetch bird observations from eBird API."""

    BASE = "https://api.ebird.org/v2"

    # Default region: CN-11 = Beijing (GB/T 2260)
    # Set env BIRDING_REGION for other provinces, e.g. CN-31 (Shanghai), CN-44 (Guangdong)
    DEFAULT_REGION = "CN-11"

    # Force direct connection (bypass any SOCKS/HTTP proxy)
    _opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler()
    )

    def __init__(self, api_key: str, cache_ttl: int = 300):
        self._api_key = api_key
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, Any]] = {}

    # ── helpers ──────────────────────────────────────────────

    def _fetch(self, path: str, params: dict[str, str] = None) -> Any:
        """GET from eBird API with caching."""
        url = f"{self.BASE}{path}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items() if v)
            url = f"{url}?{qs}"

        now = time.time()
        cached = self._cache.get(url)
        if cached and (now - cached[0]) < self._cache_ttl:
            return cached[1]

        req = urllib.request.Request(url, headers={"X-eBirdApiToken": self._api_key})
        try:
            with self._opener.open(req, timeout=15) as r:
                ct = r.headers.get("Content-Type", "")
                if "json" in ct:
                    data = json.loads(r.read().decode("utf-8"))
                else:
                    data = r.read().decode("utf-8")
                self._cache[url] = (now, data)
                return data
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"eBird API error {e.code} for {path}: {body}") from e

    def _fetch_csv(self, path: str) -> list[dict[str, str]]:
        """GET CSV endpoint, return list of dicts."""
        raw = self._fetch(path)
        if isinstance(raw, str):
            reader = csv.DictReader(io.StringIO(raw))
            return list(reader)
        # Some CSV endpoints have no header — try to detect
        return raw if isinstance(raw, list) else []

    # ── public queries ───────────────────────────────────────

    @staticmethod
    def _resolve_region(region: str = None) -> str:
        """Return region code, using env var or default."""
        return region or os.environ.get("BIRDING_REGION") or EBirdSource.DEFAULT_REGION

    def recent_observations(
        self,
        region: str = None,
        days_back: int = 14,
        max_results: int = 100,
        species_code: str = None,
    ) -> list[dict]:
        region = self._resolve_region(region)
        """Recent bird observations in a region.

        If species_code is provided, uses the species-specific endpoint:
          /data/obs/{region}/recent/{speciesCode}
        Otherwise uses the general endpoint:
          /data/obs/{region}/recent
        """
        if species_code:
            path = f"/data/obs/{region}/recent/{species_code}"
            params = {
                "back": str(days_back),
                "maxResults": str(max_results),
            }
        else:
            path = f"/data/obs/{region}/recent"
            params = {
                "back": str(days_back),
                "maxResults": str(max_results),
            }
        return self._fetch(path, params)

    def notable_observations(
        self,
        region: str = None,
        days_back: int = 14,
        max_results: int = 50,
    ) -> list[dict]:
        """Recent notable/rare observations in a region."""
        region = self._resolve_region(region)
        path = f"/data/obs/{region}/recent/notable"
        params = {
            "back": str(days_back),
            "maxResults": str(max_results),
        }
        return self._fetch(path, params)

    def hotspot_list(self, region: str = None) -> list[dict]:
        """List hotspot birding locations in a region."""
        region = self._resolve_region(region)
        path = f"/ref/hotspot/{region}"
        rows = self._fetch_csv(path)
        # The CSV has no header; build dicts manually
        if rows and any(k.startswith("L") for k in rows[0].keys() if k != ""):
            # CSV reader treated first row as header — re-parse
            headers = [
                "locId", "countryCode", "subnational1Code", "subnational2Code",
                "lat", "lng", "locName", "lastDate", "numSpecies", "numChecklists",
            ]
            raw = self._fetch(path)
            if isinstance(raw, str):
                reader = csv.reader(io.StringIO(raw))
                rows = [dict(zip(headers, r)) for r in reader]
        return rows

    def hotspot_observations(
        self,
        loc_id: str,
        days_back: int = 14,
        max_results: int = 50,
    ) -> list[dict]:
        """Recent observations at a specific hotspot."""
        path = f"/data/obs/{loc_id}/recent"
        params = {
            "back": str(days_back),
            "maxResults": str(max_results),
        }
        return self._fetch(path, params)

    def species_info(self, species_code: str) -> dict:
        """Get species information by eBird species code."""
        path = f"/ref/taxonomy/ebird/{species_code}"
        return self._fetch(path)

    def geo_recent(
        self,
        lat: float,
        lng: float,
        dist_km: int = 10,
        days_back: int = 14,
        max_results: int = 50,
    ) -> list[dict]:
        """Recent observations near a geographic point."""
        path = "/data/obs/geo/recent"
        params = {
            "lat": str(lat),
            "lng": str(lng),
            "dist": str(dist_km),
            "back": str(days_back),
            "maxResults": str(max_results),
        }
        return self._fetch(path, params)

    def geo_notable(
        self,
        lat: float,
        lng: float,
        dist_km: int = 10,
        days_back: int = 14,
        max_results: int = 30,
    ) -> list[dict]:
        """Notable observations near a geographic point."""
        path = "/data/obs/geo/recent/notable"
        params = {
            "lat": str(lat),
            "lng": str(lng),
            "dist": str(dist_km),
            "back": str(days_back),
            "maxResults": str(max_results),
        }
        return self._fetch(path, params)

    # ── formatting helpers ───────────────────────────────────

    @staticmethod
    def format_observation(obs: dict, show_location: bool = True) -> str:
        """Format a single observation record for display."""
        com = obs.get("comName", obs.get("speciesCode", "?"))
        sci = obs.get("sciName", "")
        loc = obs.get("locName", "?")
        dt = obs.get("obsDt", "?")
        cnt = obs.get("howMany", "?")
        notable = " ★" if obs.get("obsReviewed", False) else ""

        parts = [f"  {com}"]
        if sci:
            parts[0] += f" ({sci})"
        if show_location:
            parts.append(f" @ {loc}")
        parts.append(f" [{dt}]")
        parts.append(f" x{cnt}{notable}")
        return " | ".join(parts)

    @staticmethod
    def format_notable(obs: dict) -> str:
        """Format a notable observation with emphasis."""
        com = obs.get("comName", obs.get("speciesCode", "?"))
        sci = obs.get("sciName", "")
        loc = obs.get("locName", "?")
        dt = obs.get("obsDt", "?")
        cnt = obs.get("howMany", "?")
        return f"  ★ {com} ({sci}) — {loc} [{dt}] ×{cnt}"
