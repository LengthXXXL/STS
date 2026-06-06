from copy import deepcopy
from datetime import datetime

from sqlalchemy import Select, case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.custom_block import CustomBlock
from app.models.shared_block import (
    RecommendationEvent,
    SharedBlockFavorite,
    SharedBlockImport,
    SharedBlockStats,
)
from app.models.user import User
from app.schemas.custom_block import CustomBlockResponse
from app.schemas.shared_block import SharedBlockDetailResponse, SharedBlockItemResponse
from app.services.custom_block_service import custom_block_to_response

BEGINNER_CATEGORIES = ["动作", "风控"]
BEGINNER_TAGS = ["新手", "基础", "止盈", "止损"]
MAX_IMPORT_RETRIES = 25
STATS_CREATE_RETRIES = 2


class SharedBlockStatsUnavailable(RuntimeError):
    pass


def _approved_statement() -> Select[tuple[CustomBlock]]:
    return (
        select(CustomBlock)
        .where(CustomBlock.review_status == "approved")
        .options(selectinload(CustomBlock.owner), selectinload(CustomBlock.shared_stats))
    )


def _approved_block(db: Session, block_id: int) -> CustomBlock | None:
    return db.scalar(_approved_statement().where(CustomBlock.id == block_id))


def _stats_for(db: Session, block: CustomBlock) -> SharedBlockStats:
    if block.shared_stats is not None:
        return block.shared_stats

    stats = SharedBlockStats(custom_block_id=block.id)
    db.add(stats)
    db.flush()
    block.shared_stats = stats
    return stats


def _ensure_approved_block_stats(db: Session, block_id: int) -> CustomBlock | None:
    for _ in range(STATS_CREATE_RETRIES):
        block = _approved_block(db, block_id)
        if block is None:
            return None
        if block.shared_stats is not None:
            return block

        stats = SharedBlockStats(custom_block_id=block.id)
        db.add(stats)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            block = _approved_block(db, block_id)
            if block is None:
                return None
            if block.shared_stats is not None:
                return block
            continue
        else:
            block.shared_stats = stats
            return block

    raise SharedBlockStatsUnavailable("Shared block stats unavailable")


def _increment_stat(db: Session, block_id: int, field: str) -> None:
    column = getattr(SharedBlockStats, field)
    result = db.execute(
        update(SharedBlockStats)
        .where(SharedBlockStats.custom_block_id == block_id)
        .values({field: column + 1, "updated_at": datetime.utcnow()})
    )
    if result.rowcount != 1:
        raise SharedBlockStatsUnavailable("Shared block stats unavailable")


def _decrement_stat_safely(db: Session, block_id: int, field: str) -> None:
    column = getattr(SharedBlockStats, field)
    result = db.execute(
        update(SharedBlockStats)
        .where(SharedBlockStats.custom_block_id == block_id)
        .values(
            {
                field: case((column > 0, column - 1), else_=0),
                "updated_at": datetime.utcnow(),
            }
        )
    )
    if result.rowcount != 1:
        raise SharedBlockStatsUnavailable("Shared block stats unavailable")


def _is_favorited(db: Session, user: User | None, block_id: int) -> bool:
    if user is None:
        return False

    favorite_id = db.scalar(
        select(SharedBlockFavorite.id).where(
            SharedBlockFavorite.user_id == user.id,
            SharedBlockFavorite.custom_block_id == block_id,
        )
    )
    return favorite_id is not None


def _has_tag(block: CustomBlock, tag: str) -> bool:
    return tag in (block.tags or [])


def _matches_keyword(block: CustomBlock, keyword: str) -> bool:
    return (
        keyword in block.name
        or keyword in (block.description or "")
        or keyword in block.category
        or _has_tag(block, keyword)
    )


def _is_beginner_block(block: CustomBlock) -> bool:
    tags = block.tags or []
    return block.category in BEGINNER_CATEGORIES or any(tag in tags for tag in BEGINNER_TAGS)


