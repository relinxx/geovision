"""
Job Store - Thread-safe in-memory job tracking

Manages job lifecycle and state with thread-safe operations.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, Optional
from dataclasses import dataclass, field, asdict

from services.redis_store import get_redis_store


@dataclass
class JobSteps:
    """Individual step statuses."""
    environment: str = "pending"
    zoning: str = "pending"
    merge: str = "pending"
    spatial: str = "pending"
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class Job:
    """Job data structure."""
    job_id: str
    status: str  # created, running, completed, failed
    progress: int  # 0-100
    stage: str
    steps: JobSteps = field(default_factory=JobSteps)
    result: Optional[Dict] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "progress": self.progress,
            "stage": self.stage,
            "steps": self.steps.to_dict(),
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at
        }

    def to_storage_dict(self) -> Dict[str, Any]:
        """Convert job to a JSON-serializable dictionary for persistence."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "progress": self.progress,
            "stage": self.stage,
            "steps": self.steps.to_dict(),
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_storage_dict(cls, payload: Dict[str, Any]) -> "Job":
        """Rehydrate a Job from persisted storage."""
        steps_payload = payload.get("steps") or {}
        created_at_raw = payload.get("created_at")
        created_at = datetime.now()
        if isinstance(created_at_raw, str) and created_at_raw:
            try:
                created_at = datetime.fromisoformat(created_at_raw)
            except ValueError:
                created_at = datetime.now()

        return cls(
            job_id=str(payload.get("job_id") or ""),
            status=str(payload.get("status") or "created"),
            progress=int(payload.get("progress") or 0),
            stage=str(payload.get("stage") or "initializing"),
            steps=JobSteps(
                environment=str(steps_payload.get("environment") or "pending"),
                zoning=str(steps_payload.get("zoning") or "pending"),
                merge=str(steps_payload.get("merge") or "pending"),
                spatial=str(steps_payload.get("spatial") or "pending"),
            ),
            result=payload.get("result"),
            error=payload.get("error"),
            created_at=created_at,
        )


_DEFAULT_REDIS_STORE = object()


