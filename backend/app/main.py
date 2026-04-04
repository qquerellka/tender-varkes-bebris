import logging
import threading

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.api.dependencies import get_ranking_provider
from app.core.config import settings
from app.db.repositories.search import SearchRepository
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Backend platform for personalized search without ML implementation.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.include_router(api_router, prefix=settings.api_prefix)


def _get_warmup_state() -> dict[str, str]:
    return {
        "status": "ok",
        "search_warmup": getattr(app.state, "search_warmup", "unknown"),
        "ranking_warmup": getattr(app.state, "ranking_warmup", "unknown"),
    }


def _is_search_stack_ready() -> bool:
    state = _get_warmup_state()
    return state["search_warmup"] == "ready" and state["ranking_warmup"] == "ready"


def _warmup_search_stack() -> None:
    app.state.search_warmup = "running"
    app.state.ranking_warmup = "running"
    app.state.search_warmup_error = None
    app.state.ranking_warmup_error = None
    app.state.search_documents_count = None
    app.state.semantic_backend = None
    app.state.semantic_faiss_enabled = None
    app.state.ranking_provider_name = None
    app.state.ranking_provider_mode = settings.ranking_provider

    try:
        with SessionLocal() as session:
            search_repository = SearchRepository(session)
            index = search_repository._get_hybrid_index()
            app.state.search_documents_count = len(index.documents)
            app.state.semantic_backend = index._semantic_backend
            app.state.semantic_faiss_enabled = index._semantic_faiss_index is not None
            logger.info(
                "Search warmup complete: semantic_backend=%s faiss_enabled=%s documents=%s",
                index._semantic_backend,
                index._semantic_faiss_index is not None,
                len(index.documents),
            )
            app.state.search_warmup = "ready"
    except Exception as exc:
        app.state.search_warmup = "failed"
        app.state.search_warmup_error = str(exc)
        logger.warning("Search warmup failed: %s", exc)

    try:
        ranking_provider = get_ranking_provider()
        app.state.ranking_provider_name = ranking_provider.__class__.__name__
        logger.info(
            "Ranking provider warmup complete: provider=%s",
            ranking_provider.__class__.__name__,
        )
        app.state.ranking_warmup = "ready"
    except Exception as exc:
        app.state.ranking_warmup = "failed"
        app.state.ranking_warmup_error = str(exc)
        logger.warning("Ranking provider warmup failed: %s", exc)


@app.on_event("startup")
def schedule_warmup_search_stack() -> None:
    app.state.search_warmup = "pending"
    app.state.ranking_warmup = "pending"
    app.state.search_warmup_error = None
    app.state.ranking_warmup_error = None
    app.state.search_documents_count = None
    app.state.semantic_backend = None
    app.state.semantic_faiss_enabled = None
    app.state.ranking_provider_name = None
    app.state.ranking_provider_mode = settings.ranking_provider
    threading.Thread(target=_warmup_search_stack, daemon=True).start()
    logger.info("Background warmup scheduled")


@app.get("/health", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return _get_warmup_state()


@app.get("/ready", tags=["health"])
async def readiness_check() -> JSONResponse:
    payload = _get_warmup_state()
    status_code = (
        status.HTTP_200_OK
        if _is_search_stack_ready()
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return JSONResponse(content=payload, status_code=status_code)
