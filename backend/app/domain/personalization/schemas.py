from pydantic import BaseModel, Field


class SearchProfileRead(BaseModel):
    user_id: str
    organization_id: str
    top_categories: list[str] = Field(default_factory=list)
    org_top_categories: list[str] = Field(default_factory=list)
    recent_ste_ids: list[str] = Field(default_factory=list)
    top_suppliers: list[str] = Field(default_factory=list)
    popular_ste_ids: list[str] = Field(default_factory=list)
    popular_queries: list[str] = Field(default_factory=list)
    active_signals: list[str] = Field(default_factory=list)
