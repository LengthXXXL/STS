from dataclasses import dataclass

from app.schemas.backtest import (
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestSummary,
    BacktestTrade,
    EquityPoint,
    StrategyNode,
)
from app.services.market_data_service import (
    DefaultMarketDataProvider,
    MarketCandle,
    MarketDataProvider,
)


@dataclass(slots=True)
class Position:
    quantity: int = 0
    average_price: float = 0


def run_backtest(
    request: BacktestRunRequest,
    market_data_provider: MarketDataProvider | None = None,
) -> BacktestRunResponse:
    provider = market_data_provider or DefaultMarketDataProvider()

    return run_backtest_with_candles(request, provider.get_intraday_candles(request.config))


def run_backtest_with_candles(
    request: BacktestRunRequest,
    candles: list[MarketCandle],
) -> BacktestRunResponse:
    initial_cash = round(request.config.initialCash, 2)
    cash = initial_cash
    position = Position()
    trades: list[BacktestTrade] = []
    equity_curve: list[EquityPoint] = []
    closed_trade_count = 0
    closed_trade_wins = 0
    cooldown_remaining = 0

    buy_node = _first_node(request, "buy")
    sell_node = _first_node(request, "sell")
    clear_node = _first_node(request, "clear")
    take_profit_node = _first_node(request, "take-profit")
    stop_loss_node = _first_node(request, "stop-loss")
    cooldown_node = _first_node(request, "cooldown")

    if not candles:
        return _build_response(
            request=request,
            initial_cash=initial_cash,
            ending_equity=initial_cash,
            trades=trades,
            equity_curve=[EquityPoint(time=request.config.startDate, equity=initial_cash)],
            closed_trade_count=closed_trade_count,
            closed_trade_wins=closed_trade_wins,
        )

    for candle in candles:
        sold_this_candle = False

        if position.quantity > 0:
            exit_rule = _select_exit_rule(
                position=position,
                close=candle.close,
                take_profit_node=take_profit_node,
                stop_loss_node=stop_loss_node,
                clear_node=clear_node,
                sell_node=sell_node,
            )
            if exit_rule:
                sell_quantity = _quantity_from_percent(
                    position.quantity,
                    _node_percent(exit_rule.node, exit_rule.param_key, exit_rule.default_percent),
                )
                if sell_quantity > 0:
                    cash = round(cash + sell_quantity * candle.close, 2)
                    trades.append(
                        BacktestTrade(
                            time=candle.time,
                            side="SELL",
                            price=round(candle.close, 4),
                            quantity=sell_quantity,
                            reason=exit_rule.reason,
                        )
                    )
                    closed_trade_count += 1
                    if candle.close > position.average_price:
                        closed_trade_wins += 1

                    position.quantity -= sell_quantity
                    if position.quantity <= 0:
                        position.quantity = 0
                        position.average_price = 0
                    if exit_rule.kind == "stop-loss" and cooldown_node:
                        cooldown_remaining = _node_int(cooldown_node, "durationBars", 3)
                    sold_this_candle = True

        if position.quantity == 0 and buy_node and not sold_this_candle:
            if cooldown_remaining > 0:
                cooldown_remaining -= 1
            else:
                buy_quantity = _buy_quantity(
                    cash=cash,
                    price=candle.close,
                    buy_percent=_node_percent(buy_node, "sizePercent", 20),
                    market=request.config.market,
                )
                if buy_quantity > 0:
                    cash = round(cash - buy_quantity * candle.close, 2)
                    position.quantity = buy_quantity
                    position.average_price = candle.close
                    trades.append(
                        BacktestTrade(
                            time=candle.time,
                            side="BUY",
                            price=round(candle.close, 4),
                            quantity=buy_quantity,
                            reason="买入积木触发",
                        )
                    )

        equity_curve.append(
            EquityPoint(
                time=candle.time,
                equity=round(cash + position.quantity * candle.close, 2),
            )
        )

    if position.quantity > 0:
        last_candle = candles[-1]
        cash = _sell_remaining_position(
            cash=cash,
            position=position,
            candle=last_candle,
            trades=trades,
            reason=_final_sell_reason(sell_node=sell_node, clear_node=clear_node),
        )
        closed_trade_count += 1
        if last_candle.close > position.average_price:
            closed_trade_wins += 1
        position.quantity = 0
        position.average_price = 0
        equity_curve[-1] = EquityPoint(time=last_candle.time, equity=round(cash, 2))

    return _build_response(
        request=request,
        initial_cash=initial_cash,
        ending_equity=round(cash, 2),
        trades=trades,
        equity_curve=equity_curve,
        closed_trade_count=closed_trade_count,
        closed_trade_wins=closed_trade_wins,
    )


@dataclass(frozen=True, slots=True)
class ExitRule:
    node: StrategyNode
    kind: str
    param_key: str
    default_percent: float
    reason: str


