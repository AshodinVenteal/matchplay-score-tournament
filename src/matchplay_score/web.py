from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from importlib.metadata import version
from random import Random

import requests
from flask import Flask, abort, render_template

from .branding import REPOSITORY_DESCRIPTION, SITE_DESCRIPTION, SITE_TITLE
from .matchplay_api import get_matchplay_standings, get_tournament_data_cached
from .ranking import best_cards, player_cards
from .tournament import (
    ARENAS,
    CARD_GAME_LIMIT,
    MAX_PER_ERA,
    Card,
    SinglePlayerGame,
    parse_tournament,
)

app = Flask(__name__)
APP_VERSION = version("matchplay-score")
TOURNAMENT_INFO = {
    281672: "Test Tournament",
    282316: "Score High for Trans Lives",
    282630: "ScoreHigh test run",
}
TOURNAMENT_EMOJI = (
    "🏅",
    "🎖️",
    "🏁",
    "🎯",
    "🎳",
    "🕹️",
    "🎮",
    "🎲",
    "🎪",
    "🎟️",
    "🎰",
    "🏟️",
    "🎊",
    "🎉",
    "🎱",
)


def tournament_matchplay_urls():
    return {
        id: f"https://app.matchplay.events/tournaments/{id}/" for id in TOURNAMENT_INFO
    }


def tournament_icons():
    """Give listed tournaments repeatable random icons, avoiding duplicates."""
    icons = {}
    for tournament_id in sorted(TOURNAMENT_INFO):
        choices = Random(tournament_id).sample(TOURNAMENT_EMOJI, len(TOURNAMENT_EMOJI))
        icons[tournament_id] = next(
            (icon for icon in choices if icon not in icons.values()), choices[0]
        )
    icons[282316] = "🏆"
    return icons


@app.context_processor
def site_context():
    return {
        "tournaments": TOURNAMENT_INFO,
        "max_per_era": MAX_PER_ERA,
        "card_game_limit": CARD_GAME_LIMIT,
        "asset_version": APP_VERSION,
        "site_title": SITE_TITLE,
        "site_description": SITE_DESCRIPTION,
        "repository_description": REPOSITORY_DESCRIPTION,
        "tournament_icons": tournament_icons(),
        "matchplay_urls": tournament_matchplay_urls(),
        "static_snapshot": bool(app.config.get("SNAPSHOT_AT")),
    }


def score_timestamp():
    return app.config.get("SNAPSHOT_AT") or datetime.now(UTC).isoformat()


def tournament_title(tournament_id):
    return TOURNAMENT_INFO.get(tournament_id, f"Tournament {tournament_id}")


@app.template_filter("commafy")
def commafy(value: int) -> str:
    "Apply thousands separator to integers"
    return f"{value:,d}"


@app.template_filter("card_key")
def card_key(card) -> str:
    return sha256(repr(card).encode("utf-8")).hexdigest()[:16]


@app.route("/ranking/<int:tournament_id>")
def render_ranking(tournament_id: int):
    return standings_page(tournament_id)


@app.route("/monitor/<int:tournament_id>")
def render_monitor(tournament_id: int):
    return standings_page(tournament_id, monitor=True)


def standings_page(tournament_id: int, *, monitor: bool = False):
    cards = best_cards(tournament_id, use_cache=True)
    title = tournament_title(tournament_id)
    return render_template(
        "ranking.html",
        cards=cards,
        title=title,
        tournament_id=tournament_id,
        updated_at=score_timestamp(),
        active_tab="standings",
        monitor=monitor,
    )


@app.route("/player/<int:tournament_id>/<path:player_name>")
def render_player(tournament_id: int, player_name: str):
    cards = player_cards(tournament_id, player_name)
    if not cards and "_" in player_name:
        player_name = player_name.replace("_", " ")
        cards = player_cards(tournament_id, player_name)
    if not cards:
        abort(404)
    valid_cards = [card for card in cards if card.is_valid()]
    standings = best_cards(tournament_id, use_cache=True)
    rank = next(
        (i for i, card in enumerate(standings, 1) if card.player_name == player_name),
        None,
    )
    return render_template(
        "player.html",
        cards=cards,
        player_name=player_name,
        best_card=valid_cards[0] if valid_cards else None,
        rank=rank,
        title=tournament_title(tournament_id),
        tournament_id=tournament_id,
        updated_at=score_timestamp(),
        active_tab="standings",
    )


@app.route("/machines/<int:tournament_id>")
def render_machines(tournament_id: int):
    tournament = parse_tournament(get_tournament_data_cached(tournament_id))
    return render_template(
        "machines.html",
        arenas=tournament.arenas_by_id.values(),
        title=tournament_title(tournament_id),
        tournament_id=tournament_id,
        active_tab="machines",
    )


@app.route("/how-it-works/<int:tournament_id>")
def render_how_it_works(tournament_id: int):
    arenas = {arena.short_name: arena for arena in ARENAS}
    scores = {
        "Stars": 280_000,
        "Quicksilver": 340_000,
        "Creature": 120_000_000,
        "Theatre": 700_000_000,
        "Iron Maiden": 360_000_000,
        "Jurassic Park": 120_000_000,
    }
    games = [
        SinglePlayerGame(
            i, name, "Example", score, arenas[name].multiplier, arenas[name].era
        )
        for i, (name, score) in enumerate(scores.items())
    ]
    example = Card("Example", games)
    lower = Card("Example", [replace(games[0], score=100_000), *games[1:]])
    tron = arenas["TRON"]
    invalid = Card(
        "Example",
        [
            *games,
            SinglePlayerGame(
                99, tron.short_name, "Example", 25_000_000, tron.multiplier, tron.era
            ),
        ],
    )
    return render_template(
        "how_it_works.html",
        title=tournament_title(tournament_id),
        tournament_id=tournament_id,
        active_tab="how_it_works",
        example=example,
        lower=lower,
        invalid=invalid,
    )


@app.errorhandler(requests.RequestException)
def upstream_error(error):
    return (
        render_template(
            "error.html",
            title="Scores unavailable",
            message="We couldn't reach Match Play. Please try again in a moment.",
        ),
        503,
    )


@app.errorhandler(404)
def not_found(error):
    return (
        render_template(
            "error.html",
            title="Page not found",
            message="This player or page couldn't be found. Choose a tournament to continue.",
        ),
        404,
    )


@app.route("/")
def index():
    ticker = []
    unavailable = []
    for tournament_id, title in TOURNAMENT_INFO.items():
        try:
            standings = get_matchplay_standings(tournament_id)
            data = get_tournament_data_cached(tournament_id)
            players = {player["playerId"]: player["name"] for player in data["players"]}
            for standing in standings:
                ticker.append(
                    {
                        "tournament": title,
                        "tournament_id": tournament_id,
                        "player": players.get(standing["playerId"], "Unknown player"),
                        "position": standing["position"],
                        "points": standing["points"],
                    }
                )
        except requests.RequestException:
            unavailable.append(title)
    return render_template(
        "index.html",
        tournaments=TOURNAMENT_INFO,
        ticker=ticker,
        ticker_unavailable=unavailable,
        updated_at=score_timestamp(),
    )
