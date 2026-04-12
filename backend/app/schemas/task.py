from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ResearchTaskCreate(BaseModel):
    company_name: str = Field(min_length=1)
    ticker: str = ""
    report_mode: Literal["ai", "rules"] = "ai"
    start_date: date
    end_date: date
    language: str = "en"
    sources: list[str] = Field(default_factory=lambda: ["news", "official"])

    @model_validator(mode="after")
    def validate_date_range(self) -> "ResearchTaskCreate":
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class ResearchTaskResponse(BaseModel):
    task_id: str
    status: Literal["queued", "running", "completed", "failed"]


class TaskStatusResponse(BaseModel):
    task_id: str
    status: Literal["queued", "running", "completed", "failed"]
    stage: Literal[
        "queued",
        "fetching_sources",
        "filtering_articles",
        "clustering_events",
        "summarizing_events",
        "extracting_entities",
        "building_graph",
        "completed",
        "failed",
    ] = "queued"
    progress: int
    company_name: str
    ticker: str = ""
    report_mode: Literal["ai", "rules"] = "ai"
    start_date: date
    end_date: date
    created_at: datetime
