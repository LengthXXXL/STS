from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_optional_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.custom_block import CustomBlockResponse
from app.schemas.shared_block import SharedBlockDetailResponse, SharedBlockListResponse
from app.services.shared_block_service import (
    favorite_shared_block,
    get_shared_block_detail,
    import_shared_block,
    list_my_favorite_shared_blocks,
    list_shared_blocks,
    unfavorite_shared_block,
)

router = APIRouter(prefix="/shared-blocks", tags=["shared-blocks"])


@router.get("", response_model=SharedBlockListResponse)
def list_public_shared_blocks(
    keyword: str = "",
    category: str = "",
    tag: str = "",
    sort: str = "latest",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, alias="pageSize", ge=1, le=50),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> SharedBlockListResponse:
    items, total = list_shared_blocks(
        db,
        current_user,
        keyword=keyword,
        category=category,
        tag=tag,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return SharedBlockListResponse(items=items, total=total, page=page, pageSize=page_size)


@router.get("/my-favorites", response_model=SharedBlockListResponse)
def list_my_favorites(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, alias="pageSize", ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SharedBlockListResponse:
    items, total = list_my_favorite_shared_blocks(
        db,
        current_user,
        page=page,
        page_size=page_size,
    )
    return SharedBlockListResponse(items=items, total=total, page=page, pageSize=page_size)


@router.post("/{block_id}/favorite", response_model=SharedBlockDetailResponse)
def favorite(
    block_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SharedBlockDetailResponse:
    block = favorite_shared_block(db, current_user, block_id)
    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shared block not found",
        )
    return block


@router.delete("/{block_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def unfavorite(
    block_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    unfavorited = unfavorite_shared_block(db, current_user, block_id)
    if not unfavorited:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shared block not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{block_id}/import",
    response_model=CustomBlockResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_block(
    block_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomBlockResponse:
    try:
        block = import_shared_block(db, current_user, block_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shared block not found",
        )
    return block


@router.get("/{block_id}", response_model=SharedBlockDetailResponse)
def detail(
    block_id: int,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> SharedBlockDetailResponse:
    block = get_shared_block_detail(db, current_user, block_id)
    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shared block not found",
        )
    return block
