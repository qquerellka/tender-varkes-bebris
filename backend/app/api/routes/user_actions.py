from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_actor,
    get_session_dependency,
    get_user_actions_service,
)
from app.domain.search.schemas import CurrentActor
from app.domain.catalog.schemas import PurchaseHistoryItemRead
from app.domain.user_actions.schemas import (
    CartItemCreate,
    CartItemRead,
    CartItemUpdate,
    ComparisonCreate,
    ComparisonItemRead,
    FavoriteCreate,
    FavoriteItemRead,
    PurchaseCreate,
)
from app.domain.user_actions.service import UserActionsService

router = APIRouter()


@router.get("/favorites", response_model=list[FavoriteItemRead])
async def list_favorites(
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> list[FavoriteItemRead]:
    service = get_user_actions_service(session)
    return service.list_favorites(actor)


@router.post("/favorites", response_model=FavoriteItemRead, status_code=status.HTTP_201_CREATED)
async def add_favorite(
    payload: FavoriteCreate,
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> FavoriteItemRead:
    service = get_user_actions_service(session)
    return service.add_favorite(payload, actor)


@router.delete("/favorites/{ste_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    ste_id: str,
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> Response:
    service = get_user_actions_service(session)
    service.remove_favorite(ste_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/compare", response_model=list[ComparisonItemRead])
async def list_comparison_items(
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> list[ComparisonItemRead]:
    service = get_user_actions_service(session)
    return service.list_comparison_items(actor)


@router.post("/compare", response_model=ComparisonItemRead, status_code=status.HTTP_201_CREATED)
async def add_comparison_item(
    payload: ComparisonCreate,
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> ComparisonItemRead:
    service = get_user_actions_service(session)
    return service.add_comparison_item(payload, actor)


@router.delete("/compare/{ste_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_comparison_item(
    ste_id: str,
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> Response:
    service = get_user_actions_service(session)
    service.remove_comparison_item(ste_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/cart", response_model=list[CartItemRead])
async def list_cart_items(
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> list[CartItemRead]:
    service = get_user_actions_service(session)
    return service.list_cart_items(actor)


@router.post("/cart", response_model=CartItemRead, status_code=status.HTTP_201_CREATED)
async def add_cart_item(
    payload: CartItemCreate,
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> CartItemRead:
    service = get_user_actions_service(session)
    return service.add_cart_item(payload, actor)


@router.patch("/cart/{ste_id}", response_model=CartItemRead)
async def update_cart_item(
    ste_id: str,
    payload: CartItemUpdate,
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> CartItemRead:
    service = get_user_actions_service(session)
    return service.update_cart_item(ste_id, payload, actor)


@router.delete("/cart/{ste_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_cart_item(
    ste_id: str,
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> Response:
    service = get_user_actions_service(session)
    service.remove_cart_item(ste_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/purchases", response_model=PurchaseHistoryItemRead, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    payload: PurchaseCreate,
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> PurchaseHistoryItemRead:
    service = get_user_actions_service(session)
    return service.create_purchase(payload, actor)
