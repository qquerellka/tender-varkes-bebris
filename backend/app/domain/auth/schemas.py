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
