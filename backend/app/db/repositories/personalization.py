from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    CartItemModel,
    ComparisonItemModel,
    FavoriteModel,
    OrgSearchProfileModel,
    SearchEventModel,
    STEItemModel,
    UserSearchProfileModel,
)


class PersonalizationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_user_profile(
        self,
        user_id: str,
        organization_id: str,
    ) -> UserSearchProfileModel | None:
        stmt = select(UserSearchProfileModel).where(
            UserSearchProfileModel.user_id == user_id,
            UserSearchProfileModel.organization_id == organization_id,
        )
        return self.session.scalar(stmt)

    def get_org_profile(self, organization_id: str) -> OrgSearchProfileModel | None:
        stmt = select(OrgSearchProfileModel).where(
            OrgSearchProfileModel.organization_id == organization_id
        )
        return self.session.scalar(stmt)

    def get_recent_event_items(
        self,
        user_id: str,
        organization_id: str,
        limit: int = 8,
    ) -> list[STEItemModel]:
        stmt = (
            select(STEItemModel)
            .join(SearchEventModel, SearchEventModel.ste_id == STEItemModel.id)
            .where(
                SearchEventModel.user_id == user_id,
                SearchEventModel.organization_id == organization_id,
                SearchEventModel.ste_id.isnot(None),
                SearchEventModel.event_type.in_(
                    [
                        "result_clicked",
                        "result_opened",
                        "favorite_added",
                        "comparison_added",
                        "cart_added",
                        "purchase_completed",
                    ]
                ),
            )
            .options(joinedload(STEItemModel.category), joinedload(STEItemModel.supplier))
            .order_by(SearchEventModel.created_at.desc())
            .limit(limit * 3)
        )
        return self._deduplicate_items(self.session.scalars(stmt), limit)

    def get_collection_signal_items(
        self,
        user_id: str,
        limit: int = 8,
    ) -> list[STEItemModel]:
        statements = (
            select(STEItemModel)
            .join(FavoriteModel, FavoriteModel.ste_id == STEItemModel.id)
            .where(FavoriteModel.user_id == user_id)
            .options(joinedload(STEItemModel.category), joinedload(STEItemModel.supplier))
            .order_by(FavoriteModel.created_at.desc())
            .limit(limit),
            select(STEItemModel)
            .join(ComparisonItemModel, ComparisonItemModel.ste_id == STEItemModel.id)
            .where(ComparisonItemModel.user_id == user_id)
            .options(joinedload(STEItemModel.category), joinedload(STEItemModel.supplier))
            .order_by(ComparisonItemModel.created_at.desc())
            .limit(limit),
            select(STEItemModel)
            .join(CartItemModel, CartItemModel.ste_id == STEItemModel.id)
            .where(CartItemModel.user_id == user_id)
            .options(joinedload(STEItemModel.category), joinedload(STEItemModel.supplier))
            .order_by(CartItemModel.updated_at.desc())
            .limit(limit),
        )

        seen_ids: set[str] = set()
        items: list[STEItemModel] = []
        for stmt in statements:
            for item in self.session.scalars(stmt):
                if item.id in seen_ids:
                    continue
                seen_ids.add(item.id)
                items.append(item)
                if len(items) >= limit:
                    return items
        return items

    @staticmethod
    def _deduplicate_items(items, limit: int) -> list[STEItemModel]:
        seen_ids: set[str] = set()
        result: list[STEItemModel] = []
        for item in items:
            if item.id in seen_ids:
                continue
            seen_ids.add(item.id)
            result.append(item)
            if len(result) >= limit:
                break
        return result
