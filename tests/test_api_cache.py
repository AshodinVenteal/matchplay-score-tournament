from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from unittest.mock import Mock

import pytest
import requests

from matchplay_score import matchplay_api as api


@pytest.fixture
def upstream(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(api, "time", lambda: clock[0])
    monkeypatch.setattr(
        api, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds)
    )
    roster = Mock(status_code=200)
    roster.json.return_value = {"data": {"players": [], "arenas": []}}
    cards = Mock(status_code=200)
    cards.json.return_value = {"data": [{"cardId": 1}], "links": {"next": None}}
    get = Mock(
        side_effect=lambda url, **kwargs: cards if url.endswith("/cards") else roster
    )
    monkeypatch.setattr(api._session, "get", get)
    return clock, get, cards


def test_viewers_share_one_roster_and_card_fetch(upstream):
    _, get, _ = upstream
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(api.get_cards, [123] * 8))
    assert get.call_count == 2
    results[0][0]["cardId"] = 99
    assert results[1][0]["cardId"] == 1
    assert api.get_tournament_data(123) == {"players": [], "arenas": []}
    assert get.call_count == 2


def test_new_scores_available_after_fifteen_seconds(upstream):
    clock, get, cards = upstream
    assert api.get_cards(123) == [{"cardId": 1}]
    clock[0] += 14
    api.get_cards(123)
    assert get.call_count == 2
    cards.json.return_value["data"] = [{"cardId": 2}]
    clock[0] += 2
    assert api.get_cards(123) == [{"cardId": 2}]
    assert get.call_count == 4


def test_rate_limit_preserves_cards_and_timestamp(upstream):
    clock, get, _ = upstream
    api.get_cards(123)
    original = api.snapshot_status(123)[0]
    clock[0] += 16
    response = Mock(status_code=429, headers={"Retry-After": "120"})
    response.raise_for_status.side_effect = requests.HTTPError("429")
    get.side_effect = lambda *args, **kwargs: response
    assert api.get_cards(123) == [{"cardId": 1}]
    assert api.snapshot_status(123) == (original, True)
    assert api.get_cards(123) == [{"cardId": 1}]
    assert get.call_count == 3
    with pytest.raises(requests.HTTPError, match="cooldown"):
        api.get_cards(999)
    assert get.call_count == 3


def test_failed_second_card_page_keeps_complete_previous_list(upstream):
    clock, get, _ = upstream
    api.get_cards(123)
    clock[0] += 16
    first = Mock(status_code=200)
    first.json.return_value = {
        "data": [{"cardId": 2}],
        "links": {"next": api.API_ORIGIN + "/api/page/2"},
    }
    get.side_effect = [
        Mock(json=lambda: {"data": {"players": [], "arenas": []}}),
        first,
        requests.Timeout(),
    ]
    assert api.get_cards(123) == [{"cardId": 1}]


def test_vercel_workers_reuse_shared_runtime_cache(upstream, monkeypatch):
    _, get, _ = upstream

    class Shared:
        def __init__(self):
            self.data = {}

        def get(self, key):
            return deepcopy(self.data.get(key))

        def set(self, key, value, options):
            self.data[key] = deepcopy(value)

    shared = Shared()
    monkeypatch.setattr(api, "_shared", lambda: shared)
    api.get_cards(123)
    api._cache.clear()
    assert api.get_cards(123) == [{"cardId": 1}]
    assert get.call_count == 2


def test_block_external_pagination(upstream):
    _, get, _ = upstream
    with pytest.raises(ValueError, match="origin"):
        api.get_paginated_data("https://example.com/cards")
    assert get.call_count == 0


@pytest.mark.parametrize("value", ["nan", "inf", None, "bad", "-2"])
def test_retry_after_is_finite(value):
    assert api.retry_seconds(value) == 60
