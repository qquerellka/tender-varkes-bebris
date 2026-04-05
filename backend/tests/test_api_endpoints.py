import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_session_dependency
from app.auth.portal_customers import build_portal_customer_org_id, build_portal_customer_user_id
from app.db.base import Base
from app.db.models import OrgSearchProfileModel, OrganizationModel, PurchaseHistoryModel, UserModel, UserSearchProfileModel
from app.db.repositories.search import SearchRepository
from app.db.seed import seed_demo_data
from app.main import app


class ApiEndpointsTests(unittest.TestCase):
    def setUp(self) -> None:
        SearchRepository._search_vocabulary_cache = None
        SearchRepository._search_spell_vocabulary_cache = None
        SearchRepository._hybrid_index_cache = None
        SearchRepository._hybrid_index_signature = None

        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            class_=Session,
        )

        with self.session_factory() as session:
            seed_demo_data(session)

        def override_session_dependency():
            session = self.session_factory()
            try:
                yield session
            finally:
                session.close()

        self.override_session_dependency = override_session_dependency
        app.dependency_overrides[get_session_dependency] = override_session_dependency

        self.warmup_patch = patch("app.main._warmup_search_stack", self._fake_warmup)
        self.warmup_patch.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.warmup_patch.stop()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    @staticmethod
    def _fake_warmup() -> None:
        app.state.search_warmup = "ready"
        app.state.ranking_warmup = "ready"
        app.state.search_warmup_error = None
        app.state.ranking_warmup_error = None
        app.state.search_documents_count = 15
        app.state.semantic_backend = "fallback_tfidf"
        app.state.semantic_faiss_enabled = False
        app.state.ranking_provider_name = "NoopRankingProvider"
        app.state.ranking_provider_mode = "noop"

    def _headers(self, user_id: str) -> dict[str, str]:
        return {"X-Demo-User-Id": user_id}

    def test_auth_demo_users_and_empty_profile_endpoints(self) -> None:
        users_response = self.client.get("/api/v1/auth/demo-users")
        self.assertEqual(users_response.status_code, 200)
        users = users_response.json()
        self.assertGreaterEqual(len(users), 8)
        self.assertTrue(any(item["entry_mode"] == "history" for item in users))
        self.assertTrue(any(item["entry_mode"] == "empty" for item in users))

        empty_user = next(
            item for item in users if item["role"] == "customer" and item["entry_mode"] == "empty"
        )
        login_response = self.client.post(
            "/api/v1/auth/login-demo",
            json={"user_id": empty_user["id"]},
        )
        self.assertEqual(login_response.status_code, 200)

        profile_response = self.client.get(
            "/api/v1/profile/search",
            headers=self._headers(empty_user["id"]),
        )
        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(profile_response.json()["top_categories"], [])

        purchases_response = self.client.get(
            "/api/v1/profile/purchases",
            headers=self._headers(empty_user["id"]),
        )
        self.assertEqual(purchases_response.status_code, 200)
        self.assertEqual(purchases_response.json(), [])

    def test_auth_supports_login_for_customer_from_contract_inn(self) -> None:
        buyer_inn = "7701234567"
        organization_id = build_portal_customer_org_id(buyer_inn)
        user_id = build_portal_customer_user_id(buyer_inn)

        with self.session_factory() as session:
            session.merge(OrganizationModel(id=organization_id, name="Тестовый заказчик по ИНН"))
            session.merge(
                UserModel(
                    id=user_id,
                    organization_id=organization_id,
                    name="Тестовый заказчик по ИНН",
                    role="customer",
                )
            )
            session.merge(
                PurchaseHistoryModel(
                    id="purchase_test_inn",
                    user_id=user_id,
                    organization_id=organization_id,
                    ste_id="ste_107",
                    quantity="1",
                    price="1000",
                )
            )
            session.merge(
                UserSearchProfileModel(
                    user_id=user_id,
                    organization_id=organization_id,
                    top_categories_json=["Офис и снабжение"],
                    recent_ste_ids_json=["ste_107"],
                    top_suppliers_json=['ООО "МосСнаб"'],
                    popular_queries_json=["бумага офисная"],
                )
            )
            session.merge(
                OrgSearchProfileModel(
                    organization_id=organization_id,
                    top_categories_json=["Офис и снабжение"],
                    popular_ste_ids_json=["ste_107"],
                )
            )
            session.commit()

        customers_response = self.client.get(
            "/api/v1/auth/customer-organizations",
            params={"query": "7701"},
        )
        self.assertEqual(customers_response.status_code, 200)
        customers = customers_response.json()
        self.assertTrue(any(item["buyer_inn"] == buyer_inn for item in customers))

        login_response = self.client.post(
            "/api/v1/auth/login-inn",
            json={"buyer_inn": buyer_inn},
        )
        self.assertEqual(login_response.status_code, 200)
        session_payload = login_response.json()
        self.assertEqual(session_payload["user_id"], user_id)
        self.assertEqual(session_payload["organization_id"], organization_id)
        self.assertEqual(session_payload["auth_method"], "inn")
        self.assertEqual(session_payload["buyer_inn"], buyer_inn)
        self.assertTrue(session_payload["has_history"])

        profile_response = self.client.get(
            "/api/v1/profile/search",
            headers=self._headers(user_id),
        )
        self.assertEqual(profile_response.status_code, 200)
        self.assertIn("Офис и снабжение", profile_response.json()["top_categories"])

    def test_search_and_debug_endpoints_expose_runtime_status(self) -> None:
        actor_id = "demo_customer_transport"
        search_response = self.client.post(
            "/api/v1/search",
            json={"query": "бумага", "filters": {"strict_match": False}},
            headers=self._headers(actor_id),
        )
        self.assertEqual(search_response.status_code, 200)
        payload = search_response.json()
        self.assertTrue(payload["items"])
        session_id = payload["meta"]["session_id"]

        event_response = self.client.post(
            "/api/v1/events",
            json={
                "session_id": session_id,
                "event_type": "result_clicked",
                "ste_id": payload["items"][0]["id"],
                "page_type": "catalog",
                "rank_position": 1,
                "results_page": 1,
                "payload": {"source": "api-test"},
            },
            headers=self._headers(actor_id),
        )
        self.assertEqual(event_response.status_code, 201)

        telemetry_response = self.client.get(
            "/api/v1/debug/telemetry/health",
            params={"search_session_id": session_id},
            headers=self._headers(actor_id),
        )
        self.assertEqual(telemetry_response.status_code, 200)
        self.assertGreaterEqual(telemetry_response.json()["events_count"], 2)

        search_stack_response = self.client.get(
            "/api/v1/debug/search-stack",
            headers=self._headers(actor_id),
        )
        self.assertEqual(search_stack_response.status_code, 200)
        search_stack = search_stack_response.json()
        self.assertTrue(search_stack["ready"])
        self.assertEqual(search_stack["search_warmup"], "ready")
        self.assertEqual(search_stack["ranking_warmup"], "ready")
        self.assertEqual(search_stack["ranking_provider"], "NoopRankingProvider")
        self.assertEqual(search_stack["search_documents_count"], 15)


if __name__ == "__main__":
    unittest.main()
