// Type definitions for the application

export type ZoneType = 'residential' | 'commercial' | 'industrial' | 'mixed' | 'green';
export type MapStyle = 'satellite' | 'street' | 'landuse';
export type SimulationSpeed = 'slow' | 'medium' | 'fast';
export type ViewType =
  | 'workbench'
  | 'environmental'
  | 'layers'
  | 'plans'
  | 'copilot'
  | 'settings'
  | 'agents'
  | 'constraints';

// Copilot types
export interface CopilotSSEEvent {
  type: 'agent_start' | 'agent_complete' | 'text_chunk' | 'final' | 'error';
  agent?: string;
  message?: string;
  result?: Record<string, any>;
  text?: string;
  summary?: string;
  land_use_plan?: Array<{ parcel_id: string; use_label: string }>;
}

export interface CopilotMessage {
  role: 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
}

export interface AgentStepStatus {
  agent: string;
  label: string;
  status: 'pending' | 'running' | 'done' | 'skipped';
  result?: Record<string, any>;
}

export interface RiskContribution {
  factor: string;
  label: string;
  weight: number;
  active: boolean;
  contribution_pct: number;
}

export interface RiskExplanation {
  parcel_id: string;
  contributions: RiskContribution[];
  total_rule_score: number;
  xgb_risk_score?: number;
}

export interface CounterfactualResult {
  parcel_id: string;
  original_score: number;
  counterfactual_score: number;
  delta: number;
  applied_changes: Record<string, { from: number; to: number }>;
}

export interface SpatialAssignmentExplanationScores {
  suitability: Record<LandUseAssignment, number>;
  assigned_use_score: number;
  environmental_risk: number | null;
  allowed_uses: string[];
}

export interface SpatialAssignmentSpatialContext {
  enabled?: boolean;
  radius_m?: number | null;
  assigned_use?: LandUseAssignment | 'unknown';
  neighbor_pairs_evaluated: number;
  compatible_pairs: number;
  conflict_pairs: number;
  green_buffer_pairs: number;
  industrial_residential_conflicts: number;
  nearby_use_counts: Record<string, number>;
  closest_neighbors?: Array<{
    parcel_id: string;
    assigned_use: LandUseAssignment | 'unknown';
    distance_m: number;
    compatibility_score: number;
  }>;
  reasons?: string[];
  warnings?: string[];
}

export interface SpatialAssignmentExplanation {
  parcel_id: string | null;
  assigned_use: LandUseAssignment;
  headline: string;
  reasons: string[];
  warnings: string[];
  risk_level: 'low' | 'moderate' | 'high' | 'unknown';
  best_suitability_use: LandUseAssignment;
  scores: SpatialAssignmentExplanationScores;
  spatial_context?: SpatialAssignmentSpatialContext | null;
}

export interface ExplainSpatialAssignmentRequest {
  parcel_id?: string | null;
  parcel_properties: Record<string, any>;
  assigned_use: LandUseAssignment;
  target_mix?: Partial<LandUseMixTargets>;
  use_spatial_compatibility?: boolean;
  spatial_neighbor_radius_m?: number;
  plan_assignments?: Array<{ parcel_id: string; use_label: LandUseAssignment | string }>;
  plan_parcels?: any[];
}

export interface LandUseZone {
  id: string;
  type: ZoneType;
  x: number;
  y: number;
  width: number;
  height: number;
  population?: number;
  compliance: number;
  selected?: boolean;
}

export interface Metrics {
  population: number;
  traffic: number;
  zoning: number;
  environmental: number;
  greenArea: number;
}

export interface GeoJSONExport {
  type: 'FeatureCollection';
  features: Array<{
    type: 'Feature';
    geometry: {
      type: 'Polygon';
      coordinates: number[][][];
    };
    properties: {
      id: string;
      type: ZoneType;
      population?: number;
      compliance: number;
    };
  }>;
  metadata: {
    region: string;
    timestamp: string;
    version: string;
  };
}

export interface AgentConfig {
  id: string;
  name: string;
  enabled: boolean;
  parameters: Record<string, unknown>;
}

export interface PlanningParameters {
  /** Soil sand percentage (10-80) */
  soil_sand_pct?: number;
  /** Soil clay percentage (5-40) */
  soil_clay_pct?: number;
  /** Mean Air Quality Index (20-200) */
  aqi_mean?: number;
  /** Mean impervious surface ratio (0-1) */
  impervious_mean?: number;
}

export interface Parcel {
  id: string;
  polygon: [number, number][];
  centroid: { x: number; y: number };
  /** Optional planning parameters for this parcel */
  planningParams?: PlanningParameters;
}

export interface ParcelGeoJSONExport {
  type: 'FeatureCollection';
  features: Array<{
    type: 'Feature';
    id: string;
    geometry: {
      type: 'Polygon';
      coordinates: number[][][];
    };
    properties: {
      centroid: { x: number; y: number };
      /** Optional planning parameters for model prediction */
      soil_sand_pct?: number;
      soil_clay_pct?: number;
      aqi_mean?: number;
      impervious_mean?: number;
      /** Optional land use assignment from optimized plan */
      land_use?: LandUseAssignment;
    };
  }>;
}

export interface ParcelSuitabilityScore {
  id: string;
  score: number;
}

export interface ParcelSuitabilityScores {
  residential: number;
  commercial: number;
  industrial: number;
  green: number;
  environmental_risk?: number;
}

export interface ParcelWithScores extends Parcel {
  suitabilityScores?: ParcelSuitabilityScores;
}

/** Land use assignment for a parcel (from optimized land use plan) */
export type LandUseAssignment = 'residential' | 'commercial' | 'industrial' | 'green';

