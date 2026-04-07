from app.db.models import STEItemModel
from app.db.repositories.personalization import PersonalizationRepository
from app.domain.personalization.schemas import SearchProfileRead


class PersonalizationService:
    def __init__(self, repository: PersonalizationRepository) -> None:
        self.repository = repository

    def get_search_profile(
        self,
        user_id: str,
        organization_id: str,
    ) -> SearchProfileRead:
        user_profile = self.repository.get_user_profile(
            user_id=user_id,
            organization_id=organization_id,
        )
        org_profile = self.repository.get_org_profile(organization_id=organization_id)
        recent_event_items = self.repository.get_recent_event_items(
            user_id=user_id,
            organization_id=organization_id,
            limit=8,
        )
        collection_signal_items = self.repository.get_collection_signal_items(
            user_id=user_id,
            limit=8,
        )

        top_categories = list(user_profile.top_categories_json if user_profile else [])
        recent_ste_ids = list(user_profile.recent_ste_ids_json if user_profile else [])
        top_suppliers = list(user_profile.top_suppliers_json if user_profile else [])
        popular_queries = list(user_profile.popular_queries_json if user_profile else [])
        active_signals: list[str] = []

        self._merge_items(
            top_categories=top_categories,
            recent_ste_ids=recent_ste_ids,
            top_suppliers=top_suppliers,
            items=recent_event_items,
            signal_label="Недавние просмотры и открытия карточек влияют на выдачу",
            active_signals=active_signals,
        )
        self._merge_items(
            top_categories=top_categories,
            recent_ste_ids=recent_ste_ids,
            top_suppliers=top_suppliers,
            items=collection_signal_items,
            signal_label="Избранное, сравнение и корзина повышают похожие позиции",
            active_signals=active_signals,
        )

        return SearchProfileRead(
            user_id=user_id,
            organization_id=organization_id,
            top_categories=top_categories,
            org_top_categories=org_profile.top_categories_json if org_profile else [],
            recent_ste_ids=recent_ste_ids,
            top_suppliers=top_suppliers,
            popular_ste_ids=org_profile.popular_ste_ids_json if org_profile else [],
            popular_queries=popular_queries,
            active_signals=active_signals,
        )

    @staticmethod
    def _merge_items(
        *,
        top_categories: list[str],
        recent_ste_ids: list[str],
        top_suppliers: list[str],
        items: list[STEItemModel],
        signal_label: str,
        active_signals: list[str],
    ) -> None:
        if not items:
            return

        active_signals.append(signal_label)

        for item in items:
            if item.id not in recent_ste_ids:
                recent_ste_ids.insert(0, item.id)
            if item.category.name not in top_categories:
                top_categories.insert(0, item.category.name)
            if item.supplier.name not in top_suppliers:
                top_suppliers.insert(0, item.supplier.name)

        del recent_ste_ids[12:]
        del top_categories[8:]
        del top_suppliers[8:]
