from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ResearchTaskCreate(BaseModel):
    company_name: str = Field(min_length=1)
    start_date: date
    end_date: date
    language: str = "en"
    sources: list[str] = ["news", "official"]


class ResearchTaskResponse(BaseModel):
    task_id: str
    status: Literal["queued", "running", "completed", "failed"]


class TaskStatusResponse(BaseModel):
    task_id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: int
    company_name: str
    start_date: date
    end_date: date
