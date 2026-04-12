from threading import Lock, Thread
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from app.schemas.graph import GraphResponse
from app.schemas.task import ResearchTaskCreate, ResearchTaskResponse, TaskStatusResponse
from app.services.news_research import build_error_graph, run_news_research
from app.services.storage import load_persisted_state, save_task_result


router = APIRouter()

_TASKS, _GRAPHS = load_persisted_state()
_LOCK = Lock()


@router.get("/research/tasks", response_model=list[TaskStatusResponse])
def list_tasks() -> list[TaskStatusResponse]:
    return sorted(
        _TASKS.values(),
        key=lambda task: task.created_at,
        reverse=True,
    )


@router.post("/research/tasks", response_model=ResearchTaskResponse)
def create_task(payload: ResearchTaskCreate) -> ResearchTaskResponse:
    with _LOCK:
        task_id = f"task_{len(_TASKS) + 1:03d}"
        task = TaskStatusResponse(
            task_id=task_id,
            status="queued",
            stage="queued",
            progress=0,
            company_name=payload.company_name,
            ticker=payload.ticker,
            start_date=payload.start_date,
            end_date=payload.end_date,
            created_at=datetime.now(UTC),
        )
        _TASKS[task_id] = task

    Thread(
        target=_run_task_worker,
        args=(task_id, payload),
        daemon=True,
    ).start()

    return ResearchTaskResponse(task_id=task_id, status="queued")


@router.get("/research/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task(task_id: str) -> TaskStatusResponse:
    task = _TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/research/tasks/{task_id}/graph", response_model=GraphResponse)
def get_graph(task_id: str) -> GraphResponse:
    if task_id not in _TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    if task_id not in _GRAPHS:
        raise HTTPException(status_code=409, detail="Graph is not ready yet")
    return _GRAPHS[task_id]


def _update_task(task_id: str, **changes: object) -> None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            return
        _TASKS[task_id] = task.model_copy(update=changes)


def _run_task_worker(task_id: str, payload: ResearchTaskCreate) -> None:
    _update_task(task_id, status="running", stage="fetching_sources", progress=5)

    def stage_callback(stage: str, progress: int) -> None:
        _update_task(task_id, status="running", stage=stage, progress=progress)

    try:
        graph = run_news_research(
            payload.company_name,
            payload.ticker,
            payload.start_date,
            payload.end_date,
            stage_callback=stage_callback,
        )
        _GRAPHS[task_id] = graph
        _update_task(task_id, status="completed", stage="completed", progress=100)
        save_task_result(_TASKS[task_id], graph)

        event_nodes = [node for node in graph.nodes if node.type == "Event"]
        generated_by = sorted(
            {
                str(node.data.get("generated_by"))
                for node in event_nodes
                if isinstance(node.data.get("generated_by"), str)
            }
        )
        confidence = sorted(
            {
                str(node.data.get("confidence"))
                for node in event_nodes
                if isinstance(node.data.get("confidence"), str)
            }
        )
        ai_reasons = sorted(
            {
                str(node.data.get("ai_reason"))
                for node in event_nodes
                if isinstance(node.data.get("ai_reason"), str) and node.data.get("ai_reason")
            }
        )
        print(
            "[company-news-graph]",
            f"task={task_id}",
            f"company={payload.company_name}",
            f"ticker={payload.ticker or '-'}",
            f"events={len(event_nodes)}",
            f"generated_by={generated_by or ['rules']}",
            f"confidence={confidence or ['heuristic']}",
            f"ai_reason={ai_reasons or ['none']}",
        )
    except Exception as exc:
        graph = build_error_graph(payload.company_name, str(exc))
        _GRAPHS[task_id] = graph
        _update_task(task_id, status="failed", stage="failed", progress=100)
        save_task_result(_TASKS[task_id], graph)
