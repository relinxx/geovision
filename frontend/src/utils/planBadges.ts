export type PlanBadgeVariant = 'success' | 'warning' | 'info' | 'neutral';

export interface PlanBadge {
  label: string;
  description: string;
  variant?: PlanBadgeVariant;
}

interface PlanAssignmentLike {
  use_label?: unknown;
}

interface PlanLike {
  objectives?: unknown;
  assignments?: PlanAssignmentLike[];
}

interface BadgeCandidate extends PlanBadge {
  priority: number;
}

export interface GetPlanBadgesParams {
  plans: PlanLike[];
  objectiveNames?: string[];
  targetMix?: Partial<Record<string, number>> | null;
}

const MAX_BADGES_PER_PLAN = 3;
const BUILT_USE_LABELS = new Set(['residential', 'commercial', 'industrial', 'mixed_use']);
const GREEN_USE_LABELS = new Set(['green', 'open_space', 'conservation', 'park', 'parks']);

const BADGES = {
  overall: {
    label: 'Best Overall Tradeoff',
    description: 'Best normalized balance across available objectives.',
    variant: 'success' as const,
    priority: 0,
  },
  risk: {
    label: 'Safest Plan',
    description: 'Lowest environmental risk exposure among generated plans.',
    variant: 'success' as const,
    priority: 1,
  },
  targetMix: {
    label: 'Closest to Target Mix',
    description: 'Most closely matches the requested land-use mix.',
    variant: 'info' as const,
    priority: 2,
  },
  zoning: {
    label: 'Best Zoning Compliance',
    description: 'Lowest zoning violation penalty among generated plans.',
    variant: 'info' as const,
    priority: 3,
  },
  compact: {
    label: 'Most Compact / Least Fragmented',
    description: 'Lowest fragmentation or adjacency penalty.',
    variant: 'neutral' as const,
    priority: 4,
  },
  green: {
    label: 'Greenest Plan',
    description: 'Highest share of green/conservation assignments.',
    variant: 'success' as const,
    priority: 5,
  },
  development: {
    label: 'Most Development-Friendly',
    description: 'Highest share of built-use assignments.',
    variant: 'warning' as const,
    priority: 6,
  },
};

function normalizeUseLabel(value: unknown): string {
  return String(value ?? '')
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_');
}

function getAssignments(plan: PlanLike): PlanAssignmentLike[] {
  return Array.isArray(plan.assignments) ? plan.assignments : [];
}

function getObjectiveValues(plan: PlanLike): number[] {
  return Array.isArray(plan.objectives)
    ? plan.objectives.map((value) => Number(value))
    : [];
}

function findObjectiveIndex(objectiveNames: string[] | undefined, tokens: string[]): number {
  if (!Array.isArray(objectiveNames)) return -1;
  return objectiveNames.findIndex((name) => {
    const normalized = String(name || '').toLowerCase();
    return tokens.some((token) => normalized.includes(token));
  });
}

function getObjectiveSeries(plans: PlanLike[], objectiveIndex: number): Array<number | null> {
  return plans.map((plan) => {
    const value = getObjectiveValues(plan)[objectiveIndex];
    return Number.isFinite(value) ? value : null;
  });
}

function normalizeTargetMix(
  targetMix?: Partial<Record<string, number>> | null
): Record<string, number> | null {
  if (!targetMix || typeof targetMix !== 'object') return null;
  const entries = Object.entries(targetMix)
    .map(([rawKey, rawValue]) => [normalizeUseLabel(rawKey), Number(rawValue)] as const)
    .filter(([, value]) => Number.isFinite(value) && value >= 0);
  const total = entries.reduce((sum, [, value]) => sum + value, 0);
  if (total <= 0) return null;
  return Object.fromEntries(entries.map(([key, value]) => [key, value / total]));
}

function computeUseShares(plan: PlanLike): Record<string, number> {
  const assignments = getAssignments(plan);
  if (assignments.length === 0) return {};

  const counts = new Map<string, number>();
  for (const assignment of assignments) {
    const label = normalizeUseLabel(assignment.use_label);
    if (!label) continue;
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }

  const total = Math.max(1, assignments.length);
  return Object.fromEntries(
    Array.from(counts.entries()).map(([label, count]) => [label, count / total])
  );
}

function computeTargetMixDeviation(
  plan: PlanLike,
  targetMix?: Partial<Record<string, number>> | null
): number | null {
  const normalizedTarget = normalizeTargetMix(targetMix);
  if (!normalizedTarget) return null;

  const shares = computeUseShares(plan);
  let deviation = 0;
  const labels = new Set([...Object.keys(normalizedTarget), ...Object.keys(shares)]);
  for (const label of labels) {
    deviation += Math.abs((shares[label] ?? 0) - (normalizedTarget[label] ?? 0));
  }
  return Number.isFinite(deviation) ? deviation : null;
}

function computeGreenShare(plan: PlanLike): number | null {
  const assignments = getAssignments(plan);
  if (assignments.length === 0) return null;
  const greenCount = assignments.filter((assignment) =>
    GREEN_USE_LABELS.has(normalizeUseLabel(assignment.use_label))
  ).length;
  return greenCount / assignments.length;
}

function computeBuiltUseShare(plan: PlanLike): number | null {
  const assignments = getAssignments(plan);
  if (assignments.length === 0) return null;
  const builtCount = assignments.filter((assignment) =>
    BUILT_USE_LABELS.has(normalizeUseLabel(assignment.use_label))
  ).length;
  return builtCount / assignments.length;
}

