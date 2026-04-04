import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.repositories.catalog import CatalogRepository
from app.db.repositories.events import EventRepository
from app.db.repositories.personalization import PersonalizationRepository
from app.db.repositories.search import SearchRepository
from app.db.repositories.user_actions import UserActionsRepository
from app.db.seed import seed_demo_data
from app.domain.auth.schemas import DemoLoginRequest
from app.domain.auth.service import AuthService
from app.domain.catalog.service import CatalogService
from app.domain.events.service import EventService
from app.domain.events.schemas import SearchEventCreate, SearchImpressionBatchCreate, SearchImpressionCreate
from app.domain.personalization.service import PersonalizationService
from app.domain.search.schemas import CurrentActor, SearchFilters, SearchRequest
from app.domain.search.service import SearchService
from app.domain.user_actions.schemas import CartItemCreate, ComparisonCreate, FavoriteCreate
from app.domain.user_actions.service import UserActionsService
from app.integrations.ml.base import NoopRankingProvider


class DemoSmokeFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        SearchRepository._search_vocabulary_cache = None
        SearchRepository._hybrid_index_cache = None
        SearchRepository._hybrid_index_signature = None

        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.session_factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)

        with self.session_factory() as session:
            seed_demo_data(session)

    def test_demo_flow_covers_auth_catalog_search_and_user_actions(self) -> None:
        with self.session_factory() as session:
            auth_service = AuthService(session)
            search_repository = SearchRepository(session)
            catalog_service = CatalogService(
                repository=CatalogRepository(session),
                search_repository=search_repository,
            )
            search_service = SearchService(
                catalog_service=catalog_service,
                event_service=EventService(EventRepository(session)),
                personalization_service=PersonalizationService(PersonalizationRepository(session)),
                search_repository=search_repository,
                ranking_provider=NoopRankingProvider(),
            )
            user_actions_service = UserActionsService(
                repository=UserActionsRepository(session),
                catalog_repository=CatalogRepository(session),
                event_service=EventService(EventRepository(session)),
            )
            personalization_service = PersonalizationService(PersonalizationRepository(session))

            demo_users = auth_service.list_demo_users()
            self.assertGreaterEqual(len(demo_users), 8)
            self.assertTrue(any(user.has_history for user in demo_users))
            self.assertTrue(any(not user.has_history for user in demo_users))

            seeded_user = next(
                user for user in demo_users if user.role == "customer" and user.has_history
            )
            login = auth_service.login_demo(DemoLoginRequest(user_id=seeded_user.id))
            self.assertEqual(login.user_id, seeded_user.id)
            self.assertEqual(login.role, "customer")

            actor = CurrentActor(
                user_id=login.user_id,
                organization_id=login.organization_id,
                role=login.role,
            )

            categories = catalog_service.list_categories()
            suppliers = catalog_service.list_suppliers()
            summary = catalog_service.get_catalog_summary(user_id=actor.user_id)
            feed = catalog_service.get_catalog_feed(
                user_id=actor.user_id,
                organization_id=actor.organization_id,
                limit=6,
                offset=0,
            )

            self.assertGreater(len(categories), 0)
            self.assertGreater(len(suppliers), 0)
            self.assertGreater(summary.ste_items_count, 0)
            self.assertGreater(len(feed.items), 0)
            self.assertGreater(feed.total, 0)

            result = search_service.search(
                SearchRequest(
                    query="бумага",
                    filters=SearchFilters(strict_match=False),
                ),
                actor,
            )
            self.assertEqual(result.meta.query, "бумага")
            self.assertGreater(len(result.items), 0)

            top_item = result.items[0]

            favorite = user_actions_service.add_favorite(
                FavoriteCreate(ste_id=top_item.id),
                actor,
            )
            comparison = user_actions_service.add_comparison_item(
                ComparisonCreate(ste_id=top_item.id),
                actor,
            )
            cart = user_actions_service.add_cart_item(
                CartItemCreate(ste_id=top_item.id, quantity=2),
                actor,
            )

            self.assertEqual(favorite.ste_id, top_item.id)
            self.assertEqual(comparison.ste_id, top_item.id)
            self.assertEqual(cart.quantity, 2)

            profile = personalization_service.get_search_profile(
                user_id=actor.user_id,
                organization_id=actor.organization_id,
            )
            self.assertIn(
                "Избранное, сравнение и корзина повышают похожие позиции",
                profile.active_signals,
            )
            self.assertIn(top_item.id, profile.recent_ste_ids)

    def test_empty_demo_customer_has_no_history_before_new_actions(self) -> None:
        with self.session_factory() as session:
            auth_service = AuthService(session)
            search_repository = SearchRepository(session)
            catalog_service = CatalogService(
                repository=CatalogRepository(session),
                search_repository=search_repository,
            )
            personalization_service = PersonalizationService(PersonalizationRepository(session))

            empty_user = next(
                user
                for user in auth_service.list_demo_users()
                if user.role == "customer" and not user.has_history
            )
            actor = CurrentActor(
                user_id=empty_user.id,
                organization_id=empty_user.organization_id,
                role=empty_user.role,
            )

            purchases = catalog_service.get_purchase_history(
                user_id=actor.user_id,
                organization_id=actor.organization_id,
                limit=6,
            )
            profile = personalization_service.get_search_profile(
                user_id=actor.user_id,
                organization_id=actor.organization_id,
            )

            self.assertEqual(purchases, [])
            self.assertEqual(profile.top_categories, [])
            self.assertEqual(profile.recent_ste_ids, [])
            self.assertEqual(profile.top_suppliers, [])
            self.assertEqual(profile.popular_queries, [])
            self.assertEqual(profile.active_signals, [])

    def test_debug_telemetry_lists_recent_events_and_impressions(self) -> None:
        with self.session_factory() as session:
            auth_service = AuthService(session)
            search_repository = SearchRepository(session)
            event_service = EventService(EventRepository(session))
            search_service = SearchService(
                catalog_service=CatalogService(
                    repository=CatalogRepository(session),
                    search_repository=search_repository,
                ),
                event_service=event_service,
                personalization_service=PersonalizationService(PersonalizationRepository(session)),
                search_repository=search_repository,
                ranking_provider=NoopRankingProvider(),
            )

            demo_user = auth_service.list_demo_users()[0]
            actor = CurrentActor(
                user_id=demo_user.id,
                organization_id=demo_user.organization_id,
                role=demo_user.role,
            )

            result = search_service.search(
                SearchRequest(
                    query="бумага",
                    filters=SearchFilters(strict_match=False),
                ),
                actor,
            )
            top_item = result.items[0]

            event_service.create_impressions(
                SearchImpressionBatchCreate(
                    items=[
                        SearchImpressionCreate(
                            search_session_id=result.meta.session_id,
                            ste_id=top_item.id,
                            rank_position=1,
                            results_page=1,
                            visible=True,
                        )
                    ]
                ),
                actor,
            )
            event_service.create_event(
                SearchEventCreate(
                    session_id=result.meta.session_id,
                    event_type="result_clicked",
                    ste_id=top_item.id,
                    page_type="catalog",
                    rank_position=1,
                    results_page=1,
                    payload={"source": "test"},
                ),
                actor,
            )

            events = event_service.list_events(
                user_id=actor.user_id,
                search_session_id=result.meta.session_id,
                limit=10,
            )
            impressions = event_service.list_impressions(
                user_id=actor.user_id,
                search_session_id=result.meta.session_id,
                limit=10,
            )

            self.assertGreaterEqual(events.total, 2)
            self.assertEqual(events.items[0].session_id, result.meta.session_id)
            self.assertEqual(impressions.total, 1)
            self.assertEqual(impressions.items[0].search_session_id, result.meta.session_id)
            self.assertEqual(impressions.items[0].ste_id, top_item.id)

            health = event_service.get_health_summary(
                user_id=actor.user_id,
                search_session_id=result.meta.session_id,
            )
            self.assertEqual(health.search_sessions_count, 1)
            self.assertGreaterEqual(health.events_count, 2)
            self.assertEqual(health.impressions_count, 1)
            self.assertGreaterEqual(health.result_clicked_count, 1)
            self.assertGreaterEqual(health.click_through_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
