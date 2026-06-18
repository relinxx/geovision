# GeoVision Full-Stack Scan Report

Generated on: 2026-04-24

## 1. System Summary

GeoVision is currently organized as a React/Vite frontend and a FastAPI backend with three main backend execution styles:

1. Direct REST endpoints for auth, suitability scoring, zoning RAG, spatial generation, spatial optimization, copilot streaming, and risk counterfactuals.
2. A background orchestration API (`/orchestrator/*`) that runs async multi-stage jobs with in-memory job tracking.
3. Internal agent/service pipelines for environmental risk, zoning RAG, spatial optimization, and copilot orchestration.

The frontend does **not** expose each dashboard page as its own URL. It uses a single protected route, `/dashboard/*`, and swaps dashboard pages through `activeView` state inside `frontend/src/App.tsx`.

Important architectural reality:

- The current UI still relies heavily on **static GeoJSON in `frontend/public`** for parcel display and overlay display.
- `POST /predict_suitability` exists, and the frontend client has a method for it, but the current pages do **not** call it.
- The backend orchestration endpoints also exist, but the current frontend does **not** call them.
- The dashboard was recently restructured so **Workbench** is the default operational landing page, while the older planner/environment map was reframed as **Environmental Agent**.
- Cross-page planner state is now shared through `PlannerWorkspaceContext` instead of being owned only by the old planner page.

## 2. Frontend Navigation and Runtime Model

Primary frontend shell:

- `frontend/src/App.tsx`: Sets up `BrowserRouter`, `AuthProvider`, `PlannerSettingsProvider`, and `PlannerWorkspaceProvider`.
- `frontend/src/layouts/MainLayout/MainLayout.tsx`: Wraps protected dashboard content with the left navigation sidebar.
- `frontend/src/components/navigation/Sidebar/Sidebar.tsx`: Switches the protected dashboard view between `workbench`, `environmental`, `layers`, `plans`, `copilot`, and `settings`.

Route behavior:

- `/`: Redirects to `/dashboard` if authenticated, otherwise `/welcome`.
- `/welcome`: Public landing page.
- `/login`: Public login page.
- `/register`: Public registration page.
- `/dashboard/*`: Protected shell that renders one of the dashboard pages by React state, not nested URL routing.

Current protected dashboard views:

- `workbench`
- `environmental`
- `layers`
- `plans`
- `copilot`
- `settings`

Important current runtime model:

- `workbench` is now the default dashboard landing view.
- `environmental` is the current parcel-selection plus environmental-risk plus spatial-optimization page.
- `plans` now reads optimization output from shared workspace state rather than from `App.tsx` props.
- `layers` uses the shared primary parcel selection so Workbench and Layers can hand off parcel context.
- `copilot` remains functionally separate and still owns its own conversation and map-selection flow.

## 3. Backend HTTP API Inventory

| Endpoint(s) | Method | Implementation | What it does | Current frontend consumer |
| --- | --- | --- | --- | --- |
| `/health`, `/api/health` | `GET` | `backend/main.py` | Basic health check. | None |
| `/auth/register` | `POST` | `backend/routers/auth.py` | Creates a user, hashes password, returns JWT + user payload. | `RegisterPage` via `AuthContext.register()` |
| `/auth/login` | `POST` | `backend/routers/auth.py` | Authenticates user and returns JWT + user payload. | `LoginPage` via `AuthContext.login()` |
| `/auth/logout` | `POST` | `backend/routers/auth.py` | Placeholder logout endpoint; currently stateless. | None |
| `/auth/me` | `GET` | `backend/routers/auth.py` | Validates JWT and returns current user. | `AuthContext.validateToken()` on app boot |
| `/predict_suitability`, `/api/predict_suitability` | `POST` | `backend/main.py` | Accepts parcel GeoJSON, attaches features, runs `SuitabilityAgent.predict()`, returns GeoJSON with suitability scores. | No current page calls it |
| `/rag/zoning/ask`, `/api/rag/zoning/ask` | `POST` | `backend/main.py` | Zoning RAG endpoint with session memory and parcel context. | `LayersPage` through `ZoningChatPanel` |
| `/spatial/generate`, `/api/spatial/generate` | `POST` | `backend/main.py` | Generates derived geometries such as subdivision, buffers, Voronoi, or grid. | None |
| `/spatial/optimize`, `/api/spatial/optimize` | `POST` | `backend/main.py` | Runs NSGA-II spatial optimization on selected parcel features. | `Environmental Agent` (`HomePage`) |
| `/orchestrator/plan` | `POST` | `backend/routers/orchestrator.py` | Creates async orchestration job. | None |
| `/orchestrator/status/{job_id}` | `GET` | `backend/routers/orchestrator.py` | Polls async orchestration job state. | None |
| `/orchestrator/result/{job_id}` | `GET` | `backend/routers/orchestrator.py` | Returns orchestration job output after completion. | None |
| `/copilot/query`, `/api/copilot/query` | `POST` | `backend/main.py` | Streams SSE events from the copilot orchestrator. | `CopilotPage` via `useCopilotStream()` |
| `/risk/counterfactual`, `/api/risk/counterfactual` | `POST` | `backend/main.py` | Computes a what-if risk score by toggling hazard flags. | `CopilotPage` via `ExplanationDrawer` |

Operational API notes:

- API key middleware can protect nearly the whole backend if `GEOVISION_API_KEY` is set. Only `/health`, `/api/health`, docs routes, and OpenAPI are explicitly exempt.
- Rate limiting is configured in code for:
  - `POST /predict_suitability`
  - `POST /rag/zoning/ask`
  - `POST /spatial/optimize`
