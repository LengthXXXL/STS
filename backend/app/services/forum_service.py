from typing import Literal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.backtest import BacktestTask
from app.models.custom_block import CustomBlock
from app.models.forum import ForumComment, ForumPost, ForumPostAttachment
from app.models.strategy import Strategy
from app.models.uploaded_file import UploadedFile
from app.models.user import User
from app.schemas.forum import (
    ForumAttachmentResponse,
    ForumCommentCreate,
    ForumCommentResponse,
    ForumCommentReviewResponse,
    ForumPostCreate,
    ForumPostDetailResponse,
    ForumPostItemResponse,
)

APPROVED = "approved"
PENDING_REVIEW = "pending_review"
REJECTED = "rejected"
ForumPostSort = Literal["latest_reply", "newest", "most_commented"]


class ForumRelatedContentNotFound(ValueError):
    pass


class ForumAttachmentNotFound(ValueError):
    pass


def forum_post_to_response(db: Session, post: ForumPost) -> ForumPostItemResponse:
    related_title, related_summary = _related_content_summary(db, post)
    return ForumPostItemResponse(
        id=post.id,
        authorId=post.author_id,
        authorName=post.author.username,
        title=post.title,
        content=post.content,
        topic=post.topic,
        sharedBlockId=post.shared_block_id,
        relatedType=post.related_type,
        relatedId=post.related_id,
        relatedTitle=related_title,
        relatedSummary=related_summary,
        reviewStatus=post.review_status,
        reviewReason=post.review_reason,
        attachments=[forum_attachment_to_response(attachment) for attachment in post.attachments],
        commentCount=_approved_comment_count(db, post.id),
        createdAt=post.created_at,
        updatedAt=post.updated_at,
    )


def forum_comment_to_response(comment: ForumComment) -> ForumCommentResponse:
    return ForumCommentResponse(
        id=comment.id,
        postId=comment.post_id,
        authorId=comment.author_id,
        authorName=comment.author.username,
        content=comment.content,
        reviewStatus=comment.review_status,
        reviewReason=comment.review_reason,
        createdAt=comment.created_at,
        updatedAt=comment.updated_at,
    )


def forum_comment_to_review_response(comment: ForumComment) -> ForumCommentReviewResponse:
    base = forum_comment_to_response(comment)
    return ForumCommentReviewResponse(
        **base.model_dump(by_alias=True),
        postTitle=comment.post.title,
    )


def forum_attachment_to_response(attachment: ForumPostAttachment) -> ForumAttachmentResponse:
    return ForumAttachmentResponse(
        id=attachment.id,
        fileId=attachment.file_id,
        originalName=attachment.file.original_name,
        contentType=attachment.file.content_type,
        size=attachment.file.size,
        downloadUrl=f"/api/forum/posts/{attachment.post_id}/attachments/{attachment.file_id}/download",
    )


def create_forum_post(
    db: Session,
    author: User,
    request: ForumPostCreate,
) -> ForumPostItemResponse:
    related_type = request.related_type
    related_id = request.related_id
    if (related_type is None) != (related_id is None):
        raise ValueError("Related content requires both type and id")
    if related_type is not None and related_id is not None:
        _ensure_related_content_access(db, author, related_type, related_id)

    attachment_files = _owned_attachment_files(db, author, request.attachment_file_ids)
    post = ForumPost(
        author_id=author.id,
        title=request.title.strip(),
        content=request.content.strip(),
        topic=request.topic.strip(),
        shared_block_id=request.shared_block_id,
        related_type=related_type,
        related_id=related_id,
        review_status=PENDING_REVIEW,
    )
    db.add(post)
    db.flush()
    for file in attachment_files:
        file.business_type = "forum"
        file.business_id = post.id
        file.visibility = "public"
        db.add(ForumPostAttachment(post_id=post.id, file_id=file.id))
    db.commit()
    db.refresh(post)
    return forum_post_to_response(db, post)


