from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MarketCode = Literal["A_SHARE", "US_STOCK"]


class MarketSession(BaseModel):
    label: str
    start: str
    end: str


class MarketCostProfile(BaseModel):
    commission_bps: float = Field(alias="commissionBps")
    min_commission: float = Field(alias="minCommission")
    slippage_bps: float = Field(alias="slippageBps")
    buy_fee_bps: float = Field(alias="buyFeeBps")
    sell_fee_bps: float = Field(alias="sellFeeBps")
    sell_tax_bps: float = Field(alias="sellTaxBps")
    sec_fee_per_million: float | None = Field(default=None, alias="secFeePerMillion")
    per_share_sell_fee: float | None = Field(default=None, alias="perShareSellFee")
    max_per_share_sell_fee: float | None = Field(default=None, alias="maxPerShareSellFee")

    model_config = ConfigDict(populate_by_name=True)


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
    cost_profile: MarketCostProfile = Field(alias="costProfile")
    sessions: list[MarketSession]
    notes: list[str]

    model_config = ConfigDict(populate_by_name=True)


class MarketRuleListResponse(BaseModel):
    items: list[MarketRuleResponse]
