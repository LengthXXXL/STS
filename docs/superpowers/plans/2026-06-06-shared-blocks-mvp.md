# Shared Blocks MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first complete public custom-block sharing loop: publish from personal space, review as admin, browse/search in the shared-blocks page, favorite, and import into the current user's private block library.

**Architecture:** Keep `custom_blocks` as the source table for block templates and use its `review_status` as the publishing state. Add small supporting tables for public stats, favorites, import records, and recommendation events. Expose new REST APIs under `/api/shared-blocks` and `/api/admin/custom-block-reviews`, then wire Vue views to those APIs with focused component tests.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pydantic, Pytest, Vue 3 Composition API, Pinia, Vitest, Vite, MySQL 8.0-compatible models.

---

## File Structure

Backend files:

- Modify `backend/app/models/custom_block.py`: add relationships to stats, favorites, imports, and events.
- Create `backend/app/models/shared_block.py`: define `SharedBlockStats`, `SharedBlockFavorite`, `SharedBlockImport`, and `RecommendationEvent`.
- Modify `backend/app/models/__init__.py`: import the new models so `Base.metadata.create_all` sees them.
- Modify `backend/app/schemas/custom_block.py`: keep current response shape; no breaking change.
- Create `backend/app/schemas/shared_block.py`: shared block list/detail/favorite/import/admin response schemas.
- Modify `backend/app/services/custom_block_service.py`: add `publish_custom_block` and reuse import-name conflict helpers.
- Create `backend/app/services/shared_block_service.py`: public list/detail, stats, favorite/unfavorite, import, admin review logic.
- Modify `backend/app/api/custom_blocks.py`: add `POST /custom-blocks/{id}/publish`.
- Create `backend/app/api/shared_blocks.py`: add public shared-block endpoints.
- Create `backend/app/api/admin_custom_block_reviews.py`: add admin review endpoints.
- Modify `backend/app/main.py`: include shared-block and admin review routers.
- Test `backend/tests/test_custom_blocks.py`: publish state-transition tests.
- Create `backend/tests/test_shared_blocks.py`: public list/detail/favorite/import/admin review tests.

Frontend files:

- Modify `frontend/src/views/PersonalSpaceView.vue`: add publish/re-publish/approved actions and status handling.
- Modify `frontend/tests/personal-space-view.test.ts`: cover publish button state and API calls.
- Replace `frontend/src/views/SharedBlocksView.vue`: build the actual sharing page with search/filter/sort, list, detail, favorite, import, and admin review tab.
- Create `frontend/tests/shared-blocks-view.test.ts`: cover sharing page behaviors.
- Modify `frontend/src/styles/base.css`: add shared-block page and publish button styling, consistent with the existing black/purple theme.

No Alembic migration files are added in this project stage because the current backend uses `Base.metadata.create_all(bind=engine)` in development. New tables will be created automatically for fresh dev databases. Existing dev databases need only the new supporting tables, which `create_all` can create without altering existing tables.

---

### Task 1: Custom Block Publishing State

**Files:**
- Modify: `backend/app/services/custom_block_service.py`
- Modify: `backend/app/api/custom_blocks.py`
- Test: `backend/tests/test_custom_blocks.py`

- [ ] **Step 1: Write failing backend tests for publishing**

Add these tests to `backend/tests/test_custom_blocks.py` after `test_custom_block_crud_flow_for_current_user`:

```python
def test_custom_block_owner_can_publish_private_block(client):
    token = register_and_token(client, "alice", "alice@example.com")
    create_response = client.post(
        "/api/custom-blocks",
        json=custom_block_payload("发布模板"),
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201

    publish_response = client.post(
        f"/api/custom-blocks/{create_response.json()['id']}/publish",
        headers=auth_headers(token),
    )

    assert publish_response.status_code == 200
    assert publish_response.json()["reviewStatus"] == "pending_review"


def test_custom_block_publish_rejects_non_owner(client):
    alice_token = register_and_token(client, "alice", "alice@example.com")
    bob_token = register_and_token(client, "bob", "bob@example.com")
    create_response = client.post(
        "/api/custom-blocks",
        json=custom_block_payload("Alice 发布模板"),
        headers=auth_headers(alice_token),
    )

    publish_response = client.post(
        f"/api/custom-blocks/{create_response.json()['id']}/publish",
        headers=auth_headers(bob_token),
    )

    assert publish_response.status_code == 404


def test_custom_block_publish_rejects_pending_or_approved(client):
    token = register_and_token(client, "alice", "alice@example.com")
    create_response = client.post(
        "/api/custom-blocks",
        json=custom_block_payload("只允许发布一次"),
        headers=auth_headers(token),
    )
    block_id = create_response.json()["id"]
    first_publish = client.post(f"/api/custom-blocks/{block_id}/publish", headers=auth_headers(token))
    second_publish = client.post(f"/api/custom-blocks/{block_id}/publish", headers=auth_headers(token))

    assert first_publish.status_code == 200
    assert second_publish.status_code == 409
    assert second_publish.json()["detail"] == "Custom block is already submitted or public"
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
backend/.venv/bin/pytest backend/tests/test_custom_blocks.py -q
```

Expected: failures for `POST /api/custom-blocks/{id}/publish` returning `405 Method Not Allowed` or `404 Not Found`, because the route does not exist.

- [ ] **Step 3: Implement publishing service logic**

Add to `backend/app/services/custom_block_service.py`:

```python
PUBLISHABLE_REVIEW_STATUSES = {"private", "rejected"}


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
```

Update the service import section only if needed. `Session`, `User`, and `CustomBlockResponse` already exist in this file.

- [ ] **Step 4: Add publish endpoint**

Modify `backend/app/api/custom_blocks.py` imports:

```python
from app.services.custom_block_service import (
    create_custom_block,
    delete_custom_block,
    get_custom_block,
    list_custom_blocks,
    publish_custom_block,
    update_custom_block,
)
```

Add this route before `@router.get("/{block_id}")`:

```python
@router.post("/{block_id}/publish", response_model=CustomBlockResponse)
def publish(
    block_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomBlockResponse:
    try:
        block = publish_custom_block(db, current_user, block_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if block is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom block not found")
    return block
```

- [ ] **Step 5: Verify GREEN**

Run:

```bash
backend/.venv/bin/pytest backend/tests/test_custom_blocks.py -q
```

Expected: all tests in `test_custom_blocks.py` pass.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add backend/app/api/custom_blocks.py backend/app/services/custom_block_service.py backend/tests/test_custom_blocks.py
git commit -m "feat: submit custom blocks for review"
```

---

### Task 2: Shared Block Models, Schemas, Public List, and Detail

**Files:**
- Create: `backend/app/models/shared_block.py`
- Modify: `backend/app/models/custom_block.py`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/shared_block.py`
- Create: `backend/app/services/shared_block_service.py`
- Create: `backend/app/api/shared_blocks.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_shared_blocks.py`

