from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from research_agent.tools.base import BaseToolAdapter
from research_agent.tools.registry import arun_multi_source_search
from research_agent.app.watchdog_storage import (
    InterestProfile,
    WatchdogDigest,
    get_watchdog_storage,
)


logger = logging.getLogger(__name__)


# Module-level scheduler task reference for lifecycle management
_scheduler_task: asyncio.Task[None] | None = None


def _is_newer(paper: dict[str, Any], last_checked: float) -> bool:
    """Check if a paper was published after the last check time.

    Uses the paper's 'year' field as a proxy, since exact timestamps
    are not always available from all providers.
    """
    year_val = paper.get("year")
    if year_val is None:
        return True
    year = year_val
    if isinstance(year, str):
        try:
            year = int(year)
        except (ValueError, TypeError):
            return True
    elif not isinstance(year, (int, float)):
        return True
    if year == 0:
        return True
    # If paper year is greater than or equal to the year of last check, consider it new
    last_check_year = float(time.gmtime(last_checked).tm_year) if last_checked > 0 else 0
    return year >= last_check_year or not last_checked



async def run_watchdog_check(
    profile: InterestProfile,
    registry: dict[str, BaseToolAdapter],
) -> WatchdogDigest:
    """Execute a single watchdog check for one interest profile.

    Searches across paper providers for new papers matching the profile's
    topic and keywords, then generates a digest.

    Args:
        profile: The interest profile to check.
        registry: Tool registry for paper searches.

    Returns:
        A WatchdogDigest with new papers found.
    """
    logger.info("Watchdog checking profile '%s': %s", profile.profile_id, profile.topic)

    # Build the search query from the topic + keywords
    query_parts = [profile.topic]
    if profile.keywords:
        query_parts.extend(profile.keywords)
    if profile.authors:
        query_parts.extend(profile.authors)
    query = " ".join(query_parts)

    # Limit providers to paper-focused ones for monitoring
    paper_registry = {
        name: adapter
        for name, adapter in registry.items()
        if name in ("arxiv", "semantic_scholar", "openalex", "pubmed")
        and getattr(adapter, "is_searcher", True)
    }

    if not paper_registry:
        logger.warning("No paper providers available for watchdog check")
        return WatchdogDigest(
            digest_id=f"digest-{uuid.uuid4().hex[:8]}",
            profile_id=profile.profile_id,
            user_id=profile.user_id,
            topic=profile.topic,
            new_papers=[],
            paper_count=0,
            summary="No paper providers available for search.",
        )

    try:
        result_map = await arun_multi_source_search(
            query=query,
            registry=paper_registry,
            limit=10,
        )

        new_papers: list[dict[str, Any]] = []
        seen_titles: set[str] = set()

        for provider, result in result_map.items():
            for item in result.items:
                if not isinstance(item, dict):
                    continue
                title = item.get("title", "")
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)

                if _is_newer(item, profile.last_checked_at):
                    item["watchdog_provider"] = provider
                    new_papers.append(item)

        # Sort by year descending (newest first)
        new_papers.sort(
            key=lambda p: (
                int(p.get("year", 0)) if isinstance(p.get("year"), (int, str)) and str(p.get("year", "0")).isdigit() else 0
            ),
            reverse=True,
        )

        paper_count = len(new_papers)
        if paper_count == 0:
            summary = f"No new papers found for '{profile.topic}' since last check."
        else:
            summary = f"Found {paper_count} new paper{'s' if paper_count != 1 else ''} on '{profile.topic}'."

        return WatchdogDigest(
            digest_id=f"digest-{uuid.uuid4().hex[:8]}",
            profile_id=profile.profile_id,
            user_id=profile.user_id,
            topic=profile.topic,
            new_papers=new_papers,
            paper_count=paper_count,
            summary=summary,
        )

    except Exception as exc:
        logger.exception("Watchdog check failed for profile '%s'", profile.profile_id)
        return WatchdogDigest(
            digest_id=f"digest-{uuid.uuid4().hex[:8]}",
            profile_id=profile.profile_id,
            user_id=profile.user_id,
            topic=profile.topic,
            new_papers=[],
            paper_count=0,
            summary=f"Watchdog check failed: {exc}",
        )


