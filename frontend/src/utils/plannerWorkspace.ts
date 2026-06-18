import type {
  LandUseAssignment,
  ParcelSuitabilityScores,
  SpatialOptimizationPlan,
  SpatialOptimizationResponse,
} from '../types';

export const WORKSPACE_PARCEL_GEOJSON_URL = '/parcels_env_risk_clipped.geojson';
export const WORKSPACE_SOURCE_MODE_LABEL = 'Static GeoJSON';
export const WORKSPACE_DATASET_LABEL = 'parcels_env_risk_clipped.geojson';

export const PARCEL_ID_CANDIDATES = [
  'APN',
  'apn',
  'parcel_id',
  'parcelId',
  'PARCELID',
  'PARNO',
  'id',
  'OBJECTID',
] as const;

export const RISK_CANDIDATES = [
  'risk_score_norm',
  'environmental_risk',
  'xgb_risk_score',
  'rule_risk_score',
] as const;

export const ZONE_CANDIDATES = [
  'ZONING_CODE',
  'zoning_code',
  'zone',
  'zoning',
  'zone_code',
  'allowed_uses',
] as const;

export const JURISDICTION_CANDIDATES = [
  'jurisdiction',
  'JURISDICTION',
  'city',
  'CITY',
  'municipality',
  'county',
] as const;

export const SUITABILITY_FIELD_CANDIDATES: Record<LandUseAssignment, string[]> = {
  residential: ['suitability_residential', 'residential'],
  commercial: ['suitability_commercial', 'commercial'],
  industrial: ['suitability_industrial', 'industrial'],
  green: ['suitability_green', 'green'],
};

export type PlannerConstraintKey =
  | 'steep'
  | 'liquefaction'
  | 'flood'
  | 'fault'
  | 'fire'
  | 'esa'
  | 'mscp';

export interface ConstraintSummaryItem {
  key: PlannerConstraintKey;
  label: string;
  count: number;
  share: number;
}

const CONSTRAINT_DEFINITIONS: Array<{
  key: PlannerConstraintKey;
  label: string;
  property: string;
  kind: 'hazard' | 'policy';
}> = [
  { key: 'steep', label: 'Steep Slope', property: 'is_steep', kind: 'hazard' },
  {
    key: 'liquefaction',
    label: 'Liquefaction',
    property: 'has_liquefaction',
    kind: 'hazard',
  },
  { key: 'flood', label: 'Flood', property: 'has_flood', kind: 'hazard' },
  { key: 'fault', label: 'Fault', property: 'has_fault', kind: 'hazard' },
  { key: 'fire', label: 'Fire Zone', property: 'is_fire_zone', kind: 'hazard' },
  { key: 'esa', label: 'ESA', property: 'in_esa', kind: 'policy' },
  { key: 'mscp', label: 'MSCP', property: 'in_mscp', kind: 'policy' },
];

export interface WorkspaceOptimizationMetadata {
  parcelCount: number;
  warnings: string[];
  debugTimeline: SpatialOptimizationResponse['debug_timeline'];
  settings: SpatialOptimizationResponse['settings'] | null;
  generatedAt: string;
}

export interface WorkspaceFeatureSummary {
  count: number;
  areaM2: number | null;
  averageParcelAreaM2: number | null;
  averagePerimeterM: number | null;
  dominantZone: string | null;
  dominantConstraint: string | null;
  zoningCategories: string[];
  jurisdictions: string[];
  averageRisk: number | null;
  constrainedParcelCount: number;
  protectedParcelCount: number;
  multiConstraintParcelCount: number;
  topConstraints: ConstraintSummaryItem[];
  protectedFlags: ConstraintSummaryItem[];
  suitabilityAverages: Partial<Record<LandUseAssignment, number>>;
}

export function getParcelId(feature: any): string {
  const props = (feature?.properties || {}) as Record<string, unknown>;
  for (const key of PARCEL_ID_CANDIDATES) {
    const value = props[key];
    if (value === null || value === undefined) continue;
    const normalized = String(value).trim();
    if (normalized) return normalized;
  }

  const fallback = feature?.id;
  if (fallback !== null && fallback !== undefined) {
    const normalized = String(fallback).trim();
    if (normalized) return normalized;
  }

  return '';
}

export function buildFeatureMap(features: any[]): Map<string, any> {
  const next = new Map<string, any>();
  for (const feature of features) {
    const parcelId = getParcelId(feature);
    if (!parcelId || next.has(parcelId)) continue;
    next.set(parcelId, feature);
  }
  return next;
}

function getProperty(properties: Record<string, any>, candidates: readonly string[]): unknown {
  for (const key of candidates) {
    if (properties[key] !== undefined && properties[key] !== null && properties[key] !== '') {
      return properties[key];
    }
  }
  return undefined;
}

function coerceNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}

function coerceBooleanFlag(value: unknown): boolean {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return Number.isFinite(value) && value !== 0;
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    return ['1', 'true', 'yes', 'y'].includes(normalized);
  }
  return false;
}

