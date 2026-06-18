import { useEffect, useMemo, useState, useCallback } from 'react';
import DeckGL from '@deck.gl/react';
import { PolygonLayer, BitmapLayer } from '@deck.gl/layers';
import { TileLayer } from '@deck.gl/geo-layers';
import type { MapViewState } from '@deck.gl/core';
import type { LandUseAssignment, ParcelSuitabilityScores } from '../../../types';
import { Loader2 } from 'lucide-react';
import './DeckGLMap.css';

interface DeckGLMapProps {
  geoJsonUrl: string;
  fallbackGeoJsonUrl?: string;
  scoresById: Map<string, ParcelSuitabilityScores>;
  colorMode:
    | 'environmental_risk'
    | 'residential'
    | 'commercial'
    | 'industrial'
    | 'green'
    | 'best'
    | 'dominant'
    | 'land_use_plan';
  onParcelSelect?: (apn: string, properties: any, feature: any) => void;
  onParcelHover?: (apn: string | null, properties: any | null, feature: any | null) => void;
  onFeaturesLoaded?: (features: any[]) => void;
  selectedParcelIds?: string[];
  onBulkParcelSelect?: (parcelIds: string[], featureById: Map<string, any>) => void;
  enableRightDragBulkSelect?: boolean;
  landUsePlanByParcel?: Map<string, LandUseAssignment>;
  autoFitToData?: boolean;
  lockViewportToData?: boolean;
}

interface FeatureProperties {
  APN?: string;
  apn?: string;
  parcel_id?: string;
  parcelId?: string;
  PARCELID?: string;
  PARNO?: string;
  id?: string;
  OBJECTID?: string;
  xgb_risk_score?: number;
  rule_risk_score?: number;
  building_height?: number;
  elevation?: number;
  zoning_code?: string;
  land_use?: string;
  [key: string]: any;
}

const PARCEL_ID_KEYS = [
  'APN', 'apn', 'parcel_id', 'parcelId', 'PARCELID', 'PARNO', 'id', 'OBJECTID'
] as const;

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

function polygonToCoordinates(geometry: any): [number, number][] {
  if (!geometry || !geometry.coordinates) return [];
  
  // GeoJSON Polygons are arrays of LinearRings: [[[lng, lat], [lng, lat], ...]]
  // The first element is the outer ring
  const coords = geometry.coordinates;
  
  if (Array.isArray(coords) && Array.isArray(coords[0])) {
    // coords[0] is the outer ring (array of [lng, lat] pairs)
    const outerRing = coords[0];
    if (Array.isArray(outerRing) && outerRing.length >= 3) {
      // Validate that we have [number, number] pairs
      const valid = outerRing.every((pt: any) => 
        Array.isArray(pt) && 
        typeof pt[0] === 'number' && 
        typeof pt[1] === 'number'
      );
      if (valid) {
        return outerRing as [number, number][];
      }
    }
  }
  return [];
}

