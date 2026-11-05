"""Shared setup for local browser checks."""

import os
from pathlib import Path


def launch_browser(playwright):
    executable = os.environ.get("SCOREHIGH_BROWSER")
    if not executable and os.name == "nt":
        cache = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
        installed = sorted(cache.glob("chromium-*/chrome-win*/chrome.exe"))
        if installed:
            executable = str(installed[-1])
    return playwright.chromium.launch(executable_path=executable)
