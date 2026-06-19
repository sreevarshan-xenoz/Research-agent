"""Tests for auth.py utilities: double-check locking in _get_jwt_secret()."""
from __future__ import annotations

import threading

import pytest

from research_agent.app.auth import _get_jwt_secret


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_jwt_cache():
    """Save and restore the module-level _JWT_SECRET_CACHE between tests."""
    import research_agent.app.auth as auth_mod

    before = auth_mod._JWT_SECRET_CACHE
    auth_mod._JWT_SECRET_CACHE = None
    yield
    auth_mod._JWT_SECRET_CACHE = before


# ---------------------------------------------------------------------------
# _get_jwt_secret — basic contract
# ---------------------------------------------------------------------------

class TestGetJwtSecretContract:
    """_get_jwt_secret() returns a valid string and caches it."""

    def test_returns_non_empty_string(self):
        """The function returns a non-empty string."""
        secret = _get_jwt_secret()
        assert isinstance(secret, str)
        assert len(secret) > 0

    def test_returns_same_object_on_second_call(self):
        """Second call returns the exact same object (first-check fast path)."""
        first = _get_jwt_secret()
        second = _get_jwt_secret()
        assert first is second  # identity proves caching, not just equality

    def test_default_secret_when_no_env_override(self, monkeypatch):
        """Without env override, returns the dev default secret."""
        monkeypatch.delenv("SECRET_KEY", raising=False)
        import research_agent.app.auth as auth_mod
        auth_mod._JWT_SECRET_CACHE = None

        secret = _get_jwt_secret()
        assert isinstance(secret, str)
        assert len(secret) > 0


# ---------------------------------------------------------------------------
# _get_jwt_secret — double-check locking correctness
# ---------------------------------------------------------------------------

class TestGetJwtSecretDoubleCheckLock:
    """Verify the double-checked locking pattern works correctly."""

    def test_fast_path_returns_cached_value(self, monkeypatch):
        """First-check fast path: when cache is set, return immediately without lock."""
        monkeypatch.setattr(
            "research_agent.app.auth._JWT_SECRET_CACHE",
            "pre-cached-secret",
        )

        secret = _get_jwt_secret()
        assert secret == "pre-cached-secret"

    def test_second_check_path(self, monkeypatch):
        """Second-check path: cache set between first check and lock acquisition.

        This simulates the scenario where a concurrent thread sets the cache
        after the first check but before the lock is acquired.
        """
        lock_acquisitions = 0

        class TrackingLock:
            """Wrapper that counts lock acquisitions."""
            def __enter__(self):
                nonlocal lock_acquisitions
                lock_acquisitions += 1
                # On first acquisition, simulate another thread having set the cache
                if lock_acquisitions == 1:
                    monkeypatch.setattr(
                        "research_agent.app.auth._JWT_SECRET_CACHE",
                        "set-by-other-thread",
                    )
                return self

            def __exit__(self, *args):
                pass

        monkeypatch.setattr(
            "research_agent.app.auth._JWT_SECRET_LOCK",
            TrackingLock(),
        )
        # Ensure cache starts as None
        monkeypatch.setattr(
            "research_agent.app.auth._JWT_SECRET_CACHE",
            None,
        )

        secret = _get_jwt_secret()

        # The second check should have found the cache set by "other thread"
        assert secret == "set-by-other-thread"
        assert lock_acquisitions == 1

    def test_concurrent_calls_return_same_value(self):
        """Multiple concurrent callers all get the same cached value."""
        results: list[str] = []
        exceptions: list[Exception] = []
        lock = threading.Lock()

        def call_get_jwt_secret():
            try:
                val = _get_jwt_secret()
                with lock:
                    results.append(val)
            except Exception as exc:
                with lock:
                    exceptions.append(exc)

        threads = [threading.Thread(target=call_get_jwt_secret) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"
        assert len(results) == 8
        # All threads should see the same value
        assert all(r == results[0] for r in results)

    def test_lock_not_acquired_when_cache_hot(self, monkeypatch):
        """When cache is already set, the lock is never acquired (fast path)."""
        lock_used = False

        class FailOnEnterLock:
            def __enter__(self):
                nonlocal lock_used
                lock_used = True
                return self
            def __exit__(self, *args):
                pass

        monkeypatch.setattr(
            "research_agent.app.auth._JWT_SECRET_CACHE",
            "hot-cache",
        )
        monkeypatch.setattr(
            "research_agent.app.auth._JWT_SECRET_LOCK",
            FailOnEnterLock(),
        )

        _get_jwt_secret()
        assert not lock_used, "Lock was acquired on hot cache (fast path missed)"


# ---------------------------------------------------------------------------
# _get_jwt_secret — fallback on settings failure
# ---------------------------------------------------------------------------

class TestGetJwtSecretFallback:
    """_get_jwt_secret() falls back when settings are unavailable."""

    def test_fallback_to_env_when_settings_fails(self, monkeypatch):
        """When load_settings raises, falls back to SECRET_KEY env var."""
        monkeypatch.setenv("SECRET_KEY", "my-test-env-secret")

        # Replace load_settings with a function that raises
        monkeypatch.setattr(
            "research_agent.config.load_settings",
            lambda: (_ for _ in ()).throw(RuntimeError("settings unavailable")),
        )

        secret = _get_jwt_secret()
        assert secret == "my-test-env-secret"

    def test_fallback_to_dev_default_when_no_env(self, monkeypatch):
        """When both settings and SECRET_KEY env fail, falls back to dev default."""
        monkeypatch.delenv("SECRET_KEY", raising=False)

        monkeypatch.setattr(
            "research_agent.config.load_settings",
            lambda: (_ for _ in ()).throw(RuntimeError("settings unavailable")),
        )

        secret = _get_jwt_secret()
        # Dev default from the source code
        assert secret == "DEV_SECRET_DO_NOT_USE_IN_PROD"
