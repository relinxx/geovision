"""Orchestrator Steps - Wrapper functions for agent execution."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from agent.spatial_agent.spatial.config import NSGA2Config, SpatialConfig
from agent.spatial_agent.spatial.optimizer import SpatialOptimizer
from agent.spatial_agent.spatial.types import ParcelRecord
from agent.zoning_agent.rag_service import RagService
from services.shared import get_suitability_agent, resolve_rag_persist_dir

logger = logging.getLogger(__name__)


def run_environment_stage(parcel_ids: List[str]) -> Dict[str, Any]:
    """Run environment suitability prediction stage."""
    logger.info("[ENVIRONMENT] Starting environment stage for %d parcels", len(parcel_ids))
    try:
        agent = get_suitability_agent()
        parcels_df = pd.DataFrame({"parcel_id": parcel_ids})
        results_df = agent.predict(parcels_df)
        results = results_df.to_dict(orient="records")
        logger.info("[ENVIRONMENT] Completed with %d results", len(results))
        return {"stage": "environment", "parcel_count": len(parcel_ids), "results": results}
    except Exception as e:
        logger.error("[ENVIRONMENT] Error: %s", e, exc_info=True)
        raise


def run_zoning_stage(parcel_ids: List[str]) -> Dict[str, Any]:
    """Run zoning regulation retrieval stage via RAG."""
    logger.info("[ZONING] Starting zoning stage for %d parcels", len(parcel_ids))
    try:
        backend_dir = Path(__file__).resolve().parent.parent
        persist_dir = resolve_rag_persist_dir(backend_dir)
        try:
            rag_service = RagService(persist_dir=persist_dir)
        except Exception as exc:
            placeholder_note = (
                "RAG placeholder mode: Gemini credentials are missing or RAG is unavailable. "
                "Configure GEMINI_API_KEY and restart backend."
            )
            logger.warning("[ZONING] RAG unavailable (%s). Returning placeholder results.", exc)
            return {
                "stage": "zoning",
                "parcel_count": len(parcel_ids),
                "note": placeholder_note,
                "results": [
                    {
                        "parcel_id": pid,
                        "regulations_found": 0,
                        "regulations": [],
                        "placeholder": True,
                        "reason": str(exc),
                    }
                    for pid in parcel_ids
                ],
            }

        # Single batched query covers all parcels — avoids N × (embed + Chroma) round-trips.
        # top_k is shared across all parcels; each gets the same general zoning context.
        batch_query = "What are the zoning regulations, setbacks, FAR limits, and allowed uses?"
        try:
            shared_chunks = rag_service.retrieve(batch_query, top_k=5, mmr=True)
        except Exception as exc:
            logger.warning("[ZONING] Batch retrieve failed: %s", exc)
            shared_chunks = []

        shared_regulations = [
            {
                "source": chunk.metadata.get("source", ""),
                "jurisdiction": chunk.metadata.get("jurisdiction", ""),
                "section": chunk.metadata.get("section", ""),
                "text_preview": chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text,
            }
            for chunk in shared_chunks
        ]

        zoning_results = [
            {
                "parcel_id": parcel_id,
                "regulations_found": len(shared_regulations),
                "regulations": shared_regulations,
            }
            for parcel_id in parcel_ids
        ]

        logger.info("[ZONING] Completed with %d results", len(zoning_results))
        return {"stage": "zoning", "parcel_count": len(parcel_ids), "results": zoning_results}

    except Exception as e:
        logger.error("[ZONING] Error: %s", e, exc_info=True)
        raise


def merge_outputs(env_data: Dict[str, Any], zoning_data: Dict[str, Any]) -> Dict[str, Any]:
    """Merge environment and zoning outputs into unified parcel context."""
    logger.info("[MERGE] Starting merge stage")
    try:
        env_lookup = {r["parcel_id"]: r for r in env_data.get("results", [])}
        zoning_lookup = {r["parcel_id"]: r for r in zoning_data.get("results", [])}
        all_parcel_ids = set(env_lookup) | set(zoning_lookup)

        merged_results = []
        for parcel_id in all_parcel_ids:
            env_result = env_lookup.get(parcel_id, {})
            zoning_result = zoning_lookup.get(parcel_id, {})
            merged_results.append({
                "parcel_id": parcel_id,
                "suitability": {
                    "residential":       env_result.get("residential", 0.0),
                    "commercial":        env_result.get("commercial", 0.0),
                    "industrial":        env_result.get("industrial", 0.0),
                    "green":             env_result.get("green", 0.0),
                    "environmental_risk": env_result.get("environmental_risk", 0.0),
                },
                "zoning": {
                    "regulations_found": zoning_result.get("regulations_found", 0),
                    "regulations":       zoning_result.get("regulations", []),
                },
            })

        logger.info("[MERGE] Completed with %d unified parcels", len(merged_results))
        return {"stage": "merge", "parcel_count": len(merged_results), "unified_results": merged_results}

    except Exception as e:
        logger.error("[MERGE] Error: %s", e, exc_info=True)
        raise


def run_spatial_stage(unified_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run spatial optimization stage using the NSGA-II Spatial Agent."""
    logger.info("[SPATIAL] Starting spatial optimization stage")
    try:
        unified_results = unified_data.get("unified_results", [])
        if not unified_results:
            return {
                "stage": "spatial",
                "parcel_count": 0,
                "plans": [],
                "objective_names": [],
                "note": "No merged parcel data available for spatial optimization.",
            }

        parcels: list[ParcelRecord] = []
        for index, item in enumerate(unified_results):
            parcel_id = str(item.get("parcel_id") or f"parcel-{index}")
            suitability = item.get("suitability", {}) or {}
            try:
                risk = float(suitability.get("environmental_risk", 0.0) or 0.0)
            except (TypeError, ValueError):
                risk = 0.0
            parcels.append(ParcelRecord(
                parcel_id=parcel_id,
                area_m2=1.0,
                centroid_x=0.0,
                centroid_y=0.0,
                risk_score_norm=risk,
                suitability={
                    "residential": float(suitability.get("residential", 0.0) or 0.0),
                    "commercial":  float(suitability.get("commercial",  0.0) or 0.0),
                    "industrial":  float(suitability.get("industrial",  0.0) or 0.0),
                    "green":       float(suitability.get("green",       0.0) or 0.0),
                },
                allowed_use_codes=(),
            ))

        optimizer = SpatialOptimizer(
            config=SpatialConfig(
                nsga2=NSGA2Config(population_size=40, generations=30, num_output_plans=5, random_seed=42)
            )
        )
        result = optimizer.optimize(parcels=parcels)

        plan_dicts = [
            {
                "rank": plan.rank,
                "crowding_distance": plan.crowding_distance,
                "objectives": list(plan.objectives),
                "assignments": [
                    {"parcel_id": a.parcel_id, "use_code": a.use_code, "use_label": a.use_label}
                    for a in plan.assignments
                ],
            }
            for plan in result.plans
        ]

        logger.info("[SPATIAL] Completed for %d parcels with %d Pareto plans", len(parcels), len(plan_dicts))
        return {
            "stage": "spatial",
            "parcel_count": len(parcels),
            "objective_names": list(result.objective_names),
            "plans": plan_dicts,
        }

    except Exception as e:
        logger.error("[SPATIAL] Error: %s", e, exc_info=True)
        raise
