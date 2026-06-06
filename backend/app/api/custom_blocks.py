from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.custom_block import (
    CustomBlockCreate,
    CustomBlockListResponse,
    CustomBlockResponse,
    CustomBlockUpdate,
)
from app.services.custom_block_service import (
    create_custom_block,
    delete_custom_block,
    get_custom_block,
    list_custom_blocks,
    update_custom_block,
)

router = APIRouter(prefix="/custom-blocks", tags=["custom-blocks"])


@router.post("", response_model=CustomBlockResponse, status_code=status.HTTP_201_CREATED)
def create(
    request: CustomBlockCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomBlockResponse:
    return create_custom_block(db, current_user, request)


@router.get("", response_model=CustomBlockListResponse)
def list_current_user_custom_blocks(
    keyword: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, alias="pageSize", ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomBlockListResponse:
    items, total = list_custom_blocks(
        db,
        current_user,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return CustomBlockListResponse(items=items, total=total, page=page, pageSize=page_size)


@router.get("/{block_id}", response_model=CustomBlockResponse)
def detail(
    block_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomBlockResponse:
    block = get_custom_block(db, current_user, block_id)
    if block is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom block not found")
    return block


@router.put("/{block_id}", response_model=CustomBlockResponse)
def update(
    block_id: int,
    request: CustomBlockUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomBlockResponse:
    block = update_custom_block(db, current_user, block_id, request)
    if block is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom block not found")
    return block


@router.delete("/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    block_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    deleted = delete_custom_block(db, current_user, block_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom block not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
