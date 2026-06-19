from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from research_agent.app.watchdog_storage import (
    InterestProfile,
    WatchdogDigest,
    WatchdogStorage,
    get_watchdog_storage,
    _CHECK_INTERVALS,
)
from research_agent.orchestration.watchdog import (
    run_watchdog_check,
    run_all_due_checks,
    format_digest_for_display,
    _is_newer,
    start_watchdog_scheduler,
    stop_watchdog_scheduler,
)


# ──────────────────────────────────────────────
# InterestProfile dataclass tests
# ──────────────────────────────────────────────

class TestInterestProfile:
    def test_default_fields(self):
        profile = InterestProfile(profile_id="p1", user_id="u1", topic="LLMs")
        assert profile.profile_id == "p1"
        assert profile.user_id == "u1"
        assert profile.topic == "LLMs"
        assert profile.keywords == []
        assert profile.authors == []
        assert profile.venues == []
        assert profile.check_interval == "daily"
        assert profile.last_checked_at == 0.0
        assert profile.enabled is True

    def test_with_all_fields(self):
        profile = InterestProfile(
            profile_id="p1",
            user_id="u1",
            topic="Transformers",
            keywords=["attention", "self-attention"],
            authors=["Vaswani"],
            venues=["NeurIPS"],
            check_interval="weekly",
        )
        assert profile.keywords == ["attention", "self-attention"]
        assert profile.authors == ["Vaswani"]
        assert profile.venues == ["NeurIPS"]
        assert profile.check_interval == "weekly"

    def test_created_at_set_automatically(self):
        profile = InterestProfile(profile_id="p1", user_id="u1", topic="AI")
        assert profile.created_at > 0


# ──────────────────────────────────────────────
# WatchdogDigest dataclass tests
# ──────────────────────────────────────────────

class TestWatchdogDigest:
    def test_default_fields(self):
        digest = WatchdogDigest(digest_id="d1", profile_id="p1", user_id="u1", topic="AI")
        assert digest.digest_id == "d1"
        assert digest.profile_id == "p1"
        assert digest.user_id == "u1"
        assert digest.topic == "AI"
        assert digest.new_papers == []
        assert digest.paper_count == 0
        assert digest.summary == ""

    def test_with_papers(self):
        papers = [{"title": "Paper A", "year": 2024}]
        digest = WatchdogDigest(
            digest_id="d1",
            profile_id="p1",
            user_id="u1",
            topic="AI",
            new_papers=papers,
            paper_count=len(papers),
            summary="Found 1 paper.",
        )
        assert len(digest.new_papers) == 1
        assert digest.paper_count == 1
        assert digest.summary == "Found 1 paper."


# ──────────────────────────────────────────────
# WatchdogStorage tests
# ──────────────────────────────────────────────

