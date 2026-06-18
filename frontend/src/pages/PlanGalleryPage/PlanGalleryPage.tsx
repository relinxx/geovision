/**
 * PlanGalleryPage Component
 * =========================
 * Page for browsing generated land-use plans, comparing alternatives,
 * and visualizing plan outcomes on the map.
 * 
 * @component
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { DashboardLayout } from '../../layouts/DashboardLayout/DashboardLayout';
import { ParcelMap } from '../../components/map/ParcelMap';
import { DeckGLMap } from '../../components/map/DeckGLMap/DeckGLMap';
import { SpatialMapLegend } from '../../components/map';
import {
  PlanComparisonDashboard,
  type SelectedPlanComparisonItem,
} from '../../components/plans/PlanComparisonDashboard';
import { SpatialDifferenceMap } from '../../components/plans/SpatialDifferenceMap';
import type {
  LandUseAssignment,
  Metrics,
  LandUseZone,
  ReferenceMapLayerVisibility,
  SavedMapListItem,
  SpatialOverlayLayerKey,
  SpatialOverlayVisibility,
  SpatialAssignmentExplanation,
  SpatialOptimizationPlan,
  SpatialOptimizationResponse,
  PlanningMetrics,
} from '../../types';
import { getOverlayCandidatePlanId, resolveOverlayPlanId } from '../../utils/overlayPlanResolver';
import { getPlanBadges } from '../../utils/planBadges';
import {
  buildPlanReportSummary,
  capturePlanMapImage,
  type ConflictSeverity,
} from '../../utils/planReport';
import { toast } from 'sonner';
import { usePlannerSettings } from '../../context/PlannerSettingsContext';
import { usePlannerWorkspace } from '../../context/PlannerWorkspaceContext';
import { apiClient } from '../../utils/api';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import './PlanGalleryPage.css';

/** Props for the PlanGalleryPage component */
interface PlanGalleryPageProps {
  metrics: Metrics;
  simulationTime: number;
  zones: LandUseZone[];
  selectedRegion: string;
}

const EMPTY_SCORES = new Map();

const OVERLAY_LAYER_KEYS: SpatialOverlayLayerKey[] = [
  'roads',
  'networks',
  'blocks',
  'green',
  'buildings',
  'plots',
  'density',
];

const OVERLAY_LAYER_LABELS: Record<SpatialOverlayLayerKey, string> = {
  roads: 'Roads',
  networks: 'Networks',
  blocks: 'Blocks',
  green: 'Green Areas',
  buildings: 'Buildings',
  plots: 'Plots',
  density: 'Density',
};

const DEFAULT_OVERLAY_VISIBILITY: SpatialOverlayVisibility = {
  roads: true,
  networks: true,
  blocks: true,
  green: true,
  buildings: false,
  plots: false,
  density: false,
};

const EMPTY_REFERENCE_LAYER_VISIBILITY: ReferenceMapLayerVisibility = {
  municipal_boundaries: false,
  zoning_base_sd: false,
  zoning_unincorporated: false,
  general_plan_land_use_sd: false,
};

// Simple 3D toggle hook
function use3DMapToggle() {
  const [use3D, setUse3D] = useState(false);
  const toggle = () => setUse3D((v) => !v);
  return { use3D, toggle };
}

const LAND_USE_TERM_META: Record<LandUseAssignment, { label: string; description: string }> = {
  residential: {
    label: 'Housing',
    description: 'Share of parcels allocated for residential neighborhoods and homes.',
  },
  commercial: {
    label: 'Commerce & Services',
    description: 'Share of parcels allocated for business, retail, and service activity.',
  },
  industrial: {
    label: 'Employment & Industry',
    description: 'Share of parcels allocated for production, warehousing, and industrial jobs.',
  },
  green: {
    label: 'Parks & Open Space',
    description: 'Share of parcels allocated for green areas, recreation, and ecological space.',
  },
};

const OBJECTIVE_TERM_META: Record<string, { label: string; description: string }> = {
  zoning_violation_penalty: {
    label: 'Zoning Compliance Gap',
    description: 'Penalty for assignments that conflict with zoning constraints. Lower is better.',
  },
  mean_suitability_loss: {
    label: 'Site Suitability Mismatch',
    description: 'Average mismatch between assigned land use and parcel suitability. Lower is better.',
  },
  environmental_risk_exposure: {
    label: 'Environmental Exposure Impact',
    description: 'Total exposure of the plan to environmental risk. Lower is better.',
  },
  fragmentation_penalty: {
    label: 'Land-Use Fragmentation',
    description: 'Penalty for fragmented, discontinuous land-use patterns. Lower is better.',
  },
  land_use_balance_penalty: {
    label: 'Mix Balance Deviation',
    description: 'Difference between actual land-use mix and target mix. Lower is better.',
  },
  spatial_compatibility_penalty: {
    label: 'Spatial Compatibility',
    description: 'Penalty for nearby land-use conflicts and weak spatial clustering. Lower is better.',
  },
};

