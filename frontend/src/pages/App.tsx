import React, { useEffect, useState } from "react";

import type { GraphResponse, TaskStatusResponse } from "../lib/api";
import { getResearchGraph, listResearchTasks, runResearchTask } from "../lib/api";
import { GraphView } from "../components/GraphView";
import { SummaryPanel } from "../components/SummaryPanel";
import { messages, type Locale } from "../lib/i18n";

const SUGGESTIONS: { ticker: string; name: string }[] = [
  { ticker: "AAPL", name: "Apple" },
  { ticker: "MSFT", name: "Microsoft" },
  { ticker: "NVDA", name: "NVIDIA" },
  { ticker: "GOOGL", name: "Alphabet" },
  { ticker: "AMZN", name: "Amazon" },
  { ticker: "META", name: "Meta Platforms" },
  { ticker: "TSLA", name: "Tesla" },
  { ticker: "ORCL", name: "Oracle" },
  { ticker: "AMD", name: "Advanced Micro Devices" },
  { ticker: "INTC", name: "Intel" },
  { ticker: "AVGO", name: "Broadcom" },
  { ticker: "QCOM", name: "Qualcomm" },
  { ticker: "TSM", name: "TSMC" },
  { ticker: "IBM", name: "IBM" },
  { ticker: "CRM", name: "Salesforce" },
  { ticker: "ADBE", name: "Adobe" },
  { ticker: "NFLX", name: "Netflix" },
  { ticker: "DIS", name: "Disney" },
  { ticker: "JPM", name: "JPMorgan Chase" },
  { ticker: "GS", name: "Goldman Sachs" },
  { ticker: "BAC", name: "Bank of America" },
  { ticker: "V", name: "Visa" },
  { ticker: "MA", name: "Mastercard" },
  { ticker: "PYPL", name: "PayPal" },
  { ticker: "JNJ", name: "Johnson & Johnson" },
  { ticker: "UNH", name: "UnitedHealth" },
  { ticker: "PFE", name: "Pfizer" },
  { ticker: "WMT", name: "Walmart" },
  { ticker: "MCD", name: "McDonald's" },
  { ticker: "NKE", name: "Nike" },
  { ticker: "XOM", name: "ExxonMobil" },
  { ticker: "BA", name: "Boeing" },
  { ticker: "BABA", name: "Alibaba" },
  { ticker: "BIDU", name: "Baidu" },
  { ticker: "PDD", name: "PDD Holdings" },
  { ticker: "JD", name: "JD.com" },
];