def _to_item(
    db: Session,
    block: CustomBlock,
    current_user: User | None,
) -> SharedBlockItemResponse:
    stats = block.shared_stats
    nodes = block.template.get("nodes", [])
    edges = block.template.get("edges", [])
    return SharedBlockItemResponse(
        id=block.id,
        ownerId=block.owner_id,
        authorName=block.owner.username,
        name=block.name,
        description=block.description,
        category=block.category,
        tags=block.tags,
        reviewStatus=block.review_status,
        nodeCount=len(nodes),
        connectionCount=len(edges),
        viewCount=stats.view_count if stats is not None else 0,
        favoriteCount=stats.favorite_count if stats is not None else 0,
        importCount=stats.import_count if stats is not None else 0,
        isFavorited=_is_favorited(db, current_user, block.id),
        createdAt=block.created_at,
        updatedAt=block.updated_at,
    )


def _to_detail(
    db: Session,
    block: CustomBlock,
    current_user: User | None,
) -> SharedBlockDetailResponse:
    item = _to_item(db, block, current_user)
    return SharedBlockDetailResponse(
        **item.model_dump(by_alias=True),
        template=block.template,
    )


def list_shared_blocks(
    db: Session,
    current_user: User | None,
    *,
    keyword: str = "",
    category: str = "",
    tag: str = "",
    sort: str = "latest",
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[SharedBlockItemResponse], int]:
    statement = _approved_statement()
    should_commit = False

    keyword = keyword.strip()
    if keyword:
        db.add(
            RecommendationEvent(
                user_id=current_user.id if current_user is not None else None,
                event_type="search",
                keyword=keyword,
            )
        )
        should_commit = True

    category = category.strip()
    if category:
        statement = statement.where(CustomBlock.category == category)

    tag = tag.strip()
    sort = sort.strip()
    if sort == "popular":
        popularity_score = (
            func.coalesce(SharedBlockStats.favorite_count, 0) * 2
            + func.coalesce(SharedBlockStats.import_count, 0) * 3
            + func.coalesce(SharedBlockStats.view_count, 0)
        )
        statement = statement.outerjoin(
            SharedBlockStats,
            SharedBlockStats.custom_block_id == CustomBlock.id,
        ).order_by(popularity_score.desc(), CustomBlock.updated_at.desc(), CustomBlock.id.desc())
    elif sort == "beginner":
        statement = statement.order_by(CustomBlock.updated_at.desc(), CustomBlock.id.desc())
    else:
        statement = statement.order_by(CustomBlock.updated_at.desc(), CustomBlock.id.desc())

    if keyword or tag or sort == "beginner":
        blocks = db.scalars(statement).all()
        if keyword:
            blocks = [block for block in blocks if _matches_keyword(block, keyword)]
        if tag:
            blocks = [block for block in blocks if _has_tag(block, tag)]
        if sort == "beginner":
            blocks.sort(
                key=lambda block: (_is_beginner_block(block), block.updated_at, block.id),
                reverse=True,
            )
        total = len(blocks)
        blocks = blocks[(page - 1) * page_size : page * page_size]
    else:
        total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        blocks = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()

    items = [_to_item(db, block, current_user) for block in blocks]
    if should_commit:
        db.commit()
    return items, total


def get_shared_block_detail(
    db: Session,
    current_user: User | None,
    block_id: int,
) -> SharedBlockDetailResponse | None:
    block = _ensure_approved_block_stats(db, block_id)
    if block is None:
        return None

    _increment_stat(db, block.id, "view_count")
    db.add(
        RecommendationEvent(
            user_id=current_user.id if current_user is not None else None,
            event_type="view",
            custom_block_id=block.id,
        )
    )
    db.commit()
    block = _approved_block(db, block.id)
    if block is None:
        return None
    return _to_detail(db, block, current_user)


def favorite_shared_block(
    db: Session,
    current_user: User,
    block_id: int,
) -> SharedBlockDetailResponse | None:
    block = _ensure_approved_block_stats(db, block_id)
    if block is None:
        return None

    favorite = db.scalar(
        select(SharedBlockFavorite).where(
            SharedBlockFavorite.user_id == current_user.id,
            SharedBlockFavorite.custom_block_id == block.id,
        )
    )
    if favorite is None:
        db.add(
            SharedBlockFavorite(
                user_id=current_user.id,
                custom_block_id=block.id,
            )
        )
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            block = _approved_block(db, block_id)
            if block is None:
                return None
            return _to_detail(db, block, current_user)

        _increment_stat(db, block.id, "favorite_count")
        db.add(
            RecommendationEvent(
                user_id=current_user.id,
                event_type="favorite",
                custom_block_id=block.id,
            )
        )
        db.commit()
        block = _approved_block(db, block.id)
        if block is None:
            return None

    return _to_detail(db, block, current_user)