- [ ] **Step 1: Write failing public shared-block tests**

Create `backend/tests/test_shared_blocks.py`:

```python
from app.models.custom_block import CustomBlock
from tests.test_custom_blocks import custom_block_payload
from tests.test_strategies import auth_headers, register_and_token


def create_custom_block(client, token: str, name: str = "公开模板") -> dict:
    response = client.post(
        "/api/custom-blocks",
        json=custom_block_payload(name),
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()


def approve_block_directly(db_session, block_id: int) -> None:
    block = db_session.get(CustomBlock, block_id)
    assert block is not None
    block.review_status = "approved"
    db_session.commit()


def test_shared_blocks_list_only_returns_approved_blocks(client, db_session):
    token = register_and_token(client, "alice", "alice@example.com")
    private_block = create_custom_block(client, token, "私有模板")
    approved_block = create_custom_block(client, token, "公开止盈模板")
    approve_block_directly(db_session, approved_block["id"])

    response = client.get("/api/shared-blocks")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == approved_block["id"]
    assert payload["items"][0]["name"] == "公开止盈模板"
    assert payload["items"][0]["authorName"] == "alice"
    assert payload["items"][0]["nodeCount"] == 2
    assert payload["items"][0]["connectionCount"] == 1
    assert private_block["name"] not in [item["name"] for item in payload["items"]]


def test_shared_blocks_support_keyword_category_tag_and_latest_sort(client, db_session):
    token = register_and_token(client, "alice", "alice@example.com")
    risk_block = create_custom_block(client, token, "公开止盈模板")
    action_payload = custom_block_payload("公开买入模板")
    action_payload["category"] = "动作"
    action_payload["tags"] = ["买入", "基础"]
    action_response = client.post("/api/custom-blocks", json=action_payload, headers=auth_headers(token))
    assert action_response.status_code == 201
    approve_block_directly(db_session, risk_block["id"])
    approve_block_directly(db_session, action_response.json()["id"])

    response = client.get("/api/shared-blocks?keyword=买入&category=动作&tag=基础&sort=latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["name"] == "公开买入模板"


def test_shared_block_detail_records_view_count(client, db_session):
    token = register_and_token(client, "alice", "alice@example.com")
    block = create_custom_block(client, token, "详情模板")
    approve_block_directly(db_session, block["id"])

    first_response = client.get(f"/api/shared-blocks/{block['id']}")
    second_response = client.get(f"/api/shared-blocks/{block['id']}")

    assert first_response.status_code == 200
    assert first_response.json()["viewCount"] == 1
    assert second_response.status_code == 200
    assert second_response.json()["viewCount"] == 2
    assert second_response.json()["template"]["edges"][0]["from"] == "buy-1"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
backend/.venv/bin/pytest backend/tests/test_shared_blocks.py -q
```

Expected: import or route failures because shared-block models, schemas, and routers do not exist.

- [ ] **Step 3: Add shared block support models**

Create `backend/app/models/shared_block.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SharedBlockStats(Base):
    __tablename__ = "shared_block_stats"
    __table_args__ = (UniqueConstraint("custom_block_id", name="uq_shared_block_stats_block"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    custom_block_id: Mapped[int] = mapped_column(ForeignKey("custom_blocks.id"), nullable=False, index=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    favorite_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    import_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    custom_block = relationship("CustomBlock", back_populates="shared_stats")


class SharedBlockFavorite(Base):
    __tablename__ = "shared_block_favorites"
    __table_args__ = (UniqueConstraint("user_id", "custom_block_id", name="uq_shared_block_favorite_user_block"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    custom_block_id: Mapped[int] = mapped_column(ForeignKey("custom_blocks.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="shared_block_favorites")
    custom_block = relationship("CustomBlock", back_populates="shared_favorites")


class SharedBlockImport(Base):
    __tablename__ = "shared_block_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    source_custom_block_id: Mapped[int] = mapped_column(ForeignKey("custom_blocks.id"), nullable=False, index=True)
    imported_custom_block_id: Mapped[int] = mapped_column(ForeignKey("custom_blocks.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="shared_block_imports")
    source_custom_block = relationship("CustomBlock", foreign_keys=[source_custom_block_id])
    imported_custom_block = relationship("CustomBlock", foreign_keys=[imported_custom_block_id])


class RecommendationEvent(Base):
    __tablename__ = "recommendation_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    custom_block_id: Mapped[int | None] = mapped_column(ForeignKey("custom_blocks.id"), nullable=True, index=True)
    keyword: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="recommendation_events")
    custom_block = relationship("CustomBlock", back_populates="recommendation_events")
```

Modify `backend/app/models/custom_block.py`:

```python
    shared_stats = relationship(
        "SharedBlockStats",
        back_populates="custom_block",
        cascade="all, delete-orphan",
        uselist=False,
    )
    shared_favorites = relationship(
        "SharedBlockFavorite",
        back_populates="custom_block",
        cascade="all, delete-orphan",
    )
    recommendation_events = relationship(
        "RecommendationEvent",
        back_populates="custom_block",
        cascade="all, delete-orphan",
    )
```

Modify `backend/app/models/user.py` inside `TYPE_CHECKING` imports:

```python
    from app.models.shared_block import RecommendationEvent, SharedBlockFavorite, SharedBlockImport
```

Add relationships to `User`:

```python
    shared_block_favorites: Mapped[list["SharedBlockFavorite"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    shared_block_imports: Mapped[list["SharedBlockImport"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    recommendation_events: Mapped[list["RecommendationEvent"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
```

Modify `backend/app/models/__init__.py`:

```python
from app.models.shared_block import (
    RecommendationEvent,
    SharedBlockFavorite,
    SharedBlockImport,
    SharedBlockStats,
)
```

and add those four names to `__all__`.

- [ ] **Step 4: Add shared block schemas**

Create `backend/app/schemas/shared_block.py`:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.backtest import StrategyDraft


class SharedBlockItemResponse(BaseModel):
    id: int
    owner_id: int = Field(alias="ownerId")
    author_name: str = Field(alias="authorName")
    name: str
    description: str | None
    category: str
    tags: list[str]
    review_status: str = Field(alias="reviewStatus")
    node_count: int = Field(alias="nodeCount")
    connection_count: int = Field(alias="connectionCount")
    view_count: int = Field(alias="viewCount")
    favorite_count: int = Field(alias="favoriteCount")
    import_count: int = Field(alias="importCount")
    is_favorited: bool = Field(alias="isFavorited")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class SharedBlockDetailResponse(SharedBlockItemResponse):
    template: StrategyDraft


