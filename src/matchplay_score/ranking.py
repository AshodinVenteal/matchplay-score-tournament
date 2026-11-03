__package__ = "matchplay_score"
from .tournament import Card, parse_tournament, parse_card, UNKNOWN
from .matchplay_api import get_tournament_data_cached, get_tournament_data, get_cards


def best_cards(tournament_id: int, use_cache: bool = True) -> list[Card]:
    if use_cache:
        tournament_data = get_tournament_data_cached(tournament_id)
    else:
        tournament_data = get_tournament_data(tournament_id)
    card_data: list[dict] = get_cards(tournament_id)

    tournament = parse_tournament(tournament_data)

    cards_by_player: dict[str, Card] = {}
    for card_item in card_data:
        card: Card = parse_card(card_item, tournament)
        if card.is_valid():
            if use_cache and card.player_name == UNKNOWN:
                return best_cards(tournament_id, use_cache=False)

            if card.player_name not in cards_by_player:
                cards_by_player[card.player_name] = card
            elif (
                cards_by_player[card.player_name].computed_score()
                < card.computed_score()
            ):
                cards_by_player[card.player_name] = card

    return sorted(cards_by_player.values(), key=Card.computed_score, reverse=True)


def main():
    from pprint import pprint

    pprint(best_cards(281672))


if __name__ == "__main__":
    main()
