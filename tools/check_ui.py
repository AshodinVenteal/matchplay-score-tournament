"""Check a demo export or a running ScoreHigh site in Chromium."""

from argparse import ArgumentParser
from pathlib import Path

from browser_helpers import launch_browser
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--preview-dir", type=Path, default=ROOT / ".preview/demo")
    parser.add_argument("--url", help="Live or exported tournament standings URL")
    parser.add_argument("--screenshots", type=Path, default=ROOT / ".preview/ui")
    args = parser.parse_args()
    url = args.url or (args.preview_dir.resolve() / "index.html").as_uri()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch_browser(p)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        for width in [320, 390, 768, 1000, 1440, 1920]:
            page.set_viewport_size({"width": width, "height": 900})
            page.goto(url, wait_until="networkidle")
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            ), width
            assert page.locator(".ranking-entry").count() > 0
            for mode in ["light", "dark"]:
                page.locator(".display-settings > summary").click()
                page.locator("[data-theme-select]").select_option(mode)
                page.locator(".display-settings > summary").click()
                assert page.locator("html").get_attribute("data-theme") == mode
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                )
            entries = page.locator(".ranking-entry")
            assert entries.evaluate_all(
                "els => els.every(el => el.querySelectorAll('.player-game-banners .monitor-game-block').length === 6)"
            )
            arrow = page.locator("[data-card-toggle]").first
            arrow.click()
            expect(arrow).to_have_attribute("aria-expanded", "true")
            assert page.locator(".card-details").first.evaluate("el => el.open")
            page.keyboard.press("Space")
            expect(arrow).to_have_attribute("aria-expanded", "false")
            page.locator("[data-follow-player]").first.click()
            page.locator("[data-following-filter]").click()
            assert page.locator(".ranking-entry:visible").count() == 1
            page.locator("[data-following-filter]").click()
            page.locator("[data-follow-player]").first.click()
            page.locator("[data-claim-player]").first.click()
            assert page.locator("[data-claim-player]:visible").count() == 1
            page.locator("[data-claim-player]:visible").click()
            page.locator("[data-expand]").click()
            expect(
                page.locator("[data-card-toggle][aria-expanded=true]")
            ).to_have_count(entries.count())
            page.locator("[data-expand]").click()
            search = page.locator("[data-player-search]")
            name = page.locator(".player-info > a").first.inner_text()
            search.fill(name)
            assert page.locator(".ranking-entry:visible").count() >= 1
            search.fill("")
            if width in [390, 1440]:
                page.locator("h1").click()
                page.screenshot(path=str(args.screenshots / f"standings-{width}.png"))
        for style in ["windows", "portal", "matchplay"]:
            page.set_viewport_size({"width": 390, "height": 900})
            page.locator(".display-settings > summary").click()
            page.locator("[data-style-select]").select_option(style)
            page.locator(".display-settings > summary").click()
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            ), style
        for title in ["Machines", "How it works", "Standings"]:
            page.get_by_role("navigation", name="Tournament", exact=True).get_by_role(
                "link", name=title, exact=True
            ).click()
            if title == "Machines":
                assert page.locator("#format").evaluate("el => el.open")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.set_viewport_size({"width": 1600, "height": 900})
        page.locator(".event-display-link").click()
        assert page.locator("html").get_attribute("data-monitor") == "true"
        assert page.locator(".podium-card:visible").count() > 0
        page.get_by_role("link", name="Exit display").click()
        plain_context = browser.new_context(
            java_script_enabled=False, viewport={"width": 390, "height": 900}
        )
        plain = plain_context.new_page()
        plain.goto(url)
        plain.locator(".card-details > summary").first.click()
        assert plain.locator(".game-breakdown").first.is_visible()
        assert not errors, errors
        browser.close()
    print(
        "PASS: responsive standings, preferences, tracking, progress slots, disclosures, navigation, monitor link, and no-script fallback."
    )


if __name__ == "__main__":
    main()
