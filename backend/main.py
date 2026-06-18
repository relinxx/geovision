"""
GeoVision Backend API

FastAPI application providing REST endpoints for:
- Parcel suitability prediction (environmental risk analysis)
- Zoning RAG (Retrieval-Augmented Generation) chat interface
- Orchestrator agent for multi-step workflow planning
- Spatial agent for geometric data generation

Architecture:
    - Environment Agent: Provides pre-computed environmental risk scores
    - Zoning Agent: RAG-based chat for zoning regulation queries
    - Orchestrator Agent: Coordinates multi-agent workflows
    - Spatial Agent: Generates spatial data (subdivisions, buffers, etc.)
"""
from __future__ import annotations

import logging
import math
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, model_validator
from shapely.geometry import shape as shapely_shape
from shapely.errors import ShapelyError
from shapely.validation import explain_validity

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address
except ImportError:
    Limiter = None  # type: ignore[assignment]
    RateLimitExceeded = None  # type: ignore[assignment]
    _rate_limit_exceeded_handler = None  # type: ignore[assignment]

    def get_remote_address(request: Request) -> str:
        client = getattr(request, "client", None)
        return getattr(client, "host", "unknown")

from agent.spatial_agent.agent import SpatialAgent
from agent.spatial_agent.spatial.config import NSGA2Config, SpatialConfig
from agent.spatial_agent.spatial.objectives import (
    default_objectives,
    make_land_use_balance_penalty,
)
from agent.spatial_agent.spatial.optimizer import SpatialOptimizer
from agent.zoning_agent.rag_service import ChatSessionStore, RagService
from agent.zoning_agent.zoning_lookup import get_zoning_params
from config import get_settings
from routers.auth import router as auth_router
from routers.orchestrator import router as orchestrator_router
from routers.saved_maps import router as saved_maps_router
from services.nearby_parcels import (
    NearbyParcelDataError,
    NearbyParcelLookupError,
    NearbyParcelNotFoundError,
    get_nearby_parcels_service,
)
from services.redis_store import get_redis_store
from services.assignment_explainer import explain_assignment
from services.spatial_cache import (
    build_spatial_optimize_cache_key,
    get_spatial_optimize_cache_ttl_seconds,
    normalize_target_mix,
)
from services.spatial_compatibility import (
    build_neighbor_pairs,
    build_parcel_feature_lookup,
    explain_assignment_spatial_context,
    explain_spatial_compatibility,
    make_spatial_compatibility_objective,
    score_spatial_compatibility,
)
from services.shared import get_suitability_agent, resolve_rag_persist_dir
from utils.features import FEATURE_SCHEMA, attach_features
from utils.geojson_output import build_output_geojson
from utils.helpers import env_int


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_rag()
    yield


app = FastAPI(title="GeoVision Backend", version="0.1.0", lifespan=lifespan)
settings = get_settings()

# Rate limiter — keyed by IP address
if Limiter is not None:
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    if RateLimitExceeded is not None and _rate_limit_exceeded_handler is not None:
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
else:
    class _NoopLimiter:
        def limit(self, _rule: str):
            def decorator(func):
                return func

            return decorator

    limiter = _NoopLimiter()
    app.state.limiter = limiter
    logging.warning("slowapi is not installed; request rate limiting is disabled.")


# Add CORS middleware to allow frontend requests.
# Production deployments should set CORS_ORIGINS explicitly.
cors_origins = settings.cors_origins
allow_credentials = cors_origins != ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,  # In production, set CORS_ORIGINS to explicit frontend origins.
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount orchestrator routes (plan/status/result).
app.include_router(orchestrator_router)

# Mount authentication routes (register/login/logout).
app.include_router(auth_router)
app.include_router(saved_maps_router, prefix="/api")

_rag: Optional[RagService] = None
_rag_unavailable_reason: Optional[str] = None
_spatial_agent: Optional[SpatialAgent] = None
_nearby_parcels_service = None
_redis_store = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def _get_redis_store_cached():
    global _redis_store
    if _redis_store is None:
        _redis_store = get_redis_store()
    return _redis_store


def _get_nearby_parcels_service():
    global _nearby_parcels_service
    if _nearby_parcels_service is None:
        _nearby_parcels_service = get_nearby_parcels_service()
    return _nearby_parcels_service


_chat_sessions = ChatSessionStore(
    max_sessions=env_int("RAG_MAX_SESSIONS", default=5000, minimum=100),
    ttl_seconds=env_int("RAG_SESSION_TTL_SECONDS", default=86400, minimum=300),
)
_api_key = settings.geovision_api_key




