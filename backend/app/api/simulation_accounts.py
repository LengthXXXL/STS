from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.simulation_account import (
    SimulationAccountCreate,
    SimulationAccountListResponse,
    SimulationAccountResponse,
    SimulationAccountUpdate,
)
from app.services.simulation_account_service import (
    create_simulation_account,
    delete_simulation_account,
    get_simulation_account,
    list_simulation_accounts,
    update_simulation_account,
)

router = APIRouter(prefix="/simulation-accounts", tags=["simulation-accounts"])


@router.post("", response_model=SimulationAccountResponse, status_code=status.HTTP_201_CREATED)
def create(
    request: SimulationAccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SimulationAccountResponse:
    return create_simulation_account(db, current_user, request)


@router.get("", response_model=SimulationAccountListResponse)
def list_current_user_simulation_accounts(
    keyword: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, alias="pageSize", ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SimulationAccountListResponse:
    items, total = list_simulation_accounts(
        db,
        current_user,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return SimulationAccountListResponse(items=items, total=total, page=page, pageSize=page_size)


@router.get("/{account_id}", response_model=SimulationAccountResponse)
def detail(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SimulationAccountResponse:
    account = get_simulation_account(db, current_user, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation account not found",
        )
    return account


@router.put("/{account_id}", response_model=SimulationAccountResponse)
def update(
    account_id: int,
    request: SimulationAccountUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SimulationAccountResponse:
    account = update_simulation_account(db, current_user, account_id, request)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation account not found",
        )
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    deleted = delete_simulation_account(db, current_user, account_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation account not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
