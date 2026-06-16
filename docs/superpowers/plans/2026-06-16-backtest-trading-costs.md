# Backtest Trading Costs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add market-specific transaction costs and conservative slippage to STS backtests, then show those costs in trade results.

**Architecture:** Keep the strategy JSON unchanged and insert a focused cost calculation layer between signal execution and cash/position mutation. Market fee assumptions live in `market_rule_service`, the backtest engine consumes them through a new cost helper, persistence stores the expanded trade fields, and the frontend displays cost assumptions plus per-trade costs.

**Tech Stack:** Python 3.10, FastAPI, SQLAlchemy, Pydantic, pytest, Vue 3, TypeScript, Vitest.

---

## File Structure

- Create `backend/app/services/trading_cost_service.py`
  - Owns cost profile validation, slippage price adjustment, cost breakdown calculation, and buy quantity affordability.
- Modify `backend/app/schemas/market_rule.py`
  - Adds `MarketCostProfile` to `MarketRuleResponse`.
- Modify `backend/app/services/market_rule_service.py`
  - Adds A-share and US stock default cost profiles.
- Modify `backend/app/schemas/backtest.py`
  - Adds cost fields to `BacktestTrade`.
- Modify `backend/app/services/backtest_service.py`
  - Uses `trading_cost_service` when filling buy, sell, clear, risk exits, and final close.
- Modify `backend/app/models/backtest.py`
  - Adds cost columns to `BacktestTradeRecord`.
- Modify `backend/app/core/schema_migrations.py`
  - Adds dev-only columns for existing local databases.
- Modify `backend/app/services/backtest_record_service.py`
  - Persists and reads trade cost fields.
- Modify `backend/tests/test_market_rules.py`
  - Covers market cost profiles.
- Modify `backend/tests/test_backtest_engine.py`
  - Covers slippage, costs, A-share stamp duty, US sell-side regulatory fees, and affordability.
- Modify `backend/tests/test_backtests.py`
  - Covers saved backtest detail returning cost fields.
- Modify `frontend/src/components/BacktestResultVisualization.vue`
  - Adds optional cost fields to trade type and renders cost/net cash columns.
- Modify `frontend/src/views/BuilderView.vue`
  - Displays the active market cost assumption in the review modal.
- Modify `frontend/tests/builder-view.test.ts`
  - Covers cost assumption copy plus cost and net cash display through the existing builder result flow.

---

## Task 1: Market Cost Profiles

**Files:**
- Modify: `backend/app/schemas/market_rule.py`
- Modify: `backend/app/services/market_rule_service.py`
- Test: `backend/tests/test_market_rules.py`

- [ ] **Step 1: Write the failing tests**

Add tests proving both market rule responses expose distinct cost profiles:

```python
def test_market_rules_include_a_share_cost_profile(client):
    response = client.get("/api/market-rules/A_SHARE")

    assert response.status_code == 200
    profile = response.json()["costProfile"]
    assert profile["commissionBps"] == 2.5
    assert profile["minCommission"] == 5
    assert profile["slippageBps"] == 1
    assert profile["buyFeeBps"] == 0.641
    assert profile["sellFeeBps"] == 0.641
    assert profile["sellTaxBps"] == 5
    assert profile["secFeePerMillion"] is None
    assert profile["perShareSellFee"] is None


def test_market_rules_include_us_stock_cost_profile(client):
    response = client.get("/api/market-rules/US_STOCK")

    assert response.status_code == 200
    profile = response.json()["costProfile"]
    assert profile["commissionBps"] == 0
    assert profile["minCommission"] == 0
    assert profile["slippageBps"] == 1
    assert profile["buyFeeBps"] == 0
    assert profile["sellFeeBps"] == 0
    assert profile["sellTaxBps"] == 0
    assert profile["secFeePerMillion"] == 20.6
    assert profile["perShareSellFee"] == 0.000166
    assert profile["maxPerShareSellFee"] == 8.3
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_market_rules.py -q
```

Expected: FAIL because `costProfile` is not present.

- [ ] **Step 3: Add schema and service fields**

In `backend/app/schemas/market_rule.py`, add:

