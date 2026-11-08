"""Check native font commas, card history states, and monitor game scores."""

import logging
from threading import Thread
from unittest.mock import patch

from browser_helpers import launch_browser
from check_monitor_responsive import GEOMETRY
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from matchplay_score import web
from matchplay_score.tournament import Card, SinglePlayerGame


def main():
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    def games(eras):
        return [
            SinglePlayerGame(i, f"Game {i}", "Test Player", 35000000 + i, 1, era)
            for i, era in enumerate(eras)
        ]

    valid = Card(
        "Test Player",
        games(["old", "old", "mid", "mid", "new", "new"]),
        card_id=3,
        status="completed",
    )
    invalid = Card(
        "Test Player",
        games(["old", "mid", "mid", "mid", "new", "new"]),
        card_id=2,
        status="completed",
    )
    abandoned = Card("Test Player", games(["old", "new"]), card_id=1, abandoned=True)
    in_progress = Card("Test Player", games(["mid"]), card_id=4)
    server = make_server("127.0.0.1", 0, web.app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with (
            patch.object(
                web,
                "player_cards",
                return_value=[valid, invalid, abandoned, in_progress],
            ),
            patch.object(web, "best_cards", return_value=[valid]),
            sync_playwright() as p,
        ):
            browser = launch_browser(p)
            page = browser.new_page(
                viewport={"width": 390, "height": 900}, timezone_id="America/New_York"
            )
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(
                f"http://127.0.0.1:{server.server_port}/player/282630/Test_Player"
            )
            expect(page.locator(".invalid-card")).to_have_count(1)
            expect(page.locator(".invalid-card")).to_contain_text(
                "3 Mid games; the limit is 2."
            )
            expect(page.locator(".invalid-card")).to_contain_text(
                "erasing the latest entry"
            )
            expect(page.locator(".abandoned-notice")).to_contain_text("Abandoned")
            expect(page.locator(".card-label").last).to_contain_text("Card in progress")
            for width in [320, 390, 768, 1440]:
                page.set_viewport_size({"width": width, "height": 900})
                for font in [
                    "plain",
                    "matrix",
                    "lcd",
                    "highway",
                    "terminal",
                    "segmented",
                    "plain",
                ]:
                    page.locator(".display-settings > summary").click()
                    page.locator("[data-score-font-select]").select_option(font)
                    page.locator(".display-settings > summary").click()
                    page.evaluate("document.fonts.ready")
                    score = page.locator(".player-stats > div:nth-child(2) > strong")
                    if font == "segmented":
                        expect(score.locator(".score-comma")).to_have_count(2)
                    else:
                        expect(page.locator(".score-comma")).to_have_count(0)
                    assert score.evaluate("el=>el.scrollWidth <= el.clientWidth + 1"), (
                        width,
                        font,
                    )
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= innerWidth"
                    ), (width, font)
            page.set_viewport_size({"width": 1600, "height": 900})
            page.goto(f"http://127.0.0.1:{server.server_port}/examples/")
            expect(page.locator(".history-card")).to_have_count(4)
            expect(page.locator(".latest-card-badge")).to_have_count(1)
            expect(page.locator(".last-added-game")).to_have_count(4)
            expect(page.locator(".card-added time")).to_have_count(4)
            expect(
                page.locator('.card-added time[datetime="2026-11-07T14:00:00Z"]')
            ).to_contain_text("9:00:00 AM EST")
            for width in [320, 390, 768, 1440]:
                page.set_viewport_size({"width": width, "height": 900})
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                ), width
            for width, height in [
                (1024, 768),
                (1280, 720),
                (1366, 768),
                (1600, 900),
                (1920, 1080),
            ]:
                page.set_viewport_size({"width": width, "height": height})
                page.goto(f"http://127.0.0.1:{server.server_port}/examples/monitor/")
                page.wait_for_timeout(100)
                failures = page.evaluate(GEOMETRY)
                assert not failures, (width, height, failures)
                scores = page.locator(".ranking-entry:visible .monitor-game-score")
                assert scores.evaluate_all(
                    "els => els.every(el => getComputedStyle(el).fontFamily.includes('monospace') && el.scrollWidth <= el.clientWidth + 1)"
                )
                assert page.locator(".monitor-game-score .score-comma").count() == 0
                if width >= 1600:
                    assert scores.evaluate_all(
                        "els => els.every(el => parseFloat(getComputedStyle(el).fontSize) >= 14)"
                    )
            expect(
                page.locator(".ranking-entry:visible").first.locator(
                    ".monitor-game-score"
                )
            ).to_have_count(6)
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        thread.join()
    print(
        "PASS: native commas across all fonts, single-line player totals, invalid and abandoned labels, and monitor row scores."
    )


if __name__ == "__main__":
    main()
