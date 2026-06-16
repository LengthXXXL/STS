# Market Rule Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce realistic V1 market rules in backtests: A-share previous-close price limits, valid quote increments, and regular-session-only execution.

**Architecture:** Extend the market data layer so A-share cached candles carry real `previous_close` metadata, then add a focused market execution rule service between signal selection and trade cost calculation. The backtest engine asks that service whether an order can fill and uses the normalized price before applying existing slippage, cost, cash, and position logic.

**Tech Stack:** Python 3.10, FastAPI, SQLAlchemy, Pydantic, pytest, MySQL 8.0 for local dev, Vue 3 for browser verification.

---

## File Structure

- Modify `backend/app/models/market_data.py`
  - Add `previous_close` to cached K-line rows.
- Modify `backend/app/core/schema_migrations.py`
  - Add dev-only schema migration for existing local databases.
- Modify `backend/app/services/market_data_service.py`
  - Add `previous_close` to `MarketCandle`, cache read/write, and A-share EastMoney enrichment.
- Modify `backend/app/services/market_data_download_service.py`
  - Treat A-share completed ranges with missing `previous_close` metadata as not ready.
- Create `backend/app/services/market_execution_rule_service.py`
  - Own market session checks, quote-price rounding, A-share limit-up/limit-down checks, and user-facing block messages.
- Modify `backend/app/services/backtest_service.py`
  - Call the execution rule service before buy, sell, risk exit, and final close fills.
- Modify `backend/tests/test_market_data_provider.py`
  - Cover `previous_close` parsing and cache persistence.
- Modify `backend/tests/test_market_data_downloads.py`
  - Cover A-share incomplete metadata coverage and US-stock tolerance.
- Create `backend/tests/test_market_execution_rules.py`
  - Cover focused rule helper behavior.
- Modify `backend/tests/test_backtest_engine.py`
  - Cover rule enforcement inside real backtest flow.

---

## Task 1: Previous Close Schema And Cache

**Files:**
- Modify: `backend/app/models/market_data.py`
- Modify: `backend/app/core/schema_migrations.py`
- Modify: `backend/app/services/market_data_service.py`
- Test: `backend/tests/test_market_data_provider.py`

- [ ] **Step 1: Write the failing cache tests**

Add assertions to `test_cached_provider_persists_and_reuses_intraday_candles`:

```python
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
                    previous_close=10.0,
                ),
                MarketCandle(
                    time="2026-01-01 09:40",
                    open=10.25,
                    high=10.5,
                    low=10.2,
                    close=10.45,
                    volume=1500,
                    previous_close=10.0,
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
    assert first_candles[0].previous_close == 10.0
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
            row.previous_close,
        )
        for row in cached_rows
    ] == [
        ("2026-01-01 09:35", "LIVE", 10.1, 10.3, 10.0, 10.25, 1200, 10.0),
        ("2026-01-01 09:40", "LIVE", 10.25, 10.5, 10.2, 10.45, 1500, 10.0),
    ]

    cached_again = CachedMarketDataProvider(
        db_session,
        source_provider=FailingProvider(),
    ).get_intraday_candles(config)

    assert cached_again == first_candles
```

Update `test_cached_provider_ignores_unknown_source_rows_and_replaces_them` so the source candle includes `previous_close=10.0` and the final row assertion includes it:

```python
assert [(row.source, row.close, row.previous_close) for row in rows] == [
    ("LIVE", 10.25, 10.0)
]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_market_data_provider.py::test_cached_provider_persists_and_reuses_intraday_candles tests/test_market_data_provider.py::test_cached_provider_ignores_unknown_source_rows_and_replaces_them -q
```

Expected: FAIL because `MarketCandle` and `MarketKlineCache` do not expose `previous_close`.

- [ ] **Step 3: Add schema and cache support**

In `backend/app/models/market_data.py`, add:

```python
previous_close: Mapped[float | None] = mapped_column(Float, nullable=True)
```

In `backend/app/services/market_data_service.py`, extend the dataclass:

```python
@dataclass(frozen=True, slots=True)
class MarketCandle:
    time: str
    close: float
    volume: float = 0
    open: float | None = None
    high: float | None = None
    low: float | None = None
    previous_close: float | None = None
```

In `_cached_candles`, pass through the cached value:

