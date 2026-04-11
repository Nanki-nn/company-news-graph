# Company News Graph

Research recent company news and disclosures, extract structured events, and render the result as an interactive graph.

## Scope

- Input: company name + time range
- Pipeline: fetch articles, extract entities/events, normalize, build graph
- Output: summary + graph with source evidence

## Repository Layout

```text
backend/   FastAPI API and pipeline skeleton
frontend/  React + Vite UI skeleton
docs/      Product and technical docs
```

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## MVP

- Create research task
- Return mock company event graph
- Show graph-ready nodes and edges in UI
- Keep schema ready for real fetch/extraction/Neo4j integration

## Next Steps

1. Integrate news/disclosure sources
2. Add structured event extraction
3. Persist tasks and sources
4. Write to Neo4j
5. Replace mock graph with live graph
