from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_optional_current_user
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
from app.services.file_service import resolve_download_path
from app.services.forum_service import (
    ForumAttachmentNotFound,
    ForumRelatedContentNotFound,
    create_forum_comment,
    create_forum_post,
    get_forum_post_detail,
    get_public_forum_attachment,
    list_forum_posts,
    list_my_favorite_forum_posts,
    list_my_forum_comments,
    list_my_forum_posts,
    react_to_forum_post,
    unreact_to_forum_post,
)

router = APIRouter(prefix="/forum", tags=["forum"])


@router.get("/posts", response_model=ForumPostListResponse)
def list_posts(
    keyword: str = "",
    topic: str = "",
    author: str = "",
    related_type: Literal["", "strategy", "backtest", "custom_block", "shared_block"] = Query(
        default="",
        alias="relatedType",
    ),
    sort: Literal[
        "latest_reply",
        "newest",
        "most_commented",
        "most_liked",
        "most_favorited",
        "hot",
    ] = Query(default="latest_reply"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, alias="pageSize", ge=1, le=50),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> ForumPostListResponse:
    items, total = list_forum_posts(
        db,
        current_user,
        keyword=keyword,
        topic=topic,
        author=author,
        related_type=related_type,
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
    except ForumAttachmentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
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


@router.get("/my-favorites", response_model=ForumPostListResponse)
def list_my_favorites(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, alias="pageSize", ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ForumPostListResponse:
    items, total = list_my_favorite_forum_posts(
        db,
        current_user,
        page=page,
        page_size=page_size,
    )
    return ForumPostListResponse(items=items, total=total, page=page, pageSize=page_size)


@router.get("/posts/{post_id}", response_model=ForumPostDetailResponse)
def detail(
    post_id: int,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> ForumPostDetailResponse:
    post = get_forum_post_detail(db, post_id, current_user)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum post not found")
    return post


@router.post("/posts/{post_id}/like", response_model=ForumPostDetailResponse)
def like_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ForumPostDetailResponse:
    post = react_to_forum_post(db, current_user, post_id, "like")
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum post not found")
    return post


@router.delete("/posts/{post_id}/like", status_code=status.HTTP_204_NO_CONTENT)
def unlike_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if not unreact_to_forum_post(db, current_user, post_id, "like"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum post not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/posts/{post_id}/favorite", response_model=ForumPostDetailResponse)
def favorite_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ForumPostDetailResponse:
    post = react_to_forum_post(db, current_user, post_id, "favorite")
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum post not found")
    return post


@router.delete("/posts/{post_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def unfavorite_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if not unreact_to_forum_post(db, current_user, post_id, "favorite"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forum post not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/posts/{post_id}/attachments/{file_id}/download")
def download_attachment(
    post_id: int,
    file_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    file_record = get_public_forum_attachment(db, post_id, file_id)
    if file_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    try:
        path = resolve_download_path(file_record)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment content not found",
        ) from exc
    return FileResponse(
        path,
        filename=file_record.original_name,
        media_type=file_record.content_type,
    )


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
