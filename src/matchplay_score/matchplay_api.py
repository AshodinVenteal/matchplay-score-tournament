"""Persistent Match Play snapshots, shared pacing, and stale-on-error reads."""

import json
import math
import os
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from tempfile import gettempdir
from threading import RLock
from time import sleep, time
from urllib.parse import urlsplit

import requests

API_ORIGIN = "https://api.matchplay.events"
LIVE_TTL = 120
ROSTER_TTL = 300
STALE_TTL = 86400
_session = requests.Session()
_session.headers.update({"User-Agent": "ScoreHigh/1.1", "Accept": "application/json"})
_feed_cache = {}
_feed_lock = RLock()
_feed_retry_at = 0.0
_batch = ContextVar("scorehigh_snapshot_batch", default=None)


@contextmanager
def snapshot_batch():
    """Freeze input data for one export, even if rendering exceeds a cache TTL."""
    token = _batch.set({})
    try:
        yield
    finally:
        _batch.reset(token)


def _batch_read(key, loader):
    batch = _batch.get()
    if batch is None:
        return loader()
    if key not in batch:
        batch[key] = loader()
    return deepcopy(batch[key])


def cache_path():
    return Path(
        os.environ.get(
            "SCOREHIGH_CACHE_PATH",
            Path(gettempdir()) / "scorehigh" / "matchplay.sqlite3",
        )
    )


@contextmanager
def _store():
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    try:
        # The transaction also serializes concurrent workers using this file.
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS snapshots (key TEXT PRIMARY KEY, payload TEXT NOT NULL, updated REAL NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value REAL NOT NULL)"
        )
        yield connection
    finally:
        # Save cooldowns even when the upstream request raised an exception.
        connection.commit()
        connection.close()


def _state(connection, key):
    row = connection.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
    return row[0] if row else 0


def _set_state(connection, key, value):
    connection.execute("INSERT OR REPLACE INTO state VALUES (?, ?)", (key, value))


def _read(connection, key, loader, ttl=LIVE_TTL):
    row = connection.execute(
        "SELECT payload, updated FROM snapshots WHERE key = ?", (key,)
    ).fetchone()
    if row and time() - row[1] < ttl:
        return json.loads(row[0])
    try:
        value = loader()
    except requests.RequestException, ValueError:
        if row and time() - row[1] < STALE_TTL:
            return json.loads(row[0])
        raise
    connection.execute(
        "INSERT OR REPLACE INTO snapshots VALUES (?, ?, ?)",
        (key, json.dumps(value), time()),
    )
    return value


def _retry_seconds(value):
    try:
        seconds = float(value)
        if math.isfinite(seconds):
            return max(60, seconds)
    except TypeError, ValueError:
        pass
    try:
        date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            date = date.replace(tzinfo=UTC)
        return max(60, date.timestamp() - time())
    except TypeError, ValueError, OverflowError:
        return 60


def _fetch_json(connection, url):
    if (
        urlsplit(url).netloc != "api.matchplay.events"
        or urlsplit(url).scheme != "https"
    ):
        raise ValueError("Unexpected Match Play pagination origin")
    scope = "api"
    if time() < _state(connection, scope + "_cooldown"):
        raise requests.HTTPError("Match Play rate-limit cooldown is active")
    delay = _state(connection, scope + "_next") - time()
    if delay > 0:
        sleep(delay)
    # No automatic HTTP retries: each attempt must go through this shared gate.
    _set_state(connection, scope + "_next", time() + 1)
    try:
        response = _session.get(url, timeout=(5, 15))
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException, ValueError:
        failures = min(6, _state(connection, scope + "_failures") + 1)
        delay = min(1800, 60 * 2 ** (failures - 1))
        if "response" in locals() and response.status_code == 429:
            delay = max(delay, _retry_seconds(response.headers.get("Retry-After")))
        _set_state(connection, scope + "_failures", failures)
        _set_state(connection, scope + "_cooldown", time() + delay)
        raise
    # A successful metadata/page read must not reset a repeatedly failing card fetch.
    return payload


def _request_json(url, ttl=LIVE_TTL):
    if (
        urlsplit(url).netloc != "api.matchplay.events"
        or urlsplit(url).scheme != "https"
    ):
        raise ValueError("Unexpected Match Play pagination origin")
    with _store() as connection:
        return _read(connection, url, lambda: _fetch_json(connection, url), ttl)


