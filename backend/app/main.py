import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db import Base, engine
from app.routes import health, proxy
from app.routes import admin, openai_proxy

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import app.models  # noqa: F401 — registers all models with Base.metadata
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        logger.warning("Could not create database tables on startup: %s", exc)
    yield


app = FastAPI(title="LLMGuard Lite", lifespan=lifespan)

# ── CORS ───────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Consistent error envelope ──────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


# ── Routes ─────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(proxy.router)
app.include_router(openai_proxy.router)
app.include_router(admin.router)
