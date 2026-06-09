# Backtest OHLCV Execution Plan

Date: 2026-06-09

## Steps

1. Add failing tests for next-open buy execution, stop-loss/take-profit touch prices, and OHLCV cache persistence.
2. Update the `MarketCandle` model with OHLC helpers and preserve close-only compatibility.
3. Update Yahoo, EastMoney, local, and cached market data providers to produce OHLCV candles.
4. Add dev schema migration for `market_kline_cache.open_price/high_price/low_price`.
5. Refactor the backtest loop to fill ordinary pending orders at the next candle open.
6. Refactor touch-based exits to use high/low trigger prices and stop-loss priority.
7. Update affected tests to the new execution semantics.
8. Run backend tests, frontend tests, and production build; use a browser smoke check only if frontend surfaces change.
9. Commit and push the update to GitHub.
