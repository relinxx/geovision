interface SystemStatusCardProps {
  datasetLoaded: boolean;
  environmentalValuesAvailable: boolean;
  zoningAssistantAvailable: boolean;
  optimizationAvailable: boolean;
  plansAvailable: boolean;
  sourceMode: string;
}

interface StatusRowProps {
  label: string;
  value: string;
  tone?: 'ready' | 'muted';
}

function StatusRow({ label, value, tone = 'ready' }: StatusRowProps) {
  return (
    <div className="workbench-status-row">
      <span className="workbench-status-row__label">{label}</span>
      <span
        className={`workbench-status-badge ${
          tone === 'ready'
            ? 'workbench-status-badge--ready'
            : 'workbench-status-badge--muted'
        }`}
      >
        {value}
      </span>
    </div>
  );
}

export function SystemStatusCard({
  datasetLoaded,
  environmentalValuesAvailable,
  zoningAssistantAvailable,
  optimizationAvailable,
  plansAvailable,
  sourceMode,
}: SystemStatusCardProps) {
  return (
    <section className="workbench-card workbench-panel-card">
      <header className="workbench-section-header">
        <div>
          <h2 className="workbench-section-title">System / Data Status</h2>
          <p className="workbench-section-description">
            Lightweight transparency about the current workspace runtime.
          </p>
        </div>
      </header>

      <div className="workbench-status-list">
        <StatusRow
          label="Parcel Dataset"
          value={datasetLoaded ? 'Loaded' : 'Unavailable'}
          tone={datasetLoaded ? 'ready' : 'muted'}
        />
        <StatusRow
          label="Environmental Values"
          value={environmentalValuesAvailable ? 'Available' : 'Unavailable'}
          tone={environmentalValuesAvailable ? 'ready' : 'muted'}
        />
        <StatusRow
          label="Zoning Assistant"
          value={zoningAssistantAvailable ? 'Available' : 'Unavailable'}
          tone={zoningAssistantAvailable ? 'ready' : 'muted'}
        />
        <StatusRow
          label="Optimization"
          value={optimizationAvailable ? 'Ready' : 'Select Parcels'}
          tone={optimizationAvailable ? 'ready' : 'muted'}
        />
        <StatusRow
          label="Plans"
          value={plansAvailable ? 'Available' : 'None Yet'}
          tone={plansAvailable ? 'ready' : 'muted'}
        />
        <StatusRow label="Source Mode" value={sourceMode} tone="ready" />
      </div>
    </section>
  );
}
