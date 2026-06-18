/**
 * MapControls Component
 * ====================
 * Map zoom controls and zone info tooltip.
 */

import { motion } from 'motion/react';
import { LandUseZone } from '../../../types';
import { ZONE_TYPES } from '../../../config/constants';
import './MapControls.css';

interface MapControlsProps {
  zoomLevel: number;
  setZoomLevel: (zoom: number) => void;
  zones: LandUseZone[];
}

/**
 * MapControls component.
 * Provides zoom controls and displays selected zone information.
 */
export function MapControls({ zoomLevel, setZoomLevel, zones }: MapControlsProps) {
  const selectedZone = zones.find((z) => z.selected);

  return (
    <>
      {/* Zoom Controls */}
      <div className="zoom-controls">
        <button
          className="zoom-btn"
          onClick={() => setZoomLevel(zoomLevel + 1)}
          aria-label="Zoom in"
        >
          +
        </button>
        <button
          className="zoom-btn"
          onClick={() => setZoomLevel(zoomLevel - 1)}
          aria-label="Zoom out"
        >
          −
        </button>
      </div>

      {/* Info tooltip for selected zone */}
      {selectedZone && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="zone-tooltip"
        >
          <h4 className="zone-tooltip__title">Zone Details</h4>
          <div className="zone-tooltip__content">
            <div className="zone-tooltip__row">
              <span className="zone-tooltip__label">Type:</span>
              <span className="zone-tooltip__value">
                {ZONE_TYPES[selectedZone.type].label}
              </span>
            </div>
            {selectedZone.population && (
              <div className="zone-tooltip__row">
                <span className="zone-tooltip__label">Population:</span>
                <span className="zone-tooltip__value">{selectedZone.population}</span>
              </div>
            )}
            <div className="zone-tooltip__row">
              <span className="zone-tooltip__label">Compliance:</span>
              <span className="zone-tooltip__value--highlight">{selectedZone.compliance}%</span>
            </div>
          </div>
        </motion.div>
      )}
    </>
  );
}
