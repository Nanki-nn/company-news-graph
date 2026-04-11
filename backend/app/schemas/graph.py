from typing import Any

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    data: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str
    type: str
    data: dict[str, Any] = Field(default_factory=dict)


class GraphSummary(BaseModel):
    event_count: int
    source_count: int
    top_event_types: list[str]


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    summary: GraphSummary
