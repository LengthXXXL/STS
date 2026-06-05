from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
    simulationAccountId: int | None = Field(default=None, ge=1)


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


class BacktestRecordListItem(BaseModel):
    id: int
    run_id: str = Field(alias="runId")
    status: str
    market: str
    symbol: str
    timeframe: str
    start_date: str = Field(alias="startDate")
    end_date: str = Field(alias="endDate")
    total_return_percent: float = Field(alias="totalReturnPercent")
    max_drawdown_percent: float = Field(alias="maxDrawdownPercent")
    win_rate_percent: float = Field(alias="winRatePercent")
    ending_equity: float = Field(alias="endingEquity")
    trade_count: int = Field(alias="tradeCount")
    created_at: str = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


class BacktestRecordListResponse(BaseModel):
    items: list[BacktestRecordListItem]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")

    model_config = ConfigDict(populate_by_name=True)


class BacktestRecordDetailResponse(BacktestRecordListItem):
    strategy: StrategyDraft
    config: BacktestConfig
    summary: BacktestSummary
    trades: list[BacktestTrade]
    equityCurve: list[EquityPoint]