function getPolygonCenter(coordinates: [number, number][]): [number, number] {
  if (coordinates.length === 0) return [0, 0];
  let sumX = 0, sumY = 0;
  for (const [x, y] of coordinates) {
    sumX += x;
    sumY += y;
  }
  return [sumX / coordinates.length, sumY / coordinates.length];
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
      const height = Math.random() * 100 + 20;

      features.push({
        type: 'Feature',
        properties: {
          APN: `DEMO-${String(index).padStart(4, '0')}`,
          xgb_risk_score: risk,
          rule_risk_score: risk,
          building_height: height,
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

  return { type: 'FeatureCollection', features };
}

function getRiskColor(score: number): [number, number, number, number] {
  const r = Math.max(0, Math.min(1, score));
  if (r <= 0.10) return [22, 163, 74, 245];    // Dark green - very high opacity
  if (r <= 0.20) return [34, 197, 94, 240];    // Medium green - high opacity
  if (r <= 0.30) return [202, 138, 4, 240];    // Dark gold - high opacity
  if (r <= 0.40) return [234, 88, 12, 240];    // Dark orange - high opacity
  return [220, 38, 38, 245];                   // Dark red - very high opacity
}

function getLandUseColor(assignment: LandUseAssignment): [number, number, number, number] {
  const colors: Record<LandUseAssignment, [number, number, number, number]> = {
    residential: [59, 199, 245, 220],
    commercial: [255, 184, 108, 220],
    industrial: [239, 68, 68, 220],
    green: [79, 255, 167, 220],
  };
  return colors[assignment] || [71, 85, 105, 180];
}

export function DeckGLMap({
  geoJsonUrl,
  fallbackGeoJsonUrl,
  scoresById,
  colorMode,
  onParcelSelect,
  onParcelHover,
  onFeaturesLoaded,
  selectedParcelIds = [],
  landUsePlanByParcel,
  autoFitToData = false,
}: DeckGLMapProps) {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadWarning, setLoadWarning] = useState<string | null>(null);
  const [usingFallbackData, setUsingFallbackData] = useState(false);
  const [viewState, setViewState] = useState<MapViewState>({
    longitude: -117.0,
    latitude: 32.8,
    zoom: 12,
    pitch: 45,
    bearing: 0,
  });
  const [hoveredParcelId, setHoveredParcelId] = useState<string | null>(null);
  void hoveredParcelId;

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
      if (onFeaturesLoaded) {
        onFeaturesLoaded(Array.isArray(json.features) ? json.features : []);
      }
      setLoading(false);

      if (autoFitToData && json?.features?.length > 0) {
        const coords: [number, number][] = [];
        for (const feature of json.features.slice(0, 100)) {
          const polyCoords = polygonToCoordinates(feature.geometry);
          if (polyCoords.length > 0) {
            coords.push(...polyCoords);
          }
        }
        if (coords.length > 0) {
          const center = getPolygonCenter(coords);
          setViewState(prev => ({
            ...prev,
            longitude: center[0],
            latitude: center[1],
            zoom: 13,
          }));
        }
      }
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
      if (onFeaturesLoaded) {
        onFeaturesLoaded(fallback.features);
      }
      setLoading(false);
    };

    void loadData();

    return () => {
      cancelled = true;
    };
  }, [geoJsonUrl, fallbackGeoJsonUrl, onFeaturesLoaded, autoFitToData]);

  // Base polygon data — does NOT depend on hover state to avoid per-hover recompute
  const parcelPolygons = useMemo(() => {
    if (!data?.features) return [];

    return data.features.map((feature: any, index: number) => {
      const apn = getParcelId(feature);
      const props = feature.properties || {};
      const coords = polygonToCoordinates(feature.geometry);
      if (coords.length < 3) return null;

      let color: [number, number, number, number] = [71, 85, 105, 200];
      // Deterministic height based on index — no Math.random() to avoid memo churn
      let height = props.building_height || props.elevation || 10 + (index % 40);

      if (colorMode === 'environmental_risk') {
        const scores = scoresById.get(apn);
        let score = 0;
        if (scores?.environmental_risk !== undefined) {
          score = scores.environmental_risk;
        } else if (props.xgb_risk_score !== undefined) {
          score = props.xgb_risk_score / 100;
        } else if (props.rule_risk_score !== undefined) {
          score = props.rule_risk_score / 100;
        }
        color = getRiskColor(score);
        height = 20 + score * 80;
      } else if (colorMode === 'land_use_plan' && landUsePlanByParcel) {
        const assignment = landUsePlanByParcel.get(apn);
        if (assignment) {
          color = getLandUseColor(assignment);
          height = 40 + (index % 60);
        } else {
          color = [71, 85, 105, 100];
          height = 10;
        }
      }

      return { polygon: coords, properties: props, apn, index, color, height };
    }).filter(Boolean);
  }, [data, scoresById, colorMode, landUsePlanByParcel]);

  const layers = useMemo(() => {
    // OSM base map — free, no token required
    const osmTiles = new TileLayer({
      id: 'osm-base',
      data: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      minZoom: 0,
      maxZoom: 19,
      tileSize: 256,
      renderSubLayers: (props: any) => {
        const { boundingBox } = props.tile;
        return new BitmapLayer(props, {
          data: undefined,
          image: props.data,
          bounds: [
            boundingBox[0][0], boundingBox[0][1],
            boundingBox[1][0], boundingBox[1][1],
          ],
        });
      },
    });

    if (parcelPolygons.length === 0) return [osmTiles];

    const selectedIdSetLocal = new Set(selectedParcelIds);

    const parcelLayer = new PolygonLayer({
      id: 'parcels-3d',
      data: parcelPolygons,
      pickable: true,
      extruded: true,
      wireframe: false,
      filled: true,
      stroked: true,
      getPolygon: (d: any) => d.polygon,
      getElevation: (d: any) => selectedIdSetLocal.has(d.apn) ? d.height * 1.5 : d.height,
      elevationScale: 8,
      getFillColor: (d: any) => selectedIdSetLocal.has(d.apn) ? [113, 112, 255, 240] : d.color,
      // Visible white border on every parcel — key fix for distinguishing parcels
      getLineColor: (d: any) => selectedIdSetLocal.has(d.apn)
        ? [255, 255, 255, 255]
        : [255, 255, 255, 90],
      getLineWidth: (d: any) => selectedIdSetLocal.has(d.apn) ? 4 : 1,
      lineWidthMinPixels: 1,
      lineWidthMaxPixels: 6,
      material: {
        ambient: 1.0,
        diffuse: 0.0,
        shininess: 0,
      },
      autoHighlight: true,
      highlightColor: [113, 112, 255, 120],
      updateTriggers: {
        getFillColor: [selectedParcelIds],
        getElevation: [selectedParcelIds],
        getLineColor: [selectedParcelIds],
        getLineWidth: [selectedParcelIds],
      },
      onHover: (info: any) => {
        if (info.object) {
          const { apn, properties } = info.object;
          const feature = { properties, geometry: { coordinates: [info.object.polygon] } };
          setHoveredParcelId(apn);
          if (onParcelHover) {
            onParcelHover(apn, properties, feature);
          }
        } else {
          setHoveredParcelId(null);
          if (onParcelHover) {
            onParcelHover(null, null, null);
          }
        }
      },
      onClick: (info: any) => {
        if (info.object && onParcelSelect) {
          const { apn, properties } = info.object;
          onParcelSelect(apn, properties, { properties, geometry: { coordinates: [info.object.polygon] } });
        }
      },
    });

    return [osmTiles, parcelLayer];
  }, [parcelPolygons, selectedParcelIds, onParcelHover, onParcelSelect]);

  const handleViewStateChange = useCallback(({ viewState }: { viewState: MapViewState }) => {
    setViewState(viewState);
  }, []);

  return (
    <div className="relative w-full h-full">
      {loading && (
        <div className="absolute inset-0 bg-[#0B1E39]/80 flex items-center justify-center z-[1000]">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 text-[#4FFFA7] animate-spin" />
            <span className="text-sm text-[#D8E2F0]">Loading 3D parcels...</span>
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

      <DeckGL

        viewState={viewState}
        onViewStateChange={handleViewStateChange}
        controller={true}
        layers={layers}
        getTooltip={({ object }: { object?: any }) => {
          if (!object) return null;
          return {
            text: `APN: ${object.apn}\nHeight: ${object.height.toFixed(1)}m`,
            style: {
              backgroundColor: '#0B1E39',
              color: '#D8E2F0',
              fontSize: '12px',
              padding: '8px 12px',
              borderRadius: '6px',
              border: '1px solid rgba(79, 255, 167, 0.3)',
              boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
            },
          };
        }}
        style={{ width: '100%', height: '100%' }}
        parameters={{
          clearColor: [0, 0, 0, 0],
        }}
      />

      {/* 3D Controls */}
      <div className="deckgl-view-controls">
        <button
          onClick={() => setViewState(prev => ({ 
            ...prev, 
            pitch: 0, 
            bearing: 0,
            transitionDuration: 800,
          }))}
          className="deckgl-view-btn"
        >
          <span>🗺️</span>
          <span>2D View</span>
        </button>
        <button
          onClick={() => setViewState(prev => ({ 
            ...prev, 
            pitch: 45, 
            bearing: 0,
            transitionDuration: 800,
          }))}
          className="deckgl-view-btn"
        >
          <span>🧊</span>
          <span>3D View</span>
        </button>
        <button
          onClick={() => setViewState(prev => ({ 
            ...prev, 
            pitch: 60, 
            bearing: 30,
            transitionDuration: 800,
          }))}
          className="deckgl-view-btn"
        >
          <span>📐</span>
          <span>Isometric</span>
        </button>
      </div>

      {/* Height legend */}
      <div className="deckgl-legend">
        <div className="deckgl-legend-title">Environmental Risk</div>
        <div className="deckgl-legend-item">
          <div className="deckgl-legend-color" style={{ backgroundColor: '#16a34a' }} />
          <span>Very Low (0-10%)</span>
        </div>
        <div className="deckgl-legend-item">
          <div className="deckgl-legend-color" style={{ backgroundColor: '#22c55e' }} />
          <span>Low (10-20%)</span>
        </div>
        <div className="deckgl-legend-item">
          <div className="deckgl-legend-color" style={{ backgroundColor: '#ca8a04' }} />
          <span>Medium (20-30%)</span>
        </div>
        <div className="deckgl-legend-item">
          <div className="deckgl-legend-color" style={{ backgroundColor: '#ea580c' }} />
          <span>High (30-40%)</span>
        </div>
        <div className="deckgl-legend-item">
          <div className="deckgl-legend-color" style={{ backgroundColor: '#dc2626' }} />
          <span>Very High (40%+)</span>
        </div>
        <div className="mt-2 pt-2 border-t border-[#4FFFA7]/20 text-[10px] text-[#8A9AB0]">
          3D Height represents risk level
        </div>
      </div>
    </div>
  );
}
