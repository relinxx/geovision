interface WorkbenchAction {
  title: string;
  description: string;
  readiness: string;
  ready: boolean;
  ctaLabel: string;
  onClick: () => void;
}

interface NextActionsCardProps {
  actions: WorkbenchAction[];
}

export function NextActionsCard({ actions }: NextActionsCardProps) {
  return (
    <section className="workbench-card workbench-panel-card">
      <header className="workbench-section-header">
        <div>
          <h2 className="workbench-section-title">Recommended Next Actions</h2>
          <p className="workbench-section-description">
            Fast workflow handoff based on the current workspace state.
          </p>
        </div>
      </header>

      <div className="workbench-action-list">
        {actions.map((action) => (
          <article key={action.title} className="workbench-action-tile">
            <div className="workbench-action-tile__content">
              <div className="workbench-action-tile__title-row">
                <h3 className="workbench-action-tile__title">{action.title}</h3>
                <span
                  className={`workbench-status-badge ${
                    action.ready
                      ? 'workbench-status-badge--ready'
                      : 'workbench-status-badge--blocked'
                  }`}
                >
                  {action.readiness}
                </span>
              </div>
              <p className="workbench-action-tile__description">{action.description}</p>
            </div>
            <button type="button" className="workbench-secondary-btn" onClick={action.onClick}>
              {action.ctaLabel}
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}
