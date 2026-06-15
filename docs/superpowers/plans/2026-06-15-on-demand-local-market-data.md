# On-Demand Local Market Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make STS download and persist real K-line data only after the user confirms a backtest, then run backtests from prepared local MySQL data instead of unstable live fetching.

**Architecture:** Add a local market-data preparation layer around the existing `market_kline_cache` table. A new download-range table records completed or failed date ranges, new APIs expose coverage and preparation, and the builder calls coverage before running a backtest. The backtest endpoint refuses unprepared local data so failed downloads never produce fake or partial results.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, MySQL 8.0, pytest, Vue 3, Pinia, Axios, Vitest.

---

## File Structure

- Modify `backend/app/models/market_data.py`: add `MarketDataDownloadRange`.
- Modify `backend/app/models/__init__.py`: export `MarketDataDownloadRange`.
- Modify `backend/app/core/schema_migrations.py`: add dev migration guard for `market_data_download_ranges`.
- Create `backend/app/schemas/market_data.py`: request and response schemas for coverage and prepare endpoints.
- Create `backend/app/services/market_data_download_service.py`: validation, coverage checks, range splitting, estimates, download preparation, and local-only cache reading.
- Modify `backend/app/services/market_data_service.py`: expose a public `cache_candles()` wrapper and a local-only provider that never fetches live data.
- Create `backend/app/api/market_data.py`: `POST /api/market-data/coverage` and `POST /api/market-data/prepare`.
- Modify `backend/app/api/backtests.py`: require completed local coverage before running and use local-only cached candles.
- Modify `backend/app/main.py`: include the market-data router.
- Create `backend/tests/test_market_data_downloads.py`: service and API tests for coverage and prepare.
- Modify `backend/tests/test_backtests.py`: seed completed download ranges and assert unprepared local data is rejected.
- Modify `frontend/src/views/BuilderView.vue`: add coverage check, missing-data confirmation, download waiting state, and continue-after-download flow.
- Modify `frontend/src/styles/base.css`: style the new market-data prompt and download status in the existing obsidian/purple visual system.
- Modify `frontend/tests/builder-view.test.ts`: cover coverage-ready, missing-data prompt, cancel, download-and-continue, and prepare failure paths.

---

### Task 1: Backend Download Range Model

**Files:**
- Modify: `backend/app/models/market_data.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/core/schema_migrations.py`
- Test: `backend/tests/test_market_data_downloads.py`

- [ ] **Step 1: Write failing model test**

Create `backend/tests/test_market_data_downloads.py` with this initial content:

```python
from sqlalchemy import select

from app.models import MarketDataDownloadRange


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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
./.venv/bin/python -m pytest tests/test_market_data_downloads.py::test_market_data_download_range_model_persists_completed_range -q
```

Expected: FAIL because `MarketDataDownloadRange` is not exported from `app.models`.

- [ ] **Step 3: Add model**

In `backend/app/models/market_data.py`, keep `MarketKlineCache` unchanged and add this class below it:

```python
class MarketDataDownloadRange(Base):
    __tablename__ = "market_data_download_ranges"
    __table_args__ = (
        UniqueConstraint(
            "market",
            "symbol",
            "timeframe",
            "start_date",
            "end_date",
            name="uq_market_data_download_range_identity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    end_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="LIVE", index=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
```

- [ ] **Step 4: Export model**

In `backend/app/models/__init__.py`, change the market-data import to:

```python
from app.models.market_data import MarketDataDownloadRange, MarketKlineCache
```

Add `"MarketDataDownloadRange"` to `__all__` directly before `"MarketKlineCache"`.

- [ ] **Step 5: Add dev schema migration**

In `backend/app/core/schema_migrations.py`, add a table-creation block at the end of `ensure_development_schema()`:

```python
    if not inspector.has_table("market_data_download_ranges"):
        from app.models.market_data import MarketDataDownloadRange

        MarketDataDownloadRange.__table__.create(bind=engine, checkfirst=True)
```

Keep this inside the function, after the existing `market_kline_cache` block.

- [ ] **Step 6: Run model test**

Run:

```bash
cd backend
./.venv/bin/python -m pytest tests/test_market_data_downloads.py::test_market_data_download_range_model_persists_completed_range -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/market_data.py backend/app/models/__init__.py backend/app/core/schema_migrations.py backend/tests/test_market_data_downloads.py
git commit -m "feat: add market data download ranges"
```

---

### Task 2: Coverage And Prepare Service

