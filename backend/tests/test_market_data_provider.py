import pytest
from sqlalchemy import select

from app import models
from app.schemas.backtest import BacktestConfig
from app.services import market_data_service
from app.services.market_data_service import (
    DefaultMarketDataProvider,
    EastMoneyMarketDataProvider,
    LocalMarketDataProvider,
    MarketCandle,
    MarketDataUnavailableError,
    YahooChartMarketDataProvider,
    _fetch_eastmoney_json,
    _fetch_json,
)


def _config(**overrides):
    payload = {
        "market": "A_SHARE",
        "symbol": "000001.SZ",
        "timeframe": "5m",
        "startDate": "2026-01-01",
        "endDate": "2026-01-02",
        "initialCash": 100000,
    }
    payload.update(overrides)
    return BacktestConfig.model_validate(payload)


def test_local_provider_returns_valid_five_minute_candles_for_config():
    provider = LocalMarketDataProvider()

    candles = provider.get_intraday_candles(_config())

    assert len(candles) == 6
    assert candles[0].time == "2026-01-01 09:35"
    assert candles[-1].time == "2026-01-01 10:00"
    assert all(candle.close > 0 for candle in candles)


def test_local_provider_uses_market_and_timeframe_to_shape_candles():
    provider = LocalMarketDataProvider()

    a_share_candles = provider.get_intraday_candles(_config(market="A_SHARE", timeframe="5m"))
    us_stock_candles = provider.get_intraday_candles(_config(market="US_STOCK", timeframe="1m"))

    assert a_share_candles[0].close != us_stock_candles[0].close
    assert us_stock_candles[0].time == "2026-01-01 09:31"
    assert us_stock_candles[-1].time == "2026-01-01 09:36"


def test_yahoo_provider_parses_chart_response_into_candles():
    requested_urls = []

    def fetch_json(url):
        requested_urls.append(url)
        return {
            "chart": {
                "result": [
                    {
                        "meta": {"exchangeTimezoneName": "America/New_York"},
                        "timestamp": [1767277800, 1767278100, 1767278400],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [186.9, None, 188.0],
                                    "high": [187.5, None, 189.0],
                                    "low": [186.5, None, 187.8],
                                    "close": [187.125, None, 188.45678],
                                    "volume": [12000, None, 18000],
                                }
                            ]
                        },
                    }
                ],
                "error": None,
            }
        }

    provider = YahooChartMarketDataProvider(fetch_json=fetch_json)

    candles = provider.get_intraday_candles(_config(market="US_STOCK", symbol="AAPL"))

    assert "AAPL" in requested_urls[0]
    assert "interval=5m" in requested_urls[0]
    assert "period1=" in requested_urls[0]
    assert "period2=" in requested_urls[0]
    assert candles == [
        MarketCandle(
            time="2026-01-01 09:30",
            open=186.9,
            high=187.5,
            low=186.5,
            close=187.125,
            volume=12000,
        ),
        MarketCandle(
            time="2026-01-01 09:40",
            open=188.0,
            high=189.0,
            low=187.8,
            close=188.4568,
            volume=18000,
        ),
    ]


def test_yahoo_provider_rejects_non_us_market():
    provider = YahooChartMarketDataProvider(fetch_json=lambda url: {})

    with pytest.raises(MarketDataUnavailableError):
        provider.get_intraday_candles(_config(market="A_SHARE"))


def test_yahoo_provider_wraps_fetch_errors_as_unavailable():
    def fetch_json(url):
        raise OSError("network down")

    provider = YahooChartMarketDataProvider(fetch_json=fetch_json)

    with pytest.raises(MarketDataUnavailableError):
        provider.get_intraday_candles(_config(market="US_STOCK", symbol="AAPL"))