@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    if not _api_key:
        return await call_next(request)

    public_paths = {
        "/health",
        "/api/health",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
    if request.url.path in public_paths:
        return await call_next(request)

    incoming = request.headers.get("x-api-key")
    if incoming != _api_key:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    return await call_next(request)


@app.middleware("http")
async def spatial_request_logger(request: Request, call_next):
    tracked_paths = {"/spatial/optimize", "/api/spatial/optimize"}
    if request.url.path not in tracked_paths:
        return await call_next(request)

    started_at = time.perf_counter()
    logging.info(
        "[spatial-request] started method=%s path=%s query=%s",
        request.method,
        request.url.path,
        request.url.query,
    )
    try:
        response = await call_next(request)
    except Exception:
        logging.error(
            "[spatial-request] failed method=%s path=%s elapsed=%.3fs",
            request.method,
            request.url.path,
            time.perf_counter() - started_at,
            exc_info=True,
        )
        raise

    logging.info(
        "[spatial-request] completed method=%s path=%s status=%s elapsed=%.3fs",
        request.method,
        request.url.path,
        response.status_code,
        time.perf_counter() - started_at,
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logging.error(
        "Request validation failed: method=%s path=%s errors=%s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


class GeoJSONFeature(BaseModel):
    """Minimal GeoJSON Feature shape — permissive on extra fields for forward-compat."""

    model_config = {"extra": "allow"}

    type: str = "Feature"
    geometry: Optional[Dict[str, Any]] = None
    properties: Optional[Dict[str, Any]] = None
    id: Optional[Any] = None

    @model_validator(mode="after")
    def validate_geometry(self) -> "GeoJSONFeature":
        if self.geometry is None:
            return self
        try:
            geom = shapely_shape(self.geometry)
        except (ShapelyError, ValueError, TypeError) as exc:
            raise ValueError(f"Invalid GeoJSON geometry: {exc}") from exc
        if not geom.is_valid:
            logging.warning(
                "GeoJSON geometry is topologically invalid; spatial processing will attempt repair. "
                "Reason: %s",
                explain_validity(geom),
            )
        return self


def _parcels_as_dicts(parcels: List[GeoJSONFeature]) -> List[Dict[str, Any]]:
    return [f.model_dump(exclude_none=False) for f in parcels]


# ── Planning metrics ──────────────────────────────────────────────────────────
_AVG_UNIT_SIZE_M2 = 85.0
_AVG_HOUSEHOLD_SIZE = 2.5
_WHO_GREEN_M2_PER_PERSON = 9.0
_TAX_USD_PER_M2: Dict[str, float] = {
    "residential": 12.0,
    "commercial": 18.0,
    "industrial": 9.0,
    "green": 0.0,
}
_HAZARD_FLAGS = ("has_flood", "has_fault", "has_liquefaction", "is_steep", "is_fire_zone")


def _build_parcel_lookup(
    parcel_dicts: List[Dict[str, Any]],
) -> tuple[Dict[str, Dict], Dict[str, float]]:
    """Return (props_map, area_map) keyed by parcel_id string."""
    try:
        from pyproj import Geod
        _geod: Any = Geod(ellps="WGS84")
    except Exception:
        _geod = None

    props_map: Dict[str, Dict] = {}
    area_map: Dict[str, float] = {}

    for feat in parcel_dicts:
        props = feat.get("properties") or {}
        pid = str(
            props.get("APN") or props.get("apn") or
            props.get("parcel_id") or props.get("PARCELID") or
            feat.get("id") or ""
        ).strip()
        if not pid:
            continue
        props_map[pid] = props

        area: Optional[float] = None
        for k in ("area_m2", "AREA_M2", "Shape_Area"):
            v = props.get(k)
            if v is not None:
                try:
                    area = float(v)
                    break
                except (TypeError, ValueError):
                    pass

        if not area or area <= 0:
            geom_data = feat.get("geometry")
            if geom_data and _geod:
                try:
                    geom = shapely_shape(geom_data)
                    area_abs, _ = _geod.geometry_area_perimeter(geom)
                    area = float(abs(area_abs))
                except Exception:
                    area = 500.0
            else:
                area = 500.0

        area_map[pid] = area or 500.0

    return props_map, area_map


def _compute_planning_metrics(
    props_map: Dict[str, Dict],
    area_map: Dict[str, float],
    assignments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    area_by_use: Dict[str, float] = {
        "residential": 0.0, "commercial": 0.0, "industrial": 0.0, "green": 0.0,
    }
    hazard_built = 0

    for a in assignments:
        pid = str(a.get("parcel_id", ""))
        label = str(a.get("use_label", "")).lower()
        area = area_map.get(pid, 500.0)
        props = props_map.get(pid, {})

        if label in area_by_use:
            area_by_use[label] += area

        if label != "green":
            if any(int(props.get(f, 0) or 0) for f in _HAZARD_FLAGS):
                hazard_built += 1

    housing_units = int(area_by_use["residential"] / _AVG_UNIT_SIZE_M2)
    residents = int(housing_units * _AVG_HOUSEHOLD_SIZE)
    green_per_resident = (
        round(area_by_use["green"] / residents, 1) if residents > 0
        else round(area_by_use["green"], 1)
    )
    tax_yield = int(sum(area_by_use.get(u, 0.0) * r for u, r in _TAX_USD_PER_M2.items()))
    total_area = sum(area_by_use.values())

    return {
        "housing_units": housing_units,
        "estimated_residents": residents,
        "green_space_per_resident_m2": green_per_resident,
        "who_green_target_m2": _WHO_GREEN_M2_PER_PERSON,
        "hazard_built_parcels": hazard_built,
        "total_parcels": len(assignments),
        "estimated_annual_tax_usd": tax_yield,
        "area_m2": {
            "residential": round(area_by_use["residential"]),
            "commercial": round(area_by_use["commercial"]),
            "industrial": round(area_by_use["industrial"]),
            "green": round(area_by_use["green"]),
            "total": round(total_area),
        },
    }


class ParcelRequest(BaseModel):
    """
    Request schema for parcel suitability prediction endpoint.

    This endpoint accepts an array of GeoJSON Feature objects representing parcels
    and returns suitability scores (residential, commercial, industrial, green)
    along with environmental risk assessments.

    Examples:
        >>> request = ParcelRequest(parcels=[
        ...     {
        ...         "id": "12345",
        ...         "type": "Feature",
        ...         "geometry": {"type": "Polygon", "coordinates": [...]},
        ...         "properties": {"centroid": {"x": -117.0, "y": 32.8}}
        ...     }
        ... ])
    """

    parcels: List[GeoJSONFeature] = Field(
        ...,
        description="Array of GeoJSON Feature objects. Each feature should have an 'id' "
        "and 'properties' dict. The 'properties' may contain optional planning parameters "
        "like 'soil_sand_pct', 'soil_clay_pct', 'aqi_mean', and 'impervious_mean'."
    )


class ZoningRagRequest(BaseModel):
    """
    Request schema for Zoning RAG (Retrieval-Augmented Generation) chat endpoint.

    This endpoint enables conversational queries about zoning regulations with context
    from selected parcels. The RAG system retrieves relevant zoning documents and
    generates answers using GPT models.

    Usage:
        - First message: Include 'apn' and 'context' to set parcel context
        - Subsequent messages: Only include 'question' and 'session_id' (context persists)
        - Changing parcel: Send new 'apn' and 'context' to update context
    """

    question: str = Field(..., description="User's zoning-related question")
    apn: Optional[str] = Field(
        None,
        description="Assessor Parcel Number (APN) of selected parcel. "
        "Include on first message or when changing selection."
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="Parcel properties (zoning code, jurisdiction, etc.) as context. "
        "Include on first message or when changing selection."
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID for maintaining conversation context. "
        "Omit on first message (backend generates one)."
    )


class SpatialGenerateRequest(BaseModel):
    """
    Request schema for spatial data generation endpoint.

    Generates new spatial geometries based on input parcels using various algorithms:
    - Subdivision: Divides parcels into smaller units
    - Buffer zones: Creates buffer polygons around parcels
    - Voronoi: Generates Voronoi diagrams from parcel centroids
    - Grid: Creates grid overlay cells
    """

    parcels: List[GeoJSONFeature] = Field(
        ...,
        description="Array of GeoJSON Feature objects representing input parcels."
    )
    generation_type: Literal["parcel_subdivision", "buffer_zones", "voronoi", "grid"] = Field(
        "parcel_subdivision",
        description="Type of spatial generation. Options: 'parcel_subdivision', "
        "'buffer_zones', 'voronoi', 'grid'"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        None,
        description="Generation-specific parameters. Examples: "
        "- subdivision: {'target_area': 1000.0, 'min_area': 100.0} "
        "- buffer: {'distance': 50.0, 'units': 'meters'} "
        "- grid: {'cell_size': 100.0, 'cell_units': 'meters'}"
    )

    @model_validator(mode="after")
    def validate_generation_parameters(self) -> "SpatialGenerateRequest":
        params = self.parameters or {}

        def _coerce_positive_number(field_name: str, default_value: float) -> float:
            raw_value = params.get(field_name, default_value)
            try:
                numeric = float(raw_value)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid {field_name}: expected numeric value")
            if numeric <= 0.0:
                raise ValueError(f"Invalid {field_name}: must be greater than zero")
            return numeric

        if self.generation_type == "grid":
            _coerce_positive_number("cell_size", 100.0)
        elif self.generation_type == "parcel_subdivision":
            target_area = _coerce_positive_number("target_area", 1000.0)
            min_area = _coerce_positive_number("min_area", 100.0)
            if min_area > target_area:
                raise ValueError("Invalid min_area: cannot exceed target_area")
        elif self.generation_type == "buffer_zones":
            _coerce_positive_number("distance", 50.0)

        return self


class SpatialOptimizeRequest(BaseModel):
    """
    Request schema for NSGA-II spatial land-use optimization.

    This endpoint accepts parcel GeoJSON features and optimization settings:
    - target_mix: desired land-use percentages (residential/commercial/industrial/green)
    - num_output_plans: number of Pareto plans (k) to return
    - population_size / generations: NSGA-II search controls
    """

    parcels: List[GeoJSONFeature] = Field(
        ...,
        description="GeoJSON Feature array used as optimization candidates.",
        min_length=1,
    )
    target_mix: Dict[str, float] = Field(
        default_factory=dict,
        description="Desired land-use ratio weights keyed by use label.",
    )
    num_output_plans: int = Field(
        5,
        ge=1,
        le=20,
        description="Number of output plans (k) to return from the Pareto front.",
    )
    population_size: int = Field(
        30,
        ge=10,
        le=500,
        description="NSGA-II population size.",
    )
    generations: int = Field(
        20,
        ge=1,
        le=500,
        description="NSGA-II number of generations.",
    )
    include_adjacency: bool = Field(
        True,
        description="Whether to infer parcel adjacency and include fragmentation objective.",
    )
    adjacency_predicate: str = Field(
        "touches",
        pattern="^(touches|intersects)$",
        description="Adjacency rule: 'touches' or 'intersects'.",
    )
    debug: bool = Field(
        True,
        description="Enable detailed progress logging for diagnostics.",
    )
    progress_every_generations: int = Field(
        10,
        ge=1,
        le=100,
        description="How frequently to emit NSGA-II generation progress updates.",
    )
    interactive_mode: bool = Field(
        True,
        description="Apply interactive runtime caps for UI responsiveness.",
    )
    use_spatial_compatibility: bool = Field(
        False,
        description="Enable centroid-neighbour spatial compatibility scoring.",
    )
    spatial_neighbor_radius_m: float = Field(
        250,
        gt=0,
        le=5000,
        description="Neighbour search radius in meters for spatial compatibility.",
    )
    spatial_compatibility_weight: float = Field(
        0.15,
        ge=0,
        le=1,
        description="Small weighting factor for spatial compatibility penalty objective.",
    )


class NearbyParcelsRequest(BaseModel):
    parcel_id: str = Field(..., min_length=1)
    radius_m: float = Field(..., gt=0, le=5000)
    limit: int = Field(default=150, ge=1, le=1000)


class NearbyParcelResult(BaseModel):
    parcel_id: str
    distance_m: float


class NearbyPlanningSummary(BaseModel):
    average_risk: float
    high_risk_count: int
    dominant_zoning: str
    zoning_counts: Dict[str, int]
    land_use_counts: Dict[str, int]
    hazard_counts: Dict[str, int]
    insight: str


class NearbyParcelsResponse(BaseModel):
    center_parcel_id: str
    radius_m: float
    count: int
    parcel_ids: List[str]
    results: List[NearbyParcelResult]
    summary: NearbyPlanningSummary | None = None
    source: Literal["redis_geo", "memory_fallback"]


class ExplainAssignmentRequest(BaseModel):
    parcel_id: str | None = None
    parcel_properties: Dict[str, Any]
    assigned_use: Literal["residential", "commercial", "industrial", "green"]
    target_mix: Dict[str, float] = Field(default_factory=dict)
    use_spatial_compatibility: bool = Field(
        False,
        description="When true, include neighbour-aware context in the assignment explanation.",
    )
    spatial_neighbor_radius_m: float = Field(
        250,
        gt=0,
        le=5000,
        description="Neighbour radius used to explain local spatial compatibility.",
    )
    plan_assignments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Assignments for the selected generated plan.",
    )
    plan_parcels: List[GeoJSONFeature] = Field(
        default_factory=list,
        description="GeoJSON features for parcels in the selected generated plan.",
    )


@app.get("/health", tags=["system"])
@app.get("/api/health", tags=["system"])
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/api/predict_suitability", tags=["suitability"])
@limiter.limit("60/minute")
def predict_suitability(request: Request, body: ParcelRequest) -> dict:
    """
    Predict land-use suitability scores for parcels based on environmental risk.
    
    This is the primary endpoint for parcel suitability analysis. It:
    
    1. Accepts parcels (GeoJSON Feature array from frontend)
    2. Extracts or generates features (uses planning parameters if provided)
    3. Calls SuitabilityAgent.predict() to get suitability scores
    4. Returns scores merged back into GeoJSON format for map visualization
    
    The suitability scores are derived from environmental risk assessments:
    - Environmental risk: 0-1 (normalized from 0-100 XGBoost predictions)
    - Residential/Commercial/Industrial/Green: 0-1 suitability scores
      computed using heuristic rules that convert risk to suitability
    
    Returns:
        GeoJSON FeatureCollection with suitability scores in each feature's properties.
        Scores include: residential, commercial, industrial, green, environmental_risk

    Request:
      POST /predict_suitability
      {
        "parcels": [  # from ParcelGeoJSONExport.features
          {
            "id": "p1",
            "type": "Feature",
            "geometry": {
              "type": "Polygon",
              "coordinates": [[[x1, y1], [x2, y2], ...]]
            },
            "properties": {
              "centroid": {"x": 73.05, "y": 31.42}
            }
          },
          ...
        ]
      }

    Response (GeoJSON FeatureCollection):
      {
        "type": "FeatureCollection",
        "features": [
          {
            "type": "Feature",
            "id": "p1",
            "geometry": {...},  # original geometry preserved
            "properties": {
              "centroid": {...},  # original properties preserved
              "residential": 0.42,  # normalized suitability scores (0-1, sum to 1.0)
              "commercial": 0.21,
              "industrial": 0.15,
              "green": 0.22
            }
          },
          ...
        ]
      }
    """
    try:
        # Step 1: Accept parcels (already in body.parcels)
        if not body.parcels:
            raise HTTPException(status_code=400, detail="No parcels provided")

        logging.info("Received %d parcels for prediction", len(body.parcels))
        parcel_dicts = _parcels_as_dicts(body.parcels)

        features_df = attach_features(parcel_dicts)
        
        if features_df.empty:
            raise HTTPException(
                status_code=400, detail="Failed to extract features from parcels"
            )

        # Ensure we have all required schema features
        # Only include columns that exist in both the DataFrame and schema
        schema_keys = [k for k in FEATURE_SCHEMA.keys() if k in features_df.columns]
        if not schema_keys:
            raise HTTPException(
                status_code=400,
                detail=f"No matching features found. Expected: {list(FEATURE_SCHEMA.keys())}",
            )

        # Prepare DataFrame with parcel_id and features
        ordered_df = features_df[["parcel_id"] + schema_keys]

        results_df = get_suitability_agent().predict(ordered_df)

        # Step 4: Return scores (convert DataFrame to list of dicts for GeoJSON builder)
        predictions = results_df.to_dict(orient="records")

        # Build GeoJSON output with scores merged into properties (B4)
        output_geojson = build_output_geojson(parcel_dicts, predictions)

        return output_geojson

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ValueError as e:
        logging.error("Validation error: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Validation error: {e}")
    except Exception as e:
        logging.error("Internal server error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while processing suitability prediction.")


def get_spatial_agent() -> SpatialAgent:
    """Get or create the SpatialAgent instance."""
    global _spatial_agent
    if _spatial_agent is None:
        _spatial_agent = SpatialAgent()
    return _spatial_agent


def _has_rag_api_key() -> bool:
    return True  # embeddings run locally via sentence-transformers; no API key needed


def _load_rag_env_files(backend_dir: Path) -> None:
    """Load .env files relevant to RAG startup without overriding existing env."""
    if load_dotenv is None:
        logging.info("python-dotenv is unavailable; skipping .env preload for RAG startup.")
        return

    candidate_env_files = [
        backend_dir / ".env",
        backend_dir / "agent" / "zoning_agent" / ".env",
        backend_dir / "agent" / "zoning_agent" / "src" / ".env",
        Path.cwd() / ".env",
    ]

    loaded_any = False
    for env_path in candidate_env_files:
        if not env_path.exists():
            continue
        load_dotenv(dotenv_path=env_path, override=False)
        loaded_any = True
        logging.info("Loaded environment file for RAG startup: %s", env_path)

    if not loaded_any:
        logging.info("No .env file found for RAG startup preload; relying on process environment.")


def _enrich_parcel_ctx_from_lookup(parcel_ctx: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Supplement parcel context with values from the local zoning lookup table.

    Only fills in MAX_HEIGHT, MAX_FAR, MIN_LOT_SIZE, ALLOWED_USES when those
    keys are absent from the context already, so GIS-sourced values always win.
    """
    if not parcel_ctx:
        return parcel_ctx
    zoning_code = parcel_ctx.get("ZONING_CODE", "")
    params = get_zoning_params(zoning_code)
    if not params:
        return parcel_ctx
    enriched = dict(parcel_ctx)
    for key, lookup_key in (
        ("MAX_HEIGHT",    "MAX_HEIGHT"),
        ("MAX_FAR",       "MAX_FAR"),
        ("MIN_LOT_SIZE",  "MIN_LOT_SIZE"),
        ("ALLOWED_USES",  "ALLOWED_USES"),
    ):
        if enriched.get(key) is None and params.get(lookup_key) is not None:
            enriched[key] = params[lookup_key]
    return enriched


def _build_rag_placeholder_answer(question: str, apn: Optional[str]) -> str:
    parcel_text = f" for parcel {apn}" if apn else ""
    return (
        "RAG is currently running in placeholder mode"
        f"{parcel_text} because Gemini API credentials are not configured. "
        "Set GEMINI_API_KEY and restart the backend to enable "
        "document-grounded zoning answers. "
        f"Question received: {question}"
    )


def _init_rag() -> None:
    global _rag, _rag_unavailable_reason
    # Where to persist Chroma
    backend_dir = Path(__file__).resolve().parent
    _load_rag_env_files(backend_dir)
    persist = resolve_rag_persist_dir(backend_dir)

    if not _has_rag_api_key():
        _rag = None
        _rag_unavailable_reason = "GEMINI_API_KEY not set"
        logging.info(
            "RAG startup in placeholder mode: %s.",
            _rag_unavailable_reason,
        )
        return

    try:
        _rag = RagService(persist_dir=persist)
        _rag_unavailable_reason = None
    except Exception as exc:
        _rag = None
        _rag_unavailable_reason = "RAG service unavailable"
        logging.warning("RAG disabled at startup: %s", exc)
        return

    ingest_on_startup = settings.rag_ingest_on_startup
    if not ingest_on_startup:
        logging.info("RAG startup ingestion disabled (set RAG_INGEST_ON_STARTUP=true to enable).")
        return

    # Ingest PDFs from src/data if collection is empty
    data_dir = backend_dir / "agent" / "zoning_agent" / "src" / "data"
    try:
        # Only ingest if empty to avoid duplicate work
        if _rag.collection.count() == 0:
            _rag.ingest_dir(data_dir)
    except Exception as exc:
        logging.warning("RAG ingestion skipped: %s", exc)


@app.post("/api/rag/zoning/ask", tags=["rag", "zoning"])
@limiter.limit("20/minute")
def zoning_rag_ask(request: Request, req: ZoningRagRequest) -> Dict[str, Any]:
    """
    Zoning RAG endpoint with persistent Chroma and session-scoped parcel context.

    Behavior:
    - First message after selecting a parcel: send `apn` and `context` once.
    - Subsequent messages: omit `apn/context`; backend remembers via `session_id`.
    - If `apn` is provided later and changes, we update the session parcel context.
    """
    try:
        # Manage chat session
        sid = _chat_sessions.ensure(req.session_id)
        if req.apn and req.context is not None:
            _chat_sessions.set_parcel(sid, req.apn, req.context)
        apn, parcel_ctx = _chat_sessions.get_parcel(sid)

        # Enrich parcel context with local zoning lookup (fills gaps; GIS values win)
        parcel_ctx = _enrich_parcel_ctx_from_lookup(parcel_ctx)

        if _rag is None:
            reason = _rag_unavailable_reason or "RAG service unavailable"
            return {
                "answer": _build_rag_placeholder_answer(req.question, apn),
                "session_id": sid,
                "apn": apn,
                "citations": [],
                "placeholder": True,
                "reason": reason,
            }

        # Retrieve relevant chunks
        constructed         = _rag.construct_query(req.question, parcel_ctx)
        jurisdiction_filter = _rag.get_jurisdiction_filter(parcel_ctx)
        zone_filter         = _rag.get_zone_filter(parcel_ctx)
        retrieved = _rag.retrieve(
            constructed,
            top_k=6,
            mmr=True,
            jurisdiction_filter=jurisdiction_filter,
            zone_filter=zone_filter,
        )

        # Fetch conversation history and generate answer
        history = _chat_sessions.get_history(sid)
        answer  = _rag.answer(req.question, parcel_ctx, retrieved, history=history)

        # Store this turn so follow-up questions have context
        _chat_sessions.add_turn(sid, req.question, answer)

        citations = [
            {
                "source":     r.metadata.get("source"),
                "start_page": r.metadata.get("start_page"),
                "end_page":   r.metadata.get("end_page"),
            }
            for r in retrieved[:6]
        ]

        return {"answer": answer, "session_id": sid, "apn": apn, "citations": citations}
    except HTTPException:
        raise
    except Exception as e:
        logging.error("RAG endpoint failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while processing RAG request.")


@app.post("/api/spatial/generate", tags=["spatial"])
def spatial_generate(request: SpatialGenerateRequest) -> Dict[str, Any]:
    """
    Generate spatial data based on input parcels.
    
    Request:
      POST /spatial/generate
      {
        "parcels": [...],  # GeoJSON Feature array
        "generation_type": "parcel_subdivision",  # or "buffer_zones", "voronoi", "grid"
        "parameters": {
          "target_area": 1000.0,  # for subdivision (m²)
          "distance": 50.0,  # for buffer (meters)
          "cell_size": 100.0  # for grid (meters)
        }
      }
    
    Response:
      {
        "type": "FeatureCollection",
        "features": [...]
      }
    """
    try:
        if not request.parcels:
            raise HTTPException(status_code=400, detail="No parcels provided")
        
        spatial_agent = get_spatial_agent()
        result = spatial_agent.generate(
            parcels=_parcels_as_dicts(request.parcels),
            generation_type=request.generation_type,
            parameters=request.parameters or {}
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"Error in spatial generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while generating spatial output.")


@app.post("/spatial/nearby-parcels", tags=["spatial"])
@app.post("/api/spatial/nearby-parcels", tags=["spatial"], include_in_schema=False)
def spatial_nearby_parcels(body: NearbyParcelsRequest) -> Dict[str, Any]:
    try:
        service = _get_nearby_parcels_service()
        response = service.nearby_parcels(
            parcel_id=body.parcel_id,
            radius_m=body.radius_m,
            limit=body.limit,
        )
        return NearbyParcelsResponse(
            center_parcel_id=response["center_parcel_id"],
            radius_m=response["radius_m"],
            count=response["count"],
            parcel_ids=response["parcel_ids"],
            results=[NearbyParcelResult(**item) for item in response["results"]],
            summary=NearbyPlanningSummary(**response["summary"]) if response.get("summary") else None,
            source=response["source"],
        ).model_dump()
    except NearbyParcelNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except NearbyParcelDataError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except NearbyParcelLookupError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Parcel '{exc.args[0]}' was not found.")
    except HTTPException:
        raise
    except Exception as exc:
        logging.error("Error resolving nearby parcels: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while resolving nearby parcels.")


@app.post("/spatial/optimize", tags=["spatial"])
@app.post("/api/spatial/optimize", tags=["spatial"], include_in_schema=False)
@limiter.limit("10/minute")
def spatial_optimize(request: Request, body: SpatialOptimizeRequest) -> Dict[str, Any]:
    """
    Run Spatial Agent NSGA-II optimization and return top-k generated plans.

    Request:
      POST /spatial/optimize
      {
        "parcels": [...],                     # GeoJSON Feature array
        "target_mix": {                       # optional desired percentages/weights
          "residential": 0.35,
          "commercial": 0.25,
          "industrial": 0.20,
          "green": 0.20
        },
        "num_output_plans": 5,               # k
        "population_size": 80,
        "generations": 100,
        "include_adjacency": true,
        "adjacency_predicate": "touches"
      }
    """
    try:
        started_at = time.perf_counter()
        request_id = uuid.uuid4().hex[:8]
        if not body.parcels:
            raise HTTPException(status_code=400, detail="No parcels provided")
        features_as_dicts = _parcels_as_dicts(body.parcels)
        parcel_feature_list = features_as_dicts

        parcel_count = len(body.parcels)
        warnings: List[str] = []
        debug_timeline: List[Dict[str, Any]] = []

        def progress_logger(event: Dict[str, Any]) -> None:
            stage = str(event.get("stage", "unknown"))
            elapsed_seconds = float(event.get("elapsed_seconds", 0.0) or 0.0)
            entry = {
                "stage": stage,
                "elapsed_seconds": elapsed_seconds,
                "generation": event.get("generation"),
                "total_generations": event.get("total_generations"),
                "progress_ratio": event.get("progress_ratio"),
                "parcel_count": event.get("parcel_count"),
                "feature_count": event.get("feature_count"),
                "comparisons": event.get("comparisons"),
                "edge_count": event.get("edge_count"),
            }
            debug_timeline.append(entry)

            if body.debug:
                details: List[str] = [f"stage={stage}", f"elapsed={elapsed_seconds:.2f}s"]
                for key in (
                    "generation",
                    "total_generations",
                    "progress_ratio",
                    "feature_count",
                    "parcel_count",
                    "comparisons",
                    "edge_count",
                ):
                    value = event.get(key)
                    if value is not None:
                        if key == "progress_ratio":
                            try:
                                details.append(f"{key}={float(value):.2%}")
                            except (TypeError, ValueError):
                                details.append(f"{key}={value}")
                        else:
                            details.append(f"{key}={value}")
                logging.info("[spatial:%s] %s", request_id, " ".join(details))

        progress_logger(
            {
                "stage": "request_received",
                "elapsed_seconds": 0.0,
                "parcel_count": parcel_count,
            }
        )

        effective_population_size = body.population_size
        effective_generations = body.generations
        effective_include_adjacency = body.include_adjacency

        if body.interactive_mode:
            if parcel_count <= 20:
                ui_cap_population = 24
                ui_cap_generations = 12
            elif parcel_count <= 100:
                ui_cap_population = 30
                ui_cap_generations = 20
            elif parcel_count <= 400:
                ui_cap_population = 40
                ui_cap_generations = 25
            elif parcel_count <= 800:
                ui_cap_population = 35
                ui_cap_generations = 18
            else:
                ui_cap_population = 30
                ui_cap_generations = 12

            capped_population = min(effective_population_size, ui_cap_population)
            capped_generations = min(effective_generations, ui_cap_generations)
            if (
                capped_population != effective_population_size
                or capped_generations != effective_generations
            ):
                warnings.append(
                    "Interactive mode capped population/generations for faster response."
                )
            effective_population_size = capped_population
            effective_generations = capped_generations

        # Adjacency inference is O(n^2) with expensive geometry predicates.
        if effective_include_adjacency and parcel_count > 800:
            effective_include_adjacency = False
            warnings.append(
                "Adjacency disabled automatically for large parcel count to avoid long runtime."
            )

        # Keep interactive workloads bounded for UI requests.
        max_work_units = 3_000_000  # parcel_count * population_size * generations
        work_units = parcel_count * effective_population_size * effective_generations
        if work_units > max_work_units:
            scale = max_work_units / float(work_units)
            scaled_generations = max(5, int(effective_generations * scale))
            effective_generations = min(effective_generations, scaled_generations)

            work_units = parcel_count * effective_population_size * effective_generations
            if work_units > max_work_units:
                scaled_population = max(10, int(max_work_units / (parcel_count * max(1, effective_generations))))
                effective_population_size = min(effective_population_size, scaled_population)

            warnings.append(
                "Optimization settings were reduced automatically to keep response time interactive."
            )
        progress_logger(
            {
                "stage": "effective_settings",
                "elapsed_seconds": time.perf_counter() - started_at,
                "parcel_count": parcel_count,
                "population_size": effective_population_size,
                "generations": effective_generations,
                "include_adjacency": effective_include_adjacency,
            }
        )

        objectives = list(default_objectives())
        normalized_target_mix = normalize_target_mix(body.target_mix)

        if normalized_target_mix:
            objectives.append(make_land_use_balance_penalty(normalized_target_mix))

        parcel_feature_lookup = build_parcel_feature_lookup(parcel_feature_list)
        spatial_neighbor_pairs = []
        if body.use_spatial_compatibility:
            spatial_neighbor_pairs = build_neighbor_pairs(
                list(parcel_feature_lookup.keys()),
                parcel_feature_lookup,
                body.spatial_neighbor_radius_m,
            )
            objectives.append(
                make_spatial_compatibility_objective(
                    spatial_neighbor_pairs,
                    parcel_feature_lookup,
                    body.spatial_compatibility_weight,
                )
            )
            progress_logger(
                {
                    "stage": "spatial_compatibility_neighbors_ready",
                    "elapsed_seconds": time.perf_counter() - started_at,
                    "parcel_count": parcel_count,
                    "edge_count": len(spatial_neighbor_pairs),
                }
            )
            if not spatial_neighbor_pairs:
                warnings.append(
                    "Spatial compatibility was enabled, but no nearby parcel pairs were found."
                )

        redis_store = _get_redis_store_cached()
        spatial_cache_ttl_seconds = get_spatial_optimize_cache_ttl_seconds()
        spatial_cache_key: Optional[str] = None
        if redis_store and spatial_cache_ttl_seconds > 0 and not body.debug:
            spatial_cache_key = build_spatial_optimize_cache_key(
                features=features_as_dicts,
                num_output_plans=body.num_output_plans,
                population_size=effective_population_size,
                generations=effective_generations,
                include_adjacency=effective_include_adjacency,
                adjacency_predicate=body.adjacency_predicate,
                target_mix=normalized_target_mix,
                use_spatial_compatibility=body.use_spatial_compatibility,
                spatial_neighbor_radius_m=(
                    body.spatial_neighbor_radius_m if body.use_spatial_compatibility else None
                ),
                spatial_compatibility_weight=(
                    body.spatial_compatibility_weight if body.use_spatial_compatibility else None
                ),
            )
            try:
                cached_response = redis_store.get_json(spatial_cache_key)
            except Exception as exc:
                logging.warning("Failed to read spatial optimize cache entry: %s", exc)
                cached_response = None
            if isinstance(cached_response, dict):
                cached_warnings = list(cached_response.get("warnings") or [])
                if "Returned cached optimization result." not in cached_warnings:
                    cached_warnings.append("Returned cached optimization result.")
                cached_response["warnings"] = cached_warnings
                logging.info(
                    "Spatial optimize cache hit: request_id=%s cache_key=%s parcels=%s",
                    request_id,
                    spatial_cache_key,
                    parcel_count,
                )
                return cached_response

        optimizer = SpatialOptimizer(
            config=SpatialConfig(
                nsga2=NSGA2Config(
                    population_size=effective_population_size,
                    generations=effective_generations,
                    num_output_plans=body.num_output_plans,
                )
            ),
            objective_functions=tuple(objectives),
        )

        parcel_props_map, parcel_area_map = _build_parcel_lookup(parcel_feature_list)

        result = optimizer.optimize_geojson_features(
            features=parcel_feature_list,
            include_adjacency=effective_include_adjacency,
            adjacency_predicate=body.adjacency_predicate,
            progress_callback=progress_logger,
            progress_every_generations=body.progress_every_generations,
        )

        plans_payload: List[Dict[str, Any]] = []
        for plan in result.plans:
            crowding_distance = float(plan.crowding_distance)
            if not math.isfinite(crowding_distance):
                crowding_distance = 1e9

            objective_values: List[float] = []
            for raw_value in plan.objectives:
                numeric_value = float(raw_value)
                if not math.isfinite(numeric_value):
                    numeric_value = 1e9
                objective_values.append(numeric_value)

            plan_assignments_dicts = [
                {"parcel_id": a.parcel_id, "use_label": a.use_label}
                for a in plan.assignments
            ]
            planning_metrics = _compute_planning_metrics(
                parcel_props_map, parcel_area_map, plan_assignments_dicts
            )

            plan_payload = {
                "rank": plan.rank,
                "crowding_distance": crowding_distance,
                "objectives": objective_values,
                "planning_metrics": planning_metrics,
                "assignments": [
                    {
                        "parcel_id": assignment.parcel_id,
                        "use_code": assignment.use_code,
                        "use_label": assignment.use_label,
                    }
                    for assignment in plan.assignments
                ],
            }
            if body.use_spatial_compatibility:
                spatial_result = score_spatial_compatibility(
                    plan_assignments_dicts,
                    spatial_neighbor_pairs,
                    parcel_feature_lookup,
                )
                plan_payload.update(
                    {
                        "spatial_compatibility_score": spatial_result["score"],
                        "spatial_compatibility_summary": spatial_result["summary"],
                        "spatial_compatibility_warnings": explain_spatial_compatibility(
                            plan_assignments_dicts,
                            spatial_neighbor_pairs,
                            parcel_feature_lookup,
                        ),
                    }
                )
            plans_payload.append(plan_payload)

        total_hazard_parcels = sum(
            1 for props in parcel_props_map.values()
            if any(int(props.get(f, 0) or 0) for f in _HAZARD_FLAGS)
        )
        current_state: Dict[str, Any] = {
            "housing_units": 0,
            "estimated_residents": 0,
            "green_space_per_resident_m2": 0.0,
            "who_green_target_m2": _WHO_GREEN_M2_PER_PERSON,
            "hazard_built_parcels": 0,
            "total_hazard_parcels": total_hazard_parcels,
            "total_parcels": parcel_count,
            "estimated_annual_tax_usd": 0,
            "area_m2": {
                "residential": 0,
                "commercial": 0,
                "industrial": 0,
                "green": 0,
                "total": round(sum(parcel_area_map.values())),
            },
        }

        elapsed_seconds = time.perf_counter() - started_at
        progress_logger(
            {
                "stage": "request_completed",
                "elapsed_seconds": elapsed_seconds,
                "parcel_count": parcel_count,
                "plan_count": len(result.plans),
            }
        )
        logging.info(
            "Spatial optimize completed: request_id=%s parcels=%s pop=%s gen=%s adjacency=%s elapsed=%.2fs",
            request_id,
            parcel_count,
            effective_population_size,
            effective_generations,
            effective_include_adjacency,
            elapsed_seconds,
        )
        response_payload = {
            "parcel_count": parcel_count,
            "objective_names": list(result.objective_names),
            "plans": plans_payload,
            "current_state": current_state,
            "settings": {
                "num_output_plans": body.num_output_plans,
                "population_size": effective_population_size,
                "generations": effective_generations,
                "include_adjacency": effective_include_adjacency,
                "adjacency_predicate": body.adjacency_predicate,
                "target_mix": normalized_target_mix,
                "use_spatial_compatibility": body.use_spatial_compatibility,
                "spatial_neighbor_radius_m": body.spatial_neighbor_radius_m,
                "spatial_compatibility_weight": body.spatial_compatibility_weight,
                "spatial_neighbor_pairs": len(spatial_neighbor_pairs),
                "elapsed_seconds": elapsed_seconds,
                "request_id": request_id,
            },
            "warnings": warnings,
            "debug_timeline": debug_timeline if body.debug else [],
        }

        if redis_store and spatial_cache_key and spatial_cache_ttl_seconds > 0 and not body.debug:
            try:
                redis_store.set_json(
                    spatial_cache_key,
                    response_payload,
                    ttl_seconds=spatial_cache_ttl_seconds,
                )
            except Exception as exc:
                logging.warning("Failed to persist spatial optimize cache entry: %s", exc)

        return response_payload
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in spatial optimization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while optimizing spatial plans.")


@app.post("/api/spatial/explain-assignment", tags=["spatial"])
def spatial_explain_assignment(body: ExplainAssignmentRequest) -> Dict[str, Any]:
    try:
        resolved_parcel_id = body.parcel_id
        if resolved_parcel_id is None:
            props = body.parcel_properties or {}
            for key in (
                "parcel_id",
                "parcelId",
                "APN",
                "apn",
                "PARCELID",
                "PARNO",
                "join_key",
                "id",
            ):
                value = props.get(key)
                if value is None:
                    continue
                candidate = str(value).strip()
                if candidate:
                    resolved_parcel_id = candidate
                    break

        spatial_context = None
        if (
            body.use_spatial_compatibility
            and resolved_parcel_id
            and body.plan_assignments
            and body.plan_parcels
        ):
            plan_parcel_dicts = _parcels_as_dicts(body.plan_parcels)
            parcel_feature_lookup = build_parcel_feature_lookup(plan_parcel_dicts)
            plan_parcel_ids = [
                str(item.get("parcel_id") or item.get("parcelId") or item.get("APN") or "").strip()
                for item in body.plan_assignments
            ]
            plan_parcel_ids = [parcel_id for parcel_id in plan_parcel_ids if parcel_id]

            neighbor_pairs = build_neighbor_pairs(
                plan_parcel_ids or list(parcel_feature_lookup.keys()),
                parcel_feature_lookup,
                body.spatial_neighbor_radius_m,
            )
 
            clicked_pairs = [
            pair for pair in neighbor_pairs
            if str(pair[0]) == str(resolved_parcel_id) or str(pair[1]) == str(resolved_parcel_id)
            ]

            logging.info(
            "[assignment-spatial-debug] parcel=%s use_spatial=%s assignments=%s parcels=%s lookup=%s total_pairs=%s clicked_pairs=%s radius=%s",
             resolved_parcel_id,
             body.use_spatial_compatibility,
             len(body.plan_assignments or []),
             len(body.plan_parcels or []),
             len(parcel_feature_lookup),
             len(neighbor_pairs),
             len(clicked_pairs),
             body.spatial_neighbor_radius_m,
            ) 

            spatial_context = explain_assignment_spatial_context(
                parcel_id=resolved_parcel_id,
                assignments=body.plan_assignments,
                neighbor_pairs=neighbor_pairs,
                parcel_feature_lookup=parcel_feature_lookup,
                radius_m=body.spatial_neighbor_radius_m,
            )

        explanation = explain_assignment(
            parcel_properties=body.parcel_properties,
            assigned_use=body.assigned_use,
            target_mix=body.target_mix,
            spatial_context=spatial_context,
        )
        return {
    "parcel_id": resolved_parcel_id,
    **explanation,
    "spatial_context": explanation.get("spatial_context", spatial_context),
    "_debug_spatial_explain": {
        "use_spatial_compatibility": body.use_spatial_compatibility,
        "plan_assignments_count": len(body.plan_assignments or []),
        "plan_parcels_count": len(body.plan_parcels or []),
        "feature_lookup_count": len(parcel_feature_lookup) if body.plan_parcels else 0,
        "total_neighbor_pairs": len(neighbor_pairs) if body.plan_parcels else 0,
        "clicked_neighbor_pairs": len(clicked_pairs) if body.plan_parcels else 0,
        "resolved_parcel_id": resolved_parcel_id,
        "radius_m": body.spatial_neighbor_radius_m,
    },
}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logging.error("Error explaining parcel assignment: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while explaining parcel assignment.",
        )


# ── Copilot endpoints ────────────────────────────────────────────────────────

from services.copilot_orchestrator import CopilotOrchestrator
from services.risk_explainer import RiskExplainer

_copilot_orchestrator: Optional[CopilotOrchestrator] = None

def _get_copilot() -> CopilotOrchestrator:
    global _copilot_orchestrator
    if _copilot_orchestrator is None:
        _copilot_orchestrator = CopilotOrchestrator()
    return _copilot_orchestrator


class CopilotQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    parcel_ids: List[str] = Field(default_factory=list)
    parcel_features: List[Dict[str, Any]] = Field(default_factory=list)
    history: List[Dict[str, Any]] = Field(default_factory=list)


class CounterfactualRequest(BaseModel):
    parcel_id: str
    parcel_properties: Dict[str, Any]
    changes: Dict[str, Any]


@app.post("/api/copilot/query")
async def copilot_query(request: Request, body: CopilotQueryRequest) -> StreamingResponse:
    """
    Stream Planner's Copilot response as Server-Sent Events.

    Each event: data: {"type": "...", ...}\\n\\n
    Event types: agent_start, agent_complete, text_chunk, final, error
    """
    orchestrator = _get_copilot()

    async def event_generator():
        async for chunk in orchestrator.stream(
            query=body.query,
            parcel_ids=body.parcel_ids,
            parcel_features=body.parcel_features,
            history=body.history,
        ):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/risk/counterfactual")
async def risk_counterfactual(request: Request, body: CounterfactualRequest):
    """
    Compute what-if risk score by toggling hazard flags.

    Returns original and counterfactual scores plus delta.
    """
    explainer = RiskExplainer()
    result = explainer.counterfactual(body.parcel_properties, body.changes)
    return {**result, "parcel_id": body.parcel_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
