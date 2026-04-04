from pydantic import BaseModel


class DemoUserRead(BaseModel):
    id: str
    name: str
    organization_id: str
    organization_name: str
    role: str
    persona: str


class DemoLoginRequest(BaseModel):
    user_id: str


class AuthSessionRead(BaseModel):
    user_id: str
    name: str
    organization_id: str
    organization_name: str
    role: str
    persona: str | None = None
