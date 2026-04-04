from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_actor,
    get_search_service,
    get_session_dependency,
)
from app.domain.search.schemas import (
    CurrentActor,
    SearchHistoryResponse,
    SearchRequest,
    SearchResponse,
    SearchSuggestionsResponse,
    SpellcheckResponse,
)
from app.domain.search.service import SearchService

router = APIRouter()


def ensure_search_stack_ready(request: Request) -> None:
    search_warmup = getattr(request.app.state, "search_warmup", "unknown")
    ranking_warmup = getattr(request.app.state, "ranking_warmup", "unknown")

    if search_warmup in {"pending", "running"} or ranking_warmup in {"pending", "running"}:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search stack is warming up. Retry in a few seconds.",
        )

    if search_warmup == "failed" or ranking_warmup == "failed":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search stack warmup failed. Check backend logs.",
        )


@router.post("", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    _: None = Depends(ensure_search_stack_ready),
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> SearchResponse:
    search_service = get_search_service(session)
    return search_service.search(payload, actor)


@router.get("/suggestions", response_model=SearchSuggestionsResponse)
async def suggestions(
    query: str = Query(""),
    _: None = Depends(ensure_search_stack_ready),
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> SearchSuggestionsResponse:
    search_service = get_search_service(session)
    return search_service.get_suggestions(query=query, actor=actor)


@router.get("/spellcheck", response_model=SpellcheckResponse)
async def spellcheck(
    query: str = Query(...),
    _: None = Depends(ensure_search_stack_ready),
    session: Session = Depends(get_session_dependency),
) -> SpellcheckResponse:
    search_service = get_search_service(session)
    return search_service.get_spellcheck(query)


@router.get("/history", response_model=SearchHistoryResponse)
async def history(
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> SearchHistoryResponse:
    search_service = get_search_service(session)
    return search_service.get_history(actor=actor, limit=limit)
