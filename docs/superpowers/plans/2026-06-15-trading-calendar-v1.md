# Trading Calendar V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a backend trading calendar so market data coverage ignores real A-share and US stock full-day holidays instead of only weekends.

**Architecture:** Create a focused `trading_calendar_service.py` with static 2025/2026 holiday sets and small query helpers. Wire `market_data_download_service.py` to use those helpers for missing-range calculation, row estimates, and candle coverage grouping.

**Tech Stack:** Python 3.10, FastAPI, Pydantic, SQLAlchemy, pytest.

---

### Task 1: Add Trading Calendar Service

**Files:**
- Create: `backend/app/services/trading_calendar_service.py`
- Test: `backend/tests/test_trading_calendar_service.py`

- [ ] **Step 1: Write failing tests**

```python
from datetime import date

from app.services.trading_calendar_service import (
    count_trading_days,
    has_missing_trading_day,
    is_trading_day,
)


def test_a_share_holidays_are_not_trading_days():
    assert is_trading_day("A_SHARE", date(2026, 2, 16)) is False
    assert is_trading_day("A_SHARE", date(2026, 2, 24)) is True


def test_us_stock_holidays_are_not_trading_days():
    assert is_trading_day("US_STOCK", date(2026, 4, 3)) is False
    assert is_trading_day("US_STOCK", date(2026, 4, 6)) is True


def test_missing_trading_day_skips_holiday_breaks_but_keeps_regular_weekdays():
    assert has_missing_trading_day("A_SHARE", date(2026, 2, 13), date(2026, 2, 24)) is False
    assert has_missing_trading_day("US_STOCK", date(2026, 4, 2), date(2026, 4, 6)) is False
    assert has_missing_trading_day("US_STOCK", date(2026, 3, 2), date(2026, 3, 6)) is True


def test_count_trading_days_uses_market_holidays():
    assert count_trading_days("A_SHARE", date(2026, 2, 15), date(2026, 2, 24)) == 1
    assert count_trading_days("US_STOCK", date(2026, 4, 3), date(2026, 4, 6)) == 1
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_trading_calendar_service.py -q`

Expected: FAIL because `app.services.trading_calendar_service` does not exist.

- [ ] **Step 3: Implement service**

Create static holiday sets for A-share and US stock, plus the three helper functions.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_trading_calendar_service.py -q`

Expected: `4 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/app/services/trading_calendar_service.py backend/tests/test_trading_calendar_service.py
git commit -m "feat: add trading calendar service"
```

### Task 2: Wire Market Data Coverage to Trading Calendar

**Files:**
- Modify: `backend/app/services/market_data_download_service.py`
- Modify: `backend/tests/test_market_data_downloads.py`

- [ ] **Step 1: Write failing market-data tests**

Add tests showing:

```python
def test_prepare_market_data_ignores_a_share_spring_festival_gap(db_session):
    class FestivalProvider:
        def get_intraday_candles(self, config):
            assert config.startDate == "2026-02-13"
            assert config.endDate == "2026-02-24"
            return [
                MarketCandle(time="2026-02-13 09:35", open=10, high=10.2, low=9.9, close=10.1, volume=1000),
                MarketCandle(time="2026-02-24 09:35", open=10.1, high=10.3, low=10.0, close=10.2, volume=1000),
            ]

    request = _market_data_request(startDate="2026-02-13", endDate="2026-02-24")
    response = prepare_market_data(db_session, request, source_provider=FestivalProvider())

    assert response.ready is True
    assert response.missingRanges == []


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
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_market_data_downloads.py -q`

Expected: FAIL because market data coverage still uses weekend-only logic.

- [ ] **Step 3: Wire service**

Replace local weekday checks with `is_trading_day`, `count_trading_days`, and `has_missing_trading_day`.

- [ ] **Step 4: Run focused tests**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_market_data_downloads.py tests/test_trading_calendar_service.py -q`

Expected: all pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/app/services/market_data_download_service.py backend/tests/test_market_data_downloads.py
git commit -m "feat: use trading calendar for market data coverage"
```

### Task 3: Final Verification

**Files:**
- No new files expected.

- [ ] **Step 1: Run backend full suite**

Run: `cd backend && ./.venv/bin/python -m pytest -q`

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend full suite**

Run: `cd frontend && npm test`

Expected: all frontend tests pass.

- [ ] **Step 3: Build frontend**

Run: `cd frontend && npm run build`

Expected: build succeeds.

- [ ] **Step 4: Push**

Run:

```bash
git status --short
git push origin main
```

Expected: clean worktree, push succeeds.