def _select_exit_rule(
    *,
    position: Position,
    close: float,
    take_profit_node: StrategyNode | None,
    stop_loss_node: StrategyNode | None,
    clear_node: StrategyNode | None,
    sell_node: StrategyNode | None,
) -> ExitRule | None:
    if take_profit_node and _position_return_percent(position, close) >= _node_float(
        take_profit_node, "profitRate", 5
    ):
        return ExitRule(
            node=take_profit_node,
            kind="take-profit",
            param_key="sellPercent",
            default_percent=50,
            reason="止盈触发",
        )

    if stop_loss_node and _position_loss_percent(position, close) >= _node_float(
        stop_loss_node, "lossRate", 3
    ):
        return ExitRule(
            node=stop_loss_node,
            kind="stop-loss",
            param_key="sellPercent",
            default_percent=100,
            reason="止损触发",
        )

    if clear_node:
        return ExitRule(
            node=clear_node,
            kind="clear",
            param_key="sellPercent",
            default_percent=100,
            reason=clear_node.params.get("reason") or "清仓积木触发",
        )

    if sell_node:
        return ExitRule(
            node=sell_node,
            kind="sell",
            param_key="sellPercent",
            default_percent=50,
            reason="卖出积木触发",
        )

    return None


def _build_response(
    *,
    request: BacktestRunRequest,
    initial_cash: float,
    ending_equity: float,
    trades: list[BacktestTrade],
    equity_curve: list[EquityPoint],
    closed_trade_count: int,
    closed_trade_wins: int,
) -> BacktestRunResponse:
    total_return_percent = (
        round((ending_equity - initial_cash) / initial_cash * 100, 2) if initial_cash else 0
    )
    win_rate_percent = (
        round(closed_trade_wins / closed_trade_count * 100, 1) if closed_trade_count else 0
    )

    return BacktestRunResponse(
        runId=f"engine-{request.config.symbol}-{request.config.timeframe}",
        status="COMPLETED",
        config=request.config,
        summary=BacktestSummary(
            totalReturnPercent=total_return_percent,
            maxDrawdownPercent=_max_drawdown_percent(equity_curve),
            winRatePercent=win_rate_percent,
            endingEquity=ending_equity,
            tradeCount=len(trades),
        ),
        trades=trades,
        equityCurve=equity_curve,
    )


def _sell_remaining_position(
    *,
    cash: float,
    position: Position,
    candle: MarketCandle,
    trades: list[BacktestTrade],
    reason: str,
) -> float:
    trades.append(
        BacktestTrade(
            time=candle.time,
            side="SELL",
            price=round(candle.close, 4),
            quantity=position.quantity,
            reason=reason,
        )
    )
    return round(cash + position.quantity * candle.close, 2)


def _final_sell_reason(
    *,
    sell_node: StrategyNode | None,
    clear_node: StrategyNode | None,
) -> str:
    if clear_node:
        return clear_node.params.get("reason") or "清仓积木触发"
    if sell_node:
        return "卖出积木触发"
    return "回测结束清仓"


def _buy_quantity(*, cash: float, price: float, buy_percent: float, market: str) -> int:
    budget = cash * buy_percent / 100
    raw_quantity = int(budget / price)
    if market == "A_SHARE":
        return raw_quantity // 100 * 100
    return raw_quantity


def _quantity_from_percent(quantity: int, percent: float) -> int:
    if percent >= 100:
        return quantity
    return min(quantity, max(1, int(quantity * percent / 100)))


def _first_node(request: BacktestRunRequest, node_type: str) -> StrategyNode | None:
    return next((node for node in request.strategy.nodes if node.type == node_type), None)


def _node_percent(node: StrategyNode, key: str, default: float) -> float:
    return min(100, max(0, _node_float(node, key, default)))


def _node_float(node: StrategyNode, key: str, default: float) -> float:
    try:
        return float(node.params.get(key, default))
    except (TypeError, ValueError):
        return default


def _node_int(node: StrategyNode, key: str, default: int) -> int:
    try:
        return max(1, int(float(node.params.get(key, default))))
    except (TypeError, ValueError):
        return default


def _position_return_percent(position: Position, close: float) -> float:
    if not position.average_price:
        return 0
    return (close - position.average_price) / position.average_price * 100


def _position_loss_percent(position: Position, close: float) -> float:
    return max(0, -_position_return_percent(position, close))


def _max_drawdown_percent(equity_curve: list[EquityPoint]) -> float:
    if not equity_curve:
        return 0

    peak = equity_curve[0].equity
    max_drawdown = 0.0
    for point in equity_curve:
        peak = max(peak, point.equity)
        if peak:
            max_drawdown = max(max_drawdown, (peak - point.equity) / peak * 100)
    return round(max_drawdown, 2)
