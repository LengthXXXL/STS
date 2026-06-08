# Backtest Execution Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persisted and user-visible backtest execution timeline that explains trades, blocked orders, cooldown starts, and position closes.

**Architecture:** Extend the existing backtest response with a `timeline` list while keeping `trades`, `events`, and `equityCurve` unchanged. Persist timeline rows next to existing trade/event/equity rows, then render the same timeline component style in Builder and Personal Space.

**Tech Stack:** Python 3.10, FastAPI, Pydantic, SQLAlchemy, MySQL/SQLite tests, Vue 3, TypeScript, Vitest.

---

## File Map

- Modify `backend/app/schemas/backtest.py`: add `BacktestTimelineItem` and `timeline` fields.
- Modify `backend/app/models/backtest.py`: add `BacktestTimelineRecord` table and relationship.
- Modify `backend/app/models/__init__.py`: export `BacktestTimelineRecord`.
- Modify `backend/app/services/backtest_service.py`: build timeline during backtest execution.
- Modify `backend/app/services/backtest_record_service.py`: save and load timeline records.
- Modify `backend/tests/test_backtest_engine.py`: assert timeline events for buy/sell/blocked/cooldown.
- Modify `backend/tests/test_backtests.py`: assert API response and persisted detail include `timeline`.
- Modify `frontend/src/views/BuilderView.vue`: type and render timeline in run result.
- Modify `frontend/src/views/PersonalSpaceView.vue`: type and render timeline in saved backtest detail.
- Modify `frontend/src/styles/base.css`: add timeline visual style.
- Modify `frontend/tests/builder-view.test.ts`: assert Builder timeline display.
- Modify `frontend/tests/personal-space-view.test.ts`: assert Personal Space timeline display and legacy safety.

## Task 1: Backend Timeline Schema and Engine

**Files:**
- Modify: `backend/app/schemas/backtest.py`
- Modify: `backend/app/services/backtest_service.py`
- Test: `backend/tests/test_backtest_engine.py`

- [ ] **Step 1: Write failing engine tests**

Add assertions like:

```python
assert [item.event_type for item in result.timeline] == ["TRADE_FILLED", "TRADE_FILLED"]
assert result.timeline[0].title == "买入成交"
assert result.timeline[0].nodeLabel == "买入"
assert result.timeline[1].title == "卖出成交"
assert result.timeline[1].description == "止盈触发"
```

For A-share blocked orders:

```python
blocked_items = [item for item in result.timeline if item.event_type == "ORDER_BLOCKED"]
assert blocked_items[0].rule == "T+1"
assert blocked_items[0].title == "卖出信号被拦截"
assert blocked_items[0].description == "A股 T+1 规则限制，当日买入持仓不可卖出"
```

For stop-loss cooldown:

```python
cooldown_items = [item for item in result.timeline if item.event_type == "COOLDOWN_STARTED"]
assert cooldown_items[0].title == "进入冷却"
assert cooldown_items[0].details == {"durationBars": 2, "reason": "止损后冷却"}
```

- [ ] **Step 2: Run the focused backend test and verify RED**

Run:

```bash
backend/.venv/bin/pytest backend/tests/test_backtest_engine.py -q
```

Expected: fail because `BacktestRunResponse` has no `timeline`.

- [ ] **Step 3: Add schema and engine implementation**

Add `BacktestTimelineItem`:

```python
class BacktestTimelineItem(BaseModel):
    id: str
    time: str
    event_type: Literal[
        "TRADE_FILLED",
        "ORDER_BLOCKED",
        "COOLDOWN_STARTED",
        "POSITION_CLOSED",
    ] = Field(alias="eventType")
    title: str
    description: str
    severity: Literal["info", "success", "warning", "danger"]
    side: Literal["BUY", "SELL"] | None = None
    price: float | None = None
    quantity: int | None = None
    rule: str | None = None
    node_id: str | None = Field(default=None, alias="nodeId")
    node_type: str | None = Field(default=None, alias="nodeType")
    node_label: str | None = Field(default=None, alias="nodeLabel")
    details: dict[str, int | float | str | bool] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)
```

Add `timeline: list[BacktestTimelineItem] = Field(default_factory=list)` to both response schemas.

In `run_backtest_with_candles()`, maintain `timeline: list[BacktestTimelineItem] = []` and append items through helper functions for buy/sell/block/cooldown/close.

- [ ] **Step 4: Run focused backend tests and verify GREEN**

Run:

```bash
backend/.venv/bin/pytest backend/tests/test_backtest_engine.py -q
```

Expected: all tests in `test_backtest_engine.py` pass.

## Task 2: Persist Timeline Records

**Files:**
- Modify: `backend/app/models/backtest.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/services/backtest_record_service.py`
- Test: `backend/tests/test_backtests.py`

- [ ] **Step 1: Write failing API persistence test**

Extend `test_run_backtest_persists_owned_task_trades_and_equity_curve`:

```python
assert payload["timeline"]
detail = client.get(f"/api/backtests/{task.id}", headers=auth_headers(token))
assert detail.status_code == 200
detail_payload = detail.json()
assert detail_payload["timeline"] == payload["timeline"]
```

- [ ] **Step 2: Run focused API tests and verify RED**

Run:

```bash
backend/.venv/bin/pytest backend/tests/test_backtests.py -q
```

