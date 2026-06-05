from sqlalchemy.orm import Session

from app.models.backtest import BacktestEquityPointRecord, BacktestTask, BacktestTradeRecord
from app.models.user import User
from app.schemas.backtest import BacktestRunRequest, BacktestRunResponse


def save_backtest_result(
    db: Session,
    request: BacktestRunRequest,
    result: BacktestRunResponse,
    owner: User | None = None,
) -> BacktestTask:
    task = BacktestTask(
        owner_id=owner.id if owner else None,
        run_id=result.runId,
        status=result.status,
        market=request.config.market,
        symbol=request.config.symbol.strip().upper(),
        timeframe=request.config.timeframe,
        start_date=request.config.startDate,
        end_date=request.config.endDate,
        initial_cash=request.config.initialCash,
        total_return_percent=result.summary.totalReturnPercent,
        max_drawdown_percent=result.summary.maxDrawdownPercent,
        win_rate_percent=result.summary.winRatePercent,
        ending_equity=result.summary.endingEquity,
        trade_count=result.summary.tradeCount,
        strategy=request.strategy.model_dump(by_alias=True),
        config=request.config.model_dump(by_alias=True),
    )
    db.add(task)
    db.flush()

    for sequence, trade in enumerate(result.trades):
        db.add(
            BacktestTradeRecord(
                task_id=task.id,
                sequence=sequence,
                trade_time=trade.time,
                side=trade.side,
                price=trade.price,
                quantity=trade.quantity,
                reason=trade.reason,
            )
        )

    for sequence, point in enumerate(result.equityCurve):
        db.add(
            BacktestEquityPointRecord(
                task_id=task.id,
                sequence=sequence,
                point_time=point.time,
                equity=point.equity,
            )
        )

    db.commit()
    db.refresh(task)
    return task
