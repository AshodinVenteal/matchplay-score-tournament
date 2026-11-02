from matchplay_score.matchplay_api import get_tournament_data, get_cards
from matchplay_score.tournament import parse_tournament, parse_card, Card


def test_cards():
    tournament_data = get_tournament_data(277028)
    card_data: list[dict] = get_cards(277028)

    tournament = parse_tournament(tournament_data)

    for card_item in card_data:
        card: Card = parse_card(card_item, tournament)
        print(card.player_name, card.computed_score())
        print([(game.game_name, game.computed_score()) for game in card.games])
        assert 0 <= card.computed_score()
