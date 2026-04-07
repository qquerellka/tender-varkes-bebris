from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_catalog_service,
    get_current_actor,
    get_personalization_service,
    get_session_dependency,
)
from app.domain.catalog.schemas import PurchaseHistoryItemRead, SupplierInsightsRead
from app.domain.catalog.service import CatalogService
from app.domain.personalization.schemas import SearchProfileRead
from app.domain.personalization.service import PersonalizationService
from app.domain.search.schemas import CurrentActor

router = APIRouter()


@router.get("/search", response_model=SearchProfileRead)
async def get_search_profile(
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> SearchProfileRead:
    personalization_service = get_personalization_service(session)
    if not actor.personalization_enabled:
        return SearchProfileRead(user_id=actor.user_id, organization_id=actor.organization_id)

    return personalization_service.get_search_profile(
        user_id=actor.user_id,
        organization_id=actor.organization_id,
    )


@router.get("/purchases", response_model=list[PurchaseHistoryItemRead])
async def get_purchase_history(
    limit: int = 6,
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> list[PurchaseHistoryItemRead]:
    if not actor.personalization_enabled:
        return []

    catalog_service = get_catalog_service(session)
    return catalog_service.get_purchase_history(
        user_id=actor.user_id,
        organization_id=actor.organization_id,
        limit=limit,
    )


@router.get("/supplier-insights", response_model=SupplierInsightsRead)
async def get_supplier_insights(
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> SupplierInsightsRead:
    if actor.role != "supplier":
        return SupplierInsightsRead(
            matched_suppliers=[],
            owned_catalog_items_count=0,
            owned_purchase_history_count=0,
            tracked_categories_count=0,
            top_demand_categories=[],
            top_competitors=[],
            hot_opportunities=[],
        )

    catalog_service = get_catalog_service(session)
    return catalog_service.get_supplier_insights(actor.organization_name or "")
