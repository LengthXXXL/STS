from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_optional_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.shared_block import SharedBlockDetailResponse, SharedBlockListResponse
from app.services.shared_block_service import get_shared_block_detail, list_shared_blocks

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
