from typing import Literal

from pydantic import BaseModel, Field


class StrategyNode(BaseModel):
    id: str
    type: str
    label: str
    x: float
    y: float
    params: dict[str, str]


class StrategyEdge(BaseModel):
    id: str
    from_: str = Field(alias="from")
    to: str


class StrategyViewport(BaseModel):
    x: float
    y: float
    scale: float


class StrategyDraft(BaseModel):
    version: int
    nodes: list[StrategyNode]
    edges: list[StrategyEdge]
    viewport: StrategyViewport


class BacktestConfig(BaseModel):
    market: Literal["A_SHARE", "US_STOCK"]
    symbol: str
    timeframe: Literal["5m", "1m"]
    startDate: str
    endDate: str
    initialCash: float = Field(gt=0)


class BacktestRunRequest(BaseModel):
    strategy: StrategyDraft
    config: BacktestConfig


class BacktestSummary(BaseModel):
    totalReturnPercent: float
    maxDrawdownPercent: float
    winRatePercent: float
    endingEquity: float
    tradeCount: int


class BacktestTrade(BaseModel):
    time: str
    side: Literal["BUY", "SELL"]
    price: float
    quantity: int
    reason: str


class EquityPoint(BaseModel):
    time: str
    equity: float


class BacktestRunResponse(BaseModel):
    runId: str
    status: Literal["COMPLETED"]
    config: BacktestConfig
    summary: BacktestSummary
    trades: list[BacktestTrade]
    equityCurve: list[EquityPoint]
