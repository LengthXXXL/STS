from fastapi import APIRouter, HTTPException, status

from app.schemas.market_rule import MarketRuleListResponse, MarketRuleResponse
from app.services.market_rule_service import get_market_rule, list_market_rules

router = APIRouter(prefix="/market-rules", tags=["market-rules"])


@router.get("", response_model=MarketRuleListResponse)
def list_rules() -> MarketRuleListResponse:
    return MarketRuleListResponse(items=list_market_rules())


@router.get("/{market}", response_model=MarketRuleResponse)
def detail(market: str) -> MarketRuleResponse:
    rule = get_market_rule(market)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market rule not found",
        )
    return rule