```python
MarketCandle(
    time=row.candle_time,
    open=row.open_price if row.open_price is not None else row.close,
    high=row.high_price if row.high_price is not None else row.close,
    low=row.low_price if row.low_price is not None else row.close,
    close=row.close,
    volume=row.volume,
    previous_close=row.previous_close,
)
```

In `_cache_candles`, write:

```python
previous_close=float(candle.previous_close) if candle.previous_close is not None else None,
```

In `backend/app/core/schema_migrations.py`, add this inside the `market_kline_cache` migration block:

```python
if "previous_close" not in column_names:
    connection.execute(text("ALTER TABLE market_kline_cache ADD COLUMN previous_close FLOAT"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_market_data_provider.py::test_cached_provider_persists_and_reuses_intraday_candles tests/test_market_data_provider.py::test_cached_provider_ignores_unknown_source_rows_and_replaces_them -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/market_data.py backend/app/core/schema_migrations.py backend/app/services/market_data_service.py backend/tests/test_market_data_provider.py
git commit -m "feat: cache candle previous close"
```

---

## Task 2: A-Share Previous Close Enrichment

**Files:**
- Modify: `backend/app/services/market_data_service.py`
- Test: `backend/tests/test_market_data_provider.py`

- [ ] **Step 1: Write failing EastMoney enrichment tests**

Add these tests to `backend/tests/test_market_data_provider.py`:

```python
def test_eastmoney_provider_attaches_previous_close_from_daily_klines():
    requested_urls = []

    def fetch_json(url):
        requested_urls.append(url)
        if "klt=101" in url:
            return {
                "data": {
                    "klines": [
                        "2026-01-01,10.00,10.10,10.20,9.90,200000",
                        "2026-01-02,10.10,10.25,10.35,10.00,220000",
                    ]
                }
            }
        return {
            "data": {
                "klines": [
                    "2026-01-02 09:35,10.20,10.30,10.35,10.15,1200",
                    "2026-01-02 09:40,10.30,10.32,10.40,10.25,1500",
                ]
            }
        }

    provider = EastMoneyMarketDataProvider(fetch_json=fetch_json)

    candles = provider.get_intraday_candles(
        _config(market="A_SHARE", symbol="000001.SZ", startDate="2026-01-02")
    )

    assert any("klt=5" in url for url in requested_urls)
    assert any("klt=101" in url for url in requested_urls)
    assert [candle.previous_close for candle in candles] == [10.10, 10.10]


def test_eastmoney_provider_requires_previous_close_for_a_share():
    def fetch_json(url):
        if "klt=101" in url:
            return {"data": {"klines": ["2026-01-02,10.10,10.25,10.35,10.00,220000"]}}
        return {
            "data": {
                "klines": ["2026-01-02 09:35,10.20,10.30,10.35,10.15,1200"]
            }
        }

    provider = EastMoneyMarketDataProvider(fetch_json=fetch_json)

    with pytest.raises(MarketDataUnavailableError, match="A股行情缺少前收盘价"):
        provider.get_intraday_candles(
            _config(market="A_SHARE", symbol="000001.SZ", startDate="2026-01-02")
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_market_data_provider.py::test_eastmoney_provider_attaches_previous_close_from_daily_klines tests/test_market_data_provider.py::test_eastmoney_provider_requires_previous_close_for_a_share -q
```

Expected: FAIL because EastMoney minute candles do not fetch daily previous-close data.

- [ ] **Step 3: Implement A-share daily enrichment**

In `backend/app/services/market_data_service.py`, add imports:

```python
from datetime import date, datetime, timedelta, timezone
```

Add a constant:

```python
A_SHARE_MISSING_PREVIOUS_CLOSE_MESSAGE = "A股行情缺少前收盘价，无法执行涨跌停规则"
```

Update `EastMoneyMarketDataProvider.get_intraday_candles`:

```python
minute_payload = self.fetch_json(self._build_url(config))
daily_payload = self.fetch_json(self._build_daily_url(config))
try:
    candles = self._parse_response(minute_payload)
    return self._attach_previous_close(candles, daily_payload)
except MarketDataUnavailableError:
    raise
```

Add helper methods:

