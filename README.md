# ScoreHigh

Scoring system for the TPC ScoreHigh format, as used in [Score High for Trans Lives](https://posts.arborelia.net/trans-lives/).

[Public site](https://score.arborelia.net) | [Preview](https://ashodinventeal.github.io/scorehigh-preview/)

This frontend runs with the existing Flask application, including the hosted
deployment at https://tpc-high-score.vercel.app. The links above are the separate
ScoreHigh deployment and simulated preview.

ScoreHigh multiplies each machine score by its configured multiplier and ranks each player by their best valid card. A card allows two games from each of three eras. Cards with fewer than six games show their progress and unused slots; cards over an era limit stay in player history but do not count toward standings.

## Run locally

Python 3.14 and [uv](https://docs.astral.sh/uv/) are required.

```sh
uv sync --group dev
uv run scorehigh --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`. The older `matchplay-score` command remains available.

Configure tournament IDs, names, and Match Play links in `src/matchplay_score/web.py`. Machine eras and multipliers live in `src/matchplay_score/tournament.py`. The configured test event is tournament `281672`. Alternatively, you could attach this to your already built back-end. Ideally you're using the python scripts in general so you're not rewriting the wheel here.

## Standings and event display

The standings support search, expandable machine scores, and player history. Claim and follow selections are stored on the viewer's device; they do not create accounts or change tournament records.

The Monitor button opens the event display. Page one shows prominent cards for ranks 1-3 and rows for ranks 4-8. Later pages show the remaining players, with capacity adjusted to the available height. Pages rotate every 12 seconds with a whole-board fade; manual paging, pause, fullscreen, and reduced motion are supported. Common supported landscape sizes are from 1024x768 through 2560x1440, including 1600x900 and 1920x1080.

Display settings provide light/dark/system colors, a simple layout, Classic Windows, and a 2000s Portal layout. Hey look, I wanted options! Standings scores default to readable monospace; the event display uses 7 Segment Display font. The optional score fonts are bundled locally with their license notices.

## Score snapshots and caching

The separate ScoreHigh GitHub Pages deployment publishes static score snapshots
about every five minutes; the browser checks published snapshots every 60
seconds. This repository includes the exporter without enabling a scheduled
Pages deployment.

Vercel reads the published JSON snapshots instead of calling Match Play. The
included `vercel.json` sets `SCOREHIGH_SNAPSHOT_URL` to
`https://ashodinventeal.github.io/scorehigh`. If you run your own publisher,
change that URL to its site root. It must publish `data/tournaments/<id>.json`
for every configured tournament. Vercel does not use local disk for this path
and refuses direct API reads if the snapshot URL is missing. Public HTML is
cached at Vercel's CDN for 60 seconds with 300 seconds of background revalidation.

The publisher is the only Match Play reader. Its SQLite store preserves successful
responses, request pacing, and cooldowns between runs; set `SCOREHIGH_CACHE_PATH`
to a persistent location and restore/save it in the publisher workflow. Live cards
are cached as complete lists for 120 seconds, rosters for 300 seconds, and requests
are spaced at least one second apart. Failed requests back off exponentially and
respect longer Retry-After values. Successful snapshots can be used for up to 24
hours during outages, with their original fetch timestamps. A failed export must
not replace the deployed site.

The homepage standings ticker is off by default. Enable **Homepage standings
ticker** in Display settings; the choice is saved on that device. It uses the same
ScoreHigh card totals as the standings, without a separate Match Play standings
request. Disabled tickers make no polling requests.

Here's how to build the public snapshot locally:

```sh
uv run python -m matchplay_score.export --output _site --base-path /scorehigh
```

This command uses real tournament data so be sure it is connected to where you are running the Matchplay tournament. The separate preview uses clearly labeled simulated data:

```sh
uv run python tools/build_tournament_demo.py --output .preview/demo/index.html
```

## Project structure

- `src/matchplay_score/`: scoring, cached API reads, Flask routes, and static export.
- `templates/components.html`: shared game banners and card progress labels.
- `static/matchplay.css`: simple standings and shared banners.
- `static/monitor.css` and `static/monitor.js`: event display layout and paging.
- `static/scorehigh.js`: display preferences, player tracking, disclosures, and refresh.
- `tests/`: offline scoring, rendering, export, and API-cache checks.
- `tools/`: demo export and browser checks.

## Checks and packages

```sh
uv run pytest
uv run ruff check src tests tools
uv build
```

The default tests run offline. To run the public API integration check:

```sh
uv run pytest -m integration
```

For browser checks, install Chromium once, then point the checker at the demo export or a running site:

```sh
uv run --with playwright playwright install chromium
uv run --with playwright python tools/check_ui.py --preview-dir .preview/demo
uv run --with playwright python tools/check_monitor_responsive.py --preview-dir .preview/demo
```

## Attribution and licensing

Original scoring code: Elia Lake / arborelia, copyright 2026. Original terms are retained unchanged in `LICENSE.txt`. Front-end Code and Design: Ash Harmeyer / Ashodin, copyright 2026.

Font notices are included in `src/matchplay_score/static/fonts/`. The small comma image preserves the outline from 7 Segment Display by Bernard Teo, based on Mylicia's segment font, under the included CC BY-SA 3.0 terms. Other font families retain their own notices. This repository does not relicense those assets.
