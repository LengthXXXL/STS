from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.custom_block import CustomBlock
from app.models.user import User
from app.schemas.custom_block import (
    CustomBlockCreate,
    CustomBlockExposedParam,
    CustomBlockResponse,
    CustomBlockUpdate,
)

PUBLISHABLE_REVIEW_STATUSES = {"private", "rejected"}


def custom_block_to_response(block: CustomBlock) -> CustomBlockResponse:
    return CustomBlockResponse(
        id=block.id,
        ownerId=block.owner_id,
        name=block.name,
        description=block.description,
        category=block.category,
        tags=block.tags,
        template=block.template,
        exposedParams=block.exposed_params or [],
        reviewStatus=block.review_status,
        createdAt=block.created_at,
        updatedAt=block.updated_at,
    )


def create_custom_block(
    db: Session,
    owner: User,
    request: CustomBlockCreate,
) -> CustomBlockResponse:
    name = request.name.strip()
    if _custom_block_name_exists(db, owner, name):
        raise ValueError("Custom block name already exists")

    block = CustomBlock(
        owner_id=owner.id,
        name=name,
        description=request.description.strip() if request.description else None,
        category=request.category.strip(),
        tags=_normalize_tags(request.tags),
        template=request.template.model_dump(by_alias=True),
        exposed_params=_normalize_exposed_params(request.exposed_params, request),
        review_status="private",
    )
    db.add(block)
    _commit_custom_block_change(db)
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


def publish_custom_block(db: Session, owner: User, block_id: int) -> CustomBlockResponse | None:
    block = db.scalar(_owned_custom_block_statement(owner).where(CustomBlock.id == block_id))
    if block is None:
        return None
    if block.review_status not in PUBLISHABLE_REVIEW_STATUSES:
        raise ValueError("Custom block is already submitted or public")

    block.review_status = "pending_review"
    _commit_custom_block_change(db)
    db.refresh(block)
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

    name = request.name.strip()
    if _custom_block_name_exists(db, owner, name, exclude_id=block.id):
        raise ValueError("Custom block name already exists")

    block.name = name
    block.description = request.description.strip() if request.description else None
    block.category = request.category.strip()
    block.tags = _normalize_tags(request.tags)
    block.template = request.template.model_dump(by_alias=True)
    block.exposed_params = _normalize_exposed_params(request.exposed_params, request)
    _commit_custom_block_change(db)
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


def _custom_block_name_exists(
    db: Session,
    owner: User,
    name: str,
    *,
    exclude_id: int | None = None,
) -> bool:
    statement = _owned_custom_block_statement(owner).where(
        func.lower(CustomBlock.name) == name.lower()
    )
    if exclude_id is not None:
        statement = statement.where(CustomBlock.id != exclude_id)
    return db.scalar(select(func.count()).select_from(statement.subquery())) > 0


def _commit_custom_block_change(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Custom block name already exists") from exc


def _normalize_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    for tag in tags:
        value = tag.strip()
        if value and value not in normalized:
            normalized.append(value[:24])
    return normalized[:12]


def _normalize_exposed_params(
    params: list[CustomBlockExposedParam],
    request: CustomBlockCreate | CustomBlockUpdate,
) -> list[dict]:
    template_node_ids = {node.id for node in request.template.nodes}
    normalized: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for param in params:
        key = (param.node_id, param.param_key)
        if param.node_id not in template_node_ids or key in seen:
            continue
        seen.add(key)
        normalized.append(param.model_dump(by_alias=True))

    return normalized[:24]
