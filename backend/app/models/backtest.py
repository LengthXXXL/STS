from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BacktestTask(Base):
    __tablename__ = "backtest_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    run_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    market: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    initial_cash: Mapped[float] = mapped_column(Float, nullable=False)
    total_return_percent: Mapped[float] = mapped_column(Float, nullable=False)
    max_drawdown_percent: Mapped[float] = mapped_column(Float, nullable=False)
    win_rate_percent: Mapped[float] = mapped_column(Float, nullable=False)
    ending_equity: Mapped[float] = mapped_column(Float, nullable=False)
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False)
    strategy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="backtest_tasks")
    trades: Mapped[list["BacktestTradeRecord"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="BacktestTradeRecord.sequence",
    )
    events: Mapped[list["BacktestEventRecord"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="BacktestEventRecord.sequence",
    )
    equity_points: Mapped[list["BacktestEquityPointRecord"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="BacktestEquityPointRecord.sequence",
    )


class BacktestTradeRecord(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("backtest_tasks.id"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    trade_time: Mapped[str] = mapped_column(String(16), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    task = relationship("BacktestTask", back_populates="trades")


class BacktestEventRecord(Base):
    __tablename__ = "backtest_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("backtest_tasks.id"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_time: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    rule: Mapped[str] = mapped_column(String(40), nullable=False)

    task = relationship("BacktestTask", back_populates="events")


class BacktestEquityPointRecord(Base):
    __tablename__ = "backtest_equity_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("backtest_tasks.id"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    point_time: Mapped[str] = mapped_column(String(16), nullable=False)
    equity: Mapped[float] = mapped_column(Float, nullable=False)

    task = relationship("BacktestTask", back_populates="equity_points")
