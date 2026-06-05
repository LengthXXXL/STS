from fastapi import APIRouter, HTTPException, status

from app.schemas.backtest import BacktestRunRequest, BacktestRunResponse
from app.services.backtest_service import run_backtest as run_backtest_service

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("/run", response_model=BacktestRunResponse)
def run_backtest(request: BacktestRunRequest) -> BacktestRunResponse:
    if not request.strategy.nodes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Strategy must contain at least one node",
        )

    return run_backtest_service(request)
