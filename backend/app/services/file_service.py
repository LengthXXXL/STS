from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import BACKEND_DIR, get_settings
from app.models.uploaded_file import UploadedFile
from app.models.user import User
from app.schemas.uploaded_file import UploadedFileResponse

ALLOWED_CONTENT_TYPES = {
    "application/json",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/csv",
    "text/plain",
}
ALLOWED_BUSINESS_TYPES = {"general", "strategy", "backtest", "forum", "custom_block"}
ALLOWED_VISIBILITIES = {"private", "public"}


def upload_root() -> Path:
    settings = get_settings()
    root = Path(settings.upload_dir)
    if not root.is_absolute():
        root = BACKEND_DIR / root
    return root


def uploaded_file_to_response(file_record: UploadedFile) -> UploadedFileResponse:
    return UploadedFileResponse(
        id=file_record.id,
        ownerId=file_record.owner_id,
        originalName=file_record.original_name,
        contentType=file_record.content_type,
        size=file_record.size,
        businessType=file_record.business_type,
        businessId=file_record.business_id,
        visibility=file_record.visibility,
        createdAt=file_record.created_at,
        downloadUrl=f"/api/files/{file_record.id}/download",
    )


def create_uploaded_file(
    db: Session,
    owner: User,
    upload: UploadFile,
    *,
    business_type: str = "general",
    business_id: int | None = None,
    visibility: str = "private",
) -> UploadedFileResponse:
    filename = sanitize_filename(upload.filename or "")
    if not filename:
        raise ValueError("文件名不能为空")

    business_type = normalize_choice(business_type, ALLOWED_BUSINESS_TYPES, "general")
    visibility = normalize_choice(visibility, ALLOWED_VISIBILITIES, "private")
    content_type = upload.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("暂不支持这种文件类型")

    content = upload.file.read()
    max_size = get_settings().upload_max_size_mb * 1024 * 1024
    if len(content) <= 0:
        raise ValueError("不能上传空文件")
    if len(content) > max_size:
        raise ValueError(f"文件不能超过 {get_settings().upload_max_size_mb}MB")

    root = upload_root()
    root.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{Path(filename).suffix.lower()}"
    storage_path = root / stored_name
    storage_path.write_bytes(content)

    file_record = UploadedFile(
        owner_id=owner.id,
        original_name=filename,
        stored_name=stored_name,
        storage_path=str(storage_path),
        content_type=content_type,
        size=len(content),
        business_type=business_type,
        business_id=business_id,
        visibility=visibility,
    )
    db.add(file_record)
    try:
        db.commit()
    except Exception:
        storage_path.unlink(missing_ok=True)
        raise

    db.refresh(file_record)
    return uploaded_file_to_response(file_record)


def list_uploaded_files(
    db: Session,
    owner: User,
    *,
    keyword: str = "",
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[UploadedFileResponse], int]:
    statement = _owned_file_statement(owner)
    keyword = keyword.strip()
    if keyword:
        like_keyword = f"%{keyword}%"
        statement = statement.where(
            or_(
                UploadedFile.original_name.like(like_keyword),
                UploadedFile.content_type.like(like_keyword),
                UploadedFile.business_type.like(like_keyword),
            )
        )

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    file_records = db.scalars(
        statement.order_by(UploadedFile.created_at.desc(), UploadedFile.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [uploaded_file_to_response(file_record) for file_record in file_records], total


def get_owned_uploaded_file(db: Session, owner: User, file_id: int) -> UploadedFile | None:
    return db.scalar(_owned_file_statement(owner).where(UploadedFile.id == file_id))


def delete_uploaded_file(db: Session, owner: User, file_id: int) -> bool:
    file_record = get_owned_uploaded_file(db, owner, file_id)
    if file_record is None:
        return False

    storage_path = Path(file_record.storage_path)
    db.delete(file_record)
    db.commit()
    storage_path.unlink(missing_ok=True)
    return True


def resolve_download_path(file_record: UploadedFile) -> Path:
    path = Path(file_record.storage_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError
    return path


def sanitize_filename(filename: str) -> str:
    safe_name = Path(filename).name.strip()
    return "".join(
        character if character not in {"\\", "/", "\0"} else "_" for character in safe_name
    )


def normalize_choice(value: str, allowed_values: set[str], default: str) -> str:
    normalized = value.strip().lower()
    return normalized if normalized in allowed_values else default


def _owned_file_statement(owner: User) -> Select[tuple[UploadedFile]]:
    return select(UploadedFile).where(UploadedFile.owner_id == owner.id)
