import type { LandUseMixTargets, SpatialOptimizationPlan } from '../types';
import type { PlanBadge } from './planBadges';
import {
  calculateLandUseMix,
  calculateTargetMixDeviation,
  getParcelRisk,
  getPlanAssignments,
  type ComparisonLandUse,
  type LandUseMixStats,
  type NormalizedPlanAssignment,
} from './planComparison';

export type ConflictSeverity = 'High' | 'Medium' | 'Low';

export interface PlanReportMixRow {
  use: ComparisonLandUse;
  label: string;
  count: number;
  targetPercent: number | null;
  actualPercent: number;
  difference: number | null;
}

export interface PlanReportConflict {
  parcelId: string;
  assignedUse: string;
  issue: string;
  severity: ConflictSeverity;
}

export interface HighRiskBuiltParcel {
  parcelId: string;
  assignedUse: string;
  riskLabel: string;
  hazardFlags: string[];
}

export interface PlanReportMetrics {
  totalAssigned: number;
  targetDeviation: number | null;
  highRiskBuiltCount: number | null;
  possibleZoningConflictCount: number | null;
  objectiveTotal: number | null;
}

export interface PlanComparisonReportRow {
  planLabel: string;
  badges: string;
  residentialPercent: number;
  commercialPercent: number;
  industrialPercent: number;
  greenPercent: number;
  targetDeviation: number | null;
  highRiskBuiltCount: number | null;
  possibleZoningConflictCount: number | null;
  environmentalRiskObjective: number | null;
  zoningPenaltyObjective: number | null;
  fragmentationPenaltyObjective: number | null;
}

export interface ObjectiveMeaning {
  name: string;
  label: string;
  explanation: string;
}

export interface PlanReportSummary {
  mixRows: PlanReportMixRow[];
  mixStats: LandUseMixStats;
  metrics: PlanReportMetrics;
  conflicts: PlanReportConflict[];
  highRiskBuiltParcels: HighRiskBuiltParcel[];
  planComparisonRows: PlanComparisonReportRow[];
  executiveSummary: string;
  selectedPlanExplanation: string;
  objectiveMeanings: ObjectiveMeaning[];
  targetMixAvailable: boolean;
}

const LAND_USE_ORDER: ComparisonLandUse[] = ['residential', 'commercial', 'industrial', 'green'];
const BUILT_USES = new Set(['residential', 'commercial', 'industrial', 'mixed_use']);

const LAND_USE_LABELS: Record<ComparisonLandUse, string> = {
  residential: 'Residential',
  commercial: 'Commercial',
  industrial: 'Industrial',
  green: 'Green',
};

const HAZARD_FLAG_LABELS: Array<[string, string]> = [
  ['has_flood', 'Flood'],
  ['flood', 'Flood'],
  ['floodplain', 'Floodplain'],
  ['steep_slope', 'Steep slope'],
  ['is_steep', 'Steep slope'],
  ['fault', 'Fault'],
  ['has_fault', 'Fault'],
  ['liquefaction', 'Liquefaction'],
  ['has_liquefaction', 'Liquefaction'],
  ['fire', 'Fire hazard'],
  ['fire_zone', 'Fire hazard'],
  ['is_fire_zone', 'Fire hazard'],
  ['esa', 'Environmentally sensitive area'],
  ['in_esa', 'Environmentally sensitive area'],
  ['mscp', 'MSCP area'],
  ['in_mscp', 'MSCP area'],
  ['protected', 'Protected land'],
  ['sensitive', 'Sensitive resource'],
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function getProperties(featureOrProperties: unknown): Record<string, unknown> {
  if (!isRecord(featureOrProperties)) return {};
  const properties = featureOrProperties.properties;
  return isRecord(properties) ? properties : featureOrProperties;
}

function coerceBoolean(value: unknown): boolean {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return value !== 0;
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    return ['true', 'yes', 'y', '1', 'active', 'present'].includes(normalized);
  }
  return false;
}

function coerceNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function normalizeUse(value: unknown): string {
  return String(value ?? '')
    .trim()
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/[\s-]+/g, '_')
    .replace(/[^a-z0-9_]/g, '');
}

