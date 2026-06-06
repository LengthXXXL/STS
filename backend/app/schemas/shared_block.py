from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.backtest import StrategyDraft


class SharedBlockItemResponse(BaseModel):
    id: int
    owner_id: int = Field(alias="ownerId")
    author_name: str = Field(alias="authorName")
    name: str
    description: str | None
    category: str
    tags: list[str]
    review_status: str = Field(alias="reviewStatus")
    node_count: int = Field(alias="nodeCount")
    connection_count: int = Field(alias="connectionCount")
    view_count: int = Field(alias="viewCount")
    favorite_count: int = Field(alias="favoriteCount")
    import_count: int = Field(alias="importCount")
    is_favorited: bool = Field(alias="isFavorited")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class SharedBlockDetailResponse(SharedBlockItemResponse):
    template: StrategyDraft


class SharedBlockListResponse(BaseModel):
    items: list[SharedBlockItemResponse]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")

    model_config = ConfigDict(populate_by_name=True)
