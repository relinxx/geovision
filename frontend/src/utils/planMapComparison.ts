import type { SpatialOptimizationPlan } from '../types';
import { getParcelRisk } from './planComparison';

export type PlanMapUse = 'residential' | 'commercial' | 'industrial' | 'green';

export type MapComparisonStatus =
  | 'unchanged'
  | 'built_to_green'
  | 'green_to_built'
  | 'built_to_built'
  | 'other_change'
  | 'missing';

export type RiskLevel = 'high' | 'medium' | 'low' | 'unknown';

export type PlanningImpact =
  | 'Likely improvement'
  | 'Potential concern'
  | 'Growth opportunity / needs zoning review'
  | 'Conservation shift'
  | 'Land-use priority shift'
  | 'Neutral / no change'
  | 'Needs review';

export type PlanComparisonFilter =
  | 'all'
  | 'changed'
  | 'green_to_built'
  | 'built_to_green'
  | 'built_to_built'
  | 'high_risk_changes'
  | 'potential_concerns';

export interface ParcelPlanComparison {
  parcelId: string;
  baselineUse: PlanMapUse | null;
  comparisonUse: PlanMapUse | null;
  status: MapComparisonStatus;
}

export interface PlanMapComparisonSummary {
  totalParcels: number;
  changedParcels: number;
  unchanged: number;
  builtToGreen: number;
  greenToBuilt: number;
  builtToBuilt: number;
  otherChange: number;
  missing: number;
  riskDataAvailable: boolean;
  highRiskImproved: number | null;
  highRiskWorsened: number | null;
}

export interface PlanComparisonLegendItem {
  status: MapComparisonStatus;
  label: string;
  description: string;
  color: string;
  fillColor: string;
  fillOpacity: number;
  changed: boolean;
}

export interface PlanComparisonPathStyle {
  color: string;
  weight: number;
  fillColor: string;
  fillOpacity: number;
}

export interface PlanComparisonTransition {
  fromUse: PlanMapUse;
  toUse: PlanMapUse;
  label: string;
  count: number;
}

const BUILT_USES = new Set<PlanMapUse>(['residential', 'commercial', 'industrial']);
const ASSIGNMENT_ARRAY_KEYS = ['assignments', 'assignment', 'parcel_assignments'];
const PARCEL_ID_KEYS = ['parcel_id', 'parcelId', 'apn', 'APN', 'id', 'parcel'];
const USE_KEYS = ['use_label', 'assigned_use', 'use', 'land_use', 'landUse', 'label'];

const USE_LABELS: Record<PlanMapUse, string> = {
  residential: 'Residential',
  commercial: 'Commercial',
  industrial: 'Industrial',
  green: 'Green/Open Space',
};

export const PLAN_COMPARISON_STYLES: Record<MapComparisonStatus, PlanComparisonPathStyle> = {
  unchanged: {
    color: '#64748b',
    weight: 0.4,
    fillColor: '#64748b',
    fillOpacity: 0.15,
  },
  built_to_green: {
    color: '#16a34a',
    weight: 1,
    fillColor: '#22c55e',
    fillOpacity: 0.65,
  },
  green_to_built: {
    color: '#dc2626',
    weight: 1,
    fillColor: '#ef4444',
    fillOpacity: 0.7,
  },
  built_to_built: {
    color: '#f97316',
    weight: 1,
    fillColor: '#fb923c',
    fillOpacity: 0.6,
  },
  other_change: {
    color: '#9333ea',
    weight: 1,
    fillColor: '#a855f7',
    fillOpacity: 0.55,
  },
  missing: {
    color: '#94a3b8',
    weight: 0.3,
    fillColor: '#94a3b8',
    fillOpacity: 0.08,
  },
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
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

function normalizeUseCode(value: unknown): PlanMapUse | null {
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric)) return null;
  if (numeric === 0) return 'residential';
  if (numeric === 1) return 'commercial';
  if (numeric === 2) return 'industrial';
  if (numeric === 3) return 'green';
  return null;
}

