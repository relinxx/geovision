import type { WorkspaceOptimizationMetadata } from '../../utils/plannerWorkspace';

interface OptimizationSnapshotCardProps {
  latestOptimization: WorkspaceOptimizationMetadata | null;
  planCount: number;
  objectiveNames: string[];
  onOpenPlans: () => void;
}

function formatGeneratedAt(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleString(undefined, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function OptimizationSnapshotCard({
  latestOptimization,
  planCount,
  objectiveNames,
  onOpenPlans,
}: OptimizationSnapshotCardProps) {
  if (!latestOptimization) {
    return (
      <section className="workbench-card workbench-panel-card">
        <header className="workbench-section-header">
          <div>
            <h2 className="workbench-section-title">Latest Optimization Snapshot</h2>
            <p className="workbench-section-description">
              The most recent optimization response will appear here after a run.
            </p>
          </div>
        </header>
        <div className="workbench-empty-state">
          <div className="workbench-empty-state__title">No optimization run yet</div>
          <p className="workbench-empty-state__text">
            Open Environmental Agent, select parcels, and generate alternatives to populate this
            snapshot.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="workbench-card workbench-panel-card">
      <header className="workbench-section-header">
        <div>
          <h2 className="workbench-section-title">Latest Optimization Snapshot</h2>
          <p className="workbench-section-description">
            Summary of the most recent spatial optimization response.
          </p>
        </div>
        {/* Updated to use new button design system */}
        <button type="button" className="btn btn--primary" onClick={onOpenPlans}>
          Open Plans
        </button>
      </header>

      <div className="workbench-kv-grid">
        <div className="workbench-kv-item">
          <span className="workbench-kv-item__label">Optimized Parcels</span>
          <span className="workbench-kv-item__value">{latestOptimization.parcelCount}</span>
        </div>
        <div className="workbench-kv-item">
          <span className="workbench-kv-item__label">Plans Returned</span>
          <span className="workbench-kv-item__value">{planCount}</span>
        </div>
        <div className="workbench-kv-item">
          <span className="workbench-kv-item__label">Generated</span>
          <span className="workbench-kv-item__value">
            {formatGeneratedAt(latestOptimization.generatedAt)}
          </span>
        </div>
      </div>

      {/* Pill group with consistent sizing */}
      <div className="workbench-chip-group">
        <span className="workbench-chip-group__label">Objectives</span>
        {objectiveNames.length > 0 ? (
          objectiveNames.map((objective) => (
            <span key={objective} className="pill pill--primary">
              {objective}
            </span>
          ))
        ) : (
          <span className="pill pill--muted">—</span>
        )}
      </div>

      {latestOptimization.settings && (
        <div className="workbench-kv-grid">
          <div className="workbench-kv-item">
            <span className="workbench-kv-item__label">Population Size</span>
            <span className="workbench-kv-item__value">
              {latestOptimization.settings.population_size}
            </span>
          </div>
          <div className="workbench-kv-item">
            <span className="workbench-kv-item__label">Generations</span>
            <span className="workbench-kv-item__value">
              {latestOptimization.settings.generations}
            </span>
          </div>
          <div className="workbench-kv-item">
            <span className="workbench-kv-item__label">Adjacency</span>
            <span className="workbench-kv-item__value">
              {latestOptimization.settings.include_adjacency ? 'Enabled' : 'Disabled'}
            </span>
          </div>
          <div className="workbench-kv-item">
            <span className="workbench-kv-item__label">Boundary Rule</span>
            <span className="workbench-kv-item__value">
              {latestOptimization.settings.adjacency_predicate}
            </span>
          </div>
        </div>
      )}

      {/* Warning pills with consistent sizing */}
      <div className="workbench-chip-group">
        <span className="workbench-chip-group__label">Warnings</span>
        {latestOptimization.warnings.length > 0 ? (
          latestOptimization.warnings.map((warning) => (
            <span key={warning} className="pill pill--warning">
              {warning}
            </span>
          ))
        ) : (
          <span className="pill pill--muted">None</span>
        )}
      </div>
    </section>
  );
}