- The limiter becomes a no-op when `slowapi` is not installed.
- The frontend API client in `frontend/src/utils/api.ts` retries base URLs with and without `/api`, but `AuthContext` does **not**.
- `HEAD /health` is **not** implemented; only `GET /health` is defined, so `HEAD /health` returns `405 Method Not Allowed`.
- Default dev CORS origins in `backend/main.py` now include common local frontend hosts and fallback Vite ports, including `localhost` and `127.0.0.1` on `3000`, `5173`, `5174`, `5175`, and `5176`.

## 4. Backend Function and Module Inventory

This section covers the backend files that define request handlers, services, model workflows, or supporting runtime logic.

### 4.1 App Bootstrap, Request Models, and Top-Level Endpoints

`backend/main.py`

- `lifespan(app)`: Initializes SQLite and RAG startup state.
- `_build_default_cors_origins()`: Builds the fallback local-origin allowlist used when `CORS_ORIGINS` is unset.
- `_env_int(name, default, minimum)`: Reads bounded integer env settings.
- `api_key_guard(request, call_next)`: Optional API key gate for requests.
- `spatial_request_logger(request, call_next)`: Logs optimize request timing.
- `validation_exception_handler(request, exc)`: Returns structured `422` validation responses.
- `GeoJSONFeature`: Minimal request-side GeoJSON feature model with geometry validation.
- `_parcels_as_dicts(parcels)`: Converts Pydantic parcel objects to dictionaries.
- `ParcelRequest`: Request schema for suitability scoring.
- `ZoningRagRequest`: Request schema for zoning RAG.
- `SpatialGenerateRequest`: Request schema for geometry generation.
- `SpatialOptimizeRequest`: Request schema for NSGA-II optimization.
- `health_check()`: Simple liveness endpoint.
- `predict_suitability(request, body)`: Direct suitability scoring pipeline.
- `get_spatial_agent()`: Lazy singleton for `SpatialAgent`.
- `_has_rag_api_key()`: Currently hardcoded `True`; startup always attempts RAG init.
- `_load_rag_env_files(backend_dir)`: Loads `.env` files relevant to zoning RAG.
- `_enrich_parcel_ctx_from_lookup(parcel_ctx)`: Fills zoning context gaps from `ZONING_PARAMS`.
- `_build_rag_placeholder_answer(question, apn)`: Placeholder answer text when RAG is unavailable.
- `_init_rag()`: Creates the process-wide `RagService` instance and optional startup ingestion.
- `zoning_rag_ask(request, req)`: Session-aware zoning RAG handler.
- `spatial_generate(request)`: Geometry-generation endpoint.
- `spatial_optimize(request, body)`: NSGA-II optimization endpoint used by the planner page.
- `_get_copilot()`: Lazy singleton for `CopilotOrchestrator`.
- `CopilotQueryRequest`: SSE copilot request schema.
- `CounterfactualRequest`: Risk what-if request schema.
- `copilot_query(request, body)`: Streams SSE events from the copilot orchestrator.
- `risk_counterfactual(request, body)`: Computes rule-weight based what-if scoring.

### 4.2 Routers

`backend/routers/auth.py`

- `get_current_user(credentials, auth_service)`: JWT dependency used by `/auth/me`.
- `register(user_data, auth_service)`: Creates user and access token.
- `login(login_data, auth_service)`: Verifies credentials and returns token.
- `logout()`: Placeholder logout response only.
- `get_current_user_info(current_user)`: Returns authenticated user profile.

`backend/routers/orchestrator.py`

- `create_orchestration_plan(request)`: Creates async orchestration job.
- `get_job_status(job_id)`: Returns job status, stage, step states, and progress.
- `get_job_result(job_id)`: Returns completed job output.

### 4.3 Auth and Database Services

`backend/database.py`

- `init_db()`: Creates or repairs the SQLite `users` table.
- `get_db()`: Context manager for SQLite connections.

`backend/services/auth_service.py`

- `verify_password(plain_password, hashed_password)`: Bcrypt verification helper.
- `get_password_hash(password)`: Bcrypt hashing helper.
- `create_access_token(data, expires_delta)`: Creates JWT access token.
- `decode_access_token(token)`: Decodes JWT into `TokenPayload`.
- `AuthService.create_user(user_data)`: Inserts a new user into SQLite.
- `AuthService.authenticate_user(login_data)`: Validates login credentials.
- `AuthService.get_user_by_id(user_id)`: Fetches user profile by ID.
- `get_auth_service()`: Singleton factory for `AuthService`.

### 4.4 Shared Helpers

`backend/services/shared.py`

- `resolve_rag_persist_dir(backend_dir)`: Resolves Chroma persistence directory.
- `get_suitability_agent()`: Lazy singleton for `SuitabilityAgent`.

### 4.5 Orchestrator Runtime

`backend/services/job_store.py`

- `JobSteps`: Dataclass for per-stage status.
- `Job`: Dataclass for whole job state.
- `JobStore._env_int(name, default, minimum)`: Reads bounded store config.
- `JobStore._prune_locked()`: Prunes stale and overflow jobs.
- `JobStore.create_job(job_id)`: Creates initial job record.
- `JobStore.get_job(job_id)`: Fetches job state.
- `JobStore.update_job(...)`: Updates job fields atomically.
- `JobStore.update_step(job_id, step_name, step_status)`: Updates step state.
- `JobStore.list_jobs()`: Returns all jobs.
- `get_job_store()`: Singleton factory for `JobStore`.

`backend/services/orchestrator_service.py`

