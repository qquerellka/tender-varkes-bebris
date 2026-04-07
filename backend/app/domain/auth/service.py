from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.demo import (
    ensure_demo_profiles,
    get_demo_profile_definition,
    list_demo_profiles,
)
from app.db.models import UserModel
from app.domain.auth.schemas import AuthSessionRead, DemoLoginRequest, DemoUserRead
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
        )

    def get_current_session(self, actor: CurrentActor) -> AuthSessionRead:
        ensure_demo_profiles(self.session)
        definition = get_demo_profile_definition(actor.user_id)
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
        )
