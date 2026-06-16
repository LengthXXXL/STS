# Backtest Trading Costs And Slippage Design

Date: 2026-06-16

## Goal

Make STS backtest results less idealized by applying realistic transaction costs and
conservative slippage to every simulated fill. This slice focuses on single-stock intraday
backtests and preserves the existing strategy-building flow.

## Product Scope

This work adds:

- market-specific default cost profiles for A-shares and US stocks;
- slippage-adjusted fill prices for buys and sells;
- commission, exchange, regulatory, transfer, tax, and per-share sell fees where applicable;
- trade result fields that show gross amount, total cost, slippage impact, and net cash change;
- frontend display of each trade's total cost and net cash change;
- tests proving that costs lower returns and that A-share and US rules differ.

This work does not add:

- user-editable cost profiles in the UI;
- broker account integration;
- short selling, margin, options, futures, or portfolio-level financing;
- async backtest jobs;
- new technical indicators.

## Rule Sources And Default Assumptions

Fee rules change over time, so STS will keep the values centralized in market rule profiles.
The defaults below are used for simulation only and can be updated later without changing the
strategy format.

### A-shares

Default A-share profile:

- Broker commission: 2.5 bps on both buy and sell, minimum CNY 5 per order.
- Exchange handling fee: 0.00341% on both buy and sell.
- Securities management fee: 0.002% on both buy and sell.
- Transfer fee: 0.001% on both buy and sell.
- Stamp duty: 0.05% on sell only.
- Slippage: 1 bps, applied conservatively.

The broker commission is an STS default assumption because actual broker pricing differs.
The other listed fees come from public market-rule references and are centralized so they can
be updated later.

### US stocks

Default US stock profile:

- Broker commission: 0 by default, matching the common retail zero-commission assumption.
- SEC Section 31 fee: USD 20.60 per USD 1,000,000 of covered sell transactions for trades on
  or after 2026-04-04.
- FINRA Trading Activity Fee for covered equity sales: USD 0.000166 per sold share, capped at
  USD 8.30 per trade.
- Slippage: 1 bps, applied conservatively.

US costs are sell-side heavy in this V1 slice. Additional exchange routing, maker/taker, ADR,
and broker-specific fees remain out of scope.

## Cost Calculation

The backtest engine chooses the base execution price exactly as it does today:

- ordinary buy, sell, and clear: next candle open;
- stop loss: touched stop price;
- take profit: touched take-profit price;
- moving stop: touched moving-stop price;
- final forced close: last candle close.

Then the cost engine applies slippage:

- buy fill price = base execution price * `(1 + slippageBps / 10000)`;
- sell fill price = base execution price * `(1 - slippageBps / 10000)`.

For each fill:

```text
grossAmount = fillPrice * quantity
totalCost = commission + market fees + regulatory fees + taxes

buy netCashChange = -(grossAmount + totalCost)
sell netCashChange = grossAmount - totalCost
```

Buy quantity must be affordable after costs. For A-shares this means the engine first rounds
to the lot size, then steps down by one lot until `grossAmount + totalCost <= cash`.

The position average price should represent the actual cost basis after buy-side costs:

```text
averagePrice = (grossAmount + buyCosts) / quantity
```

Sell win/loss calculation should compare net sell proceeds per share with that cost basis.

## Data Model And API Changes

### Backtest trade response

`BacktestTrade` gains these fields:

- `grossAmount`: trade value before costs.
- `costAmount`: total fee/tax/regulatory cost.
- `slippageAmount`: absolute difference between base and slippage-adjusted execution value.
- `netCashChange`: cash movement after costs, negative for buys and positive for sells.
- `costBreakdown`: object keyed by component name, for example `commission`, `stampDuty`,
  `secFee`, or `finraTaf`.

Existing response fields stay unchanged:

- `time`
- `side`
- `price`
- `quantity`
- `reason`

### Backtest trade persistence

`backtest_trades` gains nullable/defaulted columns:

- `gross_amount`
- `cost_amount`
- `slippage_amount`
- `net_cash_change`
- `cost_breakdown` JSON

Development schema migration backfills old rows with zero costs and derives gross/net from
existing price and quantity where possible.

### Market rule response

`MarketRuleResponse` gains a `costProfile` object so the frontend can explain assumptions:

- `commissionBps`
- `minCommission`
- `slippageBps`
- `buyFeeBps`
- `sellFeeBps`
- `sellTaxBps`
- `secFeePerMillion`
- `perShareSellFee`
- `maxPerShareSellFee`

Unused fields are `null` for markets where they do not apply.

## Frontend Behavior

The first UI pass is deliberately compact:

- The run-backtest modal shows a small cost assumption line under the selected market:
  - A-share example: `成本假设：佣金 2.5bps，卖出印花税 5bps，滑点 1bps`
  - US example: `成本假设：零佣金，SEC/FINRA 卖出监管费，滑点 1bps`
- The result trade table adds:
  - `成本`
  - `净现金变化`
- Existing equity curve, drawdown chart, buy/sell markers, and timeline remain in place.

No new user input is added in this slice. User-editable fee profiles can be added after the
calculation is stable.

## Error Handling

- If a cost profile is missing, the backend raises a clear configuration error instead of
running a zero-cost simulation accidentally.
- If a buy signal cannot afford at least the minimum tradable quantity after costs, the order
is skipped and a timeline item records that cash was insufficient after costs.
- If a component produces a negative or invalid cost, the backend treats it as configuration
invalid and fails the backtest.

## Testing Strategy

Backend tests:

- A buy-and-sell strategy with costs has lower ending equity than the same no-cost arithmetic.
- A-share sell trades include stamp duty and buy trades do not.
- A-share buy sizing steps down so `gross + costs` never exceeds available cash.
- US sell trades include SEC and FINRA costs while buy trades do not.
- Slippage worsens both buy and sell execution prices.
- Persisted backtest detail returns the new cost fields.

Frontend tests:

- The backtest review modal displays the active market cost assumption.
- The result table renders cost and net cash change.
- Existing backtest result visualization still renders with older mock trades that do not
  include cost fields, using zero defaults.

## Acceptance Criteria

- Running the same strategy after this slice produces lower or equal total return than the
  old no-cost result.
- Trade details make costs visible enough that users understand why net cash differs from
  `price * quantity`.
- A-share and US stock simulations use different cost profiles.
- Existing strategy JSON remains compatible.
- Existing saved backtest records remain readable.

## References

- China stamp duty reduction: https://english.www.gov.cn/policies/policywatch/202308/28/content_WS64ec5513c6d0868f4e8dee23.html
- Shanghai Stock Exchange fee table: https://english.sse.com.cn/start/taxes/
- HKEX Stock Connect transaction fee table: https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Fees/Securities-%28Stock-Connect%29/Trading/Transactions?sc_lang=en
- SEC Section 31 FY2026 fee advisory: https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2
- FINRA Trading Activity Fee rule: https://www.finra.org/rules-guidance/rulebooks/corporate-organization/section-1-member-regulatory-fees