export interface ParcelLandUsePlan {
  parcelId: string;
  assignment: LandUseAssignment;
  confidence?: number;
}

export interface LandUseMixTargets {
  residential: number;
  commercial: number;
  industrial: number;
  green: number;
}

export interface SpatialOptimizationAssignment {
  parcel_id: string;
  use_code: number;
  use_label: string;
}

export interface SpatialCompatibilitySummary {
  neighbor_pairs_evaluated: number;
  compatible_pairs: number;
  conflict_pairs: number;
  green_buffer_pairs: number;
  industrial_residential_conflicts: number;
}

export type SpatialOverlayLayerKey =
  | 'roads'
  | 'networks'
  | 'blocks'
  | 'green'
  | 'buildings'
  | 'plots'
  | 'density';

export type SpatialOverlayVisibility = Record<SpatialOverlayLayerKey, boolean>;

export type ReferenceMapLayerKey =
  | 'municipal_boundaries'
  | 'zoning_base_sd'
  | 'zoning_unincorporated'
  | 'general_plan_land_use_sd';

export type ReferenceMapLayerVisibility = Record<ReferenceMapLayerKey, boolean>;

export interface PlanningMetrics {
  housing_units: number;
  estimated_residents: number;
  green_space_per_resident_m2: number;
  who_green_target_m2: number;
  hazard_built_parcels: number;
  total_parcels: number;
  estimated_annual_tax_usd: number;
  area_m2: {
    residential: number;
    commercial: number;
    industrial: number;
    green: number;
    total: number;
  };
}

export interface CurrentStatePlanningMetrics extends PlanningMetrics {
  total_hazard_parcels: number;
}

export interface SpatialOptimizationPlan {
  rank: number;
  crowding_distance: number;
  objectives: number[];
  assignments: SpatialOptimizationAssignment[];
  planning_metrics?: PlanningMetrics;
  spatial_compatibility_score?: number;
  spatial_compatibility_summary?: SpatialCompatibilitySummary | null;
  spatial_compatibility_warnings?: string[];
}

export interface SpatialOptimizeRequest {
  parcels: any[];
  target_mix: Partial<LandUseMixTargets>;
  num_output_plans: number;
  population_size?: number;
  generations?: number;
  include_adjacency?: boolean;
  adjacency_predicate?: 'touches' | 'intersects';
  debug?: boolean;
  progress_every_generations?: number;
  interactive_mode?: boolean;
  use_spatial_compatibility?: boolean;
  spatial_neighbor_radius_m?: number;
  spatial_compatibility_weight?: number;
}

export interface SpatialOptimizationResponse {
  parcel_count: number;
  objective_names: string[];
  plans: SpatialOptimizationPlan[];
  current_state?: CurrentStatePlanningMetrics;
  warnings?: string[];
  debug_timeline?: Array<{
    stage: string;
    elapsed_seconds: number;
    generation?: number;
    total_generations?: number;
    progress_ratio?: number;
    parcel_count?: number;
    feature_count?: number;
    comparisons?: number;
    edge_count?: number;
  }>;
  settings: {
    num_output_plans: number;
    population_size: number;
    generations: number;
    include_adjacency: boolean;
    adjacency_predicate: 'touches' | 'intersects';
    target_mix: Partial<LandUseMixTargets>;
    use_spatial_compatibility?: boolean;
    spatial_neighbor_radius_m?: number;
    spatial_compatibility_weight?: number;
    spatial_neighbor_pairs?: number;
    elapsed_seconds?: number;
    request_id?: string;
  };
}

export interface SavedMapCreatePayload {
  name: string;
  description?: string | null;
  selected_plan_rank?: number | null;
  input_parcels: any[];
  optimization_result: SpatialOptimizationResponse;
}

export interface SavedMapUpdatePayload {
  name?: string;
  description?: string | null;
  selected_plan_rank?: number | null;
}

export interface SavedMapListItem {
  id: number;
  name: string;
  description: string | null;
  parcel_count: number;
  plan_count: number;
  selected_plan_rank: number | null;
  created_at: string;
  updated_at: string;
}

export interface SavedMapResponse extends SavedMapListItem {
  user_id: number;
  input_parcels: any[];
  optimization_result: SpatialOptimizationResponse;
}

export interface SavedMapListResponse {
  items: SavedMapListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface UserAccountSettings {
  fullName: string;
  plannerRole: string;
  organization: string;
  email: string;
}

export interface ScenarioGenerationSettings {
  basePopulationSize: number;
  baseGenerations: number;
  neighborhoodContinuity: boolean;
  boundaryRule: 'touches' | 'intersects';
  smartScalingForLargeSelections: boolean;
  progressUpdateEvery: number;
  interactiveRun: boolean;
  diagnosticsMode: boolean;
}

export interface RegulatoryGuidanceSettings {
  autoFetchParcelGuidance: boolean;
  includeParcelContext: boolean;
  keepConversationContext: boolean;
  responseStyle: 'concise' | 'balanced' | 'detailed';
  defaultQuestionTemplate: string;
  showParcelTagNotifications: boolean;
}

export interface EnvironmentalReviewSettings {
  lowRiskMax: number;
  moderateRiskMax: number;
  elevatedRiskMax: number;
  highRiskMax: number;
  showHazardChecklist: boolean;
}

export interface GrowthDemandSettings {
  defaultPlanAlternatives: number;
  maxPlanAlternatives: number;
}

export interface PlannerRuntimeSettings {
  userAccount: UserAccountSettings;
  scenarioGeneration: ScenarioGenerationSettings;
  regulatoryGuidance: RegulatoryGuidanceSettings;
  environmentalReview: EnvironmentalReviewSettings;
  growthDemand: GrowthDemandSettings;
}
