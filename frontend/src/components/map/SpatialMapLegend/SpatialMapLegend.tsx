/**
 * SpatialMapLegend Component
 * ==========================
 * Map legend component showing layer visibility and color coding.
 * Displays primary legend items, plan overlays, and reference layers.
 */

import { useMemo } from 'react';
import type {
  ReferenceMapLayerKey,
  ReferenceMapLayerVisibility,
  SpatialOverlayLayerKey,
  SpatialOverlayVisibility,
} from '../../../types';
import './SpatialMapLegend.css';

type MapColorMode =
  | 'environmental_risk'
  | 'residential'
  | 'commercial'
  | 'industrial'
  | 'green'
  | 'best'
  | 'dominant'
  | 'land_use_plan';

interface SpatialMapLegendProps {
  colorMode: MapColorMode;
  showPlanOverlays: boolean;
  overlayVisibility: SpatialOverlayVisibility;
  referenceLayerVisibility: ReferenceMapLayerVisibility;
  anchor?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left';
}

const OVERLAY_LAYER_ORDER: SpatialOverlayLayerKey[] = [
  'roads', 'networks', 'blocks', 'green', 'buildings', 'plots', 'density',
];

const REFERENCE_LAYER_ORDER: ReferenceMapLayerKey[] = [
  'municipal_boundaries', 'zoning_base_sd', 'zoning_unincorporated', 'general_plan_land_use_sd',
];

const LAND_USE_ITEMS = [
  { label: 'Residential', color: '#3BC7F5' },
  { label: 'Commercial', color: '#FFB86C' },
  { label: 'Industrial', color: '#ef4444' },
  { label: 'Green', color: '#4FFFA7' },
];

const RISK_ITEMS = [
  { label: 'Very Low (0-10)', color: '#166534' },
  { label: 'Low (10-20)', color: '#4ade80' },
  { label: 'Medium (20-30)', color: '#eab308' },
  { label: 'Medium-High (30-40)', color: '#f97316' },
  { label: 'High (>40)', color: '#ef4444' },
];

type LegendItemKind = 'fill' | 'line' | 'gradient';

const OVERLAY_LAYER_STYLE: Record<SpatialOverlayLayerKey, { label: string; color: string; kind: LegendItemKind; dash?: boolean }> = {
  roads: { label: 'Roads', color: '#f59e0b', kind: 'line' },
  networks: { label: 'Networks', color: '#22d3ee', kind: 'line', dash: true },
  blocks: { label: 'Blocks', color: '#a1a1aa', kind: 'fill' },
  green: { label: 'Green Areas', color: '#22c55e', kind: 'fill' },
  buildings: { label: 'Buildings', color: '#f97316', kind: 'fill' },
  plots: { label: 'Plots', color: '#60a5fa', kind: 'fill' },
  density: { label: 'Density', color: '#1d4ed8', kind: 'gradient' },
};

const REFERENCE_LAYER_STYLE: Record<ReferenceMapLayerKey, { label: string; color: string }> = {
  municipal_boundaries: { label: 'Municipal Boundaries', color: '#f8fafc' },
  zoning_base_sd: { label: 'Zoning Base (SD)', color: '#f87171' },
  zoning_unincorporated: { label: 'Zoning Unincorporated', color: '#fb7185' },
  general_plan_land_use_sd: { label: 'General Plan Land Use', color: '#a78bfa' },
};

/** Renders a color swatch for legend items */
function LegendSwatch({ color, kind, dash = false }: { color: string; kind: LegendItemKind; dash?: boolean }) {
  if (kind === 'line') {
    return (
      <span className="swatch swatch--line">
        <span className={`swatch--line-inner ${dash ? 'swatch--line-inner--dashed' : ''}`} style={{ borderColor: color }} />
      </span>
    );
  }
  if (kind === 'gradient') {
    return <span className="swatch swatch--gradient" />;
  }
  return <span className="swatch swatch--fill" style={{ backgroundColor: color }} />;
}

/**
 * SpatialMapLegend component.
 * Displays a legend for map layers with color coding.
 */
export function SpatialMapLegend({
  colorMode,
  showPlanOverlays,
  overlayVisibility,
  referenceLayerVisibility,
  anchor = 'top-right',
}: SpatialMapLegendProps) {
  const activeOverlayKeys = useMemo(
    () => OVERLAY_LAYER_ORDER.filter((key) => overlayVisibility[key]),
    [overlayVisibility]
  );
  const activeReferenceKeys = useMemo(
    () => REFERENCE_LAYER_ORDER.filter((key) => referenceLayerVisibility[key]),
    [referenceLayerVisibility]
  );

  const primaryLegendItems = colorMode === 'land_use_plan' ? LAND_USE_ITEMS : RISK_ITEMS;
  const primaryLegendTitle = colorMode === 'land_use_plan' ? 'Land Use' : 'Environmental Risk';

  const anchorClassName = `map-legend--${anchor}`;

  return (
    <div className={`map-legend ${anchorClassName}`}>
      <div className="map-legend__title">Map Legend</div>

      <div className="legend-section">
        <div className="legend-section__title">{primaryLegendTitle}</div>
        <div className="legend-items">
          {primaryLegendItems.map((item) => (
            <div key={item.label} className="legend-item">
              <LegendSwatch color={item.color} kind="fill" />
              <span>{item.label}</span>
            </div>
          ))}
        </div>
      </div>

      {showPlanOverlays && activeOverlayKeys.length > 0 && (
        <div className="legend-section legend-section--bordered">
          <div className="legend-section__title">Plan Overlays</div>
          <div className="legend-items">
            {activeOverlayKeys.map((key) => {
              const config = OVERLAY_LAYER_STYLE[key];
              return (
                <div key={key} className="legend-item">
                  <LegendSwatch color={config.color} kind={config.kind} dash={config.dash} />
                  <span>{config.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {activeReferenceKeys.length > 0 && (
        <div className="legend-section legend-section--bordered">
          <div className="legend-section__title">Reference Layers</div>
          <div className="legend-items">
            {activeReferenceKeys.map((key) => {
              const config = REFERENCE_LAYER_STYLE[key];
              return (
                <div key={key} className="legend-item">
                  <LegendSwatch color={config.color} kind="line" />
                  <span>{config.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