def unfavorite_shared_block(db: Session, current_user: User, block_id: int) -> bool:
    block = _approved_block(db, block_id)
    if block is None:
        return False

    favorite = db.scalar(
        select(SharedBlockFavorite).where(
            SharedBlockFavorite.user_id == current_user.id,
            SharedBlockFavorite.custom_block_id == block.id,
        )
    )
    if favorite is not None:
        block = _ensure_approved_block_stats(db, block_id)
        if block is None:
            return False
        db.delete(favorite)
        _decrement_stat_safely(db, block.id, "favorite_count")

    db.add(
        RecommendationEvent(
            user_id=current_user.id,
            event_type="unfavorite",
            custom_block_id=block.id,
        )
    )
    db.commit()
    return True


def _import_name(db: Session, current_user: User, base_name: str) -> str:
    candidate = base_name
    index = 0
    while _import_name_exists(db, current_user, candidate):
        index += 1
        suffix = "（导入）" if index == 1 else f"（导入 {index}）"
        candidate = f"{base_name}{suffix}"
    return candidate


def _import_name_exists(db: Session, current_user: User, name: str) -> bool:
    count = db.scalar(
        select(func.count()).where(
            CustomBlock.owner_id == current_user.id,
            func.lower(CustomBlock.name) == name.lower(),
        )
    )
    return (count or 0) > 0


def import_shared_block(
    db: Session,
    current_user: User,
    block_id: int,
) -> CustomBlockResponse | None:
    for _ in range(MAX_IMPORT_RETRIES):
        source = _ensure_approved_block_stats(db, block_id)
        if source is None:
            return None

        imported = CustomBlock(
            owner_id=current_user.id,
            name=_import_name(db, current_user, source.name),
            description=source.description,
            category=source.category,
            tags=list(source.tags or []),
            template=deepcopy(source.template),
            review_status="private",
        )
        db.add(imported)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue

        _increment_stat(db, source.id, "import_count")
        db.add(
            SharedBlockImport(
                user_id=current_user.id,
                source_custom_block_id=source.id,
                imported_custom_block_id=imported.id,
            )
        )
        db.add(
            RecommendationEvent(
                user_id=current_user.id,
                event_type="import",
                custom_block_id=source.id,
            )
        )
        db.commit()
        db.refresh(imported)
        return custom_block_to_response(imported)

    raise ValueError("Unable to import shared block with a unique name")


def list_pending_reviews(
    db: Session,
    keyword: str = "",
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[SharedBlockItemResponse], int]:
    statement = (
        select(CustomBlock)
        .where(CustomBlock.review_status == "pending_review")
        .options(selectinload(CustomBlock.owner), selectinload(CustomBlock.shared_stats))
        .order_by(CustomBlock.updated_at.desc(), CustomBlock.id.desc())
    )

    keyword = keyword.strip()
    if keyword:
        blocks = db.scalars(statement).all()
        blocks = [block for block in blocks if _matches_keyword(block, keyword)]
        total = len(blocks)
        blocks = blocks[(page - 1) * page_size : page * page_size]
    else:
        total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        blocks = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()

    return [_to_item(db, block, None) for block in blocks], total


def review_custom_block(
    db: Session,
    block_id: int,
    status: str,
) -> SharedBlockDetailResponse | None:
    result = db.execute(
        update(CustomBlock)
        .where(CustomBlock.id == block_id, CustomBlock.review_status == "pending_review")
        .values(review_status=status, updated_at=datetime.utcnow())
    )
    if result.rowcount != 1:
        return None

    block = db.scalar(
        select(CustomBlock)
        .where(CustomBlock.id == block_id)
        .options(selectinload(CustomBlock.owner), selectinload(CustomBlock.shared_stats))
        .execution_options(populate_existing=True)
    )
    if block is None:
        return None

    if status == "approved":
        _stats_for(db, block)

    db.commit()
    db.refresh(block)
    return _to_detail(db, block, None)
