import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import * as L from 'leaflet';
import { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import type {
  LandUseAssignment,
  ParcelSuitabilityScores,
  ReferenceMapLayerKey,
  SpatialOverlayLayerKey,
} from '../../types';
import {
  PLAN_COMPARISON_STYLES,
  shouldEmphasizeComparisonParcel,
  type ParcelPlanComparison,
  type PlanComparisonFilter,
} from '../../utils/planMapComparison';
import { Loader2 } from 'lucide-react';

interface ParcelMapProps {
  geoJsonUrl: string;
  /** Optional fallback parcel dataset URL if the primary URL is unavailable. */
  fallbackGeoJsonUrl?: string;
  scoresById: Map<string, ParcelSuitabilityScores>;
  colorMode:
    | 'neutral'
    | 'environmental_risk'
    | 'residential'
    | 'commercial'
    | 'industrial'
    | 'green'
    | 'best'
    | 'dominant'
    | 'land_use_plan'
    | 'plan_comparison';
  onParcelSelect?: (apn: string, properties: FeatureProperties, feature: any) => void;
  onParcelHover?: (apn: string | null, properties: FeatureProperties | null, feature: any | null) => void;
  onFeaturesLoaded?: (features: any[]) => void;
  /** When true, only render features with a valid zoning property (default key 'ZONING_CODE'). */
  onlyWithZoning?: boolean;
  /** Property name to check for zoning existence; defaults to 'ZONING_CODE'. */
  zoningProperty?: string;
  /** Values to exclude for zoningProperty (e.g., '', 'UNKNOWN', null). */
  zoningExcludeValues?: Array<string | null | undefined>;
  /** Show plan overlays */
  showPlanOverlays?: boolean;
  /** Plan overlay data (GeoJSON) */
  planOverlayData?: any;
  /** Plan overlay layers (roads/networks/blocks/green/buildings/plots/density). */
  planOverlayLayers?: Partial<Record<SpatialOverlayLayerKey, any>>;
  /** Static/reference map layers (zoning boundaries/land-use etc). */
  referenceMapLayers?: Partial<Record<ReferenceMapLayerKey, any>>;
  /** Callback when total parcels count is determined */
  onTotalParcelsCount?: (count: number) => void;
  /** Currently selected parcel IDs/APNs for highlight styling. */
  selectedParcelIds?: string[];
  /** Fit the viewport to selected parcels when the trigger changes. */
  fitToSelectedParcelIdsTrigger?: number;
  /** Called when box selection selects multiple parcels. */
  onBulkParcelSelect?: (parcelIds: string[], featureById: Map<string, any>) => void;
  /** Enable box selection gestures (left-click hold drag, or Shift + right-drag). */
  enableRightDragBulkSelect?: boolean;
  /** Optional plan assignments used by `land_use_plan` mode. */
  landUsePlanByParcel?: Map<string, LandUseAssignment>;
  /** Optional parcel-level comparison results used by `plan_comparison` mode. */
  planComparisonByParcel?: Map<string, ParcelPlanComparison> | Record<string, ParcelPlanComparison>;
  /** Optional parcel feature lookup for risk-aware comparison filters. */
  planComparisonParcelFeatureById?: ReadonlyMap<string, unknown>;
  /** When true in `plan_comparison` mode, unchanged parcels are dimmed further. */
  showOnlyChangedComparisonParcels?: boolean;
  /** Optional review filter used by `plan_comparison` mode. */
  planComparisonFilter?: PlanComparisonFilter;
  /** Optional key to force remounting the comparison layer when baseline/comparison changes. */
  planComparisonLayerKey?: string;
  /** Fit map viewport to loaded GeoJSON bounds after load. */
  autoFitToData?: boolean;
  /** Constrain pan viewport to loaded parcel bounds for a trimmed map experience. */
  lockViewportToData?: boolean;
}

interface FeatureProperties {
  APN?: string;
  xgb_risk_score?: number;
  rule_risk_score?: number;
  [key: string]: any;
}

const PARCEL_ID_KEYS = [
  'APN',
  'apn',
  'parcel_id',
  'parcelId',
  'PARCELID',
  'PARNO',
  'id',
  'OBJECTID',
] as const;

const OVERLAY_LAYER_ORDER: SpatialOverlayLayerKey[] = [
  'blocks',
  'green',
  'plots',
  'density',
  'buildings',
  'roads',
  'networks',
];

const REFERENCE_LAYER_ORDER: ReferenceMapLayerKey[] = [
  'general_plan_land_use_sd',
  'zoning_base_sd',
  'zoning_unincorporated',
  'municipal_boundaries',
];

function getParcelId(feature: any): string {
  const props = (feature?.properties || {}) as Record<string, unknown>;
  for (const key of PARCEL_ID_KEYS) {
    const value = props[key];
    if (value !== null && value !== undefined) {
      const id = String(value).trim();
      if (id) return id;
    }
  }

  const fallback = feature?.id;
  if (fallback !== null && fallback !== undefined) {
    const id = String(fallback).trim();
    if (id) return id;
  }

  return '';
}

function getFeatureBounds(feature: any): L.LatLngBounds | null {
  const coordinates = feature?.geometry?.coordinates;
  if (!coordinates) {
    return null;
  }

  let minLng = Number.POSITIVE_INFINITY;
  let maxLng = Number.NEGATIVE_INFINITY;
  let minLat = Number.POSITIVE_INFINITY;
  let maxLat = Number.NEGATIVE_INFINITY;

  const walkCoordinates = (value: any): void => {
    if (!Array.isArray(value)) return;
    if (value.length >= 2 && typeof value[0] === 'number' && typeof value[1] === 'number') {
      const lng = value[0];
      const lat = value[1];
      if (Number.isFinite(lng) && Number.isFinite(lat)) {
        minLng = Math.min(minLng, lng);
        maxLng = Math.max(maxLng, lng);
        minLat = Math.min(minLat, lat);
        maxLat = Math.max(maxLat, lat);
      }
      return;
    }
    for (const item of value) {
      walkCoordinates(item);
    }
  };

  walkCoordinates(coordinates);

  if (
    !Number.isFinite(minLng) ||
    !Number.isFinite(maxLng) ||
    !Number.isFinite(minLat) ||
    !Number.isFinite(maxLat)
  ) {
    return null;
  }

  return L.latLngBounds([minLat, minLng], [maxLat, maxLng]);
}

function buildFallbackGeoJson(rowCount = 5, colCount = 5) {
  const centerLat = 32.8;
  const centerLon = -117.0;
  const cellSize = 0.01;
  const lon0 = centerLon - (colCount * cellSize) / 2;
  const lat0 = centerLat - (rowCount * cellSize) / 2;

  const features = [];
  let index = 1;
  for (let r = 0; r < rowCount; r += 1) {
    for (let c = 0; c < colCount; c += 1) {
      const minLon = lon0 + c * cellSize;
      const minLat = lat0 + r * cellSize;
      const maxLon = minLon + cellSize;
      const maxLat = minLat + cellSize;
      const risk = (index * 7) % 50;

      features.push({
        type: 'Feature',
        properties: {
          APN: `DEMO-${String(index).padStart(4, '0')}`,
          xgb_risk_score: risk,
          rule_risk_score: risk,
          source: 'fallback-demo',
        },
        geometry: {
          type: 'Polygon',
          coordinates: [[
            [minLon, minLat],
            [maxLon, minLat],
            [maxLon, maxLat],
            [minLon, maxLat],
            [minLon, minLat],
          ]],
        },
      });
      index += 1;
    }
  }

  return {
    type: 'FeatureCollection',
    features,
  };
}

function getDensityFillColor(intensity: number): string {
  const normalized = Math.max(0, Math.min(1, Number.isFinite(intensity) ? intensity : 0));
  if (normalized < 0.2) return '#dbeafe';
  if (normalized < 0.4) return '#93c5fd';
  if (normalized < 0.6) return '#60a5fa';
  if (normalized < 0.8) return '#2563eb';
  return '#1e3a8a';
}

function styleOverlayLayer(
  layerKey: SpatialOverlayLayerKey,
  feature: any
): L.PathOptions {
  const props = (feature?.properties || {}) as Record<string, any>;

  if (layerKey === 'roads') {
    const widthM = Number(props.width_m);
    return {
      color: '#f59e0b',
      weight: Number.isFinite(widthM) ? Math.max(1, Math.min(4, widthM / 4)) : 2,
      opacity: 0.9,
    };
  }

  if (layerKey === 'networks') {
    return {
      color: '#22d3ee',
      weight: 1.2,
      opacity: 0.85,
      dashArray: '4 4',
    };
  }

  if (layerKey === 'blocks') {
    return {
      color: '#a1a1aa',
      weight: 0.7,
      fillColor: '#a1a1aa',
      fillOpacity: 0.05,
    };
  }

  if (layerKey === 'green') {
    return {
      color: '#16a34a',
      weight: 0.8,
      fillColor: '#22c55e',
      fillOpacity: 0.22,
    };
  }

  if (layerKey === 'buildings') {
    const heightM = Number(props.height_m);
    return {
      color: '#b45309',
      weight: 0.6,
      fillColor: '#f97316',
      fillOpacity: Number.isFinite(heightM) ? Math.max(0.2, Math.min(0.65, heightM / 60)) : 0.3,
    };
  }

  if (layerKey === 'plots') {
    return {
      color: '#60a5fa',
      weight: 0.5,
      fillColor: '#60a5fa',
      fillOpacity: 0.03,
    };
  }

  const intensity = Number(props.intensity);
  return {
    color: '#1d4ed8',
    weight: 0.5,
    fillColor: getDensityFillColor(intensity),
    fillOpacity: 0.3,
  };
}

function styleReferenceLayer(
  layerKey: ReferenceMapLayerKey,
): L.PathOptions {
  if (layerKey === 'municipal_boundaries') {
    return {
      color: '#f8fafc',
      weight: 1.8,
      opacity: 0.95,
      fillOpacity: 0,
    };
  }

  if (layerKey === 'zoning_base_sd') {
    return {
      color: '#f87171',
      weight: 0.6,
      opacity: 0.45,
      fillColor: '#f87171',
      fillOpacity: 0.05,
    };
  }

  if (layerKey === 'zoning_unincorporated') {
    return {
      color: '#fb7185',
      weight: 0.6,
      opacity: 0.45,
      fillColor: '#fb7185',
      fillOpacity: 0.05,
    };
  }

  return {
    color: '#a78bfa',
    weight: 0.5,
    opacity: 0.35,
    fillColor: '#a78bfa',
    fillOpacity: 0.04,
  };
}

// Component to handle viewport-based lazy loading
function LazyGeoJSONLayer({ 
  data, 
  styleFeature, 
  onEachFeature,
  mapBounds 
}: { 
  data: any; 
  styleFeature: any; 
  onEachFeature: any;
  mapBounds: any;
}) {
  const map = useMap();
  const [visibleFeatures, setVisibleFeatures] = useState<any[]>([]);
  
  useEffect(() => {
    if (!data?.features) return;
    
    // Filter features within current viewport bounds
    const bounds = map.getBounds();
    const filtered = data.features.filter((feature: any) => {
      if (!feature.geometry?.coordinates) return false;
      // Simple bbox check for performance
      const coords = feature.geometry.coordinates[0];
      if (!coords || coords.length === 0) return false;
      
      // Check if any coordinate is within bounds
      return coords.some((coord: [number, number]) => {
        return bounds.contains([coord[1], coord[0]]);
      });
    });
    
    setVisibleFeatures(filtered);
  }, [data, map, mapBounds]);
  
  const visibleData = useMemo(() => ({
    ...data,
    features: visibleFeatures
  }), [data, visibleFeatures]);
  
  if (visibleFeatures.length === 0) return null;
  
  return (
    <GeoJSON
      data={visibleData}
      style={styleFeature}
      onEachFeature={onEachFeature}
    />
  );
}

function FitToGeoJsonBounds({
  data,
  enabled,
}: {
  data: any;
  enabled: boolean;
}) {
  const map = useMap();

  useEffect(() => {
    if (!enabled || !data?.features || !Array.isArray(data.features) || data.features.length === 0) {
      return;
    }

    const layer = L.geoJSON(data);
    const bounds = layer.getBounds();
    if (!bounds.isValid()) {
      return;
    }

    map.invalidateSize();
    map.fitBounds(bounds, {
      padding: [24, 24],
      maxZoom: 16,
    });
  }, [data, enabled, map]);

  return null;
}

function FitToSelectedParcelBounds({
  data,
  selectedParcelIds,
  trigger,
}: {
  data: any;
  selectedParcelIds: string[];
  trigger: number;
}) {
  const map = useMap();

  useEffect(() => {
    if (
      trigger === 0 ||
      selectedParcelIds.length === 0 ||
      !data?.features ||
      !Array.isArray(data.features)
    ) {
      return;
    }

    const selectedIdSet = new Set(selectedParcelIds);
    const selectedFeatures = data.features.filter((feature: any) =>
      selectedIdSet.has(getParcelId(feature))
    );

    if (selectedFeatures.length === 0) {
      return;
    }

    const layer = L.geoJSON({
      type: 'FeatureCollection',
      features: selectedFeatures,
    } as any);
    const bounds = layer.getBounds();
    if (!bounds.isValid()) {
      return;
    }

    map.invalidateSize();
    map.fitBounds(bounds, {
      padding: [24, 24],
      maxZoom: 17,
    });
  }, [data, map, selectedParcelIds, trigger]);

  return null;
}

function RightDragBulkSelect({
  enabled,
  parcelFeatures,
  onBulkSelect,
}: {
  enabled: boolean;
  parcelFeatures: any[];
  onBulkSelect?: (parcelIds: string[], featureById: Map<string, any>) => void;
}) {
  const LEFT_HOLD_DELAY_MS = 220;
  const LEFT_HOLD_MOVE_CANCEL_THRESHOLD_PX = 6;
  const map = useMap();
  const dragStateRef = useRef<{
    isDragging: boolean;
    startLatLng: L.LatLng | null;
    endLatLng: L.LatLng | null;
    rectangle: L.Rectangle | null;
    wasDraggingEnabled: boolean;
    wasBoxZoomEnabled: boolean;
    suppressContextMenuOnce: boolean;
    pendingLeftHold: boolean;
    leftHoldTimerId: number | null;
    pendingStartLatLng: L.LatLng | null;
    pendingStartPoint: L.Point | null;
  }>({
    isDragging: false,
    startLatLng: null,
    endLatLng: null,
    rectangle: null,
    wasDraggingEnabled: true,
    wasBoxZoomEnabled: true,
    suppressContextMenuOnce: false,
    pendingLeftHold: false,
    leftHoldTimerId: null,
    pendingStartLatLng: null,
    pendingStartPoint: null,
  });

  useEffect(() => {
    if (!enabled || !onBulkSelect) {
      return;
    }

    const mapContainer = map.getContainer();

    const eventToContainerPoint = (event: MouseEvent | PointerEvent): L.Point => {
      const rect = mapContainer.getBoundingClientRect();
      return L.point(event.clientX - rect.left, event.clientY - rect.top);
    };

    const eventToLatLng = (event: MouseEvent | PointerEvent): L.LatLng => {
      const point = eventToContainerPoint(event);
      return map.containerPointToLatLng(point);
    };

    const clearLeftHoldTimer = () => {
      const state = dragStateRef.current;
      if (state.leftHoldTimerId !== null) {
        window.clearTimeout(state.leftHoldTimerId);
        state.leftHoldTimerId = null;
      }
    };

    const cancelPendingLeftHold = () => {
      const state = dragStateRef.current;
      clearLeftHoldTimer();
      state.pendingLeftHold = false;
      state.pendingStartLatLng = null;
      state.pendingStartPoint = null;
    };

    const startBoxDrag = (startLatLng: L.LatLng, suppressContextMenuOnce: boolean) => {
      const state = dragStateRef.current;
      if (state.isDragging) {
        return;
      }

      state.isDragging = true;
      state.startLatLng = startLatLng;
      state.endLatLng = startLatLng;
      state.wasDraggingEnabled = map.dragging.enabled();
      state.wasBoxZoomEnabled = map.boxZoom.enabled();
      state.suppressContextMenuOnce = suppressContextMenuOnce;

      if (state.wasDraggingEnabled) {
        map.dragging.disable();
      }
      if (state.wasBoxZoomEnabled) {
        map.boxZoom.disable();
      }

      if (state.rectangle) {
        map.removeLayer(state.rectangle);
      }
      state.rectangle = L.rectangle(L.latLngBounds(startLatLng, startLatLng), {
        color: '#4FFFA7',
        weight: 1.5,
        fillColor: '#4FFFA7',
        fillOpacity: 0.12,
        interactive: false,
      }).addTo(map);
    };

    const cleanupDragVisual = () => {
      const state = dragStateRef.current;
      if (state.rectangle) {
        map.removeLayer(state.rectangle);
      }
      clearLeftHoldTimer();
      state.rectangle = null;
      state.startLatLng = null;
      state.endLatLng = null;
      state.isDragging = false;
      state.suppressContextMenuOnce = false;
      state.pendingLeftHold = false;
      state.pendingStartLatLng = null;
      state.pendingStartPoint = null;
      if (state.wasDraggingEnabled) {
        map.dragging.enable();
      }
      if (state.wasBoxZoomEnabled) {
        map.boxZoom.enable();
      }
    };

    const completeSelection = () => {
      const state = dragStateRef.current;
      if (!state.isDragging || !state.startLatLng || !state.endLatLng) {
        cleanupDragVisual();
        return;
      }

      const startPoint = map.latLngToContainerPoint(state.startLatLng);
      const endPoint = map.latLngToContainerPoint(state.endLatLng);
      const dragDistance = startPoint.distanceTo(endPoint);
      if (dragDistance < 8) {
        cleanupDragVisual();
        return;
      }

      const selectionBounds = L.latLngBounds(state.startLatLng, state.endLatLng);
      const selectedIds: string[] = [];
      const featureById = new Map<string, any>();

      for (const feature of parcelFeatures) {
        const parcelId = getParcelId(feature);
        if (!parcelId || featureById.has(parcelId)) {
          continue;
        }
        const featureBounds = getFeatureBounds(feature);
        if (!featureBounds) {
          continue;
        }
        if (selectionBounds.intersects(featureBounds)) {
          selectedIds.push(parcelId);
          featureById.set(parcelId, feature);
        }
      }

      onBulkSelect(selectedIds, featureById);
      cleanupDragVisual();
    };

    const beginShiftRightDrag = (event: MouseEvent | PointerEvent) => {
      if (event.button !== 2 || !event.shiftKey) {
        return;
      }
      if (dragStateRef.current.isDragging) {
        return;
      }
      cancelPendingLeftHold();
      event.preventDefault();
      event.stopPropagation();
      startBoxDrag(eventToLatLng(event), true);
    };

    const beginLeftHoldDrag = (event: MouseEvent | PointerEvent) => {
      if (event.button !== 0) {
        return;
      }
      const state = dragStateRef.current;
      if (state.isDragging || state.pendingLeftHold) {
        return;
      }

      state.pendingLeftHold = true;
      state.pendingStartLatLng = eventToLatLng(event);
      state.pendingStartPoint = eventToContainerPoint(event);
      clearLeftHoldTimer();
      state.leftHoldTimerId = window.setTimeout(() => {
        const nextState = dragStateRef.current;
        if (!nextState.pendingLeftHold || !nextState.pendingStartLatLng) {
          return;
        }
        const heldStartLatLng = nextState.pendingStartLatLng;
        cancelPendingLeftHold();
        startBoxDrag(heldStartLatLng, false);
      }, LEFT_HOLD_DELAY_MS);
    };

    const maybeCancelPendingLeftHoldOnMove = (event: MouseEvent | PointerEvent) => {
      const state = dragStateRef.current;
      if (!state.pendingLeftHold || !state.pendingStartPoint) {
        return;
      }

      const movement = eventToContainerPoint(event).distanceTo(state.pendingStartPoint);
      if (movement > LEFT_HOLD_MOVE_CANCEL_THRESHOLD_PX) {
        cancelPendingLeftHold();
      }
    };

    const moveDrag = (event: MouseEvent | PointerEvent) => {
      const state = dragStateRef.current;
      if (state.pendingLeftHold) {
        maybeCancelPendingLeftHoldOnMove(event);
        return;
      }
      if (!state.isDragging || !state.startLatLng || !state.rectangle) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      const currentLatLng = eventToLatLng(event);
      state.endLatLng = currentLatLng;
      state.rectangle.setBounds(L.latLngBounds(state.startLatLng, currentLatLng));
    };

    const endDrag = (event?: MouseEvent | PointerEvent) => {
      const state = dragStateRef.current;
      if (state.pendingLeftHold) {
        cancelPendingLeftHold();
        return;
      }
      if (!state.isDragging) {
        return;
      }
      if (event) {
        event.preventDefault();
        event.stopPropagation();
      }
      completeSelection();
    };

    const preventContextMenu = (event: Event) => {
      const state = dragStateRef.current;
      if (!state.suppressContextMenuOnce) {
        return;
      }
      state.suppressContextMenuOnce = false;
      event.preventDefault();
      event.stopPropagation();
    };

    const handleMouseDownCapture = (event: MouseEvent) => {
      beginShiftRightDrag(event);
      beginLeftHoldDrag(event);
    };

    const handlePointerDownCapture = (event: PointerEvent) => {
      beginShiftRightDrag(event);
      beginLeftHoldDrag(event);
    };

    const handleMouseMoveCapture = (event: MouseEvent) => {
      moveDrag(event);
    };

    const handlePointerMoveCapture = (event: PointerEvent) => {
      moveDrag(event);
    };

    const handleMouseUpCapture = (event: MouseEvent) => {
      endDrag(event);
    };

    const handlePointerUpCapture = (event: PointerEvent) => {
      endDrag(event);
    };

    const listenerOptions: AddEventListenerOptions = {
      capture: true,
      passive: false,
    };

    mapContainer.addEventListener('mousedown', handleMouseDownCapture, listenerOptions);
    mapContainer.addEventListener('pointerdown', handlePointerDownCapture, listenerOptions);
    mapContainer.addEventListener('contextmenu', preventContextMenu, listenerOptions);
    window.addEventListener('mousemove', handleMouseMoveCapture, listenerOptions);
    window.addEventListener('pointermove', handlePointerMoveCapture, listenerOptions);
    window.addEventListener('mouseup', handleMouseUpCapture, listenerOptions);
    window.addEventListener('pointerup', handlePointerUpCapture, listenerOptions);

    return () => {
      mapContainer.removeEventListener('mousedown', handleMouseDownCapture, listenerOptions);
      mapContainer.removeEventListener('pointerdown', handlePointerDownCapture, listenerOptions);
      mapContainer.removeEventListener('contextmenu', preventContextMenu, listenerOptions);
      window.removeEventListener('mousemove', handleMouseMoveCapture, listenerOptions);
      window.removeEventListener('pointermove', handlePointerMoveCapture, listenerOptions);
      window.removeEventListener('mouseup', handleMouseUpCapture, listenerOptions);
      window.removeEventListener('pointerup', handlePointerUpCapture, listenerOptions);
      cleanupDragVisual();
    };
  }, [enabled, map, onBulkSelect, parcelFeatures]);

  return null;
}
	
function SyncMapSize() {
  const map = useMap();

  useEffect(() => {
    const resize = () => {
      map.invalidateSize();
    };

    const timer = window.setTimeout(resize, 0);
    window.addEventListener('resize', resize);

    return () => {
      window.clearTimeout(timer);
      window.removeEventListener('resize', resize);
    };
  }, [map]);

  return null;
}

export function ParcelMap({ 
  geoJsonUrl, 
  fallbackGeoJsonUrl,
  scoresById, 
  colorMode, 
  onParcelSelect, 
  onParcelHover,
  onFeaturesLoaded,
  onlyWithZoning = false, 
  zoningProperty = 'ZONING_CODE', 
  zoningExcludeValues = ['', 'UNKNOWN', null, undefined],
  showPlanOverlays = false,
  planOverlayData,
  planOverlayLayers,
  referenceMapLayers,
  onTotalParcelsCount,
  selectedParcelIds = [],
  fitToSelectedParcelIdsTrigger = 0,
  onBulkParcelSelect,
  enableRightDragBulkSelect = false,
  landUsePlanByParcel,
  planComparisonByParcel,
  planComparisonParcelFeatureById,
  showOnlyChangedComparisonParcels = false,
  planComparisonFilter = 'all',
  planComparisonLayerKey,
  autoFitToData = false,
  lockViewportToData = false,
}: ParcelMapProps) {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadWarning, setLoadWarning] = useState<string | null>(null);
  const [usingFallbackData, setUsingFallbackData] = useState(false);
  const previousDataRef = useRef<any>(null);
  const zoningFilterWarningShownRef = useRef(false);
  const onFeaturesLoadedRef = useRef(onFeaturesLoaded);
  const onTotalParcelsCountRef = useRef(onTotalParcelsCount);
  const selectedIdSet = useMemo(() => new Set(selectedParcelIds), [selectedParcelIds]);
  const planComparisonLookup = useMemo(() => {
    if (!planComparisonByParcel) return new Map<string, ParcelPlanComparison>();
    if (planComparisonByParcel instanceof Map) {
      return planComparisonByParcel;
    }
    return new Map(Object.entries(planComparisonByParcel));
  }, [planComparisonByParcel]);

  useEffect(() => {
    onFeaturesLoadedRef.current = onFeaturesLoaded;
    onTotalParcelsCountRef.current = onTotalParcelsCount;
  }, [onFeaturesLoaded, onTotalParcelsCount]);

  // Lazy load GeoJSON data
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    setLoadWarning(null);
    setUsingFallbackData(false);

    const candidateUrls = [geoJsonUrl, fallbackGeoJsonUrl].filter(
      (value, index, arr): value is string => Boolean(value) && arr.indexOf(value) === index
    );

    const applyLoadedData = (json: any) => {
      setData(json);
      if (onFeaturesLoadedRef.current) {
        onFeaturesLoadedRef.current(Array.isArray(json.features) ? json.features : []);
      }
      if (onTotalParcelsCountRef.current && json?.features) {
        onTotalParcelsCountRef.current(json.features.length);
      }
      setLoading(false);
    };

    const loadData = async () => {
      let primaryError: string | null = null;
      let finalError: string | null = null;

      for (let index = 0; index < candidateUrls.length; index += 1) {
        const url = candidateUrls[index];
        try {
          const res = await fetch(url);
          if (!res.ok) {
            throw new Error(`HTTP ${res.status} while loading ${url}`);
          }
          const json = await res.json();
          if (!json?.features || !Array.isArray(json.features) || json.features.length === 0) {
            throw new Error(`No parcel features found in ${url}`);
          }
          if (cancelled) return;

          if (index > 0) {
            const warningPrefix = primaryError
              ? `Primary parcel dataset failed (${primaryError}).`
              : 'Primary parcel dataset failed.';
            setLoadWarning(`${warningPrefix} Loaded fallback dataset from ${url}.`);
          } else {
            setLoadWarning(null);
          }

          applyLoadedData(json);
          return;
        } catch (err) {
          const message = err instanceof Error ? err.message : String(err);
          finalError = message;
          if (index === 0) {
            primaryError = message;
          }
          console.error('Failed to load parcels GeoJSON:', err);
        }
      }

      if (cancelled) return;

      const errorMessage =
        primaryError && finalError && finalError !== primaryError
          ? `Primary error: ${primaryError}. Fallback error: ${finalError}`
          : finalError || primaryError || 'Unknown parcel data loading error';

      setLoadError(errorMessage);
      const fallback = buildFallbackGeoJson();
      setData(fallback);
      setUsingFallbackData(true);
      if (onFeaturesLoadedRef.current) {
        onFeaturesLoadedRef.current(fallback.features);
      }
      if (onTotalParcelsCountRef.current) {
        onTotalParcelsCountRef.current(fallback.features.length);
      }
      setLoading(false);
    };

    void loadData();

    return () => {
      cancelled = true;
    };
  }, [geoJsonUrl, fallbackGeoJsonUrl]);

  // Efficient GeoJSON diff - only update when data actually changes
  const processedData = useMemo(() => {
    if (!data) return null;
    
    // Check if data has actually changed
    if (previousDataRef.current === data) {
      return previousDataRef.current;
    }
    
    // Optionally filter features to only those with zoning info
    let renderData = data;
    if (onlyWithZoning && data && Array.isArray(data.features)) {
      const excludeSet = new Set(
        zoningExcludeValues.map((v) => (typeof v === 'string' ? v.toUpperCase().trim() : v))
      );
      const filtered = data.features.filter((f: any) => {
        const props = (f && f.properties) || {};
        const val = props[zoningProperty];
        if (val === null || val === undefined) return false;
        if (typeof val === 'string') {
          const norm = val.toUpperCase().trim();
          return !excludeSet.has(norm) && norm.length > 0;
        }
        return true;
      });

      if (filtered.length === 0 && data.features.length > 0) {
        if (!zoningFilterWarningShownRef.current) {
          console.warn(
            `[ParcelMap] Zoning filter produced no features for property "${zoningProperty}". Rendering unfiltered parcel dataset.`
          );
          zoningFilterWarningShownRef.current = true;
        }
        renderData = data;
      } else {
        zoningFilterWarningShownRef.current = false;
        renderData = { ...data, features: filtered };
      }
    } else {
      zoningFilterWarningShownRef.current = false;
    }
    
    previousDataRef.current = renderData;
    return renderData;
  }, [data, onlyWithZoning, zoningProperty, zoningExcludeValues]);

  const styleFeature = useCallback((feature: any) => {
    const props: FeatureProperties = feature.properties || {};
    const apn = getParcelId(feature);
    const scores = scoresById.get(apn);
    const isSelected = selectedIdSet.has(apn);

    if (colorMode === 'land_use_plan') {
      const assignment = landUsePlanByParcel?.get(apn);
      const landUseColors: Record<LandUseAssignment, string> = {
        residential: '#3BC7F5',
        commercial: '#FFB86C',
        industrial: '#ef4444',
        green: '#4FFFA7',
      };
      const hasAssignment = Boolean(assignment);
      const fillColor = hasAssignment ? landUseColors[assignment!] : '#475569';

      return {
        color: isSelected ? '#f8fafc' : '#94a3b8',
        weight: isSelected ? 3 : 1.2,
        fillOpacity: hasAssignment ? 0.85 : 0.45,
        fillColor,
      };
    }

    if (colorMode === 'plan_comparison') {
      const comparison = planComparisonLookup.get(apn);
      const status = comparison?.status ?? 'missing';
      const baseStyle = PLAN_COMPARISON_STYLES[status];
      const legacyChangedOnly = showOnlyChangedComparisonParcels && status === 'unchanged';
      const comparisonFeature = planComparisonParcelFeatureById?.get(apn) ?? feature;
      const emphasized = shouldEmphasizeComparisonParcel(comparison, planComparisonFilter, comparisonFeature);
      const dimForFilter = !emphasized;
      const isDimmed = legacyChangedOnly || dimForFilter;

      return {
        color: isSelected ? '#f8fafc' : isDimmed ? '#475569' : baseStyle.color,
        weight: isSelected ? 2.5 : isDimmed ? 0.2 : baseStyle.weight,
        fillColor: baseStyle.fillColor,
        fillOpacity: isDimmed ? 0.035 : baseStyle.fillOpacity,
      };
    }

    let score = 0;
    if (colorMode === 'environmental_risk') {
      if (scores?.environmental_risk !== undefined) {
        score = scores.environmental_risk;
      } else if (props.xgb_risk_score !== undefined) {
        score = (props.xgb_risk_score as number) / 100;
      } else if (props.rule_risk_score !== undefined) {
        score = (props.rule_risk_score as number) / 100;
      }

      // Clamp risk to [0,1]
      const r = Math.max(0, Math.min(1, score));

      // Discrete 5-band colors tuned for 0-100 risk scores:
      // 0-10 very low, 10-20 low, 20-30 medium-low, 30-40 medium-high, >40 high.
      let fillColor: string;
      if (r <= 0.10) {
        fillColor = '#166534'; // very low - dark green
      } else if (r <= 0.20) {
        fillColor = '#4ade80'; // low - light green
      } else if (r <= 0.30) {
        fillColor = '#eab308'; // medium-low - yellow
      } else if (r <= 0.40) {
        fillColor = '#f97316'; // medium-high - orange
      } else {
        fillColor = '#ef4444'; // high - red
      }

      return {
        color: isSelected ? '#3BC7F5' : '#111827',
        weight: isSelected ? 3 : 1,
        fillOpacity: isSelected ? 0.95 : 0.8,
        fillColor,
      };
    }

    // Neutral parcel styling for workbench and zoning-focused views.
    return {
      color: isSelected ? '#dbeafe' : '#64748b',
      weight: isSelected ? 3 : 1,
      fillOpacity: isSelected ? 0.48 : 0.22,
      fillColor: isSelected ? '#3BC7F5' : '#334155',
    };
  }, [
    scoresById,
    colorMode,
    selectedIdSet,
    landUsePlanByParcel,
    planComparisonLookup,
    planComparisonParcelFeatureById,
    showOnlyChangedComparisonParcels,
    planComparisonFilter,
  ]);

  const constrainedBounds = useMemo<L.LatLngBoundsExpression | undefined>(() => {
    if (!lockViewportToData || !processedData?.features || processedData.features.length === 0) {
      return undefined;
    }

    const bounds = L.geoJSON(processedData).getBounds();
    if (!bounds.isValid()) {
      return undefined;
    }

    const padded = bounds.pad(0.08);
    return [
      [padded.getSouth(), padded.getWest()],
      [padded.getNorth(), padded.getEast()],
    ];
  }, [lockViewportToData, processedData]);

  const handleEachFeature = useCallback((feature: any, layer: any) => {
    const props: FeatureProperties = (feature.properties || {}) as FeatureProperties;
    const apn = getParcelId(feature);
    if (!apn) return;
    layer.on('mouseover', () => {
      layer.setStyle({ weight: 2, color: '#4FFFA7' });
      if (onParcelHover) {
        onParcelHover(apn, props, feature);
      }
    });
    layer.on('mouseout', () => {
      layer.setStyle(styleFeature(feature));
      if (onParcelHover) {
        onParcelHover(null, null, null);
      }
    });
    layer.on('click', () => {
      if (onParcelSelect) {
        onParcelSelect(apn, props, feature);
      }
    });
  }, [onParcelHover, onParcelSelect, styleFeature]);

  // Rough center on San Diego; adjust zoom as needed
  const center: [number, number] = [32.8, -117.0];

  return (
    <div className="relative w-full h-full">
      {loading && (
        <div className="absolute inset-0 bg-[#0B1E39]/80 flex items-center justify-center z-[1000]">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 text-[#4FFFA7] animate-spin" />
            <span className="text-sm text-[#D8E2F0]">Loading parcels...</span>
          </div>
        </div>
      )}
      {loadError && (
        <div className="absolute top-3 left-3 right-3 z-[1001] rounded-md border border-[#f97316]/50 bg-[#7c2d12]/70 px-3 py-2 text-xs text-[#FED7AA]">
          Failed to load parcel GeoJSON. Using demo fallback parcels. Details: {loadError}
        </div>
      )}
      {!loadError && loadWarning && (
        <div className="absolute top-3 left-3 right-3 z-[1001] rounded-md border border-[#facc15]/50 bg-[#713f12]/65 px-3 py-2 text-xs text-[#fde68a]">
          {loadWarning}
        </div>
      )}
      {usingFallbackData && (
        <div className="absolute bottom-3 right-3 z-[1001] rounded-md border border-[#3BC7F5]/50 bg-[#0B1E39]/80 px-2 py-1 text-[11px] text-[#3BC7F5]">
          Demo parcel data
        </div>
      )}
      <MapContainer
        center={center}
        zoom={10}
        style={{ width: '100%', height: '100%' }}
        scrollWheelZoom={true}
        preferCanvas={true}
        maxBounds={constrainedBounds}
        maxBoundsViscosity={lockViewportToData ? 1 : 0}
      >
        <TileLayer
          attribution='&copy; OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <SyncMapSize />
        <FitToGeoJsonBounds data={processedData} enabled={autoFitToData} />
        <FitToSelectedParcelBounds
          data={processedData}
          selectedParcelIds={selectedParcelIds}
          trigger={fitToSelectedParcelIdsTrigger}
        />
        <RightDragBulkSelect
          enabled={enableRightDragBulkSelect}
          parcelFeatures={processedData?.features || []}
          onBulkSelect={onBulkParcelSelect}
        />
        {processedData && (
          <GeoJSON
            key={`parcels-${processedData.features?.length || 0}-${selectedParcelIds.join('|')}-${colorMode}-${planComparisonLayerKey ?? ''}-${showOnlyChangedComparisonParcels ? 'changed' : 'all'}-${planComparisonFilter}`}
            data={processedData}
            style={styleFeature as any}
            onEachFeature={handleEachFeature}
          />
        )}
        {showPlanOverlays &&
          planOverlayLayers &&
          OVERLAY_LAYER_ORDER.map((layerKey) => {
            const layerData = planOverlayLayers[layerKey];
            if (!layerData?.features || !Array.isArray(layerData.features) || layerData.features.length === 0) {
              return null;
            }

            return (
              <GeoJSON
                key={`overlay-${layerKey}-${layerData.features.length}`}
                data={layerData}
                style={(feature) => styleOverlayLayer(layerKey, feature)}
              />
            );
          })}
        {referenceMapLayers &&
          REFERENCE_LAYER_ORDER.map((layerKey) => {
            const layerData = referenceMapLayers[layerKey];
            if (!layerData?.features || !Array.isArray(layerData.features) || layerData.features.length === 0) {
              return null;
            }
            return (
              <GeoJSON
                key={`reference-${layerKey}-${layerData.features.length}`}
                data={layerData}
                style={() => styleReferenceLayer(layerKey)}
              />
            );
          })}
        {showPlanOverlays && !planOverlayLayers && planOverlayData && (
          <GeoJSON
            data={planOverlayData}
            style={{
              color: '#4FFFA7',
              weight: 2,
              fillOpacity: 0.1,
              fillColor: '#4FFFA7',
            }}
          />
        )}
      </MapContainer>
    </div>
  );
}
