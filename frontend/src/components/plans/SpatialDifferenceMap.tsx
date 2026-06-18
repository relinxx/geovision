import { useEffect, useMemo, useState } from 'react';
import { ParcelMap } from '../map/ParcelMap';
import type { ParcelSuitabilityScores } from '../../types';
import type { SelectedPlanComparisonItem } from './PlanComparisonDashboard';
import {
  calculateTransitionBreakdown,
  comparePlanAssignments,
  formatPlanUseLabel,
  formatRiskScore,
  generatePlanComparisonNarrative,
  getComparisonLegendItems,
  getPlanningImpact,
  getRiskSensitivePlannerInterpretation,
  summarizePlanComparison,
  type ParcelPlanComparison,
  type PlanComparisonFilter,
} from '../../utils/planMapComparison';
import { getParcelRisk } from '../../utils/planComparison';
import './SpatialDifferenceMap.css';

interface SpatialDifferenceMapProps {
  selectedPlans: SelectedPlanComparisonItem[];
  parcelFeatureById: ReadonlyMap<string, unknown>;
  geoJsonUrl: string;
}

interface SelectedComparisonParcel {
  parcelId: string;
  comparison: ParcelPlanComparison | null;
  risk: number | null;
}

const EMPTY_SCORES = new Map<string, ParcelSuitabilityScores>();

function formatCount(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return 'N/A';
  return value.toLocaleString();
}

const REVIEW_FILTER_OPTIONS: Array<{ value: PlanComparisonFilter; label: string }> = [
  { value: 'all', label: 'All parcels' },
  { value: 'changed', label: 'Changed parcels only' },
  { value: 'green_to_built', label: 'Green -> Built' },
  { value: 'built_to_green', label: 'Built -> Green' },
  { value: 'built_to_built', label: 'Built -> Built' },
  { value: 'high_risk_changes', label: 'High-risk changes' },
  { value: 'potential_concerns', label: 'Potential concerns' },
];

function findPlanByIndex(
  selectedPlans: SelectedPlanComparisonItem[],
  planIndex: number
): SelectedPlanComparisonItem | null {
  return selectedPlans.find((item) => item.planIndex === planIndex) ?? null;
}

