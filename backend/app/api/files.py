from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.uploaded_file import UploadedFileListResponse, UploadedFileResponse
from app.services.file_service import (
    create_uploaded_file,
    delete_uploaded_file,
    get_owned_uploaded_file,
    list_uploaded_files,
    resolve_download_path,
)

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", response_model=UploadedFileResponse, status_code=status.HTTP_201_CREATED)
def upload(
    file: UploadFile = File(...),
    business_type: str = Form(default="general", alias="businessType"),
    business_id: int | None = Form(default=None, alias="businessId"),
    visibility: str = Form(default="private"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadedFileResponse:
    try:
        return create_uploaded_file(
            db,
            current_user,
            file,
            business_type=business_type,
            business_id=business_id,
            visibility=visibility,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=UploadedFileListResponse)
def list_current_user_files(
    keyword: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, alias="pageSize", ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadedFileListResponse:
    items, total = list_uploaded_files(
        db,
        current_user,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return UploadedFileListResponse(items=items, total=total, page=page, pageSize=page_size)


@router.get("/{file_id}/download")
def download(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    file_record = get_owned_uploaded_file(db, current_user, file_id)
    if file_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    try:
        path = resolve_download_path(file_record)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File content not found",
        ) from exc
    return FileResponse(
        path,
        filename=file_record.original_name,
        media_type=file_record.content_type,
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    deleted = delete_uploaded_file(db, current_user, file_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
