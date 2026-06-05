from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.strategy import (
    StrategyCreate,
    StrategyListResponse,
    StrategyResponse,
    StrategyUpdate,
)
from app.services.strategy_service import (
    create_strategy,
    delete_strategy,
    get_strategy,
    list_strategies,
    update_strategy,
)

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.post("", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
def create(
    request: StrategyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrategyResponse:
    return create_strategy(db, current_user, request)


@router.get("", response_model=StrategyListResponse)
def list_current_user_strategies(
    keyword: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, alias="pageSize", ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrategyListResponse:
    items, total = list_strategies(
        db,
        current_user,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return StrategyListResponse(items=items, total=total, page=page, pageSize=page_size)


@router.get("/{strategy_id}", response_model=StrategyResponse)
def detail(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrategyResponse:
    strategy = get_strategy(db, current_user, strategy_id)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    return strategy


@router.put("/{strategy_id}", response_model=StrategyResponse)
def update(
    strategy_id: int,
    request: StrategyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrategyResponse:
    strategy = update_strategy(db, current_user, strategy_id, request)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    return strategy


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    deleted = delete_strategy(db, current_user, strategy_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
