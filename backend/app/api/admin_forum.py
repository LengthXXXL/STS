from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.core.database import get_db
from app.models.user import User
from app.schemas.forum import (
    ForumCommentResponse,
    ForumCommentReviewListResponse,
    ForumPostItemResponse,
    ForumPostListResponse,
)
from app.services.forum_service import (
    APPROVED,
    REJECTED,
    list_forum_comment_reviews,
    list_forum_post_reviews,
    review_forum_comment,
    review_forum_post,
)

router = APIRouter(prefix="/admin", tags=["admin-forum"])


@router.get("/forum-post-reviews", response_model=ForumPostListResponse)
def list_post_reviews(
    keyword: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, alias="pageSize", ge=1, le=50),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> ForumPostListResponse:
    del current_user
    items, total = list_forum_post_reviews(db, keyword=keyword, page=page, page_size=page_size)
    return ForumPostListResponse(items=items, total=total, page=page, pageSize=page_size)


@router.get("/forum-comment-reviews", response_model=ForumCommentReviewListResponse)
def list_comment_reviews(
    keyword: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, alias="pageSize", ge=1, le=50),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> ForumCommentReviewListResponse:
    del current_user
    items, total = list_forum_comment_reviews(
        db,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return ForumCommentReviewListResponse(items=items, total=total, page=page, pageSize=page_size)


@router.post("/forum-posts/{post_id}/approve", response_model=ForumPostItemResponse)
def approve_post(
    post_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> ForumPostItemResponse:
    del current_user
    post = review_forum_post(db, post_id, APPROVED)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum post not found")
    return post


@router.post("/forum-posts/{post_id}/reject", response_model=ForumPostItemResponse)
def reject_post(
    post_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> ForumPostItemResponse:
    del current_user
    post = review_forum_post(db, post_id, REJECTED)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum post not found")
    return post


@router.post("/forum-comments/{comment_id}/approve", response_model=ForumCommentResponse)
def approve_comment(
    comment_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> ForumCommentResponse:
    del current_user
    comment = review_forum_comment(db, comment_id, APPROVED)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum comment not found")
    return comment


@router.post("/forum-comments/{comment_id}/reject", response_model=ForumCommentResponse)
def reject_comment(
    comment_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> ForumCommentResponse:
    del current_user
    comment = review_forum_comment(db, comment_id, REJECTED)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum comment not found")
    return comment