async def run_all_due_checks(
    registry: dict[str, BaseToolAdapter],
) -> list[WatchdogDigest]:
    """Run watchdog checks for all enabled profiles that are due.

    Args:
        registry: Tool registry for paper searches.

    Returns:
        List of WatchdogDigests generated.
    """
    storage = get_watchdog_storage()
    due_profiles = storage.get_enabled_profiles()

    if not due_profiles:
        logger.debug("No watchdog profiles due for check")
        return []

    logger.info("Running watchdog checks for %d due profiles", len(due_profiles))

    digests: list[WatchdogDigest] = []
    for profile in due_profiles:
        try:
            digest = await run_watchdog_check(profile, registry)
            digests.append(digest)

            # Save the digest and update the profile's last_checked timestamp
            storage.save_digest(digest)
            storage.update_last_checked(profile.profile_id)

            logger.info(
                "Watchdog digest for '%s': %d new papers",
                profile.topic,
                digest.paper_count,
            )
        except Exception:
            logger.exception("Watchdog check failed for profile '%s'", profile.profile_id)

    return digests


async def start_watchdog_scheduler(
    registry: dict[str, BaseToolAdapter],
    interval_seconds: int = 3600,
) -> asyncio.Task[None]:
    """Start the background watchdog scheduler.

    Runs a loop that periodically checks all due profiles and generates
    digests. The scheduler runs as an asyncio Task.

    Args:
        registry: Tool registry for paper searches.
        interval_seconds: How often to check for due profiles (default: 1 hour).

    Returns:
        The scheduler asyncio Task. Cancel it to stop.
    """
    global _scheduler_task

    async def _loop() -> None:
        logger.info(
            "Watchdog scheduler started (check interval: %d seconds)",
            interval_seconds,
        )
        while True:
            try:
                await run_all_due_checks(registry)
            except asyncio.CancelledError:
                logger.info("Watchdog scheduler cancelled")
                raise
            except Exception as exc:
                logger.exception("Watchdog scheduler error: %s", exc)

            await asyncio.sleep(interval_seconds)

    _scheduler_task = asyncio.create_task(_loop())
    return _scheduler_task


async def stop_watchdog_scheduler() -> None:
    """Stop the background watchdog scheduler by cancelling its task."""
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass  # Expected on cancellation
        _scheduler_task = None
        logger.info("Watchdog scheduler stopped")


def format_digest_for_display(digest: WatchdogDigest) -> str:
    """Format a watchdog digest as a human-readable string.

    Args:
        digest: The watchdog digest to format.

    Returns:
        Formatted digest string with summary and paper list.
    """
    lines = [
        "# Research Watchdog Digest",
        f"**Topic:** {digest.topic}",
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(digest.generated_at))}",
        f"**Papers found:** {digest.paper_count}",
        "",
        digest.summary,
        "",
    ]

    if digest.new_papers:
        lines.append("## New Papers")
        lines.append("")
        for i, paper in enumerate(digest.new_papers[:20], 1):
            title = paper.get("title", "Untitled")
            authors = paper.get("authors", ["Unknown"])
            if isinstance(authors, list):
                authors_str = ", ".join(authors[:3])
                if len(authors) > 3:
                    authors_str += " et al."
            else:
                authors_str = str(authors)
            year = paper.get("year", "n.d.")
            url = paper.get("url", "")
            provider = paper.get("watchdog_provider", paper.get("provider", "unknown"))

            lines.append(f"### {i}. {title}")
            lines.append(f"**Authors:** {authors_str}")
            lines.append(f"**Year:** {year}")
            lines.append(f"**Source:** {provider}")
            if url:
                lines.append(f"**URL:** {url}")
            lines.append("")

    return "\n".join(lines)