```python
def _build_daily_url(self, config: BacktestConfig) -> str:
    daily_start = date.fromisoformat(config.startDate) - timedelta(days=20)
    query = urlencode(
        {
            "secid": _eastmoney_secid(config.symbol),
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56",
            "klt": "101",
            "fqt": "1",
            "beg": _compact_date(daily_start.isoformat()),
            "end": _compact_date(config.endDate),
        }
    )
    return f"{self.base_url}?{query}"

def _attach_previous_close(
    self,
    candles: list[MarketCandle],
    daily_payload: dict[str, Any],
) -> list[MarketCandle]:
    previous_close_by_day = _previous_close_by_day_from_eastmoney_daily(daily_payload)
    enriched: list[MarketCandle] = []
    for candle in candles:
        candle_day = candle.time[:10]
        previous_close = previous_close_by_day.get(candle_day)
        if previous_close is None:
            raise MarketDataUnavailableError(A_SHARE_MISSING_PREVIOUS_CLOSE_MESSAGE)
        enriched.append(
            MarketCandle(
                time=candle.time,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                previous_close=previous_close,
            )
        )
    return enriched
```

Add module helpers:

```python
def _previous_close_by_day_from_eastmoney_daily(payload: dict[str, Any]) -> dict[str, float]:
    data = payload.get("data") if isinstance(payload, dict) else None
    klines = data.get("klines") if isinstance(data, dict) else None
    if not klines:
        raise MarketDataUnavailableError(A_SHARE_MISSING_PREVIOUS_CLOSE_MESSAGE)

    daily_closes: list[tuple[str, float]] = []
    for raw_kline in klines:
        parts = raw_kline.split(",")
        if len(parts) < 3:
            continue
        try:
            daily_closes.append((parts[0], round(float(parts[2]), 4)))
        except ValueError:
            continue

    daily_closes.sort(key=lambda item: item[0])
    result: dict[str, float] = {}
    for index in range(1, len(daily_closes)):
        current_day, _ = daily_closes[index]
        _, previous_close = daily_closes[index - 1]
        result[current_day] = previous_close
    return result
```

- [ ] **Step 4: Update existing EastMoney tests**

Existing EastMoney tests that use `fetch_json` must return a daily payload when `klt=101` is in the URL. Use this pattern:

```python
def fetch_json(url):
    requested_urls.append(url)
    if "klt=101" in url:
        return {
            "data": {
                "klines": [
                    "2025-12-31,9.90,10.00,10.10,9.80,200000",
                    "2026-01-01,10.00,10.20,10.30,9.90,220000",
                ]
            }
        }
    return {
        "data": {
            "klines": [
                "2026-01-01 09:35,10.10,10.25,10.30,10.00,1200",
                "2026-01-01 09:40,10.25,10.45678,10.50,10.20,1500",
            ]
        }
    }
```

Update expected `MarketCandle` values by adding `previous_close=10.0`.

- [ ] **Step 5: Run provider tests**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_market_data_provider.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/market_data_service.py backend/tests/test_market_data_provider.py
git commit -m "feat: enrich a share candles with previous close"
```

---

## Task 3: Coverage For Incomplete A-Share Metadata

**Files:**
- Modify: `backend/app/services/market_data_download_service.py`
- Modify: `backend/tests/test_market_data_downloads.py`
- Modify: `backend/tests/test_backtests.py`

- [ ] **Step 1: Write failing coverage tests**

Add tests to `backend/tests/test_market_data_downloads.py`:

```python
def test_coverage_requires_previous_close_for_a_share_completed_ranges(db_session):
    db_session.add(
        MarketKlineCache(
            market="A_SHARE",
            symbol="000001.SZ",
            timeframe="5m",
            source="LIVE",
            candle_time="2025-03-03 09:35",
            open_price=10.0,
            high_price=10.2,
            low_price=9.9,
            close=10.1,
            volume=1000,
            previous_close=None,
        )
    )
    db_session.add(
        MarketDataDownloadRange(
            market="A_SHARE",
            symbol="000001.SZ",
            timeframe="5m",
            start_date="2025-03-03",
            end_date="2025-03-03",
            status="completed",
            row_count=1,
            source="LIVE",
        )
    )
    db_session.commit()

    coverage = get_market_data_coverage(
        db_session,
        _market_data_request(startDate="2025-03-03", endDate="2025-03-03"),
    )

    assert coverage.ready is False
    assert [item.model_dump() for item in coverage.missingRanges] == [
        {"startDate": "2025-03-03", "endDate": "2025-03-03"}
    ]
    assert "需要下载" in coverage.message