class SharedBlockListResponse(BaseModel):
    items: list[SharedBlockItemResponse]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")

    model_config = ConfigDict(populate_by_name=True)
```

- [ ] **Step 5: Add public shared block service**

Create `backend/app/services/shared_block_service.py` with these public functions:

```python
from sqlalchemy import Select, String, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.custom_block import CustomBlock
from app.models.shared_block import RecommendationEvent, SharedBlockFavorite, SharedBlockStats
from app.models.user import User
from app.schemas.shared_block import SharedBlockDetailResponse, SharedBlockItemResponse


def _approved_statement() -> Select[tuple[CustomBlock]]:
    return (
        select(CustomBlock)
        .options(selectinload(CustomBlock.owner), selectinload(CustomBlock.shared_stats))
        .where(CustomBlock.review_status == "approved")
    )


def _stats_for(db: Session, block: CustomBlock) -> SharedBlockStats:
    if block.shared_stats is not None:
        return block.shared_stats
    stats = SharedBlockStats(custom_block_id=block.id)
    db.add(stats)
    db.flush()
    block.shared_stats = stats
    return stats


def _is_favorited(db: Session, user: User | None, block_id: int) -> bool:
    if user is None:
        return False
    favorite = db.scalar(
        select(SharedBlockFavorite).where(
            SharedBlockFavorite.user_id == user.id,
            SharedBlockFavorite.custom_block_id == block_id,
        )
    )
    return favorite is not None


def _to_item(db: Session, block: CustomBlock, current_user: User | None) -> SharedBlockItemResponse:
    stats = _stats_for(db, block)
    return SharedBlockItemResponse(
        id=block.id,
        ownerId=block.owner_id,
        authorName=block.owner.username,
        name=block.name,
        description=block.description,
        category=block.category,
        tags=block.tags,
        reviewStatus=block.review_status,
        nodeCount=len(block.template.get("nodes", [])),
        connectionCount=len(block.template.get("edges", [])),
        viewCount=stats.view_count,
        favoriteCount=stats.favorite_count,
        importCount=stats.import_count,
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
    keyword = keyword.strip()
    category = category.strip()
    tag = tag.strip()

    if keyword:
        statement = statement.where(
            or_(
                CustomBlock.name.like(f"%{keyword}%"),
                CustomBlock.description.like(f"%{keyword}%"),
                CustomBlock.category.like(f"%{keyword}%"),
            )
        )
        db.add(RecommendationEvent(user_id=current_user.id if current_user else None, event_type="search", keyword=keyword))

    if category:
        statement = statement.where(CustomBlock.category == category)
    if tag:
        statement = statement.where(CustomBlock.tags.cast(String).like(f'%"{tag}"%'))

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0

    if sort == "popular":
        statement = statement.outerjoin(SharedBlockStats).order_by(
            (
                func.coalesce(SharedBlockStats.favorite_count, 0) * 2
                + func.coalesce(SharedBlockStats.import_count, 0) * 3
                + func.coalesce(SharedBlockStats.view_count, 0)
            ).desc(),
            CustomBlock.updated_at.desc(),
        )
    elif sort == "beginner":
        statement = statement.outerjoin(SharedBlockStats).order_by(
            (
                (CustomBlock.category.in_(["动作", "风控"])).desc()
            ),
            CustomBlock.updated_at.desc(),
        )
    else:
        statement = statement.order_by(CustomBlock.updated_at.desc(), CustomBlock.id.desc())

    blocks = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    items = [_to_item(db, block, current_user) for block in blocks]
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
            user_id=current_user.id if current_user else None,
            event_type="view",
            custom_block_id=block.id,
        )
    )
    db.commit()
    db.refresh(block)
    item = _to_item(db, block, current_user)
    return SharedBlockDetailResponse(**item.model_dump(by_alias=True), template=block.template)
```

The tag predicate casts JSON to text and searches for the quoted tag. That keeps the implementation compatible with the current SQLite test database and MySQL 8.0's JSON text representation for this MVP.

- [ ] **Step 6: Add public shared block router**

Create `backend/app/api/shared_blocks.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_optional_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.shared_block import SharedBlockDetailResponse, SharedBlockListResponse
from app.services.shared_block_service import get_shared_block_detail, list_shared_blocks

router = APIRouter(prefix="/shared-blocks", tags=["shared-blocks"])


