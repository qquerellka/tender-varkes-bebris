from pydantic import BaseModel


class DemoUserRead(BaseModel):
    id: str
    name: str
    organization_id: str
    organization_name: str
    role: str
    persona: str
    entry_mode: str = "empty"
    has_history: bool = False
    entry_note: str | None = None


class DemoLoginRequest(BaseModel):
    user_id: str


class CustomerInnRead(BaseModel):
    user_id: str
    organization_id: str
    organization_name: str
    buyer_inn: str
    contracts_count: int = 0
    has_history: bool = True
    entry_note: str | None = None


class CustomerInnLoginRequest(BaseModel):
    buyer_inn: str


class AuthSessionRead(BaseModel):
    user_id: str
    name: str
    organization_id: str
    organization_name: str
    role: str
    entry_mode: str = "empty"
    has_history: bool = False
    entry_note: str | None = None
    persona: str | None = None
    auth_method: str = "demo"
    buyer_inn: str | None = None
