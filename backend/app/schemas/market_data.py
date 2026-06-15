from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class MarketDataRange(BaseModel):
    startDate: str
    endDate: str


class MarketDataRequest(BaseModel):
    market: Literal["A_SHARE", "US_STOCK"]
    symbol: str
    timeframe: Literal["5m", "1m"]
    startDate: str
    endDate: str

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("股票代码不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_date_range(self):
        start = date.fromisoformat(self.startDate)
        end = date.fromisoformat(self.endDate)
        if start > end:
            raise ValueError("开始日期不能晚于结束日期")
        if (end - start).days > 397:
            raise ValueError("单次回测仅支持 1 只股票，时间范围最长 13 个月")
        return self


class MarketDataCoverageResponse(BaseModel):
    ready: bool
    missingRanges: list[MarketDataRange]
    estimatedRows: int = Field(ge=0)
    estimatedSeconds: int = Field(ge=0)
    message: str


class MarketDataPrepareResponse(MarketDataCoverageResponse):
    downloadedRows: int = Field(ge=0)
    failedRanges: list[MarketDataRange]
