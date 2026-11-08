from unittest.mock import patch

from matchplay_score import ranking
from matchplay_score.tournament import Card, SinglePlayerGame


def games(eras):
    return [
        SinglePlayerGame(i, f"Game {i}", "Test Player", 1000, 1, era)
        for i, era in enumerate(eras)
    ]


def test_invalid_only_means_too_many_games_in_a_category():
    card = Card(
        "Test Player",
        games(["old", "old", "mid", "mid", "mid", "new"]),
        status="completed",
    )
    assert not card.is_valid()
    assert card.invalid_reasons() == ["3 Mid games; the limit is 2."]
    assert card.history_status() == "Invalid"
    partial = Card("Test Player", games(["old", "mid"]))
    assert partial.is_valid()
    assert partial.history_status() == "Card in progress"


def test_standings_can_keep_invalid_only_players_without_replacing_valid_cards():
    valid = Card("Alice", games(["old", "mid"]), card_id=1)
    invalid_alice = Card("Alice", games(["mid"] * 3), card_id=2, status="completed")
    invalid_bob = Card("Bob", games(["old"] * 3), card_id=3, status="completed")
    newer_bob = Card("Bob", games(["new"] * 3), card_id=4, status="completed")
    voided = Card("Carol", games(["old"]), card_id=5, voided=True)
    entries = [invalid_bob, invalid_alice, valid, newer_bob, voided]
    tournament = {"players": [], "arenas": []}
    for include_invalid in (False, True):
        with (
            patch.object(
                ranking, "get_tournament_data_cached", return_value=tournament
            ) as roster,
            patch.object(
                ranking, "get_cards", return_value=[{}] * len(entries)
            ) as cards,
            patch.object(ranking, "parse_card", side_effect=entries),
        ):
            result = ranking.best_cards(1, include_invalid=include_invalid)
        assert result == ([valid, newer_bob, voided] if include_invalid else [valid])
        roster.assert_called_once()
        cards.assert_called_once()


def test_newer_card_does_not_void_an_older_incomplete_card():
    tournament = {"players": [{"playerId": 1, "name": "Test Player"}], "arenas": []}
    old = Card("Test Player", games(["old"]), card_id=1, created_at="2026-11-01")
    old.games[0].score = 1000000
    new = Card("Test Player", games(["new"]), card_id=2, created_at="2026-11-02")
    with (
        patch.object(ranking, "get_tournament_data_cached", return_value=tournament),
        patch.object(ranking, "get_cards", return_value=[{}, {}]),
        patch.object(ranking, "parse_card", side_effect=[new, old]),
    ):
        cards = ranking.player_cards(1, "Test Player")
    assert cards[0] is new
    assert old.history_status() == "Card in progress"
    assert not old.voided
    assert new.history_status() == "Card in progress"
    assert new.is_latest
    assert not old.is_latest


def test_completed_invalid_card_not_voided():
    card = Card(
        "Test Player",
        games(["old", "old", "mid", "mid", "mid", "new"]),
        status="completed",
    )
    assert card.history_status() == "Invalid"


def test_matchplay_voided_card_stays_in_history_but_not_standings():
    tournament = {
        "players": [{"playerId": 1, "name": "Test Player"}],
        "arenas": [
            {"arenaId": 1, "name": "Stars", "tournamentArena": {"status": "active"}}
        ],
    }
    valid = {
        "cardId": 1,
        "playerId": 1,
        "voided": False,
        "singlePlayerGames": [
            {"arenaId": 1, "playerId": 1, "score": 1000, "voided": False},
        ],
    }
    voided = {
        "cardId": 2,
        "playerId": 1,
        "voided": True,
        "singlePlayerGames": [
            {"arenaId": 1, "playerId": 1, "score": 9999999, "voided": True},
        ],
    }
    with (
        patch.object(ranking, "get_tournament_data_cached", return_value=tournament),
        patch.object(ranking, "get_cards", return_value=[valid, voided]),
    ):
        standings = ranking.best_cards(1)
        history = ranking.player_cards(1, "Test Player")
    assert len(standings) == 1
    assert standings[0].card_id == 1
    assert len(history) == 2
    assert history[0].history_status() == "Voided"
    assert len(history[0].games) == 1
    assert history[0].computed_score() > standings[0].computed_score()


def test_last_added_game_uses_creation_time_not_score_or_list_order():
    old, recent = games(["old", "mid"])
    old.created_at = "2026-11-07T13:00:00+01:00"
    old.game_id = 100
    old.score = 99999999
    recent.created_at = "2026-11-07T12:05:00Z"
    recent.game_id = 99
    card = Card("Test Player", [recent, old])
    assert card.last_added_game() is recent


def test_last_added_game_falls_back_to_id_without_inventing_a_time():
    first, last = games(["old", "new"])
    first.game_id = 10
    last.game_id = 11
    card = Card("Test Player", [last, first])
    assert card.last_added_game() is last
    assert last.created_at == ""
    assert Card("Test Player", games(["old"])).last_added_game() is None
