from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.custom_block import CustomBlock
from app.models.shared_block import (
    RecommendationEvent,
    SharedBlockFavorite,
    SharedBlockStats,
)
from app.models.user import User
from app.schemas.shared_block import SharedBlockDetailResponse, SharedBlockItemResponse

BEGINNER_CATEGORIES = ["动作", "风控"]
BEGINNER_TAGS = ["新手", "基础", "止盈", "止损"]


def _approved_statement() -> Select[tuple[CustomBlock]]:
    return (
        select(CustomBlock)
        .where(CustomBlock.review_status == "approved")
        .options(selectinload(CustomBlock.owner), selectinload(CustomBlock.shared_stats))
    )


def _stats_for(db: Session, block: CustomBlock) -> SharedBlockStats:
    if block.shared_stats is not None:
        return block.shared_stats

    stats = SharedBlockStats(custom_block_id=block.id)
    db.add(stats)
    db.flush()
    return stats


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
    block = db.scalar(_approved_statement().where(CustomBlock.id == block_id))
    if block is None:
        return None

    stats = _stats_for(db, block)
    stats.view_count += 1
    db.add(
        RecommendationEvent(
            user_id=current_user.id if current_user is not None else None,
            event_type="view",
            custom_block_id=block.id,
        )
    )
    db.commit()
    db.refresh(block)
    item = _to_item(db, block, current_user)
    return SharedBlockDetailResponse(
        **item.model_dump(by_alias=True),
        template=block.template,
    )