/** Format timestamp for display */
function formatTimestamp(date: Date): string {
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Format objective value */
function formatObjectiveValue(value: number): string {
  if (!Number.isFinite(value)) return 'N/A';
  return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

function fmtTax(usd: number): string {
  if (usd >= 1_000_000) return `$${(usd / 1_000_000).toFixed(1)}M`;
  if (usd >= 1_000) return `$${Math.round(usd / 1_000)}K`;
  return `$${usd}`;
}

function Delta({ base, value, unit = '', lowerIsBetter = false }: {
  base: number; value: number; unit?: string; lowerIsBetter?: boolean;
}) {
  const diff = value - base;
  if (diff === 0) return <span style={{ color: '#8899aa', fontSize: 11 }}>—</span>;
  const positive = lowerIsBetter ? diff < 0 : diff > 0;
  const arrow = diff > 0 ? '↑' : '↓';
  const absVal = Math.abs(diff);
  const formatted = absVal >= 1000 ? `${Math.round(absVal / 1000)}K` : absVal >= 1 ? Math.round(absVal).toString() : absVal.toFixed(1);
  return (
    <span style={{ color: positive ? '#4FFFA7' : '#ef4444', fontSize: 11, fontWeight: 600 }}>
      {arrow} {formatted}{unit}
    </span>
  );
}

function PlanningMetricsCard({ pm, baseline, label }: {
  pm: PlanningMetrics; baseline?: PlanningMetrics | null; label?: string;
}) {
  const whoMet = pm.green_space_per_resident_m2 >= pm.who_green_target_m2;
  const hazardColor = pm.hazard_built_parcels === 0 ? '#4FFFA7' : pm.hazard_built_parcels <= 1 ? '#FFB86C' : '#ef4444';

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 12px', marginTop: 8 }}>
      <MetricRow
        icon="🏠"
        label="Housing Units"
        value={pm.housing_units.toLocaleString()}
        delta={baseline ? <Delta base={baseline.housing_units} value={pm.housing_units} /> : null}
      />
      <MetricRow
        icon="👥"
        label="Est. Residents"
        value={pm.estimated_residents.toLocaleString()}
        delta={baseline ? <Delta base={baseline.estimated_residents} value={pm.estimated_residents} /> : null}
      />
      <MetricRow
        icon="🌿"
        label="Green/Resident"
        value={`${pm.green_space_per_resident_m2} m²`}
        subtext={whoMet ? '✓ WHO target met' : `WHO: ${pm.who_green_target_m2} m²`}
        valueColor={whoMet ? '#4FFFA7' : '#FFB86C'}
        delta={baseline ? <Delta base={baseline.green_space_per_resident_m2} value={pm.green_space_per_resident_m2} unit=" m²" /> : null}
      />
      <MetricRow
        icon="💰"
        label="Est. Tax/Year"
        value={fmtTax(pm.estimated_annual_tax_usd)}
        delta={baseline ? <Delta base={baseline.estimated_annual_tax_usd} value={pm.estimated_annual_tax_usd} /> : null}
      />
      <MetricRow
        icon="⚠️"
        label="Built on Hazard"
        value={`${pm.hazard_built_parcels} / ${pm.total_parcels} parcels`}
        valueColor={hazardColor}
        delta={baseline ? <Delta base={baseline.hazard_built_parcels} value={pm.hazard_built_parcels} lowerIsBetter /> : null}
      />
    </div>
  );
}

function SpatialCompatibilityCard({ plan }: { plan: SpatialOptimizationPlan }) {
  const summary = plan.spatial_compatibility_summary;
  if (!summary) {
    return null;
  }

  const warnings = plan.spatial_compatibility_warnings ?? [];
  return (
    <div className="spatial-compatibility-card">
      <div className="spatial-compatibility-card__header">
        <span>Spatial Compatibility</span>
        <strong>{formatPercentScore(plan.spatial_compatibility_score)}</strong>
      </div>
      <div className="spatial-compatibility-card__grid">
        <span>Pairs</span>
        <strong>{summary.neighbor_pairs_evaluated}</strong>
        <span>Compatible</span>
        <strong>{summary.compatible_pairs}</strong>
        <span>Conflicts</span>
        <strong>{summary.conflict_pairs}</strong>
        <span>Green buffers</span>
        <strong>{summary.green_buffer_pairs}</strong>
      </div>
      {summary.industrial_residential_conflicts > 0 && (
        <div className="spatial-compatibility-card__flag">
          Industrial-residential conflicts: {summary.industrial_residential_conflicts}
        </div>
      )}
      {warnings.length > 0 && (
        <ul className="spatial-compatibility-card__notes">
          {warnings.slice(0, 2).map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function MetricRow({ icon, label, value, subtext, valueColor, delta }: {
  icon: string; label: string; value: string; subtext?: string;
  valueColor?: string; delta?: React.ReactNode;
}) {
  return (
    <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 6, padding: '6px 8px' }}>
      <div style={{ fontSize: 10, color: '#8899aa', marginBottom: 2 }}>{icon} {label}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: valueColor || '#e8f0fc' }}>{value}</span>
        {delta}
      </div>
      {subtext && <div style={{ fontSize: 10, color: valueColor || '#8899aa', marginTop: 1 }}>{subtext}</div>}
    </div>
  );
}

/** Convert objective name to readable label */
function toReadableObjectiveLabel(value: string): string {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatAssignmentUseLabel(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatPercentScore(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 'N/A';
  }
  return `${(value * 100).toFixed(0)}%`;
}

function buildDefaultSavedMapName(): string {
  return `Generated Plans ${new Date().toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })}`;
}

/** Get metadata for an objective */
function getObjectiveMeta(rawObjectiveName: string): { label: string; description: string } {
  const key = rawObjectiveName.trim().toLowerCase();
  const known = OBJECTIVE_TERM_META[key];
  if (known) return known;
  return {
    label: toReadableObjectiveLabel(rawObjectiveName),
    description: 'Optimization criterion used to compare candidate land-use plans.',
  };
}

/** Compute land use mix percentages for a plan */
function computeMix(plan: SpatialOptimizationPlan): Record<LandUseAssignment, number> {
  const counts: Record<LandUseAssignment, number> = {
    residential: 0,
    commercial: 0,
    industrial: 0,
    green: 0,
  };
  for (const assignment of plan.assignments) {
    const label = assignment.use_label as LandUseAssignment;
    if (label in counts) {
      counts[label] += 1;
    }
  }
  const total = Math.max(1, plan.assignments.length);
  return {
    residential: (counts.residential / total) * 100,
    commercial: (counts.commercial / total) * 100,
    industrial: (counts.industrial / total) * 100,
    green: (counts.green / total) * 100,
  };
}

/**
 * PlanGalleryPage component.
 * Allows users to browse and compare generated land-use plans.
 */
export function PlanGalleryPage({
  metrics,
  simulationTime,
  zones,
  selectedRegion,
}: PlanGalleryPageProps) {
  const { settings } = usePlannerSettings();
  const {
    generatedPlans,
    objectiveNames,
    activePlanIndex,
    setActivePlanIndex,
    latestOptimization,
    loadedFeatureById,
    loadedParcelFeatures,
    totalLoadedParcels,
    registerLoadedParcelFeatures,
    storeOptimizationResult,
    currentState,
  } = usePlannerWorkspace();
  const [totalParcels, setTotalParcels] = useState(0);
  
  const selectedPlan =
    generatedPlans.length > 0
      ? generatedPlans[Math.min(activePlanIndex, generatedPlans.length - 1)]
      : null;

  const selectedPlanAssignments = useMemo(() => {
    const assignments = new Map<string, LandUseAssignment>();
    if (!selectedPlan) return assignments;
    for (const assignment of selectedPlan.assignments) {
      const label = assignment.use_label as LandUseAssignment;
      if (
        label === 'residential' ||
        label === 'commercial' ||
        label === 'industrial' ||
        label === 'green'
      ) {
        assignments.set(assignment.parcel_id, label);
      }
    }
    return assignments;
  }, [selectedPlan]);

  const mappedAssignmentsCount = selectedPlanAssignments.size;
  const selectedPlanAssignmentCount = selectedPlan?.assignments.length ?? 0;
  const [showPlanOverlays, setShowPlanOverlays] = useState(false);
  const [overlayVisibility, setOverlayVisibility] =
    useState<SpatialOverlayVisibility>(DEFAULT_OVERLAY_VISIBILITY);
  const [planOverlayLayers, setPlanOverlayLayers] = useState<
    Partial<Record<SpatialOverlayLayerKey, any>>
  >({});
  const overlayLayerCacheRef = useRef<Map<string, any>>(new Map());
  const overlayFallbackWarningsRef = useRef<Set<string>>(new Set());
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const { use3D, toggle: toggle3D } = use3DMapToggle();
  const [hoveredPlanParcel, setHoveredPlanParcel] = useState<{
    apn: string;
    assignedUse: LandUseAssignment;
  } | null>(null);
  const [pinnedPlanParcel, setPinnedPlanParcel] = useState<{
    apn: string;
    assignedUse: LandUseAssignment | null;
  } | null>(null);
  const [assignmentExplanation, setAssignmentExplanation] =
    useState<SpatialAssignmentExplanation | null>(null);
  const [isLoadingAssignmentExplanation, setIsLoadingAssignmentExplanation] = useState(false);
  const [assignmentExplanationMessage, setAssignmentExplanationMessage] = useState<string | null>(
    null
  );
  const assignmentRequestIdRef = useRef(0);
  const [isSaveDialogOpen, setIsSaveDialogOpen] = useState(false);
  const [saveMapName, setSaveMapName] = useState('');
  const [saveMapDescription, setSaveMapDescription] = useState('');
  const [saveMapSelectedRank, setSaveMapSelectedRank] = useState('');
  const [saveMapError, setSaveMapError] = useState<string | null>(null);
  const [isSavingMap, setIsSavingMap] = useState(false);
  const [showSavedPlansPanel, setShowSavedPlansPanel] = useState(false);
  const [savedMaps, setSavedMaps] = useState<SavedMapListItem[]>([]);
  const [savedMapsTotal, setSavedMapsTotal] = useState(0);
  const [isLoadingSavedMaps, setIsLoadingSavedMaps] = useState(false);
  const [savedMapsError, setSavedMapsError] = useState<string | null>(null);
  const [openingSavedMapId, setOpeningSavedMapId] = useState<number | null>(null);
  const [deletingSavedMapId, setDeletingSavedMapId] = useState<number | null>(null);
  const [loadedSavedMapName, setLoadedSavedMapName] = useState<string | null>(null);
  const [isComparisonMode, setIsComparisonMode] = useState(false);
  const [comparisonPlanIndexes, setComparisonPlanIndexes] = useState<number[]>([]);
  const [comparisonMessage, setComparisonMessage] = useState<string | null>(null);
  const reportMapRef = useRef<HTMLDivElement | null>(null);

  const canSaveMap = generatedPlans.length > 0;
  const planBadgesByIndex = useMemo(
    () =>
      getPlanBadges({
        plans: generatedPlans,
        objectiveNames,
        targetMix: latestOptimization?.settings?.target_mix ?? null,
      }),
    [generatedPlans, objectiveNames, latestOptimization?.settings?.target_mix]
  );
  const planRankOptions = useMemo(
    () => generatedPlans.map((plan) => ({ rank: plan.rank })),
    [generatedPlans]
  );
  const selectedComparisonPlans = useMemo<SelectedPlanComparisonItem[]>(
    () =>
      comparisonPlanIndexes
        .map((planIndex) => {
          const plan = generatedPlans[planIndex];
          return plan ? { plan, planIndex } : null;
        })
        .filter((item): item is SelectedPlanComparisonItem => item !== null),
    [comparisonPlanIndexes, generatedPlans]
  );

  const optimizationResultForSave = useMemo<SpatialOptimizationResponse | null>(() => {
    if (generatedPlans.length === 0) {
      return null;
    }

    return {
      parcel_count: latestOptimization?.parcelCount ?? generatedPlans[0]?.assignments.length ?? 0,
      objective_names: objectiveNames,
      plans: generatedPlans,
      warnings: latestOptimization?.warnings ?? [],
      debug_timeline: latestOptimization?.debugTimeline ?? [],
      settings:
        latestOptimization?.settings ?? {
          num_output_plans: generatedPlans.length,
          population_size: 0,
          generations: 0,
          include_adjacency: false,
          adjacency_predicate: 'intersects',
          target_mix: {},
        },
    };
  }, [generatedPlans, latestOptimization, objectiveNames]);

  const inputParcelsForSave = useMemo(() => {
    const seenParcelIds = new Set<string>();
    const nextFeatures: any[] = [];

    // Prefer the exact parcels referenced by generated plan assignments.
    for (const plan of generatedPlans) {
      for (const assignment of plan.assignments) {
        const parcelId = String(assignment.parcel_id || '');
        if (!parcelId || seenParcelIds.has(parcelId)) {
          continue;
        }
        const feature = loadedFeatureById.get(parcelId);
        if (!feature) {
          continue;
        }
        seenParcelIds.add(parcelId);
        nextFeatures.push(feature);
      }
    }

    if (nextFeatures.length > 0) {
      return nextFeatures;
    }

    // Fallback: trim to the optimization parcel_count if available.
    if (Array.isArray(loadedParcelFeatures) && loadedParcelFeatures.length > 0) {
      const expectedCount = latestOptimization?.parcelCount ?? loadedParcelFeatures.length;
      return loadedParcelFeatures.slice(0, Math.max(1, expectedCount));
    }

    return nextFeatures;
  }, [generatedPlans, latestOptimization?.parcelCount, loadedFeatureById, loadedParcelFeatures]);

  const loadSavedMaps = useCallback(async () => {
    setIsLoadingSavedMaps(true);
    setSavedMapsError(null);
    try {
      const response = await apiClient.listSavedMaps({ limit: 50, offset: 0 });
      setSavedMaps(response.items ?? []);
      setSavedMapsTotal(response.total ?? 0);
    } catch (error: any) {
      const message =
        typeof error?.message === 'string' ? error.message : 'Failed to load saved maps.';
      setSavedMapsError(message);
      toast.error(message);
    } finally {
      setIsLoadingSavedMaps(false);
    }
  }, []);

  useEffect(() => {
    assignmentRequestIdRef.current += 1;
    setHoveredPlanParcel(null);
    setPinnedPlanParcel(null);
    setAssignmentExplanation(null);
    setAssignmentExplanationMessage(null);
    setIsLoadingAssignmentExplanation(false);
  }, [selectedPlan]);

  useEffect(() => {
    if (!showSavedPlansPanel) {
      return;
    }
    void loadSavedMaps();
  }, [loadSavedMaps, showSavedPlansPanel]);

  useEffect(() => {
    setIsComparisonMode(false);
    setComparisonPlanIndexes([]);
    setComparisonMessage(null);
  }, [generatedPlans]);

  useEffect(() => {
    if (!isSaveDialogOpen) {
      return;
    }

    const selectedRank =
      selectedPlan && typeof selectedPlan.rank === 'number' ? String(selectedPlan.rank) : '';
    setSaveMapSelectedRank(selectedRank);
    if (!saveMapName.trim()) {
      setSaveMapName(`Saved Plan ${new Date().toISOString().slice(0, 16).replace('T', ' ')}`);
    }
    setSaveMapError(null);
  }, [isSaveDialogOpen, saveMapName, selectedPlan]);

  const handleSaveMap = useCallback(async (options?: { quickSave?: boolean }) => {
    const trimmedName = options?.quickSave
      ? buildDefaultSavedMapName()
      : saveMapName.trim();
    if (!trimmedName) {
      const message = 'Map name is required.';
      setSaveMapError(message);
      toast.error(message);
      return;
    }

    if (!optimizationResultForSave) {
      const message = 'No generated optimization result is available to save.';
      setSaveMapError(message);
      toast.error(message);
      return;
    }

    if (!Array.isArray(inputParcelsForSave) || inputParcelsForSave.length === 0) {
      const message = 'No parcel features are loaded for this optimization result.';
      setSaveMapError(message);
      toast.error(message);
      return;
    }

    setIsSavingMap(true);
    setSaveMapError(null);

    try {
      const selectedRank =
        options?.quickSave
          ? selectedPlan?.rank ?? null
          : saveMapSelectedRank.trim().length > 0
            ? Number(saveMapSelectedRank)
            : selectedPlan?.rank ?? null;

      await apiClient.saveGeneratedMap({
        name: trimmedName,
        description: options?.quickSave ? null : saveMapDescription.trim() || null,
        selected_plan_rank: Number.isFinite(selectedRank as number)
          ? (selectedRank as number)
          : null,
        input_parcels: inputParcelsForSave,
        optimization_result: optimizationResultForSave,
      });

      toast.success('Saved map successfully.');
      setIsSaveDialogOpen(false);
      setShowSavedPlansPanel(true);
      await loadSavedMaps();
    } catch (error: any) {
      const message = typeof error?.message === 'string' ? error.message : 'Failed to save map.';
      setSaveMapError(message);
      toast.error(message);
    } finally {
      setIsSavingMap(false);
    }
  }, [
    inputParcelsForSave,
    loadSavedMaps,
    optimizationResultForSave,
    saveMapDescription,
    saveMapName,
    saveMapSelectedRank,
    selectedPlan,
  ]);

  const handleOpenSavedMap = useCallback(
    async (savedMapId: number) => {
      setOpeningSavedMapId(savedMapId);
      try {
        const savedMap = await apiClient.getSavedMap(savedMapId);
        const optimizationResult = savedMap.optimization_result as SpatialOptimizationResponse;

        if (
          !optimizationResult ||
          !Array.isArray(optimizationResult.plans) ||
          optimizationResult.plans.length === 0
        ) {
          toast.error('Saved map does not contain valid optimization plans.');
          return;
        }

        if (Array.isArray(savedMap.input_parcels) && savedMap.input_parcels.length > 0) {
          registerLoadedParcelFeatures(savedMap.input_parcels);
        }

        storeOptimizationResult(optimizationResult);

        let restoredPlanIndex = 0;
        if (typeof savedMap.selected_plan_rank === 'number') {
          const matchedIndex = optimizationResult.plans.findIndex(
            (plan) => Number(plan.rank) === Number(savedMap.selected_plan_rank)
          );
          if (matchedIndex >= 0) {
            restoredPlanIndex = matchedIndex;
          }
        }
        setActivePlanIndex(restoredPlanIndex);

        setLoadedSavedMapName(savedMap.name);
        toast.success(`Loaded saved map "${savedMap.name}".`);
      } catch (error: any) {
        const message =
          typeof error?.message === 'string' ? error.message : 'Failed to open saved map.';
        toast.error(message);
      } finally {
        setOpeningSavedMapId(null);
      }
    },
    [registerLoadedParcelFeatures, setActivePlanIndex, storeOptimizationResult]
  );

  const handleDeleteSavedMap = useCallback(
    async (savedMapId: number) => {
      const confirmDelete = window.confirm('Delete this saved map?');
      if (!confirmDelete) {
        return;
      }

      setDeletingSavedMapId(savedMapId);
      try {
        await apiClient.deleteSavedMap(savedMapId);
        toast.success('Saved map deleted.');
        await loadSavedMaps();
      } catch (error: any) {
        const message =
          typeof error?.message === 'string' ? error.message : 'Failed to delete saved map.';
        toast.error(message);
      } finally {
        setDeletingSavedMapId(null);
      }
    },
    [loadSavedMaps]
  );

  const handleToggleComparisonPlan = useCallback((planIndex: number) => {
    setComparisonPlanIndexes((prev) => {
      if (prev.includes(planIndex)) {
        setComparisonMessage(null);
        return prev.filter((index) => index !== planIndex);
      }

      if (prev.length >= 3) {
        setComparisonMessage('You can compare up to 3 plans at once.');
        return prev;
      }

      setComparisonMessage(null);
      return [...prev, planIndex].sort((left, right) => left - right);
    });
  }, []);

  const handleClearComparison = useCallback(() => {
    setComparisonPlanIndexes([]);
    setComparisonMessage(null);
  }, []);

  const handleToggleComparisonMode = useCallback(() => {
    setIsComparisonMode((prev) => {
      const next = !prev;
      if (!next) {
        setComparisonPlanIndexes([]);
        setComparisonMessage(null);
      }
      return next;
    });
  }, []);

  const handlePlanParcelHover = useCallback(
    (apn: string | null) => {
      if (!apn) {
        setHoveredPlanParcel(null);
        return;
      }

      const assignedUse = selectedPlanAssignments.get(apn);
      if (!assignedUse) {
        setHoveredPlanParcel(null);
        return;
      }

      setHoveredPlanParcel({ apn, assignedUse });
    },
    [selectedPlanAssignments]
  );

  const handlePlanParcelSelect = useCallback(
    (apn: string, properties: any, feature: any) => {
      const assignedUse = selectedPlanAssignments.get(apn);
      const nextRequestId = assignmentRequestIdRef.current + 1;
      assignmentRequestIdRef.current = nextRequestId;
      setPinnedPlanParcel({ apn, assignedUse: assignedUse ?? null });
      setAssignmentExplanation(null);

      if (!assignedUse) {
        setIsLoadingAssignmentExplanation(false);
        setAssignmentExplanationMessage(`Parcel ${apn} is not assigned in the selected plan.`);
        return;
      }

      setAssignmentExplanationMessage(null);
      setIsLoadingAssignmentExplanation(true);

      const loadedFeature = loadedFeatureById.get(apn);
      const parcelProperties =
        properties ?? feature?.properties ?? loadedFeature?.properties ?? {};

      const includeSpatialContext = Boolean(
        latestOptimization?.settings?.use_spatial_compatibility && selectedPlan
      );
      const planAssignmentsForExplanation =
        selectedPlan?.assignments.map((assignment) => ({
          parcel_id: assignment.parcel_id,
          use_label: assignment.use_label,
        })) ?? [];
      const planParcelsForExplanation = includeSpatialContext
        ? planAssignmentsForExplanation
            .map((assignment) => loadedFeatureById.get(assignment.parcel_id))
            .filter(Boolean)
        : [];

      void apiClient
        .explainSpatialAssignment({
          parcel_id: apn,
          parcel_properties: parcelProperties,
          assigned_use: assignedUse,
          target_mix: latestOptimization?.settings?.target_mix ?? {},
          ...(includeSpatialContext
            ? {
                use_spatial_compatibility: true,
                spatial_neighbor_radius_m:
                  latestOptimization?.settings?.spatial_neighbor_radius_m ?? 250,
                plan_assignments: planAssignmentsForExplanation,
                plan_parcels: planParcelsForExplanation,
              }
            : {}),
        })
        .then((result) => {
          if (assignmentRequestIdRef.current !== nextRequestId) return;
          setAssignmentExplanation(result);
          setAssignmentExplanationMessage(null);
        })
        .catch((error: any) => {
          if (assignmentRequestIdRef.current !== nextRequestId) return;
          const message =
            typeof error?.message === 'string'
              ? error.message
              : 'Failed to load assignment explanation.';
          setAssignmentExplanation(null);
          setAssignmentExplanationMessage(message);
        })
        .finally(() => {
          if (assignmentRequestIdRef.current !== nextRequestId) return;
          setIsLoadingAssignmentExplanation(false);
        });
    },
    [
      latestOptimization?.settings?.spatial_neighbor_radius_m,
      latestOptimization?.settings?.target_mix,
      latestOptimization?.settings?.use_spatial_compatibility,
      loadedFeatureById,
      selectedPlan,
      selectedPlanAssignments,
    ]
  );

  // Load plan overlay layers
  useEffect(() => {
    if (!showPlanOverlays) {
      setPlanOverlayLayers({});
      return;
    }

    const visibleLayers = OVERLAY_LAYER_KEYS.filter((layerKey) => overlayVisibility[layerKey]);
    if (visibleLayers.length === 0) {
      setPlanOverlayLayers({});
      return;
    }

    const candidatePlanId = getOverlayCandidatePlanId(activePlanIndex);
    let cancelled = false;

    const fetchPlanOverlayLayer = async (
      planId: string,
      layerKey: SpatialOverlayLayerKey
    ): Promise<any | null> => {
      const cacheKey = `${planId}:${layerKey}`;
      const cachedLayer = overlayLayerCacheRef.current.get(cacheKey);
      if (cachedLayer) {
        return cachedLayer;
      }

      const layerUrl = `/data/geovision/spatial/layouts/${planId}/${layerKey}.geojson`;
      try {
        const response = await fetch(layerUrl);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = await response.json();
        if (!payload?.features || !Array.isArray(payload.features)) {
          throw new Error('Missing feature array');
        }
        overlayLayerCacheRef.current.set(cacheKey, payload);
        return payload;
      } catch (error) {
        console.warn('[PlanGalleryOverlay] failed to load layer', {
          planId,
          layerKey,
          layerUrl,
          error,
        });
        return null;
      }
    };

    const loadPlanOverlayLayers = async () => {
      const loaded: Partial<Record<SpatialOverlayLayerKey, any>> = {};
      const resolution = await resolveOverlayPlanId({
        candidatePlanId,
        visibleLayers,
        getLayerData: fetchPlanOverlayLayer,
      });
      const resolvedPlanId = resolution.planId;

      if (resolution.usedFallback) {
        const warningKey = `${candidatePlanId}->${resolvedPlanId}:${resolution.validationLayerKey}`;
        if (!overlayFallbackWarningsRef.current.has(warningKey)) {
          overlayFallbackWarningsRef.current.add(warningKey);
          console.warn('[PlanGalleryOverlay] using fallback overlay plan', {
            candidatePlanId,
            resolvedPlanId,
            validationLayerKey: resolution.validationLayerKey,
            reason: resolution.fallbackReason,
          });
        }
      }

      await Promise.all(
        visibleLayers.map(async (layerKey) => {
          const payload = await fetchPlanOverlayLayer(resolvedPlanId, layerKey);
          if (payload) {
            loaded[layerKey] = payload;
          }
        })
      );

      if (!cancelled) {
        setPlanOverlayLayers(loaded);
      }
    };

    loadPlanOverlayLayers();
    return () => {
      cancelled = true;
    };
  }, [showPlanOverlays, overlayVisibility, activePlanIndex]);

  /** Generate planner-ready PDF report for selected plan */
  const handleGenerateReport = async () => {
    if (!selectedPlan) {
      toast.error('Select a plan before generating a report.');
      return;
    }
   
    setIsGeneratingReport(true);
    try {
      const { jsPDF } = await import('jspdf');
      const selectedPlanIndex = Math.min(activePlanIndex, generatedPlans.length - 1);
      const selectedPlanNumber = selectedPlanIndex + 1;
      const selectedPlanLabel = `Plan ${selectedPlanNumber}`;
      const generatedAt = new Date();
      const targetMix = latestOptimization?.settings?.target_mix ?? null;
      const selectedObjectives = Array.isArray(selectedPlan.objectives)
        ? selectedPlan.objectives
        : [];
      const selectedBadges = planBadgesByIndex[selectedPlanIndex] ?? [];
      const reportSummary = buildPlanReportSummary({
        selectedPlan,
        selectedPlanIndex,
        plans: generatedPlans,
        objectiveNames,
        targetMix,
        parcelFeatureById: loadedFeatureById,
        badgesByPlan: planBadgesByIndex,
      });
      const mapImage = await capturePlanMapImage(reportMapRef.current);
      const activeOverlayLabels = OVERLAY_LAYER_KEYS.filter(
        (layerKey) => overlayVisibility[layerKey]
      ).map((layerKey) => OVERLAY_LAYER_LABELS[layerKey]);
      const overlaySummary = showPlanOverlays
        ? activeOverlayLabels.length > 0
          ? activeOverlayLabels.join(', ')
          : 'Enabled (no overlay layers selected)'
        : 'Disabled';

      const doc = new jsPDF({
        orientation: 'portrait',
        unit: 'pt',
        format: 'a4',
      });
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = 48;
      const contentWidth = pageWidth - margin * 2;
      const tableBorderColor = [210, 222, 238] as [number, number, number];
      let cursorY = margin;

      const ensureSpace = (height: number) => {
        if (cursorY + height <= pageHeight - margin) return;
        doc.addPage();
        cursorY = margin;
      };

      const addSectionTitle = (title: string) => {
        ensureSpace(26);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(14);
        doc.setTextColor(15, 31, 61);
        doc.text(title, margin, cursorY);
        cursorY += 20;
      };

      const addParagraph = (
        text: string,
        options: { italic?: boolean; color?: [number, number, number] } = {}
      ) => {
        const lines = doc.splitTextToSize(text, contentWidth);
        ensureSpace(lines.length * 12 + 8);
        doc.setFont('helvetica', options.italic ? 'italic' : 'normal');
        doc.setFontSize(10);
        doc.setTextColor(...(options.color ?? [35, 53, 78]));
        doc.text(lines, margin, cursorY);
        cursorY += lines.length * 12 + 6;
      };

      const addKeyValue = (label: string, value: string) => {
        ensureSpace(16);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(10);
        doc.setTextColor(15, 31, 61);
        doc.text(label, margin, cursorY);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(35, 53, 78);
        const lines = doc.splitTextToSize(value, contentWidth - 190);
        doc.text(lines, margin + 190, cursorY);
        cursorY += Math.max(14, lines.length * 12);
      };

      const addBulletList = (items: string[]) => {
        for (const item of items) {
          const lines = doc.splitTextToSize(item, contentWidth - 14);
          ensureSpace(lines.length * 12 + 4);
          doc.setFont('helvetica', 'normal');
          doc.setFontSize(10);
          doc.setTextColor(35, 53, 78);
          doc.text('-', margin, cursorY);
          doc.text(lines, margin + 14, cursorY);
          cursorY += lines.length * 12 + 4;
        }
      };

      const addDivider = () => {
        ensureSpace(16);
        doc.setDrawColor(202, 214, 233);
        doc.setLineWidth(0.8);
        doc.line(margin, cursorY, pageWidth - margin, cursorY);
        cursorY += 14;
      };

      const formatPercent = (value: number | null | undefined) =>
        value === null || value === undefined || !Number.isFinite(value)
          ? 'N/A'
          : `${value.toFixed(1)}%`;
      const formatPoints = (value: number | null | undefined) =>
        value === null || value === undefined || !Number.isFinite(value)
          ? 'N/A'
          : `${value.toFixed(1)} pts`;
      const formatCount = (value: number | null | undefined) =>
        value === null || value === undefined || !Number.isFinite(value) ? 'N/A' : String(value);
      const formatObjectiveForReport = (value: number | null | undefined) =>
        value === null || value === undefined || !Number.isFinite(value)
          ? 'N/A'
          : formatObjectiveValue(value);
      const severityLabel = (severity: ConflictSeverity) => severity;

      const addTable = ({
        headers,
        rows,
        widths,
        fontSize = 8,
      }: {
        headers: string[];
        rows: string[][];
        widths: number[];
        fontSize?: number;
      }) => {
        const rowPadding = 4;
        const lineHeight = fontSize + 3;
        const headerHeight = lineHeight + rowPadding * 2;
        const tableWidth = widths.reduce((sum, width) => sum + width, 0);

        const drawHeader = () => {
          ensureSpace(headerHeight);
          doc.setFillColor(232, 240, 252);
          doc.setDrawColor(...tableBorderColor);
          doc.rect(margin, cursorY, tableWidth, headerHeight, 'FD');
          let x = margin;
          doc.setFont('helvetica', 'bold');
          doc.setFontSize(fontSize);
          doc.setTextColor(15, 31, 61);
          headers.forEach((header, index) => {
            doc.text(header, x + rowPadding, cursorY + rowPadding + fontSize);
            x += widths[index];
          });
          cursorY += headerHeight;
        };

        drawHeader();
        rows.forEach((row, rowIndex) => {
          const wrappedCells = row.map((cell, index) =>
            doc.splitTextToSize(String(cell ?? ''), Math.max(20, widths[index] - rowPadding * 2))
          );
          const rowHeight =
            Math.max(1, ...wrappedCells.map((lines) => lines.length)) * lineHeight +
            rowPadding * 2;
          if (cursorY + rowHeight > pageHeight - margin) {
            doc.addPage();
            cursorY = margin;
            drawHeader();
          }

          const fill = rowIndex % 2 === 0 ? 255 : 248;
          doc.setFillColor(fill, fill === 255 ? 255 : 251, 255);
          doc.setDrawColor(...tableBorderColor);
          doc.rect(margin, cursorY, tableWidth, rowHeight, 'FD');
          let x = margin;
          doc.setFont('helvetica', 'normal');
          doc.setFontSize(fontSize);
          doc.setTextColor(35, 53, 78);
          wrappedCells.forEach((lines, index) => {
            doc.text(lines, x + rowPadding, cursorY + rowPadding + fontSize);
            x += widths[index];
          });
          cursorY += rowHeight;
        });
        cursorY += 8;
      };

      doc.setFillColor(15, 31, 61);
      doc.rect(0, 0, pageWidth, 126, 'F');
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(13);
      doc.setTextColor(79, 255, 167);
      doc.text('GeoVision', margin, 38);
      doc.setFontSize(23);
      doc.setTextColor(232, 240, 252);
      doc.text('Land Use Plan Report', margin, 68);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(11);
      doc.text(
        'AI-assisted land-use planning summary for selected parcel assignments',
        margin,
        90
      );
      doc.text(`${selectedPlanLabel} | Generated ${formatTimestamp(generatedAt)}`, margin, 110);

      cursorY = 154;
      addSectionTitle('Selected Plan Map');
      if (mapImage) {
        const imageHeight = Math.min(300, contentWidth * 0.56);
        ensureSpace(imageHeight + 34);
        doc.addImage(mapImage, 'PNG', margin, cursorY, contentWidth, imageHeight);
        cursorY += imageHeight + 14;
        addParagraph('Figure 1: Generated land-use assignment map for the selected plan.', {
          italic: true,
          color: [94, 112, 136],
        });
      } else {
        addParagraph('Map image could not be captured in this export.', {
          italic: true,
          color: [150, 72, 0],
        });
      }
      addDivider();

      addSectionTitle('Executive Summary');
      addParagraph(reportSummary.executiveSummary);
      addDivider();

      addSectionTitle('Plan Metadata');
      addKeyValue('Project', 'GeoVision');
      addKeyValue('Region', selectedRegion || 'N/A');
      addKeyValue('Selected Plan', selectedPlanLabel);
      addKeyValue('Report Generated', formatTimestamp(generatedAt));
      addKeyValue('Total Assignments', formatCount(reportSummary.metrics.totalAssigned));
      addKeyValue('Mapped Assignments', `${mappedAssignmentsCount}/${selectedPlanAssignmentCount}`);
      addKeyValue('Overlay Context', overlaySummary);
      addKeyValue('Prepared By', settings.userAccount.fullName || 'N/A');
      addKeyValue('Role', settings.userAccount.plannerRole || 'N/A');
      addKeyValue('Organization', settings.userAccount.organization || 'N/A');
      addDivider();

      addSectionTitle('Recommendation Badges');
      if (selectedBadges.length > 0) {
        selectedBadges.forEach((badge) => {
          addKeyValue(`Badge: ${badge.label}`, badge.description);
        });
      } else {
        addParagraph('No recommendation badge was available for the selected plan.');
      }
      addDivider();

      addSectionTitle('Planning Outcomes');
      const pm = selectedPlan.planning_metrics;
      if (pm) {
        addKeyValue('Estimated Housing Units', pm.housing_units.toLocaleString());
        addKeyValue('Estimated Residents', pm.estimated_residents.toLocaleString());
        addKeyValue('Green Space per Resident', `${pm.green_space_per_resident_m2} m² (WHO target: ${pm.who_green_target_m2} m²)`);
        addKeyValue('Est. Annual Tax Revenue', fmtTax(pm.estimated_annual_tax_usd));
        addKeyValue('Built Parcels on Hazard Land', `${pm.hazard_built_parcels} of ${pm.total_parcels}`);
        addKeyValue('Total Area', `${Math.round(pm.area_m2.total).toLocaleString()} m²`);
      }
      addDivider();

      

      addSectionTitle('Optimization Indicators');
      const objectiveTotal = selectedObjectives.reduce((sum, value) => {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? sum + numericValue : sum;
}, 0);

      addKeyValue('Composite Objective Score', formatObjectiveValue(objectiveTotal));
      selectedPlan.objectives.forEach((value, objectiveIndex) => {
        const rawObjectiveName = objectiveNames[objectiveIndex] || `objective_${objectiveIndex}`;
        const objectiveMeta = getObjectiveMeta(rawObjectiveName);
        addKeyValue(objectiveMeta.label, formatObjectiveForReport(value));
      });
      addParagraph(
        'Objective values are planning model scores. Lower values generally indicate better performance unless noted otherwise.',
        {
          italic: true,
          color: [94, 112, 136],
        }
      );
      addDivider();

      addSectionTitle('Top Conflicts / Warnings');
      const topConflicts = reportSummary.conflicts.slice(0, 10);
      if (topConflicts.length > 0) {
        addTable({
          headers: ['Parcel ID', 'Assigned Use', 'Issue', 'Severity'],
          rows: topConflicts.map((conflict) => [
            conflict.parcelId,
            conflict.assignedUse,
            conflict.issue,
            severityLabel(conflict.severity),
          ]),
          widths: [86, 84, 260, 60],
          fontSize: 7.5,
        });
      } else {
        addParagraph('No major parcel-level conflicts could be computed from the available frontend data.');
      }
      addDivider();

      addSectionTitle('High-Risk Built Parcels');
      const highRiskRows = reportSummary.highRiskBuiltParcels.slice(0, 10);
      if (highRiskRows.length > 0) {
        addTable({
          headers: ['Parcel ID', 'Assigned Use', 'Risk / Flags', 'Review Note'],
          rows: highRiskRows.map((parcel) => [
            parcel.parcelId,
            parcel.assignedUse,
            parcel.hazardFlags.length > 0
              ? `${parcel.riskLabel}; ${parcel.hazardFlags.join(', ')}`
              : parcel.riskLabel,
            'Review environmental exposure before approving built-use assignment.',
          ]),
          widths: [86, 84, 150, 170],
          fontSize: 7.5,
        });
      } else {
        addParagraph('No high-risk built-use parcels were identified from available frontend data.');
      }
      addDivider();

      addSectionTitle('Plan Comparison Table');
      addTable({
        headers: [
          'Plan',
          'Badges',
          'Res %',
          'Com %',
          'Ind %',
          'Green %',
          'Target Dev.',
          'Risk Built',
          'Zoning',
        ],
        rows: reportSummary.planComparisonRows.map((row) => [
          row.planLabel,
          row.badges,
          formatPercent(row.residentialPercent),
          formatPercent(row.commercialPercent),
          formatPercent(row.industrialPercent),
          formatPercent(row.greenPercent),
          formatPoints(row.targetDeviation),
          formatCount(row.highRiskBuiltCount),
          formatCount(row.possibleZoningConflictCount),
        ]),
        widths: [38, 106, 42, 42, 42, 48, 62, 55, 55],
        fontSize: 6.8,
      });
      addDivider();

      addSectionTitle('Why This Plan?');
      addParagraph(reportSummary.selectedPlanExplanation);
      addDivider();

      addSectionTitle('Assumptions and Warnings');
      addBulletList([
        'This report is AI-assisted and should be reviewed by a qualified planner.',
        'Zoning conflicts are estimated from available parcel attributes and may require regulatory confirmation.',
        'Environmental risk is based on available model outputs and parcel flags.',
        'Generated land-use assignments are planning alternatives, not final regulatory decisions.',
        'Map export reflects the visible selected plan at the time the report was generated.',
      ]);
      addDivider();

      addSectionTitle('Appendix: Objective Meanings');
      if (reportSummary.objectiveMeanings.length > 0) {
        addTable({
          headers: ['Objective', 'Meaning'],
          rows: reportSummary.objectiveMeanings.map((objective) => [
            objective.label,
            objective.explanation,
          ]),
          widths: [150, 340],
          fontSize: 8,
        });
      } else {
        addParagraph('No objective names were available in the optimization response.');
      }

      const pageCount = doc.getNumberOfPages();
      for (let pageNumber = 1; pageNumber <= pageCount; pageNumber += 1) {
        doc.setPage(pageNumber);
        doc.setFont('helvetica', 'italic');
        doc.setFontSize(8);
        doc.setTextColor(94, 112, 136);
        doc.text(
          `Prepared for ${settings.userAccount.organization || 'N/A'} by ${
            settings.userAccount.fullName || 'GeoVision'
          }. Page ${pageNumber} of ${pageCount}.`,
          margin,
          pageHeight - 24
        );
      }

      const timestampForFile = generatedAt.toISOString().replace(/[:]/g, '-').slice(0, 16);
      doc.save(`plan-${selectedPlanNumber}-planner-report-${timestampForFile}.pdf`);
      toast.success(`${selectedPlanLabel} planner PDF exported.`);
    } catch (error) {
      console.error('[PlanReport] failed to generate report', error);
      toast.error('Unable to generate plan report PDF.');
    } finally {
      setIsGeneratingReport(false);
    }
  };

  return (
    <DashboardLayout
      metrics={metrics}
      simulationTime={simulationTime}
      zones={zones}
      selectedRegion={selectedRegion}
    >
      <div className="plan-gallery-page custom-scrollbar">
        {/* Header */}
        <header className="gallery-header">
          <div className="gallery-header__content">
            <div className="gallery-header__title-group">
              <h1 className="gallery-header__title">Plan Gallery</h1>
              <p className="gallery-header__description">
                Browse generated plans, visualize allocations on map, and compare outcomes.
              </p>
            </div>
            <div className="gallery-header__right">
              <span className="gallery-header__count">Plans: {generatedPlans.length}</span>
              <div className="gallery-header__actions">
                <button
                  type="button"
                  className="gallery-header__action-btn"
                  disabled={!canSaveMap || isSavingMap}
                  onClick={() => {
                    void handleSaveMap({ quickSave: true });
                  }}
                >
                  {isSavingMap ? 'Saving...' : 'Save Map'}
                </button>
                <button
                  type="button"
                  className="gallery-header__action-btn"
                  disabled={generatedPlans.length === 0}
                  onClick={handleToggleComparisonMode}
                >
                  {isComparisonMode ? 'Exit Compare' : 'Compare Plans'}
                </button>
                <button
                  type="button"
                  className="gallery-header__action-btn"
                  onClick={() => {
                    setShowSavedPlansPanel((prev) => !prev);
                  }}
                >
                  {showSavedPlansPanel ? 'Hide Saved Plans' : 'View Saved Plans'}
                </button>
              </div>
            </div>
          </div>

          {loadedSavedMapName && (
            <div className="saved-load-banner">Loaded from saved maps: {loadedSavedMapName}</div>
          )}

          {generatedPlans.length === 0 ? (
            <div className="empty-plans">
              No plans yet. Generate plans from the Environmental Agent to view them here.
            </div>
          ) : (
            <div className="plans-scroll-container">
              <div className="plans-flex">
                {generatedPlans.map((plan, index) => {
                  const mix = computeMix(plan);
                  const isActive = index === activePlanIndex;
                  const badges = planBadgesByIndex[index] ?? [];
                  const isCompared = comparisonPlanIndexes.includes(index);
                  const compareLimitReached = comparisonPlanIndexes.length >= 3 && !isCompared;
                  return (
                    <article
                      key={`plan-card-${index}`}
                      className={`plan-card ${isActive ? 'plan-card--active' : ''} ${
                        isCompared ? 'plan-card--compared' : ''
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => setActivePlanIndex(index)}
                        className="plan-card__preview"
                        aria-pressed={isActive}
                      >
                        <span className="plan-card__title">Plan {index + 1}</span>
                        {badges.length > 0 && (
                          <div className="plan-card__badges" aria-label={`Plan ${index + 1} badges`}>
                            {badges.map((badge) => (
                              <span
                                key={badge.label}
                                className={`plan-badge plan-badge--${badge.variant ?? 'neutral'}`}
                                title={badge.description}
                              >
                                {badge.label}
                              </span>
                            ))}
                          </div>
                        )}
                        <div className="plan-card__mix">
                          <span>Res {mix.residential.toFixed(0)}%</span>
                          <span>Com {mix.commercial.toFixed(0)}%</span>
                          <span>Ind {mix.industrial.toFixed(0)}%</span>
                          <span>Green {mix.green.toFixed(0)}%</span>
                        </div>
                      </button>
                      {isComparisonMode && (
                        <label
                          className={`plan-card__compare ${
                            compareLimitReached ? 'plan-card__compare--disabled' : ''
                          }`}
                          title={
                            compareLimitReached
                              ? 'You can compare up to 3 plans at once.'
                              : 'Include this plan in the comparison dashboard.'
                          }
                        >
                          <input
                            type="checkbox"
                            checked={isCompared}
                            aria-disabled={compareLimitReached}
                            onChange={() => handleToggleComparisonPlan(index)}
                          />
                          <span>Compare</span>
                        </label>
                      )}
                    </article>
                  );
                })}
              </div>
            </div>
          )}

          {isComparisonMode && generatedPlans.length > 0 && (
            <div className="comparison-controls">
              <div className="comparison-controls__copy">
                <span>
                  {comparisonPlanIndexes.length < 2
                    ? 'Select 2 to 3 plans to compare planning metrics.'
                    : `${comparisonPlanIndexes.length} plans selected for comparison.`}
                </span>
                {comparisonMessage && (
                  <span className="comparison-controls__message">{comparisonMessage}</span>
                )}
              </div>
              {comparisonPlanIndexes.length > 0 && (
                <button
                  type="button"
                  className="comparison-controls__clear"
                  onClick={handleClearComparison}
                >
                  Clear comparison
                </button>
              )}
            </div>
          )}

          {showSavedPlansPanel && (
            <section className="saved-plans-panel">
              <div className="saved-plans-panel__header">
                <h2>Saved Plans</h2>
                <div className="saved-plans-panel__meta">Total: {savedMapsTotal}</div>
              </div>

              {isLoadingSavedMaps ? (
                <p className="saved-plans-panel__state">Loading saved plans...</p>
              ) : savedMapsError ? (
                <p className="saved-plans-panel__state">{savedMapsError}</p>
              ) : savedMaps.length === 0 ? (
                <p className="saved-plans-panel__state">No saved plans yet.</p>
              ) : (
                <div className="saved-plans-list">
                  {savedMaps.map((savedMap) => {
                    const updatedAt = savedMap.updated_at || savedMap.created_at;
                    const updatedDate = new Date(updatedAt);
                    return (
                      <article key={savedMap.id} className="saved-plan-card">
                        <div className="saved-plan-card__content">
                          <div className="saved-plan-card__title-row">
                            <h3>{savedMap.name}</h3>
                            <span>
                              {Number.isNaN(updatedDate.valueOf())
                                ? updatedAt
                                : formatTimestamp(updatedDate)}
                            </span>
                          </div>
                          {savedMap.description && <p>{savedMap.description}</p>}
                          <div className="saved-plan-card__meta">
                            <span>Parcels: {savedMap.parcel_count}</span>
                            <span>Plans: {savedMap.plan_count}</span>
                            <span>
                              Selected rank:{' '}
                              {savedMap.selected_plan_rank === null
                                ? 'None'
                                : savedMap.selected_plan_rank}
                            </span>
                          </div>
                        </div>
                        <div className="saved-plan-card__actions">
                          <button
                            type="button"
                            className="saved-plan-btn"
                            disabled={openingSavedMapId === savedMap.id}
                            onClick={() => {
                              void handleOpenSavedMap(savedMap.id);
                            }}
                          >
                            {openingSavedMapId === savedMap.id ? 'Opening...' : 'Open'}
                          </button>
                          <button
                            type="button"
                            className="saved-plan-btn saved-plan-btn--danger"
                            disabled={deletingSavedMapId === savedMap.id}
                            onClick={() => {
                              void handleDeleteSavedMap(savedMap.id);
                            }}
                          >
                            {deletingSavedMapId === savedMap.id ? 'Deleting...' : 'Delete'}
                          </button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          )}
        </header>

        {/* Split View */}
        <div className="gallery-split-view">
          {/* Map Section */}
          <section className="map-section">
            <div className="map-section__header">
              <h2 className="map-section__title">Plan Map Visualization</h2>
              <div className="map-section__actions">
                <span className="map-section__meta">
                  Total parcels loaded: {totalLoadedParcels} | mapped assignments: {mappedAssignmentsCount}/{selectedPlanAssignmentCount}
                </span>
                <button
                  type="button"
                  onClick={toggle3D}
                  className="px-3 py-1.5 bg-[#0B1E39]/80 border border-[#4FFFA7]/40 rounded text-xs text-[#4FFFA7] hover:bg-[#4FFFA7]/10 transition-colors"
                >
                  {use3D ? '🗺️ 2D' : '🧊 3D'}
                </button>
                <button
                  type="button"
                  onClick={handleGenerateReport}
                  disabled={!selectedPlan || isGeneratingReport}
                  className="report-btn"
                  title="Export a planner-ready PDF report for the currently selected plan."
                >
                  {isGeneratingReport ? 'Generating PDF...' : 'Export Planner PDF'}
                </button>
              </div>
            </div>
            <div ref={reportMapRef} className="map-wrapper map-container">
              {use3D ? (
                <DeckGLMap
                  geoJsonUrl="/parcels_env_risk_clipped.geojson"
                  scoresById={EMPTY_SCORES}
                  colorMode="land_use_plan"
                  landUsePlanByParcel={selectedPlanAssignments}
                  selectedParcelIds={Array.from(selectedPlanAssignments.keys())}
                  onParcelHover={handlePlanParcelHover}
                  onParcelSelect={handlePlanParcelSelect}
                  autoFitToData={true}
                />
              ) : (
                <ParcelMap
                  geoJsonUrl="/parcels_env_risk_clipped.geojson"
                  scoresById={EMPTY_SCORES}
                  colorMode="land_use_plan"
                  landUsePlanByParcel={selectedPlanAssignments}
                  selectedParcelIds={Array.from(selectedPlanAssignments.keys())}
                  showPlanOverlays={showPlanOverlays}
                  planOverlayLayers={planOverlayLayers}
                  onFeaturesLoaded={registerLoadedParcelFeatures}
                  onParcelHover={handlePlanParcelHover}
                  onParcelSelect={handlePlanParcelSelect}
                  autoFitToData={true}
                  lockViewportToData={true}
                />
              )}
              {hoveredPlanParcel && (
                <div className="plan-assignment-hover" aria-live="polite">
                  <div className="plan-assignment-hover__label">Assigned Parcel</div>
                  <div className="plan-assignment-hover__apn">{hoveredPlanParcel.apn}</div>
                  <div className="plan-assignment-hover__use">
                    {formatAssignmentUseLabel(hoveredPlanParcel.assignedUse)}
                  </div>
                </div>
              )}
              <SpatialMapLegend
                colorMode="land_use_plan"
                showPlanOverlays={showPlanOverlays}
                overlayVisibility={overlayVisibility}
                referenceLayerVisibility={EMPTY_REFERENCE_LAYER_VISIBILITY}
                anchor="top-right"
              />
            </div>
          </section>

          {/* Comparison Section */}
          <aside className="comparison-section custom-scrollbar">
            {/* Overlay Controls */}
            <div className="overlay-controls">
              <label className="overlay-toggle">
                <div className="overlay-toggle__content">
                  <div className="overlay-toggle__title">Show Plan Overlays</div>
                  <div className="overlay-toggle__description">
                    Display plan overlay visualization
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={showPlanOverlays}
                  onChange={(e) => setShowPlanOverlays(e.target.checked)}
                  className="overlay-toggle__checkbox"
                />
              </label>

              {showPlanOverlays && (
                <div className="overlay-layers">
                  <div className="overlay-layers__title">Overlay Layers</div>
                  {OVERLAY_LAYER_KEYS.map((layerKey) => (
                    <label key={layerKey} className="overlay-layer-item">
                      <span>{OVERLAY_LAYER_LABELS[layerKey]}</span>
                      <input
                        type="checkbox"
                        checked={overlayVisibility[layerKey]}
                        onChange={(e) =>
                          setOverlayVisibility((prev) => ({ ...prev, [layerKey]: e.target.checked }))
                        }
                        className="overlay-layer-item__checkbox"
                      />
                    </label>
                  ))}
                </div>
              )}
            </div>

            {/* Pinned Assignment Explanation */}
            <div className="plan-assignment-explanation">
              <div className="plan-assignment-explanation__header">
                <div>
                  <h3 className="plan-assignment-explanation__title">
                    Assignment Explanation
                  </h3>
                  <p className="plan-assignment-explanation__subtitle">
                    Click an assigned parcel in the selected plan map.
                  </p>
                </div>
                {pinnedPlanParcel?.assignedUse && (
                  <span className="plan-assignment-explanation__badge">
                    {formatAssignmentUseLabel(pinnedPlanParcel.assignedUse)}
                  </span>
                )}
              </div>

              {isLoadingAssignmentExplanation ? (
                <p className="plan-assignment-explanation__state">
                  Loading explanation for parcel {pinnedPlanParcel?.apn}...
                </p>
              ) : assignmentExplanationMessage ? (
                <p className="plan-assignment-explanation__state">
                  {assignmentExplanationMessage}
                </p>
              ) : assignmentExplanation ? (
                <div className="plan-assignment-explanation__body">
                  <div className="plan-assignment-explanation__parcel">
                    Parcel {assignmentExplanation.parcel_id ?? pinnedPlanParcel?.apn}
                  </div>
                  <p className="plan-assignment-explanation__headline">
                    {assignmentExplanation.headline}
                  </p>
                  <div className="plan-assignment-explanation__metrics">
                    <div>
                      <span>Best use</span>
                      <strong>
                        {formatAssignmentUseLabel(assignmentExplanation.best_suitability_use)}
                      </strong>
                    </div>
                    <div>
                      <span>Risk</span>
                      <strong>{assignmentExplanation.risk_level}</strong>
                    </div>
                    <div>
                      <span>Assigned Suitability</span>
                      <strong>
                        {formatPercentScore(assignmentExplanation.scores.assigned_use_score)}
                      </strong>
                    </div>
                    <div>
                      <span>Environmental risk</span>
                      <strong>
                        {formatPercentScore(assignmentExplanation.scores.environmental_risk)}
                      </strong>
                    </div>
                  </div>

                  {assignmentExplanation.spatial_context && (
                    <div className="plan-assignment-explanation__details">
                      <div className="plan-assignment-explanation__details-title">
                        Spatial Context
                      </div>
                      <ul>
                        <li>
                          Nearby pairs checked:{' '}
                          {assignmentExplanation.spatial_context.neighbor_pairs_evaluated}
                        </li>
                        <li>
                          Compatible pairs:{' '}
                          {assignmentExplanation.spatial_context.compatible_pairs}
                        </li>
                        <li>
                          Conflict pairs: {assignmentExplanation.spatial_context.conflict_pairs}
                        </li>
                        {assignmentExplanation.spatial_context.industrial_residential_conflicts > 0 && (
                          <li>
                            Industrial-residential conflicts:{' '}
                            {
                              assignmentExplanation.spatial_context
                                .industrial_residential_conflicts
                            }
                          </li>
                        )}
                      </ul>
                    </div>
                  )}

                  {assignmentExplanation.reasons.length > 0 && (
                    <div className="plan-assignment-explanation__details">
                      <div className="plan-assignment-explanation__details-title">Reasons</div>
                      <ul>
                        {assignmentExplanation.reasons.slice(0, 3).map((reason) => (
                          <li key={reason}>{reason}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {assignmentExplanation.warnings.length > 0 && (
                    <div className="plan-assignment-explanation__details plan-assignment-explanation__details--warning">
                      <div className="plan-assignment-explanation__details-title">Warnings</div>
                      <ul>
                        {assignmentExplanation.warnings.slice(0, 2).map((warning) => (
                          <li key={warning}>{warning}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <p className="plan-assignment-explanation__state">
                  Hover parcels for quick assignment context. Click one to pin the full explanation.
                </p>
              )}
            </div>

            {generatedPlans.length === 0 ? (
              <p className="empty-plans">No plans available to compare.</p>
            ) : isComparisonMode ? (
              <PlanComparisonDashboard
                selectedPlans={selectedComparisonPlans}
                objectiveNames={objectiveNames}
                parcelFeatureById={loadedFeatureById}
                targetMix={latestOptimization?.settings?.target_mix ?? null}
              />
            ) : (
              <>
                <h2
                  className="comparison-section__title"
                  title="Compare each candidate plan by land-use mix and planning performance indicators."
                >
                  Plan Comparison Dashboard
                </h2>

            {generatedPlans.length === 0 ? (
              <p className="empty-plans">No plans available to compare.</p>
            ) : (
              <div className="comparison-list">
                {/* Current State Baseline */}
                {currentState && (
                  <div className="comparison-card" style={{ borderColor: '#4a5568', opacity: 0.85 }}>
                    <div className="comparison-card__header">
                      <span className="comparison-card__title" style={{ color: '#8899aa', cursor: 'default' }}>
                        Current State (Baseline)
                      </span>
                    </div>
                    <p style={{ fontSize: 11, color: '#8899aa', margin: '4px 0 8px' }}>
                      {currentState.total_hazard_parcels} of {currentState.total_parcels} parcels on hazard land.
                      All parcels currently vacant / undeveloped.
                    </p>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 12px' }}>
                      <MetricRow icon="🏠" label="Housing Units" value="0" />
                      <MetricRow icon="💰" label="Est. Tax/Year" value="$0" />
                      <MetricRow icon="🌿" label="Green/Resident" value="0 m²" />
                      <MetricRow icon="⚠️" label="Built on Hazard" value={`0 / ${currentState.total_parcels} parcels`} valueColor="#4FFFA7" />
                    </div>
                  </div>
                )}

                {generatedPlans.map((plan, index) => {
                  const mix = computeMix(plan);
                  const isActive = index === activePlanIndex;
                  const pm = plan.planning_metrics;

                    return (
                      <div
                        key={`compare-${index}`}
                        className={`comparison-card ${isActive ? 'comparison-card--active' : ''}`}
                      >
                        <div className="comparison-card__header">
                          <button
                            type="button"
                            onClick={() => setActivePlanIndex(index)}
                            className="comparison-card__title"
                            title="Select this plan to preview it on the map."
                          >
                            Plan {index + 1}
                          </button>
                        </div>

                        <div className="mix-breakdown">
                          <span title={LAND_USE_TERM_META.residential.description}>
                            {LAND_USE_TERM_META.residential.label}
                          </span>
                          <span className="mix-breakdown__value">{mix.residential.toFixed(1)}%</span>
                          <span title={LAND_USE_TERM_META.commercial.description}>
                            {LAND_USE_TERM_META.commercial.label}
                          </span>
                          <span className="mix-breakdown__value">{mix.commercial.toFixed(1)}%</span>
                          <span title={LAND_USE_TERM_META.industrial.description}>
                            {LAND_USE_TERM_META.industrial.label}
                          </span>
                          <span className="mix-breakdown__value">{mix.industrial.toFixed(1)}%</span>
                          <span title={LAND_USE_TERM_META.green.description}>
                            {LAND_USE_TERM_META.green.label}
                          </span>
                          <span className="mix-breakdown__value">{mix.green.toFixed(1)}%</span>
                        </div>

                      {pm ? (
                        <>
                          <PlanningMetricsCard pm={pm} baseline={currentState ?? null} />
                          <SpatialCompatibilityCard plan={plan} />
                        </>
                      ) : (
                        <div className="objective-score" style={{ fontSize: 11, color: '#8899aa' }}>
                          Planning metrics unavailable
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
              </>
            )}
          </aside>
        </div>

        {isComparisonMode && selectedComparisonPlans.length >= 2 && (
          <SpatialDifferenceMap
            selectedPlans={selectedComparisonPlans}
            parcelFeatureById={loadedFeatureById}
            geoJsonUrl="/parcels_env_risk_clipped.geojson"
          />
        )}

        <Dialog open={isSaveDialogOpen} onOpenChange={setIsSaveDialogOpen}>
          <DialogContent className="save-map-dialog">
            <DialogHeader>
              <DialogTitle>Save Generated Plans</DialogTitle>
              <DialogDescription>
                Save the current optimization result to your saved plans.
              </DialogDescription>
            </DialogHeader>

            <div className="save-map-dialog__form">
              <label className="save-map-dialog__field">
                <span>Map name</span>
                <input
                  className="save-map-dialog__input"
                  value={saveMapName}
                  onChange={(event) => setSaveMapName(event.target.value)}
                  placeholder="Scenario name"
                />
              </label>

              <label className="save-map-dialog__field">
                <span>Description (optional)</span>
                <textarea
                  className="save-map-dialog__textarea"
                  value={saveMapDescription}
                  onChange={(event) => setSaveMapDescription(event.target.value)}
                  rows={3}
                  placeholder="Short notes about this run"
                />
              </label>

              <label className="save-map-dialog__field">
                <span>Selected plan rank (optional)</span>
                <select
                  className="save-map-dialog__select"
                  value={saveMapSelectedRank}
                  onChange={(event) => setSaveMapSelectedRank(event.target.value)}
                >
                  <option value="">Use current selection</option>
                  {planRankOptions.map((option) => (
                    <option key={option.rank} value={String(option.rank)}>
                      Rank {option.rank}
                    </option>
                  ))}
                </select>
              </label>

              {saveMapError && <p className="save-map-dialog__error">{saveMapError}</p>}
            </div>

            <DialogFooter>
              <button
                type="button"
                className="save-map-dialog__btn save-map-dialog__btn--secondary"
                onClick={() => setIsSaveDialogOpen(false)}
                disabled={isSavingMap}
              >
                Cancel
              </button>
              <button
                type="button"
                className="save-map-dialog__btn save-map-dialog__btn--primary"
                onClick={() => {
                  void handleSaveMap();
                }}
                disabled={isSavingMap}
              >
                {isSavingMap ? 'Saving...' : 'Save'}
              </button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
}
