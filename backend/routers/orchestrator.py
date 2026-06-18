"""
Orchestrator Router - FastAPI endpoints for job orchestration.

Provides REST API for creating and monitoring multi-stage orchestration jobs.
"""

import logging

from fastapi import APIRouter, HTTPException

from schemas.orchestrator import (
    JobResultResponse,
    JobStatusResponse,
    JobStepsStatus,
    OrchestrationPlanRequest,
    OrchestrationPlanResponse,
)
from services.orchestrator_service import get_orchestrator_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


@router.post("/plan", response_model=OrchestrationPlanResponse)
async def create_orchestration_plan(request: OrchestrationPlanRequest):
    """
    Create a new orchestration job and start background execution.

    The job executes:
    1. Environment: Predict land-use suitability (0-30%)
    2. Zoning: Retrieve zoning regulations (30-60%)
    3. Merge: Combine environment + zoning data (60-80%)
    4. Spatial: Generate spatial plans (80-100%, optional)
    """
    try:
        service = get_orchestrator_service()
        job_id = await service.create_job(
            parcel_ids=request.parcel_ids,
            enable_spatial=request.enable_spatial,
        )
        return OrchestrationPlanResponse(job_id=job_id, status="created")
    except Exception as exc:
        logger.error("Error creating orchestration plan: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create orchestration job.")


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get status, progress, current stage, and per-step stage states."""
    try:
        service = get_orchestrator_service()
        job = await service.get_job_status(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        return JobStatusResponse(
            job_id=job.job_id,
            status=job.status,
            progress=job.progress,
            stage=job.stage,
            steps=JobStepsStatus(**job.steps.to_dict()),
            error=job.error,
            created_at=job.created_at,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error getting job status: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch job status.")


@router.get("/result/{job_id}", response_model=JobResultResponse)
async def get_job_result(job_id: str):
    """Return result for completed jobs only."""
    try:
        service = get_orchestrator_service()
        result = await service.get_job_result(job_id)
        return JobResultResponse(status="completed", result=result)
    except ValueError as exc:
        error_msg = str(exc)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as exc:
        logger.error("Error getting job result: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch job result.")
