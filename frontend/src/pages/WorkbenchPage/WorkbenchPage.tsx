import { useMemo } from 'react';
import { Layers, Leaf, LayoutGrid, Sparkles } from 'lucide-react';
import { DashboardLayout } from '../../layouts/DashboardLayout/DashboardLayout';
import { usePlannerWorkspace } from '../../context/PlannerWorkspaceContext';
import { usePlannerSettings } from '../../context/PlannerSettingsContext';
import { useAuth } from '../../context/AuthContext';
import type { LandUseZone, Metrics, ViewType } from '../../types';
import {
  buildSelectedFeatures,
  formatArea,
  formatPercent,
  hasEnvironmentalValues,
  previewParcelIds,
  summarizeFeatures,
  WORKSPACE_SOURCE_MODE_LABEL,
} from '../../utils/plannerWorkspace';
import { WorkbenchSummaryCards } from '../../components/workbench/WorkbenchSummaryCards';
import { PlanningAreaOverviewCard } from '../../components/workbench/PlanningAreaOverviewCard';
import { SelectionInsightCard } from '../../components/workbench/SelectionInsightCard';
import { NextActionsCard } from '../../components/workbench/NextActionsCard';
import { OptimizationSnapshotCard } from '../../components/workbench/OptimizationSnapshotCard';
import { SystemStatusCard } from '../../components/workbench/SystemStatusCard';
import { PlanningWorkflowCard } from '../../components/workbench/PlanningWorkflowCard';
import './WorkbenchPage.css';

interface WorkbenchPageProps {
  metrics: Metrics;
  simulationTime: number;
  zones: LandUseZone[];
  selectedRegion: string;
  onOpenView: (view: ViewType) => void;
}

