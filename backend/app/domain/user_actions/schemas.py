from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.catalog.schemas import STEItemRead


class FavoriteCreate(BaseModel):
    ste_id: str


class ComparisonCreate(BaseModel):
    ste_id: str


class CartItemCreate(BaseModel):
    ste_id: str
    quantity: int = Field(default=1, ge=1, le=999)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=999)


class PurchaseCreate(BaseModel):
    ste_id: str
    quantity: int = Field(default=1, ge=1, le=999)
    price: float = Field(default=0, ge=0)
    session_id: str | None = None
    contract_id: str | None = None


class FavoriteItemRead(BaseModel):
    id: str
    ste_id: str
    created_at: datetime
    item: STEItemRead


class ComparisonItemRead(BaseModel):
    id: str
    ste_id: str
    created_at: datetime
    item: STEItemRead


class CartItemRead(BaseModel):
    id: str
    ste_id: str
    quantity: int
    created_at: datetime
    updated_at: datetime
    item: STEItemRead