```python
class MarketCostProfile(BaseModel):
    commission_bps: float = Field(alias="commissionBps")
    min_commission: float = Field(alias="minCommission")
    slippage_bps: float = Field(alias="slippageBps")
    buy_fee_bps: float = Field(alias="buyFeeBps")
    sell_fee_bps: float = Field(alias="sellFeeBps")
    sell_tax_bps: float = Field(alias="sellTaxBps")
    sec_fee_per_million: float | None = Field(default=None, alias="secFeePerMillion")
    per_share_sell_fee: float | None = Field(default=None, alias="perShareSellFee")
    max_per_share_sell_fee: float | None = Field(default=None, alias="maxPerShareSellFee")

    model_config = ConfigDict(populate_by_name=True)
```

Add to `MarketRuleResponse`:

```python
cost_profile: MarketCostProfile = Field(alias="costProfile")
```

In `backend/app/services/market_rule_service.py`, import `MarketCostProfile` and add the following concrete `costProfile` values to the two market rules.

```python
costProfile=MarketCostProfile(
    commissionBps=2.5,
    minCommission=5,
    slippageBps=1,
    buyFeeBps=0.641,
    sellFeeBps=0.641,
    sellTaxBps=5,
    secFeePerMillion=None,
    perShareSellFee=None,
    maxPerShareSellFee=None,
)
```

```python
costProfile=MarketCostProfile(
    commissionBps=0,
    minCommission=0,
    slippageBps=1,
    buyFeeBps=0,
    sellFeeBps=0,
    sellTaxBps=0,
    secFeePerMillion=20.6,
    perShareSellFee=0.000166,
    maxPerShareSellFee=8.3,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_market_rules.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/market_rule.py backend/app/services/market_rule_service.py backend/tests/test_market_rules.py
git commit -m "feat: expose market cost profiles"
```

---

## Task 2: Trading Cost Helper

**Files:**
- Create: `backend/app/services/trading_cost_service.py`
- Test: `backend/tests/test_backtest_engine.py`

- [ ] **Step 1: Write the failing tests**

Add focused helper-level tests near the top of `backend/tests/test_backtest_engine.py`:

```python
from app.services.market_rule_service import get_market_rule
from app.services.trading_cost_service import calculate_trade_fill, affordable_buy_quantity


def test_cost_helper_applies_a_share_buy_slippage_and_fees():
    rule = get_market_rule("A_SHARE")

    fill = calculate_trade_fill(
        side="BUY",
        base_price=10,
        quantity=900,
        market_rule=rule,
    )

    assert fill.price == 10.001
    assert fill.gross_amount == 9000.9
    assert fill.cost_breakdown["commission"] == 5
    assert fill.cost_breakdown["marketFees"] == 0.58
    assert fill.cost_breakdown["stampDuty"] == 0
    assert fill.cost_amount == 5.58
    assert fill.net_cash_change == -9006.48


def test_cost_helper_applies_us_sell_regulatory_fees():
    rule = get_market_rule("US_STOCK")

    fill = calculate_trade_fill(
        side="SELL",
        base_price=11,
        quantity=99,
        market_rule=rule,
    )

    assert fill.price == 10.9989
    assert fill.gross_amount == 1088.89
    assert fill.cost_breakdown["secFee"] == 0.02
    assert fill.cost_breakdown["finraTaf"] == 0.02
    assert fill.cost_amount == 0.04
    assert fill.net_cash_change == 1088.85


def test_affordable_buy_quantity_steps_down_for_a_share_costs():
    rule = get_market_rule("A_SHARE")

    quantity = affordable_buy_quantity(
        cash=10000,
        base_price=10,
        target_cash=10000,
        market_rule=rule,
    )

    assert quantity == 900
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_backtest_engine.py::test_cost_helper_applies_a_share_buy_slippage_and_fees tests/test_backtest_engine.py::test_cost_helper_applies_us_sell_regulatory_fees tests/test_backtest_engine.py::test_affordable_buy_quantity_steps_down_for_a_share_costs -q
```

Expected: FAIL with `ModuleNotFoundError` or import error for `trading_cost_service`.

- [ ] **Step 3: Implement cost helper**

Create `backend/app/services/trading_cost_service.py`:

```python
from dataclasses import dataclass
from typing import Literal

from app.schemas.market_rule import MarketCostProfile, MarketRuleResponse

TradeSide = Literal["BUY", "SELL"]


@dataclass(frozen=True, slots=True)
class TradeFill:
    price: float
    gross_amount: float
    cost_amount: float
    slippage_amount: float
    net_cash_change: float
    cost_breakdown: dict[str, float]


def calculate_trade_fill(
    *,
    side: TradeSide,
    base_price: float,
    quantity: int,
    market_rule: MarketRuleResponse | None,
) -> TradeFill:
    if market_rule is None:
        raise ValueError("Market cost profile is required")
    if quantity <= 0:
        raise ValueError("Trade quantity must be positive")
    profile = market_rule.cost_profile
    _validate_profile(profile)

    price = _slippage_price(side=side, base_price=base_price, slippage_bps=profile.slippage_bps)
    gross_amount = _money(price * quantity)
    slippage_amount = _money(abs(price - base_price) * quantity)
    cost_breakdown = _cost_breakdown(
        side=side,
        gross_amount=gross_amount,
        quantity=quantity,
        profile=profile,
    )
    cost_amount = _money(sum(cost_breakdown.values()))
    net_cash_change = (
        _money(-(gross_amount + cost_amount))
        if side == "BUY"
        else _money(gross_amount - cost_amount)
    )
    return TradeFill(
        price=price,
        gross_amount=gross_amount,
        cost_amount=cost_amount,
        slippage_amount=slippage_amount,
        net_cash_change=net_cash_change,
        cost_breakdown=cost_breakdown,
    )


def affordable_buy_quantity(
    *,
    cash: float,
    base_price: float,
    target_cash: float,
    market_rule: MarketRuleResponse,
) -> int:
    lot_size = max(1, market_rule.buy_lot_size)
    raw_quantity = int(target_cash / _slippage_price(
        side="BUY",
        base_price=base_price,
        slippage_bps=market_rule.cost_profile.slippage_bps,
    ))
    quantity = raw_quantity // lot_size * lot_size
    while quantity >= market_rule.min_order_shares:
        fill = calculate_trade_fill(
            side="BUY",
            base_price=base_price,
            quantity=quantity,
            market_rule=market_rule,
        )
        if abs(fill.net_cash_change) <= _money(cash):
            return quantity
        quantity -= lot_size
    return 0


def _slippage_price(*, side: TradeSide, base_price: float, slippage_bps: float) -> float:
    multiplier = 1 + slippage_bps / 10000 if side == "BUY" else 1 - slippage_bps / 10000
    return round(base_price * multiplier, 4)


def _cost_breakdown(
    *,
    side: TradeSide,
    gross_amount: float,
    quantity: int,
    profile: MarketCostProfile,
) -> dict[str, float]:
    commission = max(_money(gross_amount * profile.commission_bps / 10000), profile.min_commission)
    market_fee_bps = profile.buy_fee_bps if side == "BUY" else profile.sell_fee_bps
    breakdown = {
        "commission": _money(commission),
        "marketFees": _money(gross_amount * market_fee_bps / 10000),
        "stampDuty": _money(gross_amount * profile.sell_tax_bps / 10000) if side == "SELL" else 0,
        "secFee": 0,
        "finraTaf": 0,
    }
    if side == "SELL" and profile.sec_fee_per_million is not None:
        breakdown["secFee"] = _money(gross_amount * profile.sec_fee_per_million / 1_000_000)
    if side == "SELL" and profile.per_share_sell_fee is not None:
        taf = _money(quantity * profile.per_share_sell_fee)
        if profile.max_per_share_sell_fee is not None:
            taf = min(taf, profile.max_per_share_sell_fee)
        breakdown["finraTaf"] = _money(taf)
    return breakdown


def _validate_profile(profile: MarketCostProfile) -> None:
    values = [
        profile.commission_bps,
        profile.min_commission,
        profile.slippage_bps,
        profile.buy_fee_bps,
        profile.sell_fee_bps,
        profile.sell_tax_bps,
    ]
    optional_values = [
        profile.sec_fee_per_million,
        profile.per_share_sell_fee,
        profile.max_per_share_sell_fee,
    ]
    if any(value < 0 for value in values):
        raise ValueError("Market cost profile contains a negative value")
    if any(value is not None and value < 0 for value in optional_values):
        raise ValueError("Market cost profile contains a negative value")


def _money(value: float) -> float:
    return round(value + 1e-9, 2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_backtest_engine.py::test_cost_helper_applies_a_share_buy_slippage_and_fees tests/test_backtest_engine.py::test_cost_helper_applies_us_sell_regulatory_fees tests/test_backtest_engine.py::test_affordable_buy_quantity_steps_down_for_a_share_costs -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/trading_cost_service.py backend/tests/test_backtest_engine.py
git commit -m "feat: add trading cost helper"
```

