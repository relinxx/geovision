import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { CurrentStatePlanningMetrics, SpatialOptimizationPlan, SpatialOptimizationResponse } from '../types';
import {
  buildFeatureMap,
  buildOptimizationMetadata,
  type WorkspaceOptimizationMetadata,
} from '../utils/plannerWorkspace';

interface PlannerWorkspaceContextValue {
  loadedParcelFeatures: any[];
  loadedFeatureById: Map<string, any>;
  totalLoadedParcels: number;
  selectedParcelIds: string[];
  selectedFeatureById: Map<string, any>;
  primarySelectedParcelId: string | null;
  primarySelectedParcelProps: any | null;
  generatedPlans: SpatialOptimizationPlan[];
  objectiveNames: string[];
  activePlanIndex: number;
  latestOptimization: WorkspaceOptimizationMetadata | null;
  currentState: CurrentStatePlanningMetrics | null;
  registerLoadedParcelFeatures: (features: any[]) => void;
  replaceSelection: (parcelIds: string[], featureById?: Map<string, any>) => void;
  addToSelection: (parcelIds: string[], featureById?: Map<string, any>) => void;
  toggleSelectedParcel: (parcelId: string, feature?: any) => void;
  clearSelection: () => void;
  selectAllLoadedParcels: () => void;
  setPrimarySelectedParcel: (parcelId: string | null, properties?: any | null, feature?: any | null) => void;
  clearGeneratedPlans: () => void;
  storeOptimizationResult: (response: SpatialOptimizationResponse) => void;
  setActivePlanIndex: (index: number) => void;
}

const PlannerWorkspaceContext = createContext<PlannerWorkspaceContextValue | null>(null);

