from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.schemas.graph import GraphResponse
from app.schemas.task import TaskStatusResponse


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "tasks"


def load_persisted_state() -> tuple[dict[str, TaskStatusResponse], dict[str, GraphResponse]]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tasks: dict[str, TaskStatusResponse] = {}
    graphs: dict[str, GraphResponse] = {}

    for path in sorted(DATA_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            task_payload = payload.get("task")
            graph_payload = payload.get("graph")
            if not isinstance(task_payload, dict) or not isinstance(graph_payload, dict):
                continue
            task_payload.setdefault("status", "completed")
            task_payload.setdefault("stage", "completed")
            task_payload.setdefault("progress", 100)
            task_payload.setdefault("ticker", "")
            task_payload.setdefault("report_mode", "ai")
            task_payload.setdefault(
                "created_at",
                datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
            )
            task = TaskStatusResponse.model_validate(task_payload)
            graph = GraphResponse.model_validate(graph_payload)
        except Exception:
            continue

        tasks[task.task_id] = task
        graphs[task.task_id] = graph

    return tasks, graphs


def save_task_result(task: TaskStatusResponse, graph: GraphResponse) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "task": task.model_dump(mode="json"),
        "graph": graph.model_dump(mode="json"),
    }
    path = DATA_DIR / f"{task.task_id}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