- `OrchestratorService._env_int(name, default, minimum)`: Reads orchestration env settings.
- `OrchestratorService.create_job(parcel_ids, enable_spatial)`: Creates job and background task.
- `OrchestratorService._execute_job(job_id, parcel_ids, enable_spatial)`: Runs the staged pipeline.
- `OrchestratorService.get_job_status(job_id)`: Reads job state.
- `OrchestratorService.get_job_result(job_id)`: Returns completed result or raises.
- `get_orchestrator_service()`: Singleton factory for `OrchestratorService`.

`backend/services/orchestrator_steps.py`

- `run_environment_stage(parcel_ids)`: Calls `SuitabilityAgent.predict()` on parcel IDs.
- `run_zoning_stage(parcel_ids)`: Runs batched zoning retrieval via `RagService`.
- `merge_outputs(env_data, zoning_data)`: Combines environment and zoning output by parcel ID.
- `run_spatial_stage(unified_data)`: Converts merged results into `ParcelRecord`s and runs a simplified NSGA-II optimization.

Operational orchestrator reality:

- Job state is still in-memory.
- Jobs do **not** survive backend restarts.
- The current frontend has no view wired to create, poll, or render orchestrator jobs.

### 4.6 Copilot and Explainability Services

`backend/services/copilot_orchestrator.py`

- `_sse(event_type, payload)`: Formats one SSE message.
- `_keyword_route(query)`: Fallback tool selection when LLM routing is unavailable.
- `CopilotOrchestrator._setup_gemini()`: Despite the name, initializes OpenAI client when available.
- `CopilotOrchestrator.stream(query, parcel_ids, parcel_features, history)`: Public SSE generator.
- `CopilotOrchestrator._pipeline(...)`: Full planner-copilot pipeline.
- `CopilotOrchestrator._plan_tools(query, parcel_ids)`: Chooses which tools to run.
- `CopilotOrchestrator._gemini_route(query)`: OpenAI-based JSON tool router.
- `CopilotOrchestrator._run_tool(tool_name, query, parcel_ids, parcel_features)`: Dispatches tool execution.
- `CopilotOrchestrator._run_environment(...)`: Environment analysis branch.
- `CopilotOrchestrator._run_zoning(...)`: Zoning retrieval branch.
- `CopilotOrchestrator._parse_target_mix(query)`: Extracts target land-use percentages from text.
- `CopilotOrchestrator._run_spatial(...)`: Spatial optimization branch for copilot.
- `CopilotOrchestrator._run_explain(...)`: Risk attribution branch.
- `CopilotOrchestrator._build_context(results, parcel_ids)`: Builds synthesis prompt context.
- `CopilotOrchestrator._synthesize(query, results, parcel_ids)`: Streams model-generated answer chunks when OpenAI is available.
- `CopilotOrchestrator._tool_start_message(tool_name)`: UI-friendly step labels.
- `CopilotOrchestrator._extract_land_use_plan(results)`: Pulls best plan assignments from results.
- `CopilotOrchestrator._clean_rag_answer(raw)`: Strips fallback citation wrappers.
- `CopilotOrchestrator._template_answer(query, results)`: Non-LLM fallback summary builder.

`backend/services/risk_explainer.py`

- `RiskExplainer.explain(parcel_props)`: Produces hazard contribution breakdown.
- `RiskExplainer.counterfactual(parcel_props, changes)`: Computes original vs modified rule score.

### 4.7 Environment Agent

`backend/agent/environment_agent/agent.py`

- `find_default_risk_data_path(base_dir)`: Finds the best precomputed risk GeoJSON file.
- `SuitabilityAgent.load_data(path)`: Loads APN-indexed `xgb_risk_score` data.
- `SuitabilityAgent._coerce_float(value)`: Numeric safety helper.
- `SuitabilityAgent._feature_based_risk(row)`: Fallback risk estimate from parcel features.
- `SuitabilityAgent.predict(parcels_df)`: Maps parcel IDs or features into environmental-risk-derived land-use suitability.

`backend/agent/environment_agent/main.py`

- `resolve_path(base_dir, candidate)`: Path resolver for CLI pipeline.
- `load_layer(path, name, target_crs)`: Reads and reprojects one hazard layer.
- `clip_to_parcels_bbox(hazard, parcels)`: Crops hazard datasets to parcel bounds.
- `_compute_flag_strtree(parcel_geoms, hazard_geoms, col_name)`: Vectorized hazard intersection flagger.
- `build_feature_frame(...)`: Loads parcels and all hazard layers, computes hazard flags and geometry features.
- `compute_rule_risk(gdf)`: Computes weighted rule score used as training target.
- `train_xgboost(gdf, random_state)`: Trains XGBoost regressor and writes `xgb_risk_score`.
- `export_geojson(gdf, out_path)`: Exports enriched parcel GeoJSON.
- `run_pipeline(args)`: Full offline training/export pipeline.
- `build_arg_parser()`: CLI parser.
- `main(argv)`: CLI entrypoint.

Environment-agent runtime reality:

- The deployed API does **not** run XGBoost at request time.
- The runtime path mostly loads precomputed `xgb_risk_score` values from GeoJSON and converts them into suitability heuristics.

### 4.8 Zoning Agent

`backend/agent/zoning_agent/rag_service.py`

