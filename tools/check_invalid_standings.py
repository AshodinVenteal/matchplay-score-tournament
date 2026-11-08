"""Check unranked players and readable correction notices without API calls."""

import logging
from pathlib import Path
from threading import Thread

from browser_helpers import launch_browser
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from matchplay_score.web import app


def main():
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    server = make_server("127.0.0.1", 0, app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser = launch_browser(p)
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            for width in (320, 390, 1440):
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(f"http://127.0.0.1:{server.server_port}/examples/standings/")
                row = page.locator(".ranking-entry").last
                expect(row).to_have_class("ranking-entry is-unranked")
                expect(row.locator(".rank")).to_have_text("—")
                expect(row.locator(".card-invalid-header")).to_be_visible()
                row.locator("[data-card-toggle]").click()
                notice = row.locator(".invalid-card-overlay")
                expect(notice).to_be_visible()
                expect(notice).to_contain_text("3 Mid games; the limit is 2.")
                expect(notice).to_contain_text("Ask a scorekeeper")
                assert (
                    row.locator(".game-breakdown").evaluate(
                        "el => getComputedStyle(el).filter"
                    )
                    == "blur(2px)"
                )
                assert notice.evaluate("el => getComputedStyle(el).filter") == "none"
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                )
                if width == 390:
                    Path(".preview").mkdir(exist_ok=True)
                    row.screenshot(path=".preview/invalid-player-standings.png")
                row.locator(".player-info > a").click()
                expect(
                    page.locator(".history-card.invalid-card .invalid-card-overlay")
                ).to_be_visible()
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                )
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        thread.join()
    print(
        "PASS: grey unranked players, blurred invalid cards, readable reasons, and player links on mobile and desktop."
    )


if __name__ == "__main__":
    main()
