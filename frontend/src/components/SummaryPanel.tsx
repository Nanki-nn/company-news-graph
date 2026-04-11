import type { Locale } from "../lib/i18n";
import { formatTopEventTypes, messages, translateGraphTerm } from "../lib/i18n";
import type { GraphResponse } from "../lib/api";

type SummaryPanelProps = {
  companyName: string;
  locale: Locale;
  graph: GraphResponse | null;
};

export function SummaryPanel({ companyName, locale, graph }: SummaryPanelProps) {
  const copy = messages[locale];
  const topTypes = graph
    ? formatTopEventTypes(graph.summary.top_event_types, locale)
    : copy.topTypesValue;
  const eventNodes = graph?.nodes.filter((node) => node.type === "Event") ?? [];
  const generators = Array.from(
    new Set(
      eventNodes
        .map((node) => node.data?.generated_by)
        .filter((value): value is string => typeof value === "string" && value.length > 0)
    )
  );
  const aiStatus = generators.length === 0
    ? copy.aiDisabled
    : generators.every((value) => value === "rules")
      ? copy.aiDisabled
      : generators.some((value) => value === "rules")
        ? copy.aiMixed
        : copy.aiEnabled;
  const aiProvider = generators.length === 0 ? "-" : generators.map((value) => translateGraphTerm(value, locale)).join(", ");
  const aiReasons = Array.from(
    new Set(
      eventNodes
        .map((node) => node.data?.ai_reason)
        .filter((value): value is string => typeof value === "string" && value.length > 0)
    )
  );
  const aiReason = aiStatus === copy.aiDisabled || aiStatus === copy.aiMixed
    ? (aiReasons[0] ?? "-")
    : "-";

  return (
    <section className="summary-grid">
      <article className="summary-card">
        <span>{copy.targetCompany}</span>
        <strong>{companyName}</strong>
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
      <article className="summary-card">
        <span>{copy.aiStatus}</span>
        <strong>{aiStatus}</strong>
      </article>
      <article className="summary-card">
        <span>{copy.aiProvider}</span>
        <strong>{aiProvider}</strong>
      </article>
      <article className="summary-card">
        <span>{copy.aiReason}</span>
        <strong>{aiReason}</strong>
      </article>
    </section>
  );
}