def test_eastmoney_provider_maps_a_share_symbol_and_parses_klines():
    requested_urls = []

    def fetch_json(url):
        requested_urls.append(url)
        return {
            "data": {
                "klines": [
                    "2026-01-01 09:35,10.10,10.25,10.30,10.00,1200",
                    "2026-01-01 09:40,10.25,10.45678,10.50,10.20,1500",
                ]
            }
        }

    provider = EastMoneyMarketDataProvider(fetch_json=fetch_json)

    candles = provider.get_intraday_candles(
        _config(market="A_SHARE", symbol="000001.SZ", timeframe="5m")
    )

    assert requested_urls[0].startswith("http://push2his.eastmoney.com/")
    assert "secid=0.000001" in requested_urls[0]
    assert "klt=5" in requested_urls[0]
    assert "beg=20260101" in requested_urls[0]
    assert "end=20260102" in requested_urls[0]
    assert candles == [
        MarketCandle(
            time="2026-01-01 09:35",
            open=10.10,
            high=10.30,
            low=10.00,
            close=10.25,
            volume=1200,
        ),
        MarketCandle(
            time="2026-01-01 09:40",
            open=10.25,
            high=10.50,
            low=10.20,
            close=10.4568,
            volume=1500,
        ),
    ]


def test_eastmoney_provider_maps_shanghai_symbols():
    requested_urls = []

    def fetch_json(url):
        requested_urls.append(url)
        return {"data": {"klines": ["2026-01-01 09:31,8.10,8.20,8.30,8.00,1200"]}}

    provider = EastMoneyMarketDataProvider(fetch_json=fetch_json)

    provider.get_intraday_candles(_config(market="A_SHARE", symbol="600000.SH", timeframe="1m"))

    assert "secid=1.600000" in requested_urls[0]
    assert "klt=1" in requested_urls[0]


def test_eastmoney_provider_wraps_fetch_errors_as_unavailable():
    def fetch_json(url):
        raise OSError("network down")

    provider = EastMoneyMarketDataProvider(fetch_json=fetch_json)

    with pytest.raises(MarketDataUnavailableError):
        provider.get_intraday_candles(_config(market="A_SHARE", symbol="000001.SZ"))


def test_default_provider_falls_back_when_yahoo_is_unavailable():
    class BrokenProvider:
        def get_intraday_candles(self, config):
            raise MarketDataUnavailableError("network failed")

    class FallbackProvider:
        def __init__(self):
            self.received_config = None

        def get_intraday_candles(self, config):
            self.received_config = config
            return [MarketCandle(time="2026-01-01 09:35", close=10)]

    fallback_provider = FallbackProvider()
    provider = DefaultMarketDataProvider(
        yahoo_provider=BrokenProvider(),
        fallback_provider=fallback_provider,
    )
    config = _config(market="US_STOCK", symbol="AAPL")

    candles = provider.get_intraday_candles(config)

    assert fallback_provider.received_config == config
    assert candles == [MarketCandle(time="2026-01-01 09:35", close=10)]


def test_default_provider_raises_when_primary_source_unavailable_without_explicit_fallback():
    class BrokenProvider:
        def get_intraday_candles(self, config):
            raise MarketDataUnavailableError("network failed")

    provider = DefaultMarketDataProvider(yahoo_provider=BrokenProvider())

    with pytest.raises(MarketDataUnavailableError):
        provider.get_intraday_candles(_config(market="US_STOCK", symbol="AAPL"))


def test_default_provider_uses_eastmoney_for_a_share_before_fallback():
    class EastMoneyProvider:
        def __init__(self):
            self.received_config = None

        def get_intraday_candles(self, config):
            self.received_config = config
            return [MarketCandle(time="2026-01-01 09:35", close=10)]

    eastmoney_provider = EastMoneyProvider()
    provider = DefaultMarketDataProvider(eastmoney_provider=eastmoney_provider)
    config = _config(market="A_SHARE", symbol="000001.SZ")

    candles = provider.get_intraday_candles(config)

    assert eastmoney_provider.received_config == config
    assert candles == [MarketCandle(time="2026-01-01 09:35", close=10)]


