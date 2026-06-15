from datetime import date, timedelta
from math import ceil

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MarketDataDownloadRange
from app.schemas.backtest import BacktestConfig
from app.schemas.market_data import (
    MarketDataCoverageResponse,
    MarketDataPrepareResponse,
    MarketDataRange,
    MarketDataRequest,
)
from app.services.market_data_service import (
    LIVE_CACHE_SOURCE,
    CachedMarketDataProvider,
    DefaultMarketDataProvider,
    MarketCandle,
    MarketDataProvider,
    MarketDataUnavailableError,
)

COMPLETED_STATUS = "completed"
FAILED_STATUS = "failed"
MAX_NON_TRADING_GAP_DAYS = 10


def get_market_data_coverage(
    db: Session,
    request: MarketDataRequest,
) -> MarketDataCoverageResponse:
    missing_ranges = _missing_ranges(db, request)
    estimated_rows = _estimate_rows(request.timeframe, missing_ranges)
    estimated_seconds = _estimate_seconds(estimated_rows)
    return MarketDataCoverageResponse(
        ready=not missing_ranges,
        missingRanges=missing_ranges,
        estimatedRows=estimated_rows,
        estimatedSeconds=estimated_seconds,
        message=_coverage_message(request, missing_ranges, estimated_seconds),
    )


def prepare_market_data(
    db: Session,
    request: MarketDataRequest,
    source_provider: MarketDataProvider | None = None,
) -> MarketDataPrepareResponse:
    missing_ranges = _missing_ranges(db, request)
    provider = source_provider or DefaultMarketDataProvider()
    cache_provider = CachedMarketDataProvider(db, source_provider=provider)
    downloaded_rows = 0
    failed_ranges: list[MarketDataRange] = []

    for missing_range in missing_ranges:
        for chunk in _chunk_range(missing_range, request.timeframe):
            config = _backtest_config_for_range(request, chunk)
            try:
                candles = provider.get_intraday_candles(config)
                covered_clusters = _covered_ranges_from_candles(candles, chunk)
                cache_provider.cache_candles(config, candles)
            except Exception as exc:
                db.rollback()
                failed_ranges.append(chunk)
                _record_download_range(
                    db,
                    request,
                    chunk,
                    status=FAILED_STATUS,
                    row_count=0,
                    error_message=str(exc),
                )
                continue

            downloaded_rows += len(candles)
            for covered_range, covered_candles in covered_clusters:
                _record_download_range(
                    db,
                    request,
                    covered_range,
                    status=COMPLETED_STATUS,
                    row_count=len(covered_candles),
                    error_message=None,
                )

    final_missing_ranges = _missing_ranges(db, request)
    if failed_ranges:
        failed_rows = _estimate_rows(request.timeframe, failed_ranges)
        return MarketDataPrepareResponse(
            ready=False,
            missingRanges=final_missing_ranges,
            estimatedRows=failed_rows,
            estimatedSeconds=_estimate_seconds(failed_rows),
            message="部分行情下载失败，请重试失败区间",
            downloadedRows=downloaded_rows,
            failedRanges=failed_ranges,
        )

    estimated_rows = _estimate_rows(request.timeframe, final_missing_ranges)
    estimated_seconds = _estimate_seconds(estimated_rows)
    return MarketDataPrepareResponse(
        ready=not final_missing_ranges,
        missingRanges=final_missing_ranges,
        estimatedRows=estimated_rows,
        estimatedSeconds=estimated_seconds,
        message=_coverage_message(request, final_missing_ranges, estimated_seconds),
        downloadedRows=downloaded_rows,
        failedRanges=[],
    )


def ensure_market_data_ready(db: Session, config: BacktestConfig) -> None:
    request = MarketDataRequest.model_validate(
        {
            "market": config.market,
            "symbol": config.symbol,
            "timeframe": config.timeframe,
            "startDate": config.startDate,
            "endDate": config.endDate,
        }
    )
    coverage = get_market_data_coverage(db, request)
    if not coverage.ready:
        raise MarketDataUnavailableError(coverage.message)


def _missing_ranges(db: Session, request: MarketDataRequest) -> list[MarketDataRange]:
    request_start = date.fromisoformat(request.startDate)
    request_end = date.fromisoformat(request.endDate)
    completed_rows = db.scalars(
        select(MarketDataDownloadRange)
        .where(MarketDataDownloadRange.market == request.market)
        .where(MarketDataDownloadRange.symbol == request.symbol)
        .where(MarketDataDownloadRange.timeframe == request.timeframe)
        .where(MarketDataDownloadRange.source == LIVE_CACHE_SOURCE)
        .where(MarketDataDownloadRange.status == COMPLETED_STATUS)
        .where(MarketDataDownloadRange.start_date <= request.endDate)
        .where(MarketDataDownloadRange.end_date >= request.startDate)
        .order_by(MarketDataDownloadRange.start_date, MarketDataDownloadRange.end_date)
    ).all()

    completed_ranges = [
        (
            max(date.fromisoformat(row.start_date), request_start),
            min(date.fromisoformat(row.end_date), request_end),
        )
        for row in completed_rows
    ]
    missing_ranges: list[MarketDataRange] = []
    missing_start: date | None = None
    missing_end: date | None = None

    cursor = request_start
    while cursor <= request_end:
        if not _is_required_market_date(cursor):
            cursor += timedelta(days=1)
            continue

        is_covered = any(start <= cursor <= end for start, end in completed_ranges)
        if is_covered:
            if missing_start is not None and missing_end is not None:
                missing_ranges.append(_range_from_dates(missing_start, missing_end))
                missing_start = None
                missing_end = None
        else:
            if missing_start is None:
                missing_start = cursor
            missing_end = cursor
        cursor += timedelta(days=1)

    if missing_start is not None and missing_end is not None:
        missing_ranges.append(_range_from_dates(missing_start, missing_end))
    return missing_ranges