class TestWatchdogStorage:
    @pytest.fixture
    def storage(self, tmp_path: Path) -> WatchdogStorage:
        return WatchdogStorage(storage_dir=str(tmp_path / "watchdog"))

    @pytest.fixture
    def sample_profile(self) -> InterestProfile:
        return InterestProfile(
            profile_id="test-p1",
            user_id="test-u1",
            topic="Large Language Models",
            keywords=["transformers", "attention"],
            check_interval="daily",
        )

    def test_save_and_get_profile(self, storage: WatchdogStorage, sample_profile: InterestProfile):
        storage.save_profile(sample_profile)
        retrieved = storage.get_profile("test-p1")
        assert retrieved is not None
        assert retrieved.topic == "Large Language Models"
        assert retrieved.keywords == ["transformers", "attention"]

    def test_get_nonexistent_profile(self, storage: WatchdogStorage):
        assert storage.get_profile("nonexistent") is None

    def test_get_user_profiles(self, storage: WatchdogStorage):
        p1 = InterestProfile(profile_id="p1", user_id="u1", topic="Topic A")
        p2 = InterestProfile(profile_id="p2", user_id="u1", topic="Topic B")
        p3 = InterestProfile(profile_id="p3", user_id="u2", topic="Topic C")
        storage.save_profile(p1)
        storage.save_profile(p2)
        storage.save_profile(p3)

        u1_profiles = storage.get_user_profiles("u1")
        assert len(u1_profiles) == 2

        u2_profiles = storage.get_user_profiles("u2")
        assert len(u2_profiles) == 1

    def test_delete_profile(self, storage: WatchdogStorage, sample_profile: InterestProfile):
        storage.save_profile(sample_profile)
        assert storage.delete_profile("test-p1") is True
        assert storage.get_profile("test-p1") is None

    def test_delete_nonexistent_profile(self, storage: WatchdogStorage):
        assert storage.delete_profile("nonexistent") is False

    def test_list_profiles(self, storage: WatchdogStorage):
        p1 = InterestProfile(profile_id="p1", user_id="u1", topic="A")
        p2 = InterestProfile(profile_id="p2", user_id="u2", topic="B")
        storage.save_profile(p1)
        storage.save_profile(p2)
        assert len(storage.list_profiles()) == 2

    def test_get_enabled_profiles_only_returns_due(self, storage: WatchdogStorage):
        # A profile checked recently should not be due
        recent_profile = InterestProfile(
            profile_id="recent",
            user_id="u1",
            topic="Recent",
            check_interval="daily",
            last_checked_at=time.time() - 100,  # 100 seconds ago
            enabled=True,
        )
        # A profile checked long ago should be due
        due_profile = InterestProfile(
            profile_id="due",
            user_id="u1",
            topic="Due",
            check_interval="daily",
            last_checked_at=time.time() - 100000,  # > 1 day ago
            enabled=True,
        )
        # A disabled profile should not be returned even if due
        disabled_profile = InterestProfile(
            profile_id="disabled",
            user_id="u1",
            topic="Disabled",
            check_interval="daily",
            last_checked_at=0,
            enabled=False,
        )
        storage.save_profile(recent_profile)
        storage.save_profile(due_profile)
        storage.save_profile(disabled_profile)

        due = storage.get_enabled_profiles()
        profile_ids = [p.profile_id for p in due]
        assert "due" in profile_ids
        assert "disabled" not in profile_ids

    def test_update_last_checked(self, storage: WatchdogStorage, sample_profile: InterestProfile):
        storage.save_profile(sample_profile)
        old_time = sample_profile.last_checked_at
        storage.update_last_checked("test-p1")
        updated = storage.get_profile("test-p1")
        assert updated is not None
        assert updated.last_checked_at > old_time

    def test_save_and_get_digest(self, storage: WatchdogStorage):
        digest = WatchdogDigest(
            digest_id="d1",
            profile_id="p1",
            user_id="u1",
            topic="AI",
            new_papers=[{"title": "Paper"}],
            paper_count=1,
            summary="Found paper",
        )
        storage.save_digest(digest)
        digests = storage.get_user_digests("u1")
        assert len(digests) == 1
        assert digests[0].digest_id == "d1"
        assert digests[0].paper_count == 1

    def test_get_user_digests_respects_limit(self, storage: WatchdogStorage):
        for i in range(5):
            digest = WatchdogDigest(
                digest_id=f"d{i}",
                profile_id="p1",
                user_id="u1",
                topic="Topic",
                new_papers=[],
                paper_count=0,
                summary=f"Digest {i}",
            )
            storage.save_digest(digest)

        digests = storage.get_user_digests("u1", limit=3)
        assert len(digests) == 3


# ──────────────────────────────────────────────
# _is_newer helper tests
# ──────────────────────────────────────────────

class TestIsNewer:
    def test_paper_with_no_year(self):
        assert _is_newer({"title": "Paper"}, time.time()) is True

    def test_recent_paper(self):
        last_checked = time.time() - 86400 * 365 * 2  # 2 years ago
        assert _is_newer({"title": "Paper", "year": 2025}, last_checked) is True

    def test_old_paper(self):
        last_checked = time.time()
        assert _is_newer({"title": "Paper", "year": 2020}, last_checked) is False

    def test_string_year(self):
        last_checked = time.time() - 86400 * 365 * 2
        assert _is_newer({"title": "Paper", "year": "2024"}, last_checked) is True


# ──────────────────────────────────────────────
# Watchdog check tests
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestRunWatchdogCheck:
    async def test_no_paper_providers(self):
        profile = InterestProfile(profile_id="p1", user_id="u1", topic="AI")
        digest = await run_watchdog_check(profile, registry={})
        assert digest.paper_count == 0
        assert "No paper providers" in digest.summary

    async def test_with_papers_found(self):
        profile = InterestProfile(
            profile_id="p1",
            user_id="u1",
            topic="AI",
            last_checked_at=0,
        )
        mock_result = MagicMock(
            items=[
                {"title": "New Paper on AI", "year": 2025, "authors": ["Author A"]},
                {"title": "Another AI Paper", "year": 2024, "authors": ["Author B"]},
            ],
            warnings=[],
        )
        mock_registry = {
            "arxiv": MagicMock(
                provider_name="arxiv",
                is_searcher=True,
                search=MagicMock(return_value=mock_result),
                asearch=AsyncMock(return_value=mock_result),
            ),
        }

        with patch(
            "research_agent.orchestration.watchdog.arun_multi_source_search",
            new=AsyncMock(return_value={"arxiv": mock_result}),
        ):
            digest = await run_watchdog_check(profile, mock_registry)

            assert digest.paper_count == 2
            assert "Found 2 new papers" in digest.summary
            assert len(digest.new_papers) == 2

    async def test_deduplicates_by_title(self):
        profile = InterestProfile(
            profile_id="p1", user_id="u1", topic="AI", last_checked_at=0,
        )
        # Same paper returned by two providers
        mock_arxiv = MagicMock(
            items=[{"title": "Same Paper", "year": 2025, "authors": ["Author"]}],
            warnings=[],
        )
        mock_ss = MagicMock(
            items=[{"title": "Same Paper", "year": 2025, "authors": ["Author"]}],
            warnings=[],
        )

        with patch(
            "research_agent.orchestration.watchdog.arun_multi_source_search",
            new=AsyncMock(return_value={"arxiv": mock_arxiv, "semantic_scholar": mock_ss}),
        ):
            digest = await run_watchdog_check(profile, {"arxiv": mock_arxiv, "semantic_scholar": mock_ss})
            assert digest.paper_count == 1  # Deduplicated

    async def test_handles_search_exception(self):
        profile = InterestProfile(profile_id="p1", user_id="u1", topic="AI")

        with patch(
            "research_agent.orchestration.watchdog.arun_multi_source_search",
            new=AsyncMock(side_effect=Exception("API error")),
        ):
            digest = await run_watchdog_check(profile, {"arxiv": MagicMock(is_searcher=True)})
            assert digest.paper_count == 0
            assert "failed" in digest.summary.lower()