- `RetrievedChunk`: Retrieved document segment dataclass.
- `RagService._make_chunk_id(...)`: Stable chunk ID helper.
- `RagService._detect_jurisdiction(pdf_path, text_sample)`: Detects City vs County context.
- `RagService._extract_zone_categories(text)`: Extracts zone categories.
- `RagService._extract_section_number(text)`: Pulls section references for citations.
- `RagService._get_zone_category(zoning_code)`: Maps zoning code to coarse zone category.
- `RagService.ingest_dir(data_dir)`: Ingests all PDFs into Chroma.
- `RagService._ingest_pdf(pdf_path, chunk_chars, overlap)`: Chunks and stores a single PDF.
- `RagService._split_with_sections(text)`: Preserves section markers during chunking.
- `RagService.retrieve(query, top_k, mmr, jurisdiction_filter, zone_filter)`: Chroma query plus optional MMR rerank.
- `RagService._mmr_vectorized(sim_to_query, doc_vecs, top_k, lambda_mult)`: Vectorized MMR selection.
- `RagService.answer(question, parcel_ctx, retrieved, history)`: Produces answer from retrieved chunks and conversation history.
- `RagService.construct_query(question, parcel_ctx)`: Adds jurisdiction and zone hints to the retrieval query.
- `RagService.get_jurisdiction_filter(parcel_ctx)`: Returns City/County filter for Chroma query.
- `RagService.get_zone_filter(parcel_ctx)`: Returns zone-category filter for Chroma query.
- `ChatSessionStore.ensure(session_id)`: Creates or refreshes chat session.
- `ChatSessionStore.set_parcel(session_id, apn, ctx)`: Stores active parcel context.
- `ChatSessionStore.get_parcel(session_id)`: Fetches parcel context for session.
- `ChatSessionStore.add_turn(session_id, question, answer)`: Stores Q/A history.
- `ChatSessionStore.get_history(session_id)`: Returns chat history.

Other zoning-agent support files:

- `backend/agent/zoning_agent/zoning_lookup.py`: Local zoning-code lookup used to enrich parcel context.
- `backend/agent/zoning_agent/main.py`: Offline zoning assignment/export pipeline, not wired into the HTTP app.
- `backend/agent/zoning_agent/merge_outputs.py`: Offline merge utility for environment + zoning GeoJSON artifacts.
- `backend/agent/zoning_agent/init_rag.py`: Bootstraps Chroma from PDFs.
- `backend/agent/zoning_agent/ingest_cli.py`: CLI wrapper around ingestion.

### 4.9 Spatial Agent

`backend/agent/spatial_agent/agent.py`

- `SpatialAgent.generate(parcels, generation_type, parameters)`: Dispatches geometry generation mode.
- `SpatialAgent._subdivide_parcels(...)`: Creates subdivision polygons.
- `SpatialAgent._create_buffer_zones(...)`: Buffers parcel geometries.
- `SpatialAgent._generate_voronoi(...)`: Builds Voronoi regions from parcel centroids.
- `SpatialAgent._generate_grid(...)`: Generates grid cells intersecting parcel area.

`backend/agent/spatial_agent/spatial/geo.py`

- `_clamp(value, lower, upper)`: Numeric clamp helper.
- `_safe_float(value, default)`: Safe numeric parse helper.
- `_extract_geometry(feature)`: Converts GeoJSON to valid Shapely geometry.
- `_geometry_area_m2(geometry)`: Computes area in square meters.
- `normalize_risk_score(properties)`: Normalizes risk from available parcel properties.
- `extract_suitability_scores(properties, land_use_labels)`: Pulls per-use suitability scores from feature properties.
- `infer_allowed_use_labels(properties, land_use_labels)`: Infers permitted uses from parcel metadata.
- `build_parcels_from_geojson(features, land_use_labels)`: Converts GeoJSON features to typed `ParcelRecord`s.
- `build_adjacency_from_geojson(features, adjacency_predicate, progress_callback)`: Builds adjacency graph with `STRtree`.
- `build_context_from_geojson(...)`: Bundles parcels + adjacency into `OptimizationContext`.

`backend/agent/spatial_agent/spatial/objectives.py`

- `zoning_violation_penalty(chromosome, context)`: Penalizes assignments outside allowed uses.
- `make_green_area_deviation(target_fraction)`: Penalizes deviation from green-space target.
- `environmental_risk_exposure(chromosome, context)`: Penalizes built area exposed to environmental risk.
- `fragmentation_penalty(chromosome, context)`: Penalizes mixed boundaries across adjacent parcels.
- `make_land_use_balance_penalty(target_mix)`: Penalizes deviation from requested use mix.
- `default_objectives()`: Default objective tuple.

`backend/agent/spatial_agent/spatial/optimizer.py`

- `SpatialOptimizer.__post_init__()`: Validates objective set.
- `SpatialOptimizer.optimize(parcels, adjacency, progress_callback, progress_every_generations)`: Runs NSGA-II on typed parcel records.
- `SpatialOptimizer.optimize_geojson_features(...)`: Preprocesses raw GeoJSON and then calls `optimize()`.
- `SpatialOptimizer._decode_plan(candidate, context)`: Converts chromosome into parcel assignments.
- `SpatialOptimizer._objective_name(function, index)`: Human-readable objective naming helper.
- `SpatialOptimizer._coerce_adjacency(adjacency)`: Normalizes adjacency map input.
- `SpatialOptimizer._notify_progress(progress_callback, event)`: Safe progress-callback wrapper.

`backend/agent/spatial_agent/spatial/config.py`

- `NSGA2Config`: Search hyperparameter model.
- `SpatialConfig`: Top-level optimizer configuration.

`backend/agent/spatial_agent/spatial/types.py`

- `ParcelRecord`, `OptimizationContext`, `Individual`, `ParcelAssignment`, `OptimizationPlan`, `OptimizationResult`: Typed optimizer datamodels.

### 4.10 Utility Modules and Schemas

`backend/utils/features.py`

