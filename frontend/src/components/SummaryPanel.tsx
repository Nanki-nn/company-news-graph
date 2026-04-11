type SummaryPanelProps = {
  companyName: string;
};

export function SummaryPanel({ companyName }: SummaryPanelProps) {
  return (
    <section className="summary-grid">
      <article className="summary-card">
        <span>Company</span>
        <strong>{companyName}</strong>
      </article>
      <article className="summary-card">
        <span>Events</span>
        <strong>2</strong>
      </article>
      <article className="summary-card">
        <span>Sources</span>
        <strong>2</strong>
      </article>
      <article className="summary-card">
        <span>Top Types</span>
        <strong>Launch, Partnership</strong>
      </article>
    </section>
  );
}
