from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from app.schemas.backtest import (
    BacktestEvent,
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestSummary,
    BacktestTimelineItem,
    BacktestTrade,
    EquityPoint,
    StrategyNode,
)
from app.schemas.market_rule import MarketRuleResponse
from app.services.market_data_service import (
    DefaultMarketDataProvider,
    MarketCandle,
    MarketDataProvider,
)
from app.services.market_execution_rule_service import (
    is_regular_session_candle,
    validate_market_order,
)
from app.services.market_rule_service import get_market_rule
from app.services.trading_cost_service import affordable_buy_quantity, calculate_trade_fill

TradeSide = Literal["BUY", "SELL"]
PRICE_TICK = Decimal("0.01")


@dataclass(slots=True)
class Position:
    quantity: int = 0
    average_price: float = 0
    highest_price: float = 0
    holding_bars: int = 0
    entry_date: str | None = None


@dataclass(frozen=True, slots=True)
class PreparedOrder:
    allowed: bool
    base_price: float
    reason: str = ""
    rule: str = ""


CONDITION_NODE_TYPES = {
    "if",
    "and",
    "or",
    "not",
    "current-price",
    "price-change",
    "moving-average",
    "volume-change",
    "position-state",
    "time-window",
}


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
    market_rule = get_market_rule(request.config.market)
    if market_rule is None:
        raise ValueError("Market rule is required for backtests")

    initial_cash = round(request.config.initialCash, 2)
    cash = initial_cash
    position = Position()
    trades: list[BacktestTrade] = []
    events: list[BacktestEvent] = []
    timeline: list[BacktestTimelineItem] = []
    equity_curve: list[EquityPoint] = []
    closed_trade_count = 0
    closed_trade_wins = 0
    cooldown_remaining = 0
    pending_buy_node: StrategyNode | None = None
    pending_exit_rule: ExitRule | None = None
    last_regular_session_candle: MarketCandle | None = None

    buy_node = _first_node(request, "buy")
    sell_node = _first_node(request, "sell")
    clear_node = _first_node(request, "clear")
    take_profit_node = _first_node(request, "take-profit")
    stop_loss_node = _first_node(request, "stop-loss")
    moving_stop_node = _first_node(request, "moving-stop")
    cooldown_node = _first_node(request, "cooldown")

    if not candles:
        return _build_response(
            request=request,
            initial_cash=initial_cash,
            ending_equity=initial_cash,
            trades=trades,
            events=events,
            timeline=timeline,
            equity_curve=[EquityPoint(time=request.config.startDate, equity=initial_cash)],
            closed_trade_count=closed_trade_count,
            closed_trade_wins=closed_trade_wins,
        )

    for candle_index, candle in enumerate(candles):
        sold_this_candle = False

        if not is_regular_session_candle(market_rule, candle):
            equity_curve.append(
                EquityPoint(
                    time=candle.time,
                    equity=round(cash + position.quantity * candle.close, 2),
                )
            )
            if position.quantity > 0:
                position.holding_bars += 1
            continue

        last_regular_session_candle = candle

        if pending_exit_rule and position.quantity > 0:
            cash, exit_filled, exit_won = _fill_exit_rule(
                cash=cash,
                position=position,
                candle=candle,
                execution_price=candle.open_price,
                exit_rule=pending_exit_rule,
                market_rule=market_rule,
                trades=trades,
                events=events,
                timeline=timeline,
            )
            if exit_filled:
                closed_trade_count += 1
                if exit_won:
                    closed_trade_wins += 1
                sold_this_candle = True
            pending_exit_rule = None

        if pending_buy_node and position.quantity == 0 and not sold_this_candle:
            if cooldown_remaining > 0:
                cooldown_remaining -= 1
            else:
                cash = _fill_buy_order(
                    cash=cash,
                    position=position,
                    candle=candle,
                    execution_price=candle.open_price,
                    buy_node=pending_buy_node,
                    buy_percent=_node_percent(pending_buy_node, "sizePercent", 20),
                    market_rule=market_rule,
                    trades=trades,
                    timeline=timeline,
                )
            pending_buy_node = None

        if position.quantity > 0:
            exit_rule = _select_touch_exit_rule(
                request=request,
                position=position,
                candle=candle,
                candles=candles,
                candle_index=candle_index,
                take_profit_node=take_profit_node,
                stop_loss_node=stop_loss_node,
                moving_stop_node=moving_stop_node,
            )
            if exit_rule:
                cash, exit_filled, exit_won = _fill_exit_rule(
                    cash=cash,
                    position=position,
                    candle=candle,
                    execution_price=exit_rule.execution_price or candle.close,
                    exit_rule=exit_rule,
                    market_rule=market_rule,
                    trades=trades,
                    events=events,
                    timeline=timeline,
                )
                if exit_filled:
                    closed_trade_count += 1
                    if exit_won:
                        closed_trade_wins += 1
                    if exit_rule.kind == "stop-loss" and cooldown_node:
                        cooldown_duration = _node_int(cooldown_node, "durationBars", 3)
                        cooldown_remaining = cooldown_duration
                        cooldown_reason = cooldown_node.params.get("abnormalRule") or "止损后冷却"
                        timeline.append(
                            _timeline_cooldown_started(
                                sequence=len(timeline),
                                time=candle.time,
                                duration_bars=cooldown_duration,
                                reason=cooldown_reason,
                                node=cooldown_node,
                            )
                        )
                    sold_this_candle = True
            if position.quantity > 0:
                position.highest_price = max(position.highest_price, candle.high_price)

        if position.quantity > 0 and not sold_this_candle and candle_index + 1 < len(candles):
            ordinary_exit_rule = _select_ordinary_exit_rule(
                request=request,
                position=position,
                candles=candles,
                candle_index=candle_index,
                clear_node=clear_node,
                sell_node=sell_node,
            )
            if ordinary_exit_rule:
                pending_exit_rule = ordinary_exit_rule

        if (
            position.quantity == 0
            and buy_node
            and not sold_this_candle
            and candle_index + 1 < len(candles)
            and _action_conditions_pass(
                request=request,
                target_node=buy_node,
                candles=candles,
                candle_index=candle_index,
                position=position,
            )
        ):
            pending_buy_node = buy_node

        equity_curve.append(
            EquityPoint(
                time=candle.time,
                equity=round(cash + position.quantity * candle.close, 2),
            )
        )
        if position.quantity > 0:
            position.holding_bars += 1

    ending_equity = equity_curve[-1].equity if equity_curve else initial_cash
    if (
        position.quantity > 0
        and last_regular_session_candle is not None
        and _can_sell_position(position, last_regular_session_candle, market_rule)
        and not _has_blocked_sell_at_time(timeline, last_regular_session_candle.time)
    ):
        last_candle = last_regular_session_candle
        final_node = clear_node or sell_node
        cash, final_filled = _sell_remaining_position(
            cash=cash,
            position=position,
            candle=last_candle,
            market_rule=market_rule,
            trades=trades,
            timeline=timeline,
            reason=_final_sell_reason(sell_node=sell_node, clear_node=clear_node),
            node=final_node,
        )
        if final_filled:
            final_reason = trades[-1].reason
            timeline.append(
                _timeline_trade_filled(
                    sequence=len(timeline),
                    time=last_candle.time,
                    side="SELL",
                    price=trades[-1].price,
                    quantity=trades[-1].quantity,
                    reason=final_reason,
                    node=final_node,
                )
            )
            timeline.append(
                _timeline_position_closed(
                    sequence=len(timeline),
                    time=last_candle.time,
                    reason=final_reason,
                    node=final_node,
                )
            )
            closed_trade_count += 1
            if trades[-1].net_cash_change / trades[-1].quantity > position.average_price:
                closed_trade_wins += 1
            position.quantity = 0
            position.average_price = 0
            position.highest_price = 0
            position.holding_bars = 0
            position.entry_date = None
            _replace_final_equity_point(equity_curve, last_candle.time, round(cash, 2))
            ending_equity = round(cash, 2)

    return _build_response(
        request=request,
        initial_cash=initial_cash,
        ending_equity=round(ending_equity, 2),
        trades=trades,
        events=events,
        timeline=timeline,
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
    execution_price: float | None = None


def _fill_buy_order(
    *,
    cash: float,
    position: Position,
    candle: MarketCandle,
    execution_price: float,
    buy_node: StrategyNode,
    buy_percent: float,
    market_rule: MarketRuleResponse,
    trades: list[BacktestTrade],
    timeline: list[BacktestTimelineItem],
) -> float:
    prepared_order = _prepare_order(
        market_rule=market_rule,
        candle=candle,
        side="BUY",
        execution_price=execution_price,
        quantity=market_rule.min_order_shares,
    )
    if not prepared_order.allowed:
        timeline.append(
            _timeline_order_blocked(
                sequence=len(timeline),
                time=candle.time,
                side="BUY",
                price=prepared_order.base_price,
                quantity=market_rule.min_order_shares,
                reason=prepared_order.reason,
                rule=prepared_order.rule,
                node=buy_node,
            )
        )
        return cash

    buy_quantity = affordable_buy_quantity(
        cash=cash,
        base_price=prepared_order.base_price,
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

    prepared_order = _prepare_order(
        market_rule=market_rule,
        candle=candle,
        side="BUY",
        execution_price=execution_price,
        quantity=buy_quantity,
    )
    if not prepared_order.allowed:
        timeline.append(
            _timeline_order_blocked(
                sequence=len(timeline),
                time=candle.time,
                side="BUY",
                price=prepared_order.base_price,
                quantity=buy_quantity,
                reason=prepared_order.reason,
                rule=prepared_order.rule,
                node=buy_node,
            )
        )
        return cash

    fill = calculate_trade_fill(
        side="BUY",
        base_price=prepared_order.base_price,
        quantity=buy_quantity,
        market_rule=market_rule,
    )
    cash = round(cash + fill.net_cash_change, 2)
    position.quantity = buy_quantity
    position.average_price = round((fill.gross_amount + fill.cost_amount) / buy_quantity, 4)
    position.highest_price = fill.price
    position.holding_bars = 0
    position.entry_date = _trade_date(candle.time)
    trades.append(
        BacktestTrade(
            time=candle.time,
            side="BUY",
            price=fill.price,
            quantity=buy_quantity,
            reason="买入积木触发",
            grossAmount=fill.gross_amount,
            costAmount=fill.cost_amount,
            slippageAmount=fill.slippage_amount,
            netCashChange=fill.net_cash_change,
            costBreakdown=fill.cost_breakdown,
        )
    )
    timeline.append(
        _timeline_trade_filled(
            sequence=len(timeline),
            time=candle.time,
            side="BUY",
            price=fill.price,
            quantity=buy_quantity,
            reason="买入积木触发",
            node=buy_node,
        )
    )
    return cash


def _fill_exit_rule(
    *,
    cash: float,
    position: Position,
    candle: MarketCandle,
    execution_price: float,
    exit_rule: ExitRule,
    market_rule: MarketRuleResponse,
    trades: list[BacktestTrade],
    events: list[BacktestEvent],
    timeline: list[BacktestTimelineItem],
) -> tuple[float, bool, bool]:
    fill_price = round(execution_price, 4)
    sell_quantity = _quantity_from_percent(
        position.quantity,
        _node_percent(exit_rule.node, exit_rule.param_key, exit_rule.default_percent),
    )
    if market_rule and not _can_sell_position(position, candle, market_rule):
        block_reason = _sell_block_reason(market_rule)
        events.append(
            BacktestEvent(
                time=candle.time,
                eventType="BLOCKED_ORDER",
                side="SELL",
                price=fill_price,
                quantity=sell_quantity,
                reason=block_reason,
                rule=market_rule.settlement_cycle,
            )
        )
        timeline.append(
            _timeline_order_blocked(
                sequence=len(timeline),
                time=candle.time,
                side="SELL",
                price=fill_price,
                quantity=sell_quantity,
                reason=block_reason,
                rule=market_rule.settlement_cycle,
                node=exit_rule.node,
            )
        )
        return cash, False, False

    if sell_quantity <= 0:
        return cash, False, False

    prepared_order = _prepare_order(
        market_rule=market_rule,
        candle=candle,
        side="SELL",
        execution_price=execution_price,
        quantity=sell_quantity,
    )
    if not prepared_order.allowed:
        events.append(
            BacktestEvent(
                time=candle.time,
                eventType="BLOCKED_ORDER",
                side="SELL",
                price=prepared_order.base_price,
                quantity=sell_quantity,
                reason=prepared_order.reason,
                rule=prepared_order.rule,
            )
        )
        timeline.append(
            _timeline_order_blocked(
                sequence=len(timeline),
                time=candle.time,
                side="SELL",
                price=prepared_order.base_price,
                quantity=sell_quantity,
                reason=prepared_order.reason,
                rule=prepared_order.rule,
                node=exit_rule.node,
            )
        )
        return cash, False, False

    fill = calculate_trade_fill(
        side="SELL",
        base_price=prepared_order.base_price,
        quantity=sell_quantity,
        market_rule=market_rule,
    )
    trade_won = fill.net_cash_change / sell_quantity > position.average_price
    cash = round(cash + fill.net_cash_change, 2)
    trades.append(
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
    )
    timeline.append(
        _timeline_trade_filled(
            sequence=len(timeline),
            time=candle.time,
            side="SELL",
            price=fill.price,
            quantity=sell_quantity,
            reason=exit_rule.reason,
            node=exit_rule.node,
        )
    )

    position.quantity -= sell_quantity
    closed_by_clear = exit_rule.kind == "clear" and position.quantity <= 0
    if position.quantity <= 0:
        position.quantity = 0
        position.average_price = 0
        position.highest_price = 0
        position.holding_bars = 0
        position.entry_date = None
    if closed_by_clear:
        timeline.append(
            _timeline_position_closed(
                sequence=len(timeline),
                time=candle.time,
                reason=exit_rule.reason,
                node=exit_rule.node,
            )
        )
    return cash, True, trade_won


def _select_touch_exit_rule(
    *,
    request: BacktestRunRequest,
    position: Position,
    candle: MarketCandle,
    candles: list[MarketCandle],
    candle_index: int,
    take_profit_node: StrategyNode | None,
    stop_loss_node: StrategyNode | None,
    moving_stop_node: StrategyNode | None,
) -> ExitRule | None:
    if stop_loss_node:
        stop_loss_price = _stop_loss_price(position, stop_loss_node)
        if candle.low_price <= stop_loss_price:
            return ExitRule(
                node=stop_loss_node,
                kind="stop-loss",
                param_key="sellPercent",
                default_percent=100,
                reason="止损触发",
                execution_price=stop_loss_price,
            )

    if take_profit_node:
        take_profit_price = _take_profit_price(position, take_profit_node)
        if candle.high_price >= take_profit_price:
            return ExitRule(
                node=take_profit_node,
                kind="take-profit",
                param_key="sellPercent",
                default_percent=50,
                reason="止盈触发",
                execution_price=take_profit_price,
            )

    moving_stop_price = (
        _moving_stop_price(position, moving_stop_node) if moving_stop_node else None
    )
    if moving_stop_node and moving_stop_price is not None and candle.low_price <= moving_stop_price:
        return ExitRule(
            node=moving_stop_node,
            kind="moving-stop",
            param_key="sellPercent",
            default_percent=100,
            reason="移动止损触发",
            execution_price=moving_stop_price,
        )

    return None


def _select_ordinary_exit_rule(
    *,
    request: BacktestRunRequest,
    position: Position,
    candles: list[MarketCandle],
    candle_index: int,
    clear_node: StrategyNode | None,
    sell_node: StrategyNode | None,
) -> ExitRule | None:
    if clear_node and _action_conditions_pass(
        request=request,
        target_node=clear_node,
        candles=candles,
        candle_index=candle_index,
        position=position,
    ):
        return ExitRule(
            node=clear_node,
            kind="clear",
            param_key="sellPercent",
            default_percent=100,
            reason=clear_node.params.get("reason") or "清仓积木触发",
        )

    if sell_node and _action_conditions_pass(
        request=request,
        target_node=sell_node,
        candles=candles,
        candle_index=candle_index,
        position=position,
    ):
        return ExitRule(
            node=sell_node,
            kind="sell",
            param_key="sellPercent",
            default_percent=50,
            reason="卖出积木触发",
        )

    return None


def _action_conditions_pass(
    *,
    request: BacktestRunRequest,
    target_node: StrategyNode,
    candles: list[MarketCandle],
    candle_index: int,
    position: Position,
) -> bool:
    condition_nodes = _incoming_condition_nodes(request, target_node)
    if not condition_nodes:
        return True

    return all(
        _condition_node_passes(
            request=request,
            node=node,
            candles=candles,
            candle_index=candle_index,
            position=position,
        )
        for node in condition_nodes
    )


def _incoming_condition_nodes(
    request: BacktestRunRequest,
    target_node: StrategyNode,
) -> list[StrategyNode]:
    nodes_by_id = {node.id: node for node in request.strategy.nodes}
    return [
        nodes_by_id[edge.from_]
        for edge in request.strategy.edges
        if edge.to == target_node.id
        and edge.from_ in nodes_by_id
        and nodes_by_id[edge.from_].type in CONDITION_NODE_TYPES
    ]


def _condition_node_passes(
    *,
    request: BacktestRunRequest,
    node: StrategyNode,
    candles: list[MarketCandle],
    candle_index: int,
    position: Position,
) -> bool:
    candle = candles[candle_index]

    if node.type in {"if", "and", "or", "not"}:
        incoming_nodes = _incoming_condition_nodes(request, node)
        if not incoming_nodes:
            return node.type == "if"

        results = [
            _condition_node_passes(
                request=request,
                node=incoming_node,
                candles=candles,
                candle_index=candle_index,
                position=position,
            )
            for incoming_node in incoming_nodes
        ]
        if node.type == "or":
            return any(results)
        if node.type == "not":
            return not results[0]
        return all(results)

    if node.type == "current-price":
        return _compare(
            candle.close,
            node.params.get("comparator", ">="),
            _node_float(node, "price", candle.close),
        )

    if node.type == "price-change":
        lookback = _node_int(node, "lookbackBars", 1)
        if candle_index - lookback < 0:
            return False
        previous_close = candles[candle_index - lookback].close
        if previous_close == 0:
            return False
        change_percent = (candle.close - previous_close) / previous_close * 100
        return _compare(
            change_percent,
            node.params.get("comparator", ">="),
            _node_float(node, "changePercent", 0),
        )

    if node.type == "moving-average":
        period = _node_int(node, "period", 5)
        if candle_index - period + 1 < 0:
            return False
        window = candles[candle_index - period + 1 : candle_index + 1]
        average_close = sum(point.close for point in window) / len(window)
        if node.params.get("relation") == "below":
            return candle.close <= average_close
        return candle.close >= average_close

    if node.type == "volume-change":
        lookback = _node_int(node, "lookbackBars", 1)
        if candle_index - lookback < 0:
            return False
        previous_volume = candles[candle_index - lookback].volume
        if previous_volume == 0:
            return False
        change_percent = (candle.volume - previous_volume) / previous_volume * 100
        return _compare(
            change_percent,
            node.params.get("comparator", ">="),
            _node_float(node, "changePercent", 0),
        )

    if node.type == "position-state":
        state = node.params.get("state", "no-position")
        if state == "has-position":
            return position.quantity > 0
        if state == "profit-gte":
            return _position_return_percent(position, candle.close) >= _node_float(
                node, "threshold", 0
            )
        if state == "holding-bars-gte":
            return position.holding_bars >= _node_int(node, "threshold", 1)
        return position.quantity == 0

    if node.type == "time-window":
        return _time_in_window(
            candle.time[-5:],
            node.params.get("startTime", "09:35"),
            node.params.get("endTime", "14:55"),
        )

    return True


def _take_profit_price(position: Position, take_profit_node: StrategyNode) -> float:
    profit_rate = _node_float(take_profit_node, "profitRate", 5)
    return round(position.average_price * (1 + profit_rate / 100), 4)


def _stop_loss_price(position: Position, stop_loss_node: StrategyNode) -> float:
    loss_rate = _node_float(stop_loss_node, "lossRate", 3)
    return round(position.average_price * (1 - loss_rate / 100), 4)


def _moving_stop_price(
    position: Position,
    moving_stop_node: StrategyNode | None,
) -> float | None:
    if moving_stop_node is None:
        return None
    if position.highest_price <= 0 or position.average_price <= 0:
        return None

    highest_return_percent = (
        (position.highest_price - position.average_price) / position.average_price * 100
    )
    if highest_return_percent < _node_float(moving_stop_node, "minProfitPercent", 5):
        return None

    trail_percent = _node_float(moving_stop_node, "trailPercent", 3)
    return round(position.highest_price * (1 - trail_percent / 100), 4)


def _build_response(
    *,
    request: BacktestRunRequest,
    initial_cash: float,
    ending_equity: float,
    trades: list[BacktestTrade],
    events: list[BacktestEvent],
    timeline: list[BacktestTimelineItem],
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
        events=events,
        timeline=timeline,
        equityCurve=equity_curve,
    )


def _timeline_trade_filled(
    *,
    sequence: int,
    time: str,
    side: str,
    price: float,
    quantity: int,
    reason: str,
    node: StrategyNode | None,
) -> BacktestTimelineItem:
    return BacktestTimelineItem(
        id=f"trade-filled-{sequence}",
        time=time,
        eventType="TRADE_FILLED",
        title="买入成交" if side == "BUY" else "卖出成交",
        description=reason,
        severity="success",
        side=side,
        price=price,
        quantity=quantity,
        nodeId=node.id if node else None,
        nodeType=node.type if node else None,
        nodeLabel=node.label if node else None,
    )


def _timeline_order_blocked(
    *,
    sequence: int,
    time: str,
    side: str,
    price: float,
    quantity: int,
    reason: str,
    rule: str,
    node: StrategyNode | None,
) -> BacktestTimelineItem:
    return BacktestTimelineItem(
        id=f"order-blocked-{sequence}",
        time=time,
        eventType="ORDER_BLOCKED",
        title="买入信号被拦截" if side == "BUY" else "卖出信号被拦截",
        description=reason,
        severity="warning",
        side=side,
        price=price,
        quantity=quantity,
        rule=rule,
        nodeId=node.id if node else None,
        nodeType=node.type if node else None,
        nodeLabel=node.label if node else None,
    )


def _timeline_cooldown_started(
    *,
    sequence: int,
    time: str,
    duration_bars: int,
    reason: str,
    node: StrategyNode,
) -> BacktestTimelineItem:
    return BacktestTimelineItem(
        id=f"cooldown-started-{sequence}",
        time=time,
        eventType="COOLDOWN_STARTED",
        title="进入冷却",
        description=reason,
        severity="info",
        nodeId=node.id,
        nodeType=node.type,
        nodeLabel=node.label,
        details={"durationBars": duration_bars, "reason": reason},
    )


def _timeline_position_closed(
    *,
    sequence: int,
    time: str,
    reason: str,
    node: StrategyNode | None,
) -> BacktestTimelineItem:
    return BacktestTimelineItem(
        id=f"position-closed-{sequence}",
        time=time,
        eventType="POSITION_CLOSED",
        title="持仓已关闭",
        description=reason,
        severity="info",
        nodeId=node.id if node else None,
        nodeType=node.type if node else None,
        nodeLabel=node.label if node else None,
    )


def _prepare_order(
    *,
    market_rule: MarketRuleResponse,
    candle: MarketCandle,
    side: TradeSide,
    execution_price: float,
    quantity: int,
) -> PreparedOrder:
    validation = validate_market_order(
        market_rule=market_rule,
        candle=candle,
        side=side,
        execution_price=execution_price,
        quantity=quantity,
    )
    if not validation.allowed:
        return PreparedOrder(
            allowed=False,
            base_price=validation.price,
            reason=validation.reason,
            rule=validation.rule,
        )

    base_price = _cap_slippage_base_price(
        market_rule=market_rule,
        candle=candle,
        side=side,
        base_price=validation.price,
    )
    fill_price = _project_fill_price(
        market_rule=market_rule,
        side=side,
        base_price=base_price,
    )
    fill_validation = validate_market_order(
        market_rule=market_rule,
        candle=candle,
        side=side,
        execution_price=fill_price,
        quantity=quantity,
    )
    if not fill_validation.allowed:
        return PreparedOrder(
            allowed=False,
            base_price=fill_validation.price,
            reason=fill_validation.reason,
            rule=fill_validation.rule,
        )

    return PreparedOrder(allowed=True, base_price=base_price)


def _cap_slippage_base_price(
    *,
    market_rule: MarketRuleResponse,
    candle: MarketCandle,
    side: TradeSide,
    base_price: float,
) -> float:
    price_limits = _a_share_price_limits(market_rule, candle)
    if price_limits is None:
        return base_price

    limit_down, limit_up = price_limits
    multiplier = _slippage_multiplier(market_rule, side)
    if multiplier <= 0:
        return base_price
    if side == "BUY":
        return min(base_price, limit_up / multiplier)
    return max(base_price, limit_down / multiplier)


def _a_share_price_limits(
    market_rule: MarketRuleResponse,
    candle: MarketCandle,
) -> tuple[float, float] | None:
    if market_rule.market != "A_SHARE" or candle.previous_close is None:
        return None

    previous_close = Decimal(str(candle.previous_close))
    limit_percent = Decimal(str(market_rule.price_limit_percent or 0))
    limit_up = (previous_close * (Decimal("1") + limit_percent / Decimal("100"))).quantize(
        PRICE_TICK,
        rounding=ROUND_HALF_UP,
    )
    limit_down = (previous_close * (Decimal("1") - limit_percent / Decimal("100"))).quantize(
        PRICE_TICK,
        rounding=ROUND_HALF_UP,
    )
    return float(limit_down), float(limit_up)


def _project_fill_price(
    *,
    market_rule: MarketRuleResponse,
    side: TradeSide,
    base_price: float,
) -> float:
    return round(base_price * _slippage_multiplier(market_rule, side), 4)


def _slippage_multiplier(market_rule: MarketRuleResponse, side: TradeSide) -> float:
    slippage_bps = market_rule.cost_profile.slippage_bps
    if side == "BUY":
        return 1 + slippage_bps / 10000
    return 1 - slippage_bps / 10000


def _sell_remaining_position(
    *,
    cash: float,
    position: Position,
    candle: MarketCandle,
    market_rule: MarketRuleResponse,
    trades: list[BacktestTrade],
    timeline: list[BacktestTimelineItem],
    reason: str,
    node: StrategyNode | None,
) -> tuple[float, bool]:
    prepared_order = _prepare_order(
        market_rule=market_rule,
        candle=candle,
        side="SELL",
        execution_price=candle.close,
        quantity=position.quantity,
    )
    if not prepared_order.allowed:
        timeline.append(
            _timeline_order_blocked(
                sequence=len(timeline),
                time=candle.time,
                side="SELL",
                price=prepared_order.base_price,
                quantity=position.quantity,
                reason=prepared_order.reason,
                rule=prepared_order.rule,
                node=node,
            )
        )
        return cash, False

    fill = calculate_trade_fill(
        side="SELL",
        base_price=prepared_order.base_price,
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
    return round(cash + fill.net_cash_change, 2), True


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


def _buy_quantity(
    *,
    cash: float,
    price: float,
    buy_percent: float,
    buy_lot_size: int,
    min_order_shares: int,
) -> int:
    budget = cash * buy_percent / 100
    raw_quantity = int(budget / price)
    lot_size = max(1, buy_lot_size)
    quantity = raw_quantity // lot_size * lot_size
    return quantity if quantity >= min_order_shares else 0


def _can_sell_position(
    position: Position,
    candle: MarketCandle,
    market_rule: MarketRuleResponse,
) -> bool:
    if market_rule.supports_intraday_round_trip:
        return True
    return position.entry_date is not None and _trade_date(candle.time) > position.entry_date


def _sell_block_reason(market_rule: MarketRuleResponse) -> str:
    if market_rule.settlement_cycle == "T+1" and not market_rule.supports_intraday_round_trip:
        return "A股 T+1 规则限制，当日买入持仓不可卖出"
    return "市场规则限制，本次卖出信号未成交"


def _has_blocked_sell_at_time(timeline: list[BacktestTimelineItem], time_value: str) -> bool:
    return any(
        item.event_type == "ORDER_BLOCKED" and item.side == "SELL" and item.time == time_value
        for item in timeline
    )


def _replace_final_equity_point(
    equity_curve: list[EquityPoint],
    time_value: str,
    equity: float,
) -> None:
    for index in range(len(equity_curve) - 1, -1, -1):
        if equity_curve[index].time == time_value:
            equity_curve[index] = EquityPoint(time=time_value, equity=equity)
            del equity_curve[index + 1 :]
            return
    equity_curve.append(EquityPoint(time=time_value, equity=equity))


def _trade_date(time_value: str) -> str:
    return time_value[:10]


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


def _compare(actual: float, comparator: str, expected: float) -> bool:
    if comparator == "<=":
        return actual <= expected
    return actual >= expected


def _time_in_window(current_time: str, start_time: str, end_time: str) -> bool:
    if start_time <= end_time:
        return start_time <= current_time <= end_time
    return current_time >= start_time or current_time <= end_time


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
