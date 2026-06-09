# Backtest Result Visualization Plan

Date: 2026-06-09

## Steps

1. Add a failing builder test that expects charts, buy/sell markers, and trade review after a backtest run.
2. Create `BacktestResultVisualization.vue` for metrics, charts, trade review, timeline, rule hints, and trade table.
3. Use the component in the builder result card.
4. Refactor personal-space backtest detail to reuse the same component.
5. Run focused tests, full frontend tests, frontend build, backend tests, and browser smoke verification.
6. Commit and push the update to GitHub.
