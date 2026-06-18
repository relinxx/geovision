import { useMemo } from 'react';
import type { LandUseMixTargets, SpatialOptimizationPlan } from '../../types';
import {
  calculatePlanComparisonMetrics,
  type ComparisonLandUse,
  type PlanComparisonMetrics,
} from '../../utils/planComparison';
import './PlanComparisonDashboard.css';

export interface SelectedPlanComparisonItem {
  plan: SpatialOptimizationPlan;
  planIndex: number;
}

interface PlanComparisonDashboardProps {
  selectedPlans: SelectedPlanComparisonItem[];
  objectiveNames: string[];
  parcelFeatureById: ReadonlyMap<string, unknown>;
  targetMix?: Partial<LandUseMixTargets> | Partial<Record<string, number>> | null;
}

interface ComputedPlanComparisonItem extends SelectedPlanComparisonItem {
  metrics: PlanComparisonMetrics;
}

type NullableMetricGetter = (item: ComputedPlanComparisonItem) => number | null;

const LAND_USE_LABELS: Record<ComparisonLandUse, string> = {
  residential: 'Residential',
  commercial: 'Commercial',
  industrial: 'Industrial',
  green: 'Green',
};

const LAND_USE_ORDER: ComparisonLandUse[] = ['residential', 'commercial', 'industrial', 'green'];

function formatObjectiveName(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return 'N/A';
  return `${(value * 100).toFixed(1)}%`;
}

function formatPoints(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return 'N/A';
  return `${value.toFixed(1)} pts`;
}

function formatCount(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return 'N/A';
  return value.toLocaleString();
}

function getLowestMetricWinners(
  items: ComputedPlanComparisonItem[],
  getter: NullableMetricGetter
): Set<number> {
  const values = items
    .map((item, index) => ({ index, value: getter(item) }))
    .filter(
      (entry): entry is { index: number; value: number } =>
        typeof entry.value === 'number' && Number.isFinite(entry.value)
    );

  if (values.length < 2) return new Set();

  const min = Math.min(...values.map((entry) => entry.value));
  const max = Math.max(...values.map((entry) => entry.value));
  if (max - min <= 1e-9) return new Set();

  return new Set(values.filter((entry) => entry.value <= min + 1e-9).map((entry) => entry.index));
}

function metricClassName(isBest: boolean): string {
  return `plan-comparison-metric${isBest ? ' plan-comparison-metric--best' : ''}`;
}