---

## Task 3: Backtest Engine Cost Integration

**Files:**
- Modify: `backend/app/schemas/backtest.py`
- Modify: `backend/app/services/backtest_service.py`
- Test: `backend/tests/test_backtest_engine.py`

- [ ] **Step 1: Write failing engine tests**

Add:

```python
def test_engine_includes_us_cost_fields_and_costs_lower_return():
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
                "id": "take-profit-1",
                "type": "take-profit",
                "label": "止盈",
                "x": 160,
                "y": 0,
                "params": {"profitRate": "5", "sellPercent": "100"},
            },
        ],
        initial_cash=10000,
        market="US_STOCK",
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", open=10, high=10.1, low=9.9, close=10),
        MarketCandle(time="2026-01-01 09:40", open=10, high=10.8, low=9.9, close=10.5),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY", "SELL"]
    assert result.trades[0].price == 10.001
    assert result.trades[0].cost_amount > 0
    assert result.trades[0].net_cash_change < 0
    assert result.trades[1].price == 10.499
    assert result.trades[1].cost_breakdown["secFee"] >= 0
    assert result.trades[1].cost_breakdown["finraTaf"] > 0
    assert result.summary.endingEquity < 10450


def test_engine_applies_a_share_stamp_duty_on_sell_only():
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
                "id": "take-profit-1",
                "type": "take-profit",
                "label": "止盈",
                "x": 160,
                "y": 0,
                "params": {"profitRate": "5", "sellPercent": "100"},
            },
        ],
        initial_cash=10000,
        market="A_SHARE",
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", open=10, high=10.1, low=9.9, close=10),
        MarketCandle(time="2026-01-01 09:40", open=10, high=10.8, low=9.9, close=10.5),
        MarketCandle(time="2026-01-02 09:35", open=10.6, high=10.8, low=10.1, close=10.7),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY", "SELL"]
    assert result.trades[0].cost_breakdown["stampDuty"] == 0
    assert result.trades[1].cost_breakdown["stampDuty"] > 0


def test_engine_skips_buy_when_cost_adjusted_quantity_is_not_affordable():
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
        initial_cash=50,
        market="A_SHARE",
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", open=10, high=10.1, low=9.9, close=10),
        MarketCandle(time="2026-01-02 09:35", open=10, high=10.1, low=9.9, close=10),
    ]

    result = run_backtest_with_candles(request, candles)

    assert result.trades == []
    assert any(item.event_type == "ORDER_BLOCKED" for item in result.timeline)
    assert "资金不足" in " ".join(item.description for item in result.timeline)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_backtest_engine.py::test_engine_includes_us_cost_fields_and_costs_lower_return tests/test_backtest_engine.py::test_engine_applies_a_share_stamp_duty_on_sell_only tests/test_backtest_engine.py::test_engine_skips_buy_when_cost_adjusted_quantity_is_not_affordable -q
```

Expected: FAIL because `BacktestTrade` has no cost fields and engine ignores costs.

- [ ] **Step 3: Add trade fields to schema**

In `backend/app/schemas/backtest.py`, extend `BacktestTrade`:

```python
class BacktestTrade(BaseModel):
    time: str
    side: Literal["BUY", "SELL"]
    price: float
    quantity: int
    reason: str
    gross_amount: float = Field(default=0, alias="grossAmount")
    cost_amount: float = Field(default=0, alias="costAmount")
    slippage_amount: float = Field(default=0, alias="slippageAmount")
    net_cash_change: float = Field(default=0, alias="netCashChange")
    cost_breakdown: dict[str, float] = Field(default_factory=dict, alias="costBreakdown")

    model_config = ConfigDict(populate_by_name=True)
```

