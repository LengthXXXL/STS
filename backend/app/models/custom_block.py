from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.shared_block import (
        RecommendationEvent,
        SharedBlockFavorite,
        SharedBlockImport,
        SharedBlockStats,
    )


class CustomBlock(Base):
    __tablename__ = "custom_blocks"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_custom_blocks_owner_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    template: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="private", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    owner = relationship("User", back_populates="custom_blocks")
    shared_stats: Mapped["SharedBlockStats | None"] = relationship(
        back_populates="custom_block",
        cascade="all, delete-orphan",
        uselist=False,
    )
    shared_favorites: Mapped[list["SharedBlockFavorite"]] = relationship(
        back_populates="custom_block",
        cascade="all, delete-orphan",
    )
    source_shared_imports: Mapped[list["SharedBlockImport"]] = relationship(
        back_populates="source_custom_block",
        cascade="all, delete-orphan",
        foreign_keys="SharedBlockImport.source_custom_block_id",
    )
    imported_shared_imports: Mapped[list["SharedBlockImport"]] = relationship(
        back_populates="imported_custom_block",
        cascade="all, delete-orphan",
        foreign_keys="SharedBlockImport.imported_custom_block_id",
    )
    recommendation_events: Mapped[list["RecommendationEvent"]] = relationship(
        back_populates="custom_block",
        cascade="all, delete-orphan",
    )
