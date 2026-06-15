from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
        if (end - start).days + 1 > 397:
            raise ValueError("单次回测仅支持 1 只股票，时间范围最长 13 个月")
        return self


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


class BacktestEvent(BaseModel):
    time: str
    event_type: Literal["BLOCKED_ORDER"] = Field(alias="eventType")
    side: Literal["BUY", "SELL"]
    price: float
    quantity: int
    reason: str
    rule: str

    model_config = ConfigDict(populate_by_name=True)


class BacktestTimelineItem(BaseModel):
    id: str
    time: str
    event_type: Literal[
        "TRADE_FILLED",
        "ORDER_BLOCKED",
        "COOLDOWN_STARTED",
        "POSITION_CLOSED",
    ] = Field(alias="eventType")
    title: str
    description: str
    severity: Literal["info", "success", "warning", "danger"]
    side: Literal["BUY", "SELL"] | None = None
    price: float | None = None
    quantity: int | None = None
    rule: str | None = None
    node_id: str | None = Field(default=None, alias="nodeId")
    node_type: str | None = Field(default=None, alias="nodeType")
    node_label: str | None = Field(default=None, alias="nodeLabel")
    details: dict[str, int | float | str | bool] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class EquityPoint(BaseModel):
    time: str
    equity: float


class BacktestRunResponse(BaseModel):
    runId: str
    status: Literal["COMPLETED"]
    config: BacktestConfig
    summary: BacktestSummary
    trades: list[BacktestTrade]
    events: list[BacktestEvent] = Field(default_factory=list)
    timeline: list[BacktestTimelineItem] = Field(default_factory=list)
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
    simulation_account_id: int | None = Field(default=None, alias="simulationAccountId")
    simulation_account_name: str | None = Field(default=None, alias="simulationAccountName")
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
    events: list[BacktestEvent] = Field(default_factory=list)
    timeline: list[BacktestTimelineItem] = Field(default_factory=list)
    equityCurve: list[EquityPoint]
