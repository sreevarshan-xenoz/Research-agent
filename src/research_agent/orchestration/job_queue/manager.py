from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
import uuid
from typing import Any, Callable

from research_agent.config import load_settings
from research_agent.orchestration.job_queue.models import Job, JobPriority, JobStatus, JobType

logger = logging.getLogger(__name__)


class JobManager:
    """Async job queue manager using Redis.

    Manages job lifecycle: enqueue → process → complete/fail/cancel.
    Uses Redis Sorted Sets for priority-ordered queues.
    Supports per-user concurrency limits, job cancellation, and progress tracking.
    """

    JOB_PREFIX = "research_job:"
    QUEUE_KEY = "research_job_queue"
    ACTIVE_KEY = "research_job_active"
    USER_ACTIVE_KEY = "research_job_user_active:"
    PROGRESS_KEY = "research_job_progress:"

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._local_registry: dict[str, Callable] = {}
        self._handlers: dict[str, Callable] = {}
        self._worker_id = f"worker-{socket.gethostname()}-{uuid.uuid4().hex[:6]}"

    # ------------------------------------------------------------------
    # Redis connection
    # ------------------------------------------------------------------

    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as aioredis
            settings = load_settings()
            pool = await self._create_pool(settings.redis.url, settings.redis.max_connections)
            self._redis = aioredis.Redis(connection_pool=pool)
        return self._redis

    async def _create_pool(self, url: str, max_connections: int):
        import redis.asyncio as aioredis
        return aioredis.ConnectionPool.from_url(
            url,
            max_connections=max_connections,
            socket_connect_timeout=5,
            socket_timeout=10,
            retry_on_timeout=True,
            health_check_interval=30,
        )

    async def close(self):
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None

    # ------------------------------------------------------------------
    # Job handlers
    # ------------------------------------------------------------------

    def register_handler(self, job_type: JobType | str, handler: Callable) -> None:
        key = job_type.value if isinstance(job_type, JobType) else job_type
        self._handlers[key] = handler
        logger.debug("Registered handler for job type: %s", key)

    # ------------------------------------------------------------------
    # Enqueue / Dequeue
    # ------------------------------------------------------------------

    async def enqueue(
        self,
        job_type: JobType | str,
        params: dict[str, Any] | None = None,
        priority: JobPriority = JobPriority.NORMAL,
        user_id: str = "",
        session_id: str = "",
        run_id: str = "",
        max_retries: int = 0,
        timeout_seconds: int = 600,
    ) -> Job:
        """Enqueue a new job."""
        job = Job(
            job_id=f"job-{uuid.uuid4().hex[:12]}",
            job_type=job_type if isinstance(job_type, JobType) else JobType(job_type),
            priority=priority,
            status=JobStatus.QUEUED,
            user_id=user_id,
            session_id=session_id,
            run_id=run_id,
            params=params or {},
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
        )

        r = await self._get_redis()
        # Store job data as JSON hash
        await r.hset(f"{self.JOB_PREFIX}{job.job_id}", mapping=job.to_dict())

        # Add to priority queue (score = priority value + timestamp for FIFO within priority)
        score = (priority.value * 1_000_000) + time.time()
        await r.zadd(self.QUEUE_KEY, {job.job_id: score})

        logger.info("Enqueued job %s (type=%s, priority=%s)", job.job_id, job.job_type.value, priority.name)
        return job

    async def dequeue(self, timeout: float = 5.0) -> Job | None:
        """Dequeue the next highest-priority job (blocking)."""
        r = await self._get_redis()

        while True:
            # Get lowest-score job from sorted set (highest priority)
            jobs = await r.zpopmin(self.QUEUE_KEY, count=1)
            if not jobs:
                if timeout <= 0:
                    return None
                await asyncio.sleep(0.5)
                timeout -= 0.5
                continue

            job_id = jobs[0][0].decode() if isinstance(jobs[0][0], bytes) else jobs[0][0]

            # Mark as running
            job_data = await self._get_job_data(job_id)
            if job_data is None:
                continue

            job_data["status"] = JobStatus.RUNNING.value
            job_data["started_at"] = time.time()
            job_data["worker_hostname"] = self._worker_id
            await r.hset(f"{self.JOB_PREFIX}{job_id}", mapping=job_data)

            # Track active jobs per user
            if job_data.get("user_id"):
                await r.sadd(f"{self.USER_ACTIVE_KEY}{job_data['user_id']}", job_id)

            await r.sadd(self.ACTIVE_KEY, job_id)

            job = self._dict_to_job(job_data, job_id)
            return job

    # ------------------------------------------------------------------
    # Job progress & status updates
    # ------------------------------------------------------------------

    async def update_progress(self, job_id: str, progress: float, result: dict[str, Any] | None = None) -> None:
        """Update job progress (0.0–1.0)."""
        r = await self._get_redis()
        await r.hset(f"{self.JOB_PREFIX}{job_id}", "progress", str(progress))
        if result:
            await r.hset(f"{self.JOB_PREFIX}{job_id}", "result", json.dumps(result))

    async def complete_job(self, job_id: str, result: dict[str, Any] | None = None) -> None:
        """Mark a job as completed."""
        r = await self._get_redis()
        now = time.time()
        await r.hset(f"{self.JOB_PREFIX}{job_id}", mapping={
            "status": JobStatus.COMPLETED.value,
            "completed_at": str(now),
            "progress": "1.0",
            "result": json.dumps(result) if result else "{}",
        })
        await self._cleanup_active(job_id)

    async def fail_job(self, job_id: str, error: str) -> None:
        """Mark a job as failed."""
        r = await self._get_redis()
        now = time.time()
        updates = {
            "status": JobStatus.FAILED.value,
            "completed_at": str(now),
            "error": error,
        }
        await r.hset(f"{self.JOB_PREFIX}{job_id}", mapping=updates)
        await self._cleanup_active(job_id)
        logger.warning("Job %s failed: %s", job_id, error[:200])

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued or running job."""
        r = await self._get_redis()
        job_data = await self._get_job_data(job_id)
        if job_data is None:
            return False

        current_status = job_data.get("status", "")
        if current_status in (JobStatus.COMPLETED.value, JobStatus.CANCELLED.value, JobStatus.FAILED.value):
            return False

        await r.hset(f"{self.JOB_PREFIX}{job_id}", "status", JobStatus.CANCELLED.value)
        await r.zrem(self.QUEUE_KEY, job_id)
        await self._cleanup_active(job_id)
        return True

    async def _cleanup_active(self, job_id: str) -> None:
        """Remove job from active sets."""
        r = await self._get_redis()
        await r.srem(self.ACTIVE_KEY, job_id)
        job_data = await self._get_job_data(job_id)
        if job_data and job_data.get("user_id"):
            await r.srem(f"{self.USER_ACTIVE_KEY}{job_data['user_id']}", job_id)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    async def get_job(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        job_data = await self._get_job_data(job_id)
        if job_data is None:
            return None
        return self._dict_to_job(job_data, job_id)

    async def list_jobs(
        self,
        user_id: str | None = None,
        status: JobStatus | None = None,
        limit: int = 20,
    ) -> list[Job]:
        """List jobs with optional filtering."""
        r = await self._get_redis()

        if user_id:
            job_ids = await r.smembers(f"{self.USER_ACTIVE_KEY}{user_id}")
            job_ids = [j.decode() if isinstance(j, bytes) else j for j in job_ids]
        else:
            # Get all job keys
            keys = await r.keys(f"{self.JOB_PREFIX}*")
            job_ids = list(set(k.decode().replace(self.JOB_PREFIX, "") for k in keys))

        jobs: list[Job] = []
        for jid in job_ids[:limit]:
            job_data = await self._get_job_data(jid)
            if job_data:
                job = self._dict_to_job(job_data, jid)
                if status is None or job.status == status:
                    jobs.append(job)

        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    async def get_queue_depth(self) -> int:
        """Get number of jobs waiting in the queue."""
        r = await self._get_redis()
        return await r.zcard(self.QUEUE_KEY)

    async def get_active_count(self) -> int:
        """Get number of currently running jobs."""
        r = await self._get_redis()
        return await r.scard(self.ACTIVE_KEY)

    async def get_user_active_count(self, user_id: str) -> int:
        """Get number of active jobs for a specific user."""
        r = await self._get_redis()
        return await r.scard(f"{self.USER_ACTIVE_KEY}{user_id}")

    async def check_concurrency_limit(self, user_id: str, max_active: int = 3) -> bool:
        """Check if user has reached their concurrency limit."""
        active = await self.get_user_active_count(user_id)
        return active < max_active

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    async def run_worker(self, poll_interval: float = 1.0) -> None:
        """Run the worker loop: dequeue jobs and execute them."""
        logger.info("Job worker started (id=%s)", self._worker_id)
        while True:
            try:
                job = await self.dequeue(timeout=poll_interval)
                if job is None:
                    continue

                handler = self._handlers.get(job.job_type.value)
                if handler is None:
                    await self.fail_job(job.job_id, f"No handler registered for job type: {job.job_type.value}")
                    continue

                logger.info("Processing job %s (type=%s)", job.job_id, job.job_type.value)
                try:
                    result = await handler(job, self)
                    await self.complete_job(job.job_id, result)
                except Exception as exc:
                    error_msg = f"{type(exc).__name__}: {exc}"
                    if job.retry_count < job.max_retries:
                        # Re-enqueue with incremented retry count
                        job.retry_count += 1
                        r = await self._get_redis()
                        score = (job.priority.value * 1_000_000) + time.time()
                        await r.zadd(self.QUEUE_KEY, {job.job_id: score})
                        await r.hset(f"{self.JOB_PREFIX}{job.job_id}", "retry_count", str(job.retry_count))
                        logger.warning("Job %s failed, retry %d/%d: %s", job.job_id, job.retry_count, job.max_retries, error_msg[:200])
                    else:
                        await self.fail_job(job.job_id, error_msg)
            except asyncio.CancelledError:
                logger.info("Job worker stopped (id=%s)", self._worker_id)
                break
            except Exception as exc:
                logger.error("Job worker error: %s", exc)
                await asyncio.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_job_data(self, job_id: str) -> dict[str, Any] | None:
        """Get job data from Redis as a dict."""
        r = await self._get_redis()
        raw = await r.hgetall(f"{self.JOB_PREFIX}{job_id}")
        if not raw:
            return None
        decoded: dict[str, Any] = {}
        for k, v in raw.items():
            key = k.decode() if isinstance(k, bytes) else k
            val = v.decode() if isinstance(v, bytes) else v
            decoded[key] = val
        return decoded

    def _dict_to_job(self, data: dict[str, Any], job_id: str) -> Job:
        """Convert a dict (from Redis) back to a Job object."""
        return Job(
            job_id=job_id,
            job_type=JobType(data.get("job_type", "research_run")),
            priority=JobPriority(int(data.get("priority", JobPriority.NORMAL.value))),
            status=JobStatus(data.get("status", JobStatus.PENDING.value)),
            user_id=data.get("user_id", ""),
            session_id=data.get("session_id", ""),
            run_id=data.get("run_id", ""),
            params=json.loads(data.get("params", "{}")),
            created_at=float(data.get("created_at", time.time())),
            started_at=float(data["started_at"]) if data.get("started_at") else None,
            completed_at=float(data["completed_at"]) if data.get("completed_at") else None,
            progress=float(data.get("progress", 0.0)),
            result=json.loads(data["result"]) if data.get("result") else None,
            error=data.get("error"),
            worker_hostname=data.get("worker_hostname"),
            max_retries=int(data.get("max_retries", 0)),
            retry_count=int(data.get("retry_count", 0)),
            timeout_seconds=int(data.get("timeout_seconds", 600)),
        )


# Module-level singleton
_manager: JobManager | None = None


def get_job_manager() -> JobManager:
    """Get the module-level JobManager singleton."""
    global _manager
    if _manager is None:
        _manager = JobManager()
    return _manager