export function normalizeRiskValue(value: unknown): number | null {
  const numeric = coerceNumber(value);
  if (numeric === null) return null;
  if (numeric < 0) return null;
  if (numeric <= 1) return numeric;
  if (numeric <= 100) return numeric / 100;
  return null;
}

export function getRiskFromProperties(properties: Record<string, any>): number | null {
  for (const key of RISK_CANDIDATES) {
    const risk = normalizeRiskValue(properties[key]);
    if (risk !== null) return risk;
  }
  return null;
}

export function getAreaM2FromProperties(properties: Record<string, any>): number | null {
  const numeric = coerceNumber(properties.area_m2);
  if (numeric === null || numeric <= 0) return null;
  return numeric;
}

export function getPerimeterMFromProperties(properties: Record<string, any>): number | null {
  const numeric = coerceNumber(properties.perimeter_m);
  if (numeric === null || numeric <= 0) return null;
  return numeric;
}

function normalizeLabel(value: unknown): string | null {
  if (typeof value === 'string') {
    const normalized = value.trim();
    return normalized.length > 0 ? normalized : null;
  }
  if (Array.isArray(value)) {
    const parts = value
      .map((entry) => (typeof entry === 'string' ? entry.trim() : ''))
      .filter(Boolean);
    return parts.length > 0 ? parts.join(', ') : null;
  }
  return null;
}

export function getZoneFromProperties(properties: Record<string, any>): string | null {
  return normalizeLabel(getProperty(properties, ZONE_CANDIDATES));
}

export function getJurisdictionFromProperties(properties: Record<string, any>): string | null {
  return normalizeLabel(getProperty(properties, JURISDICTION_CANDIDATES));
}

export function getSuitabilityFromProperties(
  properties: Record<string, any>,
  label: LandUseAssignment
): number | null {
  for (const candidate of SUITABILITY_FIELD_CANDIDATES[label]) {
    const normalized = normalizeRiskValue(properties[candidate]);
    if (normalized !== null) return normalized;
  }
  return null;
}

function incrementCount(bucket: Map<string, number>, value: string | null) {
  if (!value) return;
  bucket.set(value, (bucket.get(value) ?? 0) + 1);
}

function pickMostFrequent(bucket: Map<string, number>): string | null {
  let winner: string | null = null;
  let maxCount = -1;
  for (const [value, count] of bucket.entries()) {
    if (count > maxCount) {
      winner = value;
      maxCount = count;
    }
  }
  return winner;
}

function getActiveConstraintDefinitions(properties: Record<string, any>) {
  return CONSTRAINT_DEFINITIONS.filter((definition) =>
    coerceBooleanFlag(properties[definition.property])
  );
}

export function summarizeFeatures(features: any[]): WorkspaceFeatureSummary {
  const zoneCounts = new Map<string, number>();
  const jurisdictions = new Set<string>();
  const zoningCategories = new Set<string>();
  const constraintCounts = new Map<PlannerConstraintKey, number>();
  const suitabilityTotals: Partial<Record<LandUseAssignment, number>> = {};
  const suitabilityCounts: Partial<Record<LandUseAssignment, number>> = {};
  let totalAreaM2 = 0;
  let areaCount = 0;
  let totalPerimeterM = 0;
  let perimeterCount = 0;
  let totalRisk = 0;
  let riskCount = 0;
  let constrainedParcelCount = 0;
  let protectedParcelCount = 0;
  let multiConstraintParcelCount = 0;

  for (const feature of features) {
    const properties = (feature?.properties || {}) as Record<string, any>;
    const zone = getZoneFromProperties(properties);
    const jurisdiction = getJurisdictionFromProperties(properties);
    const area = getAreaM2FromProperties(properties);
    const perimeter = getPerimeterMFromProperties(properties);
    const risk = getRiskFromProperties(properties);
    const activeConstraints = getActiveConstraintDefinitions(properties);

    incrementCount(zoneCounts, zone);
    if (zone) zoningCategories.add(zone);
    if (jurisdiction) jurisdictions.add(jurisdiction);

    if (area !== null) {
      totalAreaM2 += area;
      areaCount += 1;
    }

    if (perimeter !== null) {
      totalPerimeterM += perimeter;
      perimeterCount += 1;
    }

    if (risk !== null) {
      totalRisk += risk;
      riskCount += 1;
    }

    if (activeConstraints.length > 0) {
      constrainedParcelCount += 1;
    }
    if (activeConstraints.length >= 2) {
      multiConstraintParcelCount += 1;
    }
    if (activeConstraints.some((definition) => definition.kind === 'policy')) {
      protectedParcelCount += 1;
    }
    activeConstraints.forEach((definition) => {
      constraintCounts.set(definition.key, (constraintCounts.get(definition.key) ?? 0) + 1);
    });

    (['residential', 'commercial', 'industrial', 'green'] as LandUseAssignment[]).forEach((label) => {
      const suitability = getSuitabilityFromProperties(properties, label);
      if (suitability === null) return;
      suitabilityTotals[label] = (suitabilityTotals[label] ?? 0) + suitability;
      suitabilityCounts[label] = (suitabilityCounts[label] ?? 0) + 1;
    });
  }

  const suitabilityAverages: Partial<Record<LandUseAssignment, number>> = {};
  (['residential', 'commercial', 'industrial', 'green'] as LandUseAssignment[]).forEach((label) => {
    const total = suitabilityTotals[label];
    const count = suitabilityCounts[label];
    if (typeof total === 'number' && typeof count === 'number' && count > 0) {
      suitabilityAverages[label] = total / count;
    }
  });

  const summaryCount = Math.max(features.length, 1);
  const topConstraints = CONSTRAINT_DEFINITIONS.map((definition) => {
    const count = constraintCounts.get(definition.key) ?? 0;
    return {
      key: definition.key,
      label: definition.label,
      count,
      share: count / summaryCount,
    };
  })
    .filter((item) => item.count > 0)
    .sort((left, right) => {
      if (right.count !== left.count) return right.count - left.count;
      return left.label.localeCompare(right.label);
    });

  const protectedFlags = topConstraints.filter(
    (item) => item.key === 'esa' || item.key === 'mscp'
  );

  return {
    count: features.length,
    areaM2: areaCount > 0 ? totalAreaM2 : null,
    averageParcelAreaM2: areaCount > 0 ? totalAreaM2 / areaCount : null,
    averagePerimeterM: perimeterCount > 0 ? totalPerimeterM / perimeterCount : null,
    dominantZone: pickMostFrequent(zoneCounts),
    dominantConstraint: topConstraints[0]?.label ?? null,
    zoningCategories: Array.from(zoningCategories.values()).sort(),
    jurisdictions: Array.from(jurisdictions.values()).sort(),
    averageRisk: riskCount > 0 ? totalRisk / riskCount : null,
    constrainedParcelCount,
    protectedParcelCount,
    multiConstraintParcelCount,
    topConstraints,
    protectedFlags,
    suitabilityAverages,
  };
}

