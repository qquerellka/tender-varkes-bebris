from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    CartItemModel,
    ComparisonItemModel,
    FavoriteModel,
    PurchaseHistoryModel,
    STEItemModel,
)


class UserActionsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ste_exists(self, ste_id: str) -> bool:
        stmt = select(STEItemModel.id).where(STEItemModel.id == ste_id).limit(1)
        return self.session.scalar(stmt) is not None

    def list_favorites(self, user_id: str) -> list[FavoriteModel]:
        stmt = (
            select(FavoriteModel)
            .where(FavoriteModel.user_id == user_id)
            .order_by(FavoriteModel.created_at.desc())
        )
        return list(self.session.scalars(stmt))

    def get_favorite(self, user_id: str, ste_id: str) -> FavoriteModel | None:
        stmt = select(FavoriteModel).where(
            FavoriteModel.user_id == user_id,
            FavoriteModel.ste_id == ste_id,
        )
        return self.session.scalar(stmt)

    def create_favorite(self, favorite: FavoriteModel) -> FavoriteModel:
        self.session.add(favorite)
        self.session.commit()
        self.session.refresh(favorite)
        return favorite

    def delete_favorite(self, user_id: str, ste_id: str) -> None:
        self.session.execute(
            delete(FavoriteModel).where(
                FavoriteModel.user_id == user_id,
                FavoriteModel.ste_id == ste_id,
            )
        )
        self.session.commit()

    def list_comparison_items(self, user_id: str) -> list[ComparisonItemModel]:
        stmt = (
            select(ComparisonItemModel)
            .where(ComparisonItemModel.user_id == user_id)
            .order_by(ComparisonItemModel.created_at.desc())
        )
        return list(self.session.scalars(stmt))

    def get_comparison_item(self, user_id: str, ste_id: str) -> ComparisonItemModel | None:
        stmt = select(ComparisonItemModel).where(
            ComparisonItemModel.user_id == user_id,
            ComparisonItemModel.ste_id == ste_id,
        )
        return self.session.scalar(stmt)

    def create_comparison_item(
        self,
        item: ComparisonItemModel,
    ) -> ComparisonItemModel:
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def delete_comparison_item(self, user_id: str, ste_id: str) -> None:
        self.session.execute(
            delete(ComparisonItemModel).where(
                ComparisonItemModel.user_id == user_id,
                ComparisonItemModel.ste_id == ste_id,
            )
        )
        self.session.commit()

    def list_cart_items(self, user_id: str) -> list[CartItemModel]:
        stmt = (
            select(CartItemModel)
            .where(CartItemModel.user_id == user_id)
            .order_by(CartItemModel.updated_at.desc())
        )
        return list(self.session.scalars(stmt))

    def get_cart_item(self, user_id: str, ste_id: str) -> CartItemModel | None:
        stmt = select(CartItemModel).where(
            CartItemModel.user_id == user_id,
            CartItemModel.ste_id == ste_id,
        )
        return self.session.scalar(stmt)

    def create_cart_item(self, item: CartItemModel) -> CartItemModel:
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def save_cart_item(self, item: CartItemModel) -> CartItemModel:
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def delete_cart_item(self, user_id: str, ste_id: str) -> None:
        self.session.execute(
            delete(CartItemModel).where(
                CartItemModel.user_id == user_id,
                CartItemModel.ste_id == ste_id,
            )
        )
        self.session.commit()

    def create_purchase_history(
        self,
        item: PurchaseHistoryModel,
    ) -> PurchaseHistoryModel:
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def list_signal_items(self, user_id: str, limit: int = 12) -> list[STEItemModel]:
        favorite_stmt = (
            select(STEItemModel)
            .join(FavoriteModel, FavoriteModel.ste_id == STEItemModel.id)
            .where(FavoriteModel.user_id == user_id)
            .options(joinedload(STEItemModel.category), joinedload(STEItemModel.supplier))
            .order_by(FavoriteModel.created_at.desc())
            .limit(limit)
        )
        comparison_stmt = (
            select(STEItemModel)
            .join(ComparisonItemModel, ComparisonItemModel.ste_id == STEItemModel.id)
            .where(ComparisonItemModel.user_id == user_id)
            .options(joinedload(STEItemModel.category), joinedload(STEItemModel.supplier))
            .order_by(ComparisonItemModel.created_at.desc())
            .limit(limit)
        )
        cart_stmt = (
            select(STEItemModel)
            .join(CartItemModel, CartItemModel.ste_id == STEItemModel.id)
            .where(CartItemModel.user_id == user_id)
            .options(joinedload(STEItemModel.category), joinedload(STEItemModel.supplier))
            .order_by(CartItemModel.updated_at.desc())
            .limit(limit)
        )

        seen_ids: set[str] = set()
        items: list[STEItemModel] = []
        for stmt in (favorite_stmt, comparison_stmt, cart_stmt):
            for item in self.session.scalars(stmt):
                if item.id in seen_ids:
                    continue
                seen_ids.add(item.id)
                items.append(item)
                if len(items) >= limit:
                    return items

        return items
