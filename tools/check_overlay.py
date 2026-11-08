"""Check streaming rotation, refresh recovery, and source sizing without API reads."""

import logging
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import requests
from browser_helpers import launch_browser
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from matchplay_score import web
from matchplay_score.examples import example_history


def main():
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    server = make_server("127.0.0.1", 0, web.app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with (
            patch.object(web, "tournament_cards", return_value=example_history()),
            sync_playwright() as p,
        ):
            browser = launch_browser(p)
            page = browser.new_page(viewport={"width": 640, "height": 270})
            page.clock.install()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            base = f"http://127.0.0.1:{server.server_port}"
            page.goto(base + "/overlay/282630?mode=recent&seconds=8")
            page.evaluate("document.fonts.ready")
            expect(page.locator(".broadcast-card:visible")).to_have_count(1)
            assert (
                page.locator(".broadcast-card:visible").get_attribute("data-card-id")
                == "4"
            )
            assert (
                page.locator("body").evaluate(
                    "el => getComputedStyle(el).backgroundColor"
                )
                == "rgba(0, 0, 0, 0)"
            )
            for width, height in [
                (640, 270),
                (480, 200),
                (640, 900),
                (480, 720),
                (320, 900),
            ]:
                page.set_viewport_size({"width": width, "height": height})
                assert not page.evaluate("""() => {
                  const panel = document.querySelector('.broadcast-panel').getBoundingClientRect();
                  return [...document.querySelectorAll('.broadcast-card:not([hidden]) strong, .broadcast-footer')]
                    .filter(el => { const b = el.getBoundingClientRect();
                      return b.right > panel.right + 1 || b.bottom > panel.bottom + 1 || b.left < panel.left;
                    }).map(el => el.textContent);
                }"""), (width, height)
            page.set_viewport_size({"width": 640, "height": 270})
            Path(".preview").mkdir(exist_ok=True)
            page.screenshot(path=".preview/obs-overlay.png")
            page.clock.run_for(8400)
            expect(page.locator(".broadcast-card:visible")).to_have_attribute(
                "data-card-id", "2"
            )
            # The source refreshes its own page, never Match Play from the browser.
            with page.expect_response(
                lambda response: "/overlay/282630" in response.url
            ):
                page.clock.run_for(15000)
            page.clock.run_for(8400)
            expect(page.locator(".broadcast-card:visible")).to_have_count(1)
            # An outage preserves cards; the next successful refresh recovers.
            with patch.object(web, "tournament_cards", side_effect=requests.Timeout):
                with page.expect_response(lambda response: response.status == 503):
                    page.clock.run_for(16000)
                expect(page.locator("[data-broadcast-status]")).to_have_text(
                    "Cached scores · retrying"
                )
                expect(page.locator(".broadcast-card:visible")).to_have_count(1)
            with page.expect_response(
                lambda response: "/overlay/282630" in response.url
            ):
                page.clock.run_for(16000)
            expect(page.locator("[data-broadcast-status]")).to_have_text(
                "Checks every 15s"
            )
            page.goto(base + "/examples/obs/")
            page.locator('select[name="mode"]').select_option("top")
            page.locator('input[name="count"]').fill("3")
            page.get_by_role("button", name="Update preview").click()
            expect(page.locator("[data-obs-url]")).to_have_value(
                base + "/examples/overlay/?mode=top&count=3&seconds=12"
            )
            expect(
                page.frame_locator("iframe").locator(".broadcast-card")
            ).to_have_count(3)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        thread.join()
    print(
        "PASS: transparent source, sizing, card rotation, cached refresh, outage recovery, and OBS setup."
    )


if __name__ == "__main__":
    main()
