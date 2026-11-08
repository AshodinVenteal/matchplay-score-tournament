"""Check optional flyer artwork without making any Match Play requests."""

import logging
from threading import Thread
from unittest.mock import patch

from browser_helpers import launch_browser
from check_monitor_responsive import GEOMETRY
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from matchplay_score import web
from matchplay_score.examples import example_standings


def main():
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    server = make_server("127.0.0.1", 0, web.app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with (
            patch.object(web, "best_cards", return_value=example_standings()),
            sync_playwright() as p,
        ):
            browser = launch_browser(p)
            page = browser.new_page(viewport={"width": 1600, "height": 900})
            urls = []
            errors = []
            page.on("request", lambda request: urls.append(request.url))
            page.on("pageerror", lambda error: errors.append(str(error)))
            url = f"http://127.0.0.1:{server.server_port}/monitor/282630"
            page.goto(url, wait_until="networkidle")
            assert not any("/images/flyers/" in item for item in urls)
            expect(page.locator("html")).to_have_attribute("data-monitor-flyers", "off")
            panel = page.locator(".monitor-display-settings")
            panel.locator("summary").click()
            toggle = panel.locator("[data-monitor-flyers]")
            expect(toggle).not_to_be_checked()
            toggle.check()
            page.keyboard.press("Escape")
            expect(page.locator("html")).to_have_attribute("data-monitor-flyers", "on")
            page.wait_for_function(
                "[...document.querySelectorAll('.podium-flyer')].every(el => el.complete && el.naturalWidth > 0)"
            )
            assert page.locator(".podium-flyer").evaluate_all(
                "els => els.every(el => getComputedStyle(el).opacity === '0.1')"
            )
            assert page.locator(".ranking-list .podium-flyer").count() == 0
            assert not any("api.matchplay.events" in item for item in urls)
            page.locator("[data-monitor-rotate]").click()
            for width, height in [
                (1024, 768),
                (1280, 720),
                (1366, 768),
                (1600, 900),
                (1920, 1080),
            ]:
                page.set_viewport_size({"width": width, "height": height})
                assert not page.evaluate(GEOMETRY), (
                    width,
                    height,
                    page.evaluate(GEOMETRY),
                )
            # A refreshed scoreboard must keep its artwork preference.
            with page.expect_response(url):
                page.locator("[data-refresh]").evaluate("el => el.click()")
            page.wait_for_function(
                "[...document.querySelectorAll('.podium-flyer')].every(el => el.hasAttribute('src') && el.complete && el.naturalWidth > 0)"
            )
            page.reload(wait_until="networkidle")
            expect(page.locator("html")).to_have_attribute("data-monitor-flyers", "on")
            panel.locator("summary").click()
            expect(toggle).to_be_checked()
            toggle.uncheck()
            expect(page.locator("html")).to_have_attribute("data-monitor-flyers", "off")
            assert page.locator(".podium-flyer").evaluate_all(
                "els => els.every(el => getComputedStyle(el).display === 'none')"
            )
            before = len([item for item in urls if "/images/flyers/" in item])
            page.reload(wait_until="networkidle")
            assert len([item for item in urls if "/images/flyers/" in item]) == before
            page.evaluate("localStorage.setItem('scorehigh-monitor-flyers','on')")
            page.goto(
                f"http://127.0.0.1:{server.server_port}/ranking/282630",
                wait_until="networkidle",
            )
            assert len([item for item in urls if "/images/flyers/" in item]) == before
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        thread.join()
    print(
        "PASS: flyers default off, load only on opt-in, use 10% opacity on top-three rows, persist through refresh, and remain monitor-only."
    )


if __name__ == "__main__":
    main()
