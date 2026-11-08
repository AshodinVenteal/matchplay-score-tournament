"""Short-lived live reads, shared Vercel snapshots, and stale-on-error recovery."""

import math
import os
from copy import deepcopy
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from loguru import logger
from threading import RLock
from time import time
from urllib.parse import urlsplit

import requests
from vercel.cache import RuntimeCacheError
from vercel.functions import RuntimeCache

API_ORIGIN = "https://api.matchplay.events"
LIVE_TTL = 15
STALE_TTL = 3600
_cache = {}
_lock = RLock()
_cooldown_until = 0.0
_failures = 0
_runtime = None
_session = requests.Session()
_session.headers.update({"User-Agent": "ScoreHigh/1.1", "Accept": "application/json"})


def _shared() -> RuntimeCache | None:
    global _runtime
    if not os.environ.get("VERCEL"):
        return None
    if _runtime is None:

        namespace = "scorehigh-live-v2-" + os.environ.get(
            "VERCEL_PROJECT_ID", "default"
        )
        _runtime = RuntimeCache(namespace=namespace, strict=True)
    return _runtime


def _read(key: str) -> dict:
    shared = _shared()
    try:
        value = shared.get(key) if shared else None
    except (RuntimeCacheError, OSError, ValueError) as error:
        # A broken shared cache must not fan out into uncoordinated API reads.
        logger.warning("Score cache unavailable: %s", error)
        value = _cache.get(key)
        if value is None:
            raise requests.RequestException(
                "Score cache temporarily unavailable"
            ) from error
    if value is not None:
        _cache[key] = value
    return deepcopy(value if value is not None else _cache.get(key))


def _write(key: str, value: dict):
    _cache[key] = deepcopy(value)
    shared = _shared()
    if shared:
        try:
            shared.set(key, value, {"ttl": STALE_TTL})
        except (RuntimeCacheError, OSError, ValueError) as error:
            logger.warning("Unable to save shared score cache: %s", error)


def retry_seconds(value):
    try:
        seconds = float(value)
        if math.isfinite(seconds):
            return max(60, seconds)
    except TypeError, ValueError:
        pass
    try:
        date = parsedate_to_datetime(value)
        return max(60, date.replace(tzinfo=date.tzinfo or UTC).timestamp() - time())
    except TypeError, ValueError, OverflowError:
        return 60


def _fetch(url):
    global _cooldown_until, _failures
    if (
        urlsplit(url).scheme != "https"
        or urlsplit(url).netloc != "api.matchplay.events"
    ):
        raise ValueError("Unexpected Match Play pagination origin")
    state = _read("rate-state") or {}
    _cooldown_until = max(_cooldown_until, state.get("cooldown", 0))
    if time() < _cooldown_until:
        raise requests.HTTPError("Match Play rate-limit cooldown is active")
    response = None
    try:
        # Cache refreshes fetch the roster and cards without artificial delays.
        # Actual rate-limit responses establish a cooldown for later refreshes.
        response = _session.get(url, timeout=(5, 15))
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as error:
        _failures = min(6, max(_failures, state.get("failures", 0)) + 1)
        delay = min(900, 60 * 2 ** (_failures - 1))
        if response is not None and response.status_code == 429:
            delay = max(delay, retry_seconds(response.headers.get("Retry-After")))
        logger.warning(
            "Match Play request failed: path=%s status=%s error=%s cooldown_seconds=%s",
            urlsplit(url).path,
            response.status_code if response is not None else "unavailable",
            type(error).__name__,
            delay,
        )
        _cooldown_until = time() + delay
        _write(
            "rate-state",
            {"cooldown": _cooldown_until, "failures": _failures},
        )
        raise


def get_cached_tournament_snapshot(tournament_id):
    """Read an existing snapshot without refreshing or contacting Match Play."""
    saved = _read(f"tournament:{tournament_id}")
    if saved and time() - saved["fetched_at"] < STALE_TTL:
        return saved
    return None


def get_tournament_snapshot(tournament_id):
    """Share one roster and complete card list between every page for this event."""
    global _failures
    key = f"tournament:{tournament_id}"
    saved = _read(key)
    if saved and time() - saved["fetched_at"] < LIVE_TTL:
        return saved
    usable = saved and time() - saved["fetched_at"] < STALE_TTL
    if usable:
        # Another refresh must not make viewers wait for cached scores.
        if not _lock.acquire(blocking=False):
            saved["stale"] = True
            return saved
    else:
        # With no usable scores yet, share the initial network fetch.
        _lock.acquire()
    try:
        # A refresh may have completed since the first cache lookup.
        saved = _read(key)
        if saved and time() - saved["fetched_at"] < LIVE_TTL:
            return saved
        try:
            tournament = _fetch(
                f"{API_ORIGIN}/api/tournaments/{tournament_id}?includeArenas=true&includePlayers=true"
            )["data"]
            cards = get_paginated_data(
                f"{API_ORIGIN}/api/tournaments/{tournament_id}/cards"
            )
        except (requests.RequestException, ValueError) as e:
            logger.warning(f"API error in get_tournament_snapshot: {e!r}")
            if saved and time() - saved["fetched_at"] < STALE_TTL:
                saved["stale"] = True
                return saved
            raise
        saved = {
            "tournament": tournament,
            "cards": cards,
            "fetched_at": time(),
            "stale": False,
        }
        _write(key, saved)
        _failures = 0
        return deepcopy(saved)
    finally:
        _lock.release()


def get_tournament_data_cached(tournament_id: int):
    return get_tournament_data(tournament_id)


def get_tournament_data(tournament_id: int):
    return get_tournament_snapshot(tournament_id)["tournament"]


def get_cards(tournament_id: int):
    return get_tournament_snapshot(tournament_id)["cards"]


def get_paginated_data(url: str) -> list[dict]:
    items = []
    visited = set()
    while url:
        if url in visited:
            raise ValueError("Repeated Match Play pagination URL")
        visited.add(url)
        payload = _fetch(url)
        items.extend(payload["data"])
        url = payload["links"]["next"]
    return items


def snapshot_status(tournament_id: int) -> tuple[str | None, bool]:
    saved = _read(f"tournament:{tournament_id}")
    if not saved:
        return None, False
    state = _read("rate-state") or {}
    stale = (
        time() < state.get("cooldown", 0) or time() - saved["fetched_at"] >= LIVE_TTL
    )
    return datetime.fromtimestamp(saved["fetched_at"], UTC).isoformat(), stale
