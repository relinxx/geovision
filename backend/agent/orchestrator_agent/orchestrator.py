"""
Orchestrator Agent Module

Coordinates multi-agent workflows by planning and managing job execution across
different specialized agents (environment, zoning, spatial, etc.).

The orchestrator:
1. Plans multi-step workflows based on user goals
2. Manages step dependencies and execution order
3. Tracks job status and step results
4. Handles error propagation and job cancellation

Architecture:
    - JobPlan: Represents a complete workflow with multiple steps
    - JobStep: Individual task executed by a specific agent
    - OrchestratorAgent: Main coordinator that plans and tracks jobs
"""
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """
    Job execution status enumeration.
    
    Status flow: PENDING -> PLANNING -> RUNNING -> COMPLETED/FAILED/CANCELLED
    """
    PENDING = "pending"      # Job created, not yet started
    PLANNING = "planning"    # Creating workflow plan
    RUNNING = "running"      # One or more steps executing
    COMPLETED = "completed"  # All steps completed successfully
    FAILED = "failed"        # One or more steps failed
    CANCELLED = "cancelled"  # Job cancelled by user/system


@dataclass
class JobStep:
    """
    Represents a single step in a multi-agent job workflow.
    
    A step defines:
    - Which agent to invoke (environment, zoning, spatial, etc.)
    - What action to perform (predict, generate, analyze, etc.)
    - Parameters for the action
    - Dependencies on other steps (execution order)
    - Execution status and results
    """
    step_id: str  # Unique identifier for this step (e.g., "env_suitability")
    agent: str    # Agent name (e.g., "environment", "zoning", "spatial")
    action: str   # Action to perform (e.g., "predict", "generate", "analyze")
    parameters: Dict[str, Any] = field(default_factory=dict)  # Action-specific parameters
    dependencies: List[str] = field(default_factory=list)  # step_ids that must complete first
    status: JobStatus = JobStatus.PENDING
    result: Optional[Dict[str, Any]] = None  # Step output/result data
    error: Optional[str] = None  # Error message if step failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class JobPlan:
    """
    Represents a complete multi-step job plan.
    
    A job plan contains:
    - User's original request/goal
    - List of steps to execute (with dependencies)
    - Overall job status and timing
    - Error information if job failed
    """
    job_id: str  # Unique job identifier (UUID)
    user_request: Dict[str, Any]  # Original request from user
    steps: List[JobStep] = field(default_factory=list)  # Workflow steps
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None  # When first step started
    completed_at: Optional[datetime] = None  # When all steps completed
    error: Optional[str] = None  # Overall job error message


