"""Generate PLANNERS_COPILOT_SPEC.pdf — implementation spec for the Copilot feature."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, Preformatted, KeepTogether,
)
from pathlib import Path

OUT = Path(__file__).parent / "PLANNERS_COPILOT_SPEC.pdf"

# ---------- Styles ----------
INDIGO = HexColor("#4f46e5")
SLATE_900 = HexColor("#0f172a")
SLATE_700 = HexColor("#334155")
SLATE_500 = HexColor("#64748b")
SLATE_100 = HexColor("#f1f5f9")
SLATE_200 = HexColor("#e2e8f0")
GREEN = HexColor("#059669")
AMBER = HexColor("#d97706")
CODE_BG = HexColor("#1e293b")

styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    "Title", parent=styles["Title"],
    fontSize=26, leading=32, textColor=SLATE_900,
    spaceAfter=4, alignment=TA_LEFT, fontName="Helvetica-Bold",
)
subtitle_style = ParagraphStyle(
    "Subtitle", parent=styles["Normal"],
    fontSize=12, leading=16, textColor=SLATE_500,
    spaceAfter=20, fontName="Helvetica",
)
h1 = ParagraphStyle(
    "H1", parent=styles["Heading1"],
    fontSize=18, leading=22, textColor=INDIGO,
    spaceBefore=16, spaceAfter=10, fontName="Helvetica-Bold",
)
h2 = ParagraphStyle(
    "H2", parent=styles["Heading2"],
    fontSize=14, leading=18, textColor=SLATE_900,
    spaceBefore=12, spaceAfter=6, fontName="Helvetica-Bold",
)
h3 = ParagraphStyle(
    "H3", parent=styles["Heading3"],
    fontSize=11, leading=14, textColor=SLATE_700,
    spaceBefore=8, spaceAfter=4, fontName="Helvetica-Bold",
)
body = ParagraphStyle(
    "Body", parent=styles["Normal"],
    fontSize=10, leading=14, textColor=SLATE_900,
    spaceAfter=6, alignment=TA_JUSTIFY, fontName="Helvetica",
)
bullet = ParagraphStyle(
    "Bullet", parent=body,
    leftIndent=14, bulletIndent=4, spaceAfter=3,
)
note_style = ParagraphStyle(
    "Note", parent=body,
    backColor=SLATE_100, borderColor=SLATE_200, borderWidth=0,
    leftIndent=8, rightIndent=8, spaceBefore=6, spaceAfter=6,
    borderPadding=8, textColor=SLATE_700,
)
code_style = ParagraphStyle(
    "Code", parent=styles["Code"],
    fontSize=8.5, leading=11, textColor=white,
    backColor=CODE_BG, borderPadding=8,
    leftIndent=0, rightIndent=0, spaceBefore=6, spaceAfter=8,
    fontName="Courier",
)

# ---------- Helpers ----------
def para(text, style=body): return Paragraph(text, style)

def code_block(text):
    return Preformatted(text, code_style)

def bullets(items):
    return [Paragraph(f"• {t}", bullet) for t in items]

def info_table(rows, col_widths=None):
    t = Table(rows, colWidths=col_widths or [2.0*inch, 4.3*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), INDIGO),
        ("TEXTCOLOR",  (0,0), (-1,0), white),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, SLATE_100]),
        ("GRID", (0,0), (-1,-1), 0.25, SLATE_200),
    ]))
    return t

# ---------- Build story ----------
story = []

# ===== COVER =====
story += [
    Paragraph("The Planner's Copilot", title_style),
    Paragraph(
        "A Conversational Multi-Agent Orchestrator for GeoVision &nbsp;&nbsp;|&nbsp;&nbsp; Implementation Specification",
        subtitle_style,
    ),
]

cover_table = Table([
    ["Project",     "GeoVision — AI-Assisted Urban Planning"],
    ["Feature",     "The Planner's Copilot"],
    ["Status",      "Proposed — Not Yet Implemented"],
    ["Owner",       "Final Year Project Team"],
    ["Dependencies", "Environment Agent, Zoning RAG, Spatial Agent (all existing)"],
    ["Est. Effort", "~1 week (focused)"],
], colWidths=[1.5*inch, 4.8*inch])
cover_table.setStyle(TableStyle([
    ("FONTSIZE", (0,0), (-1,-1), 9),
    ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
    ("TEXTCOLOR", (0,0), (0,-1), SLATE_700),
    ("TEXTCOLOR", (1,0), (1,-1), SLATE_900),
    ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ("TOPPADDING", (0,0), (-1,-1), 6),
    ("LEFTPADDING", (0,0), (-1,-1), 10),
    ("LINEBELOW", (0,0), (-1,-2), 0.25, SLATE_200),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
]))
story += [cover_table, Spacer(1, 22)]

story += [
    Paragraph("Executive Summary", h1),
    para(
        "GeoVision currently exposes three independent backend agents — an XGBoost-based "
        "Environment Agent for parcel risk scoring, a RAG-based Zoning Agent for regulation "
        "lookup, and an NSGA-II Spatial Agent for land-use optimization. Each has a dedicated "
        "REST endpoint, and the frontend calls them separately based on which UI button the "
        "user clicks."
    ),
    para(
        "The Planner's Copilot replaces this fragmented interaction model with a single "
        "natural-language chat window. A Large Language Model (Gemini) acts as an "
        "<b>orchestrator</b>: it decomposes planner intent into tool calls, invokes the "
        "correct agents in the correct order, streams their progress to the UI in real time, "
        "and synthesizes the combined result with SHAP-grounded explanations. The user never "
        "has to know three agents exist."
    ),
    para(
        "This upgrade transforms GeoVision from a collection of tools into a true multi-agent "
        "system and addresses the single most common critique of agent-based architectures: "
        "<i>“is this actually multi-agent, or just three independent services?”</i>"
    ),
]

story.append(PageBreak())

# ===== SECTION 1: ARCHITECTURE =====
story += [
    Paragraph("1. Architecture Overview", h1),
    para(
        "The Copilot sits in front of the three existing agents as a router and synthesis "
        "layer. It does not replace them; it composes them."
    ),
    Spacer(1, 6),
]

arch_rows = [
    ["Layer",           "Component",                          "Responsibility"],
    ["Frontend",        "CopilotChatPanel.tsx",               "Chat UI, live agent status timeline, counterfactual controls"],
    ["API",             "POST /api/copilot/query (SSE)",      "Server-sent events endpoint: streams agent lifecycle events"],
    ["Orchestrator",    "CopilotOrchestrator (Python)",       "LLM tool-calling loop, session state, explanation synthesis"],
    ["LLM",             "Gemini gemini-1.5-flash",            "Intent decomposition, tool selection, natural-language answer"],
    ["Tool 1",          "filter_by_risk (Environment Agent)", "Filter parcels by xgb_risk_score threshold"],
    ["Tool 2",          "query_zoning (Zoning RAG)",          "Retrieve regulations, check allowed uses"],
    ["Tool 3",          "optimize_cluster (Spatial Agent)",   "Run NSGA-II with subset of parcels"],
    ["Tool 4",          "explain_parcel (SHAP)",              "Return SHAP feature contributions for one parcel"],
    ["Tool 5",          "counterfactual_risk",                "Re-score parcels with modified hazard boundaries"],
]
arch_table = Table(arch_rows, colWidths=[1.0*inch, 1.9*inch, 3.4*inch])
arch_table.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), INDIGO),
    ("TEXTCOLOR", (0,0), (-1,0), white),
    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ("FONTSIZE", (0,0), (-1,-1), 8.5),
    ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ("TOPPADDING", (0,0), (-1,-1), 5),
    ("LEFTPADDING", (0,0), (-1,-1), 6),
    ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, SLATE_100]),
    ("GRID", (0,0), (-1,-1), 0.25, SLATE_200),
]))
story += [arch_table, Spacer(1, 14)]

story += [
    Paragraph("1.1  Request Flow", h2),
    para("A typical end-to-end request goes through these stages:"),
]
story += bullets([
    "<b>User types query</b> into CopilotChatPanel. UI opens EventSource to /api/copilot/query.",
    "<b>Orchestrator receives query</b>, packages it into a Gemini tool-calling prompt that describes each available tool.",
    "<b>Gemini emits tool calls</b>, e.g. <font face='Courier'>[filter_by_risk(max_risk=0.3), query_zoning(apns, use='multi_family'), optimize_cluster(apns, k=5)]</font>.",
    "<b>Orchestrator executes tools in order</b>, streaming <font face='Courier'>{agent, status, result}</font> events to the client over SSE. Each event triggers a UI update.",
    "<b>Tool outputs are fed back to Gemini</b> as tool results. Gemini synthesizes a final natural-language answer with citations and SHAP explanations.",
    "<b>Frontend renders the map state</b> (highlighted parcels, elevation by risk) as each agent completes, not at the end.",
])

story += [
    Spacer(1, 10),
    Paragraph("1.2  Why This Is &lsquo;Real&rsquo; Multi-Agent", h2),
    para(
        "A jury can fairly ask whether calling three APIs sequentially counts as multi-agent. "
        "The Copilot answers that definitively:"
    ),
]
story += bullets([
    "<b>The LLM does not know the sequence in advance</b> — it decides at runtime which tools to call, in which order, based on the parse of user intent. This is the textbook definition of agentic behavior.",
    "<b>Agents feed each other</b> — output of filter_by_risk becomes input to query_zoning, whose output becomes input to optimize_cluster. The data pipeline is dynamic.",
    "<b>Agents negotiate conflicts</b> — if the Spatial Agent cannot form a cluster with the filtered subset, the LLM retries with a relaxed risk threshold. This feedback loop is invisible to the user but visible in the streaming event log.",
])

story.append(PageBreak())

# ===== SECTION 2: BACKEND =====
story += [
    Paragraph("2. Backend Implementation", h1),
    Paragraph("2.1  New File: backend/services/copilot_orchestrator.py", h2),
    para(
        "Central class that owns the Gemini client, the tool registry, and the SSE event stream. "
        "Roughly 250 lines."
    ),
]

story += [code_block('''from google import genai as google_genai
from google.genai import types as t
from dataclasses import dataclass
from typing import AsyncIterator
import json, os

TOOLS = [
    t.Tool(function_declarations=[
        t.FunctionDeclaration(
            name="filter_by_risk",
            description="Filter parcels by environmental risk threshold.",
            parameters={"type":"OBJECT","properties":{
                "max_risk":{"type":"NUMBER","description":"0-1, inclusive upper bound"},
                "apns":   {"type":"ARRAY","items":{"type":"STRING"}}
            }}
        ),
        t.FunctionDeclaration(
            name="query_zoning",
            description="Check which of the given APNs permit a land use.",
            parameters={"type":"OBJECT","properties":{
                "apns":       {"type":"ARRAY","items":{"type":"STRING"}},
                "intended_use":{"type":"STRING","enum":["residential","commercial",
                                                       "industrial","mixed"]}
            }}
        ),
        t.FunctionDeclaration(
            name="optimize_cluster",
            description="Run NSGA-II over the given parcels to produce k plans.",
            parameters={"type":"OBJECT","properties":{
                "apns":{"type":"ARRAY","items":{"type":"STRING"}},
                "k":   {"type":"INTEGER"}
            }}
        ),
        t.FunctionDeclaration(
            name="explain_parcel",
            description="SHAP feature contributions for one parcel.",
            parameters={"type":"OBJECT","properties":{
                "apn":{"type":"STRING"}
            }}
        ),
    ])
]

class CopilotOrchestrator:
    def __init__(self):
        self._client = google_genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    async def stream(self, user_query: str) -> AsyncIterator[dict]:
        yield {"event":"start","query":user_query}
        chat = self._client.chats.create(
            model="gemini-1.5-flash",
            config=t.GenerateContentConfig(tools=TOOLS, temperature=0.2),
        )
        resp = chat.send_message(user_query)
        while resp.function_calls:
            for call in resp.function_calls:
                yield {"event":"agent_start","agent":call.name,"args":dict(call.args)}
                result = await self._dispatch(call.name, dict(call.args))
                yield {"event":"agent_done","agent":call.name,"result_summary":self._summarize(result)}
                resp = chat.send_message(
                    t.Part.from_function_response(name=call.name, response=result))
        yield {"event":"final","answer":resp.text}''')]

story += [
    Paragraph("2.2  Dispatch Table — Wires Tool Names to Existing Agents", h2),
    para("Each tool is a thin adapter over code that already exists. No agent logic is rewritten."),
]

story += [code_block('''async def _dispatch(self, name: str, args: dict) -> dict:
    if name == "filter_by_risk":
        agent = get_suitability_agent()       # existing singleton
        df = agent.risk_data.loc[args.get("apns") or agent.risk_data.index]
        hits = df[df["xgb_risk_score"]/100 <= args["max_risk"]]
        return {"apns": hits.index.tolist(), "count": len(hits)}

    if name == "query_zoning":
        hits = []
        for apn in args["apns"]:
            ctx = _enrich_parcel_ctx_from_lookup({"APN": apn})
            if _use_is_allowed(ctx, args["intended_use"]):
                hits.append(apn)
        return {"permitted_apns": hits}

    if name == "optimize_cluster":
        parcels = _parcels_for_apns(args["apns"])
        opt = SpatialOptimizer(config=SpatialConfig(
                 nsga2=NSGA2Config(num_output_plans=args["k"])))
        res = opt.optimize_geojson_features(features=parcels)
        return {"plans": [p.to_dict() for p in res.plans]}

    if name == "explain_parcel":
        return _shap_explain(args["apn"])'''
)]

story += [
    Paragraph("2.3  New File: backend/services/shap_explainer.py", h2),
    para(
        "Wraps the trained XGBoost model with a TreeExplainer. Called once at startup; "
        "inference is microseconds per parcel."
    ),
]

story += [code_block('''import shap, joblib, numpy as np
from functools import lru_cache
from pathlib import Path

_MODEL_PATH = Path(__file__).resolve().parents[1] \\
              / "agent" / "environment_agent" / "models" / "suitability_model.pkl"

_FEATURES = ["has_flood","has_fault","has_liquefaction","is_steep",
             "is_fire_zone","in_esa","in_mscp",
             "area_m2","perimeter_m","centroid_x","centroid_y"]

_model     = joblib.load(_MODEL_PATH)
_explainer = shap.TreeExplainer(_model)

@lru_cache(maxsize=4096)
def explain(apn: str) -> dict:
    row = get_suitability_agent().risk_data.loc[apn]
    x   = np.array([[row[f] for f in _FEATURES]])
    sv  = _explainer.shap_values(x)[0]
    contribs = sorted(zip(_FEATURES, sv.tolist()),
                      key=lambda p: abs(p[1]), reverse=True)[:5]
    return {
        "apn": apn,
        "predicted_risk": float(_model.predict(x)[0]),
        "top_drivers": [{"feature":f,"impact":round(v,3)} for f,v in contribs]
    }''')]

story += [
    Paragraph("2.4  New Endpoint: main.py", h2),
    para("A single streaming endpoint. Uses FastAPI's StreamingResponse with text/event-stream."),
]
story += [code_block('''from fastapi.responses import StreamingResponse
from services.copilot_orchestrator import CopilotOrchestrator

_copilot = CopilotOrchestrator()

@app.post("/api/copilot/query")
async def copilot_query(request: Request, body: CopilotRequest):
    async def gen():
        async for event in _copilot.stream(body.query):
            yield f"data: {json.dumps(event)}\\n\\n"
    return StreamingResponse(gen(), media_type="text/event-stream")''')]

story += [
    Paragraph("2.5  Counterfactual Risk Endpoint", h2),
    para(
        "Separately exposed so the UI can call it without going through the LLM for simple "
        "what-if queries. Reuses the existing STRtree logic from the training pipeline."
    ),
]
story += [code_block('''@app.post("/api/risk/counterfactual")
def counterfactual_risk(body: CounterfactualRequest):
    """
    Re-score parcels with modified hazard boundaries.
    body.hazard_overrides = {"fire_zone_expand_pct": 20, ...}
    Returns a delta map: {apn: {before: 0.22, after: 0.67, delta: +0.45}}
    """
    expanded = _expand_hazard_layers(body.hazard_overrides)
    flags    = _compute_flags_for_parcels(body.apns, expanded)
    new_risk = _rule_weighted_sum(flags)
    old_risk = get_suitability_agent().risk_data.loc[body.apns]["xgb_risk_score"]/100
    return {apn: {"before": float(old_risk[apn]),
                  "after":  float(new_risk[apn]),
                  "delta":  float(new_risk[apn] - old_risk[apn])}
            for apn in body.apns}''')]

story.append(PageBreak())

# ===== SECTION 3: FRONTEND =====
story += [
    Paragraph("3. Frontend Implementation", h1),
    Paragraph("3.1  New Component: CopilotChatPanel", h2),
    para(
        "Three-pane React component. Left: chat thread. Middle: live agent status timeline "
        "(updates as SSE events arrive). Right: explanation drawer that opens when a parcel "
        "is clicked on the map."
    ),
]
story += [
    info_table([
        ["File", "Purpose"],
        ["frontend/src/components/copilot/CopilotChatPanel.tsx", "Main container, layout, EventSource client"],
        ["frontend/src/components/copilot/AgentTimeline.tsx",    "Live animated timeline of agent execution"],
        ["frontend/src/components/copilot/ExplanationDrawer.tsx","SHAP contribution bars, counterfactual slider"],
        ["frontend/src/hooks/useCopilotStream.ts",               "SSE hook — parses events, manages state"],
        ["frontend/src/pages/CopilotPage/CopilotPage.tsx",       "Route-level page, composes chat + map + drawer"],
    ])
]

story += [
    Spacer(1, 10),
    Paragraph("3.2  SSE Hook — Handling Streamed Events", h2),
]
story += [code_block('''export function useCopilotStream() {
  const [events, setEvents] = useState<CopilotEvent[]>([]);
  const [state, setState]   = useState<"idle"|"running"|"done">("idle");

  const ask = useCallback(async (query: string) => {
    setEvents([]); setState("running");
    const res = await fetch("/api/copilot/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\\n\\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const evt = JSON.parse(line.slice(6));
          setEvents(prev => [...prev, evt]);
          if (evt.event === "final") setState("done");
        }
      }
    }
  }, []);

  return { ask, events, state };
}''')]

story += [
    Paragraph("3.3  Map Updates Triggered by Stream Events", h2),
    para(
        "The existing DeckGLMap accepts a <font face='Courier'>highlightedApns</font> prop. "
        "Each agent event updates this set, producing the live narrowing effect the jury sees."
    ),
]
story += [code_block('''useEffect(() => {
  const last = events[events.length - 1];
  if (!last) return;
  if (last.event === "agent_done" && last.agent === "filter_by_risk")
    setHighlightedApns(new Set(last.result_summary.apns));
  else if (last.event === "agent_done" && last.agent === "query_zoning")
    setHighlightedApns(new Set(last.result_summary.permitted_apns));
  else if (last.event === "agent_done" && last.agent === "optimize_cluster")
    setSelectedPlanApns(last.result_summary.plans[0].assignments.map(a => a.parcel_id));
}, [events]);''')]

story.append(PageBreak())

# ===== SECTION 4: SHAP DEEP DIVE =====
story += [
    Paragraph("4. SHAP-Grounded Explanations (the Research Hook)", h1),
    para(
        "SHAP (SHapley Additive exPlanations) is the current gold standard for interpreting "
        "tree-based ML models. It assigns each feature a contribution value such that their "
        "sum equals the difference between the model's prediction and the average training "
        "prediction. For your XGBoost risk model, SHAP answers:"
    ),
]
story += bullets([
    "<b>Which features pushed this parcel's risk up?</b>  (e.g. steep slope: +0.28)",
    "<b>Which features pulled it down?</b>  (e.g. low perimeter: -0.05)",
    "<b>What is the baseline?</b>  (expected_value — the average risk across all parcels)",
])

story += [
    Paragraph("4.1  Why This Impresses a Jury", h2),
    para(
        "Most student projects stop at &ldquo;we trained a model, here's R2.&rdquo; SHAP takes "
        "your XGBoost from black-box to interpretable ML — a hot research area (FAccT, NeurIPS "
        "interpretability track). It also directly addresses a question planners would ask in "
        "real life: &ldquo;why does the model think this parcel is risky?&rdquo;"
    ),
]

story += [
    Paragraph("4.2  Sample Output Structure", h2),
]
story += [code_block('''{
  "apn": "4071900600",
  "predicted_risk": 0.38,
  "expected_value": 0.27,
  "top_drivers": [
    {"feature": "has_fault",        "impact": +0.15},
    {"feature": "is_steep",         "impact": +0.09},
    {"feature": "centroid_y",       "impact": +0.04},
    {"feature": "has_flood",        "impact":  0.00},
    {"feature": "area_m2",          "impact": -0.03}
  ]
}''')]

story += [
    Paragraph("4.3  UI Rendering", h2),
    para(
        "In the Explanation Drawer, render each driver as a horizontal bar: green for negative "
        "impact (safer), red for positive (riskier), length proportional to |impact|. Show the "
        "baseline as a vertical dashed line. The sum visually equals the prediction."
    ),
]

story.append(PageBreak())

# ===== SECTION 5: COUNTERFACTUAL =====
story += [
    Paragraph("5. Counterfactual Scenario Simulation", h1),
    para(
        "After the Copilot returns an initial plan, the user can ask &ldquo;what if?&rdquo; "
        "questions that re-run the analysis with modified hazard boundaries. This is the "
        "second big demo moment and what pushes the project from &ldquo;interesting&rdquo; "
        "to &ldquo;memorable.&rdquo;"
    ),
]

story += [
    Paragraph("5.1  Supported Counterfactuals", h2),
]
story += [
    info_table([
        ["Scenario",                        "Mechanism"],
        ["Fire zone expands by X %",        "Buffer the fire hazard polygon outward by X percent of its diameter"],
        ["Sea level rises by Y meters",     "Expand flood polygons using DEM-based elevation threshold"],
        ["New fault discovered at (x,y)",   "Add a new active-fault line segment and re-run STRtree query"],
        ["ESA boundary redrawn",            "Replace the ESA polygon with a user-drawn polygon"],
    ], col_widths=[2.3*inch, 4.0*inch])
]

story += [
    Spacer(1, 10),
    Paragraph("5.2  Implementation Notes", h2),
]
story += bullets([
    "Hazard layers are already loaded into memory at server startup. Counterfactuals do not touch disk.",
    "Re-using the existing <font face='Courier'>_compute_flag_strtree</font> function means ~5 ms per hazard layer for a few hundred parcels.",
    "On the frontend, show a before/after split view: two DeckGLMaps side-by-side, or a slider that morphs between the two risk colorings.",
    "Publish the counterfactual as a named scenario so the user can save and share (e.g. &ldquo;Scenario A: 2050 sea-level projection&rdquo;).",
])

# ===== SECTION 6: ROADMAP =====
story += [
    Paragraph("6. Implementation Roadmap", h1),
]
roadmap = [
    ["Day",   "Task",                                                                          "Deliverable"],
    ["1",     "Install shap, write shap_explainer.py, verify TreeExplainer on existing model", "Working explain(apn) function + unit test"],
    ["1",     "Define tool schemas, scaffold CopilotOrchestrator class",                       "stream() emits start/final events with no tools yet"],
    ["2",     "Wire filter_by_risk, query_zoning, optimize_cluster tools",                     "End-to-end CLI test: query → 3 tool calls → final answer"],
    ["3",     "FastAPI /api/copilot/query streaming endpoint + SSE framing",                   "curl can stream events live"],
    ["4",     "CopilotChatPanel + AgentTimeline components, SSE hook",                         "UI renders events as they arrive"],
    ["5",     "ExplanationDrawer with SHAP bar chart, click-to-explain on map",                "Clicking any parcel shows its drivers"],
    ["6",     "Counterfactual endpoint + slider UI",                                           "Before/after view with animated transition"],
    ["7",     "Polish: error states, empty states, jury demo script rehearsal",                "Polished demo ready to present"],
]
road_t = Table(roadmap, colWidths=[0.45*inch, 3.1*inch, 2.75*inch])
road_t.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), INDIGO),
    ("TEXTCOLOR",  (0,0), (-1,0), white),
    ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
    ("FONTSIZE",   (0,0), (-1,-1), 8.5),
    ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ("TOPPADDING",    (0,0), (-1,-1), 5),
    ("LEFTPADDING",   (0,0), (-1,-1), 6),
    ("RIGHTPADDING",  (0,0), (-1,-1), 6),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, SLATE_100]),
    ("GRID", (0,0), (-1,-1), 0.25, SLATE_200),
]))
story += [road_t, Spacer(1, 14)]

story += [
    Paragraph("6.1  New Dependencies", h2),
]
story += [code_block("# backend/requirements.txt\nshap>=0.44.0,<1.0.0\n\n# frontend (no new npm packages required — built-in EventSource / fetch stream)")]

story.append(PageBreak())

# ===== SECTION 7: DEMO SCRIPT =====
story += [
    Paragraph("7. The Jury Demo Script", h1),
    para(
        "Three minutes. Six clicks. The goal is to make the jury actually lean forward. "
        "Do not show code during the demo — show the product working."
    ),
]

demo = [
    ["T+0:00",  "Open CopilotPage. Map shows all parcels in neutral grey."],
    ["T+0:10",  "Type: 'Find me 5 parcels for mid-density apartments — low risk, zoning allowed, clustered.' Hit enter."],
    ["T+0:12",  "Agent Timeline pane lights up: Environment Agent... (filtering 712 → 127). Map dims non-matching parcels."],
    ["T+0:20",  "Zoning Agent runs: (127 → 43 permitted). More parcels fade out. Jury sees the funnel."],
    ["T+0:30",  "Spatial Agent runs: NSGA-II with progress ticks. Five parcels glow gold. This is the wow moment."],
    ["T+0:45",  "Click the top-ranked parcel. Explanation Drawer opens: SHAP bars, citations to zoning §131.0412."],
    ["T+1:10",  "Type: 'What if fire hazard zones expand by 20% due to climate change?'"],
    ["T+1:15",  "Screen splits. Left: current plan. Right: re-scored plan. Two parcels drop out, highlighted in red. Slider at the bottom to animate between the two states."],
    ["T+1:40",  "Close with: 'This is three agents coordinated by an LLM, explaining their reasoning with SHAP, and simulating climate scenarios — not a GIS dashboard.'"],
    ["T+2:00",  "Stop talking. Let them ask questions."],
]
demo_t = Table(demo, colWidths=[0.7*inch, 5.6*inch])
demo_t.setStyle(TableStyle([
    ("FONTSIZE", (0,0), (-1,-1), 8.5),
    ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
    ("TEXTCOLOR", (0,0), (0,-1), INDIGO),
    ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ("TOPPADDING",    (0,0), (-1,-1), 6),
    ("LEFTPADDING",   (0,0), (-1,-1), 8),
    ("RIGHTPADDING",  (0,0), (-1,-1), 8),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("LINEBELOW", (0,0), (-1,-2), 0.25, SLATE_200),
]))
story += [demo_t, Spacer(1, 14)]

story += [
    Paragraph("7.1  Anticipated Jury Questions", h2),
]
qa = [
    ["&ldquo;Why multi-agent? Why not one big LLM?&rdquo;",
     "LLMs cannot do STRtree spatial joins, XGBoost inference, or NSGA-II optimization. Each agent is a specialist the LLM delegates to. The LLM's job is decomposition and synthesis — not computation."],
    ["&ldquo;How do you handle LLM hallucination?&rdquo;",
     "Tool outputs are ground truth — the LLM cannot invent parcels, zoning codes, or risk scores. The LLM only decides which tools to call and how to phrase the final answer. SHAP grounds explanations in the actual model, not generated text."],
    ["&ldquo;What if the LLM calls the wrong tool?&rdquo;",
     "Tool schemas are enumerated and validated. If the LLM calls with invalid arguments, the error is returned as a tool result and the LLM retries with corrected arguments. Standard function-calling pattern."],
    ["&ldquo;Is this novel?&rdquo;",
     "The architecture pattern (LLM-as-orchestrator over specialist ML/GIS tools) is current research — matches papers like ToolLLM (2023), Gorilla, HuggingGPT. Applied to urban planning with SHAP-grounded explanations, it is novel."],
    ["&ldquo;How do you evaluate the orchestrator?&rdquo;",
     "Build a small benchmark: 20 planner queries with expected tool-call sequences. Measure tool-selection accuracy, parameter-grounding accuracy, and end-to-end answer correctness. Report these numbers in the thesis."],
]
qa_t = Table([["Likely Question", "Your Answer"]] + [[Paragraph(q, body), Paragraph(a, body)] for q,a in qa],
             colWidths=[2.2*inch, 4.1*inch])
qa_t.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), INDIGO),
    ("TEXTCOLOR", (0,0), (-1,0), white),
    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ("FONTSIZE", (0,0), (-1,0), 9),
    ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ("TOPPADDING", (0,0), (-1,-1), 5),
    ("LEFTPADDING", (0,0), (-1,-1), 7),
    ("RIGHTPADDING", (0,0), (-1,-1), 7),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, SLATE_100]),
    ("GRID", (0,0), (-1,-1), 0.25, SLATE_200),
]))
story += [qa_t]

story.append(PageBreak())

# ===== SECTION 8: RISKS & MITIGATIONS =====
story += [
    Paragraph("8. Risks and Mitigations", h1),
]
risks = [
    ["Gemini API key is blocked (current issue).",
     "Swap to any OpenAI-compatible endpoint (OpenRouter, Together AI, local Ollama). The orchestrator only needs function-calling support. 20 lines of config change."],
    ["SSE stream drops mid-query on flaky networks.",
     "Client retries with Last-Event-ID header. Server caches the last 60 seconds of events per session ID."],
    ["SHAP computation too slow for 700k-parcel explanations.",
     "Not needed — SHAP is called per parcel on demand, not batch. TreeExplainer inference is ~1ms per row. LRU cache for repeat lookups."],
    ["Jury asks why you didn't use LangChain or CrewAI.",
     "Both frameworks add heavy abstraction you don't need. A 250-line orchestrator is easier to explain, debug, and defend than a library you can't see inside. Make this a deliberate design choice in your write-up."],
    ["Counterfactual results produce counterintuitive deltas.",
     "Validate on 3 hand-crafted scenarios before demo. Keep examples where the result is visually obvious (e.g. flood zone doubled → coastal parcels spike red)."],
]
risk_t = Table([["Risk", "Mitigation"]] + [[Paragraph(r, body), Paragraph(m, body)] for r,m in risks],
               colWidths=[2.3*inch, 4.0*inch])
risk_t.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), AMBER),
    ("TEXTCOLOR", (0,0), (-1,0), white),
    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ("FONTSIZE", (0,0), (-1,0), 9),
    ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ("TOPPADDING", (0,0), (-1,-1), 5),
    ("LEFTPADDING", (0,0), (-1,-1), 7),
    ("RIGHTPADDING", (0,0), (-1,-1), 7),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, SLATE_100]),
    ("GRID", (0,0), (-1,-1), 0.25, SLATE_200),
]))
story += [risk_t, Spacer(1, 18)]

# ===== SECTION 9: APPENDIX =====
story += [
    Paragraph("9. Appendix — The Pitch Sentence", h1),
    para(
        "If a juror reads only one thing on one slide, it should be this:"
    ),
    Spacer(1, 6),
]

pitch = Paragraph(
    "<i>&ldquo;GeoVision is not a GIS dashboard — it is an agent orchestration framework where "
    "a language model decomposes planner intent into coordinated calls across an XGBoost risk "
    "model, a RAG zoning expert, and an NSGA-II spatial optimizer, and explains every "
    "recommendation with SHAP-grounded counterfactuals.&rdquo;</i>",
    ParagraphStyle(
        "Pitch", parent=body, fontSize=12, leading=18,
        textColor=SLATE_900, backColor=HexColor("#eef2ff"),
        borderColor=INDIGO, borderWidth=2, borderPadding=14,
        leftIndent=0, rightIndent=0, alignment=TA_LEFT,
    ),
)
story += [pitch, Spacer(1, 18)]

story += [
    Paragraph("End of specification.", ParagraphStyle(
        "End", parent=body, textColor=SLATE_500, fontSize=9, alignment=TA_LEFT,
    )),
]

# ---------- Generate ----------
doc = SimpleDocTemplate(
    str(OUT), pagesize=A4,
    leftMargin=18*mm, rightMargin=18*mm,
    topMargin=18*mm, bottomMargin=18*mm,
    title="The Planner's Copilot — Implementation Specification",
    author="GeoVision FYP",
)
doc.build(story)
print(f"WROTE: {OUT}")
print(f"SIZE:  {OUT.stat().st_size/1024:.1f} KB")
