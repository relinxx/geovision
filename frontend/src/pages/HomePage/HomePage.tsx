/**
 * HomePage Component
 * ==================
 * Environmental Agent page for parcel inspection and spatial planning.
 * Features a three-column layout with planning controls, environmental map
 * visualization, and parcel information panel.
 * 
 * @component
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { DashboardLayout } from '../../layouts/DashboardLayout/DashboardLayout';
import { ParcelMap } from '../../components/map/ParcelMap';
import { DeckGLMap } from '../../components/map/DeckGLMap/DeckGLMap';
import { ParcelInfoSidebar } from '../../components/sidebar/ParcelInfoSidebar/ParcelInfoSidebar';
import {
  SpatialPlannerSidebar,
  type ScenarioPreset,
} from '../../components/sidebar/SpatialPlannerSidebar/SpatialPlannerSidebar';
import {
  Metrics,
  LandUseZone,
  LandUseAssignment,
  LandUseMixTargets,
  ReferenceMapLayerKey,
  ReferenceMapLayerVisibility,
  SpatialOverlayLayerKey,
  SpatialOverlayVisibility,
  CurrentStatePlanningMetrics,
  SpatialOptimizationPlan,
  ViewType,
} from '../../types';
import { toast } from 'sonner';
import { apiClient } from '../../utils/api';
import { getOverlayCandidatePlanId, resolveOverlayPlanId } from '../../utils/overlayPlanResolver';
import { usePlannerSettings } from '../../context/PlannerSettingsContext';
import { usePlannerWorkspace } from '../../context/PlannerWorkspaceContext';
import { buildLandUsePlanMap, buildSelectedFeatures, getParcelId } from '../../utils/plannerWorkspace';
import './HomePage.css';

/** Props for the HomePage component */
interface HomePageProps {
  metrics: Metrics;
  simulationTime: number;
  zones: LandUseZone[];
  selectedRegion: string;
  onOpenView: (view: ViewType) => void;
}

/** Color mode options for map visualization */
type ColorMode =
  | 'residential'
  | 'commercial'
  | 'industrial'
  | 'green'
  | 'best'
  | 'dominant'
  | 'land_use_plan'
  | 'environmental_risk';

/** Available overlay layer keys */
const OVERLAY_LAYER_KEYS: SpatialOverlayLayerKey[] = [
  'roads',
  'networks',
  'blocks',
  'green',
  'buildings',
  'plots',
  'density',
];

/** Default visibility for overlay layers */
const DEFAULT_OVERLAY_VISIBILITY: SpatialOverlayVisibility = {
  roads: true,
  networks: true,
  blocks: true,
  green: true,
  buildings: false,
  plots: false,
  density: false,
};

/** Reference layer file mappings */
const REFERENCE_LAYER_FILES: Record<ReferenceMapLayerKey, string> = {
  municipal_boundaries: 'municipal_boundaries.geojson',
  zoning_base_sd: 'zoning_base_sd.geojson',
  zoning_unincorporated: 'zoning_unincorporated.geojson',
  general_plan_land_use_sd: 'general_plan_land_use_sd.geojson',
};

/** Default visibility for reference layers */
const DEFAULT_REFERENCE_VISIBILITY: ReferenceMapLayerVisibility = {
  municipal_boundaries: false,
  zoning_base_sd: false,
  zoning_unincorporated: false,
  general_plan_land_use_sd: false,
};

/**
 * HomePage component.
 * Environmental analysis and planning workspace.
 */
