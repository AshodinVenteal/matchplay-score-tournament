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


def test_abandoned_uses_creation_order_not_score_order():
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
    assert cards[0] is old
    assert old.history_status() == "Abandoned"
    assert new.history_status() == "Card in progress"


def test_completed_invalid_card_not_abandoned():
    card = Card(
        "Test Player",
        games(["old", "old", "mid", "mid", "mid", "new"]),
        status="completed",
    )
    assert card.history_status() == "Invalid"
