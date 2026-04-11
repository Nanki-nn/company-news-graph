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

export async function runResearchTask(params: {
  companyName: string;
  startDate: string;
  endDate: string;
  locale: Locale;
}): Promise<GraphResponse> {
  const taskResponse = await fetch(`${API_BASE_URL}/research/tasks`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      company_name: params.companyName,
      start_date: params.startDate,
      end_date: params.endDate,
      language: params.locale,
      sources: ["news", "official"]
    })
  });

  if (!taskResponse.ok) {
    throw new Error(`Failed to create research task: ${taskResponse.status}`);
  }

  const task = (await taskResponse.json()) as TaskResponse;
  const graphResponse = await fetch(`${API_BASE_URL}/research/tasks/${task.task_id}/graph`);

  if (!graphResponse.ok) {
    throw new Error(`Failed to fetch graph: ${graphResponse.status}`);
  }

  return (await graphResponse.json()) as GraphResponse;
}
