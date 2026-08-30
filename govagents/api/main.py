"""FastAPI application entry point for GovAgents."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from govagents.api.routes import assess, policies
from govagents.api.schemas import HealthResponse
from govagents.core.config import get_settings
from govagents.core.logging import configure_logging, get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    settings = get_settings()
    configure_logging(level=settings.log_level, format=settings.log_format)

    log.info("govagents_starting", version="0.1.0")

    # Ensure data directories exist
    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    settings.assessments_path.mkdir(parents=True, exist_ok=True)

    # Auto-ingest policies on startup if corpus is empty
    from govagents.policies.ingestion import ingest_policies
    from govagents.policies.retrieval import get_retriever

    retriever = get_retriever()
    if retriever.count() == 0:
        log.info("auto_ingesting_policies")
        try:
            sources, chunks = await ingest_policies()
            log.info("policies_ingested", sources=sources, chunks=chunks)
        except Exception as e:
            log.error("policy_ingestion_failed", error=str(e))
    else:
        log.info("policy_corpus_ready", chunks=retriever.count())

    yield

    log.info("govagents_shutting_down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="GovAgents API",
        description=(
            "Multi-agent AI governance and policy reasoning system. "
            "Evaluates AI deployment proposals against governance frameworks."
        ),
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    from govagents.api.routes import config
    app.include_router(assess.router)
    app.include_router(policies.router)
    app.include_router(config.router)

    # Health check
    @app.get("/api/health", response_model=HealthResponse, tags=["system"])
    async def health_check() -> HealthResponse:
        from govagents.policies.retrieval import get_retriever

        retriever = get_retriever()
        chunks = retriever.count()
        return HealthResponse(
            status="ok",
            version="0.1.0",
            corpus_ready=chunks > 0,
            corpus_chunks=chunks,
        )

    # Serve frontend SPA
    frontend_path = Path(__file__).parent.parent / "frontend"
    if frontend_path.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

        @app.get("/", include_in_schema=False)
        async def serve_spa():
            return FileResponse(str(frontend_path / "index.html"))

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "govagents.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
