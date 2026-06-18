"""
Planner's Copilot Orchestrator

Accepts a natural-language planning query, decides which agents to invoke
(Environment, Zoning, Spatial), runs them, and streams structured SSE events
back to the caller.

Event protocol (each line: "data: <JSON>\\n\\n"):
    agent_start    — {"agent": str, "message": str}
    agent_complete — {"agent": str, "result": dict}
    text_chunk     — {"text": str}
    final          — {"summary": str, "land_use_plan": list | null}
    error          — {"message": str}

Gemini is used for both tool-routing and answer synthesis when
GEMINI_API_KEY is set; falls back to keyword routing + template answers.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── OpenAI optional import ──────────────────────────────────────────────────
try:
    from openai import OpenAI as _OpenAI  # type: ignore
    _OPENAI_AVAILABLE = True
except ImportError:
    _OpenAI = None  # type: ignore
    _OPENAI_AVAILABLE = False

_OPENAI_MODEL = "gpt-4o"


def _sse(event_type: str, payload: Dict[str, Any]) -> str:
    """Encode a single SSE data line."""
    payload["type"] = event_type
    return f"data: {json.dumps(payload, default=str)}\n\n"


# ── keyword routing helpers ─────────────────────────────────────────────────

_ENVIRONMENT_KEYWORDS = {"risk", "environment", "hazard", "flood", "fault",
                         "slope", "fire", "esa", "liquefaction", "suitability",
                         "environmental", "danger", "unsafe"}

_ZONING_KEYWORDS = {"zoning", "zone", "regulation", "code", "allowed",
                    "permit", "use", "ordinance", "compliance", "setback",
                    "fsr", "far", "height limit", "residential", "commercial",
                    "industrial"}

_SPATIAL_KEYWORDS = {"optimize", "optimise", "plan", "mix", "layout",
                     "pareto", "allocation", "assign", "land use", "generate",
                     "suggest", "recommend", "best use"}

_EXPLAIN_KEYWORDS = {"explain", "why", "factor", "cause", "attribute",
                     "breakdown", "contribution", "what causes"}


def _keyword_route(query: str) -> List[str]:
    q = query.lower()
    tools: List[str] = []
    if any(k in q for k in _EXPLAIN_KEYWORDS):
        tools.append("explain_risk")
    if any(k in q for k in _ENVIRONMENT_KEYWORDS):
        tools.append("analyze_environment")
    if any(k in q for k in _ZONING_KEYWORDS):
        tools.append("query_zoning")
    if any(k in q for k in _SPATIAL_KEYWORDS):
        tools.append("optimize_land_use")
    return tools or ["analyze_environment"]


# ── CopilotOrchestrator ─────────────────────────────────────────────────────

class CopilotOrchestrator:
    """Orchestrates agent calls for the Planner's Copilot."""

    def __init__(self):
        self._llm_client: Optional[Any] = None
        self._setup_llm()

    def _setup_llm(self) -> None:
        key = os.getenv("OPENAI_API_KEY", "")
        if not _OPENAI_AVAILABLE or not key:
            logger.info("CopilotOrchestrator: OpenAI unavailable, using keyword routing.")
            return
        try:
            self._llm_client = _OpenAI(api_key=key)
            logger.info("CopilotOrchestrator: OpenAI configured (model=%s).", _OPENAI_MODEL)
        except Exception as exc:
            logger.warning("CopilotOrchestrator: OpenAI init failed: %s", exc)

    # ── public API ──────────────────────────────────────────────────────────

    async def stream(
        self,
        query: str,
        parcel_ids: List[str],
        parcel_features: List[Dict],
        history: List[Dict],
    ) -> AsyncGenerator[str, None]:
        """
        Run the copilot pipeline and yield SSE event strings.

        Yields SSE lines; caller wraps in FastAPI StreamingResponse.
        """
        try:
            async for event in self._pipeline(query, parcel_ids, parcel_features, history):
                yield event
        except Exception as exc:
            logger.error("CopilotOrchestrator error: %s", exc, exc_info=True)
            yield _sse("error", {"message": str(exc)})

    # ── pipeline ────────────────────────────────────────────────────────────

    async def _pipeline(
        self,
        query: str,
        parcel_ids: List[str],
        parcel_features: List[Dict],
        history: List[Dict],
    ) -> AsyncGenerator[str, None]:

        yield _sse("agent_start", {
            "agent": "orchestrator",
            "message": "Routing your query to the right agents…",
        })

        # Determine which tools to call
        tools = await self._plan_tools(query, parcel_ids)

        yield _sse("agent_complete", {
            "agent": "orchestrator",
            "result": {"tools_selected": tools},
        })

        collected: Dict[str, Any] = {}

        for tool_name in tools:
            yield _sse("agent_start", {
                "agent": tool_name,
                "message": self._tool_start_message(tool_name),
            })

            result = await self._run_tool(tool_name, query, parcel_ids, parcel_features)
            collected[tool_name] = result

            yield _sse("agent_complete", {
                "agent": tool_name,
                "result": result,
            })

        # Synthesize final answer
        answer_chunks: List[str] = []
        async for chunk in self._synthesize(query, collected, parcel_ids):
            yield chunk
            if chunk.startswith("data:"):
                try:
                    payload = json.loads(chunk[5:].strip())
                    if payload.get("type") == "text_chunk":
                        answer_chunks.append(payload.get("text", ""))
                except Exception:
                    pass

        # Extract land-use plan if spatial optimization ran
        land_use_plan = self._extract_land_use_plan(collected)

        yield _sse("final", {
            "summary": "".join(answer_chunks) or self._template_answer(query, collected),
            "land_use_plan": land_use_plan,
        })

    # ── tool routing ────────────────────────────────────────────────────────

    async def _plan_tools(self, query: str, parcel_ids: List[str]) -> List[str]:
        if not parcel_ids:
            return []
        if self._llm_client is not None:
            try:
                return await self._gemini_route(query)
            except Exception as exc:
                logger.warning("Gemini routing failed (%s); falling back to keyword.", exc)
        return _keyword_route(query)

    async def _gemini_route(self, query: str) -> List[str]:
        response = self._llm_client.chat.completions.create(
            model=_OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a GIS planning assistant. Based on the user's query, decide which tools to run. "
                        "Available tools: analyze_environment, query_zoning, optimize_land_use, explain_risk. "
                        "Return ONLY a JSON array of tool names, e.g. [\"analyze_environment\",\"query_zoning\"]"
                    ),
                },
                {"role": "user", "content": query},
            ],
            temperature=0,
            max_tokens=60,
        )
        text = (response.choices[0].message.content or "").strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            tools = json.loads(text[start:end])
            valid = {"analyze_environment", "query_zoning", "optimize_land_use", "explain_risk"}
            return [t for t in tools if t in valid] or ["analyze_environment"]
        return _keyword_route(query)

    # ── tool execution ──────────────────────────────────────────────────────

    async def _run_tool(
        self,
        tool_name: str,
        query: str,
        parcel_ids: List[str],
        parcel_features: List[Dict],
    ) -> Dict[str, Any]:
        if tool_name == "analyze_environment":
            return self._run_environment(parcel_ids, parcel_features)
        if tool_name == "query_zoning":
            return self._run_zoning(query, parcel_ids, parcel_features)
        if tool_name == "optimize_land_use":
            return self._run_spatial(parcel_ids, parcel_features, query)
        if tool_name == "explain_risk":
            return self._run_explain(parcel_ids, parcel_features)
        return {"error": f"Unknown tool: {tool_name}"}

    def _run_environment(
        self,
        parcel_ids: List[str],
        parcel_features: List[Dict],
    ) -> Dict[str, Any]:
        try:
            from services.shared import get_suitability_agent
            agent = get_suitability_agent()
            df = pd.DataFrame({"parcel_id": parcel_ids})
            results_df = agent.predict(df)
            records = results_df.to_dict(orient="records")
            return {
                "stage": "environment",
                "parcel_count": len(records),
                "results": records,
            }
        except Exception as exc:
            logger.error("Environment tool error: %s", exc, exc_info=True)
            return {"stage": "environment", "error": str(exc)}

    def _run_zoning(
        self,
        query: str,
        parcel_ids: List[str],
        parcel_features: List[Dict],
    ) -> Dict[str, Any]:
        try:
            from pathlib import Path
            from services.shared import resolve_rag_persist_dir
            from agent.zoning_agent.rag_service import RagService

            backend_dir = Path(__file__).resolve().parent.parent
            rag = RagService(persist_dir=resolve_rag_persist_dir(backend_dir))

            q = query or "What are the zoning regulations and allowed uses for these parcels?"
            retrieved = rag.retrieve(q, top_k=5, mmr=True)
            answer = rag.answer(q, {}, retrieved, [])

            return {
                "stage": "zoning",
                "parcel_count": len(parcel_ids),
                "answer": answer,
                "chunks_retrieved": len(retrieved),
            }
        except Exception as exc:
            logger.error("Zoning tool error: %s", exc, exc_info=True)
            return {"stage": "zoning", "error": str(exc)}

    @staticmethod
    def _parse_target_mix(query: str) -> Dict[str, float]:
        """Extract percentage targets from query, e.g. '50% green space' → {green: 0.5}."""
        import re
        q = query.lower()
        mix: Dict[str, float] = {}
        pattern = re.compile(r'(\d+)\s*%\s*(green|residential|commercial|industrial)')
        for m in pattern.finditer(q):
            pct, use = float(m.group(1)) / 100.0, m.group(2)
            mix[use] = min(max(pct, 0.0), 1.0)
        if not mix:
            # defaults
            mix = {"residential": 0.4, "commercial": 0.2, "industrial": 0.1, "green": 0.3}
        else:
            # fill remaining uses proportionally
            remaining = max(0.0, 1.0 - sum(mix.values()))
            defaults = {"residential": 0.4, "commercial": 0.2, "industrial": 0.1, "green": 0.3}
            unfilled = {k: v for k, v in defaults.items() if k not in mix}
            total_default = sum(unfilled.values()) or 1.0
            for k, v in unfilled.items():
                mix[k] = remaining * (v / total_default)
        return mix

    def _run_spatial(
        self,
        parcel_ids: List[str],
        parcel_features: List[Dict],
        query: str,
    ) -> Dict[str, Any]:
        try:
            from agent.spatial_agent.spatial.config import NSGA2Config, SpatialConfig
            from agent.spatial_agent.spatial.objectives import (
                default_objectives, make_land_use_balance_penalty, make_green_area_deviation,
            )
            from agent.spatial_agent.spatial.optimizer import SpatialOptimizer

            if not parcel_features:
                return {"stage": "spatial", "error": "No parcel geometries provided."}

            target_mix = self._parse_target_mix(query)

            n = len(parcel_features)
            pop = min(20, max(10, n))
            gen = 15

            import re
            green_pct = target_mix.get("green", 0.3)
            objectives = (
                *default_objectives()[:1],   # zoning violation
                make_green_area_deviation(green_pct),
                *default_objectives()[2:],   # env risk, fragmentation
                make_land_use_balance_penalty(target_mix),
            )

            config = SpatialConfig(nsga2=NSGA2Config(
                population_size=pop,
                generations=gen,
                num_output_plans=min(3, n),
            ))
            optimizer = SpatialOptimizer(config=config, objective_functions=objectives)
            result = optimizer.optimize_geojson_features(
                parcel_features, include_adjacency=True, adjacency_predicate="touches",
            )

            plans = []
            for plan in result.plans[:3]:
                plans.append({
                    "rank": plan.rank,
                    "objectives": list(plan.objectives),
                    "assignments": [
                        {"parcel_id": a.parcel_id, "use_label": a.use_label}
                        for a in plan.assignments
                    ],
                })

            return {
                "stage": "spatial",
                "parcel_count": len(parcel_features),
                "objective_names": list(result.objective_names),
                "plans": plans,
            }
        except Exception as exc:
            logger.error("Spatial tool error: %s", exc, exc_info=True)
            return {"stage": "spatial", "error": str(exc)}

    def _run_explain(
        self,
        parcel_ids: List[str],
        parcel_features: List[Dict],
    ) -> Dict[str, Any]:
        from services.risk_explainer import RiskExplainer
        explainer = RiskExplainer()
        explanations = []
        for i, pid in enumerate(parcel_ids[:5]):  # Cap at 5 for display
            props = parcel_features[i] if i < len(parcel_features) else {}
            explanations.append({
                "parcel_id": pid,
                **explainer.explain(props),
            })
        return {
            "stage": "explain_risk",
            "explanations": explanations,
        }

    # ── synthesis ───────────────────────────────────────────────────────────

    def _build_context(self, results: Dict[str, Any], parcel_ids: List[str]) -> str:
        """Build a detailed, parcel-specific context block for GPT-4o."""
        lines: List[str] = []

        env = results.get("analyze_environment", {})
        if env.get("results"):
            rows = env["results"]
            lines.append(f"ENVIRONMENTAL ANALYSIS — {len(rows)} parcels:")
            for r in rows:
                pid  = r.get("parcel_id", "?")
                risk = r.get("environmental_risk", 0)
                res  = r.get("residential", 0)
                com  = r.get("commercial",  0)
                ind  = r.get("industrial",  0)
                grn  = r.get("green",       0)
                level = "HIGH" if risk > 0.6 else "MEDIUM" if risk > 0.3 else "LOW"
                lines.append(
                    f"  • Parcel {pid}: risk={risk:.0%} ({level}) | "
                    f"residential={res:.0%} commercial={com:.0%} industrial={ind:.0%} green={grn:.0%}"
                )
            risks = [r.get("environmental_risk", 0) for r in rows]
            avg   = sum(risks) / len(risks)
            safe  = [r["parcel_id"] for r in rows if r.get("environmental_risk", 1) < 0.3]
            risky = [r["parcel_id"] for r in rows if r.get("environmental_risk", 0) > 0.6]
            lines.append(f"  Summary: avg risk {avg:.0%} | safe (<30%): {safe or 'none'} | high-risk (>60%): {risky or 'none'}")

        expl = results.get("explain_risk", {})
        if expl.get("explanations"):
            lines.append("\nRISK FACTOR BREAKDOWN:")
            for ex in expl["explanations"][:3]:
                pid    = ex.get("parcel_id", "?")
                score  = ex.get("total_rule_score", 0)
                active = [c["label"] for c in ex.get("contributions", []) if c["active"]]
                lines.append(f"  • Parcel {pid}: rule score={score:.0f}/100 | active hazards: {', '.join(active) or 'none'}")

        zoning = results.get("query_zoning", {})
        if zoning.get("answer"):
            lines.append(f"\nZONING REGULATIONS:\n{zoning['answer'][:600]}")

        sp = results.get("optimize_land_use", {})
        if sp.get("plans"):
            plan0 = sp["plans"][0]
            assignments = plan0.get("assignments", [])
            mix: Dict[str, int] = {}
            for a in assignments:
                use = a.get("use_label", "unknown")
                mix[use] = mix.get(use, 0) + 1
            mix_str = " | ".join(f"{k}: {v}" for k, v in sorted(mix.items()))
            lines.append(
                f"\nSPATIAL OPTIMIZATION — {len(sp['plans'])} Pareto plans generated.\n"
                f"  Best plan assignment: {mix_str}"
            )
            lines.append("  Specific parcel assignments:")
            for a in assignments[:6]:
                lines.append(f"    • Parcel {a.get('parcel_id', '?')} → {a.get('use_label', '?')}")

        return "\n".join(lines)

    async def _synthesize(
        self,
        query: str,
        results: Dict[str, Any],
        parcel_ids: List[str],
    ) -> AsyncGenerator[str, None]:
        if self._llm_client is None:
            return

        context = self._build_context(results, parcel_ids)
        if not context.strip():
            return

        prompt = (
            f"You are a professional urban planning assistant analyzing {len(parcel_ids)} specific parcels.\n"
            f"Answer the planner's question using the ACTUAL parcel data below. "
            f"Reference specific parcel IDs and their actual risk scores. Be specific, not generic.\n\n"
            f"Question: {query}\n\n"
            f"Actual parcel data:\n{context}\n\n"
            f"Give a 3-5 sentence response that directly answers using the real numbers and parcel IDs above."
        )

        try:
            stream = self._llm_client.chat.completions.create(
                model=_OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional urban planning assistant. "
                            "Always reference specific parcel IDs and actual data values from the analysis. "
                            "Never give generic advice — ground every statement in the provided numbers."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield _sse("text_chunk", {"text": delta})
        except Exception as exc:
            logger.warning("OpenAI synthesis failed: %s", exc)

    # ── helpers ─────────────────────────────────────────────────────────────

    def _tool_start_message(self, tool_name: str) -> str:
        return {
            "analyze_environment": "Running environmental risk analysis…",
            "query_zoning":        "Querying zoning regulations…",
            "optimize_land_use":   "Optimizing land-use allocation (NSGA-II)…",
            "explain_risk":        "Computing risk factor attribution…",
        }.get(tool_name, f"Running {tool_name}…")

    def _extract_land_use_plan(self, results: Dict[str, Any]) -> Optional[List[Dict]]:
        sp = results.get("optimize_land_use") or results.get("spatial")
        if sp and "plans" in sp and sp["plans"]:
            return sp["plans"][0].get("assignments")
        return None

    @staticmethod
    def _clean_rag_answer(raw: str) -> str:
        """Strip placeholder headers from RAG fallback answers."""
        import re
        # Remove lines like "**Question:** ..." and "*(Gemini API unavailable...)*"
        lines = raw.splitlines()
        cleaned = [
            ln for ln in lines
            if not re.match(r"^\*?\*?Question:", ln.strip())
            and "Gemini API unavailable" not in ln
            and not ln.strip().startswith("*(")
        ]
        # Also strip source citations like **[Unknown, file.pdf]**
        text = "\n".join(cleaned).strip()
        text = re.sub(r"\*\*\[.*?\]\*\*\s*", "", text)
        return text.strip()

    def _template_answer(self, query: str, results: Dict[str, Any]) -> str:
        parts = []
        env = results.get("analyze_environment", {})
        if env.get("results"):
            rows  = env["results"]
            risks = [r.get("environmental_risk", 0) for r in rows]
            avg   = sum(risks) / len(risks) if risks else 0
            safe  = [r["parcel_id"] for r in rows if r.get("environmental_risk", 1) < 0.3]
            risky = [r["parcel_id"] for r in rows if r.get("environmental_risk", 0) > 0.6]
            summary = (
                f"**Environmental Analysis** — {len(rows)} parcels assessed, "
                f"average risk **{avg:.0%}**."
            )
            if safe:
                summary += f"\n- **Safe for residential** (risk <30%): {', '.join(safe)}"
            if risky:
                summary += f"\n- **High-risk** (risk >60%): {', '.join(risky)}"
            parts.append(summary)

        expl = results.get("explain_risk", {})
        if expl.get("explanations"):
            lines = ["**Risk Factor Breakdown**"]
            for ex in expl["explanations"][:4]:
                active = [c["label"] for c in ex.get("contributions", []) if c["active"]]
                lines.append(
                    f"- Parcel **{ex['parcel_id']}**: score {ex.get('total_rule_score', 0):.0f}/100"
                    + (f" — {', '.join(active[:2])}" if active else " — no active hazards")
                )
            parts.append("\n".join(lines))

        zoning = results.get("query_zoning", {})
        if zoning.get("answer"):
            cleaned = self._clean_rag_answer(zoning["answer"])
            if cleaned:
                parts.append(f"**Zoning Regulations**\n{cleaned[:400]}")

        spatial = results.get("optimize_land_use", {})
        if spatial.get("plans"):
            plan0 = spatial["plans"][0]
            mix: Dict[str, int] = {}
            for a in plan0.get("assignments", []):
                use = a.get("use_label", "?")
                mix[use] = mix.get(use, 0) + 1
            mix_str = " · ".join(f"{v} {k}" for k, v in sorted(mix.items()))
            parts.append(
                f"**Land-Use Optimization** — Generated **{len(spatial['plans'])} Pareto-optimal plan(s)**.\n"
                f"Best plan: {mix_str}. Applied to Live Map."
            )

        return "\n\n".join(parts) or "Select parcels on the map and ask a question to begin."
