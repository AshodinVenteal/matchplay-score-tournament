# matchplay-score-tournament

Support code for a 90s-style card format pinball tournament, where a card includes your entire score on each pinball table you play (times a multiplier to balance different machines against each other).

## Running locally

Make sure `uv` (the all-purpose Python environment manager) is installed. Then:

    uv run waitress-serve --host 127.0.0.1 matchplay_score.web:app

## Hosted version

https://tpc-high-score.vercel.app