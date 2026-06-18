# GeoVision Codebase Detailed Analysis

## 1) Executive Summary

This repository is a full-stack geospatial planning system with:

- A FastAPI backend that provides suitability scoring, zoning retrieval (RAG), spatial optimization, authentication, and asynchronous orchestration.
- A React + TypeScript frontend that provides map-centric planning workflows, zoning chat, parcel selection, and spatial plan generation.

Current state in plain terms:

- Core backend logic is substantial and generally well-structured, especially around the spatial optimization engine and orchestration pipeline.
- Frontend-to-backend integration is partially complete: key spatial flow is wired, but some API client areas still show placeholder/TODO intent.
- Operational accuracy is moderate: code structure is strong, but verification is limited by missing runnable test/build dependencies in the current environment.
- Security posture is currently weak due to a real API key present in a frontend environment file.

High-level readiness score (current snapshot): 6.2 / 10

- Architecture and implementation depth: 8.0 / 10
- Integration completeness: 6.0 / 10
- Documentation freshness: 3.5 / 10
- Test/verification confidence: 5.0 / 10
- Security hygiene: 2.0 / 10


## 2) What The Code Is Doing

## 2.1 Backend responsibilities

Primary app and route wiring

- backend/main.py
  - Starts FastAPI app.
  - Configures CORS and optional API-key middleware.
  - Exposes core endpoints for:
    - Health
    - Suitability prediction
    - Zoning RAG question answering
    - Spatial plan generation/optimization
  - Mounts auth and orchestrator routers.

Authentication and identity

- backend/database.py
  - Creates and manages SQLite connection/table bootstrapping.
- backend/schemas/auth.py
  - Pydantic request/response models for auth.
- backend/services/auth_service.py
  - Password hashing, JWT creation/decoding, user create/login/lookup.
- backend/routers/auth.py
  - /auth/register, /auth/login, /auth/me, /auth/logout.

Orchestration pipeline

- backend/schemas/orchestrator.py
  - Request/response models for orchestration API.
- backend/services/job_store.py
  - In-memory async-safe job lifecycle state store.
- backend/services/orchestrator_steps.py
  - Stage wrappers for environment, zoning, merge, optional spatial.
- backend/services/orchestrator_service.py
  - Runs async pipeline with progress updates, stage statuses, timeout/semaphore controls.
- backend/routers/orchestrator.py
  - /orchestrator/plan, /orchestrator/status/{job_id}, /orchestrator/result/{job_id}.

AI/analytics components

- Environment suitability agent
  - backend/agent/environment_agent/agent.py
  - Produces suitability outputs using risk data and fallback heuristics where needed.

- Zoning RAG agent
  - backend/agent/zoning_agent/rag_service.py
  - Retrieves zoning context from Chroma/OpenAI-backed retrieval and answers queries.

- Spatial optimization agent
  - backend/agent/spatial_agent/spatial/
  - NSGA-II based multi-objective optimization with parcel typing, objective evaluation, and output plan generation.

Feature and output utilities

- backend/utils/features.py
  - Extracts/normalizes features and model-facing mappings.
- backend/utils/geojson_output.py
  - Re-attaches predictions into GeoJSON for frontend map rendering.


## 2.2 Frontend responsibilities

App shell and route control

- frontend/src/App.tsx
  - Main app routing and top-level feature state orchestration.
  - Handles auth-guarded and public views.

Auth/session state

- frontend/src/context/AuthContext.tsx
  - Login/register/me validation flow and token persistence.

Planner runtime settings

- frontend/src/context/PlannerSettingsContext.tsx
  - Runtime planner constraints/settings persisted client-side.

Primary planning workflow

- frontend/src/pages/HomePage/HomePage.tsx
  - Parcel selection and map interaction.
  - Calls spatial optimization endpoint and paints resulting overlays.

Map stack

- frontend/src/components/map/ParcelMap.tsx
- frontend/src/components/map/MapCanvas.tsx
  - Leaflet-driven rendering, selection/hover interactions, and layer presentation.

Zoning chat UI

- frontend/src/components/chat/ZoningChatPanel/ZoningChatPanel.tsx
  - User Q/A interface connected to backend zoning RAG endpoint.

API abstraction layer

- frontend/src/utils/api.ts
  - Centralized client methods for backend calls.
  - Mixed maturity: several methods are integrated, several still include TODO/placeholder notes.


## 2.3 End-to-end runtime flow

Typical user flow in the current implementation:

1. User authenticates in frontend.
2. User selects parcels on map.
3. Frontend sends parcel context to backend spatial endpoint.
4. Backend computes optimization plans with NSGA-II.
5. Backend returns plan outputs (with objectives/assignments).
6. Frontend renders outputs as interactive overlays/layers.

Alternative path for staged orchestration:

1. Frontend or client submits orchestration request.
2. Backend creates async job and runs staged pipeline:
   - Environment -> Zoning -> Merge -> Optional Spatial.
3. Client polls status/result endpoints.


## 3) How The Code Is Built And Run

## 3.1 Backend setup and run

Working directory: backend

Recommended steps:

1. Create/activate a Python environment.
2. Install dependencies:
   - pip install -r requirements.txt
   - or poetry install (if using pyproject toolchain)
3. Start API:
   - uvicorn main:app --reload --host 0.0.0.0 --port 8000

Important backend environment variables:

- JWT_SECRET_KEY
- OPENAI_API_KEY
- CHROMA_OPENAI_API_KEY (if used by zoning stack)
- RAG_PERSIST_DIR
- ORCHESTRATOR_MAX_CONCURRENT_JOBS
- ORCHESTRATOR_STAGE_TIMEOUT_SECONDS
- ORCHESTRATOR_MAX_JOBS
- ORCHESTRATOR_JOB_RETENTION_HOURS
- API_KEY (if API-key middleware is enabled)


## 3.2 Frontend setup and run

Working directory: frontend

Recommended steps:

1. npm install
2. npm run dev
3. Open local Vite dev URL

Production build command:

- npm run build

Observed environment issue in this snapshot:

- Build currently fails with: vite is not recognized as an internal or external command.
- This indicates local Node dependency/bin resolution is broken in this workspace state.


## 3.3 Current validation results (executed)

Frontend build check

- Command: npm run build
- Result: failed due to missing vite executable in PATH/npm local shim resolution.

Backend tests check

- Command: python -m pytest -q
- Result: failed because pytest is not installed in current Python environment.

Backend syntax integrity fallback

- Command: python -m compileall .
- Result: completed successfully with no syntax errors reported.


## 4) Accuracy And Reliability Assessment

## 4.1 What is accurate/strong now

Backend architecture quality is strong

- Service boundaries are clear (routers, services, schemas, agents).
- Async orchestration model is coherent and production-intent.
- Spatial optimization subsystem is mature and algorithmically non-trivial.

Spatial optimization confidence is strongest

- Dedicated test suite exists under backend/agent/spatial_agent/tests.
- Objective modeling and NSGA-II implementation are separated cleanly.

Core syntax baseline is clean

- Full backend compile pass succeeded in current environment.


## 4.2 What lowers confidence

Verification gap

- No runnable backend tests in current environment due missing pytest dependency.
- Frontend production build is not currently reproducible due local dependency/bin state.

Integration gap

- Frontend actively uses optimizeSpatialPlans in HomePage.
- Frontend suitability API helper exists but is not currently wired into primary UI workflow.
- Frontend orchestrator endpoint usage is not present in current source usage scan.

Documentation drift

- frontend/ARCHITECTURE.md still marks major backend/API areas as TODO even though backend exists and is wired.

Security risk (critical)

- frontend/.env contains an OpenAI API key value.
- Any secret in repo or frontend-accessible config is a serious risk and should be treated as exposed.


## 4.3 Accuracy scorecard by subsystem

- Backend auth + API surface: 7.0 / 10
- Backend orchestrator pipeline: 7.0 / 10
- Backend spatial optimizer internals: 8.5 / 10
- Backend zoning RAG reliability: 6.0 / 10 (external dependency sensitivity)
- Frontend map/planning UX integration: 6.5 / 10
- Frontend API abstraction consistency: 5.5 / 10
- Documentation accuracy: 3.5 / 10
- Build/test reproducibility in current environment: 4.0 / 10
- Security hygiene: 2.0 / 10

Overall: 6.2 / 10


## 5) Priority Risks And Fix Plan

## P0 (immediate)

1. Rotate and revoke exposed API keys immediately.
2. Remove secrets from tracked files and enforce local-only secret loading.

## P1 (this week)

1. Repair frontend dependency state:
   - clean install and lockfile validation
   - verify vite executable resolution
2. Add pytest to backend environment and execute full suite.
3. Add CI checks for:
   - frontend build
   - backend tests
   - optional backend lint/type checks

## P2 (next)

1. Bring frontend docs in sync with actual implementation.
2. Wire frontend orchestrator UX if staged pipeline is part of product intent.
3. Decide whether unused/placeholder API client methods should be completed or removed.


## 6) Suggested Build-Ready Checklist

- [ ] Secret rotation and repository cleanup complete
- [ ] Frontend npm run build passes in clean environment
- [ ] Backend pytest suite executes and passes
- [ ] New tests added for auth/orchestrator integration
- [ ] API contract checks between frontend and backend verified
- [ ] Frontend ARCHITECTURE/INTEGRATION docs updated to current state


## 7) Final Conclusion

This is not a toy codebase: there is real system depth, especially in backend orchestration and spatial optimization. The project appears to be in late prototype / pre-production hardening stage rather than early scaffolding.

Accuracy is currently moderate and can move to high with focused stabilization work:

- close environment reproducibility gaps,
- execute full automated tests consistently,
- eliminate secret management issues,
- and synchronize documentation with the implemented system.

If those items are completed, the codebase has a solid foundation for production-oriented iteration.
