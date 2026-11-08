from unittest.mock import Mock

from matchplay_score import matchplay_api as api
from matchplay_score import web


def test_examples_show_all_history_states_without_api_calls(monkeypatch):
    get = Mock(side_effect=AssertionError("Examples must not call Match Play"))
    monkeypatch.setattr(api._session, "get", get)
    with web.app.test_client() as client:
        response = client.get("/examples/")
        assert response.status_code == 200
        html = response.text
        for label in ["Completed", "Invalid", "Abandoned", "Card in progress"]:
            assert label in html
        assert "3 Mid games; the limit is 2." in html
        assert "erasing the latest entry" in html
        assert 'data-examples="true"' in html
        assert html.count('class="history-card-heading"') == 4
        for path in [
            "standings/",
            "monitor/",
            "machines/",
            "how-it-works/",
            "player/Alex_Morgan",
        ]:
            assert client.get("/examples/" + path).status_code == 200
    get.assert_not_called()
