from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.uploaded_file import UploadedFile
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
    attachments: Mapped[list["ForumPostAttachment"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
    )
    reactions: Mapped[list["ForumPostReaction"]] = relationship(
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


class ForumPostAttachment(Base):
    __tablename__ = "forum_post_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("forum_posts.id"), nullable=False, index=True)
    file_id: Mapped[int] = mapped_column(
        ForeignKey("uploaded_files.id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    post: Mapped[ForumPost] = relationship(back_populates="attachments")
    file: Mapped["UploadedFile"] = relationship()


class ForumPostReaction(Base):
    __tablename__ = "forum_post_reactions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "post_id",
            "reaction_type",
            name="uq_forum_post_reactions_user_post_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("forum_posts.id"), nullable=False, index=True)
    reaction_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    post: Mapped[ForumPost] = relationship(back_populates="reactions")
    user: Mapped["User"] = relationship(back_populates="forum_post_reactions")