function readableUse(value: string): string {
  const normalized = normalizeUse(value);
  if (normalized === 'green') return 'Green';
  if (normalized === 'mixed_use') return 'Mixed Use';
  return normalized.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function getFeatureForAssignment(
  assignment: NormalizedPlanAssignment,
  parcelFeatureById: ReadonlyMap<string, unknown>
): unknown {
  return parcelFeatureById.get(assignment.parcelId);
}

function getPlanObjectiveValues(plan: SpatialOptimizationPlan): number[] {
  const objectives = (plan as { objectives?: unknown }).objectives;
  return Array.isArray(objectives)
    ? objectives.filter((value): value is number => typeof value === 'number' && Number.isFinite(value))
    : [];
}

function getActiveHazardFlags(feature: unknown): string[] {
  const properties = getProperties(feature);
  const flags = new Set<string>();
  for (const [key, label] of HAZARD_FLAG_LABELS) {
    if (coerceBoolean(properties[key])) {
      flags.add(label);
    }
  }
  return [...flags];
}

function riskLabel(feature: unknown): string {
  const risk = getParcelRisk(feature);
  if (risk === null) return 'N/A';
  if (risk >= 0.7) return `${Math.round(risk * 100)}% high risk`;
  if (risk >= 0.4) return `${Math.round(risk * 100)}% medium risk`;
  return `${Math.round(risk * 100)}% low risk`;
}

function isHighRiskBuiltAssignment(
  assignment: NormalizedPlanAssignment,
  feature: unknown
): boolean {
  if (!BUILT_USES.has(normalizeUse(assignment.use))) return false;
  const risk = getParcelRisk(feature);
  return (risk !== null && risk >= 0.7) || getActiveHazardFlags(feature).length > 0;
}

function normalizeTargetMixPercent(
  targetMix?: Partial<LandUseMixTargets> | Partial<Record<string, number>> | null
): Partial<Record<ComparisonLandUse, number>> | null {
  if (!targetMix || typeof targetMix !== 'object') return null;
  const values = LAND_USE_ORDER.map((use) => [use, coerceNumber(targetMix[use])] as const).filter(
    ([, value]) => value !== null && value >= 0
  );
  const total = values.reduce((sum, [, value]) => sum + (value ?? 0), 0);
  if (total <= 0) return null;
  return Object.fromEntries(
    values.map(([use, value]) => [use, ((value ?? 0) / total) * 100])
  ) as Partial<Record<ComparisonLandUse, number>>;
}

export function buildTargetMixRows(
  mixStats: LandUseMixStats,
  targetMix?: Partial<LandUseMixTargets> | Partial<Record<string, number>> | null
): PlanReportMixRow[] {
  const normalizedTarget = normalizeTargetMixPercent(targetMix);
  return LAND_USE_ORDER.map((use) => {
    const targetPercent = normalizedTarget?.[use] ?? null;
    const actualPercent = mixStats[use].percentage;
    return {
      use,
      label: LAND_USE_LABELS[use],
      count: mixStats[use].count,
      targetPercent,
      actualPercent,
      difference: targetPercent === null ? null : actualPercent - targetPercent,
    };
  });
}

function getSuitabilityScore(feature: unknown, assignedUse: string): number | null {
  const properties = getProperties(feature);
  const normalizedUse = normalizeUse(assignedUse);
  const candidates = [
    `suitability_${normalizedUse}`,
    `${normalizedUse}_suitability`,
    normalizedUse,
  ];
  for (const key of candidates) {
    const numeric = coerceNumber(properties[key]);
    if (numeric === null || numeric < 0) continue;
    return numeric <= 1 ? numeric : numeric / 100;
  }
  return null;
}

function parseAllowedUses(value: unknown): Set<string> {
  const rawItems = Array.isArray(value)
    ? value
    : typeof value === 'string'
      ? value.split(/[,;|]/)
      : [];
  const allowed = new Set<string>();
  for (const item of rawItems) {
    const normalized = normalizeUse(item);
    if (!normalized) continue;
    if (normalized.includes('mixed')) {
      allowed.add('residential');
      allowed.add('commercial');
    }
    if (normalized.includes('residential') || normalized === 'r' || normalized.startsWith('rs')) {
      allowed.add('residential');
    }
    if (normalized.includes('commercial') || normalized === 'c') {
      allowed.add('commercial');
    }
    if (normalized.includes('industrial') || normalized === 'i') {
      allowed.add('industrial');
    }
    if (
      normalized.includes('green') ||
      normalized.includes('open_space') ||
      normalized.includes('park') ||
      normalized.includes('conservation')
    ) {
      allowed.add('green');
    }
  }
  return allowed;
}

function inferAllowedUses(properties: Record<string, unknown>): Set<string> | null {
  for (const key of ['allowed_uses', 'ALLOWED_USES', 'permitted_uses', 'zoning_allowed_uses']) {
    const allowed = parseAllowedUses(properties[key]);
    if (allowed.size > 0) return allowed;
  }

  const textBlob = ['zoning', 'ZONING_CODE', 'zoning_code', 'GP_LAND_USE', 'gp_land_use']
    .map((key) => String(properties[key] ?? ''))
    .join(' ')
    .toLowerCase();
  if (!textBlob.trim()) return null;

  const allowed = parseAllowedUses(textBlob);
  if (/\brs\b|\brm\b|\br-\b|residential/.test(textBlob)) allowed.add('residential');
  if (/\bcc\b|\bcn\b|\bc-\b|commercial|retail|office/.test(textBlob)) allowed.add('commercial');
  if (/\bil\b|\bih\b|\bi-\b|industrial|manufacturing|warehouse/.test(textBlob)) allowed.add('industrial');
  if (/open space|open_space|\bos\b|park|conservation|green|agri/.test(textBlob)) allowed.add('green');
  if (/mixed|mixed_use|mixed-use/.test(textBlob)) {
    allowed.add('residential');
    allowed.add('commercial');
  }

  return allowed.size > 0 ? allowed : null;
}

function getPossibleZoningConflict(
  assignment: NormalizedPlanAssignment,
  feature: unknown
): boolean | null {
  const properties = getProperties(feature);
  const explicit = properties.zoningCompatible ?? properties.zoning_compatible;
  if (explicit !== undefined && explicit !== null) {
    return !coerceBoolean(explicit);
  }
  const allowedUses = inferAllowedUses(properties);
  if (!allowedUses) return null;
  return !allowedUses.has(normalizeUse(assignment.use));
}

export function buildHighRiskBuiltParcels(
  assignments: NormalizedPlanAssignment[],
  parcelFeatureById: ReadonlyMap<string, unknown>
): HighRiskBuiltParcel[] {
  return assignments
    .filter((assignment) =>
      isHighRiskBuiltAssignment(assignment, getFeatureForAssignment(assignment, parcelFeatureById))
    )
    .map((assignment) => {
      const feature = getFeatureForAssignment(assignment, parcelFeatureById);
      return {
        parcelId: assignment.parcelId,
        assignedUse: readableUse(assignment.use),
        riskLabel: riskLabel(feature),
        hazardFlags: getActiveHazardFlags(feature),
      };
    });
}

export function buildPossibleZoningConflictCount(
  assignments: NormalizedPlanAssignment[],
  parcelFeatureById: ReadonlyMap<string, unknown>
): number | null {
  let checked = 0;
  let conflicts = 0;
  for (const assignment of assignments) {
    const conflict = getPossibleZoningConflict(
      assignment,
      getFeatureForAssignment(assignment, parcelFeatureById)
    );
    if (conflict === null) continue;
    checked += 1;
    if (conflict) conflicts += 1;
  }
  return checked > 0 ? conflicts : null;
}

export function buildTopPlanConflicts(
  assignments: NormalizedPlanAssignment[],
  parcelFeatureById: ReadonlyMap<string, unknown>
): PlanReportConflict[] {
  const conflicts: PlanReportConflict[] = [];
  for (const assignment of assignments) {
    const feature = getFeatureForAssignment(assignment, parcelFeatureById);
    const assignedUse = readableUse(assignment.use);
    const risk = getParcelRisk(feature);
    const hazards = getActiveHazardFlags(feature);

    if (BUILT_USES.has(normalizeUse(assignment.use)) && risk !== null && risk >= 0.7) {
      conflicts.push({
        parcelId: assignment.parcelId,
        assignedUse,
        issue: `High environmental risk assigned to built use (${Math.round(risk * 100)}%).`,
        severity: 'High',
      });
    }

    if (BUILT_USES.has(normalizeUse(assignment.use)) && hazards.length > 0) {
      conflicts.push({
        parcelId: assignment.parcelId,
        assignedUse,
        issue: `Active hazard or constraint flags: ${hazards.slice(0, 3).join(', ')}.`,
        severity: 'High',
      });
    }

    const suitability = getSuitabilityScore(feature, assignment.use);
    if (suitability !== null && suitability < 0.35) {
      conflicts.push({
        parcelId: assignment.parcelId,
        assignedUse,
        issue: `Low suitability score for assigned use (${Math.round(suitability * 100)}%).`,
        severity: 'Medium',
      });
    }

    const zoningConflict = getPossibleZoningConflict(assignment, feature);
    if (zoningConflict) {
      conflicts.push({
        parcelId: assignment.parcelId,
        assignedUse,
        issue: 'Possible mismatch with available zoning or general plan attributes.',
        severity: 'Medium',
      });
    }
  }

  const severityRank: Record<ConflictSeverity, number> = { High: 0, Medium: 1, Low: 2 };
  return conflicts.sort((left, right) => severityRank[left.severity] - severityRank[right.severity]);
}

function findObjectiveValue(
  plan: SpatialOptimizationPlan,
  objectiveNames: string[],
  tokens: string[]
): number | null {
  const objectives = getPlanObjectiveValues(plan);
  const index = objectiveNames.findIndex((name) => {
    const normalized = String(name).toLowerCase();
    return tokens.some((token) => normalized.includes(token));
  });
  if (index < 0) return null;
  const value = objectives[index];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function buildPlanComparisonRows({
  plans,
  objectiveNames,
  targetMix,
  parcelFeatureById,
  badgesByPlan,
}: {
  plans: SpatialOptimizationPlan[];
  objectiveNames: string[];
  targetMix?: Partial<LandUseMixTargets> | Partial<Record<string, number>> | null;
  parcelFeatureById: ReadonlyMap<string, unknown>;
  badgesByPlan: Record<number, PlanBadge[]>;
}): PlanComparisonReportRow[] {
  return plans.slice(0, 10).map((plan, index) => {
    const assignments = getPlanAssignments(plan);
    const mix = calculateLandUseMix(assignments);
    return {
      planLabel: `Plan ${index + 1}`,
      badges: (badgesByPlan[index] ?? []).map((badge) => badge.label).join(', ') || 'None',
      residentialPercent: mix.residential.percentage,
      commercialPercent: mix.commercial.percentage,
      industrialPercent: mix.industrial.percentage,
      greenPercent: mix.green.percentage,
      targetDeviation: calculateTargetMixDeviation(mix, targetMix),
      highRiskBuiltCount: buildHighRiskBuiltParcels(assignments, parcelFeatureById).length,
      possibleZoningConflictCount: buildPossibleZoningConflictCount(assignments, parcelFeatureById),
      environmentalRiskObjective: findObjectiveValue(plan, objectiveNames, [
        'risk',
        'environment',
        'hazard',
      ]),
      zoningPenaltyObjective: findObjectiveValue(plan, objectiveNames, [
        'zoning',
        'violation',
        'compliance',
      ]),
      fragmentationPenaltyObjective: findObjectiveValue(plan, objectiveNames, [
        'fragment',
        'compact',
        'adjacency',
      ]),
    };
  });
}

export function getObjectiveMeaning(objectiveName: string): ObjectiveMeaning {
  const normalized = String(objectiveName || '').toLowerCase();
  if (normalized.includes('environment') || normalized.includes('risk')) {
    return {
      name: objectiveName,
      label: 'Environmental risk exposure',
      explanation:
        'Measures how much development is assigned to environmentally risky parcels. Lower is better.',
    };
  }
  if (normalized.includes('zoning') || normalized.includes('violation')) {
    return {
      name: objectiveName,
      label: 'Zoning violation penalty',
      explanation:
        'Measures possible mismatch between assigned land use and zoning/regulatory suitability. Lower is better.',
    };
  }
  if (normalized.includes('green') && normalized.includes('deviation')) {
    return {
      name: objectiveName,
      label: 'Green area deviation',
      explanation:
        'Measures how far the plan is from the requested green/open-space target. Lower is better.',
    };
  }
  if (normalized.includes('fragment') || normalized.includes('adjacency')) {
    return {
      name: objectiveName,
      label: 'Fragmentation penalty',
      explanation:
        'Measures whether similar land uses are scattered or spatially disconnected. Lower is better.',
    };
  }
  if (normalized.includes('balance') || normalized.includes('target_mix')) {
    return {
      name: objectiveName,
      label: 'Land use balance penalty',
      explanation:
        'Measures how far the actual land-use mix is from the requested target mix. Lower is better.',
    };
  }
  return {
    name: objectiveName,
    label: objectiveName.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase()),
    explanation:
      'Optimization objective returned by the spatial planning model. Lower values are generally treated as better unless otherwise specified.',
  };
}

function describeMainStrength(
  badges: PlanBadge[],
  mixRows: PlanReportMixRow[],
  metrics: PlanReportMetrics
): string {
  const badgeLabels = badges.map((badge) => badge.label);
  if (badgeLabels.includes('Safest Plan')) {
    return 'its comparatively low environmental risk exposure among generated alternatives';
  }
  if (badgeLabels.includes('Closest to Target Mix')) {
    return 'its close alignment with the requested land-use mix';
  }
  if (badgeLabels.includes('Greenest Plan')) {
    return 'its stronger green and conservation allocation';
  }
  if (badgeLabels.includes('Most Development-Friendly')) {
    return 'its stronger allocation toward built development uses';
  }
  const dominant = [...mixRows].sort((left, right) => right.actualPercent - left.actualPercent)[0];
  if (dominant) {
    return `its emphasis on ${dominant.label.toLowerCase()} (${dominant.actualPercent.toFixed(1)}%)`;
  }
  if (metrics.targetDeviation !== null) {
    return `a target mix deviation of ${metrics.targetDeviation.toFixed(1)} percentage points`;
  }
  return 'a complete generated assignment for the selected parcels';
}

function describeMainConcern(metrics: PlanReportMetrics): string {
  if ((metrics.highRiskBuiltCount ?? 0) > 0) {
    return `${metrics.highRiskBuiltCount} high-risk built-use parcel${metrics.highRiskBuiltCount === 1 ? '' : 's'} need review`;
  }
  if ((metrics.possibleZoningConflictCount ?? 0) > 0) {
    return `${metrics.possibleZoningConflictCount} possible zoning conflict${metrics.possibleZoningConflictCount === 1 ? '' : 's'} should be confirmed`;
  }
  if (metrics.targetDeviation !== null && metrics.targetDeviation > 20) {
    return 'the actual mix differs materially from the requested target mix';
  }
  return 'no major parcel-level warning was computable from the available frontend data';
}

export function buildSelectedPlanExplanation({
  planLabel,
  badges,
  metrics,
  mixRows,
}: {
  planLabel: string;
  badges: PlanBadge[];
  metrics: PlanReportMetrics;
  mixRows: PlanReportMixRow[];
}): string {
  const strength = describeMainStrength(badges, mixRows, metrics);
  const concern = describeMainConcern(metrics);
  const greenShare = mixRows.find((row) => row.use === 'green')?.actualPercent ?? 0;
  const builtShare = 100 - greenShare;
  return `${planLabel} performs well because it offers ${strength}. It allocates ${builtShare.toFixed(1)}% of parcels to built uses and ${greenShare.toFixed(1)}% to green/open space. The main planning concern is that ${concern}. Use this recommendation as a decision-support starting point, not a final regulatory decision.`;
}

export function buildExecutiveSummary({
  planLabel,
  badges,
  mixRows,
  metrics,
}: {
  planLabel: string;
  badges: PlanBadge[];
  mixRows: PlanReportMixRow[];
  metrics: PlanReportMetrics;
}): string {
  const primaryBadge = badges[0];
  const mixText = mixRows
    .map((row) => `${row.actualPercent.toFixed(0)}% ${row.label.toLowerCase()}`)
    .join(', ');
  const deviationText =
    metrics.targetDeviation === null
      ? 'Target mix alignment could not be computed because target settings were unavailable.'
      : metrics.targetDeviation <= 10
        ? `The plan is close to the target mix with ${metrics.targetDeviation.toFixed(1)} percentage points of total deviation.`
        : `The plan differs from the target mix by ${metrics.targetDeviation.toFixed(1)} percentage points.`;
  const badgeText = primaryBadge
    ? `${planLabel} is flagged as ${primaryBadge.label} because ${primaryBadge.description.toLowerCase()}`
    : `${planLabel} is a generated planning alternative for the selected parcels.`;
  return `${badgeText} It assigns ${mixText}. ${deviationText} Main strength: ${describeMainStrength(
    badges,
    mixRows,
    metrics
  )}. Main warning: ${describeMainConcern(metrics)}.`;
}

export function buildPlanReportSummary({
  selectedPlan,
  selectedPlanIndex,
  plans,
  objectiveNames,
  targetMix,
  parcelFeatureById,
  badgesByPlan,
}: {
  selectedPlan: SpatialOptimizationPlan;
  selectedPlanIndex: number;
  plans: SpatialOptimizationPlan[];
  objectiveNames: string[];
  targetMix?: Partial<LandUseMixTargets> | Partial<Record<string, number>> | null;
  parcelFeatureById: ReadonlyMap<string, unknown>;
  badgesByPlan: Record<number, PlanBadge[]>;
}): PlanReportSummary {
  const assignments = getPlanAssignments(selectedPlan);
  const mixStats = calculateLandUseMix(assignments);
  const mixRows = buildTargetMixRows(mixStats, targetMix);
  const targetDeviation = calculateTargetMixDeviation(mixStats, targetMix);
  const highRiskBuiltParcels = buildHighRiskBuiltParcels(assignments, parcelFeatureById);
  const possibleZoningConflictCount = buildPossibleZoningConflictCount(
    assignments,
    parcelFeatureById
  );
  const selectedObjectives = getPlanObjectiveValues(selectedPlan);
  const objectiveTotal =
    selectedObjectives.length > 0
      ? selectedObjectives.reduce((sum, value) => sum + (Number.isFinite(value) ? value : 0), 0)
      : null;
  const metrics: PlanReportMetrics = {
    totalAssigned: assignments.length,
    targetDeviation,
    highRiskBuiltCount: highRiskBuiltParcels.length,
    possibleZoningConflictCount,
    objectiveTotal,
  };
  const badges = badgesByPlan[selectedPlanIndex] ?? [];
  const planLabel = `Plan ${selectedPlanIndex + 1}`;

  return {
    mixRows,
    mixStats,
    metrics,
    conflicts: buildTopPlanConflicts(assignments, parcelFeatureById),
    highRiskBuiltParcels,
    planComparisonRows: buildPlanComparisonRows({
      plans,
      objectiveNames,
      targetMix,
      parcelFeatureById,
      badgesByPlan,
    }),
    executiveSummary: buildExecutiveSummary({ planLabel, badges, mixRows, metrics }),
    selectedPlanExplanation: buildSelectedPlanExplanation({ planLabel, badges, metrics, mixRows }),
    objectiveMeanings: objectiveNames.map(getObjectiveMeaning),
    targetMixAvailable: normalizeTargetMixPercent(targetMix) !== null,
  };
}

export async function capturePlanMapImage(element: HTMLElement | null): Promise<string | null> {
  if (!element) return null;
  try {
    const { default: html2canvas } = await import('html2canvas');
    const canvas = await html2canvas(element, {
  backgroundColor: '#ffffff',
  scale: 2,
  useCORS: true,
  onclone: (clonedDoc) => {
    clonedDoc.querySelectorAll('*').forEach((node) => {
      const el = node as HTMLElement;
      const computed = clonedDoc.defaultView?.getComputedStyle(el);

      if (!computed) return;

      const stylesToCheck = [
        'color',
        'backgroundColor',
        'borderColor',
        'outlineColor',
      ] as const;

      stylesToCheck.forEach((styleName) => {
        const value = computed[styleName];
        if (value && value.includes('oklch')) {
          if (styleName === 'backgroundColor') {
            el.style.backgroundColor = '#ffffff';
          } else {
            el.style[styleName] = '#1f2937';
          }
        }
      });
    });
  },
});
    return canvas.toDataURL('image/png', 0.92);
  } catch (error) {
    console.warn('[PlanReport] map capture failed', error);
    return null;
  }
}
