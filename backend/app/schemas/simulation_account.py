from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SimulationAccountBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    market: Literal["A_SHARE", "US_STOCK"]
    initial_cash: float = Field(alias="initialCash", gt=0)

    model_config = ConfigDict(populate_by_name=True)


class SimulationAccountCreate(SimulationAccountBase):
    pass


class SimulationAccountUpdate(SimulationAccountBase):
    pass


class SimulationAccountResponse(SimulationAccountBase):
    id: int
    owner_id: int = Field(alias="ownerId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class SimulationAccountListResponse(BaseModel):
    items: list[SimulationAccountResponse]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")

    model_config = ConfigDict(populate_by_name=True)
