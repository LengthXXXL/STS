# Personal Space MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first usable STS personal space with overview metrics, saved strategies, and owned backtest records.

**Architecture:** Backend exposes owner-scoped backtest list/detail APIs from existing persisted `backtest_tasks`, `backtest_trades`, and `backtest_equity_points` tables. Frontend refactors `PersonalSpaceView.vue` into a tabbed workspace with shared loading/error states and compact operational lists. The existing saved strategy API remains unchanged.

**Tech Stack:** Python 3.10, FastAPI, SQLAlchemy, MySQL/SQLite tests, Vue 3, Pinia, Axios, Vitest.

---

### Task 1: Backtest Record API

**Files:**
- Modify: `backend/app/schemas/backtest.py`
- Create: `backend/app/services/backtest_record_service.py` updates
- Modify: `backend/app/api/backtests.py`
- Test: `backend/tests/test_backtests.py`

- [ ] **Step 1: Write failing tests for owner-scoped backtest list/detail**

Add tests that:
- register Alice and Bob
- Alice runs a backtest
- Bob cannot see Alice's backtest
- Alice can list and detail her own backtest

- [ ] **Step 2: Run backend backtest tests**

Run: `./.venv/bin/python -m pytest tests/test_backtests.py -q`
Expected: fail because `GET /api/backtests` and `GET /api/backtests/{id}` do not exist.

- [ ] **Step 3: Add response schemas**

Add `BacktestRecordListItem`, `BacktestRecordListResponse`, and `BacktestRecordDetailResponse` in `backend/app/schemas/backtest.py`.

- [ ] **Step 4: Add list/detail service functions**

Add `list_backtest_records(db, owner, keyword, page, page_size)` and `get_backtest_record(db, owner, task_id)` to `backend/app/services/backtest_record_service.py`.

- [ ] **Step 5: Add API routes**

Add:
- `GET /api/backtests`
- `GET /api/backtests/{task_id}`

Both require login and only return the current user's records.

- [ ] **Step 6: Verify backend tests**

Run: `./.venv/bin/python -m pytest tests/test_backtests.py -q`
Expected: pass.

### Task 2: Personal Space Tabs And Overview

**Files:**
- Modify: `frontend/src/views/PersonalSpaceView.vue`
- Modify: `frontend/tests/personal-space-view.test.ts`
- Modify: `frontend/src/styles/base.css`

- [ ] **Step 1: Write failing frontend test for tabs and overview**

Test should expect:
- `概览`, `我的策略`, `我的回测` tabs
- overview metrics for strategy count and backtest count
- existing strategy list still loads from `/strategies`

- [ ] **Step 2: Run frontend test**

Run: `npm test -- personal-space-view.test.ts`
Expected: fail because current page has no tabs/overview.

- [ ] **Step 3: Implement tabbed layout**

Refactor `PersonalSpaceView.vue` with:
- `activeTab`
- `strategies`
- `backtests`
- overview computed metrics
- current strategy list behavior preserved

- [ ] **Step 4: Style compact workspace layout**

Add CSS for:
- `.space-tabs`
- `.space-overview-grid`
- `.space-table`
- `.space-detail-panel`

- [ ] **Step 5: Verify frontend test**

Run: `npm test -- personal-space-view.test.ts`
Expected: pass.

### Task 3: Backtest List And Detail In Personal Space

**Files:**
- Modify: `frontend/src/views/PersonalSpaceView.vue`
- Modify: `frontend/tests/personal-space-view.test.ts`

- [ ] **Step 1: Write failing frontend test for backtest tab**

Test should:
- mock `/backtests`
- click `我的回测`
- show symbol, timeframe, return, drawdown, trade count
- click a record and fetch `/backtests/{id}`
- show trades and equity points

- [ ] **Step 2: Run frontend test**

Run: `npm test -- personal-space-view.test.ts`
Expected: fail because backtest tab is not implemented yet.

- [ ] **Step 3: Implement backtest list and detail loading**

Add:
- `loadBacktests`
- `openBacktest`
- detail panel with summary, trades, and latest equity

- [ ] **Step 4: Verify frontend test**

Run: `npm test -- personal-space-view.test.ts`
Expected: pass.

### Task 4: Full Verification

**Files:**
- All changed backend and frontend files

- [ ] **Step 1: Run backend tests and lint**

Run:
- `cd backend && ./.venv/bin/python -m pytest -q`
- `cd backend && ./.venv/bin/python -m ruff check .`

- [ ] **Step 2: Run frontend tests and build**

Run:
- `cd frontend && npm test`
- `cd frontend && npm run build`

- [ ] **Step 3: Browser verification**

Open `http://127.0.0.1:5173/space`, verify:
- tabs switch
- strategy list still works
- backtest tab renders after login data is available
- no console errors

- [ ] **Step 4: Commit**

Commit message: `feat: add personal space backtest records`

