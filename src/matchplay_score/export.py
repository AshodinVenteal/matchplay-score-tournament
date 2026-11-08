"""Build the Flask UI into a GitHub Pages-compatible score snapshot."""

import argparse
from datetime import UTC, datetime
from importlib.metadata import distribution
from pathlib import Path
from shutil import copytree
from urllib.parse import quote, unquote

from . import web
from .matchplay_api import get_cards, get_tournament_data_cached
from .tournament import parse_card, parse_tournament


def export_site(output: Path, base_path: str = "") -> list[str]:
    base_path = "/" + base_path.strip("/") if base_path.strip("/") else ""
    if any(part in {".", ".."} for part in base_path.split("/")):
        raise ValueError("Base path must not contain relative segments")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    routes = ["/"]
    for tournament_id in web.TOURNAMENT_INFO:
        tournament = parse_tournament(get_tournament_data_cached(tournament_id))
        cards = [parse_card(item, tournament) for item in get_cards(tournament_id)]
        routes.extend(
            [
                f"/ranking/{tournament_id}",
                f"/machines/{tournament_id}",
                f"/how-it-works/{tournament_id}",
                f"/monitor/{tournament_id}",
            ]
        )
        for player in sorted({card.player_name for card in cards}):
            routes.append(
                f"/player/{tournament_id}/{quote(player.replace(' ', '_'), safe='')}"
            )
    previous_snapshot = web.app.config.get("SNAPSHOT_AT")
    web.app.config["SNAPSHOT_AT"] = datetime.now(UTC).isoformat()
    written = []
    try:
        with web.app.test_client() as client:
            for route in routes:
                response = client.get(
                    route, environ_overrides={"SCRIPT_NAME": base_path}
                )
                if response.status_code != 200:
                    raise RuntimeError(
                        f"Export failed for {route}: HTTP {response.status_code}"
                    )
                decoded_route = unquote(route).lstrip("/")
                if any(part in {".", ".."} for part in decoded_route.split("/")):
                    raise ValueError("Export route contains relative segments")
                destination = (output / decoded_route / "index.html").resolve()
                if not destination.is_relative_to(output):
                    raise ValueError("Export route escapes the output directory")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(
                    response.get_data(as_text=True), encoding="utf-8"
                )
                written.append(destination.relative_to(output).as_posix())
            missing = client.get(
                "/not-a-page", environ_overrides={"SCRIPT_NAME": base_path}
            )
            (output / "404.html").write_text(
                missing.get_data(as_text=True), encoding="utf-8"
            )
        copytree(Path(web.app.static_folder), output / "static", dirs_exist_ok=True)
        license_path = Path(__file__).resolve().parents[2] / "LICENSE.txt"
        if not license_path.is_file():
            package = distribution("matchplay-score")
            for item in package.files or []:
                if item.name == "LICENSE.txt" and "licenses" in item.parts:
                    license_path = Path(package.locate_file(item))
                    break
        if license_path.is_file():
            (output / "LICENSE.txt").write_bytes(license_path.read_bytes())
        (output / ".nojekyll").write_text("", encoding="utf-8")
    finally:
        web.app.config["SNAPSHOT_AT"] = previous_snapshot
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("_site"))
    parser.add_argument("--base-path", default="/scorehigh")
    args = parser.parse_args()
    pages = export_site(args.output, args.base_path)
    print(f"Exported {len(pages)} pages to {args.output.resolve()}")


if __name__ == "__main__":
    main()
