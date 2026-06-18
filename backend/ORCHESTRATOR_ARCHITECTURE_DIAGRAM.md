# Orchestrator Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT (Frontend/API)                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ HTTP/REST
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR ROUTER                                  │
│                      (routers/orchestrator.py)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  POST /orchestrator/plan                                                     │
│  ├─ Request: OrchestrationPlanRequest                                       │
│  ├─ Response: OrchestrationPlanResponse                                     │
│  └─ Action: Create job + start background execution                         │
│                                                                               │
│  GET /orchestrator/status/{job_id}                                          │
│  ├─ Response: JobStatusResponse                                             │
│  └─ Action: Return current job status                                       │
│                                                                               │
│  GET /orchestrator/result/{job_id}                                          │
│  ├─ Response: JobResultResponse                                             │
│  └─ Action: Return completed job result                                     │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Service Layer
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR SERVICE                                    │
│                  (services/orchestrator_service.py)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  create_job(parcel_ids, enable_spatial)                                     │
│  ├─ Generate job_id                                                         │
│  ├─ Create job in store                                                     │
│  └─ Start background execution (asyncio.create_task)                        │
│                                                                               │
│  _execute_job(job_id, parcel_ids, enable_spatial)                          │
│  ├─ Stage 1: Environment (0-30%)                                            │
│  ├─ Stage 2: Zoning (30-60%)                                                │
│  ├─ Stage 3: Merge (60-80%)                                                 │
│  ├─ Stage 4: Spatial (80-100%, optional)                                    │
│  └─ Update job status to completed/failed                                   │
│                                                                               │
│  get_job_status(job_id)                                                     │
│  └─ Query job store for current status                                      │
│                                                                               │
│  get_job_result(job_id)                                                     │
│  └─ Return result if job completed                                          │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
┌──────────────────────────┐  ┌──────────────────────────┐  ┌──────────────────────────┐
│   ORCHESTRATOR STEPS     │  │      JOB STORE           │  │    PYDANTIC SCHEMAS      │
│ (orchestrator_steps.py)  │  │   (job_store.py)         │  │  (orchestrator.py)       │
├──────────────────────────┤  ├──────────────────────────┤  ├──────────────────────────┤
│                          │  │                          │  │                          │
│ run_environment_stage()  │  │ JobStore (singleton)     │  │ OrchestrationPlanRequest │
│ ├─ Call SuitabilityAgent │  │ ├─ _jobs: Dict[str, Job] │  │ ├─ parcel_ids: List[str] │
│ └─ Return suitability    │  │ ├─ _lock: asyncio.Lock   │  │ └─ enable_spatial: bool  │
│                          │  │ └─ Thread-safe ops       │  │                          │
│ run_zoning_stage()       │  │                          │  │ JobStatusResponse        │
│ ├─ Call RagService       │  │ create_job()             │  │ ├─ job_id: str           │
│ └─ Return regulations    │  │ get_job()                │  │ ├─ status: str           │
│                          │  │ update_job()             │  │ ├─ progress: int         │
│ merge_outputs()          │  │ update_step()            │  │ ├─ stage: str            │
│ ├─ Combine env + zoning  │  │ list_jobs()              │  │ ├─ steps: JobStepsStatus │
│ └─ Return unified data   │  │                          │  │ └─ error: Optional[str]  │
│                          │  │ Job (dataclass)          │  │                          │
│ run_spatial_stage()      │  │ ├─ job_id: str           │  │ JobResultResponse        │
│ ├─ Placeholder           │  │ ├─ status: str           │  │ ├─ status: str           │
│ └─ Return spatial data   │  │ ├─ progress: int         │  │ └─ result: Dict          │
│                          │  │ ├─ stage: str            │  │                          │
└──────────────────────────┘  │ ├─ steps: JobSteps       │  └──────────────────────────┘
                              │ ├─ result: Optional[Dict]│
                              │ ├─ error: Optional[str]  │
                              │ └─ created_at: datetime  │
                              │                          │
                              └──────────────────────────┘
                                      │
                                      │ Calls existing agents
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXISTING AGENTS (Unchanged)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │ Environment      │  │ Zoning Agent     │  │ Spatial Agent    │          │
│  │ Agent            │  │ (RAG Service)    │  │ (Placeholder)    │          │
│  ├──────────────────┤  ├──────────────────┤  ├──────────────────┤          │
│  │                  │  │                  │  │                  │          │
│  │ SuitabilityAgent │  │ RagService       │  │ SpatialAgent     │          │
│  │ ├─ load_data()   │  │ ├─ retrieve()    │  │ ├─ generate()    │          │
│  │ └─ predict()     │  │ └─ answer()      │  │ └─ (stub)        │          │
│  │                  │  │                  │  │                  │          │
│  │ XGBoost Model    │  │ ChromaDB         │  │ GeoPandas        │          │
│  │ Risk Scores      │  │ OpenAI GPT       │  │ Shapely          │          │
│  │                  │  │                  │  │                  │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         JOB EXECUTION PIPELINE                               │
└─────────────────────────────────────────────────────────────────────────────┘

