/**
 * SpatialPlannerSidebar Component
 * ================================
 * Left sidebar for the Home page containing parcel statistics,
 * land use mix target controls, and the plan generation button.
 * 
 * @component
 * @example
 * ```tsx
 * <SpatialPlannerSidebar
 *   totalParcels={1000}
 *   selectedParcels={selectedIds}
 *   canSelectAllParcels={true}
 *   onSelectAllParcels={handleSelectAll}
 *   onClearSelectedParcels={handleClear}
 *   mixTargets={mixTargets}
 *   onMixTargetChange={setMixTargets}
 *   numOutputPlans={3}
 *   onNumOutputPlansChange={setNumPlans}
 *   maxOutputPlans={5}
 *   onGeneratePlans={handleGenerate}
 *   isGeneratingPlans={false}
 * />
 * ```
 */

import { useMemo } from 'react';
import { Loader2, SlidersHorizontal } from 'lucide-react';
import type { LandUseMixTargets } from '../../../types';
import './SpatialPlannerSidebar.css';

export interface ScenarioPreset {
  id: string;
  label: string;
  description: string;
  mixTargets: LandUseMixTargets;
  populationSize: number;
  generations: number;
  includeAdjacency: boolean;
}

/** Props for the SpatialPlannerSidebar component */
interface SpatialPlannerSidebarProps {
  /** Total number of parcels available */
  totalParcels: number;
  /** Array of currently selected parcel IDs */
  selectedParcels: string[];
  /** Whether the "Select All" button should be enabled */
  canSelectAllParcels: boolean;
  /** Callback to select all parcels */
  onSelectAllParcels: () => void;
  /** Callback to clear parcel selection */
  onClearSelectedParcels: () => void;
  /** Current land use mix target percentages */
  mixTargets: LandUseMixTargets;
  /** Callback when mix targets change */
  onMixTargetChange: (next: LandUseMixTargets) => void;
  /** Callback when a planning scenario preset is selected */
  onApplyScenarioPreset?: (preset: ScenarioPreset) => void;
  /** Current number of output plans to generate */
  numOutputPlans: number;
  /** Callback when number of output plans changes */
  onNumOutputPlansChange: (value: number) => void;
  /** Maximum allowed value for output plans slider */
  maxOutputPlans: number;
  /** Whether centroid-neighbour spatial compatibility should affect plan scoring */
  useSpatialCompatibility: boolean;
  /** Callback when spatial compatibility is toggled */
  onUseSpatialCompatibilityChange: (value: boolean) => void;
  /** Current spatial compatibility neighbour radius */
  spatialCompatibilityRadiusM: number;
  /** Callback when spatial compatibility neighbour radius changes */
  onSpatialCompatibilityRadiusChange: (value: number) => void;
  /** Callback to trigger plan generation */
  onGeneratePlans: () => void;
  /** Whether plan generation is in progress */
  isGeneratingPlans: boolean;
  /** Error message to display, if any */
  errorMessage?: string | null;
}

/** Land use mix categories */
const MIX_KEYS: Array<keyof LandUseMixTargets> = [
  'residential',
  'commercial',
  'industrial',
  'green',
];

/** Display labels for mix categories */
const MIX_LABELS: Record<keyof LandUseMixTargets, string> = {
  residential: 'Residential',
  commercial: 'Commercial',
  industrial: 'Industrial',
  green: 'Green',
};

const SPATIAL_COMPATIBILITY_RADII = [
  { label: '250m', value: 250 },
  { label: '500m', value: 500 },
  { label: '1km', value: 1000 },
];

