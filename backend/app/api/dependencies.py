from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth.demo import get_demo_actor
from app.core.config import settings
from app.db.repositories.catalog import CatalogRepository
from app.db.repositories.events import EventRepository
from app.db.repositories.personalization import PersonalizationRepository
from app.db.repositories.search import SearchRepository
from app.db.repositories.user_actions import UserActionsRepository
from app.db.session import get_db_session
from app.domain.auth.service import AuthService
from app.domain.catalog.service import CatalogService
from app.domain.events.service import EventService
from app.domain.personalization.service import PersonalizationService
from app.domain.search.schemas import CurrentActor
from app.domain.search.service import SearchService
from app.domain.user_actions.service import UserActionsService
from app.integrations.ml.base import NoopRankingProvider, RankingProvider
from app.integrations.ml.local import LocalMlRankingProvider


def get_catalog_repository(
    session: Session,
) -> CatalogRepository:
    return CatalogRepository(session)


def get_personalization_repository(
    session: Session,
) -> PersonalizationRepository:
    return PersonalizationRepository(session)


def get_event_repository(
    session: Session,
) -> EventRepository:
    return EventRepository(session)


def get_search_repository(
    session: Session,
) -> SearchRepository:
    return SearchRepository(session)


def get_user_actions_repository(
    session: Session,
) -> UserActionsRepository:
    return UserActionsRepository(session)


def get_session_dependency() -> Generator[Session, None, None]:
    yield from get_db_session()


def get_catalog_service(
    session: Session,
) -> CatalogService:
    return CatalogService(
        repository=get_catalog_repository(session),
        search_repository=get_search_repository(session),
    )


def get_event_service(
    session: Session,
) -> EventService:
    return EventService(repository=get_event_repository(session))


def get_auth_service(
    session: Session,
) -> AuthService:
    return AuthService(session)


def get_personalization_service(
    session: Session,
) -> PersonalizationService:
    return PersonalizationService(repository=get_personalization_repository(session))


def get_user_actions_service(
    session: Session,
) -> UserActionsService:
    return UserActionsService(
        repository=get_user_actions_repository(session),
        catalog_repository=get_catalog_repository(session),
        event_service=get_event_service(session),
    )


@lru_cache
def get_ranking_provider() -> RankingProvider:
    provider_mode = settings.ranking_provider.strip().lower()
    if provider_mode == "local_ml":
        return LocalMlRankingProvider(artifacts_dir=settings.ml_artifacts_dir)
    return NoopRankingProvider()


def get_search_service(
    session: Session,
) -> SearchService:
    catalog_service = get_catalog_service(session)
    event_service = get_event_service(session)
    personalization_service = get_personalization_service(session)
    search_repository = get_search_repository(session)
    ranking_provider = get_ranking_provider()
    return SearchService(
        catalog_service=catalog_service,
        event_service=event_service,
        personalization_service=personalization_service,
        search_repository=search_repository,
        ranking_provider=ranking_provider,
    )


def get_current_actor(
    request: Request,
    session: Session = Depends(get_session_dependency),
) -> CurrentActor:
    demo_user_id = request.headers.get("x-demo-user-id")
    return get_demo_actor(session, user_id_override=demo_user_id)
