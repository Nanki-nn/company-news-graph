import { useEffect, useMemo, useRef, useState } from "react";
import cytoscape from "cytoscape";

import type { GraphEdge, GraphNode, GraphResponse } from "../lib/api";
import type { Locale } from "../lib/i18n";
import { formatFieldLabel, messages, translateGraphTerm } from "../lib/i18n";

type GraphViewProps = {
  graph: GraphResponse | null;
  locale: Locale;
};

type SelectedElement =
  | { kind: "node"; item: GraphNode }
  | { kind: "edge"; item: GraphEdge };

export function GraphView({ graph, locale }: GraphViewProps) {
  const copy = messages[locale];
  const [selected, setSelected] = useState<SelectedElement | null>(null);
  const graphContainerRef = useRef<HTMLDivElement | null>(null);

  const nodeMap = useMemo(
    () => new Map(graph?.nodes.map((node) => [node.id, node]) ?? []),
    [graph]
  );

  const nodeLabelMap = useMemo(
    () =>
      new Map(
        graph?.nodes.map((node) => [node.id, translateGraphTerm(node.label, locale)]) ?? []
      ),
    [graph, locale]
  );

  const elements = useMemo(() => {
    if (!graph) {
      return [];
    }

    return [
      ...graph.nodes.map((node) => ({
        data: {
          id: node.id,
          label: translateGraphTerm(node.label, locale),
          type: translateGraphTerm(node.type, locale),
          rawType: node.type
        }
      })),
      ...graph.edges.map((edge) => ({
        data: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: translateGraphTerm(edge.label, locale),
          rawType: edge.type
        }
      }))
    ];
  }, [graph, locale]);

  useEffect(() => {
    if (!graph) {
      setSelected(null);
      return;
    }
    setSelected({ kind: "node", item: graph.nodes[0] });
  }, [graph]);

  useEffect(() => {
    if (!graphContainerRef.current || !graph) {
      return;
    }

    const cy = cytoscape({
      container: graphContainerRef.current,
      elements,
      layout: {
        name: "cose",
        animate: false,
        padding: 24
      },
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "text-wrap": "wrap",
            "text-max-width": 120,
            "font-size": 12,
            "font-weight": 700,
            color: "#102a43",
            "text-valign": "center",
            "text-halign": "center",
            "background-color": "#9fb3c8",
            width: 56,
            height: 56,
            padding: 10,
            "border-width": 2,
            "border-color": "#ffffff"
          }
        },
        {
          selector: 'node[rawType = "Company"]',
          style: {
            "background-color": "#0f6cbd",
            color: "#ffffff"
          }
        },
        {
          selector: 'node[rawType = "Event"]',
          style: {
            "background-color": "#efb814"
          }
        },
        {
          selector: 'node[rawType = "Product"]',
          style: {
            "background-color": "#14b8a6"
          }
        },
        {
          selector: 'node[rawType = "Source"]',
          style: {
            "background-color": "#7c3aed",
            color: "#ffffff"
          }
        },
        {
          selector: "node:selected",
          style: {
            "border-color": "#102a43",
            "border-width": 4
          }
        },
        {
          selector: "edge",
          style: {
            label: "data(label)",
            width: 2,
            "line-color": "#829ab1",
            "target-arrow-color": "#829ab1",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "font-size": 10,
            color: "#486581",
            "text-background-color": "#ffffff",
            "text-background-opacity": 0.9,
            "text-background-padding": 3
          }
        },
        {
          selector: "edge:selected",
          style: {
            width: 4,
            "line-color": "#0f6cbd",
            "target-arrow-color": "#0f6cbd"
          }
        }
      ]
    });

    cy.on("tap", "node", (event) => {
      const item = nodeMap.get(event.target.id());
      if (item) {
        setSelected({ kind: "node", item });
      }
    });

    cy.on("tap", "edge", (event) => {
      const item = graph.edges.find((edge) => edge.id === event.target.id());
      if (item) {
        setSelected({ kind: "edge", item });
      }
    });

    return () => {
      cy.destroy();
    };
  }, [elements, graph, nodeMap]);

  return (
    <section className="graph-layout">
      <div className="graph-card">
        <h2>{copy.graphTitle}</h2>
        <p>{copy.graphDescription}</p>
        {!graph ? (
          <div className="empty-state">{copy.noGraph}</div>
        ) : (
          <div className="graph-columns graph-columns-wide">
            <div className="cytoscape-panel">
              <div className="graph-toolbar">
                <span className="graph-badge">
                  {copy.nodes}: {graph.nodes.length}
                </span>
                <span className="graph-badge">
                  {copy.edges}: {graph.edges.length}
                </span>
              </div>
              <div ref={graphContainerRef} className="graph-canvas" />
            </div>
            <div className="details-panel">
              <h3>{copy.details}</h3>
              {selected ? (
                <SelectedDetails
                  selected={selected}
                  nodeMap={nodeMap}
                  nodeLabelMap={nodeLabelMap}
                  locale={locale}
                />
              ) : (
                <div className="empty-state compact">{copy.selectHint}</div>
              )}
              <h3 className="secondary-heading">{copy.edges}</h3>
              <ul className="token-list">
                {graph.edges.map((edge) => (
                  <li
                    key={edge.id}
                    className={selected?.kind === "edge" && selected.item.id === edge.id ? "is-selected" : ""}
                    onClick={() => setSelected({ kind: "edge", item: edge })}
                  >
                    <strong>{translateGraphTerm(edge.label, locale)}</strong>
                    <span>
                      {nodeLabelMap.get(edge.source) ?? edge.source} {"->"}{" "}
                      {nodeLabelMap.get(edge.target) ?? edge.target}
                    </span>
                  </li>
                ))}
              </ul>
              <h3 className="secondary-heading">{copy.nodes}</h3>
              <ul className="token-list">
                {graph.nodes.map((node) => (
                  <li
                    key={node.id}
                    className={selected?.kind === "node" && selected.item.id === node.id ? "is-selected" : ""}
                    onClick={() => setSelected({ kind: "node", item: node })}
                  >
                    <strong>{translateGraphTerm(node.label, locale)}</strong>
                    <span>{translateGraphTerm(node.type, locale)}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function SelectedDetails({
  selected,
  nodeMap,
  nodeLabelMap,
  locale
}: {
  selected: SelectedElement;
  nodeMap: Map<string, GraphNode>;
  nodeLabelMap: Map<string, string>;
  locale: Locale;
}) {
  const copy = messages[locale];

  if (selected.kind === "edge") {
    const edge = selected.item;
    return (
      <div className="detail-card">
        <div className="detail-title">{translateGraphTerm(edge.label, locale)}</div>
        <div className="detail-row">
          <span>{copy.relationPath}</span>
          <strong>
            {nodeLabelMap.get(edge.source) ?? edge.source} {"->"} {nodeLabelMap.get(edge.target) ?? edge.target}
          </strong>
        </div>
        <div className="detail-row">
          <span>{formatFieldLabel("event_type", locale)}</span>
          <strong>{translateGraphTerm(edge.type, locale)}</strong>
        </div>
      </div>
    );
  }

  const node = selected.item;
  const sourceUrl = getSourceUrl(node);
  const eventFields = [
    "event_type",
    "event_label",
    "date",
    "published_date",
    "published_at",
    "article_count",
    "generated_by",
    "confidence",
    "title",
    "article_title",
    "summary",
    "article_snippet",
    "company_name"
  ] as const;
  const sourceFields = [
    "source_name",
    "source_url",
    "url",
    "published_date",
    "published_at"
  ] as const;
  const eventEntries = getOrderedEntries(node, eventFields);
  const sourceEntries = getOrderedEntries(node, sourceFields);
  const consumedKeys = new Set([...eventEntries, ...sourceEntries].map(([key]) => key));
  const rawEntries = Object.entries(node.data ?? {}).filter(
    ([key, value]) => !consumedKeys.has(key) && value !== "" && value != null
  );
  const articles = Array.isArray(node.data?.articles) ? node.data.articles : [];
  const keyPoints = Array.isArray(node.data?.key_points) ? node.data.key_points : [];

  return (
    <div className="detail-card">
      <div className="detail-title">{translateGraphTerm(node.label, locale)}</div>
      <div className="detail-row">
        <span>{formatFieldLabel("event_type", locale)}</span>
        <strong>{translateGraphTerm(node.type, locale)}</strong>
      </div>
      {eventEntries.length > 0 ? (
        <DetailSection
          title={keyPoints.length > 0 ? copy.aiSummary : copy.eventInfo}
          entries={eventEntries}
          locale={locale}
          nodeMap={nodeMap}
        />
      ) : null}
      {keyPoints.length > 0 ? (
        <KeyPointsSection items={keyPoints} locale={locale} />
      ) : null}
      {sourceEntries.length > 0 ? (
        <DetailSection
          title={copy.sourceInfo}
          entries={sourceEntries}
          locale={locale}
          nodeMap={nodeMap}
        />
      ) : null}
      {articles.length > 0 ? (
        <RelatedArticlesSection articles={articles} locale={locale} />
      ) : null}
      {rawEntries.length > 0 ? (
        <DetailSection
          title={copy.rawData}
          entries={rawEntries}
          locale={locale}
          nodeMap={nodeMap}
        />
      ) : null}
      {sourceUrl ? (
        <a className="detail-link" href={sourceUrl} target="_blank" rel="noreferrer">
          {copy.sourceLink}
        </a>
      ) : null}
    </div>
  );
}

function KeyPointsSection({
  items,
  locale
}: {
  items: unknown[];
  locale: Locale;
}) {
  return (
    <section className="detail-section">
      <div className="detail-section-title">{messages[locale].keyPoints}</div>
      <ul className="key-points-list">
        {items.map((item, index) => (
          <li key={index}>{translateGraphTerm(String(item), locale)}</li>
        ))}
      </ul>
    </section>
  );
}

function RelatedArticlesSection({
  articles,
  locale
}: {
  articles: unknown[];
  locale: Locale;
}) {
  const copy = messages[locale];
  const normalizedArticles = articles.filter(isArticleRecord);

  return (
    <section className="detail-section">
      <div className="detail-section-title">{copy.relatedArticles}</div>
      <div className="article-list">
        {normalizedArticles.map((article, index) => (
          <article key={`${article.source_url}-${index}`} className="article-card">
            <div className="article-card-header">
              <strong>{article.title || article.source_name || `Article ${index + 1}`}</strong>
              <span>
                {[article.source_name, article.published_date].filter(Boolean).join(" · ")}
              </span>
            </div>
            {article.summary ? <p>{article.summary}</p> : null}
            {article.snippet && article.snippet !== article.summary ? <p>{article.snippet}</p> : null}
            {article.source_url ? (
              <a href={article.source_url} target="_blank" rel="noreferrer" className="detail-link subtle">
                {copy.sourceLink}
              </a>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function DetailSection({
  title,
  entries,
  locale,
  nodeMap
}: {
  title: string;
  entries: Array<[string, unknown]>;
  locale: Locale;
  nodeMap: Map<string, GraphNode>;
}) {
  return (
    <section className="detail-section">
      <div className="detail-section-title">{title}</div>
      {entries.map(([key, value]) => (
        <div key={key} className="detail-row">
          <span>{formatFieldLabel(key, locale)}</span>
          <strong className={isLongTextField(key) ? "detail-text-block" : undefined}>
            {formatValue(value, locale, nodeMap)}
          </strong>
        </div>
      ))}
    </section>
  );
}

function getOrderedEntries(
  node: GraphNode,
  keys: readonly string[]
): Array<[string, unknown]> {
  const data = node.data ?? {};
  return keys
    .map((key) => [key, data[key]] as [string, unknown])
    .filter(([, value]) => value !== "" && value != null);
}

function getSourceUrl(node: GraphNode): string | null {
  const sourceUrl = node.data?.source_url;
  if (typeof sourceUrl === "string" && sourceUrl.length > 0) {
    return sourceUrl;
  }
  const url = node.data?.url;
  if (typeof url === "string" && url.length > 0) {
    return url;
  }
  return null;
}

function isLongTextField(key: string): boolean {
  return key === "summary" || key === "article_snippet" || key === "title" || key === "article_title";
}

function formatValue(
  value: unknown,
  locale: Locale,
  nodeMap: Map<string, GraphNode>
): string {
  if (typeof value === "string") {
    const linkedNode = nodeMap.get(value);
    return linkedNode ? translateGraphTerm(linkedNode.label, locale) : translateGraphTerm(value, locale);
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => formatValue(item, locale, nodeMap)).join(", ");
  }
  return JSON.stringify(value);
}

function isArticleRecord(
  value: unknown
): value is {
  title?: string;
  summary?: string;
  snippet?: string;
  source_name?: string;
  source_url?: string;
  published_date?: string;
} {
  return typeof value === "object" && value !== null;
}
