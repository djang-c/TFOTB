"""Background research jobs for the API: one at a time, rate-limited, in memory.

Jobs run in a worker thread so a request returns at once. Only one job runs at a time and a rolling
hourly limit stops a client from queueing endless paid work. State is in memory: a restart forgets
finished jobs, but everything a job stored is in the claim store and the run log.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

log = logging.getLogger("atlas.research")


class RateLimited(RuntimeError):
    pass


@dataclass
class Job:
    job_id: str
    terms: list[str]
    status: str = "queued"  # queued | running | done | failed
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

    def public(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id, "status": self.status, "terms": self.terms, "created_at": self.created_at,
            "finished_at": self.finished_at, "result": self.result, "error": self.error,
        }


class JobManager:
    def __init__(self, max_per_hour: int = 6, keep: int = 50) -> None:
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="research")
        self._jobs: dict[str, Job] = {}
        self._starts: deque[float] = deque()
        self._lock = threading.Lock()
        self.max_per_hour, self.keep = max_per_hour, keep

    def submit(self, terms: list[str], work: Callable[[], dict[str, Any]]) -> Job:
        with self._lock:
            now = time.monotonic()
            while self._starts and now - self._starts[0] > 3600:
                self._starts.popleft()
            if len(self._starts) >= self.max_per_hour:
                raise RateLimited(f"at most {self.max_per_hour} research jobs per hour")
            self._starts.append(now)
            job = Job(uuid.uuid4().hex[:12], terms)
            self._jobs[job.job_id] = job
            for old in list(self._jobs)[: max(0, len(self._jobs) - self.keep)]:
                del self._jobs[old]
        self._pool.submit(self._run, job, work)
        return job

    def _run(self, job: Job, work: Callable[[], dict[str, Any]]) -> None:
        job.status = "running"
        try:
            job.result = work()
            job.status = "done"
        except Exception as exc:
            # the full error goes to the server log; the API shows only its type (messages can hold paths or keys)
            log.exception("research job %s failed", job.job_id)
            job.error, job.status = f"{type(exc).__name__} (see the server log)", "failed"
        job.finished_at = datetime.now(UTC).isoformat(timespec="seconds")

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def recent(self, n: int = 10) -> list[Job]:
        return list(self._jobs.values())[-n:][::-1]

    def wait(self, job_id: str, timeout: float = 5.0) -> None:  # for tests
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            j = self._jobs.get(job_id)
            if j and j.status in {"done", "failed"}:
                return
            time.sleep(0.01)
