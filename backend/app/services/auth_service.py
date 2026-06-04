from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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


def _registration_integrity_error_message(exc: IntegrityError) -> str:
    details = str(exc.orig).lower()
    if "uq_users_email" in details or "users.email" in details:
        return "Email already registered"
    if "uq_users_username" in details or "users.username" in details:
        return "Username already registered"
    return "Registration conflicts with an existing record"


def register_user(db: Session, request: RegisterRequest) -> AuthResponse:
    existing_email = db.scalar(select(User).where(User.email == request.email))
    if existing_email is not None:
        raise ValueError("Email already registered")

    existing_username = db.scalar(select(User).where(User.username == request.username))
    if existing_username is not None:
        raise ValueError("Username already registered")

    try:
        user_role = get_or_create_role(db, "user")
        user = User(
            username=request.username,
            email=str(request.email),
            password_hash=hash_password(request.password),
            roles=[user_role],
        )
        db.add(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(_registration_integrity_error_message(exc)) from exc

    db.refresh(user)
    return build_auth_response(user)


def authenticate_user(db: Session, email: str, password: str) -> AuthResponse | None:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None
    return build_auth_response(user)