**Files:**
- Create: `backend/app/schemas/market_data.py`
- Create: `backend/app/services/market_data_download_service.py`
- Modify: `backend/app/services/market_data_service.py`
- Test: `backend/tests/test_market_data_downloads.py`

- [ ] **Step 1: Add failing service tests**

Append these tests to `backend/tests/test_market_data_downloads.py`:

```python
import pytest

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
```

Add `MarketKlineCache` to the existing import from `app.models` in this test file.

- [ ] **Step 2: Run service tests to verify they fail**

Run:

```bash
cd backend
./.venv/bin/python -m pytest tests/test_market_data_downloads.py -q
```

Expected: FAIL because `app.schemas.market_data` and `app.services.market_data_download_service` do not exist.

- [ ] **Step 3: Add schemas**

Create `backend/app/schemas/market_data.py`:

```python
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class MarketDataRange(BaseModel):
    startDate: str
    endDate: str


class MarketDataRequest(BaseModel):
    market: Literal["A_SHARE", "US_STOCK"]
    symbol: str
    timeframe: Literal["5m", "1m"]
    startDate: str
    endDate: str

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("股票代码不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_date_range(self):
        start = date.fromisoformat(self.startDate)
        end = date.fromisoformat(self.endDate)
        if start > end:
            raise ValueError("开始日期不能晚于结束日期")
        if (end - start).days > 397:
            raise ValueError("单次回测仅支持 1 只股票，时间范围最长 13 个月")
        return self


class MarketDataCoverageResponse(BaseModel):
    ready: bool
    missingRanges: list[MarketDataRange]
    estimatedRows: int = Field(ge=0)
    estimatedSeconds: int = Field(ge=0)
    message: str


class MarketDataPrepareResponse(MarketDataCoverageResponse):
    downloadedRows: int = Field(ge=0)
    failedRanges: list[MarketDataRange]
```

- [ ] **Step 4: Expose public cache writer and local-only reader**

In `backend/app/services/market_data_service.py`, add a public wrapper to `CachedMarketDataProvider`:

```python
    def cache_candles(self, config: BacktestConfig, candles: list[MarketCandle]) -> None:
        self._cache_candles(config, candles)
```

Add this class below `CachedMarketDataProvider`:

```python
class LocalOnlyMarketDataProvider:
    def __init__(self, db: Session):
        self.cached_provider = CachedMarketDataProvider(db, source_provider=_UnavailableSourceProvider())

    def get_intraday_candles(self, config: BacktestConfig) -> list[MarketCandle]:
        candles = self.cached_provider._cached_candles(config)
        if not candles:
            raise MarketDataUnavailableError("Local market data is not prepared")
        return candles


class _UnavailableSourceProvider:
    def get_intraday_candles(self, config: BacktestConfig) -> list[MarketCandle]:
        raise MarketDataUnavailableError("Live fetching is disabled for local-only backtests")
```

- [ ] **Step 5: Add service**

Create `backend/app/services/market_data_download_service.py`:

```python
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_data import MarketDataDownloadRange
from app.schemas.backtest import BacktestConfig
from app.schemas.market_data import (
    MarketDataCoverageResponse,
    MarketDataPrepareResponse,
    MarketDataRange,
    MarketDataRequest,
)
from app.services.market_data_service import (
    CachedMarketDataProvider,
    DefaultMarketDataProvider,
    MarketDataProvider,
    MarketDataUnavailableError,
)

LIVE_SOURCE = "LIVE"
COMPLETED = "completed"
FAILED = "failed"


def get_market_data_coverage(db: Session, request: MarketDataRequest) -> MarketDataCoverageResponse:
    missing_ranges = _missing_ranges(db, request)
    if not missing_ranges:
        return MarketDataCoverageResponse(
            ready=True,
            missingRanges=[],
            estimatedRows=0,
            estimatedSeconds=0,
            message="本地行情已准备完成，可以直接运行回测",
        )

    estimated_rows = sum(_estimate_rows(item, request.timeframe) for item in missing_ranges)
    estimated_seconds = _estimate_seconds(estimated_rows, request.timeframe)
    return MarketDataCoverageResponse(
        ready=False,
        missingRanges=missing_ranges,
        estimatedRows=estimated_rows,
        estimatedSeconds=estimated_seconds,
        message=_missing_message(request, estimated_seconds),
    )


def prepare_market_data(
    db: Session,
    request: MarketDataRequest,
    source_provider: MarketDataProvider | None = None,
) -> MarketDataPrepareResponse:
    provider = source_provider or DefaultMarketDataProvider()
    cache = CachedMarketDataProvider(db)
    missing_ranges = _missing_ranges(db, request)
    downloaded_rows = 0
    failed_ranges: list[MarketDataRange] = []

    for missing_range in missing_ranges:
        for chunk in _split_range(missing_range, request.timeframe):
            config = _config_for_request(request, chunk)
            try:
                candles = provider.get_intraday_candles(config)
            except MarketDataUnavailableError as exc:
                _record_range(db, request, chunk, FAILED, 0, str(exc))
                failed_ranges.append(chunk)
                continue
            cache.cache_candles(config, candles)
            downloaded_rows += len(candles)
            _record_range(db, request, chunk, COMPLETED, len(candles), None)

    coverage = get_market_data_coverage(db, request)
    return MarketDataPrepareResponse(
        ready=coverage.ready,
        missingRanges=coverage.missingRanges,
        estimatedRows=coverage.estimatedRows,
        estimatedSeconds=coverage.estimatedSeconds,
        message=coverage.message if not failed_ranges else "部分行情下载失败，请重试失败区间",
        downloadedRows=downloaded_rows,
        failedRanges=failed_ranges,
    )


def ensure_market_data_ready(db: Session, config: BacktestConfig) -> None:
    request = MarketDataRequest(
        market=config.market,
        symbol=config.symbol,
        timeframe=config.timeframe,
        startDate=config.startDate,
        endDate=config.endDate,
    )
    if not get_market_data_coverage(db, request).ready:
        raise MarketDataUnavailableError("Local market data is not prepared")


def _missing_ranges(db: Session, request: MarketDataRequest) -> list[MarketDataRange]:
    completed = db.scalars(
        select(MarketDataDownloadRange)
        .where(MarketDataDownloadRange.market == request.market)
        .where(MarketDataDownloadRange.symbol == request.symbol)
        .where(MarketDataDownloadRange.timeframe == request.timeframe)
        .where(MarketDataDownloadRange.status == COMPLETED)
        .order_by(MarketDataDownloadRange.start_date)
    ).all()

    intervals = [
        (date.fromisoformat(row.start_date), date.fromisoformat(row.end_date))
        for row in completed
    ]
    return _subtract_intervals(
        date.fromisoformat(request.startDate),
        date.fromisoformat(request.endDate),
        intervals,
    )


def _subtract_intervals(
    start: date,
    end: date,
    completed: list[tuple[date, date]],
) -> list[MarketDataRange]:
    cursor = start
    missing: list[MarketDataRange] = []
    for covered_start, covered_end in completed:
        if covered_end < cursor:
            continue
        if covered_start > end:
            break
        if covered_start > cursor:
            missing.append(_range(cursor, min(covered_start - timedelta(days=1), end)))
        if covered_end >= cursor:
            cursor = covered_end + timedelta(days=1)
        if cursor > end:
            break
    if cursor <= end:
        missing.append(_range(cursor, end))
    return missing


def _split_range(range_item: MarketDataRange, timeframe: str) -> list[MarketDataRange]:
    start = date.fromisoformat(range_item.startDate)
    end = date.fromisoformat(range_item.endDate)
    chunk_days = 7 if timeframe == "1m" else 31
    chunks: list[MarketDataRange] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end)
        chunks.append(_range(cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def _record_range(
    db: Session,
    request: MarketDataRequest,
    range_item: MarketDataRange,
    status: str,
    row_count: int,
    error_message: str | None,
) -> None:
    existing = db.scalar(
        select(MarketDataDownloadRange)
        .where(MarketDataDownloadRange.market == request.market)
        .where(MarketDataDownloadRange.symbol == request.symbol)
        .where(MarketDataDownloadRange.timeframe == request.timeframe)
        .where(MarketDataDownloadRange.start_date == range_item.startDate)
        .where(MarketDataDownloadRange.end_date == range_item.endDate)
    )
    if existing is None:
        existing = MarketDataDownloadRange(
            market=request.market,
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=range_item.startDate,
            end_date=range_item.endDate,
            source=LIVE_SOURCE,
        )
        db.add(existing)
    existing.status = status
    existing.row_count = row_count
    existing.error_message = error_message
    db.commit()


def _config_for_request(request: MarketDataRequest, range_item: MarketDataRange) -> BacktestConfig:
    return BacktestConfig(
        market=request.market,
        symbol=request.symbol,
        timeframe=request.timeframe,
        startDate=range_item.startDate,
        endDate=range_item.endDate,
        initialCash=1,
    )


def _estimate_rows(range_item: MarketDataRange, timeframe: str) -> int:
    days = (date.fromisoformat(range_item.endDate) - date.fromisoformat(range_item.startDate)).days + 1
    trading_days = max(1, int(days * 5 / 7))
    bars_per_day = 240 if timeframe == "1m" else 78
    return trading_days * bars_per_day


def _estimate_seconds(rows: int, timeframe: str) -> int:
    divisor = 800 if timeframe == "1m" else 1200
    return max(5, min(180, round(rows / divisor)))


def _missing_message(request: MarketDataRequest, estimated_seconds: int) -> str:
    label = "1分钟" if request.timeframe == "1m" else "5分钟"
    return (
        f"本地缺少 {request.symbol} 的 {label}K线，系统将下载 "
        f"{request.startDate} 至 {request.endDate} 数据，预计 {estimated_seconds} 秒。"
    )


def _range(start: date, end: date) -> MarketDataRange:
    return MarketDataRange(startDate=start.isoformat(), endDate=end.isoformat())
```