const SCENARIO_PRESETS: ScenarioPreset[] = [
  {
    id: 'balanced-growth',
    label: 'Balanced Growth',
    description: 'Balanced residential, commercial, industrial, and green allocation.',
    mixTargets: { residential: 35, commercial: 25, industrial: 15, green: 25 },
    populationSize: 80,
    generations: 80,
    includeAdjacency: true,
  },
  {
    id: 'housing-priority',
    label: 'Housing Priority',
    description: 'Prioritizes residential capacity while keeping green space.',
    mixTargets: { residential: 55, commercial: 20, industrial: 5, green: 20 },
    populationSize: 80,
    generations: 80,
    includeAdjacency: true,
  },
  {
    id: 'commercial-corridor',
    label: 'Commercial Corridor',
    description: 'Prioritizes commercial land along suitable planning areas.',
    mixTargets: { residential: 30, commercial: 45, industrial: 10, green: 15 },
    populationSize: 90,
    generations: 90,
    includeAdjacency: true,
  },
  {
    id: 'conservation-first',
    label: 'Conservation First',
    description: 'Maximizes green/conservation allocation and reduces built-use pressure.',
    mixTargets: { residential: 25, commercial: 15, industrial: 5, green: 55 },
    populationSize: 80,
    generations: 90,
    includeAdjacency: true,
  },
  {
    id: 'low-risk-development',
    label: 'Low-Risk Development',
    description: 'Favors development while keeping higher green buffers.',
    mixTargets: { residential: 35, commercial: 25, industrial: 5, green: 35 },
    populationSize: 100,
    generations: 100,
    includeAdjacency: true,
  },
  {
    id: 'employment-industrial',
    label: 'Employment / Industrial Focus',
    description: 'Prioritizes industrial and employment-generating land uses.',
    mixTargets: { residential: 25, commercial: 25, industrial: 35, green: 15 },
    populationSize: 90,
    generations: 90,
    includeAdjacency: true,
  },
];

/**
 * Normalizes mix values to percentages.
 * @param mix - Raw mix target values
 * @returns Normalized percentages for each category
 */
function normalizeMix(mix: LandUseMixTargets): Record<keyof LandUseMixTargets, number> {
  const rawTotal = mix.residential + mix.commercial + mix.industrial + mix.green;
  const total = rawTotal > 0 ? rawTotal : 1;
  return {
    residential: (mix.residential / total) * 100,
    commercial: (mix.commercial / total) * 100,
    industrial: (mix.industrial / total) * 100,
    green: (mix.green / total) * 100,
  };
}

/**
 * Spatial Planner Sidebar component.
 * Provides parcel statistics, mix controls, and plan generation.
 */
