import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime
from ..models import Job, JobStatus

logger = logging.getLogger(__name__)


class JobManager:
    """In-memory job storage and management"""
    
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = asyncio.Lock()
    
    async def create_job(self, job: Job) -> Job:
        async with self._lock:
            self._jobs[job.id] = job
            logger.info(f"Created job {job.id} of type {job.job_type}")
            return job
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)
    
    async def update_job(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        result_url: Optional[str] = None,
        error: Optional[str] = None,
        provider_job_id: Optional[str] = None
    ) -> Optional[Job]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            
            if status is not None:
                job.status = status
                if status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                    job.completed_at = datetime.utcnow()
            
            if progress is not None:
                job.progress = progress
            if message is not None:
                job.message = message
            if result_url is not None:
                job.result_url = result_url
            if error is not None:
                job.error = error
            if provider_job_id is not None:
                job.provider_job_id = provider_job_id
            
            logger.info(f"Updated job {job_id}: status={job.status}, progress={job.progress}")
            return job
    
    async def list_jobs(self, job_type: Optional[str] = None) -> list[Job]:
        jobs = list(self._jobs.values())
        if job_type:
            jobs = [j for j in jobs if j.job_type == job_type]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)


# Global job manager instance
job_manager = JobManager()

