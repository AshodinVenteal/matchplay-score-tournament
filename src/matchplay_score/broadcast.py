"""Card selection and display options for streaming overlays."""

from flask import request

from .matchplay_api import get_tournament_snapshot
from .tournament import Card, creation_order, parse_card, parse_tournament


def overlay_options():
    mode = request.args.get("mode", "cycle")
    if mode not in {"cycle", "recent", "top"}:
        mode = "cycle"
    count = request.args.get("count", 3 if mode == "top" else 5, type=int)
    seconds = request.args.get("seconds", 12, type=int)
    return {
        "mode": mode,
        "count": max(1, min(10, count)),
        "seconds": max(8, min(60, seconds)),
    }


def last_submission(card):
    return max(
        [creation_order(card.created_at, card.card_id)]
        + [creation_order(game.created_at, game.game_id) for game in card.games]
    )


def select_cards(cards, mode, count):
    eligible = [card for card in cards if card.games and card.is_valid()]
    best = {}
    for card in eligible:
        if card.player_name not in best or (
            card.computed_score() > best[card.player_name].computed_score()
        ):
            best[card.player_name] = card
    standings = sorted(best.values(), key=Card.computed_score, reverse=True)
    ranks = {card.player_name: rank for rank, card in enumerate(standings, 1)}
    selected = (
        standings
        if mode == "top"
        else sorted(eligible, key=last_submission, reverse=True)
    )
    return [(card, ranks[card.player_name]) for card in selected[:count]]


def overlay_entries(cards, mode, count):
    sections = (
        [("recent", count), ("top", min(3, count))]
        if mode == "cycle"
        else [(mode, count)]
    )
    return [
        (card, rank, section)
        for section, limit in sections
        for card, rank in select_cards(cards, section, limit)
    ]


def tournament_cards(tournament_id):
    # Read the same complete snapshot as standings; never fetch per player/card.
    snapshot = get_tournament_snapshot(tournament_id)
    tournament = parse_tournament(snapshot["tournament"])
    return [parse_card(item, tournament) for item in snapshot["cards"]]
