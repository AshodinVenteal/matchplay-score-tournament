from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
import requests

from matchplay_score import matchplay_api as api


def response(payload, status=200, headers=None):
    result = Mock(status_code=status, headers=headers or {})
    result.json.return_value = payload
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError(str(status))
    return result


def page(items, next_url=None):
    return {"data": items, "links": {"next": next_url}}


def test_concurrent_readers_share_one_complete_card_fetch(monkeypatch):
    get = Mock(return_value=response(page([{"playerId": 1}])))
    monkeypatch.setattr(api._session, "get", get)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(api.get_cards, [123] * 8))
    assert get.call_count == 1
    results[0][0]["playerId"] = 999
    assert results[1][0]["playerId"] == 1


def test_stale_cards_survive_rate_limit_and_later_pages_are_atomic(monkeypatch):
    clock = [1000]
    monkeypatch.setattr(api, "time", lambda: clock[0])
    get = Mock(return_value=response(page([{"playerId": 1}])))
    monkeypatch.setattr(api._session, "get", get)
    assert api.get_cards(123) == [{"playerId": 1}]
    clock[0] += 121
    get.side_effect = [
        response(page([{"playerId": 2}], api.API_ORIGIN + "/api/page/2")),
        response({}, 429, {"Retry-After": "120"}),
    ]
    monkeypatch.setattr(api, "sleep", lambda seconds: None)
    assert api.get_cards(123) == [{"playerId": 1}]
    calls = get.call_count
    assert api.get_cards(123) == [{"playerId": 1}]
    with pytest.raises(requests.HTTPError, match="cooldown"):
        api.get_tournament_data(999)
    assert get.call_count == calls
    updated, stale = api.snapshot_status(123)
    assert updated == datetime.fromtimestamp(1000, UTC).isoformat()
    assert stale


def test_cache_survives_a_new_python_process(monkeypatch):
    import os
    import subprocess
    import sys

    get = Mock(return_value=response(page([{"playerId": 1}])))
    monkeypatch.setattr(api._session, "get", get)
    api.get_cards(123)
    script = "from matchplay_score import matchplay_api as a; a._session.get = lambda *x, **k: (_ for _ in ()).throw(AssertionError('Network call')); assert a.get_cards(123) == [{'playerId': 1}]"
    subprocess.run([sys.executable, "-c", script], env=os.environ.copy(), check=True)
    assert get.call_count == 1


def test_failed_response_is_not_saved_as_a_snapshot(monkeypatch):
    get = Mock(return_value=response({}, 500))
    monkeypatch.setattr(api._session, "get", get)
    with pytest.raises(requests.HTTPError):
        api.get_cards(123)
    with api._store() as connection:
        assert connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0] == 0
    with pytest.raises(requests.HTTPError, match="cooldown"):
        api.get_cards(123)
    assert get.call_count == 1


def test_pagination_cannot_send_requests_to_another_host(monkeypatch):
    get = Mock()
    monkeypatch.setattr(api._session, "get", get)
    with pytest.raises(ValueError, match="origin"):
        api.get_paginated_data("https://example.com/cards")
    get.assert_not_called()


def test_live_snapshot_reused_until_refresh_due(monkeypatch):
    clock = [1000]
    monkeypatch.setattr(api, "time", lambda: clock[0])
    get = Mock(return_value=response(page([])))
    monkeypatch.setattr(api._session, "get", get)
    api.get_cards(123)
    clock[0] += 119
    api.get_cards(123)
    assert get.call_count == 1
    clock[0] += 2
    api.get_cards(123)
    assert get.call_count == 2


@pytest.mark.parametrize("header", ["nan", "inf", "bad date", None, "-1"])
def test_malformed_retry_after_uses_a_finite_cooldown(header):
    assert api._retry_seconds(header) == 60


def test_retry_after_http_date(monkeypatch):
    monkeypatch.setattr(api, "time", lambda: 0)
    assert api._retry_seconds("Thu, 01 Jan 1970 00:02:00 GMT") == 120


def test_repeated_failures_back_off_across_expired_cooldowns(monkeypatch):
    clock = [1000]
    monkeypatch.setattr(api, "time", lambda: clock[0])
    get = Mock(return_value=response({}, 429))
    monkeypatch.setattr(api._session, "get", get)
    for delay in [60, 120, 240]:
        with pytest.raises(requests.HTTPError):
            api.get_cards(123)
        with api._store() as connection:
            assert api._state(connection, "api_cooldown") == clock[0] + delay
        clock[0] += delay + 1
    assert get.call_count == 3


def test_vercel_uses_shared_published_feed_without_disk_or_matchplay(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("SCOREHIGH_SNAPSHOT_URL", "https://scores.example")
    payload = {
        "tournament_id": 123,
        "updated_at": datetime.now(UTC).isoformat(),
        "tournament": {"players": []},
        "cards": [],
    }
    get = Mock(return_value=response(payload))
    monkeypatch.setattr(api._session, "get", get)

    def disk_access():
        raise AssertionError("Vercel should not use disk storage")

    monkeypatch.setattr(api, "_store", disk_access)
    assert api.get_tournament_data(123) == {"players": []}
    assert api.get_cards(123) == []
    assert api.snapshot_status(123) == (payload["updated_at"], False)
    assert get.call_count == 1
    assert get.call_args.args[0] == "https://scores.example/data/tournaments/123.json"


def test_vercel_without_feed_never_falls_back_to_matchplay(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    get = Mock()
    monkeypatch.setattr(api._session, "get", get)
    with pytest.raises(requests.HTTPError, match="SCOREHIGH_SNAPSHOT_URL"):
        api.get_cards(123)
    get.assert_not_called()


def test_feed_outage_uses_cached_scores_and_original_timestamp(monkeypatch):
    monkeypatch.setenv("SCOREHIGH_SNAPSHOT_URL", "https://scores.example")
    clock = [1000]
    monkeypatch.setattr(api, "time", lambda: clock[0])
    payload = {
        "tournament_id": 123,
        "updated_at": datetime.fromtimestamp(1000, UTC).isoformat(),
        "tournament": {"players": []},
        "cards": [],
    }
    get = Mock(side_effect=[response(payload), requests.Timeout()])
    monkeypatch.setattr(api._session, "get", get)
    assert api.get_cards(123) == []
    clock[0] += 61
    assert api.get_cards(123) == []
    assert api.snapshot_status(123) == (payload["updated_at"], True)
    assert api.get_cards(123) == []
    assert get.call_count == 2
