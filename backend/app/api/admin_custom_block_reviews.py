from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_role
from app.core.database import get_db
from app.models.user import User
from app.schemas.shared_block import SharedBlockDetailResponse, SharedBlockListResponse
from app.services.shared_block_service import list_pending_reviews, review_custom_block

router = APIRouter(prefix="/admin/custom-block-reviews", tags=["admin-custom-block-reviews"])


@router.get("", response_model=SharedBlockListResponse)
def list_reviews(
    keyword: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, alias="pageSize", ge=1, le=50),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> SharedBlockListResponse:
    del current_user
    items, total = list_pending_reviews(db, keyword=keyword, page=page, page_size=page_size)
    return SharedBlockListResponse(items=items, total=total, page=page, pageSize=page_size)


@router.post("/{block_id}/approve", response_model=SharedBlockDetailResponse)
def approve(
    block_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> SharedBlockDetailResponse:
    del current_user
    block = review_custom_block(db, block_id, "approved")
    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review item not found",
        )
    return block


@router.post("/{block_id}/reject", response_model=SharedBlockDetailResponse)
def reject(
    block_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> SharedBlockDetailResponse:
    del current_user
    block = review_custom_block(db, block_id, "rejected")
    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review item not found",
        )
    return block
