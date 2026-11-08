"""Simulated cards for checking the display without touching tournament records."""

from dataclasses import replace
from datetime import datetime, timedelta

from flask import abort, g, render_template, request, url_for

from .broadcast import overlay_options, select_cards
from .tournament import ARENAS, Card, SinglePlayerGame, creation_order

EXAMPLE_ID = 25025
EXAMPLE_PLAYER = "Alex Morgan"


def example_history():
    arenas = {arena.short_name: arena for arena in ARENAS}

    def game(name, points):
        arena = arenas[name]
        return SinglePlayerGame(
            ARENAS.index(arena),
            name,
            EXAMPLE_PLAYER,
            int(points / arena.multiplier),
            arena.multiplier,
            arena.era,
        )

    lineup = [
        game("Stars", 90_000_000),
        game("Taxi", 75_000_000),
        game("Creature", 100_000_000),
        game("TRON", 95_000_000),
        game("Jurassic Park", 85_000_000),
        game("Iron Maiden", 80_000_000),
    ]
    valid = Card(
        EXAMPLE_PLAYER,
        lineup,
        card_id=2,
        created_at="2026-11-07T12:00:00Z",
        status="completed",
    )
    invalid = Card(
        EXAMPLE_PLAYER,
        [*lineup, game("Theatre", 120_000_000)],
        card_id=3,
        created_at="2026-11-07T13:00:00Z",
        status="completed",
    )
    voided = Card(
        EXAMPLE_PLAYER,
        lineup[:2],
        card_id=1,
        created_at="2026-11-07T11:00:00Z",
        voided=True,
    )
    progress = Card(
        EXAMPLE_PLAYER,
        lineup[:4],
        card_id=4,
        created_at="2026-11-07T14:00:00Z",
        status="started",
        is_latest=True,
    )
    for card in [valid, invalid, voided, progress]:
        card.games = [
            replace(
                game,
                game_id=card.card_id * 100 + index + 1,
                created_at=(
                    datetime.fromisoformat(card.created_at)
                    + timedelta(minutes=2 * (index + 1))
                ).isoformat(),
            )
            for index, game in enumerate(card.games)
        ]
    return sorted(
        [valid, invalid, voided, progress],
        key=lambda card: creation_order(card.created_at, card.card_id),
        reverse=True,
    )


def example_standings():
    history = example_history()
    best = max((card for card in history if card.is_valid()), key=Card.computed_score)
    cards = [best]
    first_names = [
        "Taylor",
        "Jordan",
        "Sam",
        "Riley",
        "Quinn",
        "Jamie",
        "Avery",
        "Casey",
    ]
    last_names = ["Brooks", "Rivera", "Chen"]
    for index in range(24):
        name = f"{first_names[index % 8]} {last_names[index // 8]}"
        factor = 0.96 - index * 0.026
        count = 6 if index < 7 else 2 + index % 5
        games = [
            replace(game, player_name=name, score=int(game.score * factor))
            for game in best.games[:count]
        ]
        cards.append(
            Card(
                name,
                games,
                card_id=100 + index,
                status="completed" if count == 6 else "started",
            )
        )
    return sorted(cards, key=Card.computed_score, reverse=True)


def example_url_for(endpoint, **values):
    routes = {
        "index": "example_cards",
        "render_ranking": "example_ranking",
        "render_monitor": "example_monitor",
        "render_obs": "example_obs",
        "render_overlay": "example_overlay",
        "render_player": "example_player",
        "render_machines": "example_machines",
        "render_how_it_works": "example_rules",
    }
    if endpoint in routes:
        values.pop("tournament_id", None)
        if "player_name" in values:
            values["player_name"] = values["player_name"].replace(" ", "_")
        return url_for(routes[endpoint], **values)
    return url_for(endpoint, **values)


def register_examples(app):
    @app.before_request
    def example_context():
        g.example_mode = bool(
            request.endpoint and request.endpoint.startswith("example_")
        )

    @app.context_processor
    def context():
        if not g.get("example_mode"):
            return {}
        return {"example_mode": True, "url_for": example_url_for}

    def render(template, **values):
        return render_template(
            template,
            title=values.pop("title", "Examples - simulated tournament"),
            tournament_id=EXAMPLE_ID,
            updated_at="2026-11-07T14:00:00Z",
            **values,
        )

    @app.route("/examples/")
    def example_cards():
        return example_player(EXAMPLE_PLAYER)

    @app.route("/examples/player/<path:player_name>")
    def example_player(player_name):
        name = player_name.replace("_", " ")
        standings = example_standings()
        if name == EXAMPLE_PLAYER:
            cards = example_history()
        else:
            cards = [card for card in standings if card.player_name == name]
        if not cards:
            abort(404)
        valid = [card for card in cards if card.is_valid()]
        rank = next(
            (i for i, card in enumerate(standings, 1) if card.player_name == name), None
        )
        return render(
            "player.html",
            cards=cards,
            player_name=name,
            best_card=max(valid, key=Card.computed_score) if valid else None,
            rank=rank,
            active_tab="standings",
        )

    @app.route("/examples/standings/")
    def example_ranking():
        return render(
            "ranking.html",
            cards=example_standings(),
            active_tab="standings",
            monitor=False,
        )

    @app.route("/examples/monitor/")
    def example_monitor():
        return render(
            "ranking.html",
            title="25-player demo",
            cards=example_standings(),
            active_tab="standings",
            monitor=True,
        )

    @app.route("/examples/machines/")
    def example_machines():
        return render("machines.html", arenas=ARENAS, active_tab="machines")

    @app.route("/examples/obs/")
    def example_obs():
        return render("obs.html", title="25-player demo", active_tab="obs")

    @app.route("/examples/overlay/")
    def example_overlay():
        options = overlay_options()
        cards = [
            *[
                card
                for card in example_standings()
                if card.player_name != EXAMPLE_PLAYER
            ],
            *example_history(),
        ]
        return render(
            "overlay.html",
            title="25-player demo",
            entries=select_cards(cards, options["mode"], options["count"]),
            options=options,
        )

    @app.route("/examples/how-it-works/")
    def example_rules():
        from .web import render_how_it_works

        return render_how_it_works(EXAMPLE_ID)