1. CLIENT REQUEST
   │
   ├─ POST /orchestrator/plan
   │  {
   │    "parcel_ids": ["4042700100", "4042700200"],
   │    "enable_spatial": false
   │  }
   │
   ▼
2. ROUTER (orchestrator.py)
   │
   ├─ Validate request (Pydantic)
   ├─ Call service.create_job()
   │
   ▼
3. SERVICE (orchestrator_service.py)
   │
   ├─ Generate job_id = uuid4()
   ├─ Create job in store (status="created")
   ├─ Return job_id immediately
   ├─ Start background task: asyncio.create_task(_execute_job)
   │
   ▼
4. BACKGROUND EXECUTION (_execute_job)
   │
   ├─ Update status="running", stage="environment", progress=0
   │
   ├─ STAGE 1: ENVIRONMENT (0-30%)
   │  │
   │  ├─ Call run_environment_stage(parcel_ids)
   │  │  │
   │  │  ├─ Initialize SuitabilityAgent
   │  │  ├─ Create DataFrame with parcel_ids
   │  │  ├─ Call agent.predict(df)
   │  │  └─ Return suitability scores
   │  │
   │  ├─ Update step="completed", progress=30
   │  │
   │  ▼
   │
   ├─ STAGE 2: ZONING (30-60%)
   │  │
   │  ├─ Call run_zoning_stage(parcel_ids)
   │  │  │
   │  │  ├─ Initialize RagService
   │  │  ├─ For each parcel:
   │  │  │  ├─ Construct query
   │  │  │  ├─ Retrieve regulations (ChromaDB)
   │  │  │  └─ Extract metadata
   │  │  └─ Return zoning results
   │  │
   │  ├─ Update step="completed", progress=60
   │  │
   │  ▼
   │
   ├─ STAGE 3: MERGE (60-80%)
   │  │
   │  ├─ Call merge_outputs(env_data, zoning_data)
   │  │  │
   │  │  ├─ Create lookup dictionaries
   │  │  ├─ For each parcel:
   │  │  │  ├─ Combine suitability scores
   │  │  │  └─ Combine zoning regulations
   │  │  └─ Return unified results
   │  │
   │  ├─ Update step="completed", progress=80
   │  │
   │  ▼
   │
   ├─ STAGE 4: SPATIAL (80-100%, optional)
   │  │
   │  ├─ If enable_spatial=false:
   │  │  └─ Update step="skipped"
   │  │
   │  ├─ If enable_spatial=true:
   │  │  ├─ Call run_spatial_stage(unified_data)
   │  │  ├─ (Placeholder implementation)
   │  │  └─ Update step="completed"
   │  │
   │  ├─ Update progress=100
   │  │
   │  ▼
   │
   ├─ Update status="completed", result=merged_data
   │
   └─ Log: "[JOB job_id] Job completed successfully"

5. CLIENT POLLING
   │
   ├─ GET /orchestrator/status/{job_id}
   │  │
   │  ├─ Query job store
   │  ├─ Return current status, progress, stage, steps
   │  │
   │  └─ Client polls every 1-2 seconds until status="completed"
   │
   ▼
