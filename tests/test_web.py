"""Check the UI's scoring boundaries without depending on the Match Play API."""

from unittest.mock import patch

import pytest
import requests

from matchplay_score import web
from matchplay_score.tournament import Card, SinglePlayerGame


def make_card(name, games):
    return Card(
        name,
        [
            SinglePlayerGame(i, label, name, score, multiplier, era)
            for i, (label, score, multiplier, era) in enumerate(games)
        ],
    )


@pytest.fixture
def client(monkeypatch):
    web.app.config.update(TESTING=True)
    monkeypatch.setattr(web, "best_cards", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        web, "get_tournament_data_cached", lambda tournament_id: {"players": []}
    )
    return web.app.test_client()


@pytest.fixture
def valid():
    return make_card(
        "Elia Lake",
        [("Avengers", 85_000_000, 0.67, "new"), ("Congo", 327_000_000, 0.13, "mid")],
    )


def test_standings_show_full_scores_and_player_navigation(client, valid):
    with patch.object(web, "best_cards", return_value=[valid]):
        response = client.get("/ranking/281672")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "99,460,000" in html
    assert "56,950,000" in html
    assert "/player/281672/Elia_Lake" in html
    assert 'name="viewport"' in html
    assert 'http-equiv="refresh"' not in html


def test_invalid_higher_card_does_not_become_personal_best(client, valid):
    invalid = make_card(
        "Elia Lake", [(f"DMD {i}", 100_000_000, 1, "mid") for i in range(3)]
    )
    invalid.status = "completed"
    with (
        patch.object(web, "player_cards", return_value=[invalid, valid]),
        patch.object(web, "best_cards", return_value=[valid]),
    ):
        response = client.get("/player/281672/Elia%20Lake")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Best valid card</span><strong>99,460,000" in html
    assert "Invalid card" in html
    assert "3 Mid games; the limit is 2." in html
    assert "erasing the latest entry" in html


def test_legacy_player_links_and_missing_player(client, valid):
    with (
        patch.object(web, "player_cards", side_effect=[[], [valid]]),
        patch.object(web, "best_cards", return_value=[valid]),
    ):
        assert client.get("/player/281672/Elia_Lake").status_code == 200
    with patch.object(web, "player_cards", return_value=[]):
        assert client.get("/player/281672/Nobody").status_code == 404


def test_empty_standings(client):
    with patch.object(web, "best_cards", return_value=[]):
        response = client.get("/ranking/281672")
    assert response.status_code == 200
    assert "No valid cards recorded yet." in response.get_data(as_text=True)


def test_newest_card_first_does_not_replace_higher_personal_best(client, valid):
    newer = make_card("Elia Lake", [("Stars", 1000, 1, "old")])
    with (
        patch.object(web, "player_cards", return_value=[newer, valid]),
        patch.object(web, "best_cards", return_value=[valid]),
    ):
        html = client.get("/player/281672/Elia_Lake").text
    assert "Best valid card</span><strong>99,460,000" in html
    assert "Newest first" in html


def test_upstream_outage_is_clear_and_retryable(client):
    with patch.object(web, "best_cards", side_effect=requests.Timeout):
        response = client.get("/ranking/281672")
    assert response.status_code == 503
    assert "couldn&#39;t reach Match Play" in response.get_data(as_text=True)


def test_machine_catalog_uses_tournament_arenas(client):
    data = {
        "arenas": [
            {"arenaId": 1, "name": "Stars", "tournamentArena": {"status": "active"}}
        ],
        "players": [],
    }
    with patch.object(web, "get_tournament_data_cached", return_value=data):
        response = client.get("/machines/281672")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Stars" in html and "× 500" in html
    assert "Jurassic Park (Pro)" not in html


def test_names_are_escaped_and_assets_are_served(client):
    card = make_card("<script>alert(1)</script>", [])
    with patch.object(web, "best_cards", return_value=[card]):
        html = client.get("/ranking/281672").get_data(as_text=True)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert client.get("/static/scorehigh.css").status_code == 200
    assert client.get("/static/scorehigh.js").status_code == 200


def test_how_it_works_has_its_own_page_and_correct_examples(client):
    html = client.get("/how-it-works/281672").get_data(as_text=True)
    assert "<h2>How it works</h2>" in html
    assert "140,000,000" in html
    assert "429,000,000" in html
    assert "519,000,000" in html
    assert "594,000,000" in html
    import re

    assert re.search(r'aria-current="page"\s+href="/how-it-works/281672"', html)
    assert 'href="#format"' not in html


def test_tournament_icons_are_distinct_and_repeatable(client, monkeypatch):
    monkeypatch.setattr(web, "TOURNAMENT_INFO", {1: "One", 2: "Two", 3: "Three"})
    icons = web.tournament_icons()
    assert icons == web.tournament_icons()
    assert len(set(icons.values())) == 3
    home = client.get("/index").get_data(as_text=True)
    for icon in icons.values():
        assert icon in home


def test_matchplay_link_available_on_desk_and_inside_tournament(client):
    target = web.tournament_matchplay_urls()[281672]
    for path, link_class in [
        ("/index", "matchplay-button"),
        ("/how-it-works/281672", "matchplay-tab"),
    ]:
        html = client.get(path).get_data(as_text=True)
        assert f'class="{link_class}" href="{target}"' in html
        assert "Match Play" in html
        assert 'rel="noopener noreferrer"' in html