class OrchestratorAgent:
    """Orchestrator that plans and coordinates multi-agent workflows."""
    
    def __init__(self):
        """Initialize the orchestrator agent."""
        self.jobs: Dict[str, JobPlan] = {}
        logger.info("OrchestratorAgent initialized")
    
    def plan(self, request: Dict[str, Any]) -> JobPlan:
        """
        Create a job plan based on user request.
        
        Parameters
        ----------
        request : Dict[str, Any]
            User request with:
            - "parcels": List of parcel GeoJSON features (optional)
            - "goal": str, e.g., "suitability_analysis", "spatial_generation", "zoning_check"
            - "parameters": Dict with additional parameters
            
        Returns
        -------
        JobPlan
            The created job plan with steps.
        """
        job_id = str(uuid.uuid4())
        goal = request.get("goal", "suitability_analysis")
        parcels = request.get("parcels", [])
        parameters = request.get("parameters", {})
        
        logger.info(f"Planning job {job_id} with goal: {goal}")
        
        steps: List[JobStep] = []
        
        # Plan based on goal
        if goal == "suitability_analysis":
            # Step 1: Environmental suitability
            steps.append(JobStep(
                step_id="env_suitability",
                agent="environment",
                action="predict",
                parameters={
                    "parcels": parcels,
                    **parameters
                }
            ))
            # Step 2: Zoning check (optional, depends on step 1)
            if parameters.get("include_zoning", False):
                steps.append(JobStep(
                    step_id="zoning_check",
                    agent="zoning",
                    action="check",
                    parameters={"parcels": parcels},
                    dependencies=["env_suitability"]
                ))
                
        elif goal == "spatial_generation":
            # Spatial generation workflow
            steps.append(JobStep(
                step_id="spatial_generate",
                agent="spatial",
                action="generate",
                parameters={
                    "parcels": parcels,
                    **parameters
                }
            ))
            
        elif goal == "full_analysis":
            # Full pipeline: environment + zoning + spatial
            steps.append(JobStep(
                step_id="env_suitability",
                agent="environment",
                action="predict",
                parameters={"parcels": parcels}
            ))
            steps.append(JobStep(
                step_id="zoning_check",
                agent="zoning",
                action="check",
                parameters={"parcels": parcels},
                dependencies=["env_suitability"]
            ))
            steps.append(JobStep(
                step_id="spatial_generate",
                agent="spatial",
                action="generate",
                parameters={
                    "parcels": parcels,
                    "use_env_results": True,
                    "use_zoning_results": True
                },
                dependencies=["env_suitability", "zoning_check"]
            ))
        else:
            # Default: just environmental suitability
            steps.append(JobStep(
                step_id="env_suitability",
                agent="environment",
                action="predict",
                parameters={"parcels": parcels, **parameters}
            ))
        
        plan = JobPlan(
            job_id=job_id,
            user_request=request,
            steps=steps,
            status=JobStatus.PLANNING
        )
        
        self.jobs[job_id] = plan
        logger.info(f"Created plan for job {job_id} with {len(steps)} steps")
        
        return plan
    
    def get_status(self, job_id: str) -> Optional[JobPlan]:
        """
        Get the current status of a job.
        
        Parameters
        ----------
        job_id : str
            The job ID.
            
        Returns
        -------
        Optional[JobPlan]
            The job plan with current status, or None if not found.
        """
        return self.jobs.get(job_id)
    
    def update_step_status(
        self,
        job_id: str,
        step_id: str,
        status: JobStatus,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Update the status of a job step.
        
        Parameters
        ----------
        job_id : str
            The job ID.
        step_id : str
            The step ID.
        status : JobStatus
            The new status.
        result : Optional[Dict[str, Any]]
            Step result if completed successfully.
        error : Optional[str]
            Error message if failed.
            
        Returns
        -------
        bool
            True if update was successful, False otherwise.
        """
        if job_id not in self.jobs:
            logger.warning(f"Job {job_id} not found")
            return False
        
        plan = self.jobs[job_id]
        step = next((s for s in plan.steps if s.step_id == step_id), None)
        
        if not step:
            logger.warning(f"Step {step_id} not found in job {job_id}")
            return False
        
        step.status = status
        step.result = result
        step.error = error
        
        if status == JobStatus.RUNNING and not step.started_at:
            step.started_at = datetime.now()
            if not plan.started_at:
                plan.started_at = datetime.now()
                plan.status = JobStatus.RUNNING
        
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED):
            step.completed_at = datetime.now()
            
            # Update overall job status
            all_completed = all(s.status == JobStatus.COMPLETED for s in plan.steps)
            any_failed = any(s.status == JobStatus.FAILED for s in plan.steps)
            
            if any_failed:
                plan.status = JobStatus.FAILED
                plan.error = f"Step {step_id} failed: {error}"
            elif all_completed:
                plan.status = JobStatus.COMPLETED
                plan.completed_at = datetime.now()
        
        logger.info(f"Updated step {step_id} in job {job_id} to status {status}")
        return True
    
    def can_execute_step(self, job_id: str, step_id: str) -> bool:
        """
        Check if a step can be executed (all dependencies completed).
        
        Parameters
        ----------
        job_id : str
            The job ID.
        step_id : str
            The step ID.
            
        Returns
        -------
        bool
            True if step can be executed.
        """
        if job_id not in self.jobs:
            return False
        
        plan = self.jobs[job_id]
        step = next((s for s in plan.steps if s.step_id == step_id), None)
        
        if not step:
            return False
        
        # Check if all dependencies are completed
        for dep_id in step.dependencies:
            dep_step = next((s for s in plan.steps if s.step_id == dep_id), None)
            if not dep_step or dep_step.status != JobStatus.COMPLETED:
                return False
        
        return True