6. RESULT RETRIEVAL
   │
   ├─ GET /orchestrator/result/{job_id}
   │  │
   │  ├─ Verify job status="completed"
   │  ├─ Return job.result
   │  │
   │  └─ Client receives unified parcel data
   │
   ▼
7. CLIENT PROCESSING
   │
   └─ Display results in UI
      ├─ Suitability scores on map
      ├─ Zoning regulations in sidebar
      └─ Combined analysis view
```

## Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      COMPONENT INTERACTIONS                                  │
└─────────────────────────────────────────────────────────────────────────────┘

Router                Service              Steps                Agents
  │                     │                    │                    │
  │ create_job()        │                    │                    │
  ├────────────────────>│                    │                    │
  │                     │                    │                    │
  │                     │ create_job()       │                    │
  │                     ├───────────────────>│                    │
  │                     │                    │                    │
  │                     │ asyncio.create_task│                    │
  │                     │ (_execute_job)     │                    │
  │                     ├────────────────────┤                    │
  │                     │                    │                    │
  │<────────────────────┤                    │                    │
  │ job_id              │                    │                    │
  │                     │                    │                    │
  │                     │                    │ run_environment_   │
  │                     │                    │ stage()            │
  │                     │                    ├───────────────────>│
  │                     │                    │                    │
  │                     │                    │                    │ predict()
  │                     │                    │                    ├──────────┐
  │                     │                    │                    │          │
  │                     │                    │                    │<─────────┘
  │                     │                    │<───────────────────┤
  │                     │                    │ suitability_scores │
  │                     │                    │                    │
  │                     │                    │ run_zoning_stage() │
  │                     │                    ├───────────────────>│
  │                     │                    │                    │
  │                     │                    │                    │ retrieve()
  │                     │                    │                    ├──────────┐
  │                     │                    │                    │          │
  │                     │                    │                    │<─────────┘
  │                     │                    │<───────────────────┤
  │                     │                    │ zoning_regulations │
  │                     │                    │                    │
  │                     │                    │ merge_outputs()    │
  │                     │                    ├────────────────────┤
  │                     │                    │                    │
  │                     │                    │ unified_results    │
  │                     │<───────────────────┤                    │
  │                     │                    │                    │
  │                     │ update_job()       │                    │
  │                     ├───────────────────>│                    │
  │                     │ (status=completed) │                    │
  │                     │                    │                    │
  │ get_status()        │                    │                    │
  ├────────────────────>│                    │                    │
  │                     │                    │                    │
  │                     │ get_job()          │                    │
  │                     ├───────────────────>│                    │
  │                     │                    │                    │
  │<────────────────────┤                    │                    │
  │ status_response     │                    │                    │
  │                     │                    │                    │
  │ get_result()        │                    │                    │
  ├────────────────────>│                    │                    │
  │                     │                    │                    │
  │                     │ get_job()          │                    │
  │                     ├───────────────────>│                    │
  │                     │                    │                    │
  │<────────────────────┤                    │                    │
  │ result_response     │                    │                    │
  │                     │                    │                    │
```

## State Transition Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         JOB STATE TRANSITIONS                                │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────┐
                              │   CREATED   │
                              │  progress=0 │
                              └──────┬──────┘
                                     │
                                     │ Background task starts
                                     │
                                     ▼
                              ┌─────────────┐
                              │   RUNNING   │
                              │  progress=0 │
                              │ stage=env   │
                              └──────┬──────┘
                                     │
                                     │ Environment stage
                                     │
                                     ▼
                              ┌─────────────┐
                              │   RUNNING   │
                              │ progress=30 │
                              │ stage=zoning│
                              └──────┬──────┘
                                     │
                                     │ Zoning stage
                                     │
                                     ▼
                              ┌─────────────┐
                              │   RUNNING   │
                              │ progress=60 │
                              │ stage=merge │
                              └──────┬──────┘
                                     │
                                     │ Merge stage
                                     │
                                     ▼
                              ┌─────────────┐
                              │   RUNNING   │
                              │ progress=80 │
                              │stage=spatial│
                              └──────┬──────┘
                                     │
                        ┌────────────┼────────────┐
                        │                         │
                        │ Success                 │ Error
                        │                         │
                        ▼                         ▼
                 ┌─────────────┐          ┌─────────────┐
                 │  COMPLETED  │          │   FAILED    │
                 │ progress=100│          │ error!=null │
                 │ result!=null│          │             │
                 └─────────────┘          └─────────────┘
