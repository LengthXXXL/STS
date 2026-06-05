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
    volume: float = 0


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
                volume=1000 + index * 120,
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
        quote = quote_sets[0] if quote_sets else {}
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []

        candles = [
            MarketCandle(
                time=datetime.fromtimestamp(timestamp, timezone.utc)
                .astimezone(exchange_timezone)
                .strftime("%Y-%m-%d %H:%M"),
                close=round(float(close), 4),
                volume=_safe_float_at(volumes, index),
            )
            for index, (timestamp, close) in enumerate(zip(timestamps, closes, strict=False))
            if close is not None
        ]
        if not candles:
            raise MarketDataUnavailableError("Yahoo response contains no usable candles")
        return candles


class EastMoneyMarketDataProvider:
    base_url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

    def __init__(self, fetch_json: Callable[[str], dict[str, Any]] | None = None):
        self.fetch_json = fetch_json or _fetch_eastmoney_json

    def get_intraday_candles(self, config: BacktestConfig) -> list[MarketCandle]:
        if config.market != "A_SHARE":
            raise MarketDataUnavailableError("EastMoney provider only supports A-shares")

        try:
            payload = self.fetch_json(self._build_url(config))
        except Exception as exc:
            raise MarketDataUnavailableError("EastMoney request failed") from exc
        return self._parse_response(payload)

    def _build_url(self, config: BacktestConfig) -> str:
        query = urlencode(
            {
                "secid": _eastmoney_secid(config.symbol),
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56",
                "klt": _eastmoney_timeframe(config.timeframe),
                "fqt": "1",
                "beg": _compact_date(config.startDate),
                "end": _compact_date(config.endDate),
            }
        )
        return f"{self.base_url}?{query}"

    def _parse_response(self, payload: dict[str, Any]) -> list[MarketCandle]:
        data = payload.get("data") if isinstance(payload, dict) else None
        klines = data.get("klines") if isinstance(data, dict) else None
        if not klines:
            raise MarketDataUnavailableError("EastMoney response contains no klines")

        candles: list[MarketCandle] = []
        for raw_kline in klines:
            parts = raw_kline.split(",")
            if len(parts) < 3:
                continue
            try:
                candles.append(
                    MarketCandle(
                        time=parts[0],
                        close=round(float(parts[2]), 4),
                        volume=float(parts[5]) if len(parts) > 5 else 0,
                    )
                )
            except ValueError:
                continue

        if not candles:
            raise MarketDataUnavailableError("EastMoney response contains no usable candles")
        return candles


class DefaultMarketDataProvider:
    def __init__(
        self,
        yahoo_provider: MarketDataProvider | None = None,
        eastmoney_provider: MarketDataProvider | None = None,
        fallback_provider: MarketDataProvider | None = None,
    ):
        self.yahoo_provider = yahoo_provider or YahooChartMarketDataProvider()
        self.eastmoney_provider = eastmoney_provider or EastMoneyMarketDataProvider()
        self.fallback_provider = fallback_provider or LocalMarketDataProvider()

    def get_intraday_candles(self, config: BacktestConfig) -> list[MarketCandle]:
        if config.market == "US_STOCK":
            try:
                return self.yahoo_provider.get_intraday_candles(config)
            except MarketDataUnavailableError:
                return self.fallback_provider.get_intraday_candles(config)

        if config.market == "A_SHARE":
            try:
                return self.eastmoney_provider.get_intraday_candles(config)
            except MarketDataUnavailableError:
                return self.fallback_provider.get_intraday_candles(config)

        return self.fallback_provider.get_intraday_candles(config)


def _fetch_json(url: str, extra_headers: dict[str, str] | None = None) -> dict[str, Any]:
    context = ssl.create_default_context(cafile=certifi.where())
    headers = {
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        ),
    }
    headers.update(extra_headers or {})
    request = Request(
        url,
        headers=headers,
    )
    with urlopen(request, timeout=8, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_eastmoney_json(url: str) -> dict[str, Any]:
    return _fetch_json(
        url,
        extra_headers={
            "Accept": "*/*",
            "Referer": "https://quote.eastmoney.com/",
        },
    )


def _start_of_day_timestamp(date_value: str) -> int:
    return int(datetime.fromisoformat(date_value).replace(tzinfo=timezone.utc).timestamp())


def _eastmoney_secid(symbol: str) -> str:
    code = symbol.split(".")[0]
    suffix = symbol.split(".")[1].upper() if "." in symbol else ""
    if suffix == "SH" or (not suffix and code.startswith(("5", "6", "9"))):
        return f"1.{code}"
    return f"0.{code}"


def _eastmoney_timeframe(timeframe: str) -> str:
    return "1" if timeframe == "1m" else "5"


def _compact_date(date_value: str) -> str:
    return date_value.replace("-", "")


def _safe_float_at(values: list[Any], index: int) -> float:
    if index >= len(values) or values[index] is None:
        return 0
    try:
        return float(values[index])
    except (TypeError, ValueError):
        return 0


def _zoneinfo_or_utc(timezone_name: str | None):
    if not timezone_name:
        return timezone.utc
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return timezone.utc
