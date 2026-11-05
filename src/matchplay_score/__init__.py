"""ScoreHigh tournament scoring front end."""

from argparse import ArgumentParser
from importlib.metadata import version


def main() -> None:
    from waitress import serve

    from .branding import SITE_DESCRIPTION
    from .web import app

    parser = ArgumentParser(description=SITE_DESCRIPTION)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--version", action="version", version=version("matchplay-score")
    )
    args = parser.parse_args()
    serve(app, host=args.host, port=args.port)
