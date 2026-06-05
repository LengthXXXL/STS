import json
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import certifi

from app.schemas.backtest import BacktestConfig


@dataclass(frozen=True, slots=True)
class MarketCandle:
    time: str
    close: float


class MarketDataProvider(Protocol):
    def get_intraday_candles(self, config: BacktestConfig) -> list[MarketCandle]:
        """Return intraday candles for a configured symbol and date range."""


class MarketDataUnavailableError(RuntimeError):
    pass


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


class YahooChartMarketDataProvider:
    base_url = "https://query1.finance.yahoo.com/v8/finance/chart"

    def __init__(self, fetch_json: Callable[[str], dict[str, Any]] | None = None):
        self.fetch_json = fetch_json or _fetch_json

    def get_intraday_candles(self, config: BacktestConfig) -> list[MarketCandle]:
        if config.market != "US_STOCK":
            raise MarketDataUnavailableError("Yahoo Chart provider only supports US stocks")

        try:
            payload = self.fetch_json(self._build_url(config))
        except Exception as exc:
            raise MarketDataUnavailableError("Yahoo request failed") from exc
        return self._parse_response(payload)

    def _build_url(self, config: BacktestConfig) -> str:
        period1 = _start_of_day_timestamp(config.startDate)
        period2 = _start_of_day_timestamp(config.endDate) + 24 * 60 * 60
        query = urlencode(
            {
                "period1": period1,
                "period2": period2,
                "interval": config.timeframe,
                "includePrePost": "false",
                "events": "history",
            }
        )
        return f"{self.base_url}/{config.symbol}?{query}"

    def _parse_response(self, payload: dict[str, Any]) -> list[MarketCandle]:
        chart = payload.get("chart") if isinstance(payload, dict) else None
        if not isinstance(chart, dict):
            raise MarketDataUnavailableError("Yahoo response is missing chart data")
        if chart.get("error"):
            raise MarketDataUnavailableError("Yahoo returned an error")

        results = chart.get("result")
        if not results:
            raise MarketDataUnavailableError("Yahoo response contains no result")

        result = results[0]
        timezone_name = result.get("meta", {}).get("exchangeTimezoneName")
        exchange_timezone = _zoneinfo_or_utc(timezone_name)
        timestamps = result.get("timestamp") or []
        quote_sets = result.get("indicators", {}).get("quote") or []
        closes = quote_sets[0].get("close") if quote_sets else []

        candles = [
            MarketCandle(
                time=datetime.fromtimestamp(timestamp, timezone.utc)
                .astimezone(exchange_timezone)
                .strftime("%Y-%m-%d %H:%M"),
                close=round(float(close), 4),
            )
            for timestamp, close in zip(timestamps, closes, strict=False)
            if close is not None
        ]
        if not candles:
            raise MarketDataUnavailableError("Yahoo response contains no usable candles")
        return candles


class DefaultMarketDataProvider:
    def __init__(
        self,
        yahoo_provider: MarketDataProvider | None = None,
        fallback_provider: MarketDataProvider | None = None,
    ):
        self.yahoo_provider = yahoo_provider or YahooChartMarketDataProvider()
        self.fallback_provider = fallback_provider or LocalMarketDataProvider()

    def get_intraday_candles(self, config: BacktestConfig) -> list[MarketCandle]:
        if config.market == "US_STOCK":
            try:
                return self.yahoo_provider.get_intraday_candles(config)
            except MarketDataUnavailableError:
                return self.fallback_provider.get_intraday_candles(config)

        return self.fallback_provider.get_intraday_candles(config)


def _fetch_json(url: str) -> dict[str, Any]:
    context = ssl.create_default_context(cafile=certifi.where())
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36"
            ),
        },
    )
    with urlopen(request, timeout=8, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def _start_of_day_timestamp(date_value: str) -> int:
    return int(datetime.fromisoformat(date_value).replace(tzinfo=timezone.utc).timestamp())


def _zoneinfo_or_utc(timezone_name: str | None):
    if not timezone_name:
        return timezone.utc
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return timezone.utc