```

## Thread Safety Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         THREAD SAFETY MODEL                                  │
└─────────────────────────────────────────────────────────────────────────────┘

JobStore (Singleton)
├─ _jobs: Dict[str, Job]
├─ _lock: asyncio.Lock
│
└─ All operations protected by lock:
   │
   ├─ async with self._lock:
   │  ├─ create_job()
   │  ├─ get_job()
   │  ├─ update_job()
   │  ├─ update_step()
   │  └─ list_jobs()
   │
   └─ Ensures atomic operations even with concurrent requests

Concurrent Request Handling:
│
├─ Request 1: POST /plan (parcel_ids=[...])
│  ├─ Acquires lock
│  ├─ Creates job_1
│  ├─ Releases lock
│  └─ Starts background task
│
├─ Request 2: GET /status/job_1
│  ├─ Acquires lock
│  ├─ Reads job_1 status
│  ├─ Releases lock
│  └─ Returns status
│
├─ Background Task: _execute_job(job_1)
│  ├─ Acquires lock
│  ├─ Updates job_1.progress
│  ├─ Releases lock
│  └─ Continues execution
│
└─ Request 3: POST /plan (parcel_ids=[...])
   ├─ Waits for lock
   ├─ Acquires lock
   ├─ Creates job_2
   ├─ Releases lock
   └─ Starts background task

Result: No race conditions, all operations atomic
```

## Error Propagation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ERROR PROPAGATION FLOW                                 │
└─────────────────────────────────────────────────────────────────────────────┘

Agent Error
    │
    ├─ SuitabilityAgent.predict() raises FileNotFoundError
    │
    ▼
Step Wrapper
    │
    ├─ run_environment_stage() catches exception
    ├─ Logs error: "[ENVIRONMENT] Error in environment stage: ..."
    ├─ Re-raises exception
    │
    ▼
Service Layer
    │
    ├─ _execute_job() catches exception
    ├─ Logs error: "[JOB job_id] Error occurred: ..."
    ├─ Updates job: status="failed", error=str(e)
    ├─ Does NOT raise (background task)
    │
    ▼
Client Polling
    │
    ├─ GET /status/{job_id}
    ├─ Returns: {"status": "failed", "error": "FileNotFoundError: ..."}
    │
    ▼
Client Handling
    │
    └─ Display error message to user
       "Job failed: Model file not found"
```

---

## Key Design Patterns

### 1. Singleton Pattern
- `JobStore`: Single global instance
- `OrchestratorService`: Single global instance

### 2. Facade Pattern
- `orchestrator_steps.py`: Wraps existing agents
- Provides unified interface for orchestrator

### 3. Strategy Pattern
- Different execution strategies based on `enable_spatial`
- Extensible for future stage types

### 4. Observer Pattern (Implicit)
- Client polls for status updates
- Job store maintains state
- Background task updates state

### 5. Command Pattern
- Each stage is a command (function)
- Orchestrator executes commands in sequence
- Easy to add/remove/reorder stages

---

## Scalability Considerations

```
Current MVP (In-Memory)
├─ Single server instance
├─ In-memory job storage
├─ Background tasks in same process
└─ Suitable for: <100 concurrent jobs

Future Phase 2 (Redis)
├─ Multiple server instances
├─ Redis for job storage
├─ Shared state across servers
└─ Suitable for: <1000 concurrent jobs

Future Phase 3 (Celery)
├─ Distributed task queue
├─ Separate worker processes
├─ Horizontal scaling
└─ Suitable for: >1000 concurrent jobs
```

---

This architecture provides a clean, maintainable, and scalable foundation for the GeoVision orchestrator system.