- [ ] **Step 6: Run service tests**

Run:

```bash
cd backend
./.venv/bin/python -m pytest tests/test_market_data_downloads.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/market_data.py backend/app/services/market_data_download_service.py backend/app/services/market_data_service.py backend/tests/test_market_data_downloads.py
git commit -m "feat: prepare local market data on demand"
```

---

### Task 3: Market Data API

**Files:**
- Create: `backend/app/api/market_data.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_market_data_downloads.py`

- [ ] **Step 1: Add failing API tests**

Append these tests to `backend/tests/test_market_data_downloads.py`:

```python
from app.api import market_data as market_data_api


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
    assert payload["missingRanges"] == [{"startDate": "2025-03-01", "endDate": "2025-03-31"}]
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
            "startDate": "2025-03-01",
            "endDate": "2025-03-31",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["downloadedRows"] > 0
    assert payload["failedRanges"] == []
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```bash
cd backend
./.venv/bin/python -m pytest tests/test_market_data_downloads.py::test_market_data_coverage_endpoint_returns_missing_range tests/test_market_data_downloads.py::test_market_data_prepare_endpoint_downloads_and_returns_ready -q
```

Expected: FAIL because `/api/market-data/*` routes are not registered.

- [ ] **Step 3: Add API router**

Create `backend/app/api/market_data.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.market_data import (
    MarketDataCoverageResponse,
    MarketDataPrepareResponse,
    MarketDataRequest,
)
from app.services.market_data_download_service import (
    get_market_data_coverage,
    prepare_market_data,
)
from app.services.market_data_service import DefaultMarketDataProvider

router = APIRouter(prefix="/market-data", tags=["market-data"])


@router.post("/coverage", response_model=MarketDataCoverageResponse)
def coverage(
    request: MarketDataRequest,
    db: Session = Depends(get_db),
) -> MarketDataCoverageResponse:
    return get_market_data_coverage(db, request)


@router.post("/prepare", response_model=MarketDataPrepareResponse)
def prepare(
    request: MarketDataRequest,
    db: Session = Depends(get_db),
) -> MarketDataPrepareResponse:
    return prepare_market_data(db, request, source_provider=DefaultMarketDataProvider())
```

- [ ] **Step 4: Register router**

In `backend/app/main.py`, add `market_data` to the API imports and include it:

```python
from app.api import (
    admin_custom_block_reviews,
    admin_forum,
    auth,
    backtests,
    custom_blocks,
    forum,
    health,
    market_data,
    market_rules,
    shared_blocks,
    simulation_accounts,
    strategies,
)
```

Add this line after the health router:

```python
app.include_router(market_data.router, prefix="/api")
```

- [ ] **Step 5: Run API tests**

Run:

```bash
cd backend
./.venv/bin/python -m pytest tests/test_market_data_downloads.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/market_data.py backend/app/main.py backend/tests/test_market_data_downloads.py
git commit -m "feat: add market data preparation api"
```

---

### Task 4: Backtest Requires Prepared Local Data

**Files:**
- Modify: `backend/app/api/backtests.py`
- Modify: `backend/tests/test_backtests.py`
- Test: `backend/tests/test_backtests.py`

- [ ] **Step 1: Update test seed helper**

In `backend/tests/test_backtests.py`, import `MarketDataDownloadRange` from `app.models` and update `_seed_market_cache()` to add a completed range after adding candles:

```python
    db_session.add(
        MarketDataDownloadRange(
            market=market,
            symbol=symbol,
            timeframe=timeframe,
            start_date="2026-01-01",
            end_date="2026-03-01",
            status="completed",
            row_count=len(candle_times),
            source="LIVE",
        )
    )
    db_session.commit()
```

Place this before the existing `db_session.commit()` or replace the final commit with this block plus one commit.

- [ ] **Step 2: Add failing unprepared-data test**

Add this test near `test_run_backtest_reports_market_data_unavailable`:

```python
def test_run_backtest_rejects_unprepared_local_market_data(client):
    response = client.post("/api/backtests/run", json=_backtest_payload())

    assert response.status_code == 422
    assert response.json()["detail"] == "本地行情尚未准备完成，请先下载行情后再运行回测"
```

Replace the existing `test_run_backtest_reports_market_data_unavailable` with this local-only provider failure version:

```python
def test_run_backtest_reports_local_data_provider_failure(client, db_session, monkeypatch):
    _seed_market_cache(db_session)

    class FailingLocalProvider:
        def __init__(self, db):
            pass

        def get_intraday_candles(self, config):
            raise MarketDataUnavailableError("local cache missing")

    monkeypatch.setattr(backtests_api, "LocalOnlyMarketDataProvider", FailingLocalProvider)

    response = client.post("/api/backtests/run", json=_backtest_payload())

    assert response.status_code == 422
    assert response.json()["detail"] == "本地行情尚未准备完成，请先下载行情后再运行回测"
```

- [ ] **Step 3: Run targeted backtest tests to verify failure**

Run:

```bash
cd backend
./.venv/bin/python -m pytest tests/test_backtests.py::test_run_backtest_rejects_unprepared_local_market_data -q
```

Expected: FAIL because the route still attempts live fetching instead of rejecting unprepared local data.

- [ ] **Step 4: Update backtest route**

In `backend/app/api/backtests.py`, change the market-data imports:

```python
from app.services.market_data_download_service import ensure_market_data_ready
from app.services.market_data_service import LocalOnlyMarketDataProvider, MarketDataUnavailableError
```

In `run_backtest()`, before `run_backtest_service(...)`, add:

```python
        ensure_market_data_ready(db, effective_request.config)
```

Then change the provider passed to `run_backtest_service()`:

```python
            market_data_provider=LocalOnlyMarketDataProvider(db),
```

Change the exception detail to:

```python
            detail="本地行情尚未准备完成，请先下载行情后再运行回测",
```

The whole try block should keep the same save behavior after the result succeeds.

- [ ] **Step 5: Run backtest tests**

Run:

```bash
cd backend
./.venv/bin/python -m pytest tests/test_backtests.py -q
```

Expected: PASS.

- [ ] **Step 6: Run market data tests**

Run:

```bash
cd backend
./.venv/bin/python -m pytest tests/test_market_data_provider.py tests/test_market_data_downloads.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/backtests.py backend/tests/test_backtests.py
git commit -m "feat: require prepared local data for backtests"
```

---

### Task 5: Builder Coverage Check And Download Prompt

**Files:**
- Modify: `frontend/src/views/BuilderView.vue`
- Modify: `frontend/src/styles/base.css`
- Modify: `frontend/tests/builder-view.test.ts`

- [ ] **Step 1: Add failing frontend tests**

In `frontend/tests/builder-view.test.ts`, update the existing `runs a backtest and renders the returned result summary` test so the mocked `apiClient.post` resolves coverage first, then backtest:

```ts
vi.mocked(apiClient.post)
  .mockResolvedValueOnce({
    data: {
      ready: true,
      missingRanges: [],
      estimatedRows: 0,
      estimatedSeconds: 0,
      message: '本地行情已准备完成，可以直接运行回测'
    }
  })
  .mockResolvedValueOnce({
    data: {
      runId: 'mock-run-1',
      status: 'COMPLETED',
      summary: {
        totalReturnPercent: 7.3,
        maxDrawdownPercent: 2.8,
        winRatePercent: 66.7,
        endingEquity: 107300,
        tradeCount: 3
      },
      config: {
        market: 'A_SHARE',
        symbol: '000001.SZ',
        timeframe: '5m',
        startDate: '2026-01-01',
        endDate: '2026-03-01',
        initialCash: 100000
      },
      trades: [],
      events: [],
      timeline: [],
      equityCurve: [
        { time: '2026-01-05 10:30', equity: 100000 },
        { time: '2026-01-05 10:40', equity: 107300 }
      ]
    }
  })
```

Then assert:

```ts
expect(apiClient.post).toHaveBeenNthCalledWith(1, '/market-data/coverage', {
  market: 'A_SHARE',
  symbol: '000001.SZ',
  timeframe: '5m',
  startDate: '2026-01-01',
  endDate: '2026-03-01'
})
expect(apiClient.post).toHaveBeenNthCalledWith(2, '/backtests/run', {
  strategy: expect.objectContaining({ version: 1 }),
  config: expect.objectContaining({ symbol: '000001.SZ' })
})
```

Add this new test:

```ts
it('asks before downloading missing market data and continues after prepare', async () => {
  vi.mocked(apiClient.post)
    .mockResolvedValueOnce({
      data: {
        ready: false,
        missingRanges: [{ startDate: '2026-01-01', endDate: '2026-03-01' }],
        estimatedRows: 12000,
        estimatedSeconds: 20,
        message: '本地缺少 000001.SZ 的 5分钟K线，系统将下载 2026-01-01 至 2026-03-01 数据，预计 20 秒。'
      }
    })
    .mockResolvedValueOnce({
      data: {
        ready: true,
        missingRanges: [],
        estimatedRows: 0,
        estimatedSeconds: 0,
        message: '本地行情已准备完成，可以直接运行回测',
        downloadedRows: 12000,
        failedRanges: []
      }
    })
    .mockResolvedValueOnce({
      data: {
        runId: 'mock-run-2',
        status: 'COMPLETED',
        summary: {
          totalReturnPercent: 1.2,
          maxDrawdownPercent: 0.4,
          winRatePercent: 50,
          endingEquity: 101200,
          tradeCount: 1
        },
        config: {
          market: 'A_SHARE',
          symbol: '000001.SZ',
          timeframe: '5m',
          startDate: '2026-01-01',
          endDate: '2026-03-01',
          initialCash: 100000
        },
        trades: [],
        events: [],
        timeline: [],
        equityCurve: [{ time: '2026-01-05 10:30', equity: 101200 }]
      }
    })

  const wrapper = mount(BuilderView)
  mockCanvasRect(wrapper)
  await dropBlock(wrapper, 'buy', 260, 170)
  await openReviewModal()

  await wrapper.find('.review-primary-button').trigger('click')
  await flushPromises()

  expect(wrapper.find('.market-data-download-prompt').text()).toContain('需要下载本地行情')
  expect(wrapper.find('.market-data-download-prompt').text()).toContain('预计 20 秒')
  expect(apiClient.post).toHaveBeenCalledTimes(1)

  await wrapper.find('[data-market-data-action="prepare"]').trigger('click')
  await flushPromises()

  expect(apiClient.post).toHaveBeenNthCalledWith(2, '/market-data/prepare', {
    market: 'A_SHARE',
    symbol: '000001.SZ',
    timeframe: '5m',
    startDate: '2026-01-01',
    endDate: '2026-03-01'
  })
  expect(apiClient.post).toHaveBeenNthCalledWith(3, '/backtests/run', {
    strategy: expect.objectContaining({ version: 1 }),
    config: expect.objectContaining({ symbol: '000001.SZ' })
  })
  expect(wrapper.find('.backtest-result-card').text()).toContain('1.2%')
})
```

Add a cancel test:

```ts
it('cancels missing market data download without running backtest', async () => {
  vi.mocked(apiClient.post).mockResolvedValueOnce({
    data: {
      ready: false,
      missingRanges: [{ startDate: '2026-01-01', endDate: '2026-03-01' }],
      estimatedRows: 12000,
      estimatedSeconds: 20,
      message: '本地缺少 000001.SZ 的 5分钟K线，系统将下载 2026-01-01 至 2026-03-01 数据，预计 20 秒。'
    }
  })

  const wrapper = mount(BuilderView)
  mockCanvasRect(wrapper)
  await dropBlock(wrapper, 'buy', 260, 170)
  await openReviewModal()

  await wrapper.find('.review-primary-button').trigger('click')
  await flushPromises()
  await wrapper.find('[data-market-data-action="cancel"]').trigger('click')
  await flushPromises()

  expect(wrapper.find('.market-data-download-prompt').exists()).toBe(false)
  expect(apiClient.post).toHaveBeenCalledTimes(1)
})
```

Add a prepare failure test:

```ts
it('shows prepare failure and does not run backtest when market data download fails', async () => {
  vi.mocked(apiClient.post)
    .mockResolvedValueOnce({
      data: {
        ready: false,
        missingRanges: [{ startDate: '2026-01-01', endDate: '2026-03-01' }],
        estimatedRows: 12000,
        estimatedSeconds: 20,
        message: '本地缺少 000001.SZ 的 5分钟K线，系统将下载 2026-01-01 至 2026-03-01 数据，预计 20 秒。'
      }
    })
    .mockResolvedValueOnce({
      data: {
        ready: false,
        missingRanges: [{ startDate: '2026-01-01', endDate: '2026-03-01' }],
        estimatedRows: 12000,
        estimatedSeconds: 20,
        message: '部分行情下载失败，请重试失败区间',
        downloadedRows: 0,
        failedRanges: [{ startDate: '2026-01-01', endDate: '2026-03-01' }]
      }
    })

  const wrapper = mount(BuilderView)
  mockCanvasRect(wrapper)
  await dropBlock(wrapper, 'buy', 260, 170)
  await openReviewModal()

  await wrapper.find('.review-primary-button').trigger('click')
  await flushPromises()
  await wrapper.find('[data-market-data-action="prepare"]').trigger('click')
  await flushPromises()

  expect(wrapper.find('.market-data-status').text()).toContain('部分行情下载失败')
  expect(wrapper.find('.backtest-result-card').exists()).toBe(false)
  expect(apiClient.post).toHaveBeenCalledTimes(2)
})
```

- [ ] **Step 2: Run frontend tests to verify failure**

Run:

```bash
cd frontend
npm test -- builder-view.test.ts
```

Expected: FAIL because the UI does not call coverage and does not render `.market-data-download-prompt`.

- [ ] **Step 3: Add frontend types and state**

In `frontend/src/views/BuilderView.vue`, add these types near the existing backtest types:

```ts
interface MarketDataRange {
  startDate: string
  endDate: string
}

interface MarketDataCoverage {
  ready: boolean
  missingRanges: MarketDataRange[]
  estimatedRows: number
  estimatedSeconds: number
  message: string
}

interface MarketDataPrepareResult extends MarketDataCoverage {
  downloadedRows: number
  failedRanges: MarketDataRange[]
}

interface PendingBacktestPayload {
  strategy: StrategyDraft
  config: BacktestConfig
}
```

Add state next to the existing backtest refs:

```ts
const marketDataPrompt = ref<MarketDataCoverage | null>(null)
const marketDataStatus = ref('')
const isMarketDataPreparing = ref(false)
const pendingBacktestPayload = ref<PendingBacktestPayload | null>(null)
```

Add this computed helper:

```ts
const marketDataRequest = computed(() => ({
  market: backtestConfig.value.market,
  symbol: backtestConfig.value.symbol,
  timeframe: backtestConfig.value.timeframe,
  startDate: backtestConfig.value.startDate,
  endDate: backtestConfig.value.endDate
}))
```

- [ ] **Step 4: Refactor run flow**

Replace `runBacktest()` with this structure:

```ts
async function runBacktest() {
  if (backtestIssues.value.length > 0 || isBacktestRunning.value || isMarketDataPreparing.value) {
    return
  }

  const payload = {
    strategy: strategyDraft.value,
    config: backtestConfig.value
  }

  isBacktestRunning.value = true
  backtestRunError.value = ''
  backtestRunResult.value = null
  backtestPersistStatus.value = ''
  marketDataPrompt.value = null
  marketDataStatus.value = ''
  pendingBacktestPayload.value = payload

  try {
    const coverage = await apiClient.post<MarketDataCoverage>(
      '/market-data/coverage',
      marketDataRequest.value
    )
    if (!coverage.data.ready) {
      marketDataPrompt.value = coverage.data
      return
    }
    await submitBacktest(payload)
  } catch (requestError) {
    backtestRunError.value = getApiErrorMessage(requestError, '行情检查失败，请稍后重试')
  } finally {
    isBacktestRunning.value = false
  }
}

async function submitBacktest(payload: PendingBacktestPayload) {
  const response = await apiClient.post<BacktestRunResult>('/backtests/run', payload)
  backtestRunResult.value = response.data
  backtestPersistStatus.value = authStore.isAuthenticated
    ? '回测结果已保存到个人空间，可在我的回测中查看'
    : '访客回测仅在当前页面展示，登录后运行可保存到个人空间'
}
```

Add prepare and cancel handlers:

```ts
async function prepareMarketDataAndRun() {
  if (!pendingBacktestPayload.value || isMarketDataPreparing.value) {
    return
  }

  isMarketDataPreparing.value = true
  marketDataStatus.value = '正在下载行情...'
  backtestRunError.value = ''

  try {
    const response = await apiClient.post<MarketDataPrepareResult>(
      '/market-data/prepare',
      marketDataRequest.value
    )
    if (!response.data.ready) {
      marketDataStatus.value = response.data.message
      return
    }
    marketDataPrompt.value = null
    marketDataStatus.value = `已下载 ${response.data.downloadedRows} 条行情，正在运行回测`
    await submitBacktest(pendingBacktestPayload.value)
  } catch (requestError) {
    marketDataStatus.value = getApiErrorMessage(requestError, '行情下载失败，请稍后重试')
  } finally {
    isMarketDataPreparing.value = false
  }
}

function cancelMarketDataDownload() {
  marketDataPrompt.value = null
  marketDataStatus.value = ''
  pendingBacktestPayload.value = null
}
```

- [ ] **Step 5: Render prompt**

In the backtest result area of `BuilderView.vue`, render this section above `.backtest-result-card`:

```vue
<section v-if="marketDataPrompt" class="market-data-download-prompt">
  <header>
    <strong>需要下载本地行情</strong>
    <small>{{ marketDataPrompt.estimatedRows }} 条预估K线</small>
  </header>
  <p>{{ marketDataPrompt.message }}</p>
  <p v-if="marketDataStatus" class="market-data-status">{{ marketDataStatus }}</p>
  <div class="market-data-actions">
    <button
      type="button"
      data-market-data-action="cancel"
      :disabled="isMarketDataPreparing"
      @click="cancelMarketDataDownload"
    >
      取消
    </button>
    <button
      type="button"
      data-market-data-action="prepare"
      :disabled="isMarketDataPreparing"
      @click="prepareMarketDataAndRun"
    >
      {{ isMarketDataPreparing ? '正在下载' : '下载并继续回测' }}
    </button>
  </div>
</section>
```

- [ ] **Step 6: Style prompt**

Add to `frontend/src/styles/base.css` near existing `.backtest-card` styles:

```css
.market-data-download-prompt {
  border: 1px solid rgba(116, 75, 255, 0.45);
  border-radius: 8px;
  padding: 18px;
  background: rgba(17, 13, 27, 0.94);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.28);
}

.market-data-download-prompt header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
}

.market-data-download-prompt strong {
  color: #f7f2ff;
}

.market-data-download-prompt small,
.market-data-download-prompt p {
  color: #bfb2df;
}

.market-data-status {
  margin-top: 8px;
  color: #57d8c9;
}

.market-data-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
}

.market-data-actions button {
  border: 1px solid rgba(116, 75, 255, 0.55);
  border-radius: 8px;
  padding: 10px 16px;
  color: #f7f2ff;
  background: rgba(37, 25, 57, 0.92);
  font-weight: 700;
}

.market-data-actions button[data-market-data-action="prepare"] {
  border-color: rgba(87, 216, 201, 0.62);
  background: rgba(13, 72, 66, 0.92);
}

.market-data-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
```

- [ ] **Step 7: Run frontend tests**

Run:

```bash
cd frontend
npm test -- builder-view.test.ts
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/views/BuilderView.vue frontend/src/styles/base.css frontend/tests/builder-view.test.ts
git commit -m "feat: prompt for local market data before backtests"
```

---

### Task 6: Verification And Push

**Files:**
- Verify all changed backend and frontend files.

- [ ] **Step 1: Run backend market-data and backtest tests**

Run:

```bash
cd backend
./.venv/bin/python -m pytest tests/test_market_data_provider.py tests/test_market_data_downloads.py tests/test_backtests.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full backend tests**

Run:

```bash
cd backend
./.venv/bin/python -m pytest -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend tests**

Run:

```bash
cd frontend
npm test -- builder-view.test.ts
```

Expected: PASS.

- [ ] **Step 4: Run frontend build**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 5: Browser smoke**

Run the local servers if they are not already running:

```bash
cd backend
./.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm run dev -- --port 5173
```

Open `http://127.0.0.1:5173/` in the in-app browser and verify:

- Running a backtest first checks local行情 coverage.
- Missing data shows `需要下载本地行情`.
- Cancel closes the prompt.
- Confirming starts the download waiting state.
- If the backend returns ready, the backtest result renders.

- [ ] **Step 6: Push**

Run:

```bash
git status --short
git push origin main
```

Expected: working tree clean before push, and push succeeds to `main`.