export function normalizeUse(value: unknown): PlanMapUse | null {
  const normalized = String(value ?? '')
    .trim()
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/[\s-]+/g, '_')
    .replace(/[^a-z0-9_]/g, '');

  if (!normalized) return null;

  if (
    normalized === 'res' ||
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
    normalized === 'com' ||
    normalized.includes('commercial') ||
    normalized.includes('retail') ||
    normalized.includes('office')
  ) {
    return 'commercial';
  }

  if (
    normalized === 'ind' ||
    normalized.includes('industrial') ||
    normalized.includes('warehouse') ||
    normalized.includes('manufacturing')
  ) {
    return 'industrial';
  }

  if (
    normalized === 'park' ||
    normalized.includes('green') ||
    normalized.includes('open_space') ||
    normalized.includes('conservation') ||
    normalized.includes('park') ||
    normalized.includes('agri')
  ) {
    return 'green';
  }

  return null;
}

function normalizeAssignmentEntry(entry: unknown): [string, PlanMapUse] | null {
  if (!isRecord(entry)) return null;
  const parcelId = String(firstNonEmptyValue(entry, PARCEL_ID_KEYS) ?? '').trim();
  const use =
    normalizeUse(firstNonEmptyValue(entry, USE_KEYS)) ?? normalizeUseCode(entry.use_code);

  if (!parcelId || !use) return null;
  return [parcelId, use];
}

export function buildAssignmentMap(plan: unknown): Map<string, PlanMapUse> {
  const assignmentMap = new Map<string, PlanMapUse>();
  if (!isRecord(plan)) return assignmentMap;

  for (const key of ASSIGNMENT_ARRAY_KEYS) {
    const value = plan[key];
    if (Array.isArray(value)) {
      for (const entry of value) {
        const normalized = normalizeAssignmentEntry(entry);
        if (normalized) {
          assignmentMap.set(normalized[0], normalized[1]);
        }
      }
      return assignmentMap;
    }
  }

  for (const key of ASSIGNMENT_ARRAY_KEYS) {
    const value = plan[key];
    if (!isRecord(value)) continue;
    for (const [parcelId, rawUse] of Object.entries(value)) {
      const use = normalizeUse(rawUse);
      const normalizedParcelId = parcelId.trim();
      if (normalizedParcelId && use) {
        assignmentMap.set(normalizedParcelId, use);
      }
    }
    return assignmentMap;
  }

  return assignmentMap;
}

export function classifyPlanChange(
  baselineUse: PlanMapUse | null | undefined,
  comparisonUse: PlanMapUse | null | undefined
): MapComparisonStatus {
  if (!baselineUse || !comparisonUse) return 'missing';
  if (baselineUse === comparisonUse) return 'unchanged';

  const baselineBuilt = BUILT_USES.has(baselineUse);
  const comparisonBuilt = BUILT_USES.has(comparisonUse);

  if (baselineBuilt && comparisonUse === 'green') return 'built_to_green';
  if (baselineUse === 'green' && comparisonBuilt) return 'green_to_built';
  if (baselineBuilt && comparisonBuilt) return 'built_to_built';
  return 'other_change';
}

export function comparePlanAssignments(
  baselinePlan: SpatialOptimizationPlan | unknown,
  comparisonPlan: SpatialOptimizationPlan | unknown
): Map<string, ParcelPlanComparison> {
  const baselineAssignments = buildAssignmentMap(baselinePlan);
  const comparisonAssignments = buildAssignmentMap(comparisonPlan);
  const parcelIds = new Set([...baselineAssignments.keys(), ...comparisonAssignments.keys()]);
  const result = new Map<string, ParcelPlanComparison>();

  for (const parcelId of parcelIds) {
    const baselineUse = baselineAssignments.get(parcelId) ?? null;
    const comparisonUse = comparisonAssignments.get(parcelId) ?? null;
    result.set(parcelId, {
      parcelId,
      baselineUse,
      comparisonUse,
      status: classifyPlanChange(baselineUse, comparisonUse),
    });
  }

  return result;
}

