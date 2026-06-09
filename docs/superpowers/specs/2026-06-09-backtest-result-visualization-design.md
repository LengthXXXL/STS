# Backtest Result Visualization Design

Date: 2026-06-09

## Goal

Make a completed backtest easier to understand immediately after it runs. Users should see not only final metrics, but also where the strategy bought, where it sold, how equity moved, and which market rules affected execution.

## Scope

- Add a reusable frontend component for backtest result visualization.
- Show summary metrics when the component is used in the builder run-result card.
- Show equity and drawdown line charts from `equityCurve`.
- Place buy/sell markers on the equity chart when trade timestamps match equity points.
- Show a concise trade review list with side, time, quantity, price, and trigger reason.
- Show execution timeline and blocked-order rule hints.
- Reuse the component in personal-space backtest detail so both result surfaces stay consistent.

## Out Of Scope

- Candlestick/OHLC chart rendering.
- Hover tooltips, zooming, and chart brushing.
- Backend response changes.
- New indicators or benchmark comparison.

## UI Behavior

The builder result card shows metrics first, then chart cards, trade review, timeline, rule hints, and a trade table. Personal space keeps its existing backtest snapshot panel, then uses the same visualization component for the analytical sections.

The component stays SVG-based for now because the existing design already uses lightweight inline charts and the V1 chart interactions are read-only.

## Validation

- Unit coverage verifies that builder-run results render equity/drawdown charts, buy/sell markers, trade review, timeline, rule hints, and trade rows.
- Existing personal-space tests verify the refactored detail panel keeps the same visible information.
- Browser smoke test runs a simple strategy and checks that the result modal renders the new visual sections.