export function HomePage({
  metrics,
  simulationTime,
  zones,
  selectedRegion,
  onOpenView,
}: HomePageProps) {
  const { settings, updateSettings } = usePlannerSettings();
  const {
    loadedParcelFeatures,
    loadedFeatureById,
    totalLoadedParcels,
    selectedParcelIds,
    selectedFeatureById,
    primarySelectedParcelId,
    primarySelectedParcelProps,
    generatedPlans,
    activePlanIndex,
    latestOptimization,
    registerLoadedParcelFeatures,
    addToSelection,
    toggleSelectedParcel,
    clearSelection,
    selectAllLoadedParcels,
    setPrimarySelectedParcel,
    clearGeneratedPlans,
    storeOptimizationResult,
    setActivePlanIndex,
  } = usePlannerWorkspace();

  // State for suitability scores and color mode
  const [colorMode] = useState<ColorMode>('environmental_risk');
  const suitabilityScores = useMemo(() => new Map(), []);

  // Map view mode toggle (2D Leaflet vs 3D DeckGL)
  const [use3DMap, setUse3DMap] = useState<boolean>(true);

  const [isGeneratingPlan, setIsGeneratingPlan] = useState(false);

  // Plan overlay state
  const [overlayVisibility, setOverlayVisibility] =
    useState<SpatialOverlayVisibility>(DEFAULT_OVERLAY_VISIBILITY);
  const [planOverlayLayers, setPlanOverlayLayers] = useState<
    Partial<Record<SpatialOverlayLayerKey, any>>
  >({});
  const overlayLayerCacheRef = useRef<Map<string, any>>(new Map());
  const overlayFallbackWarningsRef = useRef<Set<string>>(new Set());

  // Reference layer state
  const [referenceLayerVisibility] = useState<ReferenceMapLayerVisibility>(DEFAULT_REFERENCE_VISIBILITY);
  const [referenceMapLayers, setReferenceMapLayers] = useState<
    Partial<Record<ReferenceMapLayerKey, any>>
  >({});
  const referenceLayerCacheRef = useRef<Map<string, any>>(new Map());

  // Map features state
  // Mix targets and output plans
  const [mixTargets, setMixTargets] = useState<LandUseMixTargets>({
    residential: 35,
    commercial: 25,
    industrial: 20,
    green: 20,
  });
  const [numOutputPlans, setNumOutputPlans] = useState<number>(
    settings.growthDemand.defaultPlanAlternatives
  );
  const [useSpatialCompatibility, setUseSpatialCompatibility] = useState(false);
  const [spatialCompatibilityRadiusM, setSpatialCompatibilityRadiusM] = useState(250);
  const [plannerErrorMessage, setPlannerErrorMessage] = useState<string | null>(null);

  // Sync output plans with settings
  useEffect(() => {
    const maxAlternatives = Math.max(1, settings.growthDemand.maxPlanAlternatives);
    const preferred = Math.max(
      1,
      Math.min(settings.growthDemand.defaultPlanAlternatives, maxAlternatives)
    );
    setNumOutputPlans(preferred);
  }, [settings.growthDemand.defaultPlanAlternatives, settings.growthDemand.maxPlanAlternatives]);

  /**
   * Normalizes mix targets to percentage distribution.
   */
  const normalizeTargetMix = (mix: LandUseMixTargets): Record<string, number> => {
    const total = mix.residential + mix.commercial + mix.industrial + mix.green;
    const safeTotal = total > 0 ? total : 1;
    return {
      residential: mix.residential / safeTotal,
      commercial: mix.commercial / safeTotal,
      industrial: mix.industrial / safeTotal,
      green: mix.green / safeTotal,
    };
  };

  const handleApplyScenarioPreset = (preset: ScenarioPreset) => {
    setMixTargets(preset.mixTargets);
    updateSettings((prev) => ({
      ...prev,
      scenarioGeneration: {
        ...prev.scenarioGeneration,
        basePopulationSize: preset.populationSize,
        baseGenerations: preset.generations,
        neighborhoodContinuity: preset.includeAdjacency,
      },
    }));
    setPlannerErrorMessage(null);
    toast.success(`${preset.label} preset applied.`, {
      duration: 2200,
    });
  };

  /** Count of selectable parcels from loaded features */
  const selectableParcelCount = useMemo(() => {
    if (loadedParcelFeatures.length === 0) return 0;
    const uniqueParcelIds = new Set<string>();
    for (const feature of loadedParcelFeatures) {
      const parcelId = getParcelId(feature);
      if (parcelId) {
        uniqueParcelIds.add(parcelId);
      }
    }
    return uniqueParcelIds.size;
  }, [loadedParcelFeatures]);

  /**
   * Collects all selectable parcels from map features.
   */
  const collectSelectableParcels = (): {
    selectedIds: string[];
    featureById: Map<string, any>;
  } => {
    const selectedIds: string[] = [];
    const featureById = new Map<string, any>();
    for (const feature of loadedParcelFeatures) {
      const parcelId = getParcelId(feature);
      if (!parcelId || featureById.has(parcelId)) {
        continue;
      }
      selectedIds.push(parcelId);
      featureById.set(parcelId, feature);
    }
    return { selectedIds, featureById };
  };

  const activeGeneratedPlan = useMemo(() => {
    if (generatedPlans.length === 0) return null;
    const safeIndex = Math.min(activePlanIndex, generatedPlans.length - 1);
    return generatedPlans[safeIndex] ?? null;
  }, [activePlanIndex, generatedPlans]);

  const activePlanAssignments = useMemo(
    () => buildLandUsePlanMap(activeGeneratedPlan ? [activeGeneratedPlan] : []),
    [activeGeneratedPlan]
  );

  /** Handles selecting all parcels */
  const handleSelectAllParcels = () => {
    if (loadedFeatureById.size === 0) {
      toast.error('Parcel data is not loaded yet. Please wait and try again.');
      return;
    }

    const { selectedIds, featureById } = collectSelectableParcels();
    selectAllLoadedParcels();

    if (selectedIds.length > 0) {
      const firstParcelId = selectedIds[0];
      const firstFeature = featureById.get(firstParcelId) ?? loadedFeatureById.get(firstParcelId);
      setPrimarySelectedParcel(firstParcelId, firstFeature?.properties ?? null, firstFeature);
    }

    toast.success(`Selected all ${selectedIds.length} parcels.`, {
      duration: 2500,
    });
  };

  /** Handles clearing parcel selection */
  const handleClearParcelSelection = () => {
    if (selectedParcelIds.length === 0) {
      return;
    }

    clearSelection();
    toast.info('Cleared parcel selection.', {
      duration: 2000,
    });
  };

  const handleParcelSelect = (apn: string, feature: any) => {
    toggleSelectedParcel(apn, feature);
  };

  // Fetch plan overlay layers
  useEffect(() => {
    const visibleLayers = OVERLAY_LAYER_KEYS.filter(
      (layerKey) => overlayVisibility[layerKey]
    );
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
        console.warn('[SpatialOverlay] failed to load layer', {
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
          console.warn('[SpatialOverlay] using fallback overlay plan', {
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
  }, [overlayVisibility, activePlanIndex]);

  // Load reference layers
  useEffect(() => {
    const activeReferenceLayers = (Object.keys(referenceLayerVisibility) as ReferenceMapLayerKey[])
      .filter((layerKey) => referenceLayerVisibility[layerKey]);

    if (activeReferenceLayers.length === 0) {
      setReferenceMapLayers({});
      return;
    }

    let cancelled = false;
    const loadReferenceLayers = async () => {
      const loaded: Partial<Record<ReferenceMapLayerKey, any>> = {};

      await Promise.all(
        activeReferenceLayers.map(async (layerKey) => {
          const cachedLayer = referenceLayerCacheRef.current.get(layerKey);
          if (cachedLayer) {
            loaded[layerKey] = cachedLayer;
            return;
          }

          const fileName = REFERENCE_LAYER_FILES[layerKey];
          const layerUrl = `/data/geovision/zoning/${fileName}`;
          try {
            const response = await fetch(layerUrl);
            if (!response.ok) {
              throw new Error(`HTTP ${response.status}`);
            }
            const payload = await response.json();
            if (!payload?.features || !Array.isArray(payload.features)) {
              throw new Error('Missing feature array');
            }
            referenceLayerCacheRef.current.set(layerKey, payload);
            loaded[layerKey] = payload;
          } catch (error) {
            console.warn('[ReferenceLayer] failed to load layer', {
              layerKey,
              layerUrl,
              error,
            });
          }
        })
      );

      if (!cancelled) {
        setReferenceMapLayers(loaded);
      }
    };

    loadReferenceLayers();
    return () => {
      cancelled = true;
    };
  }, [referenceLayerVisibility]);

  /**
   * Generates optimized land use plans.
   */
  const handleGenerateLandUsePlan = async () => {
    if (selectedParcelIds.length === 0) {
      const message = 'Select at least one parcel before generating plans.';
      setPlannerErrorMessage(message);
      toast.error(message);
      return;
    }

    const selectedFeatures = buildSelectedFeatures(
      selectedParcelIds,
      selectedFeatureById,
      loadedFeatureById
    );

    if (selectedFeatures.length === 0) {
      const message =
        'Selected parcels are missing geometry in the current map state. Re-select parcels and try again.';
      setPlannerErrorMessage(message);
      toast.error(message);
      return;
    }

    const parcelCount = selectedFeatures.length;

    // Smart scaling for large selections
    let effectivePopulationSize = settings.scenarioGeneration.basePopulationSize;
    let effectiveGenerations = settings.scenarioGeneration.baseGenerations;
    let effectiveIncludeAdjacency = settings.scenarioGeneration.neighborhoodContinuity;

    if (settings.scenarioGeneration.smartScalingForLargeSelections) {
      if (parcelCount > 1500) {
        effectivePopulationSize = Math.max(10, Math.min(effectivePopulationSize, 20));
        effectiveGenerations = Math.max(6, Math.min(effectiveGenerations, 12));
        effectiveIncludeAdjacency = false;
      } else if (parcelCount > 800) {
        effectivePopulationSize = Math.max(12, Math.min(effectivePopulationSize, 24));
        effectiveGenerations = Math.max(8, Math.min(effectiveGenerations, 14));
        effectiveIncludeAdjacency = false;
      } else if (parcelCount > 400) {
        effectivePopulationSize = Math.max(14, Math.min(effectivePopulationSize, 28));
        effectiveGenerations = Math.max(10, Math.min(effectiveGenerations, 16));
        effectiveIncludeAdjacency = settings.scenarioGeneration.neighborhoodContinuity;
      }
    }

    setIsGeneratingPlan(true);
    setPlannerErrorMessage(null);
    clearGeneratedPlans();
    const debugRunId = `spatial-plan-${Date.now()}`;
    console.time(debugRunId);
    console.info('[SpatialPlanner] Starting optimization request', {
      selected_parcel_count: parcelCount,
      population_size: effectivePopulationSize,
      generations: effectiveGenerations,
      include_adjacency: effectiveIncludeAdjacency,
      adjacency_predicate: settings.scenarioGeneration.boundaryRule,
      progress_every_generations: settings.scenarioGeneration.progressUpdateEvery,
      interactive_mode: settings.scenarioGeneration.interactiveRun,
      diagnostics_mode: settings.scenarioGeneration.diagnosticsMode,
      num_output_plans: numOutputPlans,
      use_spatial_compatibility: useSpatialCompatibility,
      spatial_neighbor_radius_m: spatialCompatibilityRadiusM,
    });

    try {
      const optimizePayload = {
        parcels: selectedFeatures,
        target_mix: normalizeTargetMix(mixTargets),
        num_output_plans: numOutputPlans,
        population_size: effectivePopulationSize,
        generations: effectiveGenerations,
        include_adjacency: effectiveIncludeAdjacency,
        adjacency_predicate: settings.scenarioGeneration.boundaryRule,
        debug: settings.scenarioGeneration.diagnosticsMode,
        progress_every_generations: settings.scenarioGeneration.progressUpdateEvery,
        interactive_mode: settings.scenarioGeneration.interactiveRun,
        use_spatial_compatibility: useSpatialCompatibility,
        ...(useSpatialCompatibility
          ? {
              spatial_neighbor_radius_m: spatialCompatibilityRadiusM,
              spatial_compatibility_weight: 0.15,
            }
          : {}),
      };
      console.log('[SpatialPlanner] optimize payload', optimizePayload);
      const response = await apiClient.optimizeSpatialPlans(optimizePayload);
      console.info('[SpatialPlanner] Optimization response received', {
        request_id: response.settings?.request_id,
        elapsed_seconds: response.settings?.elapsed_seconds,
        plans: response.plans?.length,
      });
      if (!response.plans || response.plans.length === 0) {
        const noPlanMessage = 'Optimization completed but no plans were returned.';
        setPlannerErrorMessage(noPlanMessage);
        toast.error(noPlanMessage);
      }
      if (response.debug_timeline && response.debug_timeline.length > 0) {
        console.table(response.debug_timeline);
      }

      storeOptimizationResult(response, response.current_state);
      if (response.plans.length > 0) {
        setActivePlanIndex(0);
        onOpenView('plans');
      }
    } catch (error: any) {
      const message =
        typeof error?.message === 'string'
          ? error.message
          : 'Spatial plan generation failed';
      console.error('[SpatialPlanner] Optimization failed', error);
      setPlannerErrorMessage(message);
      toast.error(message);
    } finally {
      console.timeEnd(debugRunId);
      setIsGeneratingPlan(false);
    }
  };

  return (
    <DashboardLayout
      metrics={metrics}
      simulationTime={simulationTime}
      zones={zones}
      selectedRegion={selectedRegion}
    >
      <div className="home-page">
        <div className="home-page__layout">
          {/* Left Sidebar - Spatial Planner Controls */}
          <SpatialPlannerSidebar
            totalParcels={totalLoadedParcels}
            selectedParcels={selectedParcelIds}
            canSelectAllParcels={selectableParcelCount > 0 && selectedParcelIds.length < selectableParcelCount}
            onSelectAllParcels={handleSelectAllParcels}
            onClearSelectedParcels={handleClearParcelSelection}
            mixTargets={mixTargets}
            onMixTargetChange={setMixTargets}
            onApplyScenarioPreset={handleApplyScenarioPreset}
            numOutputPlans={numOutputPlans}
            onNumOutputPlansChange={setNumOutputPlans}
            maxOutputPlans={settings.growthDemand.maxPlanAlternatives}
            useSpatialCompatibility={useSpatialCompatibility}
            onUseSpatialCompatibilityChange={setUseSpatialCompatibility}
            spatialCompatibilityRadiusM={spatialCompatibilityRadiusM}
            onSpatialCompatibilityRadiusChange={setSpatialCompatibilityRadiusM}
            onGeneratePlans={handleGenerateLandUsePlan}
            isGeneratingPlans={isGeneratingPlan}
            errorMessage={plannerErrorMessage}
          />

          {/* Main Content - Map */}
          <main className="main-content">
            <header className="main-content__header">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="main-content__title">Environmental Agent</h1>
                  <p className="main-content__description">
                    Inspect environmental risk conditions, select parcels for analysis, and launch
                    spatial optimization from the environmental planning workspace.
                  </p>
                </div>
                <button
                  onClick={() => setUse3DMap(!use3DMap)}
                  className="px-4 py-2 bg-[#0B1E39]/80 border border-[#4FFFA7]/40 rounded-lg text-sm text-[#4FFFA7] hover:bg-[#4FFFA7]/10 transition-colors flex items-center gap-2"
                >
                  {use3DMap ? '🗺️ Switch to 2D' : '🧊 Switch to 3D'}
                </button>
              </div>
            </header>

            <div className="map-wrapper map-container">
              {use3DMap ? (
                <DeckGLMap
                  geoJsonUrl="/parcels_env_risk_clipped.geojson"
                  scoresById={suitabilityScores}
                  colorMode={colorMode as any}
                  selectedParcelIds={selectedParcelIds}
                  onParcelSelect={(apn, _props, feature) => {
                    handleParcelSelect(apn, feature);
                  }}
                  landUsePlanByParcel={activePlanAssignments}
                  onFeaturesLoaded={registerLoadedParcelFeatures}
                  autoFitToData={true}
                />
              ) : (
                <ParcelMap
                geoJsonUrl="/parcels_env_risk_clipped.geojson"
                scoresById={suitabilityScores}
                colorMode={colorMode as any}
                selectedParcelIds={selectedParcelIds}
                enableRightDragBulkSelect={true}
                onBulkParcelSelect={(parcelIds, featureById) => {
                  if (parcelIds.length === 0) {
                    toast.info('No parcels found in the selected area.', {
                      duration: 2000,
                    });
                    return;
                  }

                  const selectedSet = new Set(selectedParcelIds);
                  const newIds = parcelIds.filter((id) => !selectedSet.has(id));
                  if (newIds.length === 0) {
                    toast.info('All parcels in the selected area are already selected.', {
                      duration: 2200,
                    });
                    return;
                  }

                  addToSelection(newIds, featureById);

                  if (!primarySelectedParcelId) {
                    const firstId = newIds[0];
                    const firstFeature = featureById.get(firstId);
                    setPrimarySelectedParcel(firstId, firstFeature?.properties ?? null, firstFeature);
                  }

                  toast.success(`Added ${newIds.length} parcels from box selection.`, {
                    duration: 2500,
                  });
                }}
                landUsePlanByParcel={activePlanAssignments}
                onParcelSelect={(apn, _props, feature) => {
                  handleParcelSelect(apn, feature);
                }}
                planOverlayLayers={planOverlayLayers}
                referenceMapLayers={referenceMapLayers}
                onFeaturesLoaded={registerLoadedParcelFeatures}
                autoFitToData={true}
                lockViewportToData={true}
              />
              )}
            </div>
          </main>

          {/* Right Sidebar - Parcel Info */}
          <ParcelInfoSidebar
            apn={primarySelectedParcelId}
            properties={primarySelectedParcelProps}
            showAssignmentExplanation={false}
          />
        </div>
      </div>
    </DashboardLayout>
  );
}
