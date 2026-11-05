import pytest

from matchplay_score.matchplay_api import get_cards, get_tournament_data
from matchplay_score.tournament import Card, parse_card, parse_tournament


@pytest.mark.integration
def test_cards():
    tournament_data = get_tournament_data(281672)
    card_data: list[dict] = get_cards(281672)

    tournament = parse_tournament(tournament_data)

    for card_item in card_data:
        card: Card = parse_card(card_item, tournament)
        print(card.player_name, card.computed_score())
        print([(game.game_name, game.computed_score()) for game in card.games])
        assert 0 <= card.computed_score() <= 1_000_000_000