def _published_snapshot(tournament_id):
    global _feed_retry_at
    base = os.environ.get("SCOREHIGH_SNAPSHOT_URL", "").rstrip("/")
    if not base:
        if os.environ.get("VERCEL"):
            raise requests.HTTPError(
                "Set SCOREHIGH_SNAPSHOT_URL for Vercel; direct Match Play reads are disabled"
            )
        return None
    if urlsplit(base).scheme != "https":
        raise ValueError("Snapshot URL must use HTTPS")

    url = f"{base}/data/tournaments/{tournament_id}.json"
    # Vercel workers read an already-published feed. No filesystem or Match Play calls.
    with _feed_lock:
        cached = _feed_cache.get(url)
        if cached and time() - cached[0] < 60:
            return json.loads(cached[1])
        try:
            if time() < _feed_retry_at:
                raise requests.HTTPError("Published snapshot retry cooldown is active")
            response = _session.get(url, timeout=(5, 15))
            response.raise_for_status()
            payload = response.json()
            if (
                payload.get("tournament_id") != tournament_id
                or not isinstance(payload.get("cards"), list)
                or not isinstance(payload.get("tournament"), dict)
            ):
                raise ValueError("Invalid published tournament snapshot")
            if (
                time() - datetime.fromisoformat(payload["updated_at"]).timestamp()
                > STALE_TTL
            ):
                raise ValueError("Published tournament snapshot is over 24 hours old")
        except (requests.RequestException, ValueError, KeyError, TypeError) as error:
            _feed_retry_at = time() + 60
            if (
                cached
                and time()
                - datetime.fromisoformat(
                    json.loads(cached[1])["updated_at"]
                ).timestamp()
                < STALE_TTL
            ):
                return json.loads(cached[1])
            raise requests.HTTPError(
                "Published scores are temporarily unavailable"
            ) from error
        _feed_cache[url] = (time(), json.dumps(payload))
        _feed_retry_at = 0
        return payload


def get_tournament_data_cached(tournament_id: int) -> dict:
    return get_tournament_data(tournament_id)


def get_tournament_data(tournament_id: int) -> dict:
    return _batch_read(
        ("tournament", tournament_id), lambda: _get_tournament_data(tournament_id)
    )


def _get_tournament_data(tournament_id):
    published = _published_snapshot(tournament_id)
    if published is not None:
        return published["tournament"]
    return _request_json(
        f"{API_ORIGIN}/api/tournaments/{tournament_id}?includeArenas=true&includePlayers=true",
        ROSTER_TTL,
    )["data"]


def get_cards(tournament_id: int) -> list[dict]:
    return _batch_read(("cards", tournament_id), lambda: _get_cards(tournament_id))


def _get_cards(tournament_id):
    published = _published_snapshot(tournament_id)
    if published is not None:
        return published["cards"]
    # Cache the entire list atomically. A failed later page cannot replace it.
    with _store() as connection:

        def load():
            cards = _paginate(
                connection, f"{API_ORIGIN}/api/tournaments/{tournament_id}/cards"
            )
            _set_state(connection, "api_failures", 0)
            return cards

        return _read(connection, f"cards:{tournament_id}", load)


def _paginate(connection, url):
    items = []
    visited = set()
    while url:
        if url in visited:
            raise ValueError("Repeated Match Play pagination URL")
        visited.add(url)
        payload = _fetch_json(connection, url)
        items.extend(payload["data"])
        url = payload["links"]["next"]
    return items


def get_paginated_data(url: str) -> list[dict]:
    with _store() as connection:
        return _read(connection, url, lambda: _paginate(connection, url))


def snapshot_status(tournament_id):
    """Return the time scores were fetched, not the time the page was rendered."""
    base = os.environ.get("SCOREHIGH_SNAPSHOT_URL", "").rstrip("/")
    if base or os.environ.get("VERCEL"):
        cached = _feed_cache.get(f"{base}/data/tournaments/{tournament_id}.json")
        if not cached:
            return None, False
        payload = json.loads(cached[1])
        return payload[
            "updated_at"
        ], time() < _feed_retry_at or time() - datetime.fromisoformat(
            payload["updated_at"]
        ).timestamp() > 600
    with _store() as connection:
        key = f"cards:{tournament_id}"
        row = connection.execute(
            "SELECT payload, updated FROM snapshots WHERE key = ?", (key,)
        ).fetchone()
        if not row:
            return None, False
        return datetime.fromtimestamp(row[1], UTC).isoformat(), time() < _state(
            connection, "api_cooldown"
        )