def test_coverage_allows_us_stock_completed_ranges_without_previous_close(db_session):
    db_session.add(
        MarketKlineCache(
            market="US_STOCK",
            symbol="AAPL",
            timeframe="5m",
            source="LIVE",
            candle_time="2026-04-06 09:35",
            open_price=180.0,
            high_price=181.0,
            low_price=179.5,
            close=180.5,
            volume=1000,
            previous_close=None,
        )
    )
    db_session.add(
        MarketDataDownloadRange(
            market="US_STOCK",
            symbol="AAPL",
            timeframe="5m",
            start_date="2026-04-06",
            end_date="2026-04-06",
            status="completed",
            row_count=1,
            source="LIVE",
        )
    )
    db_session.commit()

    coverage = get_market_data_coverage(
        db_session,
        _market_data_request(
            market="US_STOCK",
            symbol="AAPL",
            startDate="2026-04-06",
            endDate="2026-04-06",
        ),
    )

    assert coverage.ready is True
    assert coverage.missingRanges == []
```

- [ ] **Step 2: Update existing test fixtures**

Where tests create A-share `MarketCandle` values for successful `prepare_market_data`, add `previous_close=10.0`. Where tests only create a completed A-share download range and expect ready, add at least one matching cached A-share candle with non-null `previous_close`.

Use this row shape:

```python
MarketKlineCache(
    market="A_SHARE",
    symbol="000001.SZ",
    timeframe="5m",
    source="LIVE",
    candle_time="2025-03-03 09:35",
    open_price=10.0,
    high_price=10.2,
    low_price=9.9,
    close=10.1,
    volume=1000,
    previous_close=9.9,
)
```

In `backend/tests/test_backtests.py`, update `_seed_market_cache`:

```python
previous_close=base_price,
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_market_data_downloads.py::test_coverage_requires_previous_close_for_a_share_completed_ranges tests/test_market_data_downloads.py::test_coverage_allows_us_stock_completed_ranges_without_previous_close -q
```

Expected: FAIL because coverage only trusts `market_data_download_ranges`.

- [ ] **Step 4: Implement metadata-aware coverage**

In `backend/app/services/market_data_download_service.py`, import `MarketKlineCache`:

```python
from app.models import MarketDataDownloadRange, MarketKlineCache
```

In `_missing_ranges`, replace the `is_covered` calculation with:

```python
is_covered = any(
    start <= cursor <= end
    and _completed_day_has_required_metadata(db, request, cursor)
    for start, end in completed_ranges
)
```

Add:

```python
def _completed_day_has_required_metadata(
    db: Session,
    request: MarketDataRequest,
    day: date,
) -> bool:
    if request.market != "A_SHARE":
        return True

    day_start = _day_start_key(day.isoformat())
    day_end = _day_end_key(day.isoformat())
    cached_rows = db.scalars(
        select(MarketKlineCache)
        .where(MarketKlineCache.market == request.market)
        .where(MarketKlineCache.symbol == request.symbol)
        .where(MarketKlineCache.timeframe == request.timeframe)
        .where(MarketKlineCache.source == LIVE_CACHE_SOURCE)
        .where(MarketKlineCache.candle_time >= day_start)
        .where(MarketKlineCache.candle_time <= day_end)
    ).all()
    return bool(cached_rows) and all(row.previous_close is not None for row in cached_rows)
```

Add local helpers to this module:

```python
def _day_start_key(date_value: str) -> str:
    return f"{date_value} 00:00"

def _day_end_key(date_value: str) -> str:
    return f"{date_value} 23:59"
```

Import the A-share metadata failure message and expose it as a user-facing prepare failure:

```python
from app.services.market_data_service import (
    A_SHARE_MISSING_PREVIOUS_CLOSE_MESSAGE,
    A_SHARE_RECENT_MINUTE_MESSAGE,
    LIVE_CACHE_SOURCE,
    US_MARKET_DATA_SOURCE_UNCONFIGURED_MESSAGE,
    CachedMarketDataProvider,
    DefaultMarketDataProvider,
    MarketCandle,
    MarketDataProvider,
    MarketDataUnavailableError,
)

