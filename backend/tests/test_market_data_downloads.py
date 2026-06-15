import pytest
from sqlalchemy import select

from app.api import market_data as market_data_api
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
        {"startDate": "2025-03-03", "endDate": "2025-03-31"}
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

    response = prepare_market_data(
        db_session,
        _market_data_request(startDate="2025-03-03", endDate="2025-03-03"),
        source_provider=SourceProvider(),
    )

    assert response.ready is True
    assert response.downloadedRows == 1
    assert response.failedRanges == []
    assert db_session.scalar(select(MarketKlineCache).where(MarketKlineCache.symbol == "000001.SZ"))
    saved_range = db_session.scalar(select(MarketDataDownloadRange))
    assert saved_range is not None
    assert saved_range.status == "completed"
    assert saved_range.start_date == "2025-03-03"
    assert saved_range.end_date == "2025-03-03"
    assert saved_range.row_count == 1


def test_prepare_market_data_treats_weekend_boundaries_as_ready_after_weekday_candles(
    db_session,
):
    class WeekdayProvider:
        def get_intraday_candles(self, config):
            assert config.startDate == "2025-03-03"
            assert config.endDate == "2025-03-07"
            return [
                MarketCandle(
                    time=f"2025-03-0{day} 09:35",
                    open=10.0,
                    high=10.3,
                    low=9.9,
                    close=10.2,
                    volume=1200,
                )
                for day in range(3, 8)
            ]

    request = _market_data_request(startDate="2025-03-01", endDate="2025-03-09")
    response = prepare_market_data(db_session, request, source_provider=WeekdayProvider())
    coverage = get_market_data_coverage(db_session, request)

    assert response.ready is True
    assert response.missingRanges == []
    assert response.failedRanges == []
    assert coverage.ready is True
    assert coverage.missingRanges == []


def test_prepare_market_data_keeps_missing_weekday_gaps(db_session):
    class WeekdayHoleProvider:
        def get_intraday_candles(self, config):
            assert config.startDate == "2025-03-03"
            assert config.endDate == "2025-03-07"
            return [
                MarketCandle(
                    time="2025-03-03 09:35",
                    open=10.0,
                    high=10.3,
                    low=9.9,
                    close=10.2,
                    volume=1200,
                ),
                MarketCandle(
                    time="2025-03-07 09:35",
                    open=10.2,
                    high=10.4,
                    low=10.1,
                    close=10.3,
                    volume=1500,
                ),
            ]

    request = _market_data_request(startDate="2025-03-01", endDate="2025-03-09")
    response = prepare_market_data(db_session, request, source_provider=WeekdayHoleProvider())
    coverage = get_market_data_coverage(db_session, request)

    assert response.ready is False
    assert [item.model_dump() for item in response.missingRanges] == [
        {"startDate": "2025-03-04", "endDate": "2025-03-06"}
    ]
    assert response.failedRanges == []
    assert coverage.ready is False
    assert [item.model_dump() for item in coverage.missingRanges] == [
        {"startDate": "2025-03-04", "endDate": "2025-03-06"}
    ]
    saved_ranges = db_session.scalars(
        select(MarketDataDownloadRange).order_by(MarketDataDownloadRange.start_date)
    ).all()
    assert [(range_.start_date, range_.end_date, range_.row_count) for range_ in saved_ranges] == [
        ("2025-03-03", "2025-03-03", 1),
        ("2025-03-07", "2025-03-07", 1),
    ]


def test_prepare_market_data_ignores_a_share_spring_festival_gap(db_session):
    class FestivalProvider:
        def get_intraday_candles(self, config):
            assert config.startDate == "2026-02-13"
            assert config.endDate == "2026-02-24"
            return [
                MarketCandle(
                    time="2026-02-13 09:35",
                    open=10.0,
                    high=10.2,
                    low=9.9,
                    close=10.1,
                    volume=1000,
                ),
                MarketCandle(
                    time="2026-02-24 09:35",
                    open=10.1,
                    high=10.3,
                    low=10.0,
                    close=10.2,
                    volume=1000,
                ),
            ]

    request = _market_data_request(startDate="2026-02-13", endDate="2026-02-24")
    response = prepare_market_data(db_session, request, source_provider=FestivalProvider())
    coverage = get_market_data_coverage(db_session, request)

    assert response.ready is True
    assert response.missingRanges == []
    assert coverage.ready is True
    assert coverage.missingRanges == []


