/**
 * MapLegend Component
 * ===================
 * Simple map legend showing zone types and simulation status.
 */

import { ZONE_TYPES } from '../../../config/constants';
import './MapLegend.css';

interface MapLegendProps {
  isPlaying: boolean;
}

/**
 * MapLegend component.
 * Displays a simple legend for land use zone types.
 */
export function MapLegend({ isPlaying }: MapLegendProps) {
  return (
    <div className="map-legend-simple">
      <div className="map-legend-simple__title">Land Use Types</div>
      <div className="map-legend-simple__items">
        {Object.entries(ZONE_TYPES).map(([key, { label, color }]) => (
          <div key={key} className="map-legend-simple__item">
            <div
              className="map-legend-simple__swatch"
              style={{
                backgroundColor: color,
                boxShadow: `0 0 8px ${color}40`,
              }}
            />
            <span className="map-legend-simple__label">{label}</span>
          </div>
        ))}
      </div>

      {isPlaying && (
        <div className="map-legend-simple__live">
          <div className="map-legend-simple__live-indicator">
            <div className="map-legend-simple__pulse" />
            <span className="map-legend-simple__live-text">Live Simulation</span>
          </div>
        </div>
      )}
    </div>
  );
}
