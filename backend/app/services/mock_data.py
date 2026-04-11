from app.schemas.graph import GraphEdge, GraphNode, GraphResponse, GraphSummary


def build_mock_graph(company_name: str) -> GraphResponse:
    company_id = "company:target"
    event_1 = "event:product_launch"
    event_2 = "event:partnership"
    product = "product:new_platform"
    partner = "company:partner"
    source_1 = "source:1"
    source_2 = "source:2"

    nodes = [
        GraphNode(
            id=company_id,
            label=company_name,
            type="Company",
            data={"canonical_name": company_name},
        ),
        GraphNode(
            id=event_1,
            label="Product Launch",
            type="Event",
            data={
                "event_type": "product_launch",
                "date": "2026-04-05",
                "summary": f"{company_name} announced a new AI product line.",
            },
        ),
        GraphNode(
            id=event_2,
            label="Partnership",
            type="Event",
            data={
                "event_type": "partnership",
                "date": "2026-04-08",
                "summary": f"{company_name} expanded a strategic partnership.",
            },
        ),
        GraphNode(
            id=product,
            label="AI Platform X",
            type="Product",
            data={},
        ),
        GraphNode(
            id=partner,
            label="PartnerCo",
            type="Company",
            data={},
        ),
        GraphNode(
            id=source_1,
            label="Press Release",
            type="Source",
            data={"url": "https://example.com/press-release"},
        ),
        GraphNode(
            id=source_2,
            label="Industry News",
            type="Source",
            data={"url": "https://example.com/news"},
        ),
    ]

    edges = [
        GraphEdge(
            id="edge:1",
            source=company_id,
            target=event_1,
            label="INVOLVED_IN",
            type="INVOLVED_IN",
        ),
        GraphEdge(
            id="edge:2",
            source=event_1,
            target=product,
            label="LAUNCHED",
            type="LAUNCHED",
        ),
        GraphEdge(
            id="edge:3",
            source=company_id,
            target=event_2,
            label="INVOLVED_IN",
            type="INVOLVED_IN",
        ),
        GraphEdge(
            id="edge:4",
            source=event_2,
            target=partner,
            label="PARTNERED_WITH",
            type="PARTNERED_WITH",
        ),
        GraphEdge(
            id="edge:5",
            source=event_1,
            target=source_1,
            label="REPORTED_BY",
            type="REPORTED_BY",
        ),
        GraphEdge(
            id="edge:6",
            source=event_2,
            target=source_2,
            label="REPORTED_BY",
            type="REPORTED_BY",
        ),
    ]

    return GraphResponse(
        nodes=nodes,
        edges=edges,
        summary=GraphSummary(
            event_count=2,
            source_count=2,
            top_event_types=["product_launch", "partnership"],
        ),
    )