def test_coverage_ignores_us_stock_good_friday(db_session):
    db_session.add(
        MarketDataDownloadRange(
            market="US_STOCK",
            symbol="AAPL",
            timeframe="5m",
            start_date="2026-04-06",
            end_date="2026-04-06",
            status="completed",
            row_count=78,
            source="LIVE",
        )
    )
    db_session.commit()

    coverage = get_market_data_coverage(
        db_session,
        _market_data_request(
            market="US_STOCK",
            symbol="AAPL",
            startDate="2026-04-03",
            endDate="2026-04-06",
        ),
    )

    assert coverage.ready is True
    assert coverage.missingRanges == []
    assert coverage.estimatedRows == 0


def test_prepare_market_data_records_empty_result_as_failed_range(db_session):
    class EmptyProvider:
        def get_intraday_candles(self, config):
            return []

    response = prepare_market_data(db_session, _market_data_request(), source_provider=EmptyProvider())

    assert response.ready is False
    assert response.message == "部分行情下载失败，请重试失败区间"
    assert response.downloadedRows == 0
    assert [item.model_dump() for item in response.failedRanges] == [
        {"startDate": "2025-03-03", "endDate": "2025-03-31"}
    ]
    failed_range = db_session.scalar(select(MarketDataDownloadRange))
    assert failed_range is not None
    assert failed_range.status == "failed"


def test_prepare_market_data_records_partial_actual_covered_range(db_session):
    class PartialProvider:
        def get_intraday_candles(self, config):
            return [
                MarketCandle(
                    time="2025-03-03 09:35",
                    open=10.0,
                    high=10.3,
                    low=9.9,
                    close=10.2,
                    volume=1200,
                )
            ]

    response = prepare_market_data(db_session, _market_data_request(), source_provider=PartialProvider())

    assert response.ready is False
    assert response.downloadedRows == 1
    assert response.failedRanges == []
    saved_range = db_session.scalar(select(MarketDataDownloadRange))
    assert saved_range is not None
    assert saved_range.status == "completed"
    assert saved_range.start_date == "2025-03-03"
    assert saved_range.end_date == "2025-03-03"
    assert saved_range.row_count == 1
    assert [item.model_dump() for item in response.missingRanges] == [
        {"startDate": "2025-03-04", "endDate": "2025-03-31"},
    ]


def test_prepare_market_data_splits_discontinuous_covered_ranges(db_session):
    class DiscontinuousProvider:
        def get_intraday_candles(self, config):
            return [
                MarketCandle(
                    time="2025-03-03 09:35",
                    open=10.0,
                    high=10.3,
                    low=9.9,
                    close=10.2,
                    volume=1200,
                ),
                MarketCandle(
                    time="2025-03-31 09:35",
                    open=10.2,
                    high=10.4,
                    low=10.1,
                    close=10.3,
                    volume=1500,
                ),
            ]

    response = prepare_market_data(
        db_session,
        _market_data_request(),
        source_provider=DiscontinuousProvider(),
    )

    assert response.ready is False
    assert response.downloadedRows == 2
    assert response.failedRanges == []
    saved_ranges = db_session.scalars(
        select(MarketDataDownloadRange).order_by(MarketDataDownloadRange.start_date)
    ).all()
    assert [(range_.start_date, range_.end_date, range_.row_count) for range_ in saved_ranges] == [
        ("2025-03-03", "2025-03-03", 1),
        ("2025-03-31", "2025-03-31", 1),
    ]
    cached_candles = db_session.scalars(
        select(MarketKlineCache).order_by(MarketKlineCache.candle_time)
    ).all()
    assert [candle.candle_time for candle in cached_candles] == [
        "2025-03-03 09:35",
        "2025-03-31 09:35",
    ]
    assert [item.model_dump() for item in response.missingRanges] == [
        {"startDate": "2025-03-04", "endDate": "2025-03-28"},
    ]


def test_prepare_market_data_records_mixed_out_of_range_result_as_failed_range(db_session):
    class MixedProvider:
        def get_intraday_candles(self, config):
            return [
                MarketCandle(
                    time="2025-03-03 09:35",
                    open=10.0,
                    high=10.3,
                    low=9.9,
                    close=10.2,
                    volume=1200,
                ),
                MarketCandle(
                    time="2025-04-01 09:35",
                    open=10.2,
                    high=10.4,
                    low=10.1,
                    close=10.3,
                    volume=1500,
                ),
            ]

    response = prepare_market_data(db_session, _market_data_request(), source_provider=MixedProvider())

    assert response.ready is False
    assert response.message == "部分行情下载失败，请重试失败区间"
    assert response.downloadedRows == 0
    assert [item.model_dump() for item in response.failedRanges] == [
        {"startDate": "2025-03-03", "endDate": "2025-03-31"}
    ]
    failed_range = db_session.scalar(select(MarketDataDownloadRange))
    assert failed_range is not None
    assert failed_range.status == "failed"


