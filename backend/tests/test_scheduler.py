"""Tests for the nightly refresh: it must be opt-in, never 'everyone in the DB'."""
import asyncio

import scheduler
from scheduler import get_tracked_usernames, nightly_update


class TestTrackedUsernames:
    def test_unset_means_nobody(self, monkeypatch):
        monkeypatch.delenv("TRACKED_USERNAMES", raising=False)
        assert get_tracked_usernames() == []

    def test_parses_and_normalizes_list(self, monkeypatch):
        monkeypatch.setenv("TRACKED_USERNAMES", " Alice, bob ,,")
        assert get_tracked_usernames() == ["alice", "bob"]


def test_nightly_does_no_work_without_a_list(monkeypatch):
    """The 02:00 UTC outages came from refreshing every stored user uncapped."""
    monkeypatch.delenv("TRACKED_USERNAMES", raising=False)

    async def boom(*args, **kwargs):
        raise AssertionError("nightly job should not ingest when nothing is tracked")

    monkeypatch.setattr(scheduler, "ingest_user_games", boom)
    asyncio.run(nightly_update())