export function summarizePlanComparison(
  comparisonMap: Map<string, ParcelPlanComparison>,
  parcelFeatureById?: ReadonlyMap<string, unknown>
): PlanMapComparisonSummary {
  const summary: PlanMapComparisonSummary = {
    totalParcels: comparisonMap.size,
    changedParcels: 0,
    unchanged: 0,
    builtToGreen: 0,
    greenToBuilt: 0,
    builtToBuilt: 0,
    otherChange: 0,
    missing: 0,
    riskDataAvailable: false,
    highRiskImproved: null,
    highRiskWorsened: null,
  };

  let highRiskImproved = 0;
  let highRiskWorsened = 0;

  for (const comparison of comparisonMap.values()) {
    if (comparison.status === 'unchanged') {
      summary.unchanged += 1;
    } else {
      summary.changedParcels += 1;
    }

    if (comparison.status === 'built_to_green') summary.builtToGreen += 1;
    if (comparison.status === 'green_to_built') summary.greenToBuilt += 1;
    if (comparison.status === 'built_to_built') summary.builtToBuilt += 1;
    if (comparison.status === 'other_change') summary.otherChange += 1;
    if (comparison.status === 'missing') summary.missing += 1;

    const risk = parcelFeatureById ? getParcelRisk(parcelFeatureById.get(comparison.parcelId)) : null;
    if (risk !== null) {
      summary.riskDataAvailable = true;
      if (risk >= 0.7 && comparison.status === 'built_to_green') {
        highRiskImproved += 1;
      }
      if (risk >= 0.7 && comparison.status === 'green_to_built') {
        highRiskWorsened += 1;
      }
    }
  }

  if (summary.riskDataAvailable) {
    summary.highRiskImproved = highRiskImproved;
    summary.highRiskWorsened = highRiskWorsened;
  }

  return summary;
}

function normalizeRiskValue(riskValue: number | null | undefined): number | null {
  if (typeof riskValue !== 'number' || !Number.isFinite(riskValue) || riskValue < 0) {
    return null;
  }
  if (riskValue <= 1) return riskValue;
  if (riskValue <= 100) return riskValue / 100;
  return null;
}

export function classifyRiskLevel(riskValue: number | null | undefined): RiskLevel {
  const normalizedRisk = normalizeRiskValue(riskValue);
  if (normalizedRisk === null) return 'unknown';
  if (normalizedRisk >= 0.7) return 'high';
  if (normalizedRisk >= 0.4) return 'medium';
  return 'low';
}

export function getRiskLabel(riskValue: number | null | undefined): string {
  const riskLevel = classifyRiskLevel(riskValue);
  if (riskLevel === 'high') return 'High risk';
  if (riskLevel === 'medium') return 'Medium risk';
  if (riskLevel === 'low') return 'Low risk';
  return 'risk data unavailable';
}

export function formatRiskScore(riskValue: number | null | undefined): string {
  const normalizedRisk = normalizeRiskValue(riskValue);
  if (normalizedRisk === null) return 'N/A - risk data unavailable';
  return `${Math.round(normalizedRisk * 100)}% - ${getRiskLabel(normalizedRisk)}`;
}

export function formatPlanUseLabel(value: PlanMapUse | null | undefined): string {
  if (!value) return 'Missing';
  return USE_LABELS[value];
}

export function getPlanningImpact(
  status: MapComparisonStatus,
  _baselineUse?: PlanMapUse | null,
  _comparisonUse?: PlanMapUse | null,
  riskValue?: number | null
): PlanningImpact {
  const riskLevel = classifyRiskLevel(riskValue);

  if (status === 'built_to_green') {
    return riskLevel === 'high' ? 'Likely improvement' : 'Conservation shift';
  }
  if (status === 'green_to_built') {
    if (riskLevel === 'high') return 'Potential concern';
    if (riskLevel === 'medium') return 'Needs review';
    if (riskLevel === 'low') return 'Growth opportunity / needs zoning review';
    return 'Needs review';
  }
  if (status === 'built_to_built') return 'Land-use priority shift';
  if (status === 'unchanged') return 'Neutral / no change';
  return 'Needs review';
}