@router.get("", response_model=SharedBlockListResponse)
def list_public_blocks(
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared block not found")
    return block
```

Modify `backend/app/main.py`:

```python
from app.api import auth, backtests, custom_blocks, health, shared_blocks, simulation_accounts, strategies
```

and include:

```python
app.include_router(shared_blocks.router, prefix="/api")
```

- [ ] **Step 7: Verify public list/detail GREEN**

Run:

```bash
backend/.venv/bin/pytest backend/tests/test_shared_blocks.py -q
```

Expected: the three tests in this task pass.

- [ ] **Step 8: Commit Task 2**

Run:

```bash
git add backend/app/models backend/app/schemas/shared_block.py backend/app/services/shared_block_service.py backend/app/api/shared_blocks.py backend/app/main.py backend/tests/test_shared_blocks.py
git commit -m "feat: expose public shared blocks"
```

---

### Task 3: Favorites, Imports, and Admin Review

**Files:**
- Modify: `backend/app/services/shared_block_service.py`
- Modify: `backend/app/api/shared_blocks.py`
- Create: `backend/app/api/admin_custom_block_reviews.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_shared_blocks.py`

- [ ] **Step 1: Add failing tests for favorite, import, and admin review**

Append to `backend/tests/test_shared_blocks.py`:

```python
from sqlalchemy import select
from app.models.user import Role, User


def register_user_token(client, username: str, email: str) -> str:
    return register_and_token(client, username, email)


def grant_admin_role(db_session, email: str) -> None:
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    admin_role = db_session.scalar(select(Role).where(Role.name == "admin"))
    if admin_role is None:
        admin_role = Role(name="admin")
        db_session.add(admin_role)
        db_session.flush()
    user.roles.append(admin_role)
    db_session.commit()
```

Then add tests:

```python
def test_favorite_and_unfavorite_shared_block(client, db_session):
    owner_token = register_user_token(client, "alice", "alice@example.com")
    viewer_token = register_user_token(client, "bob", "bob@example.com")
    block = create_custom_block(client, owner_token, "收藏模板")
    approve_block_directly(db_session, block["id"])

    favorite_response = client.post(
        f"/api/shared-blocks/{block['id']}/favorite",
        headers=auth_headers(viewer_token),
    )
    duplicate_response = client.post(
        f"/api/shared-blocks/{block['id']}/favorite",
        headers=auth_headers(viewer_token),
    )
    list_response = client.get("/api/shared-blocks", headers=auth_headers(viewer_token))
    unfavorite_response = client.delete(
        f"/api/shared-blocks/{block['id']}/favorite",
        headers=auth_headers(viewer_token),
    )

    assert favorite_response.status_code == 200
    assert duplicate_response.status_code == 200
    assert list_response.json()["items"][0]["favoriteCount"] == 1
    assert list_response.json()["items"][0]["isFavorited"] is True
    assert unfavorite_response.status_code == 204


def test_import_shared_block_auto_renames_duplicate(client, db_session):
    owner_token = register_user_token(client, "alice", "alice@example.com")
    importer_token = register_user_token(client, "bob", "bob@example.com")
    source = create_custom_block(client, owner_token, "导入模板")
    approve_block_directly(db_session, source["id"])
    existing = create_custom_block(client, importer_token, "导入模板")

    import_response = client.post(
        f"/api/shared-blocks/{source['id']}/import",
        headers=auth_headers(importer_token),
    )

    assert existing["name"] == "导入模板"
    assert import_response.status_code == 201
    payload = import_response.json()
    assert payload["name"] == "导入模板（导入）"
    assert payload["reviewStatus"] == "private"
    assert payload["template"]["nodes"][0]["type"] == "buy"


def test_admin_can_approve_and_reject_pending_blocks(client, db_session):
    owner_token = register_user_token(client, "alice", "alice@example.com")
    admin_token = register_user_token(client, "admin", "admin@example.com")
    grant_admin_role(db_session, "admin@example.com")
    pending_block = create_custom_block(client, owner_token, "审核模板")
    publish_response = client.post(
        f"/api/custom-blocks/{pending_block['id']}/publish",
        headers=auth_headers(owner_token),
    )
    assert publish_response.status_code == 200

    review_list = client.get(
        "/api/admin/custom-block-reviews",
        headers=auth_headers(admin_token),
    )
    approve_response = client.post(
        f"/api/admin/custom-block-reviews/{pending_block['id']}/approve",
        headers=auth_headers(admin_token),
    )
    public_list = client.get("/api/shared-blocks")

    assert review_list.status_code == 200
    assert review_list.json()["items"][0]["id"] == pending_block["id"]
    assert approve_response.status_code == 200
    assert approve_response.json()["reviewStatus"] == "approved"
    assert public_list.json()["items"][0]["id"] == pending_block["id"]


def test_non_admin_cannot_review_blocks(client):
    token = register_user_token(client, "alice", "alice@example.com")

    response = client.get("/api/admin/custom-block-reviews", headers=auth_headers(token))

    assert response.status_code == 403
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
backend/.venv/bin/pytest backend/tests/test_shared_blocks.py -q
```

Expected: failures for missing favorite/import/admin endpoints.

- [ ] **Step 3: Implement service functions**

Add to `backend/app/services/shared_block_service.py`:

```python
from sqlalchemy.exc import IntegrityError

from app.models.shared_block import SharedBlockImport
from app.schemas.custom_block import CustomBlockResponse
from app.services.custom_block_service import custom_block_to_response
```

Add functions:

```python
def favorite_shared_block(db: Session, current_user: User, block_id: int) -> SharedBlockDetailResponse | None:
    block = db.scalar(_approved_statement().where(CustomBlock.id == block_id))
    if block is None:
        return None
    stats = _stats_for(db, block)
    existing = db.scalar(
        select(SharedBlockFavorite).where(
            SharedBlockFavorite.user_id == current_user.id,
            SharedBlockFavorite.custom_block_id == block.id,
        )
    )
    if existing is None:
        db.add(SharedBlockFavorite(user_id=current_user.id, custom_block_id=block.id))
        stats.favorite_count += 1
        db.add(RecommendationEvent(user_id=current_user.id, event_type="favorite", custom_block_id=block.id))
    db.commit()
    db.refresh(block)
    item = _to_item(db, block, current_user)
    return SharedBlockDetailResponse(**item.model_dump(by_alias=True), template=block.template)


def unfavorite_shared_block(db: Session, current_user: User, block_id: int) -> bool:
    block = db.scalar(_approved_statement().where(CustomBlock.id == block_id))
    if block is None:
        return False
    favorite = db.scalar(
        select(SharedBlockFavorite).where(
            SharedBlockFavorite.user_id == current_user.id,
            SharedBlockFavorite.custom_block_id == block.id,
        )
    )
    if favorite is not None:
        db.delete(favorite)
        stats = _stats_for(db, block)
        stats.favorite_count = max(0, stats.favorite_count - 1)
        db.add(RecommendationEvent(user_id=current_user.id, event_type="unfavorite", custom_block_id=block.id))
        db.commit()
    return True


def _import_name(db: Session, current_user: User, base_name: str) -> str:
    candidates = [base_name, f"{base_name}（导入）"]
    candidates.extend(f"{base_name}（导入 {index}）" for index in range(2, 50))
    for candidate in candidates:
        exists = db.scalar(
            select(func.count()).select_from(
                select(CustomBlock)
                .where(CustomBlock.owner_id == current_user.id)
                .where(func.lower(CustomBlock.name) == candidate.lower())
                .subquery()
            )
        )
        if not exists:
            return candidate
    return f"{base_name}（导入 {current_user.id}）"


def import_shared_block(db: Session, current_user: User, block_id: int) -> CustomBlockResponse | None:
    source = db.scalar(_approved_statement().where(CustomBlock.id == block_id))
    if source is None:
        return None
    imported = CustomBlock(
        owner_id=current_user.id,
        name=_import_name(db, current_user, source.name),
        description=source.description,
        category=source.category,
        tags=source.tags,
        template=source.template,
        review_status="private",
    )
    db.add(imported)
    db.flush()
    stats = _stats_for(db, source)
    stats.import_count += 1
    db.add(
        SharedBlockImport(
            user_id=current_user.id,
            source_custom_block_id=source.id,
            imported_custom_block_id=imported.id,
        )
    )
    db.add(RecommendationEvent(user_id=current_user.id, event_type="import", custom_block_id=source.id))
    db.commit()
    db.refresh(imported)
    return custom_block_to_response(imported)


def list_pending_reviews(
    db: Session,
    *,
    keyword: str = "",
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[SharedBlockItemResponse], int]:
    statement = (
        select(CustomBlock)
        .options(selectinload(CustomBlock.owner), selectinload(CustomBlock.shared_stats))
        .where(CustomBlock.review_status == "pending_review")
    )
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
    return [_to_item(db, block, None) for block in blocks], total


def review_custom_block(db: Session, block_id: int, status: str) -> SharedBlockDetailResponse | None:
    block = db.scalar(
        select(CustomBlock)
        .options(selectinload(CustomBlock.owner), selectinload(CustomBlock.shared_stats))
        .where(CustomBlock.id == block_id)
        .where(CustomBlock.review_status == "pending_review")
    )
    if block is None:
        return None
    block.review_status = status
    if status == "approved":
        _stats_for(db, block)
    db.commit()
    db.refresh(block)
    item = _to_item(db, block, None)
    return SharedBlockDetailResponse(**item.model_dump(by_alias=True), template=block.template)
```

- [ ] **Step 4: Add favorite/import routes**

Modify `backend/app/api/shared_blocks.py` imports:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from app.api.dependencies import get_current_user, get_optional_current_user
from app.schemas.custom_block import CustomBlockResponse
from app.services.shared_block_service import (
    favorite_shared_block,
    get_shared_block_detail,
    import_shared_block,
    list_shared_blocks,
    unfavorite_shared_block,
)
```

Add routes:

```python
@router.post("/{block_id}/favorite", response_model=SharedBlockDetailResponse)
def favorite(
    block_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SharedBlockDetailResponse:
    block = favorite_shared_block(db, current_user, block_id)
    if block is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared block not found")
    return block


@router.delete("/{block_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def unfavorite(
    block_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    removed = unfavorite_shared_block(db, current_user, block_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared block not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{block_id}/import", response_model=CustomBlockResponse, status_code=status.HTTP_201_CREATED)
def import_block(
    block_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomBlockResponse:
    block = import_shared_block(db, current_user, block_id)
    if block is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared block not found")
    return block
```

- [ ] **Step 5: Add admin review router**

Create `backend/app/api/admin_custom_block_reviews.py`:

```python
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
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> SharedBlockListResponse:
    items, total = list_pending_reviews(db, keyword=keyword, page=page, page_size=page_size)
    return SharedBlockListResponse(items=items, total=total, page=page, pageSize=page_size)


@router.post("/{block_id}/approve", response_model=SharedBlockDetailResponse)
def approve(
    block_id: int,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> SharedBlockDetailResponse:
    block = review_custom_block(db, block_id, "approved")
    if block is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found")
    return block


@router.post("/{block_id}/reject", response_model=SharedBlockDetailResponse)
def reject(
    block_id: int,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> SharedBlockDetailResponse:
    block = review_custom_block(db, block_id, "rejected")
    if block is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found")
    return block
```

Modify `backend/app/main.py` imports and router inclusion:

```python
from app.api import admin_custom_block_reviews, auth, backtests, custom_blocks, health, shared_blocks, simulation_accounts, strategies
```

```python
app.include_router(admin_custom_block_reviews.router, prefix="/api")
```

- [ ] **Step 6: Verify Task 3 GREEN**

Run:

```bash
backend/.venv/bin/pytest backend/tests/test_shared_blocks.py backend/tests/test_custom_blocks.py -q
```

Expected: all shared-block and custom-block tests pass.

- [ ] **Step 7: Commit Task 3**

Run:

```bash
git add backend/app/api backend/app/services/shared_block_service.py backend/tests/test_shared_blocks.py backend/app/main.py
git commit -m "feat: review favorite and import shared blocks"
```

---

### Task 4: Personal Space Publish UI

**Files:**
- Modify: `frontend/src/views/PersonalSpaceView.vue`
- Modify: `frontend/tests/personal-space-view.test.ts`
- Modify: `frontend/src/styles/base.css`

- [ ] **Step 1: Write failing frontend tests**

Add tests to `frontend/tests/personal-space-view.test.ts` near existing custom-block tests:

```ts
it('publishes a private custom block for review from personal space', async () => {
  mockPersonalSpaceRequests()
  vi.mocked(apiClient.post).mockResolvedValueOnce({
    data: { ...savedCustomBlock, reviewStatus: 'pending_review' }
  })
  const wrapper = mount(PersonalSpaceView)

  await flushPromises()
  await wrapper.find('[data-space-tab="custom-blocks"]').trigger('click')
  await wrapper.find('.custom-block-publish-button').trigger('click')
  await flushPromises()

  expect(apiClient.post).toHaveBeenCalledWith('/custom-blocks/21/publish')
  expect(wrapper.text()).toContain('已提交审核')
})

it('shows custom block publish actions by review status', async () => {
  mockPersonalSpaceRequests({
    customBlocks: [
      { ...savedCustomBlock, id: 21, reviewStatus: 'private' },
      { ...savedCustomBlock, id: 22, name: '待审核模板', reviewStatus: 'pending_review' },
      { ...savedCustomBlock, id: 23, name: '公开模板', reviewStatus: 'approved' },
      { ...savedCustomBlock, id: 24, name: '拒绝模板', reviewStatus: 'rejected' }
    ]
  })
  const wrapper = mount(PersonalSpaceView)

  await flushPromises()
  await wrapper.find('[data-space-tab="custom-blocks"]').trigger('click')

  expect(wrapper.text()).toContain('发布')
  expect(wrapper.text()).toContain('待审核')
  expect(wrapper.text()).toContain('已公开')
  expect(wrapper.text()).toContain('重新发布')
})
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
npm test -- personal-space-view.test.ts
```

Expected: failures because `.custom-block-publish-button` and status actions do not exist.

- [ ] **Step 3: Implement publish helpers in PersonalSpaceView**

Add to `frontend/src/views/PersonalSpaceView.vue` script:

```ts
function customBlockPublishLabel(block: CustomBlock) {
  if (block.reviewStatus === 'pending_review') {
    return '待审核'
  }
  if (block.reviewStatus === 'approved') {
    return '已公开'
  }
  if (block.reviewStatus === 'rejected') {
    return '重新发布'
  }
  return '发布'
}

function canPublishCustomBlock(block: CustomBlock) {
  return block.reviewStatus === 'private' || block.reviewStatus === 'rejected'
}

async function publishCustomBlock(block: CustomBlock) {
  customBlockActionError.value = ''
  customBlockActionMessage.value = ''
  if (!canPublishCustomBlock(block)) {
    customBlockActionError.value = '该积木已提交审核或已公开'
    return
  }
  try {
    const response = await apiClient.post<CustomBlock>(`/custom-blocks/${block.id}/publish`)
    const index = customBlocks.value.findIndex((item) => item.id === block.id)
    if (index >= 0) {
      customBlocks.value[index] = response.data
    }
    customBlockActionMessage.value = `已提交审核：${response.data.name}`
  } catch {
    customBlockActionError.value = '发布失败，请稍后重试'
  }
}
```

Add button in the custom-block card action group before edit:

```vue
<button
  class="custom-block-publish-button"
  type="button"
  :disabled="!canPublishCustomBlock(block)"
  @click="publishCustomBlock(block)"
>
  {{ customBlockPublishLabel(block) }}
</button>
```

- [ ] **Step 4: Add CSS for publish button**

Add to `frontend/src/styles/base.css` near custom-block action styles:

```css
.custom-block-publish-button {
  border-color: rgba(94, 230, 200, 0.44) !important;
  background: rgba(21, 57, 53, 0.76) !important;
}

.custom-block-publish-button:disabled {
  cursor: default;
  opacity: 0.64;
}
```

- [ ] **Step 5: Verify GREEN**

Run:

```bash
npm test -- personal-space-view.test.ts
```

Expected: all personal-space tests pass.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add frontend/src/views/PersonalSpaceView.vue frontend/tests/personal-space-view.test.ts frontend/src/styles/base.css
git commit -m "feat: publish custom blocks from personal space"
```

---

### Task 5: Shared Blocks Page List, Detail, Favorite, and Import

**Files:**
- Replace: `frontend/src/views/SharedBlocksView.vue`
- Create: `frontend/tests/shared-blocks-view.test.ts`
- Modify: `frontend/src/styles/base.css`

- [ ] **Step 1: Write failing sharing page tests**

Create `frontend/tests/shared-blocks-view.test.ts`:

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { apiClient } from '../src/api/http'
import { useAuthStore } from '../src/stores/auth'
import SharedBlocksView from '../src/views/SharedBlocksView.vue'

vi.mock('../src/api/http', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn()
  }
}))

const sharedBlock = {
  id: 31,
  ownerId: 1,
  authorName: 'alice',
  name: '公开止盈模板',
  description: '按收益目标退出',
  category: '风控',
  tags: ['止盈', '基础'],
  reviewStatus: 'approved',
  nodeCount: 2,
  connectionCount: 1,
  viewCount: 8,
  favoriteCount: 3,
  importCount: 2,
  isFavorited: false,
  createdAt: '2026-06-06T11:00:00',
  updatedAt: '2026-06-06T11:30:00'
}

const sharedBlockDetail = {
  ...sharedBlock,
  template: {
    version: 1,
    nodes: [
      { id: 'buy-1', type: 'buy', label: '买入', x: 0, y: 0, params: { sizePercent: '20' } },
      { id: 'take-profit-1', type: 'take-profit', label: '止盈', x: 200, y: 0, params: { profitRate: '5' } }
    ],
    edges: [{ id: 'edge-1', from: 'buy-1', to: 'take-profit-1' }],
    viewport: { x: 0, y: 0, scale: 1 }
  }
}

function mockSharedBlocks() {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === '/shared-blocks') {
      return Promise.resolve({
        data: { items: [sharedBlock], total: 1, page: 1, pageSize: 10 }
      })
    }
    if (url === '/shared-blocks/31') {
      return Promise.resolve({ data: sharedBlockDetail })
    }
    return Promise.reject(new Error(`Unhandled GET ${url}`))
  })
}

describe('shared blocks view', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('loads shared blocks and filters with query params', async () => {
    mockSharedBlocks()
    const wrapper = mount(SharedBlocksView)
    await flushPromises()

    expect(apiClient.get).toHaveBeenCalledWith('/shared-blocks', {
      params: { keyword: '', category: '', tag: '', sort: 'latest', page: 1, pageSize: 10 }
    })
    expect(wrapper.text()).toContain('公开止盈模板')
    expect(wrapper.text()).toContain('alice')
    expect(wrapper.text()).toContain('收藏 3')
    expect(wrapper.text()).toContain('导入 2')

    await wrapper.find('.shared-block-search-input').setValue('止盈')
    await wrapper.find('.shared-block-category-input').setValue('风控')
    await wrapper.find('.shared-block-tag-input').setValue('基础')
    await wrapper.find('.shared-block-sort-select').setValue('popular')
    await wrapper.find('.shared-block-search-button').trigger('click')

    expect(apiClient.get).toHaveBeenCalledWith('/shared-blocks', {
      params: { keyword: '止盈', category: '风控', tag: '基础', sort: 'popular', page: 1, pageSize: 10 }
    })
  })

  it('opens details and imports a shared block when logged in', async () => {
    mockSharedBlocks()
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { id: 55, name: '公开止盈模板（导入）' }
    })
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 2, username: 'bob', email: 'bob@example.com', roles: ['user'] }
    })
    const wrapper = mount(SharedBlocksView)
    await flushPromises()

    await wrapper.find('.shared-block-detail-button').trigger('click')
    await flushPromises()
    expect(apiClient.get).toHaveBeenCalledWith('/shared-blocks/31')
    expect(wrapper.text()).toContain('买入 x1')
    expect(wrapper.text()).toContain('止盈 x1')

    await wrapper.find('.shared-block-import-button').trigger('click')
    await flushPromises()

    expect(apiClient.post).toHaveBeenCalledWith('/shared-blocks/31/import')
    expect(wrapper.text()).toContain('已导入到我的积木：公开止盈模板（导入）')
  })

  it('favorites and unfavorites a shared block when logged in', async () => {
    mockSharedBlocks()
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { ...sharedBlockDetail, isFavorited: true, favoriteCount: 4 }
    })
    vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: null })
    const authStore = useAuthStore()
    authStore.setSession({
      token: 'token-123',
      user: { id: 2, username: 'bob', email: 'bob@example.com', roles: ['user'] }
    })
    const wrapper = mount(SharedBlocksView)
    await flushPromises()

    await wrapper.find('.shared-block-favorite-button').trigger('click')
    await flushPromises()
    expect(apiClient.post).toHaveBeenCalledWith('/shared-blocks/31/favorite')
    expect(wrapper.text()).toContain('已收藏')

    await wrapper.find('.shared-block-favorite-button').trigger('click')
    await flushPromises()
    expect(apiClient.delete).toHaveBeenCalledWith('/shared-blocks/31/favorite')
  })

  it('asks visitors to log in before favorite or import', async () => {
    mockSharedBlocks()
    const authRequired = vi.fn()
    window.addEventListener('sts:auth-required', authRequired)
    const wrapper = mount(SharedBlocksView)
    await flushPromises()

    await wrapper.find('.shared-block-favorite-button').trigger('click')
    await wrapper.find('.shared-block-import-button').trigger('click')
    await nextTick()

    expect(authRequired).toHaveBeenCalledTimes(2)
    window.removeEventListener('sts:auth-required', authRequired)
  })
})
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
npm test -- shared-blocks-view.test.ts
```

Expected: failures because `SharedBlocksView.vue` is still only an introductory page and required classes do not exist.

- [ ] **Step 3: Implement SharedBlocksView**

Replace `frontend/src/views/SharedBlocksView.vue` with a Composition API component that includes:

```ts
interface SharedBlockItem {
  id: number
  ownerId: number
  authorName: string
  name: string
  description: string | null
  category: string
  tags: string[]
  reviewStatus: 'approved'
  nodeCount: number
  connectionCount: number
  viewCount: number
  favoriteCount: number
  importCount: number
  isFavorited: boolean
  createdAt: string
  updatedAt: string
}

interface SharedBlockDetail extends SharedBlockItem {
  template: {
    version: 1
    nodes: Array<{ id: string; type: string; label: string; x: number; y: number; params: Record<string, string> }>
    edges: Array<{ id: string; from: string; to: string }>
    viewport: { x: number; y: number; scale: number }
  }
}
```

Core functions:

```ts
async function loadSharedBlocks() {
  loading.value = true
  error.value = ''
  try {
    const response = await apiClient.get<SharedBlockListResponse>('/shared-blocks', {
      params: {
        keyword: keyword.value.trim(),
        category: category.value.trim(),
        tag: tag.value.trim(),
        sort: sort.value,
        page: page.value,
        pageSize
      }
    })
    sharedBlocks.value = response.data.items
    total.value = response.data.total
  } catch {
    error.value = '公开积木加载失败'
  } finally {
    loading.value = false
  }
}

async function openDetail(block: SharedBlockItem) {
  const response = await apiClient.get<SharedBlockDetail>(`/shared-blocks/${block.id}`)
  selectedBlock.value = response.data
}

async function toggleFavorite(block: SharedBlockItem) {
  if (!authStore.isAuthenticated) {
    window.dispatchEvent(new CustomEvent('sts:auth-required'))
    return
  }
  if (block.isFavorited) {
    await apiClient.delete(`/shared-blocks/${block.id}/favorite`)
    block.isFavorited = false
    block.favoriteCount = Math.max(0, block.favoriteCount - 1)
    status.value = '已取消收藏'
  } else {
    const response = await apiClient.post<SharedBlockDetail>(`/shared-blocks/${block.id}/favorite`)
    block.isFavorited = true
    block.favoriteCount = response.data.favoriteCount
    status.value = '已收藏'
  }
}

async function importBlock(block: SharedBlockItem) {
  if (!authStore.isAuthenticated) {
    window.dispatchEvent(new CustomEvent('sts:auth-required'))
    return
  }
  const response = await apiClient.post<{ id: number; name: string }>(`/shared-blocks/${block.id}/import`)
  status.value = `已导入到我的积木：${response.data.name}`
  block.importCount += 1
}
```

Template must expose these test selectors:

- `.shared-block-search-input`
- `.shared-block-category-input`
- `.shared-block-tag-input`
- `.shared-block-sort-select`
- `.shared-block-search-button`
- `.shared-block-detail-button`
- `.shared-block-favorite-button`
- `.shared-block-import-button`

- [ ] **Step 4: Add shared blocks CSS**

Add to `frontend/src/styles/base.css`:

```css
.shared-blocks {
  display: grid;
  gap: 14px;
}

.shared-block-toolbar {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(120px, 180px) minmax(120px, 180px) minmax(120px, 160px) auto;
  gap: 10px;
}

.shared-block-toolbar input,
.shared-block-toolbar select {
  border: 1px solid #3a3150;
  border-radius: 6px;
  padding: 9px 10px;
  color: #f7f2ff;
  background: #09080d;
}

.shared-block-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 360px);
  gap: 12px;
  align-items: start;
}

.shared-block-list {
  display: grid;
  gap: 10px;
}

.shared-block-card,
.shared-block-detail {
  border: 1px solid rgba(58, 49, 80, 0.86);
  border-radius: 8px;
  padding: 14px;
  background: rgba(9, 8, 13, 0.54);
}

.shared-block-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.shared-block-actions button,
.shared-block-toolbar button {
  border: 1px solid #3a3150;
  border-radius: 6px;
  padding: 9px 12px;
  color: #f7f2ff;
  background: #191522;
  cursor: pointer;
}

.shared-block-import-button {
  border-color: rgba(94, 230, 200, 0.44) !important;
  background: rgba(21, 57, 53, 0.76) !important;
}
```

- [ ] **Step 5: Verify frontend sharing page GREEN**

Run:

```bash
npm test -- shared-blocks-view.test.ts
```

Expected: all shared-block view tests pass.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add frontend/src/views/SharedBlocksView.vue frontend/tests/shared-blocks-view.test.ts frontend/src/styles/base.css
git commit -m "feat: browse and import shared blocks"
```

---

### Task 6: Admin Review Tab in Shared Blocks Page

**Files:**
- Modify: `frontend/src/views/SharedBlocksView.vue`
- Modify: `frontend/tests/shared-blocks-view.test.ts`
- Modify: `frontend/src/styles/base.css`

- [ ] **Step 1: Write failing admin review UI test**

Append to `frontend/tests/shared-blocks-view.test.ts`:

```ts
it('lets admins review pending shared blocks', async () => {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === '/shared-blocks') {
      return Promise.resolve({ data: { items: [sharedBlock], total: 1, page: 1, pageSize: 10 } })
    }
    if (url === '/admin/custom-block-reviews') {
      return Promise.resolve({
        data: {
          items: [{ ...sharedBlock, id: 41, name: '待审核模板', reviewStatus: 'pending_review' }],
          total: 1,
          page: 1,
          pageSize: 10
        }
      })
    }
    return Promise.reject(new Error(`Unhandled GET ${url}`))
  })
  vi.mocked(apiClient.post).mockResolvedValueOnce({
    data: { ...sharedBlockDetail, id: 41, name: '待审核模板', reviewStatus: 'approved' }
  })
  const authStore = useAuthStore()
  authStore.setSession({
    token: 'token-123',
    user: { id: 1, username: 'admin', email: 'admin@example.com', roles: ['admin'] }
  })
  const wrapper = mount(SharedBlocksView)
  await flushPromises()

  expect(wrapper.find('.shared-block-review-tab').exists()).toBe(true)
  await wrapper.find('.shared-block-review-tab').trigger('click')
  await flushPromises()

  expect(apiClient.get).toHaveBeenCalledWith('/admin/custom-block-reviews', {
    params: { keyword: '', page: 1, pageSize: 10 }
  })
  expect(wrapper.text()).toContain('待审核模板')

  await wrapper.find('.shared-block-approve-button').trigger('click')
  await flushPromises()

  expect(apiClient.post).toHaveBeenCalledWith('/admin/custom-block-reviews/41/approve')
  expect(wrapper.text()).toContain('审核已通过')
})
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
npm test -- shared-blocks-view.test.ts
```

Expected: failure because admin review tab does not exist.

- [ ] **Step 3: Implement admin review state and actions**

In `SharedBlocksView.vue`, add:

```ts
const activeMode = ref<'browse' | 'review'>('browse')
const reviewItems = ref<SharedBlockItem[]>([])
const reviewKeyword = ref('')
const reviewPage = ref(1)
const reviewTotal = ref(0)
const isAdmin = computed(() => authStore.user?.roles.includes('admin') ?? false)

