from app.schemas.backtest import (
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestSummary,
    BacktestTrade,
    EquityPoint,
)


def run_mock_backtest(request: BacktestRunRequest) -> BacktestRunResponse:
    initial_cash = request.config.initialCash
    ending_equity = round(initial_cash * 1.073, 2)
    base_price = 10.2 if request.config.market == "A_SHARE" else 186.4
    quantity = max(1, int(initial_cash * 0.2 / base_price))

    trades = [
        BacktestTrade(
            time=f"{request.config.startDate} 10:30",
            side="BUY",
            price=base_price,
            quantity=quantity,
            reason="买入积木触发",
        ),
        BacktestTrade(
            time=f"{request.config.startDate} 14:10",
            side="SELL",
            price=round(base_price * 1.028, 2),
            quantity=max(1, int(quantity * 0.5)),
            reason="止盈/卖出规则触发",
        ),
        BacktestTrade(
            time=f"{request.config.endDate} 14:55",
            side="SELL",
            price=round(base_price * 1.073, 2),
            quantity=max(1, int(quantity * 0.5)),
            reason="回测结束清仓",
        ),
    ]

    equity_curve = [
        EquityPoint(time=request.config.startDate, equity=initial_cash),
        EquityPoint(time="区间25%", equity=round(initial_cash * 1.018, 2)),
        EquityPoint(time="区间50%", equity=round(initial_cash * 1.045, 2)),
        EquityPoint(time=request.config.endDate, equity=ending_equity),
    ]

    return BacktestRunResponse(
        runId=f"mock-{request.config.symbol}-{request.config.timeframe}",
        status="COMPLETED",
        config=request.config,
        summary=BacktestSummary(
            totalReturnPercent=7.3,
            maxDrawdownPercent=2.8,
            winRatePercent=66.7,
            endingEquity=ending_equity,
            tradeCount=len(trades),
        ),
        trades=trades,
        equityCurve=equity_curve,
    )
