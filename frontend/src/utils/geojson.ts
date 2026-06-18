// GeoJSON utilities for map data handling
import { LandUseZone, GeoJSONExport, Parcel, ParcelGeoJSONExport, PlanningParameters } from '../types';
import { APP_CONFIG } from '../config/constants';

/**
 * Convert parcel polygons to GeoJSON FeatureCollection
 * NOTE: Currently uses screen/pixel coordinates, not real-world lat/lng.
 * 
 * @param parcels - Array of parcel objects
 * @param globalParams - Optional global planning parameters to apply to all parcels
 */
export function convertParcelsToGeoJSON(
  parcels: Parcel[],
  globalParams?: PlanningParameters
): ParcelGeoJSONExport {
  return {
    type: 'FeatureCollection',
    features: parcels.map((p) => {
      // Use parcel-specific params if available, otherwise use global params
      const params = p.planningParams || globalParams;
      
      return {
        type: 'Feature',
        id: p.id,
        geometry: {
          type: 'Polygon',
          // GeoJSON expects coordinates: number[][][]
          coordinates: [p.polygon.map(([x, y]) => [x, y])],
        },
        properties: {
          centroid: p.centroid,
          // Include planning parameters if provided
          ...(params?.soil_sand_pct !== undefined && { soil_sand_pct: params.soil_sand_pct }),
          ...(params?.soil_clay_pct !== undefined && { soil_clay_pct: params.soil_clay_pct }),
          ...(params?.aqi_mean !== undefined && { aqi_mean: params.aqi_mean }),
          ...(params?.impervious_mean !== undefined && { impervious_mean: params.impervious_mean }),
        },
      };
    }),
  };
}

/**
 * Convert zones to GeoJSON format
 * TODO: Integrate with actual coordinate system (lat/lng)
 */
export function zonesToGeoJSON(
  zones: LandUseZone[],
  region: string
): GeoJSONExport {
  return {
    type: 'FeatureCollection',
    features: zones.map((zone) => ({
      type: 'Feature',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [zone.x, zone.y],
            [zone.x + zone.width, zone.y],
            [zone.x + zone.width, zone.y + zone.height],
            [zone.x, zone.y + zone.height],
            [zone.x, zone.y],
          ],
        ],
      },
      properties: {
        id: zone.id,
        type: zone.type,
        population: zone.population,
        compliance: zone.compliance,
      },
    })),
    metadata: {
      region,
      timestamp: new Date().toISOString(),
      version: APP_CONFIG.version,
    },
  };
}

/**
 * Load GeoJSON file
 * TODO: Implement GeoJSON parsing and validation
 */
export async function loadGeoJSON(file: File): Promise<LandUseZone[]> {
  const text = await file.text();
  const geojson = JSON.parse(text) as GeoJSONExport;

  // TODO: Convert GeoJSON features to zones
  return [];
}

/**
 * Export zones as GeoJSON file
 */
export function exportGeoJSON(zones: LandUseZone[], region: string): void {
  const geojson = zonesToGeoJSON(zones, region);
  const blob = new Blob([JSON.stringify(geojson, null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `land-use-${region}-${Date.now()}.geojson`;
  a.click();
  URL.revokeObjectURL(url);
}