def _chunk_range(missing_range: MarketDataRange, timeframe: str) -> list[MarketDataRange]:
    chunk_days = 7 if timeframe == "1m" else 31
    start = date.fromisoformat(missing_range.startDate)
    end = date.fromisoformat(missing_range.endDate)
    chunks: list[MarketDataRange] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end)
        chunks.append(_range_from_dates(cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def _record_download_range(
    db: Session,
    request: MarketDataRequest,
    range_: MarketDataRange,
    *,
    status: str,
    row_count: int,
    error_message: str | None,
) -> None:
    existing = db.scalar(
        select(MarketDataDownloadRange)
        .where(MarketDataDownloadRange.market == request.market)
        .where(MarketDataDownloadRange.symbol == request.symbol)
        .where(MarketDataDownloadRange.timeframe == request.timeframe)
        .where(MarketDataDownloadRange.start_date == range_.startDate)
        .where(MarketDataDownloadRange.end_date == range_.endDate)
    )
    if existing is None:
        existing = MarketDataDownloadRange(
            market=request.market,
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=range_.startDate,
            end_date=range_.endDate,
            status=status,
            row_count=row_count,
            source=LIVE_CACHE_SOURCE,
            error_message=error_message,
        )
        db.add(existing)
    else:
        existing.status = status
        existing.row_count = row_count
        existing.source = LIVE_CACHE_SOURCE
        existing.error_message = error_message
    db.commit()


def _covered_ranges_from_candles(
    candles: list[MarketCandle],
    requested_range: MarketDataRange,
) -> list[tuple[MarketDataRange, list[MarketCandle]]]:
    if not candles:
        raise MarketDataUnavailableError("No market data returned")

    request_start = date.fromisoformat(requested_range.startDate)
    request_end = date.fromisoformat(requested_range.endDate)
    dated_candles: list[tuple[date, MarketCandle]] = []
    for candle in candles:
        candle_date = _candle_date(candle)
        if not request_start <= candle_date <= request_end:
            raise MarketDataUnavailableError(
                "Market data contains a candle outside requested range"
            )
        dated_candles.append((candle_date, candle))

    if not dated_candles:
        raise MarketDataUnavailableError("No market data returned inside requested range")

    dated_candles.sort(key=lambda item: item[0])
    clusters: list[tuple[date, date, list[MarketCandle]]] = []
    cluster_start = dated_candles[0][0]
    previous_date = cluster_start
    cluster_candles: list[MarketCandle] = []

    for candle_date, candle in dated_candles:
        if (candle_date - previous_date).days > MAX_NON_TRADING_GAP_DAYS:
            clusters.append((cluster_start, previous_date, cluster_candles))
            cluster_start = candle_date
            cluster_candles = []
        cluster_candles.append(candle)
        previous_date = candle_date

    clusters.append((cluster_start, previous_date, cluster_candles))
    return [
        (_range_from_dates(cluster_start, cluster_end), cluster_candles)
        for cluster_start, cluster_end, cluster_candles in clusters
    ]


def _candle_date(candle: MarketCandle) -> date:
    try:
        return date.fromisoformat(candle.time[:10])
    except ValueError as exc:
        raise MarketDataUnavailableError("Market data contains an invalid candle time") from exc


def _backtest_config_for_range(
    request: MarketDataRequest,
    range_: MarketDataRange,
) -> BacktestConfig:
    return BacktestConfig.model_validate(
        {
            "market": request.market,
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "startDate": range_.startDate,
            "endDate": range_.endDate,
            "initialCash": 1,
        }
    )


def _estimate_rows(timeframe: str, ranges: list[MarketDataRange]) -> int:
    bars_per_day = 240 if timeframe == "1m" else 78
    return sum(_required_market_days(range_) * bars_per_day for range_ in ranges)


def _estimate_seconds(row_count: int) -> int:
    if row_count <= 0:
        return 0
    return min(180, max(5, ceil(row_count / 1000)))


def _coverage_message(
    request: MarketDataRequest,
    missing_ranges: list[MarketDataRange],
    estimated_seconds: int,
) -> str:
    if not missing_ranges:
        return "本地行情已准备完成，可以直接运行回测"
    timeframe_label = "1分钟K线" if request.timeframe == "1m" else "5分钟K线"
    return (
        f"本地缺少 {request.symbol} 的 {timeframe_label}，"
        f"需要下载 {len(missing_ranges)} 个区间，预计约 {estimated_seconds} 秒"
    )


def _required_market_days(range_: MarketDataRange) -> int:
    start = date.fromisoformat(range_.startDate)
    end = date.fromisoformat(range_.endDate)
    cursor = start
    days = 0
    while cursor <= end:
        if _is_required_market_date(cursor):
            days += 1
        cursor += timedelta(days=1)
    return days


def _is_required_market_date(day: date) -> bool:
    return day.weekday() < 5


def _range_from_dates(start: date, end: date) -> MarketDataRange:
    return MarketDataRange(startDate=start.isoformat(), endDate=end.isoformat())
