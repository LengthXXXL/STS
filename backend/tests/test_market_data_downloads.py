import pytest
from sqlalchemy import select

from app.models import MarketDataDownloadRange, MarketKlineCache
from app.schemas.market_data import MarketDataRequest
from app.services.market_data_download_service import (
    get_market_data_coverage,
    prepare_market_data,
)
from app.services.market_data_service import MarketCandle, MarketDataUnavailableError


def _market_data_request(**overrides):
    payload = {
        "market": "A_SHARE",
        "symbol": "000001.SZ",
        "timeframe": "5m",
        "startDate": "2025-03-01",
        "endDate": "2025-03-31",
    }
    payload.update(overrides)
    return MarketDataRequest.model_validate(payload)


def test_market_data_download_range_model_persists_completed_range(db_session):
    db_session.add(
        MarketDataDownloadRange(
            market="A_SHARE",
            symbol="000001.SZ",
            timeframe="5m",
            start_date="2025-03-01",
            end_date="2025-03-31",
            status="completed",
            row_count=1200,
            source="LIVE",
        )
    )
    db_session.commit()

    saved = db_session.scalar(select(MarketDataDownloadRange))

    assert saved is not None
    assert saved.market == "A_SHARE"
    assert saved.symbol == "000001.SZ"
    assert saved.timeframe == "5m"
    assert saved.start_date == "2025-03-01"
    assert saved.end_date == "2025-03-31"
    assert saved.status == "completed"
    assert saved.row_count == 1200
    assert saved.source == "LIVE"
    assert saved.error_message is None


def test_coverage_reports_missing_range_without_completed_download(db_session):
    coverage = get_market_data_coverage(db_session, _market_data_request())

    assert coverage.ready is False
    assert [item.model_dump() for item in coverage.missingRanges] == [
        {"startDate": "2025-03-01", "endDate": "2025-03-31"}
    ]
    assert coverage.estimatedRows > 0
    assert coverage.estimatedSeconds > 0
    assert "本地缺少 000001.SZ 的 5分钟K线" in coverage.message


def test_coverage_is_ready_when_completed_range_covers_request(db_session):
    db_session.add(
        MarketDataDownloadRange(
            market="A_SHARE",
            symbol="000001.SZ",
            timeframe="5m",
            start_date="2025-03-01",
            end_date="2025-03-31",
            status="completed",
            row_count=1200,
            source="LIVE",
        )
    )
    db_session.commit()

    coverage = get_market_data_coverage(db_session, _market_data_request())

    assert coverage.ready is True
    assert coverage.missingRanges == []
    assert coverage.estimatedRows == 0
    assert coverage.estimatedSeconds == 0
    assert coverage.message == "本地行情已准备完成，可以直接运行回测"


def test_prepare_market_data_downloads_missing_range_and_records_completion(db_session):
    class SourceProvider:
        def get_intraday_candles(self, config):
            assert config.market == "A_SHARE"
            assert config.symbol == "000001.SZ"
            assert config.timeframe == "5m"
            return [
                MarketCandle(
                    time=f"{config.startDate} 09:35",
                    open=10.0,
                    high=10.3,
                    low=9.9,
                    close=10.2,
                    volume=1200,
                )
            ]

    response = prepare_market_data(db_session, _market_data_request(), source_provider=SourceProvider())

    assert response.ready is True
    assert response.downloadedRows == 1
    assert response.failedRanges == []
    assert db_session.scalar(select(MarketKlineCache).where(MarketKlineCache.symbol == "000001.SZ"))
    saved_range = db_session.scalar(select(MarketDataDownloadRange))
    assert saved_range is not None
    assert saved_range.status == "completed"
    assert saved_range.row_count == 1


def test_prepare_market_data_records_failed_range_without_claiming_ready(db_session):
    class BrokenProvider:
        def get_intraday_candles(self, config):
            raise MarketDataUnavailableError("network failed")

    response = prepare_market_data(db_session, _market_data_request(), source_provider=BrokenProvider())

    assert response.ready is False
    assert response.downloadedRows == 0
    assert [item.model_dump() for item in response.failedRanges] == [
        {"startDate": "2025-03-01", "endDate": "2025-03-31"}
    ]
    failed_range = db_session.scalar(select(MarketDataDownloadRange))
    assert failed_range is not None
    assert failed_range.status == "failed"
    assert "network failed" in (failed_range.error_message or "")


def test_market_data_request_rejects_range_longer_than_thirteen_months():
    with pytest.raises(ValueError):
        _market_data_request(startDate="2025-01-01", endDate="2026-06-15")
