from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_actor,
    get_event_service,
    get_search_service,
    get_session_dependency,
)
from app.api.routes.search import ensure_search_stack_ready
from app.domain.events.schemas import (
    SearchEventListRead,
    SearchImpressionListRead,
    TelemetryHealthRead,
)
from app.domain.events.service import EventService
from app.domain.search.schemas import (
    CurrentActor,
    SearchDebugResponse,
    SearchRequest,
    SearchStackStatusRead,
)
from app.domain.search.service import SearchService

router = APIRouter()


@router.get("/search-stack", response_model=SearchStackStatusRead)
async def get_debug_search_stack(request: Request) -> SearchStackStatusRead:
    search_warmup = getattr(request.app.state, "search_warmup", "unknown")
    ranking_warmup = getattr(request.app.state, "ranking_warmup", "unknown")
    return SearchStackStatusRead(
        ready=search_warmup == "ready" and ranking_warmup == "ready",
        search_warmup=search_warmup,
        ranking_warmup=ranking_warmup,
        ranking_provider=getattr(request.app.state, "ranking_provider_name", None),
        ranking_provider_mode=getattr(request.app.state, "ranking_provider_mode", None),
        search_documents_count=getattr(request.app.state, "search_documents_count", None),
        semantic_backend=getattr(request.app.state, "semantic_backend", None),
        semantic_faiss_enabled=getattr(request.app.state, "semantic_faiss_enabled", None),
        search_warmup_error=getattr(request.app.state, "search_warmup_error", None),
        ranking_warmup_error=getattr(request.app.state, "ranking_warmup_error", None),
    )


@router.post("/search-ranking", response_model=SearchDebugResponse)
async def debug_search_ranking(
    payload: SearchRequest,
    _: None = Depends(ensure_search_stack_ready),
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> SearchDebugResponse:
    search_service = get_search_service(session)
    return search_service.debug_search_ranking(payload=payload, actor=actor)


@router.get("/telemetry/events", response_model=SearchEventListRead)
async def get_telemetry_events(
    user_id: str | None = Query(default=None),
    search_session_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> SearchEventListRead:
    event_service = get_event_service(session)
    effective_user_id = user_id or actor.user_id
    return event_service.list_events(
        user_id=effective_user_id,
        search_session_id=search_session_id,
        limit=limit,
    )


@router.get("/telemetry/impressions", response_model=SearchImpressionListRead)
async def get_telemetry_impressions(
    user_id: str | None = Query(default=None),
    search_session_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> SearchImpressionListRead:
    event_service = get_event_service(session)
    effective_user_id = user_id or actor.user_id
    return event_service.list_impressions(
        user_id=effective_user_id,
        search_session_id=search_session_id,
        limit=limit,
    )


@router.get("/telemetry/health", response_model=TelemetryHealthRead)
async def get_telemetry_health(
    user_id: str | None = Query(default=None),
    search_session_id: str | None = Query(default=None),
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> TelemetryHealthRead:
    event_service = get_event_service(session)
    effective_user_id = user_id or actor.user_id
    return event_service.get_health_summary(
        user_id=effective_user_id,
        search_session_id=search_session_id,
    )
