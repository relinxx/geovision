interface SummaryCardItem {
  label: string;
  value: string;
  tone?: 'accent' | 'cyan' | 'warning' | 'neutral';
}

interface WorkbenchSummaryCardsProps {
  items: SummaryCardItem[];
}

export function WorkbenchSummaryCards({ items }: WorkbenchSummaryCardsProps) {
  return (
    <section className="workbench-summary-grid" aria-label="Workbench summary metrics">
      {items.map((item) => (
        <article key={item.label} className="workbench-card workbench-summary-card">
          <div className="workbench-summary-card__label">{item.label}</div>
          <div
            className={`workbench-summary-card__value workbench-summary-card__value--${
              item.tone ?? 'neutral'
            }`}
          >
            {item.value}
          </div>
        </article>
      ))}
    </section>
  );
}
