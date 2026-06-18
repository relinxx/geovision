// Custom hook for map controls
import { useState } from 'react';
import { MapStyle, LandUseZone } from '../types';

export function useMapControls(initialZones: LandUseZone[]) {
  const [mapStyle, setMapStyle] = useState<MapStyle>('landuse');
  const [zoomLevel, setZoomLevel] = useState(1);
  const [enabledLayers, setEnabledLayers] = useState<string[]>([
    'flood',
    'zoning',
    'population',
  ]);

  const toggleLayer = (layerId: string) => {
    setEnabledLayers((prev) =>
      prev.includes(layerId)
        ? prev.filter((id) => id !== layerId)
        : [...prev, layerId]
    );
  };

  const selectZone = (zoneId: string, zones: LandUseZone[]): LandUseZone[] => {
    return zones.map((zone) => ({
      ...zone,
      selected: zone.id === zoneId ? !zone.selected : false,
    }));
  };

  return {
    mapStyle,
    zoomLevel,
    enabledLayers,
    setMapStyle,
    setZoomLevel,
    toggleLayer,
    selectZone,
  };
}