def list_forum_posts(
    db: Session,
    *,
    keyword: str = "",
    sort: ForumPostSort = "latest_reply",
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[ForumPostItemResponse], int]:
    activity = _approved_comment_activity_subquery()
    statement = _approved_post_statement().outerjoin(activity, ForumPost.id == activity.c.post_id)
    keyword = keyword.strip()
    if keyword:
        statement = statement.where(
            or_(
                ForumPost.title.like(f"%{keyword}%"),
                ForumPost.content.like(f"%{keyword}%"),
                ForumPost.topic.like(f"%{keyword}%"),
            )
        )

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    posts = db.scalars(
        statement.order_by(*_public_post_order_by(sort, activity))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [forum_post_to_response(db, post) for post in posts], total


def list_my_forum_posts(
    db: Session,
    author: User,
    *,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[ForumPostItemResponse], int]:
    statement = select(ForumPost).where(ForumPost.author_id == author.id)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    posts = db.scalars(
        statement.order_by(ForumPost.updated_at.desc(), ForumPost.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [forum_post_to_response(db, post) for post in posts], total


def list_forum_post_reviews(
    db: Session,
    *,
    keyword: str = "",
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[ForumPostItemResponse], int]:
    statement = select(ForumPost).where(ForumPost.review_status == PENDING_REVIEW)
    keyword = keyword.strip()
    if keyword:
        statement = statement.where(
            or_(
                ForumPost.title.like(f"%{keyword}%"),
                ForumPost.content.like(f"%{keyword}%"),
                ForumPost.topic.like(f"%{keyword}%"),
                ForumPost.author.has(User.username.like(f"%{keyword}%")),
            )
        )

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    posts = db.scalars(
        statement.order_by(ForumPost.updated_at.desc(), ForumPost.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [forum_post_to_response(db, post) for post in posts], total


def list_forum_comment_reviews(
    db: Session,
    *,
    keyword: str = "",
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[ForumCommentReviewResponse], int]:
    statement = select(ForumComment).where(ForumComment.review_status == PENDING_REVIEW)
    keyword = keyword.strip()
    if keyword:
        statement = statement.where(
            or_(
                ForumComment.content.like(f"%{keyword}%"),
                ForumComment.author.has(User.username.like(f"%{keyword}%")),
                ForumComment.post.has(ForumPost.title.like(f"%{keyword}%")),
            )
        )

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    comments = db.scalars(
        statement.order_by(ForumComment.updated_at.desc(), ForumComment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [forum_comment_to_review_response(comment) for comment in comments], total


def list_my_forum_comments(
    db: Session,
    author: User,
    *,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[ForumCommentReviewResponse], int]:
    statement = select(ForumComment).where(ForumComment.author_id == author.id)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    comments = db.scalars(
        statement.order_by(ForumComment.updated_at.desc(), ForumComment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [forum_comment_to_review_response(comment) for comment in comments], total


def get_forum_post_detail(db: Session, post_id: int) -> ForumPostDetailResponse | None:
    post = db.scalar(_approved_post_statement().where(ForumPost.id == post_id))
    if post is None:
        return None

    comments = db.scalars(
        select(ForumComment)
        .where(
            ForumComment.post_id == post.id,
            ForumComment.review_status == APPROVED,
        )
        .order_by(ForumComment.created_at.asc(), ForumComment.id.asc())
    ).all()
    base = forum_post_to_response(db, post)
    return ForumPostDetailResponse(
        **base.model_dump(by_alias=True),
        comments=[forum_comment_to_response(comment) for comment in comments],
    )


def get_public_forum_attachment(
    db: Session,
    post_id: int,
    file_id: int,
) -> UploadedFile | None:
    attachment = db.scalar(
        select(ForumPostAttachment)
        .join(ForumPost)
        .where(
            ForumPostAttachment.post_id == post_id,
            ForumPostAttachment.file_id == file_id,
            ForumPost.review_status == APPROVED,
        )
    )
    if attachment is None:
        return None
    return attachment.file


def create_forum_comment(
    db: Session,
    author: User,
    post_id: int,
    request: ForumCommentCreate,
) -> ForumCommentResponse | None:
    post = db.scalar(_approved_post_statement().where(ForumPost.id == post_id))
    if post is None:
        return None

    comment = ForumComment(
        post_id=post.id,
        author_id=author.id,
        content=request.content.strip(),
        review_status=PENDING_REVIEW,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return forum_comment_to_response(comment)


def review_forum_post(
    db: Session,
    post_id: int,
    review_status: str,
    review_reason: str | None = None,
) -> ForumPostItemResponse | None:
    post = db.get(ForumPost, post_id)
    if post is None:
        return None

    post.review_status = review_status
    post.review_reason = review_reason.strip() if review_reason else None
    db.commit()
    db.refresh(post)
    return forum_post_to_response(db, post)


def review_forum_comment(
    db: Session,
    comment_id: int,
    review_status: str,
    review_reason: str | None = None,
) -> ForumCommentResponse | None:
    comment = db.get(ForumComment, comment_id)
    if comment is None:
        return None

    comment.review_status = review_status
    comment.review_reason = review_reason.strip() if review_reason else None
    db.commit()
    db.refresh(comment)
    return forum_comment_to_response(comment)


def _approved_post_statement() -> Select[tuple[ForumPost]]:
    return select(ForumPost).where(ForumPost.review_status == APPROVED)


def _approved_comment_activity_subquery():
    return (
        select(
            ForumComment.post_id.label("post_id"),
            func.max(ForumComment.updated_at).label("latest_comment_at"),
            func.count(ForumComment.id).label("approved_comment_count"),
        )
        .where(ForumComment.review_status == APPROVED)
        .group_by(ForumComment.post_id)
        .subquery()
    )


def _public_post_order_by(sort: ForumPostSort, activity):
    latest_reply_at = func.coalesce(activity.c.latest_comment_at, ForumPost.updated_at)
    approved_comment_count = func.coalesce(activity.c.approved_comment_count, 0)
    if sort == "newest":
        return (ForumPost.created_at.desc(), ForumPost.id.desc())
    if sort == "most_commented":
        return (approved_comment_count.desc(), latest_reply_at.desc(), ForumPost.id.desc())
    return (latest_reply_at.desc(), ForumPost.id.desc())


def _ensure_related_content_access(
    db: Session,
    author: User,
    related_type: str,
    related_id: int,
) -> None:
    if related_type == "strategy":
        exists = db.scalar(
            select(func.count()).where(Strategy.id == related_id, Strategy.owner_id == author.id)
        )
    elif related_type == "backtest":
        exists = db.scalar(
            select(func.count()).where(
                BacktestTask.id == related_id,
                BacktestTask.owner_id == author.id,
            )
        )
    elif related_type == "custom_block":
        exists = db.scalar(
            select(func.count()).where(
                CustomBlock.id == related_id,
                CustomBlock.owner_id == author.id,
            )
        )
    elif related_type == "shared_block":
        exists = db.scalar(
            select(func.count()).where(
                CustomBlock.id == related_id,
                CustomBlock.review_status == APPROVED,
            )
        )
    else:
        exists = 0

    if not exists:
        raise ForumRelatedContentNotFound("Related content not found")


def _owned_attachment_files(
    db: Session,
    author: User,
    attachment_file_ids: list[int],
) -> list[UploadedFile]:
    unique_ids = list(dict.fromkeys(attachment_file_ids))
    if not unique_ids:
        return []

    files = db.scalars(
        select(UploadedFile).where(
            UploadedFile.id.in_(unique_ids),
            UploadedFile.owner_id == author.id,
        )
    ).all()
    files_by_id = {file.id: file for file in files}
    if any(file_id not in files_by_id for file_id in unique_ids):
        raise ForumAttachmentNotFound("Attachment file not found")
    return [files_by_id[file_id] for file_id in unique_ids]


def _related_content_summary(db: Session, post: ForumPost) -> tuple[str | None, str | None]:
    if post.related_type is None or post.related_id is None:
        return None, None

    if post.related_type == "strategy":
        strategy = db.scalar(
            select(Strategy).where(
                Strategy.id == post.related_id,
                Strategy.owner_id == post.author_id,
            )
        )
        if strategy is None:
            return "关联策略不可用", "原策略已删除或不可访问"
        config = strategy.backtest_config or {}
        symbol = config.get("symbol") or "未设置股票"
        timeframe = _format_timeframe(config.get("timeframe"))
        return strategy.name, f"策略 · {symbol} · {timeframe}"

    if post.related_type == "backtest":
        backtest = db.scalar(
            select(BacktestTask).where(
                BacktestTask.id == post.related_id,
                BacktestTask.owner_id == post.author_id,
            )
        )
        if backtest is None:
            return "关联回测不可用", "原回测已删除或不可访问"
        return (
            f"{backtest.symbol} {backtest.timeframe} 回测",
            f"收益 {backtest.total_return_percent}% · 最大回撤 {backtest.max_drawdown_percent}%",
        )

    if post.related_type == "custom_block":
        block = db.scalar(
            select(CustomBlock).where(
                CustomBlock.id == post.related_id,
                CustomBlock.owner_id == post.author_id,
            )
        )
        if block is None:
            return "关联积木不可用", "原积木已删除或不可访问"
        return block.name, _custom_block_summary("我的积木", block)

    if post.related_type == "shared_block":
        block = db.scalar(
            select(CustomBlock).where(
                CustomBlock.id == post.related_id,
                CustomBlock.review_status == APPROVED,
            )
        )
        if block is None:
            return "公开积木不可用", "原公开积木已下架或不可访问"
        return block.name, _custom_block_summary("公开积木", block)

    return None, None


def _custom_block_summary(prefix: str, block: CustomBlock) -> str:
    node_count = len((block.template or {}).get("nodes", []))
    return f"{prefix} · {block.category} · {node_count} 个积木"


def _format_timeframe(value: str | None) -> str:
    if value == "1m":
        return "1分钟"
    if value == "5m":
        return "5分钟"
    return "未设置周期"


def _approved_comment_count(db: Session, post_id: int) -> int:
    return (
        db.scalar(
            select(func.count()).where(
                ForumComment.post_id == post_id,
                ForumComment.review_status == APPROVED,
            )
        )
        or 0
    )
