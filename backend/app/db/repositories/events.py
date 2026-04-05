from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import SearchEventModel, SearchImpressionModel, SearchSessionModel, STEItemModel


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, event: SearchEventModel) -> SearchEventModel:
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def create_many(self, events: list[SearchEventModel]) -> list[SearchEventModel]:
        if not events:
            return []

        self.session.add_all(events)
        self.session.commit()
        return events

    def create_impressions(
        self,
        impressions: list[SearchImpressionModel],
    ) -> list[SearchImpressionModel]:
        if not impressions:
            return []

        self.session.add_all(impressions)
        self.session.commit()
        return impressions

    def session_exists(self, session_id: str) -> bool:
        stmt = select(SearchSessionModel.id).where(SearchSessionModel.id == session_id)
        return self.session.scalar(stmt) is not None

    def get_ste_context(self, ste_id: str) -> tuple[str | None, str | None]:
        stmt = select(STEItemModel.supplier_id, STEItemModel.category_id).where(
            STEItemModel.id == ste_id
        )
        row = self.session.execute(stmt).one_or_none()
        if row is None:
            return None, None
        return row[0], row[1]

    def list_events(
        self,
        *,
        user_id: str | None = None,
        search_session_id: str | None = None,
        limit: int = 50,
    ) -> list[SearchEventModel]:
        stmt = select(SearchEventModel).order_by(SearchEventModel.created_at.desc())
        if user_id:
            stmt = stmt.where(SearchEventModel.user_id == user_id)
        if search_session_id:
            stmt = stmt.where(SearchEventModel.session_id == search_session_id)
        stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt).all())

    def list_impressions(
        self,
        *,
        user_id: str | None = None,
        search_session_id: str | None = None,
        limit: int = 50,
    ) -> list[SearchImpressionModel]:
        stmt = select(SearchImpressionModel).order_by(SearchImpressionModel.rendered_at.desc())
        if user_id:
            stmt = stmt.where(SearchImpressionModel.user_id == user_id)
        if search_session_id:
            stmt = stmt.where(SearchImpressionModel.search_session_id == search_session_id)
        stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt).all())

    def get_health_summary(
        self,
        *,
        user_id: str,
        search_session_id: str | None = None,
    ) -> dict:
        sessions_stmt = select(func.count()).select_from(SearchSessionModel).where(
            SearchSessionModel.user_id == user_id
        )
        if search_session_id:
            sessions_stmt = sessions_stmt.where(SearchSessionModel.id == search_session_id)
        search_sessions_count = int(self.session.scalar(sessions_stmt) or 0)

        events_base = select(SearchEventModel).where(SearchEventModel.user_id == user_id)
        if search_session_id:
            events_base = events_base.where(SearchEventModel.session_id == search_session_id)

        impressions_base = select(SearchImpressionModel).where(
            SearchImpressionModel.user_id == user_id
        )
        if search_session_id:
            impressions_base = impressions_base.where(
                SearchImpressionModel.search_session_id == search_session_id
            )

        events_count = int(
            self.session.scalar(
                select(func.count()).select_from(events_base.subquery())
            )
            or 0
        )
        impressions_count = int(
            self.session.scalar(
                select(func.count()).select_from(impressions_base.subquery())
            )
            or 0
        )

        event_counts_stmt = (
            select(SearchEventModel.event_type, func.count())
            .where(SearchEventModel.user_id == user_id)
            .group_by(SearchEventModel.event_type)
            .order_by(func.count().desc(), SearchEventModel.event_type.asc())
        )
        if search_session_id:
            event_counts_stmt = event_counts_stmt.where(
                SearchEventModel.session_id == search_session_id
            )
        event_counts = [
            {"key": event_type, "count": int(count)}
            for event_type, count in self.session.execute(event_counts_stmt).all()
        ]
        event_counts_map = {item["key"]: item["count"] for item in event_counts}

        sessions_with_impressions_stmt = (
            select(func.count(func.distinct(SearchImpressionModel.search_session_id)))
            .where(SearchImpressionModel.user_id == user_id)
        )
        if search_session_id:
            sessions_with_impressions_stmt = sessions_with_impressions_stmt.where(
                SearchImpressionModel.search_session_id == search_session_id
            )
        search_sessions_with_impressions_count = int(
            self.session.scalar(sessions_with_impressions_stmt) or 0
        )

        result_clicked_count = event_counts_map.get("result_clicked", 0)
        result_opened_count = event_counts_map.get("result_opened", 0)
        purchase_intent_count = event_counts_map.get("purchase_intent", 0)
        purchase_completed_count = event_counts_map.get("purchase_completed", 0)

        click_through_rate = (
            round(result_clicked_count / impressions_count, 4) if impressions_count else 0.0
        )
        open_after_click_rate = (
            round(result_opened_count / result_clicked_count, 4)
            if result_clicked_count
            else 0.0
        )
        purchase_after_intent_rate = (
            round(purchase_completed_count / purchase_intent_count, 4)
            if purchase_intent_count
            else 0.0
        )

        return {
            "user_id": user_id,
            "search_session_id": search_session_id,
            "search_sessions_count": search_sessions_count,
            "events_count": events_count,
            "impressions_count": impressions_count,
            "result_clicked_count": result_clicked_count,
            "result_opened_count": result_opened_count,
            "purchase_intent_count": purchase_intent_count,
            "purchase_completed_count": purchase_completed_count,
            "search_sessions_with_impressions_count": search_sessions_with_impressions_count,
            "search_sessions_without_impressions_count": max(
                0, search_sessions_count - search_sessions_with_impressions_count
            ),
            "click_through_rate": click_through_rate,
            "open_after_click_rate": open_after_click_rate,
            "purchase_after_intent_rate": purchase_after_intent_rate,
            "event_counts": event_counts,
        }

    def clear_user_activity(
        self,
        *,
        user_id: str,
        organization_id: str,
    ) -> dict[str, int]:
        deleted_events = self.session.execute(
            delete(SearchEventModel).where(
                SearchEventModel.user_id == user_id,
                SearchEventModel.organization_id == organization_id,
            )
        )
        deleted_impressions = self.session.execute(
            delete(SearchImpressionModel).where(
                SearchImpressionModel.user_id == user_id,
                SearchImpressionModel.organization_id == organization_id,
            )
        )
        self.session.commit()
        return {
            "events_deleted": deleted_events.rowcount or 0,
            "impressions_deleted": deleted_impressions.rowcount or 0,
        }
