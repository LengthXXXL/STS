from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class ForumPost(Base):
    __tablename__ = "forum_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    shared_block_id: Mapped[int | None] = mapped_column(
        ForeignKey("custom_blocks.id"),
        nullable=True,
        index=True,
    )
    related_type: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    review_status: Mapped[str] = mapped_column(
        String(30),
        default="pending_review",
        nullable=False,
        index=True,
    )
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    author: Mapped["User"] = relationship(back_populates="forum_posts")
    comments: Mapped[list["ForumComment"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
    )


class ForumComment(Base):
    __tablename__ = "forum_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("forum_posts.id"), nullable=False, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(30),
        default="pending_review",
        nullable=False,
        index=True,
    )
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    post: Mapped[ForumPost] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship(back_populates="forum_comments")