export function SpatialPlannerSidebar({
  totalParcels,
  selectedParcels,
  canSelectAllParcels,
  onSelectAllParcels,
  onClearSelectedParcels,
  mixTargets,
  onMixTargetChange,
  onApplyScenarioPreset,
  numOutputPlans,
  onNumOutputPlansChange,
  maxOutputPlans,
  useSpatialCompatibility,
  onUseSpatialCompatibilityChange,
  spatialCompatibilityRadiusM,
  onSpatialCompatibilityRadiusChange,
  onGeneratePlans,
  isGeneratingPlans,
  errorMessage,
}: SpatialPlannerSidebarProps) {
  const normalizedMix = useMemo(() => normalizeMix(mixTargets), [mixTargets]);
  const activePresetId = useMemo(() => {
    const matchingPreset = SCENARIO_PRESETS.find((preset) =>
      MIX_KEYS.every((key) => preset.mixTargets[key] === mixTargets[key])
    );
    return matchingPreset?.id ?? null;
  }, [mixTargets]);

  const handleScenarioPresetClick = (preset: ScenarioPreset) => {
    if (onApplyScenarioPreset) {
      onApplyScenarioPreset(preset);
      return;
    }
    onMixTargetChange(preset.mixTargets);
  };

  return (
    <aside className="spatial-planner-sidebar custom-scrollbar">
      <div className="spatial-planner-sidebar__content">
        {/* Statistics Section */}
        <section className="sidebar-section">
          <h3 className="sidebar-section__label">Statistics</h3>
          
          <div className="stat-tile">
            <div className="stat-tile__label">Total Parcels</div>
            <div className="stat-tile__value--accent">{totalParcels || 0}</div>
          </div>
          
          <div className="stat-tile">
            <div className="stat-tile__label">Selected</div>
            <div className="stat-tile__value--secondary">{selectedParcels.length}</div>
          </div>
          
          <div className="btn-grid">
            <button
              type="button"
              onClick={onSelectAllParcels}
              disabled={!canSelectAllParcels}
              className="sidebar-btn sidebar-btn--success"
            >
              Select All
            </button>
            <button
              type="button"
              onClick={onClearSelectedParcels}
              disabled={selectedParcels.length === 0}
              className="sidebar-btn sidebar-btn--secondary"
            >
              Clear
            </button>
          </div>
        </section>

        {/* Planning Mix Targets Section */}
        <section className="sidebar-section">
          <div className="sidebar-section__header">
            <SlidersHorizontal className="sidebar-section__header-icon" />
            <h3 className="sidebar-section__label">Planning Mix Targets</h3>
          </div>

          <div className="scenario-presets" aria-label="Planning scenario presets">
            <div className="scenario-presets__header">
              <span>Planning Scenario Presets</span>
              <small>Choose a preset to quickly configure land-use targets and optimization settings.</small>
            </div>
            <div className="scenario-presets__grid">
              {SCENARIO_PRESETS.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  className={`scenario-preset${activePresetId === preset.id ? ' scenario-preset--active' : ''}`}
                  onClick={() => handleScenarioPresetClick(preset)}
                >
                  <span>{preset.label}</span>
                  <small>{preset.description}</small>
                </button>
              ))}
            </div>
          </div>

          {MIX_KEYS.map((key) => (
            <div key={key} className="mix-control">
              <div className="mix-control__row">
                <span className="mix-control__label">{MIX_LABELS[key]}</span>
                <span className="mix-control__value">{normalizedMix[key].toFixed(1)}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                step={1}
                value={mixTargets[key]}
                onChange={(e) =>
                  onMixTargetChange({
                    ...mixTargets,
                    [key]: Number(e.target.value),
                  })
                }
                className="mix-control__slider"
                aria-label={`${MIX_LABELS[key]} target percentage`}
              />
            </div>
          ))}

          {/* K Plans control */}
          <div className="mix-control">
            <div className="mix-control__row">
              <span className="mix-control__label">K Plans</span>
              <span className="mix-control__value--secondary">{numOutputPlans}</span>
            </div>
            <input
              type="range"
              min={1}
              max={Math.max(1, maxOutputPlans)}
              step={1}
              value={numOutputPlans}
              onChange={(e) => onNumOutputPlansChange(Number(e.target.value))}
              className="mix-control__slider mix-control__slider--secondary"
              aria-label="Number of output plans to generate"
            />
          </div>

          <div className="spatial-compatibility-control">
            <label className="spatial-compatibility-control__toggle">
              <span>
                <strong>Use spatial compatibility</strong>
                <small>
                  Encourages compatible land-use clusters and discourages conflicting nearby assignments.
                </small>
              </span>
              <input
                type="checkbox"
                checked={useSpatialCompatibility}
                onChange={(event) => onUseSpatialCompatibilityChange(event.target.checked)}
                aria-label="Use spatial compatibility"
              />
            </label>
            <div className="spatial-compatibility-control__radii" aria-label="Spatial compatibility radius">
              {SPATIAL_COMPATIBILITY_RADII.map((radius) => (
                <button
                  key={radius.value}
                  type="button"
                  className={`spatial-compatibility-control__radius${
                    spatialCompatibilityRadiusM === radius.value
                      ? ' spatial-compatibility-control__radius--active'
                      : ''
                  }`}
                  disabled={!useSpatialCompatibility}
                  onClick={() => onSpatialCompatibilityRadiusChange(radius.value)}
                >
                  {radius.label}
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* Generate Button */}
        <button
          type="button"
          onClick={onGeneratePlans}
          disabled={isGeneratingPlans || selectedParcels.length === 0}
          className="generate-btn"
        >
          {isGeneratingPlans ? (
            <>
              <Loader2 className="generate-btn__spinner" />
              Generating Plans...
            </>
          ) : (
            'Generate Plans'
          )}
        </button>

        {/* Error Message */}
        {errorMessage && (
          <div className="error-message" role="alert">
            {errorMessage}
          </div>
        )}
      </div>
    </aside>
  );
}