class JobStore:
    """
    Thread-safe in-memory job store.
    
    Uses asyncio.Lock for async-safe operations in FastAPI.
    """
    
    def __init__(self, redis_store: Any = _DEFAULT_REDIS_STORE):
        """Initialize job store with empty storage and lock."""
        self._jobs: Dict[str, Job] = {}
        self._lock = asyncio.Lock()
        self._max_jobs = self._env_int("ORCHESTRATOR_MAX_JOBS", default=2000, minimum=100)
        retention_hours = self._env_int(
            "ORCHESTRATOR_JOB_RETENTION_HOURS",
            default=24,
            minimum=1,
        )
        self._retention_seconds = retention_hours * 3600
        self._redis = get_redis_store() if redis_store is _DEFAULT_REDIS_STORE else redis_store
        self._jobs_index_key = "orchestrator:jobs:index"

    @staticmethod
    def _env_int(name: str, default: int, minimum: int) -> int:
        raw_value = os.getenv(name)
        if raw_value is None:
            return max(default, minimum)
        try:
            return max(int(raw_value), minimum)
        except (TypeError, ValueError):
            return max(default, minimum)

    def _prune_locked(self) -> None:
        now_ts = datetime.now().timestamp()
        stale_job_ids = [
            job_id
            for job_id, job in self._jobs.items()
            if (now_ts - job.created_at.timestamp()) > self._retention_seconds
        ]
        for job_id in stale_job_ids:
            self._jobs.pop(job_id, None)

        overflow = len(self._jobs) - self._max_jobs
        if overflow <= 0:
            return

        terminal_statuses = {"completed", "failed"}
        sortable = sorted(
            self._jobs.values(),
            key=lambda job: (
                0 if job.status in terminal_statuses else 1,
                job.created_at,
            ),
        )
        for job in sortable[:overflow]:
            self._jobs.pop(job.job_id, None)

    def _job_key(self, job_id: str) -> str:
        return f"orchestrator:job:{job_id}"

    def _save_job_redis(self, job: Job) -> None:
        if not self._redis:
            return
        self._redis.set_json(
            self._job_key(job.job_id),
            job.to_storage_dict(),
            ttl_seconds=self._retention_seconds,
        )
        self._redis.zadd(self._jobs_index_key, {job.job_id: job.created_at.timestamp()})
        self._redis.expire(self._jobs_index_key, self._retention_seconds)

        overflow = self._redis.zcard(self._jobs_index_key) - self._max_jobs
        if overflow <= 0:
            return

        overflow_ids = self._redis.zrange(self._jobs_index_key, 0, overflow - 1)
        if not overflow_ids:
            return
        for overflow_job_id in overflow_ids:
            self._redis.delete(self._job_key(overflow_job_id))
        self._redis.zrem(self._jobs_index_key, *overflow_ids)

    def _get_job_redis(self, job_id: str) -> Optional[Job]:
        if not self._redis:
            return None
        payload = self._redis.get_json(self._job_key(job_id))
        if not isinstance(payload, dict):
            self._redis.zrem(self._jobs_index_key, job_id)
            return None
        return Job.from_storage_dict(payload)

    def _list_jobs_redis(self) -> Dict[str, Job]:
        if not self._redis:
            return {}
        jobs: Dict[str, Job] = {}
        stale_job_ids: list[str] = []
        for job_id in self._redis.zrange(self._jobs_index_key, 0, -1):
            payload = self._redis.get_json(self._job_key(job_id))
            if not isinstance(payload, dict):
                stale_job_ids.append(job_id)
                continue
            job = Job.from_storage_dict(payload)
            jobs[job.job_id] = job
        if stale_job_ids:
            self._redis.zrem(self._jobs_index_key, *stale_job_ids)
        return jobs
    
    async def create_job(self, job_id: str) -> Job:
        """
        Create a new job with initial state.
        
        Parameters
        ----------
        job_id : str
            Unique job identifier
            
        Returns
        -------
        Job
            Created job instance
        """
        async with self._lock:
            if self._redis:
                job = Job(
                    job_id=job_id,
                    status="created",
                    progress=0,
                    stage="initializing"
                )
                self._save_job_redis(job)
                return job

            self._prune_locked()
            job = Job(
                job_id=job_id,
                status="created",
                progress=0,
                stage="initializing"
            )
            self._jobs[job_id] = job
            return job
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """
        Retrieve a job by ID.
        
        Parameters
        ----------
        job_id : str
            Job identifier
            
        Returns
        -------
        Optional[Job]
            Job instance or None if not found
        """
        async with self._lock:
            if self._redis:
                return self._get_job_redis(job_id)
            self._prune_locked()
            return self._jobs.get(job_id)
    
    async def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        stage: Optional[str] = None,
        result: Optional[Dict] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Update job fields atomically.
        
        Parameters
        ----------
        job_id : str
            Job identifier
        status : Optional[str]
            New status
        progress : Optional[int]
            New progress (0-100)
        stage : Optional[str]
            New stage name
        result : Optional[Dict]
            Job result data
        error : Optional[str]
            Error message
            
        Returns
        -------
        bool
            True if job was updated, False if not found
        """
        async with self._lock:
            if self._redis:
                job = self._get_job_redis(job_id)
                if not job:
                    return False

                if status is not None:
                    job.status = status
                if progress is not None:
                    job.progress = progress
                if stage is not None:
                    job.stage = stage
                if result is not None:
                    job.result = result
                if error is not None:
                    job.error = error

                self._save_job_redis(job)
                return True

            self._prune_locked()
            job = self._jobs.get(job_id)
            if not job:
                return False
            
            if status is not None:
                job.status = status
            if progress is not None:
                job.progress = progress
            if stage is not None:
                job.stage = stage
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error
            
            return True
    
    async def update_step(self, job_id: str, step_name: str, step_status: str) -> bool:
        """
        Update individual step status.
        
        Parameters
        ----------
        job_id : str
            Job identifier
        step_name : str
            Step name (environment, zoning, merge, spatial)
        step_status : str
            Step status (pending, running, completed, failed, skipped)
            
        Returns
        -------
        bool
            True if updated, False if job not found
        """
        async with self._lock:
            if self._redis:
                job = self._get_job_redis(job_id)
                if not job:
                    return False

                if hasattr(job.steps, step_name):
                    setattr(job.steps, step_name, step_status)
                    self._save_job_redis(job)
                    return True
                return False

            self._prune_locked()
            job = self._jobs.get(job_id)
            if not job:
                return False
            
            if hasattr(job.steps, step_name):
                setattr(job.steps, step_name, step_status)
                return True
            
            return False
    
    async def list_jobs(self) -> Dict[str, Job]:
        """
        List all jobs (for debugging/admin).
        
        Returns
        -------
        Dict[str, Job]
            Dictionary of all jobs
        """
        async with self._lock:
            if self._redis:
                return self._list_jobs_redis()
            self._prune_locked()
            return dict(self._jobs)


# Global singleton instance
_job_store: Optional[JobStore] = None


def get_job_store() -> JobStore:
    """
    Get or create the global job store instance.
    
    Returns
    -------
    JobStore
        Singleton job store instance
    """
    global _job_store
    if _job_store is None:
        _job_store = JobStore()
    return _job_store
