interface PlanningWorkflowCardProps {
  plannerName: string;
  selectedParcelCount: number;
  totalLoadedParcels: number;
  defaultAlternatives: number;
  populationSize: number;
  generations: number;
  boundaryRule: string;
  onSelectAll: () => void;
  onClearSelection: () => void;
  onOpenEnvironmentalAgent: () => void;
  canSelectAll: boolean;
  canClear: boolean;
}

export function PlanningWorkflowCard({
  plannerName,
  selectedParcelCount,
  totalLoadedParcels,
  defaultAlternatives,
  populationSize,
  generations,
  boundaryRule,
  onSelectAll,
  onClearSelection,
  onOpenEnvironmentalAgent,
  canSelectAll,
  canClear,
}: PlanningWorkflowCardProps) {
  return (
    <section className="workbench-card workbench-panel-card">
      <header className="workbench-section-header">
        <div>
          <h2 className="workbench-section-title">Planner Workflow</h2>
          <p className="workbench-section-description">
            Current runtime defaults and selection controls for this workspace.
          </p>
        </div>
      </header>

      <div className="workbench-kv-grid">
        <div className="workbench-kv-item">
          <span className="workbench-kv-item__label">Planner</span>
          <span className="workbench-kv-item__value">{plannerName}</span>
        </div>
        <div className="workbench-kv-item">
          <span className="workbench-kv-item__label">Selection</span>
          <span className="workbench-kv-item__value">
            {selectedParcelCount} / {totalLoadedParcels || '—'}
          </span>
        </div>
        <div className="workbench-kv-item">
          <span className="workbench-kv-item__label">Default Alternatives</span>
          <span className="workbench-kv-item__value">{defaultAlternatives}</span>
        </div>
        <div className="workbench-kv-item">
          <span className="workbench-kv-item__label">Population / Generations</span>
          <span className="workbench-kv-item__value">
            {populationSize} / {generations}
          </span>
        </div>
        <div className="workbench-kv-item">
          <span className="workbench-kv-item__label">Boundary Rule</span>
          <span className="workbench-kv-item__value">{boundaryRule}</span>
        </div>
      </div>

      <div className="workbench-action-row">
        <button
          type="button"
          className="workbench-secondary-btn"
          onClick={onSelectAll}
          disabled={!canSelectAll}
        >
          Select All Loaded
        </button>
        <button
          type="button"
          className="workbench-secondary-btn"
          onClick={onClearSelection}
          disabled={!canClear}
        >
          Clear Selection
        </button>
        <button type="button" className="workbench-primary-btn" onClick={onOpenEnvironmentalAgent}>
          Open Environmental Agent
        </button>
      </div>
    </section>
  );
}