function finiteValues(values: Array<number | null>): number[] {
  return values.filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
}

function hasMeaningfulSpread(values: Array<number | null>): boolean {
  const finite = finiteValues(values);
  if (finite.length < 2) return false;
  return Math.max(...finite) - Math.min(...finite) > 1e-9;
}

function winnerIndexes(
  values: Array<number | null>,
  direction: 'min' | 'max',
  allowTies = true
): number[] {
  const finite = finiteValues(values);
  if (finite.length === 0 || !hasMeaningfulSpread(values)) return [];

  const best = direction === 'min' ? Math.min(...finite) : Math.max(...finite);
  const tolerance = allowTies ? Math.max(Math.abs(best) * 0.02, 1e-9) : 1e-9;

  return values
    .map((value, index) => ({ value, index }))
    .filter(({ value }) => {
      if (typeof value !== 'number' || !Number.isFinite(value)) return false;
      return direction === 'min'
        ? value <= best + tolerance
        : value >= best - tolerance;
    })
    .map(({ index }) => index);
}

function normalizeLowerIsBetter(values: Array<number | null>): Array<number | null> {
  const finite = finiteValues(values);
  if (finite.length === 0) return values.map(() => null);
  const min = Math.min(...finite);
  const max = Math.max(...finite);
  const range = max - min;
  if (range <= 1e-9) return values.map((value) => (value === null ? null : 0));

  return values.map((value) => {
    if (typeof value !== 'number' || !Number.isFinite(value)) return null;
    return (value - min) / range;
  });
}

function addBadge(
  badgesByPlan: Map<number, BadgeCandidate[]>,
  planIndex: number,
  badge: BadgeCandidate
) {
  const existing = badgesByPlan.get(planIndex) ?? [];
  if (existing.some((entry) => entry.label === badge.label)) return;
  existing.push(badge);
  badgesByPlan.set(planIndex, existing);
}

export function getPlanBadges({
  plans,
  objectiveNames,
  targetMix,
}: GetPlanBadgesParams): Record<number, PlanBadge[]> {
  const safePlans = Array.isArray(plans) ? plans : [];
  const badgesByPlan = new Map<number, BadgeCandidate[]>();
  if (safePlans.length === 0) return {};

  const riskIndex = findObjectiveIndex(objectiveNames, ['risk', 'environment', 'hazard']);
  const zoningIndex = findObjectiveIndex(objectiveNames, ['zoning', 'violation', 'compliance']);
  const compactIndex = findObjectiveIndex(objectiveNames, ['fragment', 'compact', 'adjacency']);

  const riskValues = riskIndex >= 0 ? getObjectiveSeries(safePlans, riskIndex) : [];
  const zoningValues = zoningIndex >= 0 ? getObjectiveSeries(safePlans, zoningIndex) : [];
  const compactValues = compactIndex >= 0 ? getObjectiveSeries(safePlans, compactIndex) : [];
  const targetMixDeviations = safePlans.map((plan) => computeTargetMixDeviation(plan, targetMix));
  const greenShares = safePlans.map(computeGreenShare);
  const builtShares = safePlans.map(computeBuiltUseShare);

  const objectiveCount = Math.max(
    Array.isArray(objectiveNames) ? objectiveNames.length : 0,
    ...safePlans.map((plan) => getObjectiveValues(plan).length)
  );
  const objectiveSeries = Array.from({ length: objectiveCount }, (_, index) =>
    getObjectiveSeries(safePlans, index)
  );
  const normalizedSeries = objectiveSeries
    .filter(hasMeaningfulSpread)
    .map(normalizeLowerIsBetter);

  if (hasMeaningfulSpread(targetMixDeviations)) {
    normalizedSeries.push(normalizeLowerIsBetter(targetMixDeviations));
  }

  const overallScores = safePlans.map((_, planIndex) => {
    const values = normalizedSeries
      .map((series) => series[planIndex])
      .filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
    if (values.length === 0) return null;
    return values.reduce((sum, value) => sum + value, 0) / values.length;
  });

  for (const index of winnerIndexes(overallScores, 'min', false)) {
    addBadge(badgesByPlan, index, BADGES.overall);
  }
  for (const index of winnerIndexes(riskValues, 'min')) {
    addBadge(badgesByPlan, index, BADGES.risk);
  }
  for (const index of winnerIndexes(targetMixDeviations, 'min')) {
    addBadge(badgesByPlan, index, BADGES.targetMix);
  }
  for (const index of winnerIndexes(zoningValues, 'min')) {
    addBadge(badgesByPlan, index, BADGES.zoning);
  }
  for (const index of winnerIndexes(compactValues, 'min')) {
    addBadge(badgesByPlan, index, BADGES.compact);
  }
  for (const index of winnerIndexes(greenShares, 'max')) {
    addBadge(badgesByPlan, index, BADGES.green);
  }

  const worstRiskWinners = riskValues.length > 0 ? winnerIndexes(riskValues, 'max') : [];
  for (const index of winnerIndexes(builtShares, 'max')) {
    if (worstRiskWinners.includes(index)) continue;
    addBadge(badgesByPlan, index, BADGES.development);
  }

  return Object.fromEntries(
    safePlans.map((_, index) => [
      index,
      (badgesByPlan.get(index) ?? [])
        .sort((left, right) => left.priority - right.priority)
        .slice(0, MAX_BADGES_PER_PLAN)
        .map(({ priority, ...badge }) => badge),
    ])
  );
}
