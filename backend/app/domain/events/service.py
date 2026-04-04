from fastapi import HTTPException

from app.db.models import SearchEventModel, SearchImpressionModel
from app.db.repositories.events import EventRepository
from app.domain.events.schemas import (
    EventBatchResult,
    SearchEventBatchCreate,
    SearchEventCreate,
    SearchEventListRead,
    SearchEventRead,
    SearchImpressionBatchCreate,
    SearchImpressionListRead,
    SearchImpressionRead,
    TelemetryCountByTypeRead,
    TelemetryHealthRead,
)
from app.domain.search.schemas import CurrentActor


class EventService:
    def __init__(self, repository: EventRepository) -> None:
        self.repository = repository

    def create_event(self, payload: SearchEventCreate, actor: CurrentActor) -> SearchEventRead:
        if not self.repository.session_exists(payload.session_id):
            raise HTTPException(status_code=404, detail="Search session not found")

        supplier_id, category_id = self._resolve_item_context(
            ste_id=payload.ste_id,
            supplier_id=payload.supplier_id,
            category_id=payload.category_id,
        )
        return self._persist_event(
            session_id=payload.session_id,
            user_id=actor.user_id,
            organization_id=actor.organization_id,
            role=actor.role,
            event_type=payload.event_type,
            ste_id=payload.ste_id,
            supplier_id=supplier_id,
            category_id=category_id,
            query_text=payload.query_text,
            normalized_query=payload.normalized_query,
            corrected_query=payload.corrected_query,
            page_type=payload.page_type,
            page_url=payload.page_url,
            referrer=payload.referrer,
            rank_position=payload.rank_position,
            results_page=payload.results_page,
            payload=payload.payload,
        )

    def create_batch(
        self,
        payload: SearchEventBatchCreate,
        actor: CurrentActor,
    ) -> EventBatchResult:
        for item in payload.items:
            if not self.repository.session_exists(item.session_id):
                raise HTTPException(status_code=404, detail="Search session not found")

        models: list[SearchEventModel] = []
        for item in payload.items:
            supplier_id, category_id = self._resolve_item_context(
                ste_id=item.ste_id,
                supplier_id=item.supplier_id,
                category_id=item.category_id,
            )
            models.append(
                SearchEventModel(
                    session_id=item.session_id,
                    user_id=actor.user_id,
                    organization_id=actor.organization_id,
                    role=actor.role,
                    event_type=item.event_type,
                    ste_id=item.ste_id,
                    supplier_id=supplier_id,
                    category_id=category_id,
                    query_text=item.query_text,
                    normalized_query=item.normalized_query,
                    corrected_query=item.corrected_query,
                    page_type=item.page_type,
                    page_url=item.page_url,
                    referrer=item.referrer,
                    rank_position=item.rank_position,
                    results_page=item.results_page,
                    payload_json=item.payload,
                )
            )
        created = self.repository.create_many(models)
        return EventBatchResult(created_count=len(created))

    def create_impressions(
        self,
        payload: SearchImpressionBatchCreate,
        actor: CurrentActor,
    ) -> EventBatchResult:
        for item in payload.items:
            if not self.repository.session_exists(item.search_session_id):
                raise HTTPException(status_code=404, detail="Search session not found")

        models: list[SearchImpressionModel] = []
        for item in payload.items:
            supplier_id, category_id = self._resolve_item_context(
                ste_id=item.ste_id,
                supplier_id=item.supplier_id,
                category_id=item.category_id,
            )
            models.append(
                SearchImpressionModel(
                    search_session_id=item.search_session_id,
                    user_id=actor.user_id,
                    organization_id=actor.organization_id,
                    ste_id=item.ste_id,
                    supplier_id=supplier_id,
                    category_id=category_id,
                    rank_position=item.rank_position,
                    results_page=item.results_page,
                    visible=item.visible,
                )
            )
        created = self.repository.create_impressions(models)
        return EventBatchResult(created_count=len(created))

    def create_system_event(
        self,
        *,
        session_id: str,
        user_id: str,
        organization_id: str,
        role: str,
        event_type: str,
        ste_id: str | None = None,
        payload: dict | None = None,
    ) -> SearchEventRead:
        supplier_id, category_id = self._resolve_item_context(
            ste_id=ste_id,
            supplier_id=None,
            category_id=None,
        )
        return self._persist_event(
            session_id=session_id,
            user_id=user_id,
            organization_id=organization_id,
            role=role,
            event_type=event_type,
            ste_id=ste_id,
            supplier_id=supplier_id,
            category_id=category_id,
            query_text=None,
            normalized_query=None,
            corrected_query=None,
            page_type=None,
            page_url=None,
            referrer=None,
            rank_position=None,
            results_page=None,
            payload=payload or {},
        )

    def list_events(
        self,
        *,
        user_id: str,
        search_session_id: str | None = None,
        limit: int = 50,
    ) -> SearchEventListRead:
        events = self.repository.list_events(
            user_id=user_id,
            search_session_id=search_session_id,
            limit=limit,
        )
        return SearchEventListRead(
            items=[
                SearchEventRead(
                    id=event.id,
                    session_id=event.session_id,
                    user_id=event.user_id,
                    organization_id=event.organization_id,
                    role=event.role,
                    event_type=event.event_type,
                    ste_id=event.ste_id,
                    supplier_id=event.supplier_id,
                    category_id=event.category_id,
                    query_text=event.query_text,
                    normalized_query=event.normalized_query,
                    corrected_query=event.corrected_query,
                    page_type=event.page_type,
                    page_url=event.page_url,
                    referrer=event.referrer,
                    rank_position=event.rank_position,
                    results_page=event.results_page,
                    payload=event.payload_json,
                    created_at=event.created_at,
                )
                for event in events
            ],
            total=len(events),
        )

    def list_impressions(
        self,
        *,
        user_id: str,
        search_session_id: str | None = None,
        limit: int = 50,
    ) -> SearchImpressionListRead:
        impressions = self.repository.list_impressions(
            user_id=user_id,
            search_session_id=search_session_id,
            limit=limit,
        )
        return SearchImpressionListRead(
            items=[
                SearchImpressionRead(
                    id=impression.id,
                    search_session_id=impression.search_session_id,
                    user_id=impression.user_id,
                    organization_id=impression.organization_id,
                    ste_id=impression.ste_id,
                    supplier_id=impression.supplier_id,
                    category_id=impression.category_id,
                    rank_position=impression.rank_position,
                    results_page=impression.results_page,
                    visible=impression.visible,
                    rendered_at=impression.rendered_at,
                )
                for impression in impressions
            ],
            total=len(impressions),
        )

    def get_health_summary(
        self,
        *,
        user_id: str,
        search_session_id: str | None = None,
    ) -> TelemetryHealthRead:
        summary = self.repository.get_health_summary(
            user_id=user_id,
            search_session_id=search_session_id,
        )
        return TelemetryHealthRead(
            user_id=summary["user_id"],
            search_session_id=summary["search_session_id"],
            search_sessions_count=summary["search_sessions_count"],
            events_count=summary["events_count"],
            impressions_count=summary["impressions_count"],
            result_clicked_count=summary["result_clicked_count"],
            result_opened_count=summary["result_opened_count"],
            purchase_intent_count=summary["purchase_intent_count"],
            purchase_completed_count=summary["purchase_completed_count"],
            search_sessions_with_impressions_count=summary[
                "search_sessions_with_impressions_count"
            ],
            search_sessions_without_impressions_count=summary[
                "search_sessions_without_impressions_count"
            ],
            click_through_rate=summary["click_through_rate"],
            open_after_click_rate=summary["open_after_click_rate"],
            purchase_after_intent_rate=summary["purchase_after_intent_rate"],
            event_counts=[
                TelemetryCountByTypeRead(key=item["key"], count=item["count"])
                for item in summary["event_counts"]
            ],
        )

    def _persist_event(
        self,
        *,
        session_id: str,
        user_id: str,
        organization_id: str,
        role: str,
        event_type: str,
        ste_id: str | None,
        supplier_id: str | None,
        category_id: str | None,
        query_text: str | None,
        normalized_query: str | None,
        corrected_query: str | None,
        page_type: str | None,
        page_url: str | None,
        referrer: str | None,
        rank_position: int | None,
        results_page: int | None,
        payload: dict,
    ) -> SearchEventRead:
        model = SearchEventModel(
            session_id=session_id,
            user_id=user_id,
            organization_id=organization_id,
            role=role,
            event_type=event_type,
            ste_id=ste_id,
            supplier_id=supplier_id,
            category_id=category_id,
            query_text=query_text,
            normalized_query=normalized_query,
            corrected_query=corrected_query,
            page_type=page_type,
            page_url=page_url,
            referrer=referrer,
            rank_position=rank_position,
            results_page=results_page,
            payload_json=payload,
        )
        event = self.repository.create(model)
        return SearchEventRead(
            id=event.id,
            session_id=event.session_id,
            user_id=event.user_id,
            organization_id=event.organization_id,
            role=event.role,
            event_type=event.event_type,
            ste_id=event.ste_id,
            supplier_id=event.supplier_id,
            category_id=event.category_id,
            query_text=event.query_text,
            normalized_query=event.normalized_query,
            corrected_query=event.corrected_query,
            page_type=event.page_type,
            page_url=event.page_url,
            referrer=event.referrer,
            rank_position=event.rank_position,
            results_page=event.results_page,
            payload=event.payload_json,
            created_at=event.created_at,
        )

    def _resolve_item_context(
        self,
        *,
        ste_id: str | None,
        supplier_id: str | None,
        category_id: str | None,
    ) -> tuple[str | None, str | None]:
        if not ste_id or (supplier_id and category_id):
            return supplier_id, category_id

        resolved_supplier_id, resolved_category_id = self.repository.get_ste_context(ste_id)
        return supplier_id or resolved_supplier_id, category_id or resolved_category_id
