import type { LandUseMixTargets, SpatialOptimizationPlan } from '../types';

export type ComparisonLandUse = 'residential' | 'commercial' | 'industrial' | 'green';

export interface NormalizedPlanAssignment {
  parcelId: string;
  use: string;
}

export interface LandUseMixEntry {
  count: number;
  percentage: number;
}

export type LandUseMixStats = Record<ComparisonLandUse, LandUseMixEntry>;

export interface AverageRiskMetric {
  value: number | null;
  observedCount: number;
}

export interface FragmentationMetric {
  value: number;
  boundaryCount: number;
  edgeCount: number;
}

export interface PlanComparisonMetrics {
  assignments: NormalizedPlanAssignment[];
  landUseMix: LandUseMixStats;
  averageRisk: AverageRiskMetric;
  highRiskBuiltUseCount: number | null;
  zoningConflictCount: number | null;
  targetMixDeviation: number | null;
  fragmentationScore: FragmentationMetric | null;
}

type ParcelFeatureLookup = ReadonlyMap<string, unknown>;

const LAND_USE_KEYS: ComparisonLandUse[] = ['residential', 'commercial', 'industrial', 'green'];
const BUILT_USES = new Set(['residential', 'commercial', 'industrial']);
const RISK_FIELD_CANDIDATES = [
  'risk_score_norm',
  'environmental_risk',
  'risk_score',
  'xgb_risk_score',
  'rule_risk_score',
];
const ASSIGNMENT_ARRAY_KEYS = ['assignments', 'assignment', 'parcel_assignments'];
const PARCEL_ID_KEYS = ['parcel_id', 'parcelId', 'apn', 'APN', 'id', 'parcel'];
const USE_KEYS = ['use_label', 'assigned_use', 'use', 'land_use', 'landUse', 'label'];
const EXPLICIT_ALLOWED_USE_KEYS = ['allowed_uses', 'ALLOWED_USES'];
const ZONING_TEXT_KEYS = ['zoning', 'ZONING_CODE', 'zoning_code', 'GP_LAND_USE', 'gp_land_use'];
const ADJACENCY_KEYS = [
  'neighbors',
  'neighbor_ids',
  'neighborIds',
  'adjacent_parcels',
  'adjacentParcelIds',
  'ADJACENT_PARCELS',
  'adjacency',
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function getProperties(featureOrProperties: unknown): Record<string, unknown> {
  if (!isRecord(featureOrProperties)) return {};
  const properties = featureOrProperties.properties;
  return isRecord(properties) ? properties : featureOrProperties;
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

function coerceBoolean(value: unknown): boolean | null {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return value !== 0;
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    if (['true', 'yes', 'y', '1', 'compatible'].includes(normalized)) return true;
    if (['false', 'no', 'n', '0', 'incompatible'].includes(normalized)) return false;
  }
  return null;
}

function firstNonEmptyValue(record: Record<string, unknown>, keys: string[]): unknown {
  for (const key of keys) {
    const value = record[key];
    if (value !== undefined && value !== null && value !== '') {
      return value;
    }
  }
  return undefined;
}

export function normalizeUse(value: unknown): string {
  const normalized = String(value ?? '')
    .trim()
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/[\s-]+/g, '_')
    .replace(/[^a-z0-9_]/g, '');

  if (!normalized) return '';
  if (
    normalized.includes('open_space') ||
    normalized.includes('conservation') ||
    normalized.includes('park') ||
    normalized.includes('green') ||
    normalized.includes('agri')
  ) {
    return 'green';
  }
  if (
    normalized.includes('residential') ||
    normalized.includes('housing') ||
    normalized.includes('single_family') ||
    normalized.includes('multi_family') ||
    normalized.includes('multifamily') ||
    normalized.includes('duplex') ||
    normalized.includes('townhome')
  ) {
    return 'residential';
  }
  if (
    normalized.includes('commercial') ||
    normalized.includes('retail') ||
    normalized.includes('office')
  ) {
    return 'commercial';
  }
  if (
    normalized.includes('industrial') ||
    normalized.includes('warehouse') ||
    normalized.includes('manufacturing')
  ) {
    return 'industrial';
  }
  return normalized;
}

function normalizeAssignmentEntry(entry: unknown): NormalizedPlanAssignment | null {
  if (!isRecord(entry)) return null;
  const parcelId = firstNonEmptyValue(entry, PARCEL_ID_KEYS);
  const useValue = firstNonEmptyValue(entry, USE_KEYS);
  const normalizedParcelId = String(parcelId ?? '').trim();
  const normalizedUse = normalizeUse(useValue);

  if (!normalizedParcelId || !normalizedUse) return null;
  return {
    parcelId: normalizedParcelId,
    use: normalizedUse,
  };
}