- [ ] **Step 4: Integrate helper in fills**

In `backend/app/services/backtest_service.py`, import:

```python
from app.services.trading_cost_service import affordable_buy_quantity, calculate_trade_fill
```

Update `_fill_buy_order`:

```python
if market_rule is None:
    raise ValueError("Market rule is required for cost-aware backtests")
buy_quantity = affordable_buy_quantity(
    cash=cash,
    base_price=execution_price,
    target_cash=cash * buy_percent / 100,
    market_rule=market_rule,
)
if buy_quantity <= 0:
    timeline.append(
        _timeline_order_blocked(
            sequence=len(timeline),
            time=candle.time,
            side="BUY",
            price=round(execution_price, 4),
            quantity=market_rule.min_order_shares,
            reason="资金不足，扣除交易成本后无法买入最小交易单位",
            rule=f"最小交易单位 {market_rule.min_order_shares} 股",
            node=buy_node,
        )
    )
    return cash
fill = calculate_trade_fill(
    side="BUY",
    base_price=execution_price,
    quantity=buy_quantity,
    market_rule=market_rule,
)
cash = round(cash + fill.net_cash_change, 2)
position.average_price = round((fill.gross_amount + fill.cost_amount) / buy_quantity, 4)
```

When appending `BacktestTrade`, include:

```python
price=fill.price,
grossAmount=fill.gross_amount,
costAmount=fill.cost_amount,
slippageAmount=fill.slippage_amount,
netCashChange=fill.net_cash_change,
costBreakdown=fill.cost_breakdown,
```

Update `_fill_exit_rule` sell cash mutation:

```python
fill = calculate_trade_fill(
    side="SELL",
    base_price=execution_price,
    quantity=sell_quantity,
    market_rule=market_rule,
)
cash = round(cash + fill.net_cash_change, 2)
trade_won = (fill.net_cash_change / sell_quantity) > position.average_price
```

When `_fill_exit_rule` appends `BacktestTrade`, include the same cost fields used by buys:

```python
BacktestTrade(
    time=candle.time,
    side="SELL",
    price=fill.price,
    quantity=sell_quantity,
    reason=exit_rule.reason,
    grossAmount=fill.gross_amount,
    costAmount=fill.cost_amount,
    slippageAmount=fill.slippage_amount,
    netCashChange=fill.net_cash_change,
    costBreakdown=fill.cost_breakdown,
)
```

Update `_sell_remaining_position` signature and body:

```python
def _sell_remaining_position(
    *,
    cash: float,
    position: Position,
    candle: MarketCandle,
    market_rule: MarketRuleResponse,
    trades: list[BacktestTrade],
    reason: str,
) -> float:
    fill = calculate_trade_fill(
        side="SELL",
        base_price=candle.close,
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
    return round(cash + fill.net_cash_change, 2)
```

Update `_sell_remaining_position` signature to accept `market_rule` and use the helper.

- [ ] **Step 5: Run targeted engine tests**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_backtest_engine.py -q
```

Expected: PASS after updating existing expected prices/equity where costs intentionally change behavior. Existing tests that assert exact ending equity must be revised to include cost-aware expected values or use inequalities where exact costs are not the behavior under test.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/backtest.py backend/app/services/backtest_service.py backend/tests/test_backtest_engine.py
git commit -m "feat: apply trading costs in backtests"
```

---

## Task 4: Persist Trade Cost Fields

**Files:**
- Modify: `backend/app/models/backtest.py`
- Modify: `backend/app/core/schema_migrations.py`
- Modify: `backend/app/services/backtest_record_service.py`
- Test: `backend/tests/test_backtests.py`

- [ ] **Step 1: Write failing persistence test**

Add to `backend/tests/test_backtests.py`:

```python
def test_backtest_detail_returns_trade_cost_fields(client, db_session):
    _seed_market_cache(db_session)
    token = register_and_token(client, "cost-detail", "cost-detail@example.com")
    response = client.post(
        "/api/backtests/run",
        headers=auth_headers(token),
        json=_backtest_payload(),
    )
    assert response.status_code == 200
    run_payload = response.json()
    task = db_session.scalar(select(BacktestTask).where(BacktestTask.run_id == run_payload["runId"]))
    assert task is not None

    detail_response = client.get(f"/api/backtests/{task.id}", headers=auth_headers(token))

    assert detail_response.status_code == 200
    trade = detail_response.json()["trades"][0]
    assert "grossAmount" in trade
    assert "costAmount" in trade
    assert "slippageAmount" in trade
    assert "netCashChange" in trade
    assert "costBreakdown" in trade
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_backtests.py::test_backtest_detail_returns_trade_cost_fields -q
```

Expected: FAIL because cost columns are not persisted/read.

- [ ] **Step 3: Add model columns**

In `backend/app/models/backtest.py`, add to `BacktestTradeRecord`:

```python
gross_amount: Mapped[float] = mapped_column(Float, default=0, nullable=False)
cost_amount: Mapped[float] = mapped_column(Float, default=0, nullable=False)
slippage_amount: Mapped[float] = mapped_column(Float, default=0, nullable=False)
net_cash_change: Mapped[float] = mapped_column(Float, default=0, nullable=False)
cost_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
```

- [ ] **Step 4: Add development schema migration**

In `backend/app/core/schema_migrations.py`, add a `backtest_trades` block:

```python
if inspector.has_table("backtest_trades"):
    column_names = {column["name"] for column in inspector.get_columns("backtest_trades")}
    with engine.begin() as connection:
        numeric_defaults = {
            "gross_amount": "price * quantity",
            "cost_amount": "0",
            "slippage_amount": "0",
            "net_cash_change": "CASE WHEN side = 'BUY' THEN -(price * quantity) ELSE price * quantity END",
        }
        for column_name in numeric_defaults:
            if column_name not in column_names:
                connection.execute(
                    text(f"ALTER TABLE backtest_trades ADD COLUMN {column_name} FLOAT NOT NULL DEFAULT 0")
                )
        if "cost_breakdown" not in column_names:
            connection.execute(
                text("ALTER TABLE backtest_trades ADD COLUMN cost_breakdown JSON")
            )
        connection.execute(
            text(
                "UPDATE backtest_trades SET "
                "gross_amount = price * quantity, "
                "net_cash_change = CASE WHEN side = 'BUY' THEN -(price * quantity) ELSE price * quantity END "
                "WHERE gross_amount = 0"
            )
        )
```

- [ ] **Step 5: Save and read fields**

In `save_backtest_result`, pass the new trade fields to `BacktestTradeRecord`.

In the record-to-response mapper, return:

```python
BacktestTrade(
    time=row.trade_time,
    side=row.side,
    price=row.price,
    quantity=row.quantity,
    reason=row.reason,
    grossAmount=row.gross_amount,
    costAmount=row.cost_amount,
    slippageAmount=row.slippage_amount,
    netCashChange=row.net_cash_change,
    costBreakdown=row.cost_breakdown or {},
)
```

- [ ] **Step 6: Run persistence tests**

