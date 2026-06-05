from app.schemas.backtest import BacktestConfig
from app.services.market_data_service import LocalMarketDataProvider


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