async function loadReviewItems() {
  const response = await apiClient.get<SharedBlockListResponse>('/admin/custom-block-reviews', {
    params: { keyword: reviewKeyword.value.trim(), page: reviewPage.value, pageSize }
  })
  reviewItems.value = response.data.items
  reviewTotal.value = response.data.total
}

async function openReviewMode() {
  activeMode.value = 'review'
  await loadReviewItems()
}

async function approveReview(block: SharedBlockItem) {
  await apiClient.post(`/admin/custom-block-reviews/${block.id}/approve`)
  status.value = '审核已通过'
  await loadReviewItems()
  await loadSharedBlocks()
}

async function rejectReview(block: SharedBlockItem) {
  await apiClient.post(`/admin/custom-block-reviews/${block.id}/reject`)
  status.value = '审核已拒绝'
  await loadReviewItems()
}
```

Template must include:

```vue
<button
  v-if="isAdmin"
  class="shared-block-review-tab"
  type="button"
  :class="{ 'is-active': activeMode === 'review' }"
  @click="openReviewMode"
>
  审核
</button>
```

Review list buttons:

```vue
<button class="shared-block-approve-button" type="button" @click="approveReview(block)">通过</button>
<button class="shared-block-reject-button" type="button" @click="rejectReview(block)">拒绝</button>
```

- [ ] **Step 4: Add admin review CSS**

Add to `frontend/src/styles/base.css`:

```css
.shared-block-mode-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.shared-block-mode-tabs button {
  border: 1px solid #3a3150;
  border-radius: 6px;
  padding: 9px 12px;
  color: #f7f2ff;
  background: #191522;
  cursor: pointer;
}