export function formatArea(value: number | null): string {
  if (value === null || !Number.isFinite(value) || value <= 0) {
    return '—';
  }

  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toLocaleString(undefined, {
      maximumFractionDigits: 2,
    })} km²`;
  }

  if (value >= 10_000) {
    return `${(value / 10_000).toLocaleString(undefined, {
      maximumFractionDigits: 2,
    })} ha`;
  }

  return `${value.toLocaleString(undefined, {
    maximumFractionDigits: 0,
  })} m²`;
}

export function formatPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return '—';
  }

  return `${(value * 100).toLocaleString(undefined, {
    maximumFractionDigits: 1,
  })}%`;
}

export function previewParcelIds(ids: string[], maxItems = 3): string {
  if (ids.length === 0) return '—';
  const preview = ids.slice(0, maxItems);
  const suffix = ids.length > maxItems ? ` +${ids.length - maxItems}` : '';
  return `${preview.join(', ')}${suffix}`;
}

export function hasEnvironmentalValues(features: any[]): boolean {
  return features.some((feature) => {
    const properties = (feature?.properties || {}) as Record<string, any>;
    return getRiskFromProperties(properties) !== null;
  });
}

export function hasZoningValues(features: any[]): boolean {
  return features.some((feature) => {
    const properties = (feature?.properties || {}) as Record<string, any>;
    return getZoneFromProperties(properties) !== null;
  });
}

export function buildSelectedFeatures(
  selectedIds: string[],
  selectedFeatureById: Map<string, any>,
  loadedFeatureById: Map<string, any>
): any[] {
  const features: any[] = [];
  for (const id of selectedIds) {
    const feature = selectedFeatureById.get(id) ?? loadedFeatureById.get(id);
    if (feature) {
      features.push(feature);
    }
  }
  return features;
}

export function buildOptimizationMetadata(
  response: SpatialOptimizationResponse
): WorkspaceOptimizationMetadata {
  return {
    parcelCount: response.parcel_count,
    warnings: Array.isArray(response.warnings) ? response.warnings : [],
    debugTimeline: response.debug_timeline,
    settings: response.settings ?? null,
    generatedAt: new Date().toISOString(),
  };
}

export function buildLandUsePlanMap(plans: SpatialOptimizationPlan[]): Map<string, LandUseAssignment> {
  const next = new Map<string, LandUseAssignment>();
  const firstPlan = plans[0];
  if (!firstPlan) return next;

  for (const assignment of firstPlan.assignments) {
    const label = String(assignment.use_label).toLowerCase();
    if (
      label === 'residential' ||
      label === 'commercial' ||
      label === 'industrial' ||
      label === 'green'
    ) {
      next.set(String(assignment.parcel_id), label as LandUseAssignment);
    }
  }

  return next;
}

export function buildEnvironmentScores(features: any[]): Map<string, ParcelSuitabilityScores> {
  const next = new Map<string, ParcelSuitabilityScores>();

  for (const feature of features) {
    const parcelId = getParcelId(feature);
    if (!parcelId) continue;
    const properties = (feature?.properties || {}) as Record<string, any>;
    const environmentalRisk = getRiskFromProperties(properties);
    next.set(parcelId, {
      residential: 0,
      commercial: 0,
      industrial: 0,
      green: 0,
      environmental_risk: environmentalRisk ?? 0,
    });
  }

  return next;
}