def test_cached_provider_persists_and_reuses_intraday_candles(db_session):
    assert hasattr(models, "MarketKlineCache")
    assert hasattr(market_data_service, "CachedMarketDataProvider")

    MarketKlineCache = models.MarketKlineCache
    CachedMarketDataProvider = market_data_service.CachedMarketDataProvider

    class SourceProvider:
        def __init__(self):
            self.calls = 0

        def get_intraday_candles(self, config):
            self.calls += 1
            return [
                MarketCandle(
                    time="2026-01-01 09:35",
                    open=10.1,
                    high=10.3,
                    low=10.0,
                    close=10.25,
                    volume=1200,
                ),
                MarketCandle(
                    time="2026-01-01 09:40",
                    open=10.25,
                    high=10.5,
                    low=10.2,
                    close=10.45,
                    volume=1500,
                ),
            ]

    class FailingProvider:
        def get_intraday_candles(self, config):
            raise AssertionError("cache hit should not fetch source provider")

    config = _config(market="A_SHARE", symbol="000001.SZ", timeframe="5m")
    source_provider = SourceProvider()
    cached_provider = CachedMarketDataProvider(db_session, source_provider=source_provider)

    first_candles = cached_provider.get_intraday_candles(config)

    assert source_provider.calls == 1
    assert first_candles == [
        MarketCandle(
            time="2026-01-01 09:35",
            open=10.1,
            high=10.3,
            low=10.0,
            close=10.25,
            volume=1200,
        ),
        MarketCandle(
            time="2026-01-01 09:40",
            open=10.25,
            high=10.5,
            low=10.2,
            close=10.45,
            volume=1500,
        ),
    ]
    cached_rows = db_session.scalars(select(MarketKlineCache)).all()
    assert [
        (
            row.candle_time,
            row.source,
            row.open_price,
            row.high_price,
            row.low_price,
            row.close,
            row.volume,
        )
        for row in cached_rows
    ] == [
        ("2026-01-01 09:35", "LIVE", 10.1, 10.3, 10.0, 10.25, 1200),
        ("2026-01-01 09:40", "LIVE", 10.25, 10.5, 10.2, 10.45, 1500),
    ]

    cached_again = CachedMarketDataProvider(
        db_session,
        source_provider=FailingProvider(),
    ).get_intraday_candles(config)

    assert cached_again == first_candles


def test_cached_provider_ignores_unknown_source_rows_and_replaces_them(db_session):
    db_session.add(
        models.MarketKlineCache(
            market="A_SHARE",
            symbol="000001.SZ",
            timeframe="5m",
            source="UNKNOWN",
            candle_time="2026-01-01 09:35",
            open_price=9.8,
            high_price=10.0,
            low_price=9.7,
            close=9.9,
            volume=500,
        )
    )
    db_session.commit()

    class SourceProvider:
        def get_intraday_candles(self, config):
            return [
                MarketCandle(
                    time="2026-01-01 09:35",
                    open=10.1,
                    high=10.3,
                    low=10.0,
                    close=10.25,
                    volume=1200,
                )
            ]

    provider = market_data_service.CachedMarketDataProvider(
        db_session,
        source_provider=SourceProvider(),
    )

    candles = provider.get_intraday_candles(_config(market="A_SHARE", symbol="000001.SZ"))

    assert candles == [
        MarketCandle(
            time="2026-01-01 09:35",
            open=10.1,
            high=10.3,
            low=10.0,
            close=10.25,
            volume=1200,
        )
    ]
    rows = db_session.scalars(select(models.MarketKlineCache)).all()
    assert [(row.source, row.close) for row in rows] == [("LIVE", 10.25)]


def test_fetch_json_uses_explicit_ssl_context(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, timeout, context=None):
        captured["request"] = request
        captured["timeout"] = timeout
        captured["context"] = context
        return FakeResponse()

    monkeypatch.setattr("app.services.market_data_service.urlopen", fake_urlopen)

    payload = _fetch_json("https://example.test/chart")

    assert payload == {"ok": True}
    assert captured["request"].full_url == "https://example.test/chart"
    assert "Mozilla" in captured["request"].get_header("User-agent")
    assert captured["request"].get_header("Accept") == "application/json"
    assert captured["timeout"] == 8
    assert captured["context"] is not None


def test_fetch_eastmoney_json_uses_quote_referer(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self):
            return b'{"data": {"klines": []}}'

    def fake_urlopen(request, timeout, context=None):
        captured["request"] = request
        captured["timeout"] = timeout
        captured["context"] = context
        return FakeResponse()

    monkeypatch.setattr("app.services.market_data_service.urlopen", fake_urlopen)

    payload = _fetch_eastmoney_json("https://push2his.eastmoney.com/example")

    assert payload == {"data": {"klines": []}}
    assert captured["request"].get_header("Referer") == "https://quote.eastmoney.com/"
    assert captured["request"].get_header("Accept") == "*/*"
    assert captured["context"] is not None
