from __future__ import annotations

import asyncio
import hashlib
import logging
import re
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


# ─── Fingerprint helpers ────────────────────────────────────────


def _compute_fingerprint(paper: dict[str, Any]) -> str:
    """Compute a stable fingerprint for a paper.

    Uses arxiv ID, DOI, URL, or a hash of (normalized title + year)
    to create a unique identifier that persists across checks.

    Args:
        paper: Paper dict from any provider.

    Returns:
        A fingerprint string (hash-based if no stable ID available).
    """
    # Try stable IDs first
    paper_id = paper.get("paper_id") or ""
    if paper_id:
        return f"pid:{paper_id}"

    doi = paper.get("doi") or ""
    if doi:
        return f"doi:{doi}"

    url = paper.get("url") or ""
    if "arxiv.org" in url or "semanticscholar" in url:
        return f"url:{url}"

    # Fall back to normalized title + year hash
    title = (paper.get("title") or "").strip().lower()
    # Remove common noise
    title = re.sub(r"[^a-z0-9\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    year = str(paper.get("year", ""))
    raw = f"{title}|{year}"
    return f"hash:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


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
    last_check_year = float(time.gmtime(last_checked).tm_year) if last_checked > 0 else 0
    return year >= last_check_year or not last_checked


# ─── Relevance scoring ──────────────────────────────────────────


def _compute_relevance_score(
    paper: dict[str, Any],
    profile: InterestProfile,
) -> float:
    """Compute a relevance score (0.0-1.0) for a paper against a profile.

    Uses keyword overlap, author match, venue match, and freshness.
    Higher scores indicate better alignment with the user's interests.

    Args:
        paper: Paper dict with title, authors, snippet, etc.
        profile: The interest profile to score against.

    Returns:
        Relevance score between 0.0 and 1.0.
    """
    scores: list[float] = []
    weights: list[float] = []

    title = (paper.get("title") or "").lower()
    snippet = (paper.get("snippet") or "").lower()
    paper_text = f"{title} {snippet}"
    authors = [a.lower().strip() for a in (paper.get("authors") or []) if isinstance(a, str)]

    # 1. Topic match in title (weight: 3x)
    topic_words = set(re.findall(r"\w+", profile.topic.lower()))
    if topic_words:
        title_words = set(re.findall(r"\w+", title))
        overlap = len(topic_words & title_words) / max(len(topic_words), 1)
        scores.append(min(1.0, overlap * 1.5))
        weights.append(3.0)

    # 2. Keyword match in title + snippet (weight: 2x)
    if profile.keywords:
        keyword_hits = sum(1 for kw in profile.keywords if kw.lower() in paper_text)
        keyword_score = min(1.0, keyword_hits / max(len(profile.keywords), 1))
        scores.append(keyword_score)
        weights.append(2.0)

    # 3. Author match (weight: 2x)
    if profile.authors and authors:
        profile_authors_lower = [a.lower().strip() for a in profile.authors]
        author_hits = sum(1 for a in authors if any(pa in a or a in pa for pa in profile_authors_lower))
        scores.append(min(1.0, author_hits / max(len(profile.authors), 1)))
        weights.append(2.0)

    # 4. Venue match (weight: 1x)
    venue = (paper.get("journal") or paper.get("booktitle") or "").lower()
    if profile.venues and venue:
        venue_hits = sum(1 for v in profile.venues if v.lower() in venue)
        scores.append(min(1.0, venue_hits / max(len(profile.venues), 1)))
        weights.append(1.0)

    # 5. Recency bonus (weight: 1x) — newer papers score higher
    year = paper.get("year")
    if isinstance(year, (int, float)) and year > 2020:
        recency = min(1.0, (year - 2020) / 5.0)  # 2020→0.0, 2025→1.0
        scores.append(recency)
        weights.append(1.0)

    if not scores:
        return 0.5  # Neutral score when no criteria match

    weighted_sum = sum(s * w for s, w in zip(scores, weights))
    total_weight = sum(weights)
    return round(weighted_sum / total_weight, 3)


# ─── Watchdog check ─────────────────────────────────────────────


async def run_watchdog_check(
    profile: InterestProfile,
    registry: dict[str, BaseToolAdapter],
) -> WatchdogDigest:
    """Execute a single watchdog check for one interest profile.

    Searches across paper providers for new papers matching the profile's
    topic and keywords, then generates a digest with relevance scores.

    Uses true diff detection via paper fingerprints to avoid re-reporting
    papers that were already seen in previous checks.

    Args:
        profile: The interest profile to check.
        registry: Tool registry for paper searches.

    Returns:
        A WatchdogDigest with new papers found and relevance scores.
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
            limit=15,  # Increased from 10 to catch more candidates
        )

        storage = get_watchdog_storage()
        seen_fingerprints = storage.get_seen_fingerprints(profile.profile_id)
        new_papers: list[dict[str, Any]] = []
        new_fingerprints: set[str] = set()
        seen_titles: set[str] = set()
        relevance_scores: list[float] = []

        for provider, result in result_map.items():
            for item in result.items:
                if not isinstance(item, dict):
                    continue
                title = item.get("title", "")
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)

                item["watchdog_provider"] = provider
                fp = _compute_fingerprint(item)

                # True diff detection: skip if fingerprint already seen
                if fp in seen_fingerprints:
                    continue

                # Also check year-based freshness as a secondary filter
                if not _is_newer(item, profile.last_checked_at):
                    continue

                # Compute relevance score
                score = _compute_relevance_score(item, profile)
                item["relevance_score"] = score

                new_papers.append(item)
                new_fingerprints.add(fp)
                relevance_scores.append(score)

        # Save fingerprints so they won't be re-reported
        if new_fingerprints:
            storage.add_seen_fingerprints(profile.profile_id, new_fingerprints)

        # Apply min relevance threshold from notification prefs
        min_score = profile.notification_prefs.min_relevance_score
        if min_score > 0 and new_papers:
            filtered: list[dict[str, Any]] = []
            filtered_scores: list[float] = []
            for p, s in zip(new_papers, relevance_scores):
                if s >= min_score:
                    filtered.append(p)
                    filtered_scores.append(s)
            new_papers = filtered
            relevance_scores = filtered_scores

        # Sort by relevance descending
        paper_score_pairs = list(zip(new_papers, relevance_scores))
        paper_score_pairs.sort(key=lambda x: x[1], reverse=True)
        new_papers = [p for p, _ in paper_score_pairs]
        relevance_scores = [s for _, s in paper_score_pairs]

        # Limit to max per digest
        max_papers = profile.notification_prefs.max_papers_per_digest
        if max_papers > 0 and len(new_papers) > max_papers:
            new_papers = new_papers[:max_papers]
            relevance_scores = relevance_scores[:max_papers]

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
            relevance_scores=relevance_scores,
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
    digests. After each check cycle, sends email digests for profiles
    that have email notifications enabled.
    The scheduler runs as an asyncio Task.

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
                digests = await run_all_due_checks(registry)
                # Try to send email notifications for digests with new papers
                for digest in digests:
                    if digest.paper_count > 0:
                        await _maybe_send_digest_email(digest)
            except asyncio.CancelledError:
                logger.info("Watchdog scheduler cancelled")
                raise
            except Exception as exc:
                logger.exception("Watchdog scheduler error: %s", exc)

            await asyncio.sleep(interval_seconds)

    _scheduler_task = asyncio.create_task(_loop())
    return _scheduler_task


async def _maybe_send_digest_email(digest: WatchdogDigest) -> None:
    """Send an email digest if the profile has email notifications enabled."""
    storage = get_watchdog_storage()
    profile = storage.get_profile(digest.profile_id)
    if profile is None:
        return

    prefs = profile.notification_prefs
    if not prefs.email_enabled or not prefs.email_address:
        return

    try:
        from research_agent.orchestration.digest_email import build_html_digest_email
        html_content = build_html_digest_email(digest)

        # Attempt to send via configured SMTP
        from research_agent.config import load_settings
        settings = load_settings()

        email_cfg = settings.watchdog_email
        smtp_host = email_cfg.smtp_host
        smtp_port = email_cfg.smtp_port
        smtp_user = email_cfg.smtp_user
        smtp_password = str(email_cfg.smtp_password)
        from_email = email_cfg.from_email

        if not smtp_host:
            logger.warning("SMTP not configured — skipping email for digest %s", digest.digest_id)
            return

        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Research Watchdog: {digest.paper_count} new papers on '{digest.topic}'"
        msg["From"] = from_email
        msg["To"] = prefs.email_address

        text_part = MIMEText(format_digest_for_display(digest), "plain", "utf-8")
        html_part = MIMEText(html_content, "html", "utf-8")
        msg.attach(text_part)
        msg.attach(html_part)

        loop = asyncio.get_running_loop()

        def _send() -> None:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                if smtp_port == 587:
                    server.starttls()
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.sendmail(from_email, [prefs.email_address], msg.as_string())

        await loop.run_in_executor(None, _send)

        storage.mark_digest_email_sent(digest.digest_id)
        logger.info(
            "Digest email sent for '%s' to %s",
            digest.topic,
            prefs.email_address,
        )
    except Exception as exc:
        logger.exception("Failed to send digest email for '%s': %s", digest.topic, exc)


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
            score = paper.get("relevance_score", None)

            lines.append(f"### {i}. {title}")
            lines.append(f"**Authors:** {authors_str}")
            lines.append(f"**Year:** {year}")
            lines.append(f"**Source:** {provider}")
            if score is not None:
                lines.append(f"**Relevance:** {score:.0%}")
            if url:
                lines.append(f"**URL:** {url}")
            lines.append("")

    return "\n".join(lines)