export function App() {
  const loadingStepKeys = [
    "fetching_sources",
    "filtering_articles",
    "clustering_events",
    "summarizing_events",
    "extracting_entities",
    "building_graph",
    "completed",
    "failed"
  ] as const;
  const [query, setQuery] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [locale, setLocale] = useState<Locale>(() => {
    const savedLocale = window.localStorage.getItem("locale");
    return savedLocale === "en" ? "en" : "zh";
  });
  const [startDate, setStartDate] = useState("2026-03-01");
  const [endDate, setEndDate] = useState("2026-04-11");
  const [reportMode, setReportMode] = useState<"ai" | "rules">("ai");
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [tasks, setTasks] = useState<TaskStatusResponse[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [taskStage, setTaskStage] = useState<typeof loadingStepKeys[number]>("fetching_sources");
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const copy = messages[locale];

  useEffect(() => {
    window.localStorage.setItem("locale", locale);
  }, [locale]);

  useEffect(() => {
    let active = true;
    listResearchTasks()
      .then((items) => {
        if (active) {
          setTasks(items);
        }
      })
      .catch(() => {
        if (active) {
          setTasks([]);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const loadingButtonText = copy.running;
  const loadingStatusText =
    taskStage === "completed" || taskStage === "failed"
      ? copy[taskStage]
      : copy[taskStage];
  const q = query.trim().toLowerCase();
  const filteredSuggestions = !q
    ? SUGGESTIONS.slice(0, 8)
    : SUGGESTIONS.filter(
        (item) =>
          item.ticker.toLowerCase().startsWith(q) ||
          item.name.toLowerCase().includes(q)
      ).slice(0, 8);

  function selectSuggestion(item: { ticker: string; name: string }) {
    setQuery(item.ticker);
    setShowSuggestions(false);
    setActiveIndex(-1);
  }

  function handleQueryKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!showSuggestions || filteredSuggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, filteredSuggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, -1));
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      selectSuggestion(filteredSuggestions[activeIndex]);
    } else if (e.key === "Escape") {
      setShowSuggestions(false);
      setActiveIndex(-1);
    }
  }

  function setDateRange(days: number) {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - days);
    setEndDate(end.toISOString().slice(0, 10));
    setStartDate(start.toISOString().slice(0, 10));
  }

  async function handleRunResearch() {
    if (!query.trim()) {
      return;
    }

    setStatus("loading");
    setTaskStage("fetching_sources");
    setErrorMessage("");

    try {
      const normalizedQuery = query.trim();
      const inferredTicker = inferTicker(normalizedQuery);
      const nextGraph = await runResearchTask({
        companyName: normalizedQuery,
        ticker: inferredTicker,
        reportMode,
        startDate,
        endDate,
        locale,
        onTaskUpdate: (task) => {
          if (task.stage) {
            setTaskStage(task.stage);
          }
        }
      });
      setGraph(nextGraph);
      setSelectedEventId(nextGraph.nodes.find((node) => node.type === "Event")?.id ?? null);
      setTasks(await listResearchTasks());
      setStatus("success");
      setTaskStage("completed");
    } catch (error) {
      setStatus("error");
      setTaskStage("failed");
      setErrorMessage(error instanceof Error ? error.message : "Unknown error");
    }
  }

  async function handleLoadTask(task: TaskStatusResponse) {
    setQuery(task.ticker || task.company_name);
    setReportMode(task.report_mode ?? "ai");
    setStartDate(task.start_date);
    setEndDate(task.end_date);
    setStatus("loading");
    setTaskStage(task.stage ?? "fetching_sources");
    setErrorMessage("");

    try {
      const nextGraph = await getResearchGraph(task.task_id);
      setGraph(nextGraph);
      setSelectedEventId(nextGraph.nodes.find((node) => node.type === "Event")?.id ?? null);
      setStatus("success");
      setTaskStage("completed");
    } catch (error) {
      setStatus("error");
      setTaskStage("failed");
      setErrorMessage(error instanceof Error ? error.message : "Unknown error");
    }
  }

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <div className="hero-topbar">
            <p className="eyebrow">{copy.appName}</p>
            <a
              href="https://github.com/Nanki-nn/company-news-graph"
              target="_blank"
              rel="noreferrer"
              className="github-link"
              aria-label="GitHub"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M12 2C6.477 2 2 6.477 2 12c0 4.418 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.009-.868-.013-1.703-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.463-1.11-1.463-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0 1 12 6.836a9.59 9.59 0 0 1 2.504.337c1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.202 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.741 0 .267.18.578.688.48C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
              </svg>
              GitHub
            </a>
          </div>
          <h1>{copy.heroTitle}</h1>
          <p className="subcopy">{copy.heroDescription}</p>
        </div>
        <div className="query-card">
          <label>
            {copy.queryLabel}
            <div className="suggestions-wrapper">
              <input
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setShowSuggestions(true);
                  setActiveIndex(-1);
                }}
                onFocus={() => setShowSuggestions(true)}
                onBlur={() => setTimeout(() => setShowSuggestions(false), 120)}
                onKeyDown={handleQueryKeyDown}
                placeholder={copy.queryPlaceholder}
                autoComplete="off"
              />
              {showSuggestions && filteredSuggestions.length > 0 && (
                <ul className="suggestions-dropdown">
                  {filteredSuggestions.map((item, index) => (
                    <li
                      key={item.ticker}
                      className={`suggestion-item${index === activeIndex ? " is-active" : ""}`}
                      onMouseDown={(e) => {
                        e.preventDefault();
                        selectSuggestion(item);
                      }}
                    >
                      <strong>{item.ticker}</strong>
                      <span>{item.name}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </label>
          <div className="date-grid">
            <label className="nested-field">
              {copy.startDate}
              <input
                type="date"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
              />
            </label>
            <label className="nested-field">
              {copy.endDate}
              <input
                type="date"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
              />
            </label>
          </div>
          <div className="date-shortcuts">
            {([1, 7, 30, 90] as const).map((days, i) => (
              <button
                key={days}
                type="button"
                className="date-shortcut"
                onClick={() => setDateRange(days)}
              >
                {copy.dateShortcuts[i]}
              </button>
            ))}
          </div>
          <div className="mode-row">
            <div className="mode-switch" aria-label={copy.reportModeLabel}>
              <button
                type="button"
                className={reportMode === "ai" ? "mode-button active" : "mode-button"}
                onClick={() => setReportMode("ai")}
              >
                {copy.reportModeAi}
              </button>
              <button
                type="button"
                className={reportMode === "rules" ? "mode-button active" : "mode-button"}
                onClick={() => setReportMode("rules")}
              >
                {copy.reportModeRules}
              </button>
            </div>
            <p className="mode-hint">
              {reportMode === "ai" ? copy.reportModeAiHint : copy.reportModeRulesHint}
            </p>
          </div>
          <button type="button" onClick={handleRunResearch} disabled={status === "loading"}>
            {status === "loading" ? loadingButtonText : copy.runResearch}
          </button>
          <p className={`status-message ${status}`}>
            {status === "idle" && copy.statusIdle}
            {status === "loading" && (
              <>
                <span className="loading-indicator" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </span>
                <span>{loadingStatusText}</span>
              </>
            )}
            {status === "success" && copy.statusSuccess}
            {status === "error" && `${copy.statusError} ${errorMessage}`}
          </p>
          <div className="locale-switch-row">
            <button
              type="button"
              className={locale === "zh" ? "locale-text-button active" : "locale-text-button"}
              onClick={() => setLocale("zh")}
            >
              中文
            </button>
            <span className="locale-divider" aria-hidden="true">/</span>
            <button
              type="button"
              className={locale === "en" ? "locale-text-button active" : "locale-text-button"}
              onClick={() => setLocale("en")}
            >
              EN
            </button>
          </div>
        </div>
      </section>

      <SummaryPanel
        companyName={query}
        ticker={inferTicker(query)}
        startDate={startDate}
        endDate={endDate}
        locale={locale}
        graph={graph}
      />
      <section className="workspace-layout">
        <GraphView
          graph={graph}
          locale={locale}
          selectedNodeId={selectedEventId}
          onSelectNode={setSelectedEventId}
          tasks={tasks}
          onLoadTask={handleLoadTask}
        />
      </section>
    </main>
  );
}

function inferTicker(value: string): string {
  const normalized = value.trim().toUpperCase();
  if (/^[A-Z.\-]{1,8}$/.test(normalized) && /[A-Z]/.test(normalized)) {
    return normalized;
  }
  return "";
}

