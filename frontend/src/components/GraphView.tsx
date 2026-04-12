import { useEffect, useMemo, useRef, useState } from "react";
import cytoscape from "cytoscape";

import type { GraphEdge, GraphNode, GraphResponse, TaskStatusResponse } from "../lib/api";
import type { Locale } from "../lib/i18n";
import { formatFieldLabel, messages, translateGraphTerm } from "../lib/i18n";

type GraphViewProps = {
  graph: GraphResponse | null;
  locale: Locale;
  selectedNodeId?: string | null;
  onSelectNode?: (nodeId: string | null) => void;
  tasks?: TaskStatusResponse[];
  onLoadTask?: (task: TaskStatusResponse) => void;
};

type SelectedElement =
  | { kind: "node"; item: GraphNode }
  | { kind: "edge"; item: GraphEdge };

export function GraphView({
  graph,
  locale,
  selectedNodeId = null,
  onSelectNode,
  tasks = [],
  onLoadTask,
}: GraphViewProps) {
  const copy = messages[locale];
  const [selected, setSelected] = useState<SelectedElement | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [rightPanel, setRightPanel] = useState<"details" | "timeline" | "keyevents" | "history">("details");
  const [showAllTasks, setShowAllTasks] = useState(false);
  const graphContainerRef = useRef<HTMLDivElement | null>(null);
  const graphCardRef = useRef<HTMLElement | null>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const timelineItemRefs = useRef<Map<string, HTMLLIElement>>(new Map());
  const internalSelectRef = useRef(false);
  const legendItems = [
    { type: "Company", color: "#0f6cbd" },
    { type: "Event", color: "#efb814" },
    { type: "Product", color: "#14b8a6" },
    { type: "Person", color: "#6366f1" },
    { type: "Location", color: "#0f766e" },
    { type: "Regulator", color: "#475569" },
    { type: "Source", color: "#7c3aed" }
  ];
  const impactLegendItems = [
    { label: copy.impactPositive, color: "#16a34a" },
    { label: copy.impactNegative, color: "#dc2626" },
    { label: copy.impactNeutral, color: "#f59e0b" }
  ];

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

  const timelineEvents = useMemo(() => {
    if (!graph) return [];
    return graph.nodes
      .filter((node) => node.type === "Event")
      .sort((a, b) => {
        const aDate = String(a.data?.date ?? "");
        const bDate = String(b.data?.date ?? "");
        return bDate.localeCompare(aDate);
      });
  }, [graph]);

  const keyEvents = useMemo(() => {
    if (!graph) return [];
    return graph.nodes
      .filter((node) => node.type === "Event")
      .sort((a, b) => scoreGraphNode(b) - scoreGraphNode(a))
      .slice(0, 3);
  }, [graph]);

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
          rawType: node.type,
          rawImpact: String(node.data?.impact_direction ?? "neutral"),
          rawImpactLevel: String(node.data?.impact_level ?? "low")
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
    const targetNode =
      (selectedNodeId ? graph.nodes.find((node) => node.id === selectedNodeId) : null) ?? graph.nodes[0];
    setSelected({ kind: "node", item: targetNode });
  }, [graph, selectedNodeId]);

  useEffect(() => {
    const handleFullscreenChange = () => {
      const fullscreenElement = document.fullscreenElement;
      setIsFullscreen(Boolean(fullscreenElement && graphCardRef.current && fullscreenElement === graphCardRef.current));
      window.setTimeout(() => {
        cyRef.current?.resize();
        cyRef.current?.fit(undefined, 48);
      }, 50);
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, []);

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
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      autoungrabify: false,
      autounselectify: false,
      minZoom: 0.25,
      maxZoom: 5,
      wheelSensitivity: 0.7,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "text-wrap": "wrap",
            "text-max-width": 96,
            "font-size": 11,
            "font-weight": 700,
            color: "#ffffff",
            "text-valign": "center",
            "text-halign": "center",
            "text-outline-color": "rgba(15, 23, 42, 0.42)",
            "text-outline-width": 2,
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
            "background-color": "#efb814",
            color: "#102a43",
            "text-outline-color": "rgba(255, 255, 255, 0.55)"
          }
        },
        {
          selector: 'node[rawType = "Event"][rawImpact = "positive"]',
          style: {
            "background-color": "#16a34a",
            color: "#ffffff",
            "text-outline-color": "rgba(15, 23, 42, 0.42)"
          }
        },
        {
          selector: 'node[rawType = "Event"][rawImpact = "negative"]',
          style: {
            "background-color": "#dc2626",
            color: "#ffffff",
            "text-outline-color": "rgba(15, 23, 42, 0.42)"
          }
        },
        {
          selector: 'node[rawType = "Event"][rawImpact = "neutral"]',
          style: {
            "background-color": "#f59e0b",
            color: "#102a43",
            "text-outline-color": "rgba(255, 255, 255, 0.55)"
          }
        },
        {
          selector: 'node[rawType = "Event"][rawImpactLevel = "high"]',
          style: {
            width: 70,
            height: 70
          }
        },
        {
          selector: 'node[rawType = "Event"][rawImpactLevel = "medium"]',
          style: {
            width: 62,
            height: 62
          }
        },
        {
          selector: 'node[rawType = "Product"]',
          style: {
            "background-color": "#14b8a6",
            color: "#ffffff"
          }
        },
        {
          selector: 'node[rawType = "Person"]',
          style: {
            "background-color": "#6366f1",
            color: "#ffffff"
          }
        },
        {
          selector: 'node[rawType = "Location"]',
          style: {
            "background-color": "#0f766e",
            color: "#ffffff"
          }
        },
        {
          selector: 'node[rawType = "Regulator"]',
          style: {
            "background-color": "#475569",
            color: "#ffffff"
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
            "border-color": "#ffffff",
            "border-width": 5,
            "overlay-color": "#0f6cbd",
            "overlay-opacity": 0.22,
            "overlay-padding": 7,
          }
        },
        {
          selector: "node.hovered:not(:selected)",
          style: {
            "border-color": "rgba(255,255,255,0.9)",
            "border-width": 4,
            "overlay-color": "#ffffff",
            "overlay-opacity": 0.14,
            "overlay-padding": 4,
          }
        },
        {
          selector: ".dimmed",
          style: {
            opacity: 0.12,
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
    cyRef.current = cy;

    cy.on("tap", "node", (event) => {
      const item = nodeMap.get(event.target.id());
      if (item) {
        internalSelectRef.current = true;
        setSelected({ kind: "node", item });
        onSelectNode?.(item.id);
        setRightPanel("details");
        cy.elements().addClass("dimmed");
        event.target.closedNeighborhood().removeClass("dimmed");
      }
    });

    cy.on("tap", "edge", (event) => {
      const item = graph.edges.find((edge) => edge.id === event.target.id());
      if (item) {
        setSelected({ kind: "edge", item });
        cy.elements().addClass("dimmed");
        event.target.connectedNodes().closedNeighborhood().removeClass("dimmed");
        event.target.removeClass("dimmed");
      }
    });

    cy.on("tap", (event) => {
      if (event.target === cy) {
        cy.elements().removeClass("dimmed");
      }
    });

    cy.on("dblclick", (event) => {
      if (event.target === cy) {
        cy.animate({ fit: { eles: cy.elements(), padding: 32 }, duration: 250 });
      }
    });

    cy.on("mouseover", "node", (event) => {
      event.target.addClass("hovered");
      if (graphContainerRef.current) graphContainerRef.current.style.cursor = "pointer";
    });
    cy.on("mouseout", "node", (event) => {
      event.target.removeClass("hovered");
      if (graphContainerRef.current) graphContainerRef.current.style.cursor = "default";
    });
    cy.on("mouseover", "edge", () => {
      if (graphContainerRef.current) graphContainerRef.current.style.cursor = "pointer";
    });
    cy.on("mouseout", "edge", () => {
      if (graphContainerRef.current) graphContainerRef.current.style.cursor = "default";
    });

    return () => {
      cyRef.current = null;
      cy.destroy();
    };
  }, [elements, graph, nodeMap, onSelectNode]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) {
      return;
    }
    cy.elements().unselect().removeClass("dimmed");
    if (!selectedNodeId) {
      return;
    }
    const target = cy.getElementById(selectedNodeId);
    if (target.nonempty()) {
      target.select();
      const fromOutside = !internalSelectRef.current;
      internalSelectRef.current = false;
      if (fromOutside) {
        cy.animate({
          fit: { eles: target.closedNeighborhood(), padding: 80 },
          duration: 250
        });
      }
      const item = nodeMap.get(selectedNodeId);
      if (item) {
        setSelected({ kind: "node", item });
      }
      cy.elements().addClass("dimmed");
      target.closedNeighborhood().removeClass("dimmed");
    }
  }, [selectedNodeId, nodeMap]);

  useEffect(() => {
    if (tasks.length > 0 && !graph) {
      setRightPanel("history");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tasks.length]);

  useEffect(() => {
    if (graph) {
      setRightPanel("timeline");
    }
  }, [graph]);

  useEffect(() => {
    if (rightPanel !== "timeline" || !selectedNodeId) return;
    const el = timelineItemRefs.current.get(selectedNodeId);
    el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedNodeId, rightPanel]);

  function fitGraph() {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("dimmed").unselect();
    setSelected(null);
    onSelectNode?.(null);
    cy.animate({ fit: { eles: cy.elements(), padding: 32 }, duration: 250 });
  }

  function zoomGraph(direction: "in" | "out") {
    const cy = cyRef.current;
    if (!cy) return;
    const currentZoom = cy.zoom();
    const factor = direction === "in" ? 1.18 : 1 / 1.18;
    const nextZoom = Math.max(cy.minZoom(), Math.min(cy.maxZoom(), currentZoom * factor));
    cy.animate({
      zoom: {
        level: nextZoom,
        renderedPosition: {
          x: cy.width() / 2,
          y: cy.height() / 2,
        },
      },
      duration: 180,
    });
  }

  async function toggleFullscreen() {
    const element = graphCardRef.current;
    if (!element) {
      return;
    }
    if (document.fullscreenElement === element) {
      await document.exitFullscreen();
      return;
    }
    await element.requestFullscreen();
  }

  return (
    <section className="graph-layout">
      <div
        ref={graphCardRef}
        className={`graph-card${isFullscreen ? " is-fullscreen" : ""}`}
      >
        <div className={`graph-columns graph-columns-wide${isFullscreen ? " is-fullscreen" : ""}`}>
            <div className="cytoscape-panel">
              {!graph ? (
                <div className="empty-state">{copy.noGraph}</div>
              ) : (
                <>
                  <div className="graph-toolbar">
                    <span className="graph-badge">
                      {copy.nodes}: {graph.nodes.length}
                    </span>
                    <span className="graph-badge">
                      {copy.edges}: {graph.edges.length}
                    </span>
                    <button
                      type="button"
                      className="graph-action-button"
                      onClick={() => zoomGraph("out")}
                      aria-label={locale === "zh" ? "缩小图谱" : "Zoom out"}
                      title={locale === "zh" ? "缩小图谱" : "Zoom out"}
                    >
                      -
                    </button>
                    <button
                      type="button"
                      className="graph-action-button"
                      onClick={() => zoomGraph("in")}
                      aria-label={locale === "zh" ? "放大图谱" : "Zoom in"}
                      title={locale === "zh" ? "放大图谱" : "Zoom in"}
                    >
                      +
                    </button>
                    <button
                      type="button"
                      className="graph-action-button"
                      onClick={fitGraph}
                    >
                      {locale === "zh" ? "适应视图" : "Fit View"}
                    </button>
                    <button
                      type="button"
                      className="graph-action-button"
                      onClick={toggleFullscreen}
                    >
                      {isFullscreen ? copy.exitFullscreen : copy.enterFullscreen}
                    </button>
                  </div>
                  <div className="graph-legend" aria-label={copy.graphLegend}>
                    <span className="graph-legend-title">{copy.graphLegend}</span>
                    <ul className="graph-legend-list">
                      {legendItems.map((item) => (
                        <li key={item.type} className="graph-legend-item">
                          <span
                            className="graph-legend-dot"
                            style={{ backgroundColor: item.color }}
                            aria-hidden="true"
                          />
                          <span>{translateGraphTerm(item.type, locale)}</span>
                        </li>
                      ))}
                    </ul>
                    <ul className="graph-legend-list">
                      {impactLegendItems.map((item) => (
                        <li key={item.label} className="graph-legend-item">
                          <span
                            className="graph-legend-dot"
                            style={{ backgroundColor: item.color }}
                            aria-hidden="true"
                          />
                          <span>{item.label}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div ref={graphContainerRef} className="graph-canvas" />
                </>
              )}
            </div>
            <div className="details-panel">
              <div className="panel-tabs">
                <button
                  type="button"
                  className={`panel-tab${rightPanel === "details" ? " is-active" : ""}`}
                  onClick={() => setRightPanel("details")}
                >
                  {copy.details}
                </button>
                <button
                  type="button"
                  className={`panel-tab${rightPanel === "timeline" ? " is-active" : ""}`}
                  onClick={() => setRightPanel("timeline")}
                >
                  {copy.timelineTitle}
                </button>
                <button
                  type="button"
                  className={`panel-tab${rightPanel === "keyevents" ? " is-active" : ""}`}
                  onClick={() => setRightPanel("keyevents")}
                >
                  {copy.keyEventsTitle}
                </button>
                <button
                  type="button"
                  className={`panel-tab${rightPanel === "history" ? " is-active" : ""}`}
                  onClick={() => setRightPanel("history")}
                >
                  {copy.taskHistory}
                </button>
              </div>
              {rightPanel === "details" ? (
                selected ? (
                  <SelectedDetails
                    selected={selected}
                    nodeMap={nodeMap}
                    nodeLabelMap={nodeLabelMap}
                    locale={locale}
                  />
                ) : (
                  <div className="empty-state compact">{copy.selectHint}</div>
                )
              ) : rightPanel === "keyevents" ? (
                keyEvents.length === 0 ? (
                  <div className="empty-state compact">{copy.noKeyEvents}</div>
                ) : (
                  <div className="key-event-grid">
                    {keyEvents.map((event) => (
                      <article
                        key={event.id}
                        className={`key-event-card impact-${String(event.data?.impact_direction ?? "neutral")}${selectedNodeId === event.id ? " is-selected" : ""}`}
                        onClick={() => onSelectNode?.(event.id)}
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
                )
              ) : rightPanel === "timeline" ? (
                timelineEvents.length === 0 ? (
                  <div className="empty-state compact">{copy.selectHint}</div>
                ) : (
                  <ol className="timeline-list">
                    {timelineEvents.map((event) => (
                      <li
                        key={event.id}
                        ref={(el) => {
                          if (el) timelineItemRefs.current.set(event.id, el);
                          else timelineItemRefs.current.delete(event.id);
                        }}
                        className="timeline-item"
                      >
                        <div className="timeline-date">{String(event.data?.date ?? "-")}</div>
                        <div
                          className={`timeline-body impact-${String(event.data?.impact_direction ?? "neutral")}${selectedNodeId === event.id ? " is-selected" : ""}`}
                          onClick={() => onSelectNode?.(event.id)}
                        >
                          <strong>{String(event.data?.title ?? event.label)}</strong>
                          <span>
                            {[
                              translateGraphTerm(String(event.data?.event_type ?? "news"), locale),
                              translateGraphTerm(String(event.data?.impact_direction ?? "neutral"), locale),
                              translateGraphTerm(String(event.data?.impact_level ?? "low"), locale),
                            ].join(" · ")}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ol>
                )
              ) : (
                <div className="task-history">
                  <div className="task-history-header">
                    <strong>{copy.taskHistory}</strong>
                    {tasks.length > 0 ? <span>{copy.taskCount.replace("{count}", String(tasks.length))}</span> : null}
                  </div>
                  {tasks.length === 0 ? (
                    <p className="task-history-empty">{copy.noTasks}</p>
                  ) : (
                    <>
                      <ul className={`task-history-list${showAllTasks ? " expanded" : ""}`}>
                        {(showAllTasks ? tasks : tasks.slice(0, 5)).map((task) => (
                          <li key={task.task_id} className="task-history-item">
                            <div>
                              <strong>{task.ticker || task.company_name}</strong>
                              <span>
                                {[
                                  task.company_name,
                                  task.report_mode === "ai" ? "AI" : "Rules",
                                  `${task.start_date} → ${task.end_date}`,
                                  formatTaskCreatedAt(task.created_at, locale),
                                ].join(" · ")}
                              </span>
                            </div>
                            <button type="button" onClick={() => onLoadTask?.(task)}>
                              {copy.loadTask}
                            </button>
                          </li>
                        ))}
                      </ul>
                      {tasks.length > 5 ? (
                        <button
                          type="button"
                          className="task-history-toggle"
                          onClick={() => setShowAllTasks((v) => !v)}
                        >
                          {showAllTasks
                            ? copy.showLessTasks
                            : copy.showMoreTasks.replace("{count}", String(tasks.length - 5))}
                        </button>
                      ) : null}
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
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
      </div>
    );
  }

  const node = selected.item;
  const eventEntries = getOrderedEntries(node, ["date", "article_count", "confidence"] as const);
  const sourceEntries = getOrderedEntries(node, ["source_name", "published_date"] as const);
  const entityEntries = getOrderedEntries(node, ["entity_type", "role", "ticker"] as const);
  const entityDescription =
    typeof node.data?.description === "string" && node.data.description.trim().length > 0
      ? node.data.description.trim()
      : "";
  const articles = Array.isArray(node.data?.articles) ? node.data.articles : [];
  const keyPoints = Array.isArray(node.data?.key_points) ? node.data.key_points : [];
  const displayTitle = typeof node.data?.title === "string" && node.data.title.length > 0
    ? node.data.title
    : translateGraphTerm(node.label, locale);
  const compactMetaEntries = node.type === "Source" ? sourceEntries : node.type === "Event" ? eventEntries : entityEntries;
  const compactSourceEntries = node.type === "Event" ? sourceEntries : [];

  return (
    <div className="detail-card">
      <div className="detail-title">{displayTitle}</div>
      {entityDescription ? (
        <div className="detail-paragraph">{entityDescription}</div>
      ) : null}
      {compactMetaEntries.length > 0 ? (
        <CompactMeta entries={compactMetaEntries} locale={locale} nodeMap={nodeMap} />
      ) : null}
      {keyPoints.length > 0 ? (
        <KeyPointsSection items={keyPoints} locale={locale} />
      ) : null}
      {compactSourceEntries.length > 0 ? (
        <CompactMeta entries={compactSourceEntries} locale={locale} nodeMap={nodeMap} />
      ) : null}
      {articles.length > 0 ? (
        <RelatedArticlesSection articles={articles} locale={locale} />
      ) : null}
    </div>
  );
}

function CompactMeta({
  entries,
  locale,
  nodeMap
}: {
  entries: Array<[string, unknown]>;
  locale: Locale;
  nodeMap: Map<string, GraphNode>;
}) {
  return (
    <div className="detail-meta-list">
      {entries.map(([key, value]) => (
        <div key={key} className="detail-meta-item">
          <span>{formatFieldLabel(key, locale)}</span>
          <strong>{formatValue(value, locale, nodeMap)}</strong>
        </div>
      ))}
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
              {article.source_url ? (
                <a href={article.source_url} target="_blank" rel="noreferrer" className="article-title-link">
                  {article.title || article.source_name || `Article ${index + 1}`}
                </a>
              ) : (
                <strong>{article.title || article.source_name || `Article ${index + 1}`}</strong>
              )}
              <span>
                {[article.source_name, article.published_date].filter(Boolean).join(" · ")}
              </span>
            </div>
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

function scoreGraphNode(node: GraphNode): number {
  const eventType = String(node.data?.event_type ?? "news");
  const impactLevel = String(node.data?.impact_level ?? "low");
  const officialness = String(node.data?.officialness ?? "media");
  const articleCount = Number(node.data?.article_count ?? 0);
  if (eventType === "earnings_schedule") return -100;
  const impactScore = impactLevel === "high" ? 30 : impactLevel === "medium" ? 20 : 10;
  const sourceScore = officialness === "mixed" ? 15 : officialness === "official" ? 12 : 6;
  return impactScore + sourceScore + articleCount;
}

function formatTaskCreatedAt(value: string, locale: Locale): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(locale === "zh" ? "zh-CN" : "en-US", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}