- `_deterministic_fallback(parcel_id, field_name, lower, upper)`: Stable pseudo-random fallback values.
- `attach_features(parcels)`: Extracts or synthesizes parcel features for suitability endpoint.
- `rename_features_for_model(df)`: Renames frontend feature keys to model-facing names.

`backend/utils/geojson_output.py`

- `build_output_geojson(input_features, predictions)`: Merges prediction rows back into GeoJSON features.

Schema-only modules:

- `backend/schemas/auth.py`
- `backend/schemas/orchestrator.py`

These provide request/response DTOs rather than execution logic.

### 4.11 Tests and Legacy / Unwired Backend Code

`backend/tests/test_cors_defaults.py`

- Verifies that the default backend CORS configuration allows the local dev-origin combinations now expected by the frontend, including fallback Vite ports such as `5174`.

`backend/agent/orchestrator_agent/orchestrator.py`

- Defines `JobStatus`, `JobStep`, `JobPlan`, and `OrchestratorAgent`.
- This file appears to be an earlier planning abstraction.
- The running FastAPI app does **not** import or use it; the live orchestration path uses `routers/orchestrator.py`, `services/orchestrator_service.py`, `services/orchestrator_steps.py`, and `services/job_store.py`.

## 5. Frontend Shared State and Utility Inventory

### 5.1 Shared Contexts

`frontend/src/context/AuthContext.tsx`

- Stores authenticated user in local state plus localStorage.
- `login()` calls `POST /auth/login`.
- `register()` calls `POST /auth/register`.
- `validateToken()` calls `GET /auth/me` after optimistic localStorage restore.
- `logout()` is still frontend-local only; it clears localStorage and does **not** call `POST /auth/logout`.

`frontend/src/context/PlannerSettingsContext.tsx`

- Holds planner preferences and UI behavior settings.
- Persists settings in browser localStorage.
- These settings shape optimization request inputs and zoning-chat behavior.

`frontend/src/context/PlannerWorkspaceContext.tsx`

- This is now the main cross-page planning state store.
- Holds:
  - loaded parcel features
  - loaded feature map
  - total loaded parcels
  - selected parcel IDs
  - selected feature map
  - primary selected parcel ID and properties
  - generated plans
  - objective names
  - active plan index
  - latest optimization metadata
- Exposes actions for:
  - registering loaded parcel features
  - replacing or extending selection
  - toggling selection
  - selecting all loaded parcels
  - setting the primary selected parcel
  - storing optimization results
  - setting the active plan index

### 5.2 Frontend Workspace Utility Layer

`frontend/src/utils/plannerWorkspace.ts`

- Defines robust frontend-side field fallbacks for parcel ID, risk, zone, jurisdiction, and suitability properties.
- Treats the current source mode as `Static GeoJSON`.
- Builds feature maps and optimization metadata objects used by the shared workspace context.
- Derives parcel summaries for the Workbench from fields the current dataset actually supports.

Current meaningful derived planner signals on Workbench now include:

- `area_m2`
- `perimeter_m`
- `rule_risk_score`
- `xgb_risk_score`
- `has_flood`
- `has_fault`
- `has_liquefaction`
- `is_steep`
- `is_fire_zone`
- `in_esa`
- `in_mscp`

This matters because the current parcel dataset does **not** consistently expose zoning/jurisdiction metadata for every parcel, so the Workbench no longer centers its summary cards on values that are usually null.

## 6. Frontend Page Inventory

| Page / View | Route or activation path | Access | Purpose | Main data sources | Backend/API usage |
| --- | --- | --- | --- | --- | --- |
| `WelcomePage` | `/welcome` | Public | Entry/marketing page. | Static content. | None |
| `LoginPage` | `/login` | Public | Email/password login. | Local form state. | `POST /auth/login` via `AuthContext` |
| `RegisterPage` | `/register` | Public | Account creation. | Local form state. | `POST /auth/register` via `AuthContext` |
| `WorkbenchPage` | `activeView === 'workbench'` inside `/dashboard/*` | Protected | Planning command center with neutral parcel overview map, workspace summaries, selection insight, readiness actions, system status, and optimization snapshot. | Static parcel GeoJSON, shared workspace state, planner settings, authenticated user. | No direct backend call |
| `Environmental Agent` (`HomePage`) | `activeView === 'environmental'` | Protected | Environmental risk inspection, parcel selection, optimization controls, and plan-generation entry point. | Static parcel GeoJSON, overlay GeoJSON, shared workspace state, planner settings. | `POST /spatial/optimize` |
| `LayersPage` | `activeView === 'layers'` | Protected | Split view for parcel tagging + zoning RAG chat. | Static parcel GeoJSON, shared primary parcel selection, local chat state, planner settings. | `POST /rag/zoning/ask` |
| `PlanGalleryPage` | `activeView === 'plans'` | Protected | Compare generated plans, inspect overlays, export PDF report. | Shared generated plans and objective names, static overlay GeoJSON. | No backend call after plans exist |
| `CopilotPage` | `activeView === 'copilot'` | Protected | Conversational planner assistant with agent timeline, live map coloring, and explanation drawer. | Static parcel GeoJSON, local selected parcel props, SSE state, agent results. | `POST /copilot/query` and `POST /risk/counterfactual` |
| `SettingsPage` | `activeView === 'settings'` | Protected | Runtime planner preferences and read-only account summary. | `PlannerSettingsContext`, `AuthContext.user`, localStorage. | No direct backend call |

### 6.1 Page Details

`WorkbenchPage`

- This is now the default protected dashboard landing page.
- It is explicitly **not** an environmental choropleth page.
- It uses a **neutral parcel overview map** and treats the map as the planner's operational workspace.
- It shows:
  - hero/header actions to open Environmental Agent, Layers, and Plans
  - summary cards
  - planning area overview
  - selection insight
  - recommended next actions
  - planning workflow/status
  - latest optimization snapshot
  - system/data status
