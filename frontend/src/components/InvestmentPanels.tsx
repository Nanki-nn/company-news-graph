import type { GraphNode, GraphResponse } from "../lib/api";
import type { Locale } from "../lib/i18n";
import { formatFieldLabel, messages, translateGraphTerm } from "../lib/i18n";

type InvestmentPanelsProps = {
  graph: GraphResponse | null;
  locale: Locale;
};

type EventNode = GraphNode & {
  data?: Record<string, unknown>;
};

export function InvestmentPanels({ graph, locale }: InvestmentPanelsProps) {
  const copy = messages[locale];
  const eventNodes = (graph?.nodes.filter((node) => node.type === "Event") as EventNode[] | undefined) ?? [];
  const timelineEvents = [...eventNodes].sort((left, right) => {
    const leftDate = String(left.data?.date ?? "");
    const rightDate = String(right.data?.date ?? "");
    return rightDate.localeCompare(leftDate);
  });
  const keyEvents = [...eventNodes]
    .sort((left, right) => scoreEvent(right) - scoreEvent(left))
    .slice(0, 3);

  return (
    <section className="investment-panels">
      <article className="graph-card">
        <h2>{copy.keyEventsTitle}</h2>
        {keyEvents.length === 0 ? (
          <div className="empty-state compact">{copy.noKeyEvents}</div>
        ) : (
          <div className="key-event-grid">
            {keyEvents.map((event) => (
              <article
                key={event.id}
                className={`key-event-card impact-${String(event.data?.impact_direction ?? "neutral")}`}
              >
                <strong>{String(event.data?.title ?? event.label)}</strong>
                <div className="detail-meta-list">
                  <div className="detail-meta-item">
                    <span>{formatFieldLabel("event_type", locale)}</span>
                    <strong>{translateGraphTerm(String(event.data?.event_type ?? "news"), locale)}</strong>
                  </div>
                  <div className="detail-meta-item">
                    <span>{formatFieldLabel("impact_direction", locale)}</span>
                    <strong>{translateGraphTerm(String(event.data?.impact_direction ?? "neutral"), locale)}</strong>
                  </div>
                  <div className="detail-meta-item">
                    <span>{formatFieldLabel("impact_level", locale)}</span>
                    <strong>{translateGraphTerm(String(event.data?.impact_level ?? "low"), locale)}</strong>
                  </div>
                  <div className="detail-meta-item">
                    <span>{formatFieldLabel("officialness", locale)}</span>
                    <strong>{translateGraphTerm(String(event.data?.officialness ?? "media"), locale)}</strong>
                  </div>
                  <div className="detail-meta-item">
                    <span>{formatFieldLabel("price_sensitive", locale)}</span>
                    <strong>{translateGraphTerm(String(event.data?.price_sensitive ?? false), locale)}</strong>
                  </div>
                </div>
                <p>{String(event.data?.summary ?? "")}</p>
              </article>
            ))}
          </div>
        )}
      </article>
      <article className="graph-card">
        <h2>{copy.timelineTitle}</h2>
        {timelineEvents.length === 0 ? (
          <div className="empty-state compact">{copy.noKeyEvents}</div>
        ) : (
          <ol className="timeline-list">
            {timelineEvents.map((event) => (
              <li key={event.id} className="timeline-item">
                <div className="timeline-date">{String(event.data?.date ?? "-")}</div>
                <div className={`timeline-body impact-${String(event.data?.impact_direction ?? "neutral")}`}>
                  <strong>{String(event.data?.title ?? event.label)}</strong>
                  <span>
                    {[
                      translateGraphTerm(String(event.data?.event_type ?? "news"), locale),
                      translateGraphTerm(String(event.data?.impact_direction ?? "neutral"), locale),
                      translateGraphTerm(String(event.data?.officialness ?? "media"), locale),
                      translateGraphTerm(String(event.data?.impact_level ?? "low"), locale)
                    ].join(" · ")}
                  </span>
                </div>
              </li>
            ))}
          </ol>
        )}
      </article>
    </section>
  );
}

function scoreEvent(event: EventNode): number {
  const eventType = String(event.data?.event_type ?? "news");
  const impactLevel = String(event.data?.impact_level ?? "low");
  const officialness = String(event.data?.officialness ?? "media");
  const articleCount = Number(event.data?.article_count ?? 0);
  if (eventType === "earnings_schedule") {
    return -100;
  }
  const impactScore = impactLevel === "high" ? 30 : impactLevel === "medium" ? 20 : 10;
  const sourceScore = officialness === "mixed" ? 15 : officialness === "official" ? 12 : 6;
  return impactScore + sourceScore + articleCount;
}
