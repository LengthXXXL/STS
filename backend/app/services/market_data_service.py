from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from app.schemas.backtest import BacktestConfig


@dataclass(frozen=True, slots=True)
class MarketCandle:
    time: str
    close: float


class MarketDataProvider(Protocol):
    def get_intraday_candles(self, config: BacktestConfig) -> list[MarketCandle]:
        """Return intraday candles for a configured symbol and date range."""


class LocalMarketDataProvider:
    """Deterministic provider used until live A-share/US data adapters are connected."""

    def get_intraday_candles(self, config: BacktestConfig) -> list[MarketCandle]:
        base_price = 10.2 if config.market == "A_SHARE" else 186.4
        minute_step = 1 if config.timeframe == "1m" else 5
        price_factors = [1, 1.025, 0.992, 1.055, 1.038, 1.073]
        session_start = datetime.fromisoformat(f"{config.startDate}T09:30:00")

        return [
            MarketCandle(
                time=(session_start + timedelta(minutes=minute_step * (index + 1))).strftime(
                    "%Y-%m-%d %H:%M"
                ),
                close=round(base_price * factor, 4),
            )
            for index, factor in enumerate(price_factors)
        ]
