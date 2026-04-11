from fastapi import APIRouter, HTTPException

from app.schemas.graph import GraphResponse
from app.schemas.task import ResearchTaskCreate, ResearchTaskResponse, TaskStatusResponse
from app.services.mock_data import build_mock_graph


router = APIRouter()

_TASKS: dict[str, TaskStatusResponse] = {}


@router.post("/research/tasks", response_model=ResearchTaskResponse)
def create_task(payload: ResearchTaskCreate) -> ResearchTaskResponse:
    task_id = f"task_{len(_TASKS) + 1:03d}"
    _TASKS[task_id] = TaskStatusResponse(
        task_id=task_id,
        status="completed",
        progress=100,
        company_name=payload.company_name,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    return ResearchTaskResponse(task_id=task_id, status="completed")


@router.get("/research/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task(task_id: str) -> TaskStatusResponse:
    task = _TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/research/tasks/{task_id}/graph", response_model=GraphResponse)
def get_graph(task_id: str) -> GraphResponse:
    task = _TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return build_mock_graph(task.company_name)
