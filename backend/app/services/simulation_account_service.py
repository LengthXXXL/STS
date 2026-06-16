from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.simulation_account import SimulationAccount
from app.models.user import User
from app.schemas.simulation_account import (
    SimulationAccountCreate,
    SimulationAccountResponse,
    SimulationAccountUpdate,
)


def simulation_account_to_response(account: SimulationAccount) -> SimulationAccountResponse:
    return SimulationAccountResponse(
        id=account.id,
        ownerId=account.owner_id,
        name=account.name,
        description=account.description,
        market=account.market,
        initialCash=account.initial_cash,
        createdAt=account.created_at,
        updatedAt=account.updated_at,
    )


def create_simulation_account(
    db: Session,
    owner: User,
    request: SimulationAccountCreate,
) -> SimulationAccountResponse:
    account = SimulationAccount(
        owner_id=owner.id,
        name=request.name.strip(),
        description=request.description.strip() if request.description else None,
        market=request.market,
        initial_cash=request.initial_cash,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return simulation_account_to_response(account)


def list_simulation_accounts(
    db: Session,
    owner: User,
    *,
    keyword: str = "",
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[SimulationAccountResponse], int]:
    statement = _owned_simulation_account_statement(owner)
    keyword = keyword.strip()
    if keyword:
        statement = statement.where(
            or_(
                SimulationAccount.name.like(f"%{keyword}%"),
                SimulationAccount.description.like(f"%{keyword}%"),
                SimulationAccount.market.like(f"%{keyword}%"),
            )
        )

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    accounts = db.scalars(
        statement.order_by(SimulationAccount.updated_at.desc(), SimulationAccount.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return [simulation_account_to_response(account) for account in accounts], total


def get_simulation_account(
    db: Session,
    owner: User,
    account_id: int,
) -> SimulationAccountResponse | None:
    account = db.scalar(
        _owned_simulation_account_statement(owner).where(SimulationAccount.id == account_id)
    )
    if account is None:
        return None
    return simulation_account_to_response(account)


def update_simulation_account(
    db: Session,
    owner: User,
    account_id: int,
    request: SimulationAccountUpdate,
) -> SimulationAccountResponse | None:
    account = db.scalar(
        _owned_simulation_account_statement(owner).where(SimulationAccount.id == account_id)
    )
    if account is None:
        return None

    account.name = request.name.strip()
    account.description = request.description.strip() if request.description else None
    account.market = request.market
    account.initial_cash = request.initial_cash
    db.commit()
    db.refresh(account)
    return simulation_account_to_response(account)


def delete_simulation_account(db: Session, owner: User, account_id: int) -> bool:
    account = db.scalar(
        _owned_simulation_account_statement(owner).where(SimulationAccount.id == account_id)
    )
    if account is None:
        return False

    db.delete(account)
    db.commit()
    return True


def _owned_simulation_account_statement(owner: User) -> Select[tuple[SimulationAccount]]:
    return select(SimulationAccount).where(SimulationAccount.owner_id == owner.id)