export function SpatialDifferenceMap({
  selectedPlans,
  parcelFeatureById,
  geoJsonUrl,
}: SpatialDifferenceMapProps) {
  const [baselinePlanIndex, setBaselinePlanIndex] = useState<number | null>(null);
  const [comparisonPlanIndex, setComparisonPlanIndex] = useState<number | null>(null);
  const [reviewFilter, setReviewFilter] = useState<PlanComparisonFilter>('all');
  const [selectedParcel, setSelectedParcel] = useState<SelectedComparisonParcel | null>(null);

  const selectedPlanIndexes = useMemo(
    () => selectedPlans.map((item) => item.planIndex),
    [selectedPlans]
  );
  const selectedPlanKey = selectedPlanIndexes.join('|');

  useEffect(() => {
    if (selectedPlans.length < 2) {
      setBaselinePlanIndex(null);
      setComparisonPlanIndex(null);
      setSelectedParcel(null);
      return;
    }

    const currentBaseline = selectedPlanIndexes.includes(baselinePlanIndex ?? -1)
      ? baselinePlanIndex
      : selectedPlans[0].planIndex;
    const currentComparison =
      selectedPlanIndexes.includes(comparisonPlanIndex ?? -1) &&
      comparisonPlanIndex !== currentBaseline
        ? comparisonPlanIndex
        : selectedPlans.find((item) => item.planIndex !== currentBaseline)?.planIndex ?? selectedPlans[1].planIndex;

    setBaselinePlanIndex(currentBaseline);
    setComparisonPlanIndex(currentComparison);
    setSelectedParcel(null);
  }, [baselinePlanIndex, comparisonPlanIndex, selectedPlanIndexes, selectedPlanKey, selectedPlans]);

  const baselinePlan =
    baselinePlanIndex === null
      ? selectedPlans[0] ?? null
      : findPlanByIndex(selectedPlans, baselinePlanIndex) ?? selectedPlans[0] ?? null;
  const comparisonPlan =
    comparisonPlanIndex === null
      ? selectedPlans.find((item) => item.planIndex !== baselinePlan?.planIndex) ?? null
      : findPlanByIndex(selectedPlans, comparisonPlanIndex) ??
        selectedPlans.find((item) => item.planIndex !== baselinePlan?.planIndex) ??
        null;

  const comparisonMap = useMemo(() => {
    if (!baselinePlan || !comparisonPlan) {
      return new Map<string, ParcelPlanComparison>();
    }
    return comparePlanAssignments(baselinePlan.plan, comparisonPlan.plan);
  }, [baselinePlan, comparisonPlan]);

  const comparisonSummary = useMemo(
    () => summarizePlanComparison(comparisonMap, parcelFeatureById),
    [comparisonMap, parcelFeatureById]
  );

  const transitionBreakdown = useMemo(
    () => calculateTransitionBreakdown(comparisonMap),
    [comparisonMap]
  );

  const legendItems = useMemo(() => getComparisonLegendItems(), []);
  const changedRatio =
    comparisonSummary.totalParcels > 0
      ? `${comparisonSummary.changedParcels.toLocaleString()} / ${comparisonSummary.totalParcels.toLocaleString()}`
      : '0 / 0';
  const baselineLabel = baselinePlan ? `Plan ${baselinePlan.planIndex + 1}` : 'Baseline plan';
  const comparisonLabel = comparisonPlan ? `Plan ${comparisonPlan.planIndex + 1}` : 'Comparison plan';
  const comparisonNarrative = useMemo(
    () =>
      generatePlanComparisonNarrative(
        comparisonSummary,
        baselineLabel,
        comparisonLabel,
        transitionBreakdown
      ),
    [baselineLabel, comparisonLabel, comparisonSummary, transitionBreakdown]
  );

  if (selectedPlans.length < 2 || !baselinePlan || !comparisonPlan) {
    return null;
  }

  const handleBaselineChange = (value: string) => {
    const nextBaseline = Number(value);
    setBaselinePlanIndex(nextBaseline);
    setSelectedParcel(null);
    if (nextBaseline === comparisonPlan.planIndex) {
      const nextComparison = selectedPlans.find((item) => item.planIndex !== nextBaseline);
      setComparisonPlanIndex(nextComparison?.planIndex ?? null);
    }
  };

  const handleComparisonChange = (value: string) => {
    const nextComparison = Number(value);
    setComparisonPlanIndex(nextComparison);
    setSelectedParcel(null);
    if (nextComparison === baselinePlan.planIndex) {
      const nextBaseline = selectedPlans.find((item) => item.planIndex !== nextComparison);
      setBaselinePlanIndex(nextBaseline?.planIndex ?? null);
    }
  };

  const handleParcelSelect = (parcelId: string, _properties: unknown, feature: unknown) => {
    const comparison = comparisonMap.get(parcelId) ?? null;
    const risk = getParcelRisk(feature ?? parcelFeatureById.get(parcelId));
    setSelectedParcel({ parcelId, comparison, risk });
  };

  return (
    <section className="spatial-difference-section">
      <div className="spatial-difference-section__header">
        <div>
          <h2>Spatial Difference Map</h2>
          <p>Shows where the selected plans assign different land uses parcel by parcel.</p>
        </div>
      </div>

      <div className="spatial-difference-controls">
        <label>
          <span>Baseline</span>
          <select
            value={String(baselinePlan.planIndex)}
            onChange={(event) => handleBaselineChange(event.target.value)}
          >
            {selectedPlans.map((item) => (
              <option key={`baseline-${item.planIndex}`} value={String(item.planIndex)}>
                Plan {item.planIndex + 1}
              </option>
            ))}
          </select>
        </label>
        <span className="spatial-difference-controls__arrow">-&gt;</span>
        <label>
          <span>Comparison</span>
          <select
            value={String(comparisonPlan.planIndex)}
            onChange={(event) => handleComparisonChange(event.target.value)}
          >
            {selectedPlans.map((item) => (
              <option
                key={`comparison-${item.planIndex}`}
                value={String(item.planIndex)}
                disabled={item.planIndex === baselinePlan.planIndex}
              >
                Plan {item.planIndex + 1}
              </option>
            ))}
          </select>
        </label>
        <div className="spatial-difference-controls__label">
          Baseline: Plan {baselinePlan.planIndex + 1} -&gt; Comparison: Plan{' '}
          {comparisonPlan.planIndex + 1}
        </div>
        <label>
          <span>Review filter</span>
          <select
            value={reviewFilter}
            onChange={(event) => setReviewFilter(event.target.value as PlanComparisonFilter)}
          >
            {REVIEW_FILTER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="spatial-difference-summary">
        <div>
          <span>Changed parcels</span>
          <strong>{changedRatio}</strong>
        </div>
        <div>
          <span>Built -&gt; Green</span>
          <strong>{comparisonSummary.builtToGreen.toLocaleString()}</strong>
        </div>
        <div>
          <span>Green -&gt; Built</span>
          <strong>{comparisonSummary.greenToBuilt.toLocaleString()}</strong>
        </div>
        <div>
          <span>Built -&gt; Built</span>
          <strong>{comparisonSummary.builtToBuilt.toLocaleString()}</strong>
        </div>
        <div>
          <span>Unchanged</span>
          <strong>{comparisonSummary.unchanged.toLocaleString()}</strong>
        </div>
        <div>
          <span>Missing</span>
          <strong>{comparisonSummary.missing.toLocaleString()}</strong>
        </div>
        <div>
          <span>High-risk improved</span>
          <strong>{formatCount(comparisonSummary.highRiskImproved)}</strong>
        </div>
        <div>
          <span>High-risk worsened</span>
          <strong>{formatCount(comparisonSummary.highRiskWorsened)}</strong>
        </div>
      </div>

      <div className="spatial-difference-narrative">{comparisonNarrative}</div>

      <div className="spatial-difference-body">
        <div className="spatial-difference-map">
          <ParcelMap
            geoJsonUrl={geoJsonUrl}
            scoresById={EMPTY_SCORES}
            colorMode="plan_comparison"
            planComparisonByParcel={comparisonMap}
            planComparisonParcelFeatureById={parcelFeatureById}
            planComparisonFilter={reviewFilter}
            planComparisonLayerKey={`${baselinePlan.planIndex}-${comparisonPlan.planIndex}-${comparisonMap.size}-${reviewFilter}`}
            selectedParcelIds={selectedParcel?.parcelId ? [selectedParcel.parcelId] : []}
            onParcelSelect={handleParcelSelect}
            autoFitToData={true}
            lockViewportToData={true}
          />
        </div>

        <aside className="spatial-difference-side">
          <div className="spatial-difference-legend">
            <h3>Legend</h3>
            <p className="spatial-difference-legend__note">
              Green reduces development exposure, red moves green/open space to built use,
              orange changes between built uses, and gray stayed the same.
            </p>
            {legendItems.map((item) => (
              <div key={item.status} className="spatial-difference-legend__item" title={item.description}>
                <span style={{ backgroundColor: item.fillColor, borderColor: item.color }} />
                <div>
                  <strong>{item.label}</strong>
                  <small>{item.description}</small>
                </div>
              </div>
            ))}
          </div>

          <div className="spatial-difference-transitions">
            <h3>Transition Breakdown</h3>
            {transitionBreakdown.length > 0 ? (
              <div className="spatial-difference-transitions__list">
                {transitionBreakdown.slice(0, 5).map((transition) => (
                  <div key={`${transition.fromUse}-${transition.toUse}`}>
                    <span>{transition.label}</span>
                    <strong>{transition.count.toLocaleString()}</strong>
                  </div>
                ))}
                {transitionBreakdown.length > 5 && (
                  <small>+ {transitionBreakdown.length - 5} more transition types</small>
                )}
              </div>
            ) : (
              <p className="spatial-difference-detail__empty">
                No exact use-to-use transitions are available for this pair.
              </p>
            )}
          </div>

          <div className="spatial-difference-detail">
            <h3>Parcel Change Detail</h3>
            {selectedParcel?.comparison ? (
              <div className="spatial-difference-detail__content">
                <div>
                  <span>Parcel</span>
                  <strong>{selectedParcel.parcelId}</strong>
                </div>
                <div>
                  <span>Baseline</span>
                  <strong>{formatPlanUseLabel(selectedParcel.comparison.baselineUse)}</strong>
                </div>
                <div>
                  <span>Comparison</span>
                  <strong>{formatPlanUseLabel(selectedParcel.comparison.comparisonUse)}</strong>
                </div>
                <div>
                  <span>Change type</span>
                  <strong>
                    {legendItems.find((item) => item.status === selectedParcel.comparison?.status)?.label ??
                      selectedParcel.comparison.status}
                  </strong>
                </div>
                <div>
                  <span>Planning impact</span>
                  <strong>
                    {getPlanningImpact(
                      selectedParcel.comparison.status,
                      selectedParcel.comparison.baselineUse,
                      selectedParcel.comparison.comparisonUse,
                      selectedParcel.risk
                    )}
                  </strong>
                </div>
                <div>
                  <span>Risk score</span>
                  <strong>{formatRiskScore(selectedParcel.risk)}</strong>
                </div>
                <p>{getRiskSensitivePlannerInterpretation(selectedParcel.comparison, selectedParcel.risk)}</p>
              </div>
            ) : selectedParcel ? (
              <p className="spatial-difference-detail__empty">
                Parcel {selectedParcel.parcelId} has no comparison data for the selected plan pair.
              </p>
            ) : (
              <p className="spatial-difference-detail__empty">
                Select a parcel on the map to inspect its baseline and comparison assignments.
              </p>
            )}
          </div>
        </aside>
      </div>
    </section>
  );
}
