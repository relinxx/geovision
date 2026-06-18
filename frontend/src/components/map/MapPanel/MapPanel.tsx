/**
 * MapPanel Component
 * ==================
 * Map panel container with map display area.
 * Combines MapCanvas, MapLegend, and MapControls.
 */

import { LandUseZone } from '../../../types';
import { MapCanvas } from '../MapCanvas';
import { MapLegend } from '../MapLegend/MapLegend';
import { MapControls } from '../MapControls/MapControls';
import './MapPanel.css';

interface MapPanelProps {
  zones: LandUseZone[];
  onZoneSelect: (zoneId: string) => void;
  enabledLayers: string[];
  zoomLevel: number;
  setZoomLevel: (zoom: number) => void;
}

/**
 * MapPanel component.
 * Provides a container for the map with legend and controls.
 */
export function MapPanel({
  zones,
  onZoneSelect,
  enabledLayers,
  zoomLevel,
  setZoomLevel,
}: MapPanelProps) {
  return (
    <div className="map-panel">
      <div className="map-display">
        <MapCanvas
          zones={zones}
          onZoneSelect={onZoneSelect}
          isPlaying={false}
          enabledLayers={enabledLayers}
        />
        <MapLegend isPlaying={false} />
        <MapControls zoomLevel={zoomLevel} setZoomLevel={setZoomLevel} zones={zones} />
      </div>
    </div>
  );
}