USER_FACING_UNAVAILABLE_MESSAGES = {
    A_SHARE_MISSING_PREVIOUS_CLOSE_MESSAGE,
    A_SHARE_RECENT_MINUTE_MESSAGE,
    US_MARKET_DATA_SOURCE_UNCONFIGURED_MESSAGE,
}
```

- [ ] **Step 5: Run download and backtest API tests**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_market_data_downloads.py tests/test_backtests.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/market_data_download_service.py backend/tests/test_market_data_downloads.py backend/tests/test_backtests.py
git commit -m "feat: require a share previous close coverage"
```

---

## Task 4: Market Execution Rule Service

**Files:**
- Create: `backend/app/services/market_execution_rule_service.py`
- Test: `backend/tests/test_market_execution_rules.py`

- [ ] **Step 1: Write focused failing tests**

Create `backend/tests/test_market_execution_rules.py`:

```python
from app.services.market_data_service import MarketCandle
from app.services.market_execution_rule_service import (
    is_regular_session_candle,
    normalize_order_price,
    validate_market_order,
)
from app.services.market_rule_service import get_market_rule


def test_normalize_order_price_rounds_buy_up_and_sell_down():
    assert normalize_order_price("BUY", 10.001) == 10.01
    assert normalize_order_price("SELL", 10.009) == 10.00
    assert normalize_order_price("BUY", 10.01) == 10.01
    assert normalize_order_price("SELL", 10.01) == 10.01


def test_a_share_buy_above_limit_up_is_blocked():
    result = validate_market_order(
        market_rule=get_market_rule("A_SHARE"),
        candle=MarketCandle(
            time="2026-01-02 09:35",
            open=11.02,
            high=11.02,
            low=11.02,
            close=11.02,
            previous_close=10.0,
        ),
        side="BUY",
        execution_price=11.02,
        quantity=100,
    )

    assert result.allowed is False
    assert result.rule == "涨跌停"
    assert "高于涨停价 11.00" in result.reason


def test_a_share_sell_below_limit_down_is_blocked():
    result = validate_market_order(
        market_rule=get_market_rule("A_SHARE"),
        candle=MarketCandle(
            time="2026-01-02 09:35",
            open=8.98,
            high=8.98,
            low=8.98,
            close=8.98,
            previous_close=10.0,
        ),
        side="SELL",
        execution_price=8.98,
        quantity=100,
    )

    assert result.allowed is False
    assert result.rule == "涨跌停"
    assert "低于跌停价 9.00" in result.reason


def test_a_share_missing_previous_close_is_blocked():
    result = validate_market_order(
        market_rule=get_market_rule("A_SHARE"),
        candle=MarketCandle(time="2026-01-02 09:35", close=10.0),
        side="BUY",
        execution_price=10.0,
        quantity=100,
    )

    assert result.allowed is False
    assert result.rule == "前收盘价"
    assert result.reason == "行情缺少前收盘价，无法执行 A 股涨跌停规则"


def test_regular_session_checks_a_share_lunch_break_and_us_regular_hours():
    assert is_regular_session_candle(
        get_market_rule("A_SHARE"),
        MarketCandle(time="2026-01-02 11:30", close=10.0),
    ) is True
    assert is_regular_session_candle(
        get_market_rule("A_SHARE"),
        MarketCandle(time="2026-01-02 11:31", close=10.0),
    ) is False
    assert is_regular_session_candle(
        get_market_rule("US_STOCK"),
        MarketCandle(time="2026-01-02 16:00", close=180.0),
    ) is True
    assert is_regular_session_candle(
        get_market_rule("US_STOCK"),
        MarketCandle(time="2026-01-02 16:01", close=180.0),
    ) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_market_execution_rules.py -q
```

Expected: FAIL because `market_execution_rule_service.py` does not exist.

- [ ] **Step 3: Create the rule service**

Create `backend/app/services/market_execution_rule_service.py`:

```python
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from typing import Literal

from app.schemas.market_rule import MarketRuleResponse
from app.services.market_data_service import MarketCandle

TradeSide = Literal["BUY", "SELL"]
PRICE_TICK = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class MarketOrderValidation:
    allowed: bool
    price: float
    reason: str = ""
    rule: str = ""


def validate_market_order(
    *,
    market_rule: MarketRuleResponse,
    candle: MarketCandle,
    side: TradeSide,
    execution_price: float,
    quantity: int,
) -> MarketOrderValidation:
    normalized_price = normalize_order_price(side, execution_price)
    if quantity <= 0:
        return MarketOrderValidation(
            allowed=False,
            price=normalized_price,
            reason="委托数量必须大于 0",
            rule="数量",
        )
    if not is_regular_session_candle(market_rule, candle):
        return MarketOrderValidation(
            allowed=False,
            price=normalized_price,
            reason="不在常规交易时段内，订单未触发",
            rule="交易时段",
        )
    if market_rule.market == "A_SHARE":
        return _validate_a_share_price_limit(
            market_rule=market_rule,
            candle=candle,
            side=side,
            normalized_price=normalized_price,
        )
    return MarketOrderValidation(allowed=True, price=normalized_price)


def normalize_order_price(side: TradeSide, price: float) -> float:
    rounding = ROUND_CEILING if side == "BUY" else ROUND_FLOOR
    return float((Decimal(str(price)) / PRICE_TICK).to_integral_value(rounding=rounding) * PRICE_TICK)


def is_regular_session_candle(market_rule: MarketRuleResponse, candle: MarketCandle) -> bool:
    current_time = candle.time[-5:]
    return any(session.start <= current_time <= session.end for session in market_rule.sessions)


def _validate_a_share_price_limit(
    *,
    market_rule: MarketRuleResponse,
    candle: MarketCandle,
    side: TradeSide,
    normalized_price: float,
) -> MarketOrderValidation:
    if candle.previous_close is None:
        return MarketOrderValidation(
            allowed=False,
            price=normalized_price,
            reason="行情缺少前收盘价，无法执行 A 股涨跌停规则",
            rule="前收盘价",
        )

    limit_percent = Decimal(str(market_rule.price_limit_percent or 0))
    previous_close = Decimal(str(candle.previous_close))
    limit_up = _price_limit(previous_close * (Decimal("1") + limit_percent / Decimal("100")))
    limit_down = _price_limit(previous_close * (Decimal("1") - limit_percent / Decimal("100")))
    price = Decimal(str(normalized_price))

    if side == "BUY" and price > limit_up:
        return MarketOrderValidation(
            allowed=False,
            price=normalized_price,
            reason=f"A股涨停限制：买入价 {normalized_price:.2f} 高于涨停价 {float(limit_up):.2f}",
            rule="涨跌停",
        )
    if side == "SELL" and price < limit_down:
        return MarketOrderValidation(
            allowed=False,
            price=normalized_price,
            reason=f"A股跌停限制：卖出价 {normalized_price:.2f} 低于跌停价 {float(limit_down):.2f}",
            rule="涨跌停",
        )
    return MarketOrderValidation(allowed=True, price=normalized_price)


def _price_limit(value: Decimal) -> Decimal:
    return value.quantize(PRICE_TICK, rounding=ROUND_HALF_UP)
```

Run `ruff` after adding the file. If the one-line quantity validation exceeds the line length rule, split it into a multiline constructor.

- [ ] **Step 4: Run focused tests**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_market_execution_rules.py -q
./.venv/bin/python -m ruff check app/services/market_execution_rule_service.py tests/test_market_execution_rules.py
```

Expected: PASS and `All checks passed!`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/market_execution_rule_service.py backend/tests/test_market_execution_rules.py
git commit -m "feat: add market execution rules"
```

---

## Task 5: Backtest Engine Enforcement

**Files:**
- Modify: `backend/app/services/backtest_service.py`
- Modify: `backend/tests/test_backtest_engine.py`

- [ ] **Step 1: Write failing engine tests**

Add tests to `backend/tests/test_backtest_engine.py`:

```python
def test_engine_blocks_a_share_buy_above_limit_up():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            }
        ],
        initial_cash=10000,
        market="A_SHARE",
    )
    candles = [
        MarketCandle(time="2026-01-02 09:35", open=10.8, high=10.9, low=10.7, close=10.8, previous_close=10.0),
        MarketCandle(time="2026-01-02 09:40", open=11.02, high=11.02, low=11.02, close=11.02, previous_close=10.0),
    ]

    result = run_backtest_with_candles(request, candles)

    assert result.trades == []
    blocked = [item for item in result.timeline if item.event_type == "ORDER_BLOCKED"]
    assert len(blocked) == 1
    assert blocked[0].side == "BUY"
    assert blocked[0].rule == "涨跌停"
    assert "高于涨停价 11.00" in blocked[0].description


    def test_engine_blocks_a_share_sell_below_limit_down_after_t_plus_one():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
            {
                "id": "stop-loss-1",
                "type": "stop-loss",
                "label": "止损",
                "x": 160,
                "y": 0,
                "params": {"lossRate": "11", "sellPercent": "100"},
            },
        ],
        initial_cash=10000,
        market="A_SHARE",
    )
    candles = [
        MarketCandle(time="2026-01-02 09:35", open=10.0, high=10.1, low=9.9, close=10.0, previous_close=10.0),
        MarketCandle(time="2026-01-05 09:35", open=10.0, high=10.1, low=9.9, close=10.0, previous_close=10.0),
        MarketCandle(time="2026-01-06 09:35", open=8.9, high=9.0, low=8.8, close=8.9, previous_close=10.0),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY"]
    blocked = [item for item in result.timeline if item.event_type == "ORDER_BLOCKED"]
    assert len(blocked) == 1
    assert blocked[0].side == "SELL"
    assert blocked[0].rule == "涨跌停"
    assert "低于跌停价 9.00" in blocked[0].description


def test_engine_skips_non_session_candles_before_triggering_orders():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            }
        ],
        initial_cash=10000,
        market="US_STOCK",
    )
    candles = [
        MarketCandle(time="2026-01-02 08:00", open=10, high=10.1, low=9.9, close=10),
        MarketCandle(time="2026-01-02 09:35", open=10.2, high=10.3, low=10.1, close=10.2),
    ]

    result = run_backtest_with_candles(request, candles)

    assert result.trades == []
    assert result.timeline == []
```

Update existing A-share engine candles by adding `previous_close` values that keep them within price limits:

```python
MarketCandle(time="2026-01-01 09:35", open=10.0, high=10.1, low=9.9, close=10.0, previous_close=10.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_backtest_engine.py::test_engine_blocks_a_share_buy_above_limit_up tests/test_backtest_engine.py::test_engine_blocks_a_share_sell_below_limit_down_after_t_plus_one tests/test_backtest_engine.py::test_engine_skips_non_session_candles_before_triggering_orders -q
```

Expected: FAIL because the engine does not call market execution rules.

- [ ] **Step 3: Import rule helpers**

In `backend/app/services/backtest_service.py`, add:

```python
from app.services.market_execution_rule_service import (
    is_regular_session_candle,
    validate_market_order,
)
```

- [ ] **Step 4: Skip non-session signal evaluation**

Near the start of the candle loop, after `sold_this_candle = False`, add:

```python
if not is_regular_session_candle(market_rule, candle):
    equity_curve.append(
        EquityPoint(
            time=candle.time,
            equity=round(cash + position.quantity * candle.close, 2),
        )
    )
    if position.quantity > 0:
        position.holding_bars += 1
    continue
```

This prevents premarket, lunch-break, and after-hours K lines from creating signals.

- [ ] **Step 5: Validate buy orders before cost calculation**

In `_fill_buy_order`, keep the existing affordability check, then validate before `calculate_trade_fill`:

```python
validation = validate_market_order(
    market_rule=market_rule,
    candle=candle,
    side="BUY",
    execution_price=execution_price,
    quantity=buy_quantity,
)
if not validation.allowed:
    timeline.append(
        _timeline_order_blocked(
            sequence=len(timeline),
            time=candle.time,
            side="BUY",
            price=validation.price,
            quantity=buy_quantity,
            reason=validation.reason,
            rule=validation.rule,
            node=buy_node,
        )
    )
    return cash
```

Then call costs with the normalized price:

```python
fill = calculate_trade_fill(
    side="BUY",
    base_price=validation.price,
    quantity=buy_quantity,
    market_rule=market_rule,
)
```

- [ ] **Step 6: Validate sell orders after T+1 and before cost calculation**

In `_fill_exit_rule`, leave the existing `_can_sell_position` block before market validation. After `sell_quantity <= 0` returns, add:

```python
validation = validate_market_order(
    market_rule=market_rule,
    candle=candle,
    side="SELL",
    execution_price=execution_price,
    quantity=sell_quantity,
)
if not validation.allowed:
    events.append(
        BacktestEvent(
            time=candle.time,
            eventType="BLOCKED_ORDER",
            side="SELL",
            price=validation.price,
            quantity=sell_quantity,
            reason=validation.reason,
            rule=validation.rule,
        )
    )
    timeline.append(
        _timeline_order_blocked(
            sequence=len(timeline),
            time=candle.time,
            side="SELL",
            price=validation.price,
            quantity=sell_quantity,
            reason=validation.reason,
            rule=validation.rule,
            node=exit_rule.node,
        )
    )
    return cash, False, False
```

