from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.backtest import StrategyDraft


class CustomBlockBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    category: str = Field(min_length=1, max_length=40)
    tags: list[str] = Field(default_factory=list, max_length=12)
    template: StrategyDraft

    model_config = ConfigDict(populate_by_name=True)


class CustomBlockCreate(CustomBlockBase):
    pass


class CustomBlockUpdate(CustomBlockBase):
    pass


class CustomBlockResponse(CustomBlockBase):
    id: int
    owner_id: int = Field(alias="ownerId")
    review_status: str = Field(alias="reviewStatus")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class CustomBlockListResponse(BaseModel):
    items: list[CustomBlockResponse]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")

    model_config = ConfigDict(populate_by_name=True)