export function shouldEmphasizeComparisonParcel(
  comparison: ParcelPlanComparison | null | undefined,
  filter: PlanComparisonFilter,
  parcelFeature?: unknown
): boolean {
  if (!comparison) return filter === 'all';
  if (filter === 'all') return true;
  if (filter === 'changed') return comparison.status !== 'unchanged' && comparison.status !== 'missing';
  if (
    filter === 'green_to_built' ||
    filter === 'built_to_green' ||
    filter === 'built_to_built'
  ) {
    return comparison.status === filter;
  }
  if (filter === 'high_risk_changes') {
    return (
      comparison.status !== 'unchanged' &&
      comparison.status !== 'missing' &&
      classifyRiskLevel(getParcelRisk(parcelFeature)) === 'high'
    );
  }
  if (filter === 'potential_concerns') {
    const impact = getPlanningImpact(
      comparison.status,
      comparison.baselineUse,
      comparison.comparisonUse,
      getParcelRisk(parcelFeature)
    );
    return impact === 'Potential concern' || impact === 'Needs review';
  }
  return true;
}

export function calculateTransitionBreakdown(
  comparisonMap: Map<string, ParcelPlanComparison>
): PlanComparisonTransition[] {
  const transitionMap = new Map<string, PlanComparisonTransition>();

  for (const comparison of comparisonMap.values()) {
    const { baselineUse, comparisonUse } = comparison;
    if (!baselineUse || !comparisonUse || baselineUse === comparisonUse) continue;
    const key = `${baselineUse}->${comparisonUse}`;
    const existing = transitionMap.get(key);
    if (existing) {
      existing.count += 1;
    } else {
      transitionMap.set(key, {
        fromUse: baselineUse,
        toUse: comparisonUse,
        label: `${formatPlanUseLabel(baselineUse)} -> ${formatPlanUseLabel(comparisonUse)}`,
        count: 1,
      });
    }
  }

  return [...transitionMap.values()].sort((a, b) => {
    if (b.count !== a.count) return b.count - a.count;
    return a.label.localeCompare(b.label);
  });
}

export function generatePlanComparisonNarrative(
  summary: PlanMapComparisonSummary,
  baselineLabel: string,
  comparisonLabel: string,
  transitions: PlanComparisonTransition[] = []
): string {
  const total = summary.totalParcels;
  const changed = summary.changedParcels;
  const pieces = [
    `${comparisonLabel} changes ${changed.toLocaleString()} out of ${total.toLocaleString()} parcels compared with ${baselineLabel}.`,
  ];

  const largestTransition = transitions[0];
  if (largestTransition) {
    pieces.push(
      `The largest exact transition is ${largestTransition.label.toLowerCase()}, affecting ${largestTransition.count.toLocaleString()} parcel${largestTransition.count === 1 ? '' : 's'}.`
    );
  }

  if (summary.greenToBuilt > summary.builtToGreen) {
    pieces.push('The comparison plan shifts more land toward development.');
  } else if (summary.builtToGreen > summary.greenToBuilt) {
    pieces.push('The comparison plan shifts more land toward conservation or open space.');
  } else if (summary.builtToBuilt > 0) {
    pieces.push('Most visible changes are between built-use priorities rather than between development and open space.');
  }

  if (summary.riskDataAvailable) {
    if ((summary.highRiskWorsened ?? 0) > 0) {
      pieces.push(
        `${summary.highRiskWorsened?.toLocaleString()} high-risk parcel${summary.highRiskWorsened === 1 ? '' : 's'} moved from green/open space toward a built use, so those changes deserve review.`
      );
    } else if ((summary.highRiskImproved ?? 0) > 0) {
      pieces.push('No high-risk parcels worsened, and the comparison plan reduces development exposure on some risky parcels.');
    } else {
      pieces.push('No high-risk parcels worsened in the available risk data.');
    }
  }

  pieces.push('Zoning and policy review is still recommended before approval.');
  return pieces.join(' ');
}

