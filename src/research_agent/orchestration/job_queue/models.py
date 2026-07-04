from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class JobPriority(Enum):
    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0


class JobStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class JobType(Enum):
    RESEARCH_RUN = "research_run"
    EXPORT_PDF = "export_pdf"
    EXPORT_BLOG = "export_blog"
    DIGEST_EMAIL = "digest_email"
    TREND_REPORT = "trend_report"
    WATCHDOG_CHECK = "watchdog_check"


@dataclass
class Job:
    """A job in the async job queue."""
    job_id: str
    job_type: JobType
    priority: JobPriority = JobPriority.NORMAL
    status: JobStatus = JobStatus.PENDING
    user_id: str = ""
    session_id: str = ""
    run_id: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    progress: float = 0.0  # 0.0–1.0
    result: dict[str, Any] | None = None
    error: str | None = None
    worker_hostname: str | None = None
    max_retries: int = 0
    retry_count: int = 0
    timeout_seconds: int = 600

    def to_dict(self) -> dict[str, str]:
        """Serialize to flat string dict for Redis hash storage."""
        d: dict[str, str] = {
            "job_id": self.job_id,
            "job_type": self.job_type.value if isinstance(self.job_type, JobType) else str(self.job_type),
            "priority": str(self.priority.value if isinstance(self.priority, JobPriority) else self.priority),
            "status": self.status.value if isinstance(self.status, JobStatus) else str(self.status),
            "user_id": self.user_id,
            "session_id": self.session_id,
            "run_id": self.run_id,
            "params": json.dumps(self.params),
            "created_at": str(self.created_at),
            "started_at": str(self.started_at) if self.started_at is not None else "",
            "completed_at": str(self.completed_at) if self.completed_at is not None else "",
            "progress": str(self.progress),
            "result": json.dumps(self.result) if self.result is not None else "",
            "error": self.error or "",
            "worker_hostname": self.worker_hostname or "",
            "max_retries": str(self.max_retries),
            "retry_count": str(self.retry_count),
            "timeout_seconds": str(self.timeout_seconds),
        }
        return d
