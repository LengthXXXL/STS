from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_optional_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.backtest import BacktestRunRequest, BacktestRunResponse
from app.services.backtest_record_service import save_backtest_result
from app.services.backtest_service import run_backtest as run_backtest_service
from app.services.market_data_service import CachedMarketDataProvider

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("/run", response_model=BacktestRunResponse)
def run_backtest(
    request: BacktestRunRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> BacktestRunResponse:
    if not request.strategy.nodes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Strategy must contain at least one node",
        )

    result = run_backtest_service(
        request,
        market_data_provider=CachedMarketDataProvider(db),
    )
    save_backtest_result(db, request, result, current_user)
    return result
