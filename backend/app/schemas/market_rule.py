from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


MarketCode = Literal["A_SHARE", "US_STOCK"]


class MarketSession(BaseModel):
    label: str
    start: str
    end: str


class MarketRuleResponse(BaseModel):
    market: MarketCode
    market_label: str = Field(alias="marketLabel")
    currency: str
    timezone: str
    settlement_cycle: str = Field(alias="settlementCycle")
    buy_lot_size: int = Field(alias="buyLotSize")
    sell_lot_size: int = Field(alias="sellLotSize")
    min_order_shares: int = Field(alias="minOrderShares")
    supports_intraday_round_trip: bool = Field(alias="supportsIntradayRoundTrip")
    price_limit_percent: float | None = Field(alias="priceLimitPercent")
    sessions: list[MarketSession]
    notes: list[str]

    model_config = ConfigDict(populate_by_name=True)


class MarketRuleListResponse(BaseModel):
    items: list[MarketRuleResponse]