Expected: fail because timeline is not persisted or returned from detail yet.

- [ ] **Step 3: Add persistence model and service mapping**

Add `BacktestTimelineRecord` with:

```python
__tablename__ = "backtest_timeline_items"
id, task_id, sequence, item_id, item_time, event_type, title, description, severity,
side, price, quantity, rule, node_id, node_type, node_label, details_json
```

Add relationship on `BacktestTask`:

```python
timeline_items = relationship(
    "BacktestTimelineRecord",
    back_populates="task",
    cascade="all, delete-orphan",
    order_by="BacktestTimelineRecord.sequence",
)
```

In `save_backtest_result()`, loop through `result.timeline` and save every item.

In `get_backtest_record()`, map saved rows back to `BacktestTimelineItem`.

- [ ] **Step 4: Run focused API tests and verify GREEN**

Run:

```bash
backend/.venv/bin/pytest backend/tests/test_backtests.py -q
```

Expected: all tests in `test_backtests.py` pass.

## Task 3: Frontend Timeline Rendering

**Files:**
- Modify: `frontend/src/views/BuilderView.vue`
- Modify: `frontend/src/views/PersonalSpaceView.vue`
- Modify: `frontend/src/styles/base.css`
- Test: `frontend/tests/builder-view.test.ts`
- Test: `frontend/tests/personal-space-view.test.ts`

- [ ] **Step 1: Write failing frontend tests**

Builder test result mock should include:

```ts
timeline: [
  {
    id: 'trade-buy-0',
    time: '2026-01-05 10:30',
    eventType: 'TRADE_FILLED',
    title: '买入成交',
    description: '买入积木触发',
    severity: 'success',
    side: 'BUY',
    price: 10.2,
    quantity: 1900,
    rule: null,
    nodeId: 'buy-1',
    nodeType: 'buy',
    nodeLabel: '买入',
    details: {}
  }
]
```

Then assert:

```ts
expect(wrapper.find('.backtest-timeline').text()).toContain('策略执行时间线')
expect(wrapper.find('.backtest-timeline').text()).toContain('买入成交')
expect(wrapper.find('.backtest-timeline').text()).toContain('买入积木触发')
```

Personal Space should assert the same in the detail panel and add one legacy detail fixture with `timeline: []`.

- [ ] **Step 2: Run focused frontend tests and verify RED**

Run:

```bash
cd frontend && npm test -- --run builder-view.test.ts personal-space-view.test.ts
```

Expected: fail because `.backtest-timeline` is not rendered.

- [ ] **Step 3: Add frontend types and timeline sections**

Add TypeScript interface:

```ts
interface BacktestTimelineItem {
  id: string
  time: string
  eventType: 'TRADE_FILLED' | 'ORDER_BLOCKED' | 'COOLDOWN_STARTED' | 'POSITION_CLOSED'
  title: string
  description: string
  severity: 'info' | 'success' | 'warning' | 'danger'
  side?: 'BUY' | 'SELL' | null
  price?: number | null
  quantity?: number | null
  rule?: string | null
  nodeId?: string | null
  nodeType?: string | null
  nodeLabel?: string | null
  details: Record<string, string | number | boolean>
}
```

Render section:

```vue
<section v-if="backtestRunResult.timeline.length" class="backtest-timeline">
  <header>
    <strong>策略执行时间线</strong>
    <small>{{ backtestRunResult.timeline.length }} 条记录</small>
  </header>
  <ol>
    <li v-for="item in backtestRunResult.timeline" :key="item.id" :class="`timeline-item--${item.severity}`">
      <div>
        <b>{{ item.title }}</b>
        <span>{{ item.time }}</span>
      </div>
      <p>{{ item.description }}</p>
      <small>{{ timelineMeta(item) }}</small>
    </li>
  </ol>
</section>
```

Use equivalent markup in Personal Space.

- [ ] **Step 4: Run focused frontend tests and verify GREEN**

Run:

```bash
cd frontend && npm test -- --run builder-view.test.ts personal-space-view.test.ts
```

Expected: both test files pass.

## Task 4: Full Verification and Push

**Files:**
- All modified files from Tasks 1-3.

- [ ] **Step 1: Run backend full test suite**

```bash
backend/.venv/bin/pytest backend/tests -q
```

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend full test suite**

```bash
cd frontend && npm test -- --run
```

Expected: all frontend tests pass.

- [ ] **Step 3: Run frontend build**

```bash
cd frontend && npm run build
```

Expected: `vue-tsc && vite build` succeeds.

- [ ] **Step 4: Browser/API smoke check**

Run a real Builder backtest with buy + take-profit on A-share data and verify:

- “策略执行时间线” appears.
- “买入成交” appears.
- “卖出信号被拦截” appears when T+1 blocks selling.

- [ ] **Step 5: Commit and push**

```bash
git add backend frontend docs/superpowers/plans/2026-06-08-backtest-execution-timeline.md
git commit -m "feat: add backtest execution timeline" \
  -m "Updated: 2026-06-08 HH:MM CST" \
  -m "- Add timeline response schema and persistence" \
  -m "- Generate timeline entries for trades, blocked orders, cooldown, and closes" \
  -m "- Render timeline in builder and personal-space backtest results"
git push origin main
```