def test_prepare_market_data_records_unparseable_time_result_as_failed_range(db_session):
    class BadTimeProvider:
        def get_intraday_candles(self, config):
            return [
                MarketCandle(
                    time="not-a-date 09:35",
                    open=10.0,
                    high=10.3,
                    low=9.9,
                    close=10.2,
                    volume=1200,
                )
            ]

    response = prepare_market_data(db_session, _market_data_request(), source_provider=BadTimeProvider())

    assert response.ready is False
    assert response.message == "部分行情下载失败，请重试失败区间"
    assert response.downloadedRows == 0
    assert [item.model_dump() for item in response.failedRanges] == [
        {"startDate": "2025-03-03", "endDate": "2025-03-31"}
    ]
    failed_range = db_session.scalar(select(MarketDataDownloadRange))
    assert failed_range is not None
    assert failed_range.status == "failed"


def test_prepare_market_data_records_failed_range_without_claiming_ready(db_session):
    class BrokenProvider:
        def get_intraday_candles(self, config):
            raise MarketDataUnavailableError("network failed")

    response = prepare_market_data(db_session, _market_data_request(), source_provider=BrokenProvider())

    assert response.ready is False
    assert response.downloadedRows == 0
    assert [item.model_dump() for item in response.failedRanges] == [
        {"startDate": "2025-03-03", "endDate": "2025-03-31"}
    ]
    failed_range = db_session.scalar(select(MarketDataDownloadRange))
    assert failed_range is not None
    assert failed_range.status == "failed"
    assert "network failed" in (failed_range.error_message or "")


def test_prepare_market_data_records_generic_failure_and_returns_partial_failure_message(db_session):
    class BrokenProvider:
        def get_intraday_candles(self, config):
            raise RuntimeError("boom")

    response = prepare_market_data(db_session, _market_data_request(), source_provider=BrokenProvider())

    assert response.ready is False
    assert response.message == "部分行情下载失败，请重试失败区间"
    assert response.downloadedRows == 0
    assert [item.model_dump() for item in response.failedRanges] == [
        {"startDate": "2025-03-03", "endDate": "2025-03-31"}
    ]
    failed_range = db_session.scalar(select(MarketDataDownloadRange))
    assert failed_range is not None
    assert failed_range.status == "failed"
    assert "boom" in (failed_range.error_message or "")


def test_market_data_request_rejects_invalid_market_with_chinese_message():
    with pytest.raises(ValueError) as exc_info:
        _market_data_request(market="CRYPTO")

    assert "市场只支持" in str(exc_info.value)


def test_market_data_request_rejects_invalid_timeframe_with_chinese_message():
    with pytest.raises(ValueError) as exc_info:
        _market_data_request(timeframe="15m")

    assert "K线周期只支持" in str(exc_info.value)


def test_market_data_request_rejects_range_longer_than_thirteen_months():
    with pytest.raises(ValueError):
        _market_data_request(startDate="2025-01-01", endDate="2026-06-15")


def test_market_data_request_rejects_inclusive_398_day_range():
    with pytest.raises(ValueError):
        _market_data_request(startDate="2025-01-01", endDate="2026-02-02")


def test_market_data_coverage_endpoint_returns_missing_range(client):
    response = client.post(
        "/api/market-data/coverage",
        json={
            "market": "A_SHARE",
            "symbol": "000001.SZ",
            "timeframe": "5m",
            "startDate": "2025-03-01",
            "endDate": "2025-03-31",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["missingRanges"] == [{"startDate": "2025-03-03", "endDate": "2025-03-31"}]
    assert "本地缺少 000001.SZ 的 5分钟K线" in payload["message"]


def test_market_data_prepare_endpoint_downloads_and_returns_ready(client, monkeypatch):
    class SourceProvider:
        def get_intraday_candles(self, config):
            return [
                MarketCandle(
                    time=f"{config.startDate} 09:35",
                    open=10,
                    high=10.2,
                    low=9.9,
                    close=10.1,
                    volume=1000,
                )
            ]

    monkeypatch.setattr(market_data_api, "DefaultMarketDataProvider", lambda: SourceProvider())

    response = client.post(
        "/api/market-data/prepare",
        json={
            "market": "A_SHARE",
            "symbol": "000001.SZ",
            "timeframe": "5m",
            "startDate": "2025-03-03",
            "endDate": "2025-03-03",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["downloadedRows"] > 0
    assert payload["failedRanges"] == []
