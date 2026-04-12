import type { Locale } from "./i18n";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export type GraphNode = {
  id: string;
  label: string;
  type: string;
  data?: Record<string, unknown>;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
  type: string;
  data?: Record<string, unknown>;
};

export type GraphResponse = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  summary: {
    event_count: number;
    source_count: number;
    top_event_types: string[];
  };
};

type TaskResponse = {
  task_id: string;
  status: "queued" | "running" | "completed" | "failed";
};

export type TaskStatusResponse = {
  task_id: string;
  status: "queued" | "running" | "completed" | "failed";
  stage:
    | "queued"
    | "fetching_sources"
    | "filtering_articles"
    | "clustering_events"
    | "summarizing_events"
    | "extracting_entities"
    | "building_graph"
    | "completed"
    | "failed";
  progress: number;
  company_name: string;
  ticker: string;
  start_date: string;
  end_date: string;
  created_at: string;
};

export async function createResearchTask(params: {
  companyName: string;
  ticker: string;
  startDate: string;
  endDate: string;
  locale: Locale;
}): Promise<TaskResponse> {
  const taskResponse = await fetch(`${API_BASE_URL}/research/tasks`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      company_name: params.companyName,
      ticker: params.ticker,
      start_date: params.startDate,
      end_date: params.endDate,
      language: params.locale,
      sources: ["news", "official"]
    })
  });

  if (!taskResponse.ok) {
    throw new Error(`Failed to create research task: ${taskResponse.status}`);
  }

  return (await taskResponse.json()) as TaskResponse;
}

export async function getResearchTask(taskId: string): Promise<TaskStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/research/tasks/${taskId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch task: ${response.status}`);
  }
  return (await response.json()) as TaskStatusResponse;
}

export async function runResearchTask(params: {
  companyName: string;
  ticker: string;
  startDate: string;
  endDate: string;
  locale: Locale;
  onTaskUpdate?: (task: TaskStatusResponse) => void;
}): Promise<GraphResponse> {
  const task = await createResearchTask(params);

  while (true) {
    const nextTask = await getResearchTask(task.task_id);
    params.onTaskUpdate?.(nextTask);
    if (nextTask.status === "completed") {
      break;
    }
    if (nextTask.status === "failed") {
      throw new Error("Research task failed");
    }
    await new Promise((resolve) => window.setTimeout(resolve, 900));
  }

  const graphResponse = await fetch(`${API_BASE_URL}/research/tasks/${task.task_id}/graph`);
  if (!graphResponse.ok) {
    throw new Error(`Failed to fetch graph: ${graphResponse.status}`);
  }

  return (await graphResponse.json()) as GraphResponse;
}

export async function listResearchTasks(): Promise<TaskStatusResponse[]> {
  const response = await fetch(`${API_BASE_URL}/research/tasks`);
  if (!response.ok) {
    throw new Error(`Failed to list tasks: ${response.status}`);
  }
  return (await response.json()) as TaskStatusResponse[];
}

export async function getResearchGraph(taskId: string): Promise<GraphResponse> {
  const response = await fetch(`${API_BASE_URL}/research/tasks/${taskId}/graph`);
  if (!response.ok) {
    throw new Error(`Failed to fetch graph: ${response.status}`);
  }
  return (await response.json()) as GraphResponse;
}
