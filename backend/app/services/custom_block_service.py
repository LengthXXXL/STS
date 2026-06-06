from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.custom_block import CustomBlock
from app.models.user import User
from app.schemas.custom_block import CustomBlockCreate, CustomBlockResponse, CustomBlockUpdate


def custom_block_to_response(block: CustomBlock) -> CustomBlockResponse:
    return CustomBlockResponse(
        id=block.id,
        ownerId=block.owner_id,
        name=block.name,
        description=block.description,
        category=block.category,
        tags=block.tags,
        template=block.template,
        reviewStatus=block.review_status,
        createdAt=block.created_at,
        updatedAt=block.updated_at,
    )


def create_custom_block(
    db: Session,
    owner: User,
    request: CustomBlockCreate,
) -> CustomBlockResponse:
    block = CustomBlock(
        owner_id=owner.id,
        name=request.name.strip(),
        description=request.description.strip() if request.description else None,
        category=request.category.strip(),
        tags=_normalize_tags(request.tags),
        template=request.template.model_dump(by_alias=True),
        review_status="private",
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return custom_block_to_response(block)


def list_custom_blocks(
    db: Session,
    owner: User,
    *,
    keyword: str = "",
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[CustomBlockResponse], int]:
    statement = _owned_custom_block_statement(owner)
    keyword = keyword.strip()
    if keyword:
        statement = statement.where(
            or_(
                CustomBlock.name.like(f"%{keyword}%"),
                CustomBlock.description.like(f"%{keyword}%"),
                CustomBlock.category.like(f"%{keyword}%"),
            )
        )

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    blocks = db.scalars(
        statement.order_by(CustomBlock.updated_at.desc(), CustomBlock.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return [custom_block_to_response(block) for block in blocks], total


def get_custom_block(db: Session, owner: User, block_id: int) -> CustomBlockResponse | None:
    block = db.scalar(_owned_custom_block_statement(owner).where(CustomBlock.id == block_id))
    if block is None:
        return None
    return custom_block_to_response(block)


def update_custom_block(
    db: Session,
    owner: User,
    block_id: int,
    request: CustomBlockUpdate,
) -> CustomBlockResponse | None:
    block = db.scalar(_owned_custom_block_statement(owner).where(CustomBlock.id == block_id))
    if block is None:
        return None

    block.name = request.name.strip()
    block.description = request.description.strip() if request.description else None
    block.category = request.category.strip()
    block.tags = _normalize_tags(request.tags)
    block.template = request.template.model_dump(by_alias=True)
    db.commit()
    db.refresh(block)
    return custom_block_to_response(block)


def delete_custom_block(db: Session, owner: User, block_id: int) -> bool:
    block = db.scalar(_owned_custom_block_statement(owner).where(CustomBlock.id == block_id))
    if block is None:
        return False

    db.delete(block)
    db.commit()
    return True


def _owned_custom_block_statement(owner: User) -> Select[tuple[CustomBlock]]:
    return select(CustomBlock).where(CustomBlock.owner_id == owner.id)


def _normalize_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    for tag in tags:
        value = tag.strip()
        if value and value not in normalized:
            normalized.append(value[:24])
    return normalized[:12]
