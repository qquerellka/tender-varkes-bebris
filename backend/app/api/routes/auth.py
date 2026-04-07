from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_auth_service, get_current_actor, get_session_dependency
from app.domain.auth.schemas import AuthSessionRead, DemoLoginRequest, DemoUserRead
from app.domain.auth.service import AuthService
from app.domain.search.schemas import CurrentActor

router = APIRouter()


@router.get("/demo-users", response_model=list[DemoUserRead])
def list_demo_users(
    session: Session = Depends(get_session_dependency),
) -> list[DemoUserRead]:
    auth_service = get_auth_service(session)
    return auth_service.list_demo_users()


@router.post("/login-demo", response_model=AuthSessionRead)
def login_demo(
    payload: DemoLoginRequest,
    session: Session = Depends(get_session_dependency),
) -> AuthSessionRead:
    auth_service = get_auth_service(session)
    return auth_service.login_demo(payload)


@router.get("/me", response_model=AuthSessionRead)
def get_me(
    session: Session = Depends(get_session_dependency),
    actor: CurrentActor = Depends(get_current_actor),
) -> AuthSessionRead:
    auth_service = get_auth_service(session)
    return auth_service.get_current_session(actor)