export function getPlanAssignments(plan: unknown): NormalizedPlanAssignment[] {
  if (!isRecord(plan)) return [];

  for (const key of ASSIGNMENT_ARRAY_KEYS) {
    const value = plan[key];
    if (Array.isArray(value)) {
      return value
        .map(normalizeAssignmentEntry)
        .filter((assignment): assignment is NormalizedPlanAssignment => assignment !== null);
    }
  }

  const assignmentMap = firstNonEmptyValue(plan, ASSIGNMENT_ARRAY_KEYS);
  if (isRecord(assignmentMap)) {
    return Object.entries(assignmentMap)
      .map(([parcelId, use]) => ({
        parcelId: parcelId.trim(),
        use: normalizeUse(use),
      }))
      .filter((assignment) => assignment.parcelId && assignment.use);
  }

  return [];
}

export function calculateLandUseMix(
  assignments: NormalizedPlanAssignment[]
): LandUseMixStats {
  const stats = Object.fromEntries(
    LAND_USE_KEYS.map((use) => [use, { count: 0, percentage: 0 }])
  ) as LandUseMixStats;
  const total = assignments.length;

  for (const assignment of assignments) {
    if (LAND_USE_KEYS.includes(assignment.use as ComparisonLandUse)) {
      stats[assignment.use as ComparisonLandUse].count += 1;
    }
  }

  if (total === 0) return stats;

  for (const use of LAND_USE_KEYS) {
    stats[use].percentage = (stats[use].count / total) * 100;
  }

  return stats;
}

export function getParcelRisk(feature: unknown): number | null {
  const properties = getProperties(feature);
  for (const key of RISK_FIELD_CANDIDATES) {
    const rawValue = properties[key];
    const numeric = coerceNumber(rawValue);
    if (numeric === null || numeric < 0) continue;
    if (numeric <= 1) return numeric;
    if (numeric <= 100) return numeric / 100;
  }
  return null;
}

function getFeatureForAssignment(
  assignment: NormalizedPlanAssignment,
  parcelFeatureById: ParcelFeatureLookup
): unknown {
  return parcelFeatureById.get(assignment.parcelId);
}

export function calculateAverageRisk(
  assignments: NormalizedPlanAssignment[],
  parcelFeatureById: ParcelFeatureLookup
): AverageRiskMetric {
  let total = 0;
  let observedCount = 0;

  for (const assignment of assignments) {
    const risk = getParcelRisk(getFeatureForAssignment(assignment, parcelFeatureById));
    if (risk === null) continue;
    total += risk;
    observedCount += 1;
  }

  return {
    value: observedCount > 0 ? total / observedCount : null,
    observedCount,
  };
}

export function countHighRiskBuiltUseParcels(
  assignments: NormalizedPlanAssignment[],
  parcelFeatureById: ParcelFeatureLookup
): number | null {
  let observedRiskCount = 0;
  let highRiskCount = 0;

  for (const assignment of assignments) {
    if (!BUILT_USES.has(assignment.use)) continue;
    const risk = getParcelRisk(getFeatureForAssignment(assignment, parcelFeatureById));
    if (risk === null) continue;
    observedRiskCount += 1;
    if (risk >= 0.7) {
      highRiskCount += 1;
    }
  }

  return observedRiskCount > 0 ? highRiskCount : null;
}

function normalizeTargetMix(
  targetMix?: Partial<LandUseMixTargets> | Partial<Record<string, number>> | null
): Partial<Record<ComparisonLandUse, number>> | null {
  if (!targetMix || typeof targetMix !== 'object') return null;
  const values = LAND_USE_KEYS.map((use) => [use, coerceNumber(targetMix[use])] as const).filter(
    ([, value]) => value !== null && value >= 0
  );
  const total = values.reduce((sum, [, value]) => sum + (value ?? 0), 0);
  if (total <= 0) return null;

  return Object.fromEntries(
    values.map(([use, value]) => [use, ((value ?? 0) / total) * 100])
  ) as Partial<Record<ComparisonLandUse, number>>;
}

export function calculateTargetMixDeviation(
  actualMix: LandUseMixStats,
  targetMix?: Partial<LandUseMixTargets> | Partial<Record<string, number>> | null
): number | null {
  const normalizedTarget = normalizeTargetMix(targetMix);
  if (!normalizedTarget) return null;

  return LAND_USE_KEYS.reduce((deviation, use) => {
    return deviation + Math.abs(actualMix[use].percentage - (normalizedTarget[use] ?? 0));
  }, 0);
}