Then call costs with:

```python
fill = calculate_trade_fill(
    side="SELL",
    base_price=validation.price,
    quantity=sell_quantity,
    market_rule=market_rule,
)
```

- [ ] **Step 7: Validate final close**

Before using final-close blocking with `node=None`, loosen `_timeline_order_blocked` to accept an optional node:

```python
def _timeline_order_blocked(
    *,
    sequence: int,
    time: str,
    side: str,
    price: float,
    quantity: int,
    reason: str,
    rule: str,
    node: StrategyNode | None,
) -> BacktestTimelineItem:
    return BacktestTimelineItem(
        id=f"order-blocked-{sequence}",
        time=time,
        eventType="ORDER_BLOCKED",
        title="买入信号被拦截" if side == "BUY" else "卖出信号被拦截",
        description=reason,
        severity="warning",
        side=side,
        price=price,
        quantity=quantity,
        rule=rule,
        nodeId=node.id if node else None,
        nodeType=node.type if node else None,
        nodeLabel=node.label if node else None,
    )
```

Update `_sell_remaining_position` to return `(cash, filled)` and accept `timeline` plus `node`:

```python
def _sell_remaining_position(
    *,
    cash: float,
    position: Position,
    candle: MarketCandle,
    market_rule: MarketRuleResponse,
    trades: list[BacktestTrade],
    timeline: list[BacktestTimelineItem],
    reason: str,
    node: StrategyNode | None,
) -> tuple[float, bool]:
    validation = validate_market_order(
        market_rule=market_rule,
        candle=candle,
        side="SELL",
        execution_price=candle.close,
        quantity=position.quantity,
    )
    if not validation.allowed:
        timeline.append(
            _timeline_order_blocked(
                sequence=len(timeline),
                time=candle.time,
                side="SELL",
                price=validation.price,
                quantity=position.quantity,
                reason=validation.reason,
                rule=validation.rule,
                node=node,
            )
        )
        return cash, False

    fill = calculate_trade_fill(
        side="SELL",
        base_price=validation.price,
        quantity=position.quantity,
        market_rule=market_rule,
    )
    trades.append(
        BacktestTrade(
            time=candle.time,
            side="SELL",
            price=fill.price,
            quantity=position.quantity,
            reason=reason,
            grossAmount=fill.gross_amount,
            costAmount=fill.cost_amount,
            slippageAmount=fill.slippage_amount,
            netCashChange=fill.net_cash_change,
            costBreakdown=fill.cost_breakdown,
        )
    )
    return round(cash + fill.net_cash_change, 2), True
```

At the final close call site, only append `TRADE_FILLED`, `POSITION_CLOSED`, and mutate the position when `filled` is true.

- [ ] **Step 8: Run engine tests**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_backtest_engine.py -q
./.venv/bin/python -m ruff check app/services/backtest_service.py tests/test_backtest_engine.py
```

Expected: PASS and `All checks passed!`.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/backtest_service.py backend/tests/test_backtest_engine.py
git commit -m "feat: enforce market rules in backtests"
```

---

## Task 6: Full Verification And Push

**Files:**
- Verify: backend and frontend test suites
- Verify: browser backtest flow at `http://127.0.0.1:5173/`

- [ ] **Step 1: Run full backend tests**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest -q
./.venv/bin/python -m ruff check app tests
```

Expected: all tests pass and `All checks passed!`.

- [ ] **Step 2: Run frontend tests and build**

Run:

```bash
cd /Users/zluo/Project/STS/frontend
npm test -- --run
npm run build
```

Expected: Vitest passes and Vite build succeeds.

- [ ] **Step 3: Browser smoke test**

Use the in-app browser at `http://127.0.0.1:5173/`:

1. Open the builder page.
2. Create or load a strategy with a buy block.
3. Use an A-share symbol and a prepared local data range.
4. Run backtest.
5. Confirm the result modal still opens.
6. Confirm blocked market-rule events appear in the timeline when the seeded data violates price limits or trading sessions.

- [ ] **Step 4: Push all implementation commits**

Run:

```bash
cd /Users/zluo/Project/STS
git status --short
git push origin main
```

Expected: working tree is clean before push, and remote `main` receives the new commits.
