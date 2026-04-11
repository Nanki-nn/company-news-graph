from fastapi import FastAPI

from app.api.routes import router


app = FastAPI(
    title="Company News Graph API",
    version="0.1.0",
    description="Research recent company news and return graph-shaped results.",
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