- It reads loaded parcel features, selection state, and optimization results from `PlannerWorkspaceContext`.
- It does **not** call the backend directly.

`Environmental Agent` (`HomePage`)

- This is the current environmental/risk analysis page.
- It preserves:
  - environmental color-coded parcel map behavior
  - parcel click and multi-select behavior
  - parcel info sidebar
  - 2D/3D toggle
  - spatial optimization controls
  - plan generation through `POST /spatial/optimize`
- It now writes loaded parcel features, selection state, and optimization results into the shared workspace context so Workbench and Plans can reuse them.

`LayersPage`

- Uses parcel tagging plus zoning RAG chat.
- Reads and updates the shared primary selected parcel.
- This means Workbench can hand off a parcel-selection context into Layers without new routing.
- It remains the main UI consumer of `POST /rag/zoning/ask`.

`PlanGalleryPage`

- No longer depends on plan props from `App.tsx`.
- Reads `generatedPlans`, `objectiveNames`, and `activePlanIndex` from `PlannerWorkspaceContext`.
- Does not call the backend to regenerate plans.
- Still builds reports and overlays locally in the browser.

`CopilotPage`

- Remains the live conversational assistant surface.
- Uses `useCopilotStream()` to push a query and listen to SSE agent events.
- Still maintains its own local map/selection flow rather than reading from `PlannerWorkspaceContext`.
- Recolors the live map based on environment or spatial results streamed back from the backend.

`SettingsPage`

- Uses `PlannerSettingsContext` and `AuthContext` only.
- No settings are saved to the backend.
- Settings remain local/browser-persisted runtime controls.

## 7. Frontend-to-Backend Mapping

### 7.1 Direct Page Mapping

| Frontend surface | Invocation path | Backend endpoint(s) | Notes |
| --- | --- | --- | --- |
| `App` startup | `AuthProvider -> validateToken()` | `GET /auth/me` | Runs in background after optimistic localStorage restore. |
| `LoginPage` | `useAuth().login()` | `POST /auth/login` | Stores token + user in localStorage. |
| `RegisterPage` | `useAuth().register()` | `POST /auth/register` | Stores token + user in localStorage. |
| `Environmental Agent` | `apiClient.optimizeSpatialPlans()` | `POST /spatial/optimize` | Uses selected map features, mix targets, and runtime settings. |
| `LayersPage` | `ZoningChatPanel.sendAutoQuery()` and `send()` | `POST /rag/zoning/ask` | Passes APN/context/session depending on settings. |
| `CopilotPage` | `useCopilotStream.sendQuery()` | `POST /copilot/query` | SSE streaming endpoint. |
| `CopilotPage` | `ExplanationDrawer.handleRunCounterfactual()` | `POST /risk/counterfactual` | Rule-weight based what-if scoring. |

### 7.2 Dashboard State and Data Sharing

Current shared planner data path:

1. Environmental Agent loads parcel features from static GeoJSON and registers them in `PlannerWorkspaceContext`.
2. Environmental Agent updates shared parcel selection as the user clicks parcels.
3. Workbench reads those loaded features and selections to show command-center summaries.
4. Environmental Agent writes optimization responses into shared workspace state.
5. PlanGallery reads the generated plans and objective names from shared workspace state.
6. Layers reads and updates the shared primary parcel selection to keep zoning-chat context aligned.

Important exception:

- `CopilotPage` does **not** currently share this workspace context. It still uses its own selection flow.

### 7.3 Backend Endpoints With No Current Frontend Consumer

- `GET /health`
- `POST /auth/logout`
- `POST /predict_suitability`
- `POST /spatial/generate`
- `POST /orchestrator/plan`
- `GET /orchestrator/status/{job_id}`
- `GET /orchestrator/result/{job_id}`

### 7.4 Frontend API Methods That Are Unused or Placeholder

From `frontend/src/utils/api.ts`:

- `fetchMetrics()` -> `/metrics`
- `fetchZones(region)` -> `/zones`
- `runOptimization(zones)` -> `/optimize`
- `runZoningAgent(input)` -> `/agents/zoning`
- `runEnvironmentalAgent(input)` -> `/agents/environmental`
- `runPopulationAgent(input)` -> `/agents/population`
- `getSuitabilityScores()` -> `/predict_suitability`

Current status:

- The first six are unused placeholder methods and do not match live backend endpoints.
- `getSuitabilityScores()` does match a live backend endpoint, but no current page calls it.

## 8. How the Main Models and Agents Work Together

### 8.1 Authentication Workflow

1. `backend/main.py` startup calls `init_db()` to ensure the SQLite users table exists.
2. `LoginPage` and `RegisterPage` call `AuthContext`.
3. `AuthContext` stores `access_token` and `user` in browser localStorage.
4. On future app loads, `AuthContext` restores the cached session immediately and then validates it with `GET /auth/me`.
5. Protected pages are gated by `ProtectedRoute` in `frontend/src/App.tsx`.

Important details:

- Frontend logout is currently local-only. It removes localStorage state and never calls `POST /auth/logout`.
- `AuthContext` still uses a single `VITE_API_URL` base and does not retry `/api` vs non-`/api` variants.
- Backend CORS defaults were recently widened for local dev so auth preflights from common Vite ports work out of the box.

### 8.2 Environmental Risk and Suitability Workflow

Offline pipeline:

