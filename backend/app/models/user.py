from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.backtest import BacktestTask
    from app.models.custom_block import CustomBlock
    from app.models.forum import ForumComment, ForumPost
    from app.models.shared_block import (
        RecommendationEvent,
        SharedBlockFavorite,
        SharedBlockImport,
    )
    from app.models.simulation_account import SimulationAccount
    from app.models.strategy import Strategy

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        UniqueConstraint("email", name="uq_users_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    roles: Mapped[list["Role"]] = relationship(
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",
    )
    strategies: Mapped[list["Strategy"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    backtest_tasks: Mapped[list["BacktestTask"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    simulation_accounts: Mapped[list["SimulationAccount"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    custom_blocks: Mapped[list["CustomBlock"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    shared_block_favorites: Mapped[list["SharedBlockFavorite"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    shared_block_imports: Mapped[list["SharedBlockImport"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    recommendation_events: Mapped[list["RecommendationEvent"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    forum_posts: Mapped[list["ForumPost"]] = relationship(
        back_populates="author",
        cascade="all, delete-orphan",
    )
    forum_comments: Mapped[list["ForumComment"]] = relationship(
        back_populates="author",
        cascade="all, delete-orphan",
    )


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("name", name="uq_roles_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    users: Mapped[list[User]] = relationship(
        secondary=user_roles,
        back_populates="roles",
        lazy="selectin",
    )
