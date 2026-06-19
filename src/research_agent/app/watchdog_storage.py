from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


_CHECK_INTERVALS = {
    "daily": 86400,
    "weekly": 604800,
    "biweekly": 1209600,
    "monthly": 2592000,
}

DEFAULT_CHECK_INTERVAL = 86400  # daily


@dataclass
class InterestProfile:
    """A user's research interest subscription for the watchdog.

    Stores the topic, keywords, target authors, venues, and schedule
    for monitoring. New papers matching this profile are collected
    into a digest.
    """
    profile_id: str
    user_id: str
    topic: str
    keywords: list[str] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)
    venues: list[str] = field(default_factory=list)
    check_interval: str = "daily"
    last_checked_at: float = 0.0
    created_at: float = field(default_factory=time.time)
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WatchdogDigest:
    """A digest of new papers found by the watchdog for a profile."""
    digest_id: str
    profile_id: str
    user_id: str
    topic: str
    generated_at: float = field(default_factory=time.time)
    new_papers: list[dict[str, Any]] = field(default_factory=list)
    paper_count: int = 0
    summary: str = ""


class WatchdogStorage:
    """JSON-file-backed storage for interest profiles and digests.

    Thread-safe via a reentrant lock. Profiles and digests are stored
    as separate JSON files in .runtime/watchdog/.
    """

    def __init__(self, storage_dir: str | Path = ".runtime/watchdog") -> None:
        self._storage_dir = Path(storage_dir)
        self._profiles_path = self._storage_dir / "profiles.json"
        self._digests_path = self._storage_dir / "digests.json"
        self._lock = threading.Lock()

        self._storage_dir.mkdir(parents=True, exist_ok=True)

    # ── Profile CRUD ──────────────────────────────────────────

    def save_profile(self, profile: InterestProfile) -> None:
        """Save or update an interest profile."""
        profiles = self._load_profiles()
        profiles[profile.profile_id] = asdict(profile)
        self._write_json(self._profiles_path, profiles)

    def get_profile(self, profile_id: str) -> InterestProfile | None:
        """Get a single profile by ID."""
        profiles = self._load_profiles()
        data = profiles.get(profile_id)
        if data is None:
            return None
        return InterestProfile(**data)

    def get_user_profiles(self, user_id: str) -> list[InterestProfile]:
        """Get all profiles for a given user."""
        profiles = self._load_profiles()
        return [
            InterestProfile(**data)
            for data in profiles.values()
            if data.get("user_id") == user_id
        ]

    def list_profiles(self) -> list[InterestProfile]:
        """Get all profiles across all users."""
        profiles = self._load_profiles()
        return [InterestProfile(**data) for data in profiles.values()]

    def get_enabled_profiles(self) -> list[InterestProfile]:
        """Get all enabled profiles whose check interval has elapsed."""
        profiles = self.list_profiles()
        now = time.time()
        return [
            p
            for p in profiles
            if p.enabled and (now - p.last_checked_at) >= self._get_interval_seconds(p.check_interval)
        ]

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile. Returns True if it existed."""
        profiles = self._load_profiles()
        if profile_id not in profiles:
            return False
        del profiles[profile_id]
        self._write_json(self._profiles_path, profiles)
        return True

    def update_last_checked(self, profile_id: str) -> None:
        """Update the last_checked_at timestamp for a profile."""
        profiles = self._load_profiles()
        if profile_id in profiles:
            profiles[profile_id]["last_checked_at"] = time.time()
            self._write_json(self._profiles_path, profiles)

    # ── Digest CRUD ──────────────────────────────────────────

    def save_digest(self, digest: WatchdogDigest) -> None:
        """Save a generated digest."""
        digests = self._load_digests()
        digests[digest.digest_id] = asdict(digest)
        self._write_json(self._digests_path, digests)

    def get_user_digests(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[WatchdogDigest]:
        """Get the most recent digests for a user."""
        digests = self._load_digests()
        user_digests = [
            WatchdogDigest(**data)
            for data in digests.values()
            if data.get("user_id") == user_id
        ]
        user_digests.sort(key=lambda d: d.generated_at, reverse=True)
        return user_digests[:limit]

    # ── Internal helpers ──────────────────────────────────────

    def _load_profiles(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            if not self._profiles_path.exists():
                return {}
            try:
                return dict(json.loads(self._profiles_path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("Failed to load watchdog profiles: %s", exc)
                return {}

    def _load_digests(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            if not self._digests_path.exists():
                return {}
            try:
                return dict(json.loads(self._digests_path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("Failed to load watchdog digests: %s", exc)
                return {}

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        with self._lock:
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    @staticmethod
    def _get_interval_seconds(interval: str) -> int:
        return _CHECK_INTERVALS.get(interval.lower(), DEFAULT_CHECK_INTERVAL)


# Module-level singleton storage instance
_default_storage: WatchdogStorage | None = None
_storage_lock = threading.Lock()


def get_watchdog_storage() -> WatchdogStorage:
    """Get or create the module-level WatchdogStorage singleton."""
    global _default_storage
    if _default_storage is not None:
        return _default_storage
    with _storage_lock:
        if _default_storage is None:
            _default_storage = WatchdogStorage()
        return _default_storage
