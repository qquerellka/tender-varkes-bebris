from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_actor,
    get_event_service,
    get_session_dependency,
)
from app.domain.events.schemas import (
    SearchEventListRead,
    SearchImpressionListRead,
    TelemetryHealthRead,
)
from app.domain.events.service import EventService
from app.domain.search.schemas import CurrentActor

router = APIRouter()


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
