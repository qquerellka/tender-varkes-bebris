from sqlalchemy import func, select
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.auth.demo import (
    ensure_demo_profiles,
    get_demo_profile_definition,
    list_demo_profiles,
)
from app.auth.portal_customers import (
    PORTAL_CUSTOMER_USER_ID_PREFIX,
    build_portal_customer_user_id,
    extract_buyer_inn_from_user_id,
    normalize_buyer_inn,
)
from app.db.models import OrganizationModel, PurchaseHistoryModel, UserModel, UserSearchProfileModel
from app.domain.auth.schemas import (
    AuthSessionRead,
    CustomerInnLoginRequest,
    CustomerInnRead,
    DemoLoginRequest,
    DemoUserRead,
)
from app.domain.search.schemas import CurrentActor


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_demo_users(self) -> list[DemoUserRead]:
        ensure_demo_profiles(self.session)
        return [
            DemoUserRead(
                id=item.user_id,
                name=item.name,
                organization_id=item.organization_id,
                organization_name=item.organization_name,
                role=item.role,
                persona=item.persona,
                entry_mode=item.entry_mode,
                has_history=item.has_history,
                entry_note=item.entry_note,
            )
            for item in list_demo_profiles()
        ]

    def login_demo(self, payload: DemoLoginRequest) -> AuthSessionRead:
        ensure_demo_profiles(self.session)
        definition = get_demo_profile_definition(payload.user_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Demo user not found")

        user = self.session.scalar(
            select(UserModel)
            .where(UserModel.id == payload.user_id)
            .options(joinedload(UserModel.organization))
            .limit(1)
        )
        if user is None:
            raise HTTPException(status_code=404, detail="Demo user is unavailable")

        return AuthSessionRead(
            user_id=user.id,
            name=user.name,
            organization_id=user.organization_id,
            organization_name=user.organization.name,
            role=user.role,
            entry_mode=definition.entry_mode,
            has_history=definition.has_history,
            entry_note=definition.entry_note,
            persona=definition.persona,
            auth_method="demo",
        )

    def list_customer_accounts(self, query: str, limit: int = 8) -> list[CustomerInnRead]:
        normalized_query = normalize_buyer_inn(query)
        if len(normalized_query) < 3:
            return []

        stmt = (
            select(
                UserModel.id.label("user_id"),
                UserModel.organization_id.label("organization_id"),
                OrganizationModel.name.label("organization_name"),
                func.count(PurchaseHistoryModel.id).label("contracts_count"),
            )
            .join(OrganizationModel, OrganizationModel.id == UserModel.organization_id)
            .outerjoin(PurchaseHistoryModel, PurchaseHistoryModel.user_id == UserModel.id)
            .where(
                UserModel.role == "customer",
                UserModel.id.like(f"{PORTAL_CUSTOMER_USER_ID_PREFIX}{normalized_query}%"),
            )
            .group_by(UserModel.id, UserModel.organization_id, OrganizationModel.name)
            .order_by(func.count(PurchaseHistoryModel.id).desc(), OrganizationModel.name.asc())
            .limit(limit)
        )

        accounts: list[CustomerInnRead] = []
        for row in self.session.execute(stmt):
            buyer_inn = extract_buyer_inn_from_user_id(row.user_id) or ""
            contracts_count = row.contracts_count or 0
            accounts.append(
                CustomerInnRead(
                    user_id=row.user_id,
                    organization_id=row.organization_id,
                    organization_name=row.organization_name,
                    buyer_inn=buyer_inn,
                    contracts_count=contracts_count,
                    has_history=contracts_count > 0,
                    entry_note=(
                        f"Контекст построен по истории контрактов заказчика с ИНН {buyer_inn}"
                    ),
                )
            )
        return accounts

    def login_customer_by_inn(self, payload: CustomerInnLoginRequest) -> AuthSessionRead:
        buyer_inn = normalize_buyer_inn(payload.buyer_inn)
        if not buyer_inn:
            raise HTTPException(status_code=422, detail="Buyer INN is required")

        user = self.session.scalar(
            select(UserModel)
            .where(UserModel.id == build_portal_customer_user_id(buyer_inn))
            .options(joinedload(UserModel.organization))
            .limit(1)
        )
        if user is None:
            raise HTTPException(status_code=404, detail="Customer account not found")

        return self._build_portal_customer_session(user, buyer_inn)

    def get_current_session(self, actor: CurrentActor) -> AuthSessionRead:
        ensure_demo_profiles(self.session)
        definition = get_demo_profile_definition(actor.user_id)
        buyer_inn = extract_buyer_inn_from_user_id(actor.user_id)
        if buyer_inn:
            user = self.session.scalar(
                select(UserModel)
                .where(UserModel.id == actor.user_id)
                .options(joinedload(UserModel.organization))
                .limit(1)
            )
            if user is not None:
                return self._build_portal_customer_session(user, buyer_inn)

        return AuthSessionRead(
            user_id=actor.user_id,
            name=actor.name or actor.user_id,
            organization_id=actor.organization_id,
            organization_name=actor.organization_name or actor.organization_id,
            role=actor.role,
            entry_mode=definition.entry_mode if definition else "empty",
            has_history=definition.has_history if definition else False,
            entry_note=definition.entry_note if definition else None,
            persona=definition.persona if definition else None,
            auth_method="demo",
        )

    def _build_portal_customer_session(self, user: UserModel, buyer_inn: str) -> AuthSessionRead:
        user_profile = self.session.scalar(
            select(UserSearchProfileModel).where(
                UserSearchProfileModel.user_id == user.id,
                UserSearchProfileModel.organization_id == user.organization_id,
            )
        )
        purchase_count = self.session.scalar(
            select(func.count(PurchaseHistoryModel.id)).where(PurchaseHistoryModel.user_id == user.id)
        )
        has_history = user_profile is not None or (purchase_count or 0) > 0
        entry_mode = "history" if has_history else "empty"
        entry_note = (
            f"Контекст построен по истории контрактов заказчика с ИНН {buyer_inn}"
            if has_history
            else f"Для заказчика с ИНН {buyer_inn} пока нет загруженной истории"
        )

        return AuthSessionRead(
            user_id=user.id,
            name=user.name,
            organization_id=user.organization_id,
            organization_name=user.organization.name,
            role=user.role,
            entry_mode=entry_mode,
            has_history=has_history,
            entry_note=entry_note,
            persona="Заказчик по данным контрактов портала",
            auth_method="inn",
            buyer_inn=buyer_inn,
        )
