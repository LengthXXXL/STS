from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.backtest import StrategyDraft


class CustomBlockExposedParamOption(BaseModel):
    label: str = Field(min_length=1, max_length=40)
    value: str = Field(min_length=1, max_length=80)


class CustomBlockExposedParam(BaseModel):
    id: str = Field(min_length=1, max_length=140)
    node_id: str = Field(alias="nodeId", min_length=1, max_length=120)
    param_key: str = Field(alias="paramKey", min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=80)
    node_label: str = Field(alias="nodeLabel", min_length=1, max_length=80)
    type: Literal["text", "number", "select"]
    default_value: str = Field(alias="defaultValue", max_length=120)
    suffix: str | None = Field(default=None, max_length=12)
    min: str | None = Field(default=None, max_length=40)
    max: str | None = Field(default=None, max_length=40)
    step: str | None = Field(default=None, max_length=40)
    options: list[CustomBlockExposedParamOption] = Field(default_factory=list, max_length=20)

    model_config = ConfigDict(populate_by_name=True)


class CustomBlockBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    category: str = Field(min_length=1, max_length=40)
    tags: list[str] = Field(default_factory=list, max_length=12)
    template: StrategyDraft
    exposed_params: list[CustomBlockExposedParam] = Field(
        default_factory=list,
        alias="exposedParams",
        max_length=24,
    )

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