@pytest.mark.asyncio
class TestRunAllDueChecks:
    async def test_no_due_profiles(self):
        with patch(
            "research_agent.app.watchdog_storage.WatchdogStorage.get_enabled_profiles",
            return_value=[],
        ):
            digests = await run_all_due_checks({})
            assert digests == []


# ──────────────────────────────────────────────
# Digest formatting tests
# ──────────────────────────────────────────────

class TestFormatDigestForDisplay:
    def test_empty_digest(self):
        digest = WatchdogDigest(
            digest_id="d1",
            profile_id="p1",
            user_id="u1",
            topic="AI",
            new_papers=[],
            paper_count=0,
            summary="No new papers.",
        )
        formatted = format_digest_for_display(digest)
        assert "Research Watchdog Digest" in formatted
        assert "AI" in formatted
        assert "No new papers" in formatted

    def test_with_papers(self):
        papers = [
            {
                "title": "Important Paper",
                "year": 2025,
                "authors": ["Author A", "Author B"],
                "url": "https://example.com/paper",
                "watchdog_provider": "arxiv",
            }
        ]
        digest = WatchdogDigest(
            digest_id="d1",
            profile_id="p1",
            user_id="u1",
            topic="Machine Learning",
            new_papers=papers,
            paper_count=1,
            summary="Found 1 paper.",
        )
        formatted = format_digest_for_display(digest)
        assert "Important Paper" in formatted
        assert "Author A, Author B" in formatted
        assert "arxiv" in formatted


# ──────────────────────────────────────────────
# Scheduler lifecycle tests
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestSchedulerLifecycle:
    async def test_start_and_stop(self):
        task = await start_watchdog_scheduler({}, interval_seconds=99999)
        assert task is not None
        assert not task.done()

        await stop_watchdog_scheduler()
        assert task.done()

    async def test_double_stop_is_safe(self):
        await stop_watchdog_scheduler()  # No-op
        await stop_watchdog_scheduler()  # Should not raise


# ──────────────────────────────────────────────
# Integration test: full profile→digest flow
# ──────────────────────────────────────────────

@pytest.mark.asyncio
class TestFullWatchdogFlow:
    async def test_profile_to_digest(self, tmp_path: Path):
        """End-to-end: create profile, run check, retrieve digest."""
        storage = WatchdogStorage(storage_dir=str(tmp_path / "watchdog"))

        # Create and save a profile
        profile = InterestProfile(
            profile_id="integration-test",
            user_id="test-user",
            topic="Reinforcement Learning",
            keywords=["deep RL", "policy gradients"],
            check_interval="daily",
            last_checked_at=0,
        )
        storage.save_profile(profile)

        # Mock search to return papers
        mock_items = [
            {"title": "Advances in Deep RL", "year": 2025, "authors": ["Author X"]},
            {"title": "Policy Gradient Methods", "year": 2024, "authors": ["Author Y"]},
        ]
        mock_result = MagicMock(items=mock_items, warnings=[])

        mock_registry = {
            "arxiv": MagicMock(
                provider_name="arxiv",
                is_searcher=True,
                search=MagicMock(return_value=mock_result),
                asearch=AsyncMock(return_value=mock_result),
            ),
        }

        with (
            patch(
                "research_agent.orchestration.watchdog.arun_multi_source_search",
                new=AsyncMock(return_value={"arxiv": mock_result}),
            ),
            patch(
                "research_agent.app.watchdog_storage.get_watchdog_storage",
                return_value=storage,
            ),
        ):
            digests = await run_all_due_checks(mock_registry)

            assert len(digests) >= 1
            assert digests[0].paper_count == 2

            # Verify digest was saved
            saved_digests = storage.get_user_digests("test-user")
            assert len(saved_digests) >= 1

            # Verify last_checked was updated
            updated_profile = storage.get_profile("integration-test")
            assert updated_profile is not None
            assert updated_profile.last_checked_at > 0