export function WorkbenchPage({
  metrics,
  simulationTime,
  zones,
  selectedRegion,
  onOpenView,
}: WorkbenchPageProps) {
  const { settings } = usePlannerSettings();
  const { user } = useAuth();
  const {
    loadedParcelFeatures,
    loadedFeatureById,
    totalLoadedParcels,
    selectedParcelIds,
    selectedFeatureById,
    primarySelectedParcelId,
    generatedPlans,
    objectiveNames,
    latestOptimization,
    registerLoadedParcelFeatures,
    replaceSelection,
    addToSelection,
    toggleSelectedParcel,
    clearSelection,
    selectAllLoadedParcels,
    setPrimarySelectedParcel,
  } = usePlannerWorkspace();

  const selectedFeatures = useMemo(
    () => buildSelectedFeatures(selectedParcelIds, selectedFeatureById, loadedFeatureById),
    [loadedFeatureById, selectedFeatureById, selectedParcelIds]
  );

  const loadedSummary = useMemo(() => summarizeFeatures(loadedParcelFeatures), [loadedParcelFeatures]);
  const selectionSummary = useMemo(() => summarizeFeatures(selectedFeatures), [selectedFeatures]);

  const formatCountShare = (count: number, total: number) => {
    if (total <= 0) return `${count}`;
    return `${count} (${formatPercent(count / total)})`;
  };

  const selectionConstraintChips = useMemo(() => {
    return selectionSummary.topConstraints.slice(0, 4).map((item) => `${item.label}: ${item.count}`);
  }, [selectionSummary.topConstraints]);

  const selectionProtectedChips = useMemo(() => {
    return selectionSummary.protectedFlags.map((item) => `${item.label}: ${item.count}`);
  }, [selectionSummary.protectedFlags]);

  const selectionFootprintChips = useMemo(() => {
    if (selectedParcelIds.length === 0) return [];

    const shareLabel = (count: number) =>
      `${count} (${formatPercent(count / Math.max(selectedParcelIds.length, 1))})`;

    return [
      `Constrained: ${shareLabel(selectionSummary.constrainedParcelCount)}`,
      `Protected: ${shareLabel(selectionSummary.protectedParcelCount)}`,
      `Multi-Constraint: ${shareLabel(selectionSummary.multiConstraintParcelCount)}`,
    ];
  }, [
    selectedParcelIds.length,
    selectionSummary.constrainedParcelCount,
    selectionSummary.multiConstraintParcelCount,
    selectionSummary.protectedParcelCount,
  ]);

  const summaryItems = useMemo(
    () => [
      {
        label: 'Total Loaded Parcels',
        value: totalLoadedParcels > 0 ? String(totalLoadedParcels) : '—',
        tone: 'accent' as const,
      },
      {
        label: 'Selected Parcels',
        value: String(selectedParcelIds.length),
        tone: 'cyan' as const,
      },
      {
        label: 'Selected Area',
        value: formatArea(selectionSummary.areaM2),
        tone: 'neutral' as const,
      },
      {
        label: 'Primary Constraint',
        value: loadedSummary.dominantConstraint ?? 'No Flagged Constraint',
        tone: 'warning' as const,
      },
      {
        label: 'Average Environmental Risk',
        value: formatPercent(loadedSummary.averageRisk),
        tone: 'neutral' as const,
      },
      {
        label: 'Plans Generated',
        value: String(generatedPlans.length),
        tone: 'accent' as const,
      },
    ],
    [
      generatedPlans.length,
      loadedSummary.averageRisk,
      loadedSummary.dominantConstraint,
      selectionSummary.areaM2,
      selectedParcelIds.length,
      totalLoadedParcels,
    ]
  );

  const actionItems = useMemo(
    () => [
      {
        title: 'Open Environmental Agent',
        description:
          'Switch to the environmental analysis workspace to inspect risk colors and run optimization.',
        readiness: 'Ready',
        ready: true,
        ctaLabel: 'Open',
        onClick: () => onOpenView('environmental'),
      },
      {
        title: 'Ask Zoning Question',
        description: 'Use the Layers workspace to inspect one parcel and query zoning guidance.',
        readiness: selectedParcelIds.length > 0 ? 'Ready' : 'Select Parcel',
        ready: selectedParcelIds.length > 0,
        ctaLabel: 'Open Layers',
        onClick: () => onOpenView('layers'),
      },
      {
        title: 'Generate Land Use Alternatives',
        description: 'Open Environmental Agent and run the live spatial optimization workflow.',
        readiness: selectedParcelIds.length > 0 ? 'Ready' : 'Select Parcels',
        ready: selectedParcelIds.length > 0,
        ctaLabel: 'Open Planner',
        onClick: () => onOpenView('environmental'),
      },
      {
        title: 'Review Existing Plans',
        description: 'Inspect generated alternatives, overlays, and export results from the gallery.',
        readiness: generatedPlans.length > 0 ? 'Ready' : 'No Plans Yet',
        ready: generatedPlans.length > 0,
        ctaLabel: 'View Plans',
        onClick: () => onOpenView('plans'),
      },
    ],
    [generatedPlans.length, onOpenView, selectedParcelIds.length]
  );

  return (
    <DashboardLayout
      metrics={metrics}
      simulationTime={simulationTime}
      zones={zones}
      selectedRegion={selectedRegion}
    >
      <main className="workbench-page custom-scrollbar">
        <section className="workbench-card workbench-hero">
          <div className="workbench-hero__content">
            <div>
              <div className="workbench-hero__eyebrow">Planner Command Center</div>
              <h1 className="workbench-hero__title">Geovision Workbench</h1>
              <p className="workbench-hero__subtitle">
                Launch workflows, inspect planning readiness, and move between parcel selection,
                zoning guidance, optimization, and plan review from one operational dashboard.
              </p>
              {/* Pill group example - consistent sizing */}
              <div className="workbench-hero__meta">
                <span className="pill pill--default">
                  Planner: {user?.username ?? settings.userAccount.fullName}
                </span>
                <span className="pill pill--secondary">Source Mode: {WORKSPACE_SOURCE_MODE_LABEL}</span>
              </div>
            </div>

            {/* Button Group Example - Primary action first, secondary actions follow */}
            <div className="btn-group">
              <button
                type="button"
                className="btn btn--primary"
                onClick={() => onOpenView('environmental')}
              >
                <Leaf size={16} />
                Open Environmental Agent
              </button>
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => onOpenView('layers')}
              >
                <Layers size={16} />
                Open Layers
              </button>
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => onOpenView('plans')}
              >
                <LayoutGrid size={16} />
                View Plans
              </button>
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => onOpenView('environmental')}
              >
                <Sparkles size={16} />
                Generate Alternatives
              </button>
            </div>
          </div>
        </section>

        <WorkbenchSummaryCards items={summaryItems} />

        <section className="workbench-upper-grid">
          <PlanningAreaOverviewCard
            selectedParcelIds={selectedParcelIds}
            totalLoadedParcels={totalLoadedParcels}
            primaryConstraint={loadedSummary.dominantConstraint ?? 'No flagged constraint'}
            constrainedParcels={formatCountShare(
              loadedSummary.constrainedParcelCount,
              loadedSummary.count
            )}
            protectedParcels={formatCountShare(
              loadedSummary.protectedParcelCount,
              loadedSummary.count
            )}
            multiConstraintParcels={formatCountShare(
              loadedSummary.multiConstraintParcelCount,
              loadedSummary.count
            )}
            onFeaturesLoaded={registerLoadedParcelFeatures}
            onParcelSelect={(parcelId, properties, feature) => {
              toggleSelectedParcel(parcelId, feature);
            }}
            onBulkParcelSelect={(parcelIds, featureById) => {
              if (parcelIds.length === 0) return;
              addToSelection(parcelIds, featureById);
              const firstParcelId = parcelIds[0];
              setPrimarySelectedParcel(
                firstParcelId,
                featureById.get(firstParcelId)?.properties ?? null,
                featureById.get(firstParcelId) ?? null
              );
            }}
          />

          <div className="workbench-side-stack">
            <SelectionInsightCard
              selectedParcelCount={selectedParcelIds.length}
              parcelPreview={previewParcelIds(selectedParcelIds)}
              selectedArea={formatArea(selectionSummary.areaM2)}
              averageRisk={formatPercent(selectionSummary.averageRisk)}
              averageParcelSize={formatArea(selectionSummary.averageParcelAreaM2)}
              constrainedParcels={selectionSummary.constrainedParcelCount}
              keyConstraints={selectionConstraintChips}
              constraintFootprint={selectionFootprintChips}
              protectedFlags={selectionProtectedChips}
              readyForOptimization={selectedParcelIds.length > 0}
            />

            <NextActionsCard actions={actionItems} />

            <SystemStatusCard
              datasetLoaded={loadedParcelFeatures.length > 0}
              environmentalValuesAvailable={hasEnvironmentalValues(loadedParcelFeatures)}
              zoningAssistantAvailable
              optimizationAvailable={selectedParcelIds.length > 0}
              plansAvailable={generatedPlans.length > 0}
              sourceMode={WORKSPACE_SOURCE_MODE_LABEL}
            />
          </div>
        </section>

        <section className="workbench-lower-grid">
          <PlanningWorkflowCard
            plannerName={user?.username ?? settings.userAccount.fullName}
            selectedParcelCount={selectedParcelIds.length}
            totalLoadedParcels={totalLoadedParcels}
            defaultAlternatives={settings.growthDemand.defaultPlanAlternatives}
            populationSize={settings.scenarioGeneration.basePopulationSize}
            generations={settings.scenarioGeneration.baseGenerations}
            boundaryRule={settings.scenarioGeneration.boundaryRule}
            onSelectAll={selectAllLoadedParcels}
            onClearSelection={clearSelection}
            onOpenEnvironmentalAgent={() => onOpenView('environmental')}
            canSelectAll={totalLoadedParcels > 0 && selectedParcelIds.length < totalLoadedParcels}
            canClear={selectedParcelIds.length > 0}
          />

          <OptimizationSnapshotCard
            latestOptimization={latestOptimization}
            planCount={generatedPlans.length}
            objectiveNames={objectiveNames}
            onOpenPlans={() => onOpenView('plans')}
          />
        </section>
      </main>
    </DashboardLayout>
  );
}