.shared-block-mode-tabs button.is-active {
  border-color: rgba(124, 77, 255, 0.68);
  background: #302157;
}

.shared-block-approve-button {
  border-color: rgba(94, 230, 200, 0.44) !important;
  background: rgba(21, 57, 53, 0.76) !important;
}

.shared-block-reject-button {
  color: #ffe4ea !important;
  border-color: rgba(255, 139, 167, 0.48) !important;
  background: rgba(64, 25, 40, 0.72) !important;
}
```

- [ ] **Step 5: Verify admin UI GREEN**

Run:

```bash
npm test -- shared-blocks-view.test.ts
```

Expected: all shared-block view tests pass.

- [ ] **Step 6: Commit Task 6**

Run:

```bash
git add frontend/src/views/SharedBlocksView.vue frontend/tests/shared-blocks-view.test.ts frontend/src/styles/base.css
git commit -m "feat: review shared blocks from sharing page"
```

---

### Task 7: Full Verification and Browser QA

**Files:**
- No new files expected.
- Use this task to fix defects found by verification.

- [ ] **Step 1: Run backend full test suite**

Run:

```bash
backend/.venv/bin/pytest backend/tests
```

Expected: all backend tests pass. Existing JWT/key-length warnings may remain; no failures are acceptable.

- [ ] **Step 2: Run frontend full test suite**

Run:

```bash
npm test
```

Expected: all frontend tests pass.

- [ ] **Step 3: Run frontend production build**

Run:

```bash
npm run build
```

Expected: `vue-tsc` and Vite build pass.

- [ ] **Step 4: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 5: Browser QA**

Start or restart the backend if needed:

```bash
pid=$(lsof -ti tcp:8000 || true)
if [ -n "$pid" ]; then kill $pid; fi
backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use the in-app browser at:

