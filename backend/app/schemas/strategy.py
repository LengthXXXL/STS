from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.backtest import BacktestConfig, StrategyDraft


class StrategyBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    strategy: StrategyDraft
    backtest_config: BacktestConfig | None = Field(default=None, alias="backtestConfig")

    model_config = ConfigDict(populate_by_name=True)


class StrategyCreate(StrategyBase):
    pass


class StrategyUpdate(StrategyBase):
    pass


class StrategyResponse(StrategyBase):
    id: int
    owner_id: int = Field(alias="ownerId")
    is_public: bool = Field(alias="isPublic")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class StrategyListResponse(BaseModel):
    items: list[StrategyResponse]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")

    model_config = ConfigDict(populate_by_name=True)
