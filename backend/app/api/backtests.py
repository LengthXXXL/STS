from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_optional_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.backtest import (
    BacktestConfig,
    BacktestRecordDetailResponse,
    BacktestRecordListResponse,
    BacktestRunRequest,
    BacktestRunResponse,
)
from app.schemas.uploaded_file import UploadedFileResponse
from app.services.backtest_record_service import (
    get_backtest_record,
    list_backtest_records,
    save_backtest_result,
)
from app.services.backtest_report_service import export_backtest_report
from app.services.backtest_service import run_backtest as run_backtest_service
from app.services.market_data_download_service import NoTradingDaysError, ensure_market_data_ready
from app.services.market_data_service import LocalOnlyMarketDataProvider, MarketDataUnavailableError
from app.services.simulation_account_service import get_simulation_account

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


@router.post(
    "/{task_id}/export",
    response_model=UploadedFileResponse,
    status_code=status.HTTP_201_CREATED,
)
def export_backtest(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadedFileResponse:
    report_file = export_backtest_report(db, current_user, task_id)
    if report_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest not found")
    return report_file


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

    effective_request = _apply_simulation_account(request, current_user, db)
    try:
        ensure_market_data_ready(db, effective_request.config)
        result = run_backtest_service(
            effective_request,
            market_data_provider=LocalOnlyMarketDataProvider(db),
        )
    except NoTradingDaysError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except MarketDataUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="本地行情尚未准备完成，请先下载行情后再运行回测",
        ) from exc
    save_backtest_result(db, effective_request, result, current_user)
    return result


def _apply_simulation_account(
    request: BacktestRunRequest,
    current_user: User | None,
    db: Session,
) -> BacktestRunRequest:
    account_id = request.config.simulationAccountId
    if account_id is None:
        return request

    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Simulation account requires login",
        )

    account = get_simulation_account(db, current_user, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation account not found",
        )

    config_data = request.config.model_dump()
    config_data.update(
        {
            "market": account.market,
            "initialCash": account.initial_cash,
            "simulationAccountId": account.id,
        }
    )
    effective_config = BacktestConfig(**config_data)
    return BacktestRunRequest(strategy=request.strategy, config=effective_config)
