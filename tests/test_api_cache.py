from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
import requests
from cachetools import TTLCache

from matchplay_score import matchplay_api as api


@pytest.fixture(autouse=True)
def clean_cache(monkeypatch):
    api._cache.clear()
    monkeypatch.setattr(api, "_next_request", 0)
    monkeypatch.setattr(api, "_cooldown_until", 0)
    yield
    api._cache.clear()


def test_concurrent_readers_share_one_request(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = [{"playerId": 1, "position": 1, "points": 6}]
    get = Mock(return_value=response)
    monkeypatch.setattr(api._session, "get", get)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(api.get_matchplay_standings, [123] * 8))
    assert get.call_count == 1
    results[0][0]["points"] = 999
    assert results[1][0]["points"] == 6


def test_rate_limit_respects_retry_after_and_blocks_other_reads(monkeypatch):
    response = Mock(status_code=429, headers={"Retry-After": "120"})
    response.raise_for_status.side_effect = requests.HTTPError("429")
    get = Mock(return_value=response)
    monkeypatch.setattr(api._session, "get", get)
    with pytest.raises(requests.HTTPError):
        api.get_matchplay_standings(123)
    with pytest.raises(requests.HTTPError, match="cooldown"):
        api.get_cards(123)
    assert get.call_count == 1
    assert api._cooldown_until > api.monotonic() + 110


def test_failed_response_is_not_cached(monkeypatch):
    response = Mock(status_code=500)
    response.raise_for_status.side_effect = requests.HTTPError("500")
    monkeypatch.setattr(api._session, "get", Mock(return_value=response))
    with pytest.raises(requests.HTTPError):
        api.get_matchplay_standings(123)
    assert len(api._cache) == 0


def test_pagination_cannot_send_requests_to_another_host():
    with pytest.raises(ValueError, match="origin"):
        api.get_paginated_data("https://example.com/cards")


def test_cache_expires_after_sixty_seconds(monkeypatch):
    clock = [0]
    monkeypatch.setattr(
        api, "_cache", TTLCache(maxsize=256, ttl=60, timer=lambda: clock[0])
    )
    monkeypatch.setattr(api, "monotonic", lambda: clock[0])
    response = Mock(status_code=200)
    response.json.return_value = []
    get = Mock(return_value=response)
    monkeypatch.setattr(api._session, "get", get)
    api.get_matchplay_standings(123)
    clock[0] = 59
    api.get_matchplay_standings(123)
    assert get.call_count == 1
    clock[0] = 61
    api.get_matchplay_standings(123)
    assert get.call_count == 2
