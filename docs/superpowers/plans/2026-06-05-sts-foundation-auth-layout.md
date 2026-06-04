# STS Foundation Auth Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first executable STS milestone: backend FastAPI skeleton, MySQL-ready persistence layer, JWT authentication, role model, Vue 3 shell layout, login/register flow, and route-level auth state.

**Architecture:** This plan covers PRD stages 0-1 only. The backend exposes REST APIs under `/api`, uses SQLAlchemy models with a MySQL runtime URL and SQLite test URL, and signs JWT tokens containing `user_id` and roles. The frontend is a Vue 3 SPA with a fixed left navigation, top action/account bar, builder-first landing route, Pinia auth state, and Axios API client. The frontend visual direction is an obsidian-like dark interface: black and near-black surfaces as the dominant tone, refined purple accents for focus/active states, restrained borders, and a polished tool-app feel.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.x, Pydantic Settings, PyJWT, passlib bcrypt, pytest, httpx, Vue 3, Vite, TypeScript, Vue Router, Pinia, Axios, Vitest.

---

## Scope Check

The full STS V1 PRD covers many independent subsystems: strategy blocks, custom blocks, market data, backtesting, forum, sharing, recommendation, file management, and admin review. This implementation plan intentionally covers only the foundation milestone. Later plans should be created separately for:

- Strategy block system
- Custom parameterized blocks
- Simulation account and market rules
- Market data adapters and cache
- Backtesting engine
- Personal space
- Forum and audit workflow
- Shared blocks and recommendation
- File management and admin backend

## File Structure

Create this initial structure:

```text
/Users/zluo/Project/STS/
  backend/
    .env.example
    pyproject.toml
    app/
      __init__.py
      main.py
      api/
        __init__.py
        auth.py
        health.py
      core/
        __init__.py
        config.py
        database.py
        security.py
      models/
        __init__.py
        user.py
      schemas/
        __init__.py
        auth.py
      services/
        __init__.py
        auth_service.py
    tests/
      conftest.py
      test_auth.py
      test_config.py
      test_health.py
      test_security.py
  frontend/
    index.html
    package.json
    tsconfig.json
    tsconfig.node.json
    vite.config.ts
    src/
      App.vue
      main.ts
      api/
        http.ts
      router/
        index.ts
      stores/
        auth.ts
      styles/
        base.css
      views/
        BuilderView.vue
        ForumView.vue
        LoginView.vue
        PersonalSpaceView.vue
        RegisterView.vue
        SharedBlocksView.vue
    tests/
      auth-store.test.ts
```

## Task 1: Backend Package And Health Endpoint

**Files:**
- Create: `/Users/zluo/Project/STS/backend/pyproject.toml`
- Create: `/Users/zluo/Project/STS/backend/app/__init__.py`
- Create: `/Users/zluo/Project/STS/backend/app/main.py`
- Create: `/Users/zluo/Project/STS/backend/app/api/__init__.py`
- Create: `/Users/zluo/Project/STS/backend/app/api/health.py`
- Create: `/Users/zluo/Project/STS/backend/tests/test_health.py`

- [ ] **Step 1: Write the health endpoint test**

Create `/Users/zluo/Project/STS/backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_ok():
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "sts-api"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/zluo/Project/STS/backend
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest tests/test_health.py -v
```

Expected: FAIL before implementation because `pyproject.toml` and `app.main` do not exist.

- [ ] **Step 3: Create backend package metadata**

Create `/Users/zluo/Project/STS/backend/pyproject.toml`:

```toml
[project]
name = "sts-backend"
version = "0.1.0"
description = "Simulated Trading System backend"
requires-python = ">=3.10"
dependencies = [
  "fastapi>=0.111.0",
  "uvicorn[standard]>=0.30.0",
  "sqlalchemy>=2.0.30",
  "pydantic-settings>=2.2.1",
  "pymysql>=1.1.0",
  "PyJWT>=2.8.0",
  "passlib[bcrypt]>=1.7.4",
  "python-multipart>=0.0.9"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2.0",
  "httpx>=0.27.0",
  "ruff>=0.5.0"
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

- [ ] **Step 4: Create health router and FastAPI app**

Create `/Users/zluo/Project/STS/backend/app/__init__.py`:

```python
```

Create `/Users/zluo/Project/STS/backend/app/api/__init__.py`:

```python
```

Create `/Users/zluo/Project/STS/backend/app/api/health.py`:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "sts-api"}
```

