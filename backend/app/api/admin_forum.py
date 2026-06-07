from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.core.database import get_db
from app.models.user import User
from app.schemas.forum import ForumCommentResponse, ForumPostItemResponse
from app.services.forum_service import APPROVED, REJECTED, review_forum_comment, review_forum_post

router = APIRouter(prefix="/admin", tags=["admin-forum"])


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
