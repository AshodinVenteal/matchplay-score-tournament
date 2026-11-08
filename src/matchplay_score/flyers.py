"""Local promotional flyer images used by the optional monitor decoration."""

import json
from pathlib import Path

_sources = Path(__file__).parent / "static/images/flyers/sources.json"
FLYER_IMAGES = {
    name: source["file"]
    for name, source in json.loads(_sources.read_text(encoding="utf-8")).items()
}