Create `/Users/zluo/Project/STS/backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health

app = FastAPI(title="STS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
cd /Users/zluo/Project/STS/backend
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

If this workspace is not yet a git repository, initialize it once:

```bash
cd /Users/zluo/Project/STS
git init
git add backend/pyproject.toml backend/app backend/tests/test_health.py
git commit -m "feat: initialize backend health api"
```

If git was already initialized, use:

```bash
cd /Users/zluo/Project/STS
git add backend/pyproject.toml backend/app backend/tests/test_health.py
git commit -m "feat: initialize backend health api"
```

## Task 2: Backend Settings And Database Session

**Files:**
- Create: `/Users/zluo/Project/STS/backend/.env.example`
- Create: `/Users/zluo/Project/STS/backend/app/core/__init__.py`
- Create: `/Users/zluo/Project/STS/backend/app/core/config.py`
- Create: `/Users/zluo/Project/STS/backend/app/core/database.py`
- Create: `/Users/zluo/Project/STS/backend/tests/test_config.py`

- [ ] **Step 1: Write config tests**

Create `/Users/zluo/Project/STS/backend/tests/test_config.py`:

```python
from app.core.config import Settings


def test_settings_reads_database_url():
    settings = Settings(database_url="mysql+pymysql://sts:sts@localhost:3306/sts")

    assert settings.database_url == "mysql+pymysql://sts:sts@localhost:3306/sts"
    assert settings.jwt_algorithm == "HS256"


def test_cors_origins_are_split_from_csv():
    settings = Settings(cors_origins="http://localhost:5173,http://127.0.0.1:5173")

    assert settings.cors_origin_list == ["http://localhost:5173", "http://127.0.0.1:5173"]
```

- [ ] **Step 2: Run config tests to verify they fail**

Run:

```bash
cd /Users/zluo/Project/STS/backend
source .venv/bin/activate
pytest tests/test_config.py -v
```

Expected: FAIL because `app.core.config` does not exist.

- [ ] **Step 3: Create env template**

Create `/Users/zluo/Project/STS/backend/.env.example`:

```env
APP_NAME=STS API
ENVIRONMENT=development
DATABASE_URL=mysql+pymysql://sts:sts@127.0.0.1:3306/sts
JWT_SECRET_KEY=change-me-in-development
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

- [ ] **Step 4: Create settings module**

Create `/Users/zluo/Project/STS/backend/app/core/__init__.py`:

```python
```

Create `/Users/zluo/Project/STS/backend/app/core/config.py`:

```python
from functools import cached_property, lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "STS API"
    environment: str = "development"
    database_url: str = "sqlite+pysqlite:///./sts_dev.db"
    jwt_secret_key: str = "change-me-in-development"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="Comma-separated CORS origin list",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @cached_property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Create database module**

Create `/Users/zluo/Project/STS/backend/app/core/database.py`:

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 6: Update FastAPI app to use settings CORS**

Modify `/Users/zluo/Project/STS/backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
```

- [ ] **Step 7: Run tests to verify they pass**

Run:

```bash
cd /Users/zluo/Project/STS/backend
source .venv/bin/activate
pytest tests/test_config.py tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
cd /Users/zluo/Project/STS
git add backend/.env.example backend/app/core backend/app/main.py backend/tests/test_config.py
git commit -m "feat: add backend settings and database session"
```

## Task 3: Password Hashing And JWT Security

**Files:**
- Create: `/Users/zluo/Project/STS/backend/app/core/security.py`
- Create: `/Users/zluo/Project/STS/backend/tests/test_security.py`

- [ ] **Step 1: Write security tests**

Create `/Users/zluo/Project/STS/backend/tests/test_security.py`:

```python
from datetime import timedelta

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_round_trip():
    password = "StrongerPass123"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_contains_user_id_and_roles():
    token = create_access_token(
        subject="42",
        roles=["user", "admin"],
        expires_delta=timedelta(minutes=10),
        secret_key="test-secret",
    )

    payload = decode_access_token(token, secret_key="test-secret")

    assert payload["sub"] == "42"
    assert payload["roles"] == ["user", "admin"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/zluo/Project/STS/backend
source .venv/bin/activate
pytest tests/test_security.py -v
```

Expected: FAIL because `app.core.security` does not exist.

- [ ] **Step 3: Implement security helpers**

Create `/Users/zluo/Project/STS/backend/app/core/security.py`:

```python
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    *,
    subject: str,
    roles: list[str],
    expires_delta: timedelta | None = None,
    secret_key: str | None = None,
) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "roles": roles,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(
        payload,
        secret_key or settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str, secret_key: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(
        token,
        secret_key or settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
```

- [ ] **Step 4: Run security tests**

Run:

```bash
cd /Users/zluo/Project/STS/backend
source .venv/bin/activate
pytest tests/test_security.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/zluo/Project/STS
git add backend/app/core/security.py backend/tests/test_security.py
git commit -m "feat: add password hashing and jwt helpers"
```

## Task 4: User Models And Auth API

**Files:**
- Create: `/Users/zluo/Project/STS/backend/app/models/__init__.py`
- Create: `/Users/zluo/Project/STS/backend/app/models/user.py`
- Create: `/Users/zluo/Project/STS/backend/app/schemas/__init__.py`
- Create: `/Users/zluo/Project/STS/backend/app/schemas/auth.py`
- Create: `/Users/zluo/Project/STS/backend/app/services/__init__.py`
- Create: `/Users/zluo/Project/STS/backend/app/services/auth_service.py`
- Create: `/Users/zluo/Project/STS/backend/app/api/auth.py`
- Create: `/Users/zluo/Project/STS/backend/tests/conftest.py`
- Create: `/Users/zluo/Project/STS/backend/tests/test_auth.py`
- Modify: `/Users/zluo/Project/STS/backend/app/main.py`

- [ ] **Step 1: Write auth API tests**

Create `/Users/zluo/Project/STS/backend/tests/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+pysqlite://"


@pytest.fixture
def db_session():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as session:
        yield session

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
```

Create `/Users/zluo/Project/STS/backend/tests/test_auth.py`:

```python
def test_register_creates_user_and_returns_token(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "StrongerPass123",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["user"]["username"] == "alice"
    assert payload["user"]["roles"] == ["user"]
    assert payload["access_token"]


def test_register_rejects_duplicate_email(client):
    user = {
        "username": "alice",
        "email": "alice@example.com",
        "password": "StrongerPass123",
    }
    assert client.post("/api/auth/register", json=user).status_code == 201

    response = client.post(
        "/api/auth/register",
        json={**user, "username": "alice2"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


def test_login_returns_token_for_valid_credentials(client):
    client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "StrongerPass123",
        },
    )

    response = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "StrongerPass123"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "alice@example.com"
    assert response.json()["access_token"]


def test_login_rejects_bad_credentials(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "bad-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
```

- [ ] **Step 2: Run auth tests to verify they fail**

Run:

```bash
cd /Users/zluo/Project/STS/backend
source .venv/bin/activate
pytest tests/test_auth.py -v
```

Expected: FAIL because auth models and routes do not exist.

- [ ] **Step 3: Create user models**

Create `/Users/zluo/Project/STS/backend/app/models/__init__.py`:

```python
from app.models.user import Role, User, user_roles

__all__ = ["Role", "User", "user_roles"]
```

Create `/Users/zluo/Project/STS/backend/app/models/user.py`:

```python
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        UniqueConstraint("email", name="uq_users_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    roles: Mapped[list["Role"]] = relationship(
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",
    )


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("name", name="uq_roles_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    users: Mapped[list[User]] = relationship(
        secondary=user_roles,
        back_populates="roles",
        lazy="selectin",
    )
```

- [ ] **Step 4: Create auth schemas**

Create `/Users/zluo/Project/STS/backend/app/schemas/__init__.py`:

```python
```

Create `/Users/zluo/Project/STS/backend/app/schemas/auth.py`:

```python
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    roles: list[str]


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
```

- [ ] **Step 5: Add missing email dependency**

Modify `/Users/zluo/Project/STS/backend/pyproject.toml` dependencies list to include `email-validator`:

```toml
dependencies = [
  "fastapi>=0.111.0",
  "uvicorn[standard]>=0.30.0",
  "sqlalchemy>=2.0.30",
  "pydantic-settings>=2.2.1",
  "pymysql>=1.1.0",
  "PyJWT>=2.8.0",
  "passlib[bcrypt]>=1.7.4",
  "python-multipart>=0.0.9",
  "email-validator>=2.1.1"
]
```

- [ ] **Step 6: Create auth service**

Create `/Users/zluo/Project/STS/backend/app/services/__init__.py`:

```python
```

Create `/Users/zluo/Project/STS/backend/app/services/auth_service.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import Role, User
from app.schemas.auth import AuthResponse, RegisterRequest, UserResponse


def get_or_create_role(db: Session, name: str) -> Role:
    role = db.scalar(select(Role).where(Role.name == name))
    if role is not None:
        return role

    role = Role(name=name)
    db.add(role)
    db.flush()
    return role


def user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        roles=[role.name for role in user.roles],
    )


def build_auth_response(user: User) -> AuthResponse:
    roles = [role.name for role in user.roles]
    token = create_access_token(subject=str(user.id), roles=roles)
    return AuthResponse(access_token=token, user=user_to_response(user))


def register_user(db: Session, request: RegisterRequest) -> AuthResponse:
    existing_email = db.scalar(select(User).where(User.email == request.email))
    if existing_email is not None:
        raise ValueError("Email already registered")

    existing_username = db.scalar(select(User).where(User.username == request.username))
    if existing_username is not None:
        raise ValueError("Username already registered")

    user_role = get_or_create_role(db, "user")
    user = User(
        username=request.username,
        email=str(request.email),
        password_hash=hash_password(request.password),
        roles=[user_role],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return build_auth_response(user)


def authenticate_user(db: Session, email: str, password: str) -> AuthResponse | None:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None
    return build_auth_response(user)
```

- [ ] **Step 7: Create auth API router**

Create `/Users/zluo/Project/STS/backend/app/api/auth.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.services.auth_service import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        return register_user(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    response = authenticate_user(db, str(request.email), request.password)
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return response
```

- [ ] **Step 8: Register auth router and ensure models are imported**

Modify `/Users/zluo/Project/STS/backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, health
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
```

- [ ] **Step 9: Install updated dependencies and run auth tests**

Run:

```bash
cd /Users/zluo/Project/STS/backend
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest tests/test_auth.py tests/test_security.py tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
cd /Users/zluo/Project/STS
git add backend/pyproject.toml backend/app backend/tests
git commit -m "feat: add user registration and login api"
```

## Task 5: Current User Dependency And Role Checks

**Files:**
- Create: `/Users/zluo/Project/STS/backend/app/api/dependencies.py`
- Create: `/Users/zluo/Project/STS/backend/tests/test_current_user.py`
- Modify: `/Users/zluo/Project/STS/backend/app/api/auth.py`

- [ ] **Step 1: Write current user tests**

Create `/Users/zluo/Project/STS/backend/tests/test_current_user.py`:

```python
def test_me_requires_token(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_returns_current_user(client):
    register_response = client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "StrongerPass123",
        },
    )
    token = register_response.json()["access_token"]

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    assert response.json()["roles"] == ["user"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/zluo/Project/STS/backend
source .venv/bin/activate
pytest tests/test_current_user.py -v
```

Expected: FAIL because `/api/auth/me` and dependency helpers do not exist.

- [ ] **Step 3: Create dependency helpers**

Create `/Users/zluo/Project/STS/backend/app/api/dependencies.py`:

```python
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.scalar(select(User).where(User.id == int(user_id)))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User unavailable")
    return user


def require_role(role_name: str) -> Callable[[User], User]:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        role_names = {role.name for role in current_user.roles}
        if role_name not in role_names:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return current_user

    return dependency
```

- [ ] **Step 4: Add `/me` route**

Modify `/Users/zluo/Project/STS/backend/app/api/auth.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from app.services.auth_service import authenticate_user, register_user, user_to_response

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        return register_user(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    response = authenticate_user(db, str(request.email), request.password)
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return response


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return user_to_response(current_user)
```

- [ ] **Step 5: Run backend tests**

Run:

```bash
cd /Users/zluo/Project/STS/backend
source .venv/bin/activate
pytest -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/zluo/Project/STS
git add backend/app/api backend/tests/test_current_user.py
git commit -m "feat: add current user authentication dependency"
```

## Task 6: Frontend Project Shell And Layout

**Files:**
- Create: `/Users/zluo/Project/STS/frontend/package.json`
- Create: `/Users/zluo/Project/STS/frontend/index.html`
- Create: `/Users/zluo/Project/STS/frontend/tsconfig.json`
- Create: `/Users/zluo/Project/STS/frontend/tsconfig.node.json`
- Create: `/Users/zluo/Project/STS/frontend/vite.config.ts`
- Create: `/Users/zluo/Project/STS/frontend/src/main.ts`
- Create: `/Users/zluo/Project/STS/frontend/src/App.vue`
- Create: `/Users/zluo/Project/STS/frontend/src/router/index.ts`
- Create: `/Users/zluo/Project/STS/frontend/src/styles/base.css`
- Create: `/Users/zluo/Project/STS/frontend/src/views/BuilderView.vue`
- Create: `/Users/zluo/Project/STS/frontend/src/views/PersonalSpaceView.vue`
- Create: `/Users/zluo/Project/STS/frontend/src/views/ForumView.vue`
- Create: `/Users/zluo/Project/STS/frontend/src/views/SharedBlocksView.vue`

- [ ] **Step 1: Create frontend package metadata**

Create `/Users/zluo/Project/STS/frontend/package.json`:

```json
{
  "name": "sts-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "vue-tsc && vite build",
    "test": "vitest run",
    "lint": "eslint . --ext .vue,.ts"
  },
  "dependencies": {
    "@vitejs/plugin-vue": "^5.0.5",
    "axios": "^1.7.2",
    "echarts": "^5.5.0",
    "pinia": "^2.1.7",
    "vue": "^3.4.30",
    "vue-router": "^4.4.0"
  },
  "devDependencies": {
    "@types/node": "^20.14.8",
    "@vue/test-utils": "^2.4.6",
    "eslint": "^9.5.0",
    "jsdom": "^24.1.0",
    "typescript": "^5.4.5",
    "vite": "^5.3.1",
    "vitest": "^1.6.0",
    "vue-tsc": "^2.0.22"
  }
}
```

- [ ] **Step 2: Create Vite and TypeScript config**

Create `/Users/zluo/Project/STS/frontend/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>STS</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

Create `/Users/zluo/Project/STS/frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "strict": true,
    "jsx": "preserve",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "types": ["vitest/globals"]
  },
  "include": ["src/**/*.ts", "src/**/*.d.ts", "src/**/*.tsx", "src/**/*.vue", "tests/**/*.ts"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `/Users/zluo/Project/STS/frontend/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

Create `/Users/zluo/Project/STS/frontend/vite.config.ts`:

```ts
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  },
  test: {
    environment: 'jsdom',
    globals: true
  }
})
```

- [ ] **Step 3: Create router and placeholder views**

Create `/Users/zluo/Project/STS/frontend/src/router/index.ts`:

```ts
import { createRouter, createWebHistory } from 'vue-router'
import BuilderView from '../views/BuilderView.vue'
import ForumView from '../views/ForumView.vue'
import PersonalSpaceView from '../views/PersonalSpaceView.vue'
import SharedBlocksView from '../views/SharedBlocksView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'builder', component: BuilderView },
    { path: '/space', name: 'space', component: PersonalSpaceView },
    { path: '/forum', name: 'forum', component: ForumView },
    { path: '/blocks', name: 'shared-blocks', component: SharedBlocksView }
  ]
})
```

Create `/Users/zluo/Project/STS/frontend/src/views/BuilderView.vue`:

```vue
<template>
  <section class="work-surface">
    <div class="toolbar-panel">
      <button>保存策略</button>
      <button>运行回测</button>
      <button>发布积木</button>
    </div>

    <div class="canvas-placeholder">
      <h1>搭建积木</h1>
      <p>在这里拼接策略积木。未登录用户可以临时搭建，但不能保存或运行完整回测。</p>
    </div>
  </section>
</template>
```

Create `/Users/zluo/Project/STS/frontend/src/views/PersonalSpaceView.vue`:

```vue
<template>
  <section class="page-panel">
    <h1>个人空间</h1>
    <p>这里将管理我的策略、自定义积木、模拟账户、回测记录和收藏。</p>
  </section>
</template>
```

Create `/Users/zluo/Project/STS/frontend/src/views/ForumView.vue`:

```vue
<template>
  <section class="page-panel">
    <h1>论坛</h1>
    <p>这里将支持发帖、评论、审核状态和关联策略/回测/积木。</p>
  </section>
</template>
```

Create `/Users/zluo/Project/STS/frontend/src/views/SharedBlocksView.vue`:

```vue
<template>
  <section class="page-panel">
    <h1>积木分享</h1>
    <p>这里将集中提供公开积木搜索、筛选、收藏、导入和推荐。</p>
  </section>
</template>
```

- [ ] **Step 4: Create app shell matching PRD layout**

Create `/Users/zluo/Project/STS/frontend/src/App.vue`:

```vue
<template>
  <div class="app-shell">
    <aside class="side-nav" aria-label="主导航">
      <div class="brand">STS</div>
      <RouterLink to="/">搭建</RouterLink>
      <RouterLink to="/space">空间</RouterLink>
      <RouterLink to="/forum">论坛</RouterLink>
      <RouterLink to="/blocks">分享</RouterLink>
    </aside>

    <main class="main-shell">
      <header class="top-bar">
        <div class="top-actions">
          <span class="section-title">Simulated Trading System</span>
        </div>
        <div class="account-actions">
          <RouterLink to="/login">登录</RouterLink>
          <RouterLink to="/register">注册</RouterLink>
        </div>
      </header>

      <div class="content-grid">
        <RouterView />
        <aside class="block-library" aria-label="积木库">
          <h2>积木库</h2>
          <input placeholder="搜索积木" />
          <nav>
            <button>条件</button>
            <button>指标</button>
            <button>动作</button>
            <button>风控</button>
            <button>自定义</button>
          </nav>
        </aside>
      </div>
    </main>
  </div>
</template>
```

Create `/Users/zluo/Project/STS/frontend/src/main.ts`:

```ts
import { createPinia } from 'pinia'
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import './styles/base.css'

createApp(App).use(createPinia()).use(router).mount('#app')
```

- [ ] **Step 5: Create base styles**

Create `/Users/zluo/Project/STS/frontend/src/styles/base.css`:

```css
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #f7f2ff;
  background: #07070b;
}

button,
input {
  font: inherit;
}

.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
}

.side-nav {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px 10px;
  background: #050508;
  border-right: 1px solid #24202e;
  color: #fff;
}

.brand {
  font-weight: 800;
  text-align: center;
  margin-bottom: 18px;
}

.side-nav a {
  color: #cfc7dc;
  text-decoration: none;
  text-align: center;
  padding: 10px 6px;
  border-radius: 8px;
}

.side-nav a.router-link-active {
  background: #6d3df2;
  color: #fff;
  box-shadow: 0 0 24px rgba(109, 61, 242, 0.24);
}

.main-shell {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.top-bar {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: #0d0b12;
  border-bottom: 1px solid #24202e;
}

.section-title {
  font-weight: 700;
}

.account-actions {
  display: flex;
  gap: 12px;
}

.account-actions a {
  color: #b89cff;
  text-decoration: none;
  font-weight: 600;
}

.content-grid {
  min-height: calc(100vh - 64px);
  display: grid;
  grid-template-columns: minmax(0, 1fr) 260px;
  gap: 16px;
  padding: 16px;
}

.block-library,
.page-panel,
.work-surface {
  background: #111019;
  border: 1px solid #292437;
  border-radius: 8px;
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.32);
}

.work-surface,
.page-panel {
  padding: 18px;
}

.toolbar-panel {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.toolbar-panel button,
.block-library button {
  border: 1px solid #3a3150;
  background: #191522;
  color: #f7f2ff;
  border-radius: 6px;
  padding: 8px 10px;
  cursor: pointer;
}

.canvas-placeholder {
  min-height: 360px;
  border: 1px dashed #5e4f7a;
  border-radius: 8px;
  padding: 24px;
  background: #0b0a10;
}

.block-library {
  padding: 16px;
}

.block-library input {
  width: 100%;
  border: 1px solid #3a3150;
  border-radius: 6px;
  padding: 9px 10px;
  margin-bottom: 14px;
  color: #f7f2ff;
  background: #09080d;
}

.block-library nav {
  display: grid;
  gap: 8px;
}
```

- [ ] **Step 6: Install frontend dependencies and build**

Run:

```bash
cd /Users/zluo/Project/STS/frontend
npm install
npm run build
```

Expected: PASS and Vite emits `dist/`.

- [ ] **Step 7: Commit**

```bash
cd /Users/zluo/Project/STS
git add frontend
git commit -m "feat: add vue app shell layout"
```

## Task 7: Frontend Auth Store And API Client

**Files:**
- Create: `/Users/zluo/Project/STS/frontend/src/api/http.ts`
- Create: `/Users/zluo/Project/STS/frontend/src/stores/auth.ts`
- Create: `/Users/zluo/Project/STS/frontend/tests/auth-store.test.ts`

- [ ] **Step 1: Write auth store tests**

Create `/Users/zluo/Project/STS/frontend/tests/auth-store.test.ts`:

```ts
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '../src/stores/auth'

vi.mock('../src/api/http', () => ({
  apiClient: {
    post: vi.fn()
  }
}))

import { apiClient } from '../src/api/http'

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('stores user and token after login', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        access_token: 'token-123',
        token_type: 'bearer',
        user: {
          id: 1,
          username: 'alice',
          email: 'alice@example.com',
          roles: ['user']
        }
      }
    })
    const store = useAuthStore()

    await store.login('alice@example.com', 'StrongerPass123')

    expect(store.user?.username).toBe('alice')
    expect(store.token).toBe('token-123')
    expect(localStorage.getItem('sts_access_token')).toBe('token-123')
  })

  it('clears user and token on logout', () => {
    const store = useAuthStore()
    store.setSession({
      token: 'token-123',
      user: { id: 1, username: 'alice', email: 'alice@example.com', roles: ['user'] }
    })

    store.logout()

    expect(store.user).toBeNull()
    expect(store.token).toBeNull()
    expect(localStorage.getItem('sts_access_token')).toBeNull()
  })
})
```

- [ ] **Step 2: Run frontend test to verify it fails**

Run:

```bash
cd /Users/zluo/Project/STS/frontend
npm test -- tests/auth-store.test.ts
```

Expected: FAIL because `src/stores/auth.ts` and `src/api/http.ts` do not exist.

- [ ] **Step 3: Create API client**

Create `/Users/zluo/Project/STS/frontend/src/api/http.ts`:

```ts
import axios from 'axios'

export const apiClient = axios.create({
  baseURL: '/api',
  timeout: 15000
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('sts_access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
```

- [ ] **Step 4: Create auth store**

Create `/Users/zluo/Project/STS/frontend/src/stores/auth.ts`:

```ts
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { apiClient } from '../api/http'

export interface AuthUser {
  id: number
  username: string
  email: string
  roles: string[]
}

interface AuthResponse {
  access_token: string
  token_type: string
  user: AuthUser
}

interface SessionPayload {
  token: string
  user: AuthUser
}

const TOKEN_KEY = 'sts_access_token'
const USER_KEY = 'sts_user'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const storedUser = localStorage.getItem(USER_KEY)
  const user = ref<AuthUser | null>(storedUser ? JSON.parse(storedUser) : null)
  const isAuthenticated = computed(() => Boolean(token.value && user.value))

  function setSession(payload: SessionPayload) {
    token.value = payload.token
    user.value = payload.user
    localStorage.setItem(TOKEN_KEY, payload.token)
    localStorage.setItem(USER_KEY, JSON.stringify(payload.user))
  }

  async function login(email: string, password: string) {
    const response = await apiClient.post<AuthResponse>('/auth/login', { email, password })
    setSession({ token: response.data.access_token, user: response.data.user })
  }

  async function register(username: string, email: string, password: string) {
    const response = await apiClient.post<AuthResponse>('/auth/register', {
      username,
      email,
      password
    })
    setSession({ token: response.data.access_token, user: response.data.user })
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  return {
    token,
    user,
    isAuthenticated,
    setSession,
    login,
    register,
    logout
  }
})
```

- [ ] **Step 5: Run auth store tests**

Run:

```bash
cd /Users/zluo/Project/STS/frontend
npm test -- tests/auth-store.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/zluo/Project/STS
git add frontend/src/api frontend/src/stores frontend/tests
git commit -m "feat: add frontend auth store"
```

## Task 8: Frontend Login Register Views And Account Bar

**Files:**
- Create: `/Users/zluo/Project/STS/frontend/src/views/LoginView.vue`
- Create: `/Users/zluo/Project/STS/frontend/src/views/RegisterView.vue`
- Modify: `/Users/zluo/Project/STS/frontend/src/router/index.ts`
- Modify: `/Users/zluo/Project/STS/frontend/src/App.vue`
- Modify: `/Users/zluo/Project/STS/frontend/src/styles/base.css`

- [ ] **Step 1: Add auth routes**

Modify `/Users/zluo/Project/STS/frontend/src/router/index.ts`:

```ts
import { createRouter, createWebHistory } from 'vue-router'
import BuilderView from '../views/BuilderView.vue'
import ForumView from '../views/ForumView.vue'
import LoginView from '../views/LoginView.vue'
import PersonalSpaceView from '../views/PersonalSpaceView.vue'
import RegisterView from '../views/RegisterView.vue'
import SharedBlocksView from '../views/SharedBlocksView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'builder', component: BuilderView },
    { path: '/space', name: 'space', component: PersonalSpaceView },
    { path: '/forum', name: 'forum', component: ForumView },
    { path: '/blocks', name: 'shared-blocks', component: SharedBlocksView },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/register', name: 'register', component: RegisterView }
  ]
})
```

- [ ] **Step 2: Create login view**

Create `/Users/zluo/Project/STS/frontend/src/views/LoginView.vue`:

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await authStore.login(email.value, password.value)
    await router.push('/')
  } catch {
    error.value = '邮箱或密码错误'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="auth-card">
    <h1>登录</h1>
    <form @submit.prevent="submit">
      <label>
        邮箱
        <input v-model="email" type="email" required />
      </label>
      <label>
        密码
        <input v-model="password" type="password" required />
      </label>
      <p v-if="error" class="form-error">{{ error }}</p>
      <button type="submit" :disabled="loading">{{ loading ? '登录中' : '登录' }}</button>
    </form>
  </section>
</template>
```

- [ ] **Step 3: Create register view**

Create `/Users/zluo/Project/STS/frontend/src/views/RegisterView.vue`:

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const username = ref('')
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await authStore.register(username.value, email.value, password.value)
    await router.push('/')
  } catch {
    error.value = '注册失败，请检查用户名、邮箱或密码'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="auth-card">
    <h1>注册</h1>
    <form @submit.prevent="submit">
      <label>
        用户名
        <input v-model="username" type="text" minlength="3" required />
      </label>
      <label>
        邮箱
        <input v-model="email" type="email" required />
      </label>
      <label>
        密码
        <input v-model="password" type="password" minlength="8" required />
      </label>
      <p v-if="error" class="form-error">{{ error }}</p>
      <button type="submit" :disabled="loading">{{ loading ? '注册中' : '注册' }}</button>
    </form>
  </section>
</template>
```

- [ ] **Step 4: Update account bar to reflect auth state**

Modify `/Users/zluo/Project/STS/frontend/src/App.vue`:

```vue
<script setup lang="ts">
import { useAuthStore } from './stores/auth'

const authStore = useAuthStore()
</script>

<template>
  <div class="app-shell">
    <aside class="side-nav" aria-label="主导航">
      <div class="brand">STS</div>
      <RouterLink to="/">搭建</RouterLink>
      <RouterLink to="/space">空间</RouterLink>
      <RouterLink to="/forum">论坛</RouterLink>
      <RouterLink to="/blocks">分享</RouterLink>
    </aside>

    <main class="main-shell">
      <header class="top-bar">
        <div class="top-actions">
          <span class="section-title">Simulated Trading System</span>
        </div>
        <div class="account-actions">
          <template v-if="authStore.isAuthenticated && authStore.user">
            <span>{{ authStore.user.username }}</span>
            <button type="button" @click="authStore.logout">退出</button>
          </template>
          <template v-else>
            <RouterLink to="/login">登录</RouterLink>
            <RouterLink to="/register">注册</RouterLink>
          </template>
        </div>
      </header>

      <div class="content-grid">
        <RouterView />
        <aside class="block-library" aria-label="积木库">
          <h2>积木库</h2>
          <input placeholder="搜索积木" />
          <nav>
            <button>条件</button>
            <button>指标</button>
            <button>动作</button>
            <button>风控</button>
            <button>自定义</button>
          </nav>
        </aside>
      </div>
    </main>
  </div>
</template>
```

- [ ] **Step 5: Add auth form styles**

Append to `/Users/zluo/Project/STS/frontend/src/styles/base.css`:

```css
.auth-card {
  width: min(420px, 100%);
  align-self: start;
  background: #111019;
  border: 1px solid #292437;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.32);
}

.auth-card form {
  display: grid;
  gap: 14px;
}

.auth-card label {
  display: grid;
  gap: 6px;
  font-weight: 600;
}

.auth-card input {
  border: 1px solid #3a3150;
  border-radius: 6px;
  padding: 10px 12px;
  color: #f7f2ff;
  background: #09080d;
}

.auth-card button,
.account-actions button {
  border: 1px solid #7c4dff;
  background: #6d3df2;
  color: #fff;
  border-radius: 6px;
  padding: 8px 12px;
  cursor: pointer;
}

.form-error {
  margin: 0;
  color: #ff8ba7;
}
```

- [ ] **Step 6: Build frontend**

Run:

```bash
cd /Users/zluo/Project/STS/frontend
npm run build
npm test
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd /Users/zluo/Project/STS
git add frontend/src frontend/tests
git commit -m "feat: add frontend login and register flow"
```

## Task 9: End-To-End Local Smoke Run

**Files:**
- Modify: `/Users/zluo/Project/STS/docs/superpowers/plans/2026-06-05-sts-foundation-auth-layout.md`

- [ ] **Step 1: Run backend tests**

Run:

```bash
cd /Users/zluo/Project/STS/backend
source .venv/bin/activate
pytest -v
```

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend tests and build**

Run:

```bash
cd /Users/zluo/Project/STS/frontend
npm test
npm run build
```

Expected: all frontend tests pass and build succeeds.

- [ ] **Step 3: Start backend server**

Run:

```bash
cd /Users/zluo/Project/STS/backend
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Expected: server listens at `http://127.0.0.1:8000`.

- [ ] **Step 4: Start frontend dev server in another terminal**

Run:

```bash
cd /Users/zluo/Project/STS/frontend
npm run dev
```

Expected: Vite serves the app at `http://127.0.0.1:5173`.

- [ ] **Step 5: Manual smoke test**

Open `http://127.0.0.1:5173` and verify:

- The first screen is the builder page.
- Left navigation contains 搭建, 空间, 论坛, 分享.
- Right side contains 积木库.
- Top-right contains 登录 and 注册 when logged out.
- Register creates a user and redirects to the builder page.
- Top-right shows username and 退出 after login/register.
- Logout returns top-right to 登录 and 注册.

- [ ] **Step 6: Commit plan execution notes if changed**

If execution notes were added to this plan during implementation:

```bash
cd /Users/zluo/Project/STS
git add docs/superpowers/plans/2026-06-05-sts-foundation-auth-layout.md
git commit -m "docs: record foundation smoke test notes"
```

## Self-Review

### Spec Coverage

This plan covers these PRD requirements:

- Python 3.10+ backend skeleton
- Vue 3 frontend skeleton
- Frontend first screen opens to builder page
- Left navigation and top account area
- Right-side block library placeholder
- JWT login authentication
- Role-ready user model with ordinary user role
- REST API foundation
- MySQL-ready SQLAlchemy database configuration

This plan intentionally does not implement:

- Strategy CRUD
- Block definitions
- Custom parameterized blocks
- Simulation accounts
- Market data
- Backtesting
- Forum
- Shared blocks
- Recommendation
- File upload/download
- Admin review backend

Those modules need separate implementation plans.

### Placeholder Scan

The plan contains no `TBD`, `TODO`, or unspecified implementation steps. Placeholder UI text exists only as intentional first-milestone page content and should be replaced by later feature plans.

### Type Consistency

Backend auth response uses `access_token`, `token_type`, and `user`; frontend `AuthResponse` matches those fields. User role names are strings, and the default registered user role is `user` across backend tests, service code, and frontend state.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-05-sts-foundation-auth-layout.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
