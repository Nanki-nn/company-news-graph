import type { Locale } from "../lib/i18n";
import { formatTopEventTypes, messages } from "../lib/i18n";
import type { GraphResponse } from "../lib/api";

type SummaryPanelProps = {
  companyName: string;
  ticker: string;
  startDate: string;
  endDate: string;
  locale: Locale;
  graph: GraphResponse | null;
};

export function SummaryPanel({ companyName, ticker, startDate, endDate, locale, graph }: SummaryPanelProps) {
  const copy = messages[locale];
  const topTypes = graph
    ? formatTopEventTypes(graph.summary.top_event_types, locale)
    : copy.topTypesValue;
  const timeRange = `${startDate} -> ${endDate}`;

  return (
    <section className="summary-grid">
      <article className="summary-card">
        <span>{copy.targetCompany}</span>
        <strong>{ticker ? `${companyName} (${ticker})` : companyName}</strong>
      </article>
      <article className="summary-card">
        <span>{copy.timeRangeLabel}</span>
        <strong>{timeRange}</strong>
      </article>
      <article className="summary-card">
        <span>{copy.eventCount}</span>
        <strong>{graph?.summary.event_count ?? 0}</strong>
      </article>
      <article className="summary-card">
        <span>{copy.sourceCount}</span>
        <strong>{graph?.summary.source_count ?? 0}</strong>
      </article>
      <article className="summary-card">
        <span>{copy.topTypes}</span>
        <strong>{topTypes}</strong>
      </article>
    </section>
  );
}
