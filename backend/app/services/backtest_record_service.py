from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.backtest import BacktestEquityPointRecord, BacktestTask, BacktestTradeRecord
from app.models.user import User
from app.schemas.backtest import (
    BacktestRecordDetailResponse,
    BacktestRecordListItem,
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestSummary,
    BacktestTrade,
    EquityPoint,
)


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


def list_backtest_records(
    db: Session,
    owner: User,
    *,
    keyword: str = "",
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[BacktestRecordListItem], int]:
    statement = _owned_backtest_statement(owner)
    keyword = keyword.strip()
    if keyword:
        statement = statement.where(
            or_(
                BacktestTask.symbol.like(f"%{keyword}%"),
                BacktestTask.market.like(f"%{keyword}%"),
                BacktestTask.timeframe.like(f"%{keyword}%"),
            )
        )

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    records = db.scalars(
        statement.order_by(BacktestTask.created_at.desc(), BacktestTask.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [_task_to_list_item(record) for record in records], total


def get_backtest_record(
    db: Session,
    owner: User,
    task_id: int,
) -> BacktestRecordDetailResponse | None:
    task = db.scalar(_owned_backtest_statement(owner).where(BacktestTask.id == task_id))
    if task is None:
        return None

    return BacktestRecordDetailResponse(
        **_task_to_list_item(task).model_dump(by_alias=True),
        strategy=task.strategy,
        config=task.config,
        summary=BacktestSummary(
            totalReturnPercent=task.total_return_percent,
            maxDrawdownPercent=task.max_drawdown_percent,
            winRatePercent=task.win_rate_percent,
            endingEquity=task.ending_equity,
            tradeCount=task.trade_count,
        ),
        trades=[
            BacktestTrade(
                time=trade.trade_time,
                side=trade.side,
                price=trade.price,
                quantity=trade.quantity,
                reason=trade.reason,
            )
            for trade in task.trades
        ],
        equityCurve=[
            EquityPoint(time=point.point_time, equity=point.equity)
            for point in task.equity_points
        ],
    )


def _owned_backtest_statement(owner: User) -> Select[tuple[BacktestTask]]:
    return select(BacktestTask).where(BacktestTask.owner_id == owner.id)


def _task_to_list_item(task: BacktestTask) -> BacktestRecordListItem:
    return BacktestRecordListItem(
        id=task.id,
        runId=task.run_id,
        status=task.status,
        market=task.market,
        symbol=task.symbol,
        timeframe=task.timeframe,
        startDate=task.start_date,
        endDate=task.end_date,
        totalReturnPercent=task.total_return_percent,
        maxDrawdownPercent=task.max_drawdown_percent,
        winRatePercent=task.win_rate_percent,
        endingEquity=task.ending_equity,
        tradeCount=task.trade_count,
        createdAt=task.created_at.isoformat(),
    )
