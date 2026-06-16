from app.schemas.market_rule import MarketCode, MarketCostProfile, MarketRuleResponse


MARKET_RULES: dict[MarketCode, MarketRuleResponse] = {
    "A_SHARE": MarketRuleResponse(
        market="A_SHARE",
        marketLabel="A股",
        currency="CNY",
        timezone="Asia/Shanghai",
        settlementCycle="T+1",
        buyLotSize=100,
        sellLotSize=1,
        minOrderShares=100,
        supportsIntradayRoundTrip=False,
        priceLimitPercent=10,
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
        ),
        sessions=[
            {"label": "上午连续竞价", "start": "09:30", "end": "11:30"},
            {"label": "下午连续竞价", "start": "13:00", "end": "15:00"},
        ],
        notes=[
            "买入委托数量按 100 股整数倍处理。",
            "卖出允许一次性卖出不足 100 股的零股余额。",
            "普通 A 股主板按 T+1 可卖规则处理，买入当日不可卖出。",
            "普通 A 股主板默认按前收盘价上下 10% 涨跌停限制处理。",
        ],
    ),
    "US_STOCK": MarketRuleResponse(
        market="US_STOCK",
        marketLabel="美股",
        currency="USD",
        timezone="America/New_York",
        settlementCycle="T+1",
        buyLotSize=1,
        sellLotSize=1,
        minOrderShares=1,
        supportsIntradayRoundTrip=True,
        priceLimitPercent=None,
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
        ),
        sessions=[
            {"label": "常规交易时段", "start": "09:30", "end": "16:00"},
        ],
        notes=[
            "常规股票交易按 1 股为最小整数股单位处理。",
            "V1 只模拟常规交易时段，不模拟盘前盘后交易。",
            "美股不设置 A 股式固定日涨跌停，后续回测引擎按熔断和 LULD 风控扩展。",
            "股票结算周期按 T+1 处理，但同一交易日内可进行买卖模拟。",
        ],
    ),
}


def list_market_rules() -> list[MarketRuleResponse]:
    return [MARKET_RULES["A_SHARE"], MARKET_RULES["US_STOCK"]]


def get_market_rule(market: str) -> MarketRuleResponse | None:
    return MARKET_RULES.get(market)  # type: ignore[arg-type]
