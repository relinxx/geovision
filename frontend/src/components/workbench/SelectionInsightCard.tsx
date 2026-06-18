interface SelectionInsightCardProps {
  selectedParcelCount: number;
  parcelPreview: string;
  selectedArea: string;
  averageRisk: string;
  averageParcelSize: string;
  constrainedParcels: number;
  keyConstraints: string[];
  constraintFootprint: string[];
  protectedFlags: string[];
  readyForOptimization: boolean;
}

export function SelectionInsightCard({
  selectedParcelCount,
  parcelPreview,
  selectedArea,
  averageRisk,
  averageParcelSize,
  constrainedParcels,
  keyConstraints,
  constraintFootprint,
  protectedFlags,
  readyForOptimization,
}: SelectionInsightCardProps) {
  const hasSelection = selectedParcelCount > 0;

  return (
    <section className="workbench-card workbench-panel-card">
      <header className="workbench-section-header">
        <div>
          <h2 className="workbench-section-title">Current Selection Insight</h2>
          <p className="workbench-section-description">
            Environmental and parcel-pattern signals for the currently selected planning area.
          </p>
        </div>
      </header>

      {!hasSelection ? (
        <div className="workbench-empty-state">
          <div className="workbench-empty-state__title">No parcels selected</div>
          <p className="workbench-empty-state__text">
            Start on the Workbench map or open Environmental Agent to click parcels, box-select
            an area, and prepare a planning run.
          </p>
        </div>
      ) : (
        <div className="workbench-data-stack">
          <div className="workbench-kv-grid">
            <div className="workbench-kv-item">
              <span className="workbench-kv-item__label">Selected Parcels</span>
              <span className="workbench-kv-item__value">{selectedParcelCount}</span>
            </div>
            <div className="workbench-kv-item">
              <span className="workbench-kv-item__label">Parcel Preview</span>
              <span className="workbench-kv-item__value">{parcelPreview}</span>
            </div>
            <div className="workbench-kv-item">
              <span className="workbench-kv-item__label">Selected Area</span>
              <span className="workbench-kv-item__value">{selectedArea}</span>
            </div>
            <div className="workbench-kv-item">
              <span className="workbench-kv-item__label">Average Risk</span>
              <span className="workbench-kv-item__value">{averageRisk}</span>
            </div>
            <div className="workbench-kv-item">
              <span className="workbench-kv-item__label">Average Parcel Size</span>
              <span className="workbench-kv-item__value">{averageParcelSize}</span>
            </div>
            <div className="workbench-kv-item">
              <span className="workbench-kv-item__label">Constrained Parcels</span>
              <span className="workbench-kv-item__value">{constrainedParcels}</span>
            </div>
          </div>

          {/* Pill groups with consistent sizing */}
          <div className="workbench-chip-group">
            <span className="workbench-chip-group__label">Key Constraints</span>
            {keyConstraints.length > 0 ? (
              keyConstraints.map((item) => (
                <span key={item} className="pill pill--warning">
                  {item}
                </span>
              ))
            ) : (
              <span className="pill pill--muted">No flagged constraints</span>
            )}
          </div>

          <div className="workbench-chip-group">
            <span className="workbench-chip-group__label">Constraint Footprint</span>
            {constraintFootprint.length > 0 ? (
              constraintFootprint.map((item) => (
                <span key={item} className="pill pill--default">
                  {item}
                </span>
              ))
            ) : (
              <span className="pill pill--muted">Unavailable</span>
            )}
          </div>

          <div className="workbench-chip-group">
            <span className="workbench-chip-group__label">Protected / Policy Flags</span>
            {protectedFlags.length > 0 ? (
              protectedFlags.map((item) => (
                <span key={item} className="pill pill--primary">
                  {item}
                </span>
              ))
            ) : (
              <span className="pill pill--muted">
                No ecological policy flags in selection
              </span>
            )}
          </div>

          {/* Status as pill for consistent sizing */}
          <div className="workbench-status-row">
            <span className="workbench-status-row__label">Optimization Readiness</span>
            <span className={`pill ${readyForOptimization ? 'pill--primary' : 'pill--warning'}`}>
              {readyForOptimization ? 'Ready' : 'Select parcels first'}
            </span>
          </div>
        </div>
      )}
    </section>
  );
}
