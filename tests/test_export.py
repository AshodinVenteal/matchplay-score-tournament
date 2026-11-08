from unittest.mock import patch

from matchplay_score import export, web


def test_static_export_preserves_scores_links_and_history(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "TOURNAMENT_INFO", {281672: "Test Tournament"})
    tournament = {
        "arenas": [
            {"arenaId": 1, "name": "Stars", "tournamentArena": {"status": "active"}}
        ],
        "players": [{"playerId": 1, "name": "Test Player"}],
    }
    cards = [
        {
            "playerId": 1,
            "singlePlayerGames": [{"arenaId": 1, "playerId": 1, "score": 1234}],
        }
    ]
    with (
        patch.object(export, "get_tournament_data_cached", return_value=tournament),
        patch.object(export, "get_cards", return_value=cards),
        patch(
            "matchplay_score.ranking.get_tournament_data_cached",
            return_value=tournament,
        ),
        patch("matchplay_score.ranking.get_cards", return_value=cards),
        patch.object(web, "get_tournament_data_cached", return_value=tournament),
    ):
        pages = export.export_site(tmp_path, "/scorehigh")
    assert len(pages) == 6
    ranking = (tmp_path / "ranking/281672/index.html").read_text(encoding="utf-8")
    assert "617,000" in ranking
    assert "/scorehigh/static/portal.css" in ranking
    assert "/scorehigh/player/281672/Test_Player" in ranking
    assert 'data-static-snapshot="true"' in ranking
    assert (tmp_path / "player/281672/Test_Player/index.html").is_file()
    assert (tmp_path / "404.html").is_file()
    monitor = (tmp_path / "monitor/281672/index.html").read_text(encoding="utf-8")
    assert 'data-monitor="true"' in monitor
    assert "/scorehigh/monitor/281672" in ranking
    assert (tmp_path / "static/monitor.js").is_file()
    assert (tmp_path / "static/monitor.css").is_file()
    assert (tmp_path / "LICENSE.txt").is_file()
    assert (tmp_path / "static/windows.css").is_file()
    assert (tmp_path / "static/fonts/DSEG14Classic-Bold.woff2").is_file()
    assert (tmp_path / "static/fonts/DSEG-LICENSE.txt").is_file()
    assert (tmp_path / "static/images/score-high-for-trans-lives.jpg").is_file()
    how = (tmp_path / "how-it-works/281672/index.html").read_text(encoding="utf-8")
    assert 'class="comparison-row counted-card"' in how
    assert "<strong>519,000,000</strong>" in how
    assert "/scorehigh/how-it-works/281672" in ranking
    assert not web.app.config.get("SNAPSHOT_AT")


def test_export_rejects_relative_base_path(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="relative"):
        export.export_site(tmp_path, "/../bad")