export function getComparisonLegendItems(): PlanComparisonLegendItem[] {
  return [
    {
      status: 'unchanged',
      label: 'Unchanged',
      description: 'Parcel assignment stayed the same.',
      changed: false,
      ...PLAN_COMPARISON_STYLES.unchanged,
    },
    {
      status: 'built_to_green',
      label: 'Built -> Green',
      description: 'Development allocation changed to green/open space.',
      changed: true,
      ...PLAN_COMPARISON_STYLES.built_to_green,
    },
    {
      status: 'green_to_built',
      label: 'Green -> Built',
      description: 'Green/open space changed to a built land use.',
      changed: true,
      ...PLAN_COMPARISON_STYLES.green_to_built,
    },
    {
      status: 'built_to_built',
      label: 'Built -> Built',
      description: 'Built land-use category changed.',
      changed: true,
      ...PLAN_COMPARISON_STYLES.built_to_built,
    },
    {
      status: 'other_change',
      label: 'Other Change',
      description: 'Assignment changed outside the core built/green categories.',
      changed: true,
      ...PLAN_COMPARISON_STYLES.other_change,
    },
    {
      status: 'missing',
      label: 'Missing Assignment',
      description: 'Assignment is missing in one of the selected plans.',
      changed: false,
      ...PLAN_COMPARISON_STYLES.missing,
    },
  ];
}

export function getPlannerInterpretation(comparison?: ParcelPlanComparison | null): string {
  return getRiskSensitivePlannerInterpretation(comparison);
}

export function getRiskSensitivePlannerInterpretation(
  comparison?: ParcelPlanComparison | null,
  riskValue?: number | null
): string {
  if (!comparison) return 'Select a changed parcel to review the assignment difference.';

  const baselineUse = formatPlanUseLabel(comparison.baselineUse).toLowerCase();
  const comparisonUse = formatPlanUseLabel(comparison.comparisonUse).toLowerCase();
  const riskLevel = classifyRiskLevel(riskValue);

  if (comparison.status === 'built_to_green') {
    if (riskLevel === 'high') {
      return `This parcel changed from ${baselineUse} to green/open space. Because environmental risk is high, this is likely an improvement because it reduces development exposure on risky land.`;
    }
    return `This parcel changed from ${baselineUse} to green/open space. This may support conservation or open-space goals, but review whether the parcel is also suitable for planned growth.`;
  }
  if (comparison.status === 'green_to_built') {
    if (riskLevel === 'low') {
      return `This parcel changed from green/open space to ${comparisonUse}. Because environmental risk is low, the change may be acceptable from an environmental perspective. Review zoning compatibility and whether the parcel was intentionally preserved as open space before approving it.`;
    }
    if (riskLevel === 'medium') {
      return `This parcel changed from green/open space to ${comparisonUse}. Environmental risk is moderate, so this change should be reviewed before approval. Check hazard flags, zoning compatibility, and whether the growth allocation is necessary.`;
    }
    if (riskLevel === 'high') {
      return `This parcel changed from green/open space to ${comparisonUse} on a high-risk parcel. This may increase exposure to environmental hazards and should be reviewed carefully before accepting the plan.`;
    }
    return `This parcel changed from green/open space to ${comparisonUse}. Review environmental risk, zoning compatibility, and whether the parcel was intentionally preserved as open space before approving it.`;
  }
  if (comparison.status === 'built_to_built') {
    return `This parcel changed from ${baselineUse} to ${comparisonUse}, meaning the plan shifts this parcel from one development priority to another. Review suitability, zoning, and target mix before deciding which assignment is better.`;
  }
  if (comparison.status === 'unchanged') {
    return 'This parcel has the same assignment in both selected plans.';
  }
  if (comparison.status === 'missing') {
    return 'This parcel is missing an assignment in one of the selected plans, so it should be reviewed before comparison.';
  }
  return 'This parcel changed between the selected plans and may need planner review.';
}
