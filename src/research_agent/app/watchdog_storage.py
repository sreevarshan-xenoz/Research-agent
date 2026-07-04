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
class NotificationPrefs:
    """Notification preferences for a watchdog subscription."""
    email_enabled: bool = False
    email_address: str = ""
    push_enabled: bool = False
    min_relevance_score: float = 0.0
    max_papers_per_digest: int = 20


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
    notification_prefs: NotificationPrefs = field(default_factory=NotificationPrefs)
    seen_fingerprints: set[str] = field(default_factory=set)


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
    relevance_scores: list[float] = field(default_factory=list)
    email_sent: bool = False


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
        data = asdict(profile)
        # Convert set to list for JSON serialization
        data["seen_fingerprints"] = list(data.get("seen_fingerprints", []))
        # Convert nested dataclass to dict
        data["notification_prefs"] = asdict(profile.notification_prefs)
        profiles[profile.profile_id] = data
        self._write_json(self._profiles_path, profiles)

    def get_profile(self, profile_id: str) -> InterestProfile | None:
        """Get a single profile by ID."""
        profiles = self._load_profiles()
        data = profiles.get(profile_id)
        if data is None:
            return None
        return self._deserialize_profile(data)

    def get_user_profiles(self, user_id: str) -> list[InterestProfile]:
        """Get all profiles for a given user."""
        profiles = self._load_profiles()
        return [
            self._deserialize_profile(data)
            for data in profiles.values()
            if data.get("user_id") == user_id
        ]

    def list_profiles(self) -> list[InterestProfile]:
        """Get all profiles across all users."""
        profiles = self._load_profiles()
        return [self._deserialize_profile(data) for data in profiles.values()]

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

    def update_notification_prefs(self, profile_id: str, prefs: NotificationPrefs) -> bool:
        """Update notification preferences for a profile. Returns True if profile existed."""
        profiles = self._load_profiles()
        if profile_id not in profiles:
            return False
        profiles[profile_id]["notification_prefs"] = asdict(prefs)
        self._write_json(self._profiles_path, profiles)
        return True

    def add_seen_fingerprints(self, profile_id: str, fingerprints: set[str]) -> None:
        """Add paper fingerprints to a profile's seen set."""
        profiles = self._load_profiles()
        if profile_id in profiles:
            existing = set(profiles[profile_id].get("seen_fingerprints", []))
            existing.update(fingerprints)
            profiles[profile_id]["seen_fingerprints"] = list(existing)
            self._write_json(self._profiles_path, profiles)

    def get_seen_fingerprints(self, profile_id: str) -> set[str]:
        """Get the set of seen paper fingerprints for a profile."""
        profiles = self._load_profiles()
        data = profiles.get(profile_id)
        if data is None:
            return set()
        return set(data.get("seen_fingerprints", []))

    def mark_digest_email_sent(self, digest_id: str) -> None:
        """Mark a digest as having its email sent."""
        digests = self._load_digests()
        if digest_id in digests:
            digests[digest_id]["email_sent"] = True
            self._write_json(self._digests_path, digests)

    def get_unsent_digests(self) -> list[WatchdogDigest]:
        """Get all digests that have not had their email sent yet."""
        digests = self._load_digests()
        return [
            WatchdogDigest(**self._deserialize_digest(data))
            for data in digests.values()
            if not data.get("email_sent", False)
        ]

    # ── Digest CRUD ──────────────────────────────────────────

    def save_digest(self, digest: WatchdogDigest) -> None:
        """Save a generated digest."""
        digests = self._load_digests()
        digests[digest.digest_id] = self._serialize_digest(digest)
        self._write_json(self._digests_path, digests)

    def get_user_digests(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[WatchdogDigest]:
        """Get the most recent digests for a user."""
        digests = self._load_digests()
        user_digests = [
            WatchdogDigest(**self._deserialize_digest(data))
            for data in digests.values()
            if data.get("user_id") == user_id
        ]
        user_digests.sort(key=lambda d: d.generated_at, reverse=True)
        return user_digests[:limit]

    def get_all_digests(self, limit: int = 50) -> list[WatchdogDigest]:
        """Get all recent digests across all users."""
        digests = self._load_digests()
        all_digests = [
            WatchdogDigest(**self._deserialize_digest(data))
            for data in digests.values()
        ]
        all_digests.sort(key=lambda d: d.generated_at, reverse=True)
        return all_digests[:limit]

    # ── Internal helpers ──────────────────────────────────────

    def _load_profiles(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            if not self._profiles_path.exists():
                return {}
            try:
                raw = json.loads(self._profiles_path.read_text(encoding="utf-8"))
                return dict(raw)
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("Failed to load watchdog profiles: %s", exc)
                return {}

    def _load_digests(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            if not self._digests_path.exists():
                return {}
            try:
                raw = json.loads(self._digests_path.read_text(encoding="utf-8"))
                return dict(raw)
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
    def _deserialize_profile(data: dict[str, Any]) -> InterestProfile:
        """Deserialize a profile dict back into an InterestProfile.

        Handles JSON→Python type conversions for nested dataclasses and sets.
        """
        d = dict(data)
        # Convert list back to set for seen_fingerprints
        if "seen_fingerprints" in d:
            d["seen_fingerprints"] = set(d["seen_fingerprints"])
        # Convert dict back to NotificationPrefs dataclass
        if "notification_prefs" in d and isinstance(d["notification_prefs"], dict):
            d["notification_prefs"] = NotificationPrefs(**d["notification_prefs"])
        return InterestProfile(**d)

    @staticmethod
    def _serialize_digest(digest: WatchdogDigest) -> dict[str, Any]:
        d = asdict(digest)
        # Ensure relevance_scores is a list, not tuple
        d["relevance_scores"] = list(d.get("relevance_scores", []))
        return d

    @staticmethod
    def _deserialize_digest(data: dict[str, Any]) -> dict[str, Any]:
        # Convert relevance_scores list back
        scores = data.get("relevance_scores", [])
        data["relevance_scores"] = list(scores)
        return data

    @staticmethod
    def _get_interval_seconds(interval: str) -> int:
        return _CHECK_INTERVALS.get(interval.lower(), DEFAULT_CHECK_INTERVAL)

    @staticmethod
    def get_interval_seconds(interval: str) -> int:
        """Public accessor for interval seconds conversion."""
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