export function PlannerWorkspaceProvider({ children }: { children: ReactNode }) {
  const [loadedParcelFeatures, setLoadedParcelFeatures] = useState<any[]>([]);
  const [loadedFeatureById, setLoadedFeatureById] = useState<Map<string, any>>(new Map());
  const [totalLoadedParcels, setTotalLoadedParcels] = useState(0);
  const [selectedParcelIds, setSelectedParcelIds] = useState<string[]>([]);
  const [selectedFeatureById, setSelectedFeatureById] = useState<Map<string, any>>(new Map());
  const [primarySelectedParcelId, setPrimarySelectedParcelId] = useState<string | null>(null);
  const [primarySelectedParcelProps, setPrimarySelectedParcelProps] = useState<any | null>(null);
  const [generatedPlans, setGeneratedPlans] = useState<SpatialOptimizationPlan[]>([]);
  const [objectiveNames, setObjectiveNames] = useState<string[]>([]);
  const [activePlanIndex, setActivePlanIndexState] = useState(0);
  const [latestOptimization, setLatestOptimization] = useState<WorkspaceOptimizationMetadata | null>(
    null
  );
  const [currentState, setCurrentState] = useState<CurrentStatePlanningMetrics | null>(null);

  const registerLoadedParcelFeatures = useCallback(
    (features: any[]) => {
      const normalizedFeatures = Array.isArray(features) ? features : [];
      const featureById = buildFeatureMap(normalizedFeatures);

      setLoadedParcelFeatures(normalizedFeatures);
      setLoadedFeatureById(featureById);
      setTotalLoadedParcels(featureById.size);
      setSelectedFeatureById((prev) => {
        const next = new Map<string, any>();
        for (const parcelId of selectedParcelIds) {
          const feature = prev.get(parcelId) ?? featureById.get(parcelId);
          if (feature) {
            next.set(parcelId, feature);
          }
        }
        return next;
      });

      setPrimarySelectedParcelProps((prev) => {
        if (!primarySelectedParcelId) {
          return prev;
        }
        const feature = featureById.get(primarySelectedParcelId);
        return feature?.properties ?? prev;
      });
    },
    [primarySelectedParcelId, selectedParcelIds]
  );

  const replaceSelection = useCallback(
    (parcelIds: string[], featureById?: Map<string, any>) => {
      const uniqueIds = Array.from(new Set(parcelIds.filter(Boolean)));
      setSelectedParcelIds(uniqueIds);
      setSelectedFeatureById(() => {
        const next = new Map<string, any>();
        for (const parcelId of uniqueIds) {
          const feature = featureById?.get(parcelId) ?? loadedFeatureById.get(parcelId);
          if (feature) {
            next.set(parcelId, feature);
          }
        }
        return next;
      });

      if (uniqueIds.length === 0) {
        setPrimarySelectedParcelId(null);
        setPrimarySelectedParcelProps(null);
        return;
      }

      const nextPrimaryId = uniqueIds[0];
      const primaryFeature = featureById?.get(nextPrimaryId) ?? loadedFeatureById.get(nextPrimaryId);
      setPrimarySelectedParcelId(nextPrimaryId);
      setPrimarySelectedParcelProps(primaryFeature?.properties ?? null);
    },
    [loadedFeatureById]
  );

  const addToSelection = useCallback(
    (parcelIds: string[], featureById?: Map<string, any>) => {
      const nextIds = Array.from(
        new Set([...selectedParcelIds, ...parcelIds.filter(Boolean)])
      );
      setSelectedParcelIds(nextIds);
      setSelectedFeatureById((prev) => {
        const next = new Map(prev);
        for (const parcelId of nextIds) {
          const feature = featureById?.get(parcelId) ?? loadedFeatureById.get(parcelId);
          if (feature) {
            next.set(parcelId, feature);
          }
        }
        return next;
      });

      if (!primarySelectedParcelId && nextIds.length > 0) {
        const nextPrimaryId = nextIds[0];
        const primaryFeature = featureById?.get(nextPrimaryId) ?? loadedFeatureById.get(nextPrimaryId);
        setPrimarySelectedParcelId(nextPrimaryId);
        setPrimarySelectedParcelProps(primaryFeature?.properties ?? null);
      }
    },
    [loadedFeatureById, primarySelectedParcelId, selectedParcelIds]
  );

  const toggleSelectedParcel = useCallback(
    (parcelId: string, feature?: any) => {
      if (!parcelId) return;

      const isSelected = selectedParcelIds.includes(parcelId);
      if (isSelected) {
        const nextIds = selectedParcelIds.filter((id) => id !== parcelId);
        setSelectedParcelIds(nextIds);
        setSelectedFeatureById((prev) => {
          if (!prev.has(parcelId)) return prev;
          const next = new Map(prev);
          next.delete(parcelId);
          return next;
        });

        if (primarySelectedParcelId === parcelId) {
          const nextPrimaryId = nextIds[0] ?? null;
          const nextFeature =
            (nextPrimaryId && (selectedFeatureById.get(nextPrimaryId) ?? loadedFeatureById.get(nextPrimaryId))) ||
            null;
          setPrimarySelectedParcelId(nextPrimaryId);
          setPrimarySelectedParcelProps(nextFeature?.properties ?? null);
        }
        return;
      }

      setSelectedParcelIds((prev) => [...prev, parcelId]);
      if (feature) {
        setSelectedFeatureById((prev) => {
          const next = new Map(prev);
          next.set(parcelId, feature);
          return next;
        });
      } else {
        const loadedFeature = loadedFeatureById.get(parcelId);
        if (loadedFeature) {
          setSelectedFeatureById((prev) => {
            const next = new Map(prev);
            next.set(parcelId, loadedFeature);
            return next;
          });
        }
      }
      setPrimarySelectedParcelId(parcelId);
      setPrimarySelectedParcelProps(feature?.properties ?? loadedFeatureById.get(parcelId)?.properties ?? null);
    },
    [loadedFeatureById, primarySelectedParcelId, selectedFeatureById, selectedParcelIds]
  );

  const clearSelection = useCallback(() => {
    setSelectedParcelIds([]);
    setSelectedFeatureById(new Map());
    setPrimarySelectedParcelId(null);
    setPrimarySelectedParcelProps(null);
  }, []);

  const selectAllLoadedParcels = useCallback(() => {
    const parcelIds = Array.from(loadedFeatureById.keys());
    setSelectedParcelIds(parcelIds);
    setSelectedFeatureById(new Map(loadedFeatureById));
    const firstFeature = loadedFeatureById.get(parcelIds[0] ?? '');
    setPrimarySelectedParcelId(parcelIds[0] ?? null);
    setPrimarySelectedParcelProps(firstFeature?.properties ?? null);
  }, [loadedFeatureById]);

  const setPrimarySelectedParcel = useCallback(
    (parcelId: string | null, properties?: any | null, feature?: any | null) => {
      setPrimarySelectedParcelId(parcelId);
      if (!parcelId) {
        setPrimarySelectedParcelProps(null);
        return;
      }

      if (feature) {
        setSelectedFeatureById((prev) => {
          const next = new Map(prev);
          next.set(parcelId, feature);
          return next;
        });
      }

      const derivedProps =
        properties ??
        feature?.properties ??
        selectedFeatureById.get(parcelId)?.properties ??
        loadedFeatureById.get(parcelId)?.properties ??
        null;
      setPrimarySelectedParcelProps(derivedProps);
    },
    [loadedFeatureById, selectedFeatureById]
  );

  const clearGeneratedPlans = useCallback(() => {
    setGeneratedPlans([]);
    setObjectiveNames([]);
    setActivePlanIndexState(0);
  }, []);

  const storeOptimizationResult = useCallback((response: SpatialOptimizationResponse) => {
    setGeneratedPlans(Array.isArray(response.plans) ? response.plans : []);
    setObjectiveNames(Array.isArray(response.objective_names) ? response.objective_names : []);
    setActivePlanIndexState(0);
    setLatestOptimization(buildOptimizationMetadata(response));
    setCurrentState(response.current_state ?? null);
  }, []);

  const setActivePlanIndex = useCallback((index: number) => {
    setActivePlanIndexState(index);
  }, []);

  const value = useMemo<PlannerWorkspaceContextValue>(
    () => ({
      loadedParcelFeatures,
      loadedFeatureById,
      totalLoadedParcels,
      selectedParcelIds,
      selectedFeatureById,
      primarySelectedParcelId,
      primarySelectedParcelProps,
      generatedPlans,
      objectiveNames,
      activePlanIndex,
      latestOptimization,
      currentState,
      registerLoadedParcelFeatures,
      replaceSelection,
      addToSelection,
      toggleSelectedParcel,
      clearSelection,
      selectAllLoadedParcels,
      setPrimarySelectedParcel,
      clearGeneratedPlans,
      storeOptimizationResult,
      setActivePlanIndex,
    }),
    [
      activePlanIndex,
      clearGeneratedPlans,
      clearSelection,
      currentState,
      generatedPlans,
      latestOptimization,
      loadedFeatureById,
      loadedParcelFeatures,
      objectiveNames,
      primarySelectedParcelId,
      primarySelectedParcelProps,
      registerLoadedParcelFeatures,
      replaceSelection,
      addToSelection,
      selectedFeatureById,
      selectedParcelIds,
      selectAllLoadedParcels,
      setPrimarySelectedParcel,
      setActivePlanIndex,
      storeOptimizationResult,
      totalLoadedParcels,
      toggleSelectedParcel,
    ]
  );

  return (
    <PlannerWorkspaceContext.Provider value={value}>
      {children}
    </PlannerWorkspaceContext.Provider>
  );
}

export function usePlannerWorkspace() {
  const context = useContext(PlannerWorkspaceContext);
  if (!context) {
    throw new Error('usePlannerWorkspace must be used within a PlannerWorkspaceProvider');
  }
  return context;
}
