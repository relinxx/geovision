"""
Orchestrator API Schemas

Pydantic models for orchestrator request/response validation.
"""
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class OrchestrationPlanRequest(BaseModel):
    """Request schema for creating an orchestration job."""
    
    parcel_ids: List[str] = Field(
        ...,
        description="List of parcel IDs (APNs) to process",
        min_length=1
    )
    enable_spatial: bool = Field(
        default=False,
        description="Whether to enable spatial generation stage"
    )


class JobStepsStatus(BaseModel):
    """Status of individual job steps."""
    
    environment: str = Field(default="pending", description="Environment stage status")
    zoning: str = Field(default="pending", description="Zoning stage status")
    merge: str = Field(default="pending", description="Merge stage status")
    spatial: str = Field(default="pending", description="Spatial stage status")


class OrchestrationPlanResponse(BaseModel):
    """Response schema for job creation."""
    
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status: created, running, completed, failed")


class JobStatusResponse(BaseModel):
    """Response schema for job status query."""
    
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status: created, running, completed, failed")
    progress: int = Field(..., description="Progress percentage (0-100)", ge=0, le=100)
    stage: str = Field(..., description="Current stage name")
    steps: JobStepsStatus = Field(..., description="Status of individual steps")
    error: Optional[str] = Field(None, description="Error message if job failed")
    created_at: datetime = Field(..., description="Job creation timestamp")


class JobResultResponse(BaseModel):
    """Response schema for job result query."""
    
    status: str = Field(..., description="Job status (must be 'completed')")
    result: Dict = Field(..., description="Job result data with merged outputs")