1. `backend/agent/environment_agent/main.py` loads parcel geometry plus hazard layers.
2. It computes binary hazard flags using parallelized `STRtree` intersections.
3. It computes `rule_risk_score` from weighted hazard flags.
4. It trains XGBoost to predict that rule score.
5. It exports GeoJSON with `xgb_risk_score` and hazard attributes.

Runtime API path:

1. `POST /predict_suitability` accepts parcel GeoJSON features.
2. `attach_features()` extracts feature columns from parcel properties or synthesizes deterministic fallback values.
3. `SuitabilityAgent.predict()` looks up precomputed `xgb_risk_score` by parcel ID when available.
4. If lookup misses and usable feature values exist, `_feature_based_risk()` estimates risk.
5. Risk is converted into per-use suitability:
   - residential: most risk-sensitive
   - commercial: moderately risk-sensitive
   - industrial: least risk-sensitive of the built uses
   - green: increases as risk increases
6. `build_output_geojson()` merges predictions back into original GeoJSON.

Current UI reality:

- The dashboard pages do **not** call `/predict_suitability`.
- The visible parcel risk layer is presently driven by precomputed parcel GeoJSON loaded from `frontend/public`.

### 8.3 Zoning RAG Workflow

Data preparation:

1. PDF zoning documents live under `backend/agent/zoning_agent/src/data/`.
2. `RagService.ingest_dir()` splits PDFs into large overlapping chunks.
3. Chunks are stored in Chroma with metadata such as jurisdiction, section number, source file, and zone categories.
4. Sentence-transformer embeddings are generated locally; no embedding API key is required.

Runtime request flow for `/rag/zoning/ask`:

1. The frontend sends a question, and optionally `apn`, `context`, and `session_id`.
2. `ChatSessionStore` creates or refreshes the chat session.
3. If APN/context were provided, the session remembers the parcel context.
4. `_enrich_parcel_ctx_from_lookup()` fills missing zoning constraints from `ZONING_PARAMS`.
5. `RagService.construct_query()` adds jurisdiction and zoning hints to the retrieval query.
6. `RagService.retrieve()` queries Chroma, optionally reranks with vectorized MMR, and narrows by jurisdiction/zone category when available.
7. `RagService.answer()` generates the answer:
   - with OpenAI if configured
   - otherwise as structured chunk excerpts
8. The response returns `answer`, `session_id`, `apn`, and `citations`.

Frontend use:

- `LayersPage` is the direct zoning-chat page.
- `CopilotOrchestrator` also instantiates `RagService` inside its zoning branch.

### 8.4 Workbench and Shared Workspace Workflow

This is the main frontend-only coordination layer added on top of the older planner flow.

1. Workbench loads as the default protected dashboard landing view.
2. Environmental Agent registers loaded parcel features into `PlannerWorkspaceContext`.
3. Shared workspace state stores selected parcel IDs, loaded feature maps, generated plans, and optimization metadata.
4. Workbench reads that state to show:
   - parcel counts
   - selected area
   - primary environmental/development constraints
   - protected parcel share
   - optimization snapshot
   - workflow readiness
5. Workbench action buttons route the user into the correct existing live workflow:
   - Environmental Agent for selection and optimization
   - Layers for zoning questions
   - Plans for plan review

Important current design choice:

- Because the current parcel dataset does not reliably expose zoning/jurisdiction values, Workbench surfaces **constraint- and risk-based planning metrics** instead of null-heavy zoning summaries.

### 8.5 Spatial Optimization Workflow

Main planner path used by Environmental Agent:

1. User selects parcel features from the map.
2. Environmental Agent builds a payload from selected GeoJSON features plus planner settings.
3. `POST /spatial/optimize` receives:
   - parcel features
   - target mix
   - population size
   - generation count
   - adjacency controls
   - debug / interactive settings
4. The endpoint may automatically cap generations/population or disable adjacency for large jobs.
5. It builds the objective set:
   - zoning violation penalty
   - green area deviation
   - environmental risk exposure
   - fragmentation penalty
   - optional land-use balance penalty if a target mix was provided
6. `SpatialOptimizer.optimize_geojson_features()` converts raw features to `ParcelRecord`s and builds adjacency graph.
7. NSGA-II evolves candidate allocations.
8. The Pareto front is decoded into `plans`, each containing parcel-level assignments.
9. Environmental Agent stores the returned plans and objective names in `PlannerWorkspaceContext`.
10. PlanGallery consumes those stored plans without calling the backend again.

Feature extraction details from `build_parcels_from_geojson()`:

- Parcel ID can come from `parcel_id`, `APN`, `PARCELID`, `PARNO`, `id`, or feature `id`.
- Risk can come from `risk_score_norm`, `environmental_risk`, `xgb_risk_score`, or `rule_risk_score`.
- Suitability can come from `suitability_<use>` or `<use>` properties.
- Allowed uses are inferred from `allowed_uses`, `ZONING_CODE`, and general-plan text when possible.

Secondary spatial path:

- `POST /spatial/generate` uses `SpatialAgent.generate()` for geometry-generation tasks.
- No current page calls it.

### 8.6 Planner Copilot Workflow

Frontend flow:

1. User selects parcels on the copilot map.
2. `CopilotPage` extracts selected parcel IDs and selected parcel properties.
3. `useCopilotStream.sendQuery()` posts to `/copilot/query`.
4. The frontend reads streamed SSE events and updates:
   - chat messages
   - agent timeline
   - environmental coloring
   - land-use assignments
   - risk explanations

Backend flow:

1. `CopilotOrchestrator._plan_tools()` decides which tools to run:
   - OpenAI-based tool selection if available
   - keyword routing otherwise
2. Tools are run sequentially:
   - `analyze_environment`
   - `query_zoning`
   - `optimize_land_use`
   - `explain_risk`
