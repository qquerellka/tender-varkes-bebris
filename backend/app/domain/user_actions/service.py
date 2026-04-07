from fastapi import HTTPException

from app.db.models import CartItemModel, ComparisonItemModel, FavoriteModel, PurchaseHistoryModel
from app.db.repositories.catalog import CatalogRepository
from app.db.repositories.user_actions import UserActionsRepository
from app.domain.events.service import EventService
from app.domain.catalog.schemas import PurchaseHistoryItemRead, STEItemRead
from app.domain.search.schemas import CurrentActor
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


class UserActionsService:
    def __init__(
        self,
        repository: UserActionsRepository,
        catalog_repository: CatalogRepository,
        event_service: EventService,
    ) -> None:
        self.repository = repository
        self.catalog_repository = catalog_repository
        self.event_service = event_service

    def list_favorites(self, actor: CurrentActor) -> list[FavoriteItemRead]:
        return [
            FavoriteItemRead(
                id=item.id,
                ste_id=item.ste_id,
                created_at=item.created_at,
                item=self._get_ste(item.ste_id),
            )
            for item in self.repository.list_favorites(actor.user_id)
        ]

    def add_favorite(self, payload: FavoriteCreate, actor: CurrentActor) -> FavoriteItemRead:
        self._ensure_ste(payload.ste_id)
        existing = self.repository.get_favorite(actor.user_id, payload.ste_id)
        if existing is None:
            existing = self.repository.create_favorite(
                FavoriteModel(user_id=actor.user_id, ste_id=payload.ste_id)
            )

        return FavoriteItemRead(
            id=existing.id,
            ste_id=existing.ste_id,
            created_at=existing.created_at,
            item=self._get_ste(existing.ste_id),
        )

    def remove_favorite(self, ste_id: str, actor: CurrentActor) -> None:
        self.repository.delete_favorite(actor.user_id, ste_id)

    def list_comparison_items(self, actor: CurrentActor) -> list[ComparisonItemRead]:
        return [
            ComparisonItemRead(
                id=item.id,
                ste_id=item.ste_id,
                created_at=item.created_at,
                item=self._get_ste(item.ste_id),
            )
            for item in self.repository.list_comparison_items(actor.user_id)
        ]

    def add_comparison_item(
        self,
        payload: ComparisonCreate,
        actor: CurrentActor,
    ) -> ComparisonItemRead:
        self._ensure_ste(payload.ste_id)
        current_items = self.repository.list_comparison_items(actor.user_id)
        existing = next((item for item in current_items if item.ste_id == payload.ste_id), None)
        if existing is None and len(current_items) >= 4:
            raise HTTPException(
                status_code=400,
                detail="Comparison list is limited to 4 items",
            )

        if existing is None:
            existing = self.repository.create_comparison_item(
                ComparisonItemModel(user_id=actor.user_id, ste_id=payload.ste_id)
            )

        return ComparisonItemRead(
            id=existing.id,
            ste_id=existing.ste_id,
            created_at=existing.created_at,
            item=self._get_ste(existing.ste_id),
        )

    def remove_comparison_item(self, ste_id: str, actor: CurrentActor) -> None:
        self.repository.delete_comparison_item(actor.user_id, ste_id)

    def list_cart_items(self, actor: CurrentActor) -> list[CartItemRead]:
        return [
            CartItemRead(
                id=item.id,
                ste_id=item.ste_id,
                quantity=int(item.quantity),
                created_at=item.created_at,
                updated_at=item.updated_at,
                item=self._get_ste(item.ste_id),
            )
            for item in self.repository.list_cart_items(actor.user_id)
        ]

    def add_cart_item(self, payload: CartItemCreate, actor: CurrentActor) -> CartItemRead:
        self._ensure_ste(payload.ste_id)
        existing = self.repository.get_cart_item(actor.user_id, payload.ste_id)
        if existing is None:
            existing = self.repository.create_cart_item(
                CartItemModel(
                    user_id=actor.user_id,
                    ste_id=payload.ste_id,
                    quantity=str(payload.quantity),
                )
            )
        else:
            existing.quantity = str(int(existing.quantity) + payload.quantity)
            existing = self.repository.save_cart_item(existing)

        return CartItemRead(
            id=existing.id,
            ste_id=existing.ste_id,
            quantity=int(existing.quantity),
            created_at=existing.created_at,
            updated_at=existing.updated_at,
            item=self._get_ste(existing.ste_id),
        )

    def update_cart_item(
        self,
        ste_id: str,
        payload: CartItemUpdate,
        actor: CurrentActor,
    ) -> CartItemRead:
        existing = self.repository.get_cart_item(actor.user_id, ste_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Cart item not found")

        existing.quantity = str(payload.quantity)
        existing = self.repository.save_cart_item(existing)
        return CartItemRead(
            id=existing.id,
            ste_id=existing.ste_id,
            quantity=int(existing.quantity),
            created_at=existing.created_at,
            updated_at=existing.updated_at,
            item=self._get_ste(existing.ste_id),
        )

    def remove_cart_item(self, ste_id: str, actor: CurrentActor) -> None:
        self.repository.delete_cart_item(actor.user_id, ste_id)

    def create_purchase(
        self,
        payload: PurchaseCreate,
        actor: CurrentActor,
    ):
        self._ensure_ste(payload.ste_id)
        model = self.repository.create_purchase_history(
            PurchaseHistoryModel(
                user_id=actor.user_id,
                organization_id=actor.organization_id,
                ste_id=payload.ste_id,
                quantity=str(payload.quantity),
                price=str(payload.price),
            )
        )
        item = self._get_ste(model.ste_id)
        if payload.session_id:
            self.event_service.create_system_event(
                session_id=payload.session_id,
                user_id=actor.user_id,
                organization_id=actor.organization_id,
                role=actor.role,
                event_type="purchase_completed",
                ste_id=model.ste_id,
                payload={
                    "quantity": payload.quantity,
                    "price": payload.price,
                    "contract_id": payload.contract_id or "",
                },
            )

        return PurchaseHistoryItemRead(
            id=model.id,
            ste_id=model.ste_id,
            title=item.title,
            description=item.description,
            category_id=item.category_id,
            category_name=item.category_name,
            supplier_id=item.supplier_id,
            supplier_name=item.supplier_name,
            quantity=model.quantity,
            price=model.price,
            purchased_at=model.purchased_at,
        )

    def _ensure_ste(self, ste_id: str) -> None:
        if not self.repository.ste_exists(ste_id):
            raise HTTPException(status_code=404, detail="STE item not found")

    def _get_ste(self, ste_id: str) -> STEItemRead:
        item = self.catalog_repository.get_ste_by_id(ste_id)
        if item is None:
            raise HTTPException(status_code=404, detail="STE item not found")
        return STEItemRead(
            id=item.id,
            title=item.title,
            description=item.description,
            category_id=item.category_id,
            category_name=item.category.name,
            supplier_id=item.supplier_id,
            supplier_name=item.supplier.name,
            attributes=item.attributes_json,
            status=item.status,
        )
