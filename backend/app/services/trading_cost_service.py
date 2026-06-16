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
    raw_quantity = int(
        target_cash
        / _slippage_price(
            side="BUY",
            base_price=base_price,
            slippage_bps=market_rule.cost_profile.slippage_bps,
        )
    )
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
