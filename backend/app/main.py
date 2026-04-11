from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.api.routes import router


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


app = FastAPI(
    title="Company News Graph API",
    version="0.1.0",
    description="Research recent company news and return graph-shaped results.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Company News Graph API is running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
