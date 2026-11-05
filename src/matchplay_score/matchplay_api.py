"""Shared, rate-limited Match Play reads for snapshot builds and local serving."""

from copy import deepcopy
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from threading import RLock
from time import monotonic, sleep
from urllib.parse import urlsplit

import requests
from cachetools import TTLCache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_ORIGIN = "https://api.matchplay.events"
_cache = TTLCache(maxsize=256, ttl=60)
_lock = RLock()
_next_request = 0.0
_cooldown_until = 0.0
_session = requests.Session()
_session.headers.update(
    {"User-Agent": "ScoreHigh/1.0 (+https://github.com/AshodinVenteal/scorehigh)"}
)
# Rate limits are handled below instead of immediately retrying them.
_session.mount(
    API_ORIGIN,
    HTTPAdapter(
        max_retries=Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[502, 503, 504],
            allowed_methods=["GET"],
            respect_retry_after_header=False,
        )
    ),
)


def _request_json(url):
    global _next_request, _cooldown_until
    if (
        urlsplit(url).netloc != "api.matchplay.events"
        or urlsplit(url).scheme != "https"
    ):
        raise ValueError("Unexpected Match Play pagination origin")
    # The lock covers cache lookup and fetch: simultaneous viewers share one read.
    with _lock:
        if url in _cache:
            return deepcopy(_cache[url])
        now = monotonic()
        if now < _cooldown_until:
            raise requests.HTTPError("Match Play rate-limit cooldown is active")
        delay = _next_request - now
        if delay > 0:
            sleep(delay)
        _next_request = monotonic() + 1
        try:
            response = _session.get(url, timeout=(5, 15))
        except requests.RequestException:
            _cooldown_until = monotonic() + 60
            raise
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "60")
            try:
                seconds = float(retry_after)
            except ValueError:
                try:
                    seconds = (
                        parsedate_to_datetime(retry_after) - datetime.now(UTC)
                    ).total_seconds()
                except TypeError, ValueError, OverflowError:
                    seconds = 60
            _cooldown_until = monotonic() + max(60, seconds)
        try:
            response.raise_for_status()
        except requests.RequestException:
            _cooldown_until = max(_cooldown_until, monotonic() + 60)
            raise
        result = response.json()
        _cache[url] = result
        return deepcopy(result)


def get_tournament_data_cached(tournament_id: int) -> dict:
    return get_tournament_data(tournament_id)


def get_tournament_data(tournament_id: int) -> dict:
    return _request_json(
        f"{API_ORIGIN}/api/tournaments/{tournament_id}?includeArenas=true&includePlayers=true"
    )["data"]


def get_matchplay_standings(tournament_id: int) -> list[dict]:
    payload = _request_json(f"{API_ORIGIN}/api/tournaments/{tournament_id}/standings")
    return payload if isinstance(payload, list) else payload["data"]


def get_cards(tournament_id: int) -> list[dict]:
    return get_paginated_data(f"{API_ORIGIN}/api/tournaments/{tournament_id}/cards")


def get_paginated_data(url: str) -> list[dict]:
    items = []
    visited = set()
    while url:
        if url in visited:
            raise ValueError("Repeated Match Play pagination URL")
        visited.add(url)
        payload = _request_json(url)
        items.extend(payload["data"])
        url = payload["links"]["next"]
    return items
