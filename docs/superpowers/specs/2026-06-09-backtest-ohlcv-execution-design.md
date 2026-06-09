# Backtest OHLCV Execution Design

Date: 2026-06-09

## Goal

Make V1 intraday backtests closer to real trading by using full OHLCV candles and separating signal time from fill time.

## Scope

- Upgrade `MarketCandle` and K-line cache from close-only candles to OHLCV candles.
- Parse OHLCV data from Yahoo Chart and EastMoney responses.
- Keep old cached rows readable by falling back missing open/high/low values to close.
- Execute ordinary buy, sell, and clear signals at the next candle open.
- Execute touch-based risk exits from the current candle range:
  - stop loss when `low <= stop_price`, filled at stop price
  - take profit when `high >= take_profit_price`, filled at take-profit price
  - moving stop when the trailing stop price based on previously confirmed highs is touched, filled at trailing stop price
- If stop loss and take profit are both touched in one candle, stop loss wins.

## Out Of Scope For This Slice

- Fees, commissions, taxes, and slippage.
- Candlestick chart UI with buy/sell markers.
- Redis/Celery asynchronous backtest tasks.
- Additional indicators such as RSI, MACD, Bollinger Bands, and VWAP.

## Data Model

`MarketKlineCache` stores:

- `market`
- `symbol`
- `timeframe`
- `candle_time`
- `open_price`
- `high_price`
- `low_price`
- `close`
- `volume`

Development schema migration adds nullable OHLC columns to existing databases. New rows always write all OHLC values.

## Engine Behavior

The engine processes each candle in three steps:

1. Fill pending ordinary orders from the previous candle at the current open price.
2. Evaluate and fill touch-based risk exits inside the current candle.
3. Evaluate current-candle ordinary action signals and schedule them for the next candle open.

Equity is still marked to market at the current close.

Moving stop uses the highest price confirmed before the current candle when deciding whether the current low touches the trailing stop. The current candle high is recorded only after no touch exit has closed the position, which avoids guessing the intrabar order of a new high and a later pullback from OHLC data alone.
