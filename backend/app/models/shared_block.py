from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.custom_block import CustomBlock
    from app.models.user import User


class SharedBlockStats(Base):
    __tablename__ = "shared_block_stats"
    __table_args__ = (
        UniqueConstraint("custom_block_id", name="uq_shared_block_stats_custom_block_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    custom_block_id: Mapped[int] = mapped_column(
        ForeignKey("custom_blocks.id"),
        nullable=False,
        index=True,
    )
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    favorite_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    import_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    custom_block: Mapped["CustomBlock"] = relationship(back_populates="shared_stats")


class SharedBlockFavorite(Base):
    __tablename__ = "shared_block_favorites"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "custom_block_id",
            name="uq_shared_block_favorites_user_block",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    custom_block_id: Mapped[int] = mapped_column(
        ForeignKey("custom_blocks.id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="shared_block_favorites")
    custom_block: Mapped["CustomBlock"] = relationship(back_populates="shared_favorites")


class SharedBlockImport(Base):
    __tablename__ = "shared_block_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    source_custom_block_id: Mapped[int] = mapped_column(
        ForeignKey("custom_blocks.id"),
        nullable=False,
        index=True,
    )
    imported_custom_block_id: Mapped[int] = mapped_column(
        ForeignKey("custom_blocks.id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="shared_block_imports")
    source_custom_block: Mapped["CustomBlock"] = relationship(
        foreign_keys=[source_custom_block_id],
        back_populates="source_shared_imports",
    )
    imported_custom_block: Mapped["CustomBlock"] = relationship(
        foreign_keys=[imported_custom_block_id],
        back_populates="imported_shared_imports",
    )


class RecommendationEvent(Base):
    __tablename__ = "recommendation_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    custom_block_id: Mapped[int | None] = mapped_column(
        ForeignKey("custom_blocks.id"),
        nullable=True,
        index=True,
    )
    keyword: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User | None"] = relationship(back_populates="recommendation_events")
    custom_block: Mapped["CustomBlock | None"] = relationship(
        back_populates="recommendation_events",
    )
