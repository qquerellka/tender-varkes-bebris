from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_actor,
    get_event_service,
    get_session_dependency,
)
from app.domain.events.schemas import (
    EventBatchResult,
    SearchEventBatchCreate,
    SearchEventCreate,
    SearchEventRead,
    SearchImpressionBatchCreate,
)
from app.domain.events.service import EventService
from app.domain.search.schemas import CurrentActor

router = APIRouter()


@router.post("", response_model=SearchEventRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: SearchEventCreate,
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> SearchEventRead:
    event_service = get_event_service(session)
    return event_service.create_event(payload, actor)


@router.post("/batch", response_model=EventBatchResult, status_code=status.HTTP_201_CREATED)
async def create_batch(
    payload: SearchEventBatchCreate,
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> EventBatchResult:
    event_service = get_event_service(session)
    return event_service.create_batch(payload, actor)


@router.post("/impressions", response_model=EventBatchResult, status_code=status.HTTP_201_CREATED)
async def create_impressions(
    payload: SearchImpressionBatchCreate,
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> EventBatchResult:
    event_service = get_event_service(session)
    return event_service.create_impressions(payload, actor)
