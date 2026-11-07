"""Check that the homepage ticker is opt-in and polls only published scores."""

from threading import Thread
from unittest.mock import patch

from browser_helpers import launch_browser
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from matchplay_score import web
from matchplay_score.tournament import Card, SinglePlayerGame


def main():
    cards = [
        Card(
            "Ticker Player",
            [SinglePlayerGame(1, "Stars", "Ticker Player", 2000, 500, "old")],
        )
    ]
    server = make_server("127.0.0.1", 0, web.app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with (
            patch.object(web, "best_cards", return_value=cards) as standings,
            sync_playwright() as p,
        ):
            browser = launch_browser(p)
            page = browser.new_page(viewport={"width": 390, "height": 900})
            requests = []
            errors = []
            page.on("request", lambda request: requests.append(request.url))
            page.on("pageerror", lambda error: errors.append(str(error)))
            url = f"http://127.0.0.1:{server.server_port}/"
            page.goto(url)
            expect(page.locator("[data-ticker-host]")).to_be_hidden()
            assert standings.call_count == 0
            assert not any("/ticker/" in request for request in requests)
            page.locator(".display-settings > summary").click()
            expect(page.locator("[data-ticker-toggle]")).not_to_be_checked()
            page.locator("[data-ticker-toggle]").check()
            page.locator(".display-settings > summary").click()
            expect(page.locator("[data-ticker]")).to_be_visible()
            expect(page.locator(".ticker-group").first).to_contain_text(
                "1,000,000 points"
            )
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.locator("[data-ticker-pause]").click()
            expect(page.locator("[data-ticker-pause]")).to_have_attribute(
                "aria-pressed", "true"
            )
            page.reload()
            expect(page.locator("[data-ticker]")).to_be_visible()
            page.locator(".display-settings > summary").click()
            page.locator("[data-ticker-toggle]").uncheck()
            page.locator(".display-settings > summary").click()
            expect(page.locator("[data-ticker-host]")).to_be_hidden()
            count = len([request for request in requests if "/ticker/" in request])
            # Fast-forward the polling timer: a disabled ticker must stay idle.
            page.clock.install()
            page.clock.fast_forward(120000)
            assert (
                len([request for request in requests if "/ticker/" in request]) == count
            )
            page.reload()
            expect(page.locator("[data-ticker-host]")).to_be_hidden()
            assert (
                len([request for request in requests if "/ticker/" in request]) == count
            )
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        thread.join()
    print(
        "PASS: ticker is off by default, enables on request, persists, pauses, and stops polling when disabled."
    )


if __name__ == "__main__":
    main()