function parseAllowedUses(value: unknown): Set<string> {
  const rawItems = Array.isArray(value)
    ? value
    : typeof value === 'string'
      ? value.split(/[,;|]/)
      : [];
  const allowed = new Set<string>();

  for (const rawItem of rawItems) {
    const normalized = normalizeUse(rawItem);
    if (LAND_USE_KEYS.includes(normalized as ComparisonLandUse)) {
      allowed.add(normalized);
    }
    if (normalized.includes('mixed')) {
      allowed.add('residential');
      allowed.add('commercial');
    }
  }

  return allowed;
}

function inferAllowedUses(properties: Record<string, unknown>): Set<string> | null {
  for (const key of EXPLICIT_ALLOWED_USE_KEYS) {
    const allowed = parseAllowedUses(properties[key]);
    if (allowed.size > 0) return allowed;
  }

  const textBlob = ZONING_TEXT_KEYS.map((key) => String(properties[key] ?? ''))
    .join(' ')
    .toLowerCase();
  if (!textBlob.trim()) return null;

  const allowed = new Set<string>();
  const textAllowed = parseAllowedUses(textBlob);
  for (const use of textAllowed) {
    allowed.add(use);
  }
  if (/\bmixed\b|\bmixed_use\b|\bmixed-use\b/.test(textBlob)) {
    allowed.add('residential');
    allowed.add('commercial');
  }

  return allowed.size > 0 ? allowed : null;
}

export function calculateZoningConflictCount(
  assignments: NormalizedPlanAssignment[],
  parcelFeatureById: ParcelFeatureLookup
): number | null {
  let checkedCount = 0;
  let conflictCount = 0;

  for (const assignment of assignments) {
    const properties = getProperties(getFeatureForAssignment(assignment, parcelFeatureById));
    const explicitCompatibility =
      coerceBoolean(properties.zoningCompatible) ?? coerceBoolean(properties.zoning_compatible);

    if (explicitCompatibility !== null) {
      checkedCount += 1;
      if (!explicitCompatibility) conflictCount += 1;
      continue;
    }

    const allowedUses = inferAllowedUses(properties);
    if (!allowedUses) continue;

    checkedCount += 1;
    if (!allowedUses.has(assignment.use)) {
      conflictCount += 1;
    }
  }

  return checkedCount > 0 ? conflictCount : null;
}

function parseNeighborIds(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((entry) => String(entry).trim()).filter(Boolean);
  }
  if (typeof value === 'string') {
    return value.split(/[,;|]/).map((entry) => entry.trim()).filter(Boolean);
  }
  if (isRecord(value)) {
    return Object.keys(value).map((entry) => entry.trim()).filter(Boolean);
  }
  return [];
}

function getNeighborIds(feature: unknown): string[] {
  const properties = getProperties(feature);
  for (const key of ADJACENCY_KEYS) {
    const neighbors = parseNeighborIds(properties[key]);
    if (neighbors.length > 0) return neighbors;
  }
  return [];
}

export function calculateFragmentationScore(
  assignments: NormalizedPlanAssignment[],
  parcelFeatureById: ParcelFeatureLookup
): FragmentationMetric | null {
  const useByParcelId = new Map(assignments.map((assignment) => [assignment.parcelId, assignment.use]));
  const seenEdges = new Set<string>();
  let edgeCount = 0;
  let boundaryCount = 0;

  for (const assignment of assignments) {
    const neighbors = getNeighborIds(getFeatureForAssignment(assignment, parcelFeatureById));
    for (const neighborId of neighbors) {
      const neighborUse = useByParcelId.get(neighborId);
      if (!neighborUse) continue;
      const edgeKey = [assignment.parcelId, neighborId].sort().join('::');
      if (seenEdges.has(edgeKey)) continue;
      seenEdges.add(edgeKey);
      edgeCount += 1;
      if (assignment.use !== neighborUse) {
        boundaryCount += 1;
      }
    }
  }

  if (edgeCount === 0) return null;

  return {
    value: boundaryCount / edgeCount,
    boundaryCount,
    edgeCount,
  };
}

export function calculatePlanComparisonMetrics({
  plan,
  parcelFeatureById,
  targetMix,
}: {
  plan: SpatialOptimizationPlan;
  parcelFeatureById: ParcelFeatureLookup;
  targetMix?: Partial<LandUseMixTargets> | Partial<Record<string, number>> | null;
}): PlanComparisonMetrics {
  const assignments = getPlanAssignments(plan);
  const landUseMix = calculateLandUseMix(assignments);

  return {
    assignments,
    landUseMix,
    averageRisk: calculateAverageRisk(assignments, parcelFeatureById),
    highRiskBuiltUseCount: countHighRiskBuiltUseParcels(assignments, parcelFeatureById),
    zoningConflictCount: calculateZoningConflictCount(assignments, parcelFeatureById),
    targetMixDeviation: calculateTargetMixDeviation(landUseMix, targetMix),
    fragmentationScore: calculateFragmentationScore(assignments, parcelFeatureById),
  };
}
