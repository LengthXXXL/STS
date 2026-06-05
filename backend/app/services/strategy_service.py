from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.strategy import Strategy
from app.models.user import User
from app.schemas.strategy import StrategyCreate, StrategyResponse, StrategyUpdate


def strategy_to_response(strategy: Strategy) -> StrategyResponse:
    return StrategyResponse(
        id=strategy.id,
        ownerId=strategy.owner_id,
        name=strategy.name,
        description=strategy.description,
        strategy=strategy.strategy,
        backtestConfig=strategy.backtest_config,
        isPublic=strategy.is_public,
        createdAt=strategy.created_at,
        updatedAt=strategy.updated_at,
    )


def create_strategy(db: Session, owner: User, request: StrategyCreate) -> StrategyResponse:
    strategy = Strategy(
        owner_id=owner.id,
        name=request.name.strip(),
        description=request.description.strip() if request.description else None,
        strategy=request.strategy.model_dump(by_alias=True),
        backtest_config=(
            request.backtest_config.model_dump(by_alias=True) if request.backtest_config else None
        ),
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy_to_response(strategy)


def list_strategies(
    db: Session,
    owner: User,
    *,
    keyword: str = "",
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[StrategyResponse], int]:
    statement = _owned_strategy_statement(owner)
    keyword = keyword.strip()
    if keyword:
        statement = statement.where(Strategy.name.like(f"%{keyword}%"))

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    strategies = db.scalars(
        statement.order_by(Strategy.updated_at.desc(), Strategy.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return [strategy_to_response(strategy) for strategy in strategies], total


def get_strategy(db: Session, owner: User, strategy_id: int) -> StrategyResponse | None:
    strategy = db.scalar(_owned_strategy_statement(owner).where(Strategy.id == strategy_id))
    if strategy is None:
        return None
    return strategy_to_response(strategy)


def update_strategy(
    db: Session,
    owner: User,
    strategy_id: int,
    request: StrategyUpdate,
) -> StrategyResponse | None:
    strategy = db.scalar(_owned_strategy_statement(owner).where(Strategy.id == strategy_id))
    if strategy is None:
        return None

    strategy.name = request.name.strip()
    strategy.description = request.description.strip() if request.description else None
    strategy.strategy = request.strategy.model_dump(by_alias=True)
    strategy.backtest_config = (
        request.backtest_config.model_dump(by_alias=True) if request.backtest_config else None
    )
    db.commit()
    db.refresh(strategy)
    return strategy_to_response(strategy)


def delete_strategy(db: Session, owner: User, strategy_id: int) -> bool:
    strategy = db.scalar(_owned_strategy_statement(owner).where(Strategy.id == strategy_id))
    if strategy is None:
        return False

    db.delete(strategy)
    db.commit()
    return True


def _owned_strategy_statement(owner: User) -> Select[tuple[Strategy]]:
    return select(Strategy).where(Strategy.owner_id == owner.id)
