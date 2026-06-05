from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_optional_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.backtest import (
    BacktestRecordDetailResponse,
    BacktestRecordListResponse,
    BacktestRunRequest,
    BacktestRunResponse,
)
from app.services.backtest_record_service import (
    get_backtest_record,
    list_backtest_records,
    save_backtest_result,
)
from app.services.backtest_service import run_backtest as run_backtest_service
from app.services.market_data_service import CachedMarketDataProvider

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.get("", response_model=BacktestRecordListResponse)
def list_current_user_backtests(
    keyword: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, alias="pageSize", ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestRecordListResponse:
    items, total = list_backtest_records(
        db,
        current_user,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return BacktestRecordListResponse(items=items, total=total, page=page, pageSize=page_size)


@router.get("/{task_id}", response_model=BacktestRecordDetailResponse)
def backtest_detail(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestRecordDetailResponse:
    record = get_backtest_record(db, current_user, task_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest not found")
    return record


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
