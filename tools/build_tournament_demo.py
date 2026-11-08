"""Generate offline preview pages with 25 simulated tournament players."""

import argparse
import base64
import mimetypes
import re
from pathlib import Path
from random import Random

from flask import render_template

from matchplay_score.tournament import (
    ARENAS,
    CARD_GAME_LIMIT,
    ERAS,
    MAX_PER_ERA,
    Card,
    SinglePlayerGame,
)
from matchplay_score.web import app, render_how_it_works

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT.parent / "ScoreHigh-25-player-demo.html"
NAMES = [
    "Jamie Rivera",
    "Morgan Chen",
    "Alex Bennett",
    "Taylor Brooks",
    "Sam Patel",
    "Jordan Ellis",
    "Riley Nguyen",
    "Casey Thompson",
    "Avery Williams",
    "Quinn Martinez",
    "Cameron Lee",
    "Drew Robinson",
    "Skyler Davis",
    "Reese Anderson",
    "Rowan Garcia",
    "Parker Wilson",
    "Charlie Kim",
    "Emery Johnson",
    "Finley Scott",
    "Harper Lewis",
    "Sage Walker",
    "Dakota Young",
    "Robin Clark",
    "Sydney Hall",
    "Blair Adams",
]


def data_url(path):
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def main(page_kind="all"):
    if page_kind == "all":
        for kind in ["standings", "machines", "how-it-works", "monitor"]:
            main(kind)
        return
    prefix = "" if OUTPUT.stem == "index" else OUTPUT.stem + "-"
    machines_name = prefix + "machines.html"
    rules_name = prefix + "how-it-works.html"
    monitor_name = prefix + "monitor.html"
    output = (
        OUTPUT
        if page_kind == "standings"
        else OUTPUT.parent
        / (
            machines_name
            if page_kind == "machines"
            else monitor_name
            if page_kind == "monitor"
            else rules_name
        )
    )
    rng = Random(25)
    lineup_rng = Random(25025)
    cards = []
    for index, name in enumerate(NAMES):
        lineup = [
            arena
            for era in ERAS
            for arena in lineup_rng.sample(
                [arena for arena in ARENAS if arena.era == era], MAX_PER_ERA
            )
        ]
        lineup_rng.shuffle(lineup)
        lineup = lineup[: lineup_rng.randint(1, CARD_GAME_LIMIT)]
        strength = 1.25 - index * 0.032
        games = [
            SinglePlayerGame(
                ARENAS.index(arena) + 1,
                arena.short_name,
                name,
                int(rng.randint(25_000_000, 115_000_000) * strength / arena.multiplier),
                arena.multiplier,
                arena.era,
            )
            for arena in lineup
        ]
        cards.append(Card(name, games))
    cards.sort(key=Card.computed_score, reverse=True)
    with app.test_request_context("/"):
        if page_kind == "how-it-works":
            html = render_how_it_works(25025).replace(
                "Tournament 25025", "25-player demo"
            )
        else:
            html = render_template(
                "ranking.html"
                if page_kind in ["standings", "monitor"]
                else "machines.html",
                cards=cards,
                arenas=ARENAS,
                monitor=page_kind == "monitor",
                title="25-player demo",
                tournament_id=25025,
                updated_at="2026-11-03T12:00:00Z",
                active_tab="standings" if page_kind == "monitor" else page_kind,
                static_snapshot=True,
            )
    static = ROOT / "src/matchplay_score/static"

    def stylesheet(match):
        tag, name = match.group(0), match.group(1)
        path = static / name
        css = path.read_text(encoding="utf-8")
        css = re.sub(
            r"url\(['\"]?([^)'\"]+)['\"]?\)",
            lambda url: 'url("' + data_url(path.parent / url.group(1)) + '")',
            css,
        )
        encoded = base64.b64encode(css.encode("utf-8")).decode("ascii")
        return re.sub(
            r'href="/static/[^" ]+"',
            lambda _: 'href="data:text/css;base64,' + encoded + '"',
            tag,
        )

    html = re.sub(
        r'<link[^>]+href="/static/([^"?]+\.css)(?:\?[^" ]*)?"[^>]*>', stylesheet, html
    )
    html = html.replace(
        "/static/images/pinball.svg", data_url(static / "images/pinball.svg")
    )
    html = html.replace(
        "/static/images/score-arborelia-qr.svg",
        data_url(static / "images/score-arborelia-qr.svg"),
    )
    html = re.sub(
        r'data-flyer-src="/static/([^"]+)"',
        lambda match: 'data-flyer-src="' + data_url(static / match.group(1)) + '"',
        html,
    )
    monitor_script = (static / "monitor.js").read_text(encoding="utf-8")
    html = re.sub(
        r'<script src="/static/monitor.js(?:\?[^" ]*)?" defer></script>', "", html
    )
    script = (
        monitor_script + "\n" + (static / "scorehigh.js").read_text(encoding="utf-8")
    )
    # Isolate demo preferences from actual tournament choices, including file://.
    storage_prefix = (
        "scorehigh-monitor-testbed-"
        if OUTPUT.stem == "monitor-preview"
        else "scorehigh-demo-"
    )
    script = script.replace("scorehigh-", storage_prefix)
    html = re.sub(
        r'<script src="/static/scorehigh.js(?:\?[^" ]*)?" defer></script>',
        lambda _: "<script>" + script + "</script>",
        html,
    )
    # The bundled script must run after the full page has been parsed.
    html = html.replace("<script>" + script + "</script>", "")
    html = html.replace("data-refresh-status", "data-demo-status")
    html = re.sub(
        r'(<p class="update-status"[^>]*>).*?(</p>)',
        r"\1Simulated results · 25 players · no live updates\2",
        html,
    )
    html = html.replace("/monitor/25025", monitor_name)
    html = html.replace("/ranking/25025?display=monitor", monitor_name)
    html = html.replace("/ranking/25025", OUTPUT.name)
    html = re.sub(r'href="/player/25025/[^"]+"', 'href="#" data-demo-player', html)
    html = html.replace("/machines/25025", machines_name)
    html = html.replace("/how-it-works/25025", rules_name)
    html = html.replace('href="/"', f'href="{OUTPUT.name}"')
    # This is a display demo, so external tournament navigation has no target.
    html = html.replace(
        'class="matchplay-tab"', 'class="matchplay-tab" data-demo-external'
    )
    demo_script = """
const demoRefreshControls = document.querySelector('[data-refresh-controls]');
if (demoRefreshControls) demoRefreshControls.hidden = false;
document.querySelectorAll('[data-refresh], [data-auto]').forEach(el => el.hidden = true);
document.querySelectorAll('[data-demo-player]').forEach(link => link.addEventListener('click', event => {
  event.preventDefault();
  const details = link.closest('.ranking-entry').querySelector('details');
  details.open = !details.open;
}));
document.querySelectorAll('[data-demo-external]').forEach(link => {
  link.removeAttribute('target'); link.href = '#';
  link.title = 'Simulated tournament — no Match Play event';
  link.addEventListener('click', event => event.preventDefault());
});
"""
    html = html.replace(
        "</body>",
        "<script>" + script + "</script><script>" + demo_script + "</script></body>",
    )
    output.write_text(html, encoding="utf-8", newline="\n")
    print(f"Created {output} ({output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".preview/demo/index.html"
    )
    args = parser.parse_args()
    OUTPUT = args.output.resolve()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    main()
