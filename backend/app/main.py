import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.api.routes import router


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
))
_app_logger = logging.getLogger("company_news_graph")
_app_logger.setLevel(_log_level)
_app_logger.handlers.clear()
_app_logger.addHandler(_handler)
_app_logger.propagate = False
print("[startup] company_news_graph logger ready, level=", _log_level, flush=True)
_app_logger.info("[startup] logging initialized")


app = FastAPI(
    title="Company News Graph API",
    version="0.1.0",
    description="Research recent company news and return graph-shaped results.",
    redirect_slashes=False,
)


def _parse_cors_allowed_origins() -> list[str]:
    configured = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    default_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://47.111.184.231",
        "https://47.111.184.231",
    ]
    if not configured:
        return default_origins
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


def _cors_origin_regex() -> str | None:
    configured = os.getenv("CORS_ALLOWED_ORIGIN_REGEX", "").strip()
    if configured:
        return configured
    return r"https?://(localhost|127\.0\.0\.1)(:\d+)?$"


_allowed_origins = _parse_cors_allowed_origins()
_allowed_origin_regex = _cors_origin_regex()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=_allowed_origin_regex,
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
