import pytest

from matchplay_score import matchplay_api as api


@pytest.fixture(autouse=True)
def isolated_live_cache(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setattr(api, "_cache", {})
    monkeypatch.setattr(api, "_runtime", None)
    monkeypatch.setattr(api, "_next_request", 0)
    monkeypatch.setattr(api, "_cooldown_until", 0)
    monkeypatch.setattr(api, "_failures", 0)
