from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.forum import ForumComment, ForumPost
from app.models.user import User
from app.schemas.forum import (
    ForumCommentCreate,
    ForumCommentResponse,
    ForumPostCreate,
    ForumPostDetailResponse,
    ForumPostItemResponse,
)

APPROVED = "approved"
PENDING_REVIEW = "pending_review"
REJECTED = "rejected"


def forum_post_to_response(db: Session, post: ForumPost) -> ForumPostItemResponse:
    return ForumPostItemResponse(
        id=post.id,
        authorId=post.author_id,
        authorName=post.author.username,
        title=post.title,
        content=post.content,
        topic=post.topic,
        sharedBlockId=post.shared_block_id,
        reviewStatus=post.review_status,
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
        createdAt=comment.created_at,
        updatedAt=comment.updated_at,
    )


def create_forum_post(
    db: Session,
    author: User,
    request: ForumPostCreate,
) -> ForumPostItemResponse:
    post = ForumPost(
        author_id=author.id,
        title=request.title.strip(),
        content=request.content.strip(),
        topic=request.topic.strip(),
        shared_block_id=request.shared_block_id,
        review_status=PENDING_REVIEW,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return forum_post_to_response(db, post)


def list_forum_posts(
    db: Session,
    *,
    keyword: str = "",
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[ForumPostItemResponse], int]:
    statement = _approved_post_statement()
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
        statement.order_by(ForumPost.updated_at.desc(), ForumPost.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [forum_post_to_response(db, post) for post in posts], total


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
) -> ForumPostItemResponse | None:
    post = db.get(ForumPost, post_id)
    if post is None:
        return None

    post.review_status = review_status
    db.commit()
    db.refresh(post)
    return forum_post_to_response(db, post)


def review_forum_comment(
    db: Session,
    comment_id: int,
    review_status: str,
) -> ForumCommentResponse | None:
    comment = db.get(ForumComment, comment_id)
    if comment is None:
        return None

    comment.review_status = review_status
    db.commit()
    db.refresh(comment)
    return forum_comment_to_response(comment)


def _approved_post_statement() -> Select[tuple[ForumPost]]:
    return select(ForumPost).where(ForumPost.review_status == APPROVED)


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
