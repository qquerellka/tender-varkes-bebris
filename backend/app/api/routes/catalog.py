from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_catalog_service, get_current_actor, get_session_dependency
from app.domain.catalog.schemas import (
    CatalogFeedRead,
    CatalogSummaryRead,
    CategoryRead,
    RelatedSTEItemRead,
    STEItemRead,
    SupplierRead,
)
from app.domain.catalog.service import CatalogService
from app.domain.search.schemas import CurrentActor

router = APIRouter()


@router.get("/categories", response_model=list[CategoryRead])
def list_categories(
    session: Session = Depends(get_session_dependency),
) -> list[CategoryRead]:
    catalog_service = get_catalog_service(session)
    return catalog_service.list_categories()


@router.get("/suppliers", response_model=list[SupplierRead])
def list_suppliers(
    session: Session = Depends(get_session_dependency),
) -> list[SupplierRead]:
    catalog_service = get_catalog_service(session)
    return catalog_service.list_suppliers()


@router.get("/summary", response_model=CatalogSummaryRead)
def get_catalog_summary(
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> CatalogSummaryRead:
    catalog_service = get_catalog_service(session)
    return catalog_service.get_catalog_summary(user_id=actor.user_id)


@router.get("/feed", response_model=CatalogFeedRead)
def get_catalog_feed(
    limit: int = 24,
    offset: int = 0,
    category_id: str | None = None,
    supplier_id: str | None = None,
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> CatalogFeedRead:
    catalog_service = get_catalog_service(session)
    return catalog_service.get_catalog_feed(
        user_id=actor.user_id,
        organization_id=actor.organization_id,
        limit=limit,
        offset=offset,
        category_id=category_id,
        supplier_id=supplier_id,
    )


@router.get("/ste/{ste_id}", response_model=STEItemRead)
def get_ste(
    ste_id: str,
    session: Session = Depends(get_session_dependency),
) -> STEItemRead:
    catalog_service = get_catalog_service(session)
    item = catalog_service.get_ste_by_id(ste_id)
    if item is None:
        raise HTTPException(status_code=404, detail="STE item not found")
    return item


@router.get("/ste/{ste_id}/related", response_model=list[RelatedSTEItemRead])
def get_related_ste(
    ste_id: str,
    limit: int = 6,
    session: Session = Depends(get_session_dependency),
) -> list[RelatedSTEItemRead]:
    catalog_service = get_catalog_service(session)
    item = catalog_service.get_ste_by_id(ste_id)
    if item is None:
        raise HTTPException(status_code=404, detail="STE item not found")
    return catalog_service.get_related_ste_items(ste_id=ste_id, limit=limit)