- `http://127.0.0.1:5173/space?tab=custom-blocks`
- `http://127.0.0.1:5173/blocks`

Verify:

- Personal space shows `发布` for private blocks.
- Publishing changes the card status to `待审核`.
- Admin user sees the `审核` tab on the sharing page.
- Approved blocks appear in shared-block list.
- Search/filter/sort controls do not overlap at desktop width.
- Detail panel shows node summary and action buttons.
- Favorite and import buttons require login for visitors.

- [ ] **Step 6: Final commit for verification fixes**

If verification required code or style fixes, commit the exact files reported by `git status --short`. For the expected polish areas in this task, the command is:

```bash
git add frontend/src/views/SharedBlocksView.vue frontend/src/styles/base.css frontend/tests/shared-blocks-view.test.ts backend/app/services/shared_block_service.py backend/tests/test_shared_blocks.py
git commit -m "fix: polish shared blocks mvp"
```

If `git status --short` shows a different file list, replace the `git add` paths with the exact changed files from that output. If no fixes were needed, do not create an empty commit.

- [ ] **Step 7: Push all commits**

Run:

```bash
git push origin main
```

Expected: remote `main` advances successfully.

---

## Plan Self-Review

Spec coverage:

- Publish flow is covered by Task 1 and Task 4.
- Public list/detail/search/filter/sort is covered by Task 2 and Task 5.
- Favorite/import behavior is covered by Task 3 and Task 5.
- Admin review is covered by Task 3 and Task 6.
- Recommendation data foundation is covered by Task 2 and Task 3 through `recommendation_events`.
- Browser verification is covered by Task 7.

Scope control:

- Forum features are excluded.
- Complex personalization, version history, and full admin backend are excluded.
- The plan uses current architecture patterns and does not introduce Alembic or a new frontend component library.

Type consistency:

- Backend uses `review_status` internally and `reviewStatus` in API responses.
- Frontend uses `reviewStatus`, `authorName`, `nodeCount`, `connectionCount`, `viewCount`, `favoriteCount`, `importCount`, and `isFavorited` consistently with `SharedBlockItemResponse`.
- REST paths match the design spec: `/api/custom-blocks/{id}/publish`, `/api/shared-blocks`, and `/api/admin/custom-block-reviews`.
