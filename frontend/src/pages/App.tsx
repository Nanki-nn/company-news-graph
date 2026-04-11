import React, { useEffect, useState } from "react";

import type { GraphResponse, TaskStatusResponse } from "../lib/api";
import { getResearchGraph, listResearchTasks, runResearchTask } from "../lib/api";
import { GraphView } from "../components/GraphView";
import { InvestmentPanels } from "../components/InvestmentPanels";
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
  const defaultVisibleTasks = 5;
  const [query, setQuery] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [locale, setLocale] = useState<Locale>(() => {
    const savedLocale = window.localStorage.getItem("locale");
    return savedLocale === "en" ? "en" : "zh";
  });
  const [startDate, setStartDate] = useState("2026-03-01");
  const [endDate, setEndDate] = useState("2026-04-11");
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [tasks, setTasks] = useState<TaskStatusResponse[]>([]);
  const [showAllTasks, setShowAllTasks] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [loadingStep, setLoadingStep] = useState(0);
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

  useEffect(() => {
    if (status !== "loading") {
      setLoadingStep(0);
      return;
    }

    const timer = window.setInterval(() => {
      setLoadingStep((current) => (current + 1) % 4);
    }, 500);

    return () => {
      window.clearInterval(timer);
    };
  }, [status]);

  const loadingDots = ".".repeat(loadingStep);
  const loadingButtonText = `${copy.running}${loadingDots}`;
  const loadingStatusText = `${copy.statusLoading}${loadingDots}`;
  const visibleTasks = showAllTasks ? tasks : tasks.slice(0, defaultVisibleTasks);
  const hiddenTaskCount = Math.max(tasks.length - defaultVisibleTasks, 0);

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

  async function handleRunResearch() {
    if (!query.trim()) {
      return;
    }

    setStatus("loading");
    setErrorMessage("");

    try {
      const normalizedQuery = query.trim();
      const inferredTicker = inferTicker(normalizedQuery);
      const nextGraph = await runResearchTask({
        companyName: normalizedQuery,
        ticker: inferredTicker,
        startDate,
        endDate,
        locale
      });
      setGraph(nextGraph);
      setTasks(await listResearchTasks());
      setStatus("success");
    } catch (error) {
      setGraph(null);
      setStatus("error");
      setErrorMessage(error instanceof Error ? error.message : "Unknown error");
    }
  }

  async function handleLoadTask(task: TaskStatusResponse) {
    setQuery(task.ticker || task.company_name);
    setStartDate(task.start_date);
    setEndDate(task.end_date);
    setStatus("loading");
    setErrorMessage("");

    try {
      const nextGraph = await getResearchGraph(task.task_id);
      setGraph(nextGraph);
      setStatus("success");
    } catch (error) {
      setStatus("error");
      setErrorMessage(error instanceof Error ? error.message : "Unknown error");
    }
  }

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <div className="hero-topbar">
            <p className="eyebrow">{copy.appName}</p>
            <div className="locale-switch" aria-label={copy.language}>
              <button
                type="button"
                className={locale === "zh" ? "locale-button active" : "locale-button"}
                onClick={() => setLocale("zh")}
              >
                {copy.chinese}
              </button>
              <button
                type="button"
                className={locale === "en" ? "locale-button active" : "locale-button"}
                onClick={() => setLocale("en")}
              >
                {copy.english}
              </button>
            </div>
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
          <button type="button" onClick={handleRunResearch} disabled={status === "loading"}>
            {status === "loading" ? loadingButtonText : copy.runResearch}
          </button>
          <p className={`status-message ${status}`}>
            {status === "idle" && copy.statusIdle}
            {status === "loading" && loadingStatusText}
            {status === "success" && copy.statusSuccess}
            {status === "error" && `${copy.statusError} ${errorMessage}`}
          </p>
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
      <InvestmentPanels graph={graph} locale={locale} />
      <section className="workspace-layout">
        <div className="workspace-main">
          <GraphView graph={graph} locale={locale} />
        </div>
        <aside className="workspace-side">
          <section className="task-history-card">
            <div className="task-history">
              <div className="task-history-header">
                <strong>{copy.taskHistory}</strong>
                {tasks.length > 0 ? <span>{copy.taskCount.replace("{count}", String(tasks.length))}</span> : null}
              </div>
              {tasks.length === 0 ? (
                <p className="task-history-empty">{copy.noTasks}</p>
              ) : (
                <>
                  <ul className={`task-history-list ${showAllTasks ? "expanded" : ""}`}>
                    {visibleTasks.map((task) => (
                      <li key={task.task_id} className="task-history-item">
                        <div>
                          <strong>{task.company_name}</strong>
                          <span>
                            {[task.ticker, `${task.start_date} -> ${task.end_date}`].filter(Boolean).join(" · ")}
                          </span>
                        </div>
                        <button type="button" onClick={() => handleLoadTask(task)}>
                          {copy.loadTask}
                        </button>
                      </li>
                    ))}
                  </ul>
                  {hiddenTaskCount > 0 ? (
                    <button
                      type="button"
                      className="task-history-toggle"
                      onClick={() => setShowAllTasks((current) => !current)}
                    >
                      {showAllTasks
                        ? copy.showLessTasks
                        : copy.showMoreTasks.replace("{count}", String(hiddenTaskCount))}
                    </button>
                  ) : null}
                </>
              )}
            </div>
          </section>
        </aside>
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
