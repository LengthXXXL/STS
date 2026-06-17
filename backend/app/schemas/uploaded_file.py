from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UploadedFileResponse(BaseModel):
    id: int
    owner_id: int = Field(alias="ownerId")
    original_name: str = Field(alias="originalName")
    content_type: str = Field(alias="contentType")
    size: int
    business_type: str = Field(alias="businessType")
    business_id: int | None = Field(alias="businessId")
    visibility: str
    created_at: datetime = Field(alias="createdAt")
    download_url: str = Field(alias="downloadUrl")

    model_config = ConfigDict(populate_by_name=True)


class UploadedFileListResponse(BaseModel):
    items: list[UploadedFileResponse]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")

    model_config = ConfigDict(populate_by_name=True)
