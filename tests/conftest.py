import pytest

from matchplay_score import matchplay_api as api


@pytest.fixture(autouse=True)
def isolated_snapshot_store(tmp_path, monkeypatch):
    monkeypatch.setenv("SCOREHIGH_CACHE_PATH", str(tmp_path / "matchplay.sqlite3"))
    monkeypatch.delenv("SCOREHIGH_SNAPSHOT_URL", raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setattr(api, "_feed_cache", {})
    monkeypatch.setattr(api, "_feed_retry_at", 0)
