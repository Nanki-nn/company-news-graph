import { useEffect, useState } from "react";

import type { GraphResponse, TaskStatusResponse } from "../lib/api";
import { getResearchGraph, listResearchTasks, runResearchTask } from "../lib/api";
import { GraphView } from "../components/GraphView";
import { SummaryPanel } from "../components/SummaryPanel";
import { messages, type Locale } from "../lib/i18n";

export function App() {
  const [companyName, setCompanyName] = useState("Tesla");
  const [locale, setLocale] = useState<Locale>(() => {
    const savedLocale = window.localStorage.getItem("locale");
    return savedLocale === "en" ? "en" : "zh";
  });
  const [startDate, setStartDate] = useState("2026-03-01");
  const [endDate, setEndDate] = useState("2026-04-11");
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [tasks, setTasks] = useState<TaskStatusResponse[]>([]);
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

  async function handleRunResearch() {
    if (!companyName.trim()) {
      return;
    }

    setStatus("loading");
    setErrorMessage("");

    try {
      const nextGraph = await runResearchTask({
        companyName: companyName.trim(),
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
    setCompanyName(task.company_name);
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
            {copy.companyLabel}
            <input
              value={companyName}
              onChange={(event) => setCompanyName(event.target.value)}
              placeholder={copy.companyPlaceholder}
            />
          </label>
          <label>
            {copy.timeRangeLabel}
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
          </label>
          <button type="button" onClick={handleRunResearch} disabled={status === "loading"}>
            {status === "loading" ? loadingButtonText : copy.runResearch}
          </button>
          <p className={`status-message ${status}`}>
            {status === "idle" && copy.statusIdle}
            {status === "loading" && loadingStatusText}
            {status === "success" && copy.statusSuccess}
            {status === "error" && `${copy.statusError} ${errorMessage}`}
          </p>
          <section className="task-history">
            <div className="task-history-header">
              <strong>{copy.taskHistory}</strong>
            </div>
            {tasks.length === 0 ? (
              <p className="task-history-empty">{copy.noTasks}</p>
            ) : (
              <ul className="task-history-list">
                {tasks.map((task) => (
                  <li key={task.task_id} className="task-history-item">
                    <div>
                      <strong>{task.company_name}</strong>
                      <span>
                        {task.start_date} {"->"} {task.end_date}
                      </span>
                    </div>
                    <button type="button" onClick={() => handleLoadTask(task)}>
                      {copy.loadTask}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </section>

      <SummaryPanel companyName={companyName} locale={locale} graph={graph} />
      <GraphView graph={graph} locale={locale} />
    </main>
  );
}
