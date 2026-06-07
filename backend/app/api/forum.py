from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.forum import (
    ForumCommentCreate,
    ForumCommentResponse,
    ForumCommentReviewListResponse,
    ForumPostCreate,
    ForumPostDetailResponse,
    ForumPostItemResponse,
    ForumPostListResponse,
)
from app.services.forum_service import (
    ForumRelatedContentNotFound,
    create_forum_comment,
    create_forum_post,
    get_forum_post_detail,
    list_forum_posts,
    list_my_forum_comments,
    list_my_forum_posts,
)

router = APIRouter(prefix="/forum", tags=["forum"])


@router.get("/posts", response_model=ForumPostListResponse)
def list_posts(
    keyword: str = "",
    sort: Literal["latest_reply", "newest", "most_commented"] = Query(default="latest_reply"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, alias="pageSize", ge=1, le=50),
    db: Session = Depends(get_db),
) -> ForumPostListResponse:
    items, total = list_forum_posts(
        db,
        keyword=keyword,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return ForumPostListResponse(items=items, total=total, page=page, pageSize=page_size)


@router.post("/posts", response_model=ForumPostItemResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    request: ForumPostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ForumPostItemResponse:
    try:
        return create_forum_post(db, current_user, request)
    except ForumRelatedContentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/my-posts", response_model=ForumPostListResponse)
def list_my_posts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, alias="pageSize", ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ForumPostListResponse:
    items, total = list_my_forum_posts(db, current_user, page=page, page_size=page_size)
    return ForumPostListResponse(items=items, total=total, page=page, pageSize=page_size)


@router.get("/my-comments", response_model=ForumCommentReviewListResponse)
def list_my_comments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, alias="pageSize", ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ForumCommentReviewListResponse:
    items, total = list_my_forum_comments(db, current_user, page=page, page_size=page_size)
    return ForumCommentReviewListResponse(items=items, total=total, page=page, pageSize=page_size)


@router.get("/posts/{post_id}", response_model=ForumPostDetailResponse)
def detail(
    post_id: int,
    db: Session = Depends(get_db),
) -> ForumPostDetailResponse:
    post = get_forum_post_detail(db, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum post not found")
    return post


@router.post(
    "/posts/{post_id}/comments",
    response_model=ForumCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    post_id: int,
    request: ForumCommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ForumCommentResponse:
    comment = create_forum_comment(db, current_user, post_id, request)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum post not found")
    return comment