export function PlanComparisonDashboard({
  selectedPlans,
  objectiveNames,
  parcelFeatureById,
  targetMix,
}: PlanComparisonDashboardProps) {
  const comparedPlans = useMemo<ComputedPlanComparisonItem[]>(
    () =>
      selectedPlans.map((item) => ({
        ...item,
        metrics: calculatePlanComparisonMetrics({
          plan: item.plan,
          parcelFeatureById,
          targetMix,
        }),
      })),
    [parcelFeatureById, selectedPlans, targetMix]
  );

  const bestMetrics = useMemo(
    () => ({
      averageRisk: getLowestMetricWinners(
        comparedPlans,
        (item) => item.metrics.averageRisk.value
      ),
      highRiskBuiltUse: getLowestMetricWinners(
        comparedPlans,
        (item) => item.metrics.highRiskBuiltUseCount
      ),
      zoningConflicts: getLowestMetricWinners(
        comparedPlans,
        (item) => item.metrics.zoningConflictCount
      ),
      targetDeviation: getLowestMetricWinners(
        comparedPlans,
        (item) => item.metrics.targetMixDeviation
      ),
      fragmentation: getLowestMetricWinners(
        comparedPlans,
        (item) => item.metrics.fragmentationScore?.value ?? null
      ),
    }),
    [comparedPlans]
  );

  if (comparedPlans.length < 2) {
    return (
      <section className="plan-comparison-dashboard">
        <h2 className="plan-comparison-dashboard__title">Plan Comparison</h2>
        <p className="plan-comparison-dashboard__description">
          Select 2 to 3 generated plans to compare planning metrics.
        </p>
      </section>
    );
  }

  return (
    <section className="plan-comparison-dashboard">
      <div className="plan-comparison-dashboard__header">
        <div>
          <h2 className="plan-comparison-dashboard__title">Plan Comparison</h2>
          <p className="plan-comparison-dashboard__description">
            Compare selected alternatives across land-use mix, risk, zoning, and target alignment.
          </p>
        </div>
        <span className="plan-comparison-dashboard__count">{comparedPlans.length}/3</span>
      </div>

      <div className="plan-comparison-dashboard__grid">
        {comparedPlans.map((item, index) => {
          const { metrics, plan, planIndex } = item;
          const fragmentation = metrics.fragmentationScore;

          return (
            <article key={`selected-plan-${planIndex}`} className="plan-comparison-plan">
              <div className="plan-comparison-plan__header">
                <h3>Plan {planIndex + 1}</h3>
                <span>Rank {plan.rank}</span>
              </div>

              {metrics.assignments.length === 0 ? (
                <p className="plan-comparison-plan__empty">No assignments available.</p>
              ) : (
                <>
                  <div className="plan-comparison-mix">
                    {LAND_USE_ORDER.map((use) => {
                      const mix = metrics.landUseMix[use];
                      return (
                        <div key={use} className={`plan-comparison-mix__row plan-comparison-mix__row--${use}`}>
                          <span>{LAND_USE_LABELS[use]}</span>
                          <strong>
                            {mix.percentage.toFixed(1)}% ({mix.count})
                          </strong>
                        </div>
                      );
                    })}
                  </div>

                  <div className="plan-comparison-metrics">
                    <div
                      className={metricClassName(bestMetrics.averageRisk.has(index))}
                      title={
                        metrics.averageRisk.value === null
                          ? 'No environmental risk fields were found for this plan.'
                          : `Average across ${metrics.averageRisk.observedCount} parcels with risk data.`
                      }
                    >
                      <span>Average risk</span>
                      <strong>{formatPercent(metrics.averageRisk.value)}</strong>
                    </div>
                    <div
                      className={metricClassName(bestMetrics.highRiskBuiltUse.has(index))}
                      title="Built-use parcels with normalized environmental risk of 70% or higher."
                    >
                      <span>High-risk built uses</span>
                      <strong>{formatCount(metrics.highRiskBuiltUseCount)}</strong>
                    </div>
                    <div
                      className={metricClassName(bestMetrics.zoningConflicts.has(index))}
                      title={
                        metrics.zoningConflictCount === null
                          ? 'No reliable zoning compatibility fields were found.'
                          : 'Assignments that conflict with available zoning compatibility data.'
                      }
                    >
                      <span>Zoning conflicts</span>
                      <strong>{formatCount(metrics.zoningConflictCount)}</strong>
                    </div>
                    <div
                      className={metricClassName(bestMetrics.targetDeviation.has(index))}
                      title={
                        metrics.targetMixDeviation === null
                          ? 'No target mix is available for this optimization result.'
                          : 'Total absolute difference from target mix in percentage points.'
                      }
                    >
                      <span>Target deviation</span>
                      <strong>{formatPoints(metrics.targetMixDeviation)}</strong>
                    </div>
                    <div
                      className={metricClassName(bestMetrics.fragmentation.has(index))}
                      title={
                        fragmentation === null
                          ? 'Fragmentation requires parcel adjacency data.'
                          : 'Share of known neighboring parcel pairs assigned to different uses.'
                      }
                    >
                      <span>Fragmentation</span>
                      <strong>
                        {fragmentation === null
                          ? 'N/A'
                          : `${(fragmentation.value * 100).toFixed(1)}% (${fragmentation.boundaryCount}/${fragmentation.edgeCount})`}
                      </strong>
                    </div>
                  </div>

                  {plan.objectives.length > 0 && (
                    <div className="plan-comparison-objectives">
                      <div className="plan-comparison-objectives__title">Optimization Objectives</div>
                      {plan.objectives.map((value, objectiveIndex) => {
                        const objectiveName =
                          objectiveNames[objectiveIndex] ?? `objective_${objectiveIndex}`;
                        return (
                          <div key={`${planIndex}-${objectiveIndex}`} className="plan-comparison-objective">
                            <span>{formatObjectiveName(objectiveName)}</span>
                            <strong>{Number.isFinite(value) ? value.toFixed(4) : 'N/A'}</strong>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
