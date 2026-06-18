"""
Orchestrator Service - Core orchestration logic

Manages job lifecycle and coordinates multi-stage execution.
"""
import asyncio
import logging
import uuid
from typing import List

from services.job_store import get_job_store
from utils.helpers import env_int
from services.orchestrator_steps import (
    run_environment_stage,
    run_zoning_stage,
    merge_outputs,
    run_spatial_stage
)

logger = logging.getLogger(__name__)


class OrchestratorService:
    """
    Orchestrator service for managing multi-stage job execution.
    
    Coordinates environment, zoning, merge, and spatial stages with
    progress tracking and error handling.
    """
    
    def __init__(self):
        """Initialize orchestrator service."""
        self.job_store = get_job_store()
        self._max_concurrent_jobs = env_int(
            "ORCHESTRATOR_MAX_CONCURRENT_JOBS",
            default=4,
            minimum=1,
        )
        self._job_semaphore = asyncio.Semaphore(self._max_concurrent_jobs)
        self._stage_timeout_seconds = env_int(
            "ORCHESTRATOR_STAGE_TIMEOUT_SECONDS",
            default=300,
            minimum=10,
        )
        self._active_tasks: set[asyncio.Task] = set()

    async def create_job(self, parcel_ids: List[str], enable_spatial: bool = False) -> str:
        """
        Create a new orchestration job and start background execution.
        
        Parameters
        ----------
        parcel_ids : List[str]
            List of parcel IDs to process
        enable_spatial : bool
            Whether to enable spatial generation stage
            
        Returns
        -------
        str
            Job ID
        """
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Create job in store
        await self.job_store.create_job(job_id)
        
        logger.info(f"[JOB {job_id}] Created job for {len(parcel_ids)} parcels (spatial={enable_spatial})")
        
        # Start background execution
        task = asyncio.create_task(self._execute_job(job_id, parcel_ids, enable_spatial))
        self._active_tasks.add(task)
        task.add_done_callback(self._active_tasks.discard)
        
        return job_id
    
    async def _execute_job(self, job_id: str, parcel_ids: List[str], enable_spatial: bool):
        """
        Execute job pipeline in background.
        
        Pipeline stages:
        1. Environment (0-30%)
        2. Zoning (30-60%)
        3. Merge (60-80%)
        4. Spatial (80-100%, optional)
        
        Parameters
        ----------
        job_id : str
            Job identifier
        parcel_ids : List[str]
            Parcel IDs to process
        enable_spatial : bool
            Whether to run spatial stage
        """
        current_step: str | None = None
        async with self._job_semaphore:
            try:
                # Update to running status
                await self.job_store.update_job(job_id, status="running", stage="environment", progress=0)
            
                # ============================================================
                # STAGE 1: ENVIRONMENT (0-30%)
                # ============================================================
                current_step = "environment"
                logger.info(f"[JOB {job_id}] Stage started: environment")
                await self.job_store.update_step(job_id, "environment", "running")
                
                env_data = await asyncio.wait_for(
                    asyncio.to_thread(run_environment_stage, parcel_ids),
                    timeout=self._stage_timeout_seconds,
                )
                
                await self.job_store.update_step(job_id, "environment", "completed")
                await self.job_store.update_job(job_id, progress=30)
                logger.info(f"[JOB {job_id}] Stage completed: environment")
                
                # ============================================================
                # STAGE 2: ZONING (30-60%)
                # ============================================================
                current_step = "zoning"
                logger.info(f"[JOB {job_id}] Stage started: zoning")
                await self.job_store.update_job(job_id, stage="zoning")
                await self.job_store.update_step(job_id, "zoning", "running")
                
                zoning_data = await asyncio.wait_for(
                    asyncio.to_thread(run_zoning_stage, parcel_ids),
                    timeout=self._stage_timeout_seconds,
                )
                
                await self.job_store.update_step(job_id, "zoning", "completed")
                await self.job_store.update_job(job_id, progress=60)
                logger.info(f"[JOB {job_id}] Stage completed: zoning")
                
                # ============================================================
                # STAGE 3: MERGE (60-80%)
                # ============================================================
                current_step = "merge"
                logger.info(f"[JOB {job_id}] Stage started: merge")
                await self.job_store.update_job(job_id, stage="merge")
                await self.job_store.update_step(job_id, "merge", "running")
                
                merged_data = await asyncio.wait_for(
                    asyncio.to_thread(merge_outputs, env_data, zoning_data),
                    timeout=self._stage_timeout_seconds,
                )
                
                await self.job_store.update_step(job_id, "merge", "completed")
                await self.job_store.update_job(job_id, progress=80)
                logger.info(f"[JOB {job_id}] Stage completed: merge")
                
                # ============================================================
                # STAGE 4: SPATIAL (80-100%, optional)
                # ============================================================
                if enable_spatial:
                    current_step = "spatial"
                    logger.info(f"[JOB {job_id}] Stage started: spatial")
                    await self.job_store.update_job(job_id, stage="spatial")
                    await self.job_store.update_step(job_id, "spatial", "running")
                    
                    spatial_data = await asyncio.wait_for(
                        asyncio.to_thread(run_spatial_stage, merged_data),
                        timeout=self._stage_timeout_seconds,
                    )
                    
                    await self.job_store.update_step(job_id, "spatial", "completed")
                    logger.info(f"[JOB {job_id}] Stage completed: spatial")
                    
                    # Add spatial data to final result
                    merged_data["spatial"] = spatial_data
                else:
                    logger.info(f"[JOB {job_id}] Stage skipped: spatial")
                    await self.job_store.update_step(job_id, "spatial", "skipped")
                
                # ============================================================
                # COMPLETION
                # ============================================================
                await self.job_store.update_job(
                    job_id,
                    status="completed",
                    progress=100,
                    stage="completed",
                    result=merged_data
                )
                current_step = None
                
                logger.info(f"[JOB {job_id}] Job completed successfully")
                
            except Exception as e:
                # Handle errors
                error_msg = str(e)
                logger.error(f"[JOB {job_id}] Error occurred: {error_msg}", exc_info=True)
                public_error = (
                    f"Stage '{current_step}' failed."
                    if current_step is not None
                    else "Job execution failed."
                )

                if current_step is not None:
                    await self.job_store.update_step(job_id, current_step, "failed")
                
                await self.job_store.update_job(
                    job_id,
                    status="failed",
                    stage=current_step or "failed",
                    error=public_error
                )
    
    async def get_job_status(self, job_id: str):
        """
        Get current job status.
        
        Parameters
        ----------
        job_id : str
            Job identifier
            
        Returns
        -------
        Optional[Job]
            Job instance or None if not found
        """
        return await self.job_store.get_job(job_id)
    
    async def get_job_result(self, job_id: str):
        """
        Get job result (only if completed).
        
        Parameters
        ----------
        job_id : str
            Job identifier
            
        Returns
        -------
        Optional[Dict]
            Job result or None
            
        Raises
        ------
        ValueError
            If job not found or not completed
        """
        job = await self.job_store.get_job(job_id)
        
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        if job.status != "completed":
            raise ValueError(f"Job {job_id} is not completed (status: {job.status})")
        
        return job.result


# Global singleton instance
_orchestrator_service = None


def get_orchestrator_service() -> OrchestratorService:
    """
    Get or create the global orchestrator service instance.
    
    Returns
    -------
    OrchestratorService
        Singleton orchestrator service
    """
    global _orchestrator_service
    if _orchestrator_service is None:
        _orchestrator_service = OrchestratorService()
    return _orchestrator_service