Run:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest tests/test_backtests.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/backtest.py backend/app/core/schema_migrations.py backend/app/services/backtest_record_service.py backend/tests/test_backtests.py
git commit -m "feat: persist backtest trade costs"
```

---

## Task 5: Frontend Cost Display

**Files:**
- Modify: `frontend/src/components/BacktestResultVisualization.vue`
- Modify: `frontend/src/views/BuilderView.vue`
- Test: `frontend/tests/builder-view.test.ts`

- [ ] **Step 1: Write failing frontend tests**

In `frontend/tests/builder-view.test.ts`, update the existing test named `runs a backtest and renders the returned result summary` with these assertions:

```ts
expect(wrapper.find('.strategy-review-modal').text()).toContain('成本假设')
expect(wrapper.find('.backtest-trades').text()).toContain('成本')
expect(wrapper.find('.backtest-trades').text()).toContain('净现金变化')
expect(wrapper.find('.backtest-trades').text()).toContain('6.24')
expect(wrapper.find('.backtest-trades').text()).toContain('-19,386.24')
```

Update the first mocked `BUY` trade in that test to include:

```ts
grossAmount: 19380,
costAmount: 6.24,
slippageAmount: 1.94,
netCashChange: -19386.24,
costBreakdown: {
  commission: 5,
  marketFees: 1.24,
  stampDuty: 0,
  secFee: 0,
  finraTaf: 0
}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/zluo/Project/STS/frontend
npm test -- builder-view.test.ts
```

Expected: FAIL because cost labels are not displayed.

- [ ] **Step 3: Update result visualization types and table**

In `frontend/src/components/BacktestResultVisualization.vue`, extend `BacktestTrade`:

```ts
grossAmount?: number
costAmount?: number
slippageAmount?: number
netCashChange?: number
costBreakdown?: Record<string, number>
```

Add helpers:

```ts
function formatSignedAmount(value: number | undefined) {
  const numericValue = Number(value ?? 0)
  const sign = numericValue > 0 ? '+' : ''
  return `${sign}${formatAmount(numericValue)}`
}
```

Add table headers:

```html
<th>成本</th>
<th>净现金变化</th>
```

Add table cells:

```html
<td>{{ formatAmount(trade.costAmount) }}</td>
<td>{{ formatSignedAmount(trade.netCashChange) }}</td>
```

- [ ] **Step 4: Add builder cost assumption copy**

In `frontend/src/views/BuilderView.vue`, add a computed label:

```ts
const costAssumptionText = computed(() =>
  backtestSettings.market === 'A_SHARE'
    ? '成本假设：佣金 2.5bps，卖出印花税 5bps，滑点 1bps'
    : '成本假设：零佣金，SEC/FINRA 卖出监管费，滑点 1bps'
)
```

Render inside the backtest review settings block:

```html
<p class="backtest-cost-assumption">{{ costAssumptionText }}</p>
```

- [ ] **Step 5: Run frontend tests**

Run:

```bash
cd /Users/zluo/Project/STS/frontend
npm test -- builder-view.test.ts
npm test
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/BacktestResultVisualization.vue frontend/src/views/BuilderView.vue frontend/tests/builder-view.test.ts
git commit -m "feat: show backtest trading costs"
```

---

## Task 6: Full Verification And Push

**Files:**
- No new files.

- [ ] **Step 1: Run backend lint for touched files**

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m ruff check app/schemas/market_rule.py app/services/market_rule_service.py app/services/trading_cost_service.py app/schemas/backtest.py app/services/backtest_service.py app/models/backtest.py app/core/schema_migrations.py app/services/backtest_record_service.py tests/test_market_rules.py tests/test_backtest_engine.py tests/test_backtests.py
```

Expected: PASS.

- [ ] **Step 2: Run backend full tests**

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m pytest -q
```

Expected: PASS. Existing JWT key-length warnings may remain.

- [ ] **Step 3: Run frontend tests and build**

```bash
cd /Users/zluo/Project/STS/frontend
npm test
npm run build
```

Expected: PASS.

- [ ] **Step 4: Browser smoke test**

With both servers running:

```bash
cd /Users/zluo/Project/STS/backend
./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

```bash
cd /Users/zluo/Project/STS/frontend
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173/`, run a simple buy/take-profit backtest, and confirm:

- review modal shows `成本假设`;
- downloaded/prepared A-share data still works;
- result table shows `成本` and `净现金变化`;
- trade markers and equity chart still render.

- [ ] **Step 5: Push**

```bash
git status --short
git push origin main
```

Expected: all implementation commits pushed to `main`.

---

## Self-Review Notes

- Spec coverage: The plan covers market profiles, slippage, trade response fields, persistence, frontend display, error handling through insufficient-cash blocked orders, and verification.
- Scope kept out: editable fee profiles, broker integrations, async tasks, and indicators remain out of this slice.
- Type consistency: Backend API names use camelCase aliases matching frontend fields: `grossAmount`, `costAmount`, `slippageAmount`, `netCashChange`, `costBreakdown`.
- Compatibility: `BacktestTrade` defaults keep old mock data and old records readable; schema migration backfills existing local rows.
