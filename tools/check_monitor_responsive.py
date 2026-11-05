"""Check the isolated monitor testbed at common event display resolutions."""

from argparse import ArgumentParser
from pathlib import Path

from browser_helpers import launch_browser
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

GEOMETRY = """() => {
 const failures = [];
 const rect = el => el.getBoundingClientRect();
 const visible = el => el.getClientRects().length > 0;
 const within = (el, parent) => {
   const a = rect(el), b = rect(parent);
   if (a.left < b.left - 1 || a.right > b.right + 1 || a.top < b.top - 1 || a.bottom > b.bottom + 1) failures.push(el.className + ' outside ' + parent.className);
 };
 for (const el of document.querySelectorAll('.podium-card, .ranking-entry, .update-status, .monitor-tools')) {
   if (!visible(el)) continue;
   const a = rect(el);
   if (a.left < -1 || a.right > innerWidth + 1 || a.top < -1 || a.bottom > innerHeight + 1) failures.push(el.className + ' outside viewport');
 }
 for (const row of document.querySelectorAll('.podium-game')) {
   if (!visible(row)) continue;
   for (const sel of ['.monitor-game-block', '.podium-raw', '.podium-multiplier', '.podium-game-points']) {
     const child = row.querySelector(sel);
     if (child) within(child, row);
   }
   const raw = row.querySelector('.podium-raw');
   if (raw && raw.scrollWidth > raw.clientWidth + 1) failures.push('raw score clipped');
 }
 for (const row of document.querySelectorAll('.ranking-entry')) {
   if (!visible(row)) continue;
   for (const el of row.querySelectorAll('.rank, .player-info, .score-info, .monitor-games')) within(el, row);
   const games = row.querySelector('.monitor-games');
   const blocks = games.querySelectorAll('.monitor-game-block');
   const center = (rect(blocks[0]).left + rect(blocks[blocks.length - 1]).right) / 2;
   if (Math.abs(center - (rect(games).left + rect(games).right) / 2) > 1) failures.push('games not centered');
   const style = getComputedStyle(games);
   if (parseFloat(style.borderLeftWidth) < 1 || parseFloat(style.borderRightWidth) < 1) failures.push('column dividers missing');
   within(row.querySelector('.score-info>strong'), row.querySelector('.score-info'));
   if (rect(row.querySelector('.player-info')).right > rect(games).left) failures.push('name overlaps games');
   if (rect(games).right > rect(row.querySelector('.score-info')).left) failures.push('games overlap score');
 }
 return failures;
}"""


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--preview-dir", type=Path, default=ROOT / ".preview/demo")
    parser.add_argument("--url", help="Monitor display URL")
    args = parser.parse_args()
    url = args.url or (args.preview_dir.resolve() / "monitor.html").as_uri()
    failures_by_size = []
    with sync_playwright() as p:
        browser = launch_browser(p)
        page = browser.new_page()
        page.add_init_script('localStorage.setItem("scorehigh-demo-theme", "dark")')
        page.clock.install()
        for width, height in [
            (1920, 1080),
            (1600, 900),
            (1440, 900),
            (1366, 768),
            (1280, 720),
            (1024, 768),
            (2560, 1440),
        ]:
            page.set_viewport_size({"width": width, "height": height})
            page.goto(url, wait_until="networkidle")
            total = page.locator(".ranking-entry").count()
            assert total > 0, "No player cards to check"
            assert page.locator(".ranking-entry:visible .rank").all_inner_texts() == [
                str(rank) for rank in range(4, min(total + 1, 9))
            ]
            failures = page.evaluate(GEOMETRY)
            page.screenshot(
                path=str(ROOT / f".preview/responsive-monitor-{width}x{height}.png")
            )
            if failures:
                failures_by_size.append((width, height, sorted(set(failures))))
                continue
            seen = set()
            pages = int(
                page.locator("[data-monitor-page]")
                .inner_text()
                .split("/")[1]
                .split()[0]
            )
            for index in range(pages):
                assert page.locator(".podium-card:visible").count() == (
                    min(3, total) if index == 0 else 0
                )
                failures = page.evaluate(GEOMETRY)
                if failures:
                    failures_by_size.append(
                        (width, height, index, sorted(set(failures)))
                    )
                seen.update(
                    int(rank)
                    for rank in page.locator(
                        ".ranking-entry:visible .rank"
                    ).all_inner_texts()
                )
                if pages > 1:
                    page.locator("[data-monitor-next]").click()
                    page.clock.run_for(650)
                    page.wait_for_function(
                        'getComputedStyle(document.querySelector(".scoreboard")).opacity === "1"'
                    )
            assert seen == set(range(4, total + 1)), (width, height, seen)
            print("Checked", width, height, pages, "pages")
        browser.close()
    assert not failures_by_size, failures_by_size
    print(
        "PASS: all finalists, score breakdowns, and remaining player pages fit every tested resolution."
    )


if __name__ == "__main__":
    main()
