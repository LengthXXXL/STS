from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Literal

from app.schemas.market_rule import MarketRuleResponse
from app.services.market_data_service import MarketCandle

TradeSide = Literal["BUY", "SELL"]
PRICE_TICK = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class MarketOrderValidation:
    allowed: bool
    price: float
    reason: str = ""
    rule: str = ""


def validate_market_order(
    market_rule: MarketRuleResponse,
    candle: MarketCandle,
    side: TradeSide,
    execution_price: float,
    quantity: int,
) -> MarketOrderValidation:
    normalized_price = normalize_order_price(side, execution_price)
    if quantity <= 0:
        return MarketOrderValidation(
            allowed=False,
            price=normalized_price,
            reason="委托数量必须大于 0",
            rule="数量",
        )
    if not is_regular_session_candle(market_rule, candle):
        return MarketOrderValidation(
            allowed=False,
            price=normalized_price,
            reason="不在常规交易时段内，订单未触发",
            rule="交易时段",
        )
    if market_rule.market == "A_SHARE":
        return _validate_a_share_price_limit(
            market_rule=market_rule,
            candle=candle,
            side=side,
            normalized_price=normalized_price,
        )
    return MarketOrderValidation(allowed=True, price=normalized_price)


def normalize_order_price(side: TradeSide, price: float) -> float:
    rounding = ROUND_CEILING if side == "BUY" else ROUND_FLOOR
    ticks = (Decimal(str(price)) / PRICE_TICK).to_integral_value(rounding=rounding)
    return float(ticks * PRICE_TICK)


def is_regular_session_candle(market_rule: MarketRuleResponse, candle: MarketCandle) -> bool:
    current_time = candle.time[-5:]
    return any(session.start <= current_time <= session.end for session in market_rule.sessions)


def _validate_a_share_price_limit(
    *,
    market_rule: MarketRuleResponse,
    candle: MarketCandle,
    side: TradeSide,
    normalized_price: float,
) -> MarketOrderValidation:
    if candle.previous_close is None:
        return MarketOrderValidation(
            allowed=False,
            price=normalized_price,
            reason="行情缺少前收盘价，无法执行 A 股涨跌停规则",
            rule="前收盘价",
        )

    limit_percent = Decimal(str(market_rule.price_limit_percent or 0))
    previous_close = Decimal(str(candle.previous_close))
    limit_up = _price_limit(
        previous_close * (Decimal("1") + limit_percent / Decimal("100"))
    )
    limit_down = _price_limit(
        previous_close * (Decimal("1") - limit_percent / Decimal("100"))
    )
    price = Decimal(str(normalized_price))

    if side == "BUY" and price > limit_up:
        return MarketOrderValidation(
            allowed=False,
            price=normalized_price,
            reason=f"A股涨停限制：买入价 {normalized_price:.2f} 高于涨停价 {float(limit_up):.2f}",
            rule="涨跌停",
        )
    if side == "SELL" and price < limit_down:
        return MarketOrderValidation(
            allowed=False,
            price=normalized_price,
            reason=f"A股跌停限制：卖出价 {normalized_price:.2f} 低于跌停价 {float(limit_down):.2f}",
            rule="涨跌停",
        )
    return MarketOrderValidation(allowed=True, price=normalized_price)


def _price_limit(value: Decimal) -> Decimal:
    return value.quantize(PRICE_TICK, rounding=ROUND_HALF_UP)
