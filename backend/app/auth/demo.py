from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import OrganizationModel, UserModel
from app.domain.search.schemas import CurrentActor


@dataclass(frozen=True)
class DemoProfileDefinition:
    user_id: str
    organization_id: str
    organization_name: str
    name: str
    role: str
    persona: str


DEMO_PROFILE_DEFINITIONS: tuple[DemoProfileDefinition, ...] = (
    DemoProfileDefinition(
        user_id="demo_customer_transport",
        organization_id="demo_org_transport",
        organization_name="Департамент городской логистики",
        name="Анна Прохорова",
        role="customer",
        persona="Транспорт и хозяйственное снабжение",
    ),
    DemoProfileDefinition(
        user_id="demo_customer_it",
        organization_id="demo_org_it",
        organization_name="Центр цифровой инфраструктуры",
        name="Илья Назаров",
        role="customer",
        persona="ИТ-закупки и инфраструктура",
    ),
    DemoProfileDefinition(
        user_id="demo_supplier_food",
        organization_id="demo_org_supplier_food",
        organization_name='ООО "Русский хлебозавод"',
        name="Марина Колосова",
        role="supplier",
        persona="Поставщик продуктов и выпечки",
    ),
    DemoProfileDefinition(
        user_id="demo_supplier_toys",
        organization_id="demo_org_supplier_toys",
        organization_name='ООО "Стеллар Трейд"',
        name="Виктор Проскурин",
        role="supplier",
        persona="Поставщик детских товаров и сезонной продукции",
    ),
)


def list_demo_profiles() -> tuple[DemoProfileDefinition, ...]:
    return DEMO_PROFILE_DEFINITIONS


def get_demo_profile_definition(user_id: str) -> DemoProfileDefinition | None:
    return next((item for item in DEMO_PROFILE_DEFINITIONS if item.user_id == user_id), None)


def ensure_demo_profiles(session: Session) -> None:
    changed = False

    for profile in DEMO_PROFILE_DEFINITIONS:
        organization = session.get(OrganizationModel, profile.organization_id)
        if organization is None:
            session.add(
                OrganizationModel(
                    id=profile.organization_id,
                    name=profile.organization_name,
                )
            )
            changed = True

        user = session.get(UserModel, profile.user_id)
        if user is None:
            session.add(
                UserModel(
                    id=profile.user_id,
                    organization_id=profile.organization_id,
                    name=profile.name,
                    role=profile.role,
                )
            )
            changed = True
            continue

        if (
            user.organization_id != profile.organization_id
            or user.name != profile.name
            or user.role != profile.role
        ):
            user.organization_id = profile.organization_id
            user.name = profile.name
            user.role = profile.role
            changed = True

    if changed:
        session.commit()


def _build_actor(user: UserModel) -> CurrentActor:
    return CurrentActor(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
        name=user.name,
        organization_name=user.organization.name if user.organization else None,
        personalization_enabled=True,
    )


def get_demo_actor(
    session: Session,
    user_id_override: str | None = None,
) -> CurrentActor:
    ensure_demo_profiles(session)

    if user_id_override:
        overridden_user = session.scalar(
            select(UserModel).where(UserModel.id == user_id_override).limit(1)
        )
        if overridden_user is not None:
            return _build_actor(overridden_user)

    fallback_user = session.scalar(
        select(UserModel).where(UserModel.id == DEMO_PROFILE_DEFINITIONS[0].user_id).limit(1)
    )
    if fallback_user is not None:
        return _build_actor(fallback_user)

    any_user = session.scalar(select(UserModel).order_by(UserModel.id.asc()).limit(1))
    if any_user is not None:
        return _build_actor(any_user)

    default_profile = DEMO_PROFILE_DEFINITIONS[0]
    return CurrentActor(
        user_id=default_profile.user_id,
        organization_id=default_profile.organization_id,
        role=default_profile.role,
        name=default_profile.name,
        organization_name=default_profile.organization_name,
        personalization_enabled=True,
    )