3. Each tool emits `agent_start` and `agent_complete` SSE events.
4. If OpenAI is available, `_synthesize()` streams natural-language answer chunks.
5. Otherwise `_template_answer()` builds a deterministic markdown summary.
6. The final SSE event includes `summary` and optional `land_use_plan`.

What each copilot tool actually uses:

- `analyze_environment`: Calls `SuitabilityAgent.predict()` on parcel IDs only.
- `query_zoning`: Creates a `RagService`, retrieves chunks, and asks for a synthesized zoning answer.
- `optimize_land_use`: Runs a smaller NSGA-II optimization directly on selected parcel features.
- `explain_risk`: Uses `RiskExplainer.explain()` to compute hazard contributions.

### 8.7 Risk Explanation and Counterfactual Workflow

1. `CopilotOrchestrator._run_explain()` creates `RiskExplainer` output for up to five selected parcels.
2. `CopilotPage` stores those explanations and shows the explanation drawer button.
3. `ExplanationDrawer` lets the user toggle hazard flags such as flood, fault, liquefaction, and fire hazard.
4. `POST /risk/counterfactual` sends original parcel properties plus the hazard changes.
5. `RiskExplainer.counterfactual()` recomputes rule score using the same hazard weights and returns original score, modified score, delta, and applied changes.

### 8.8 Background Orchestrator Workflow

This is separate from the live Workbench, Environmental Agent, and Copilot paths.

Request flow:

1. Client would call `POST /orchestrator/plan` with parcel IDs and optional `enable_spatial`.
2. `OrchestratorService.create_job()` creates a UUID and writes initial job state to `JobStore`.
3. A background task runs `_execute_job()` under a concurrency semaphore.
4. Stages run in order:
   - environment
   - zoning
   - merge
   - optional spatial
5. `GET /orchestrator/status/{job_id}` returns progress and stage state.
6. `GET /orchestrator/result/{job_id}` returns the final merged payload.

Current status:

- The backend path is implemented.
- The frontend currently has **no UI wired** to create, poll, or render these jobs.

## 9. Important Integration Findings

### 9.1 Workbench and Environmental Agent are now deliberately separate roles

- Workbench is the planner command center and neutral operational map.
- Environmental Agent is the environmental-risk analysis surface and optimization entry point.
- This is the correct current product architecture and should replace any earlier descriptions that treated the old planner/environment page as the dashboard home.

### 9.2 Live planner pages still use static parcel data, not live suitability scoring

- Workbench, Environmental Agent, Layers, and Copilot all rely on static parcel GeoJSON loaded from `frontend/public`.
- `POST /predict_suitability` is live, but no page currently calls it.
- This means the visible parcel risk layer is presently driven by exported static GeoJSON, not by the REST scoring path.

### 9.3 Shared workspace state now connects multiple dashboard views

- `PlannerWorkspaceContext` is now the main cross-page state holder for parcel loading, selection, plans, and optimization metadata.
- Workbench, Environmental Agent, Layers, and Plans are now better aligned around one source of truth.
- Copilot is not yet integrated into that shared workspace state.

### 9.4 Auth routing is still less resilient than the main API client

- `frontend/src/utils/api.ts` retries both base URLs with and without `/api`.
- `frontend/src/context/AuthContext.tsx` does **not** do that.
- Auth deployment is therefore still more fragile than the rest of the frontend API layer if `VITE_API_URL` is set inconsistently.

### 9.5 Several backend endpoints are implemented but not surfaced in UI

- `/predict_suitability`
- `/spatial/generate`
- `/orchestrator/*`
- `/auth/logout`
- `/health`

### 9.6 Several frontend API methods are placeholders only

- `/metrics`
- `/zones`
- `/optimize`
- `/agents/zoning`
- `/agents/environmental`
- `/agents/population`

These are not part of the running backend API surface.

### 9.7 The dashboard is still state-driven, not URL-driven

- Only `/dashboard/*` is routed.
- Individual dashboard views are not deep-linkable by URL.
- A refresh keeps the user inside the protected shell, but not on named URL routes per page.

### 9.8 There is a legacy orchestrator module that is not part of the running request path

- `backend/agent/orchestrator_agent/orchestrator.py` looks like an earlier orchestration abstraction.
- It is not imported by `backend/main.py`.
- The production request path uses the router/service/job-store stack instead.

### 9.9 Naming drift still exists around “Gemini” vs OpenAI

- `backend/services/copilot_orchestrator.py` still uses names like `_setup_gemini()` and comments referencing Gemini.
- The actual implementation is OpenAI-based when an OpenAI key is present.
- The code runs, but the naming is inconsistent and can mislead future maintainers.

## 10. Practical End-to-End Picture

If you look at the codebase as one system, the current real user journey is:

1. User authenticates through `/auth/login` or `/auth/register`.
2. Protected dashboard loads into **Workbench** by default.
3. Workbench shows the neutral planning overview and routes the user into the correct workflow.
4. Environmental Agent selects parcels from static map data and sends those selected features to `/spatial/optimize`.
5. PlanGallery visualizes the returned Pareto plans without additional backend calls.
6. Layers tags one parcel and asks `/rag/zoning/ask` for zoning guidance.
7. Copilot sends selected parcel IDs and properties to `/copilot/query`, which may call environment, zoning, spatial, and explanation tools, then streams the response.
8. If the user opens the explanation drawer, `/risk/counterfactual` computes what-if changes to hazard-based risk.

The currently disconnected but ready-to-use backend capabilities are:

- direct suitability scoring via `/predict_suitability`
- geometry generation via `/spatial/generate`
- async orchestration jobs via `/orchestrator/*`
