from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ForumRelatedType = Literal["strategy", "backtest", "custom_block", "shared_block"]


class ForumPostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=3000)
    topic: str = Field(default="交流", min_length=1, max_length=40)
    shared_block_id: int | None = Field(default=None, alias="sharedBlockId")
    related_type: ForumRelatedType | None = Field(default=None, alias="relatedType")
    related_id: int | None = Field(default=None, alias="relatedId", ge=1)
    attachment_file_ids: list[int] = Field(
        default_factory=list,
        alias="attachmentFileIds",
        max_length=5,
    )

    model_config = ConfigDict(populate_by_name=True)


class ForumCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1200)


class ForumReviewDecisionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class ForumCommentResponse(BaseModel):
    id: int
    post_id: int = Field(alias="postId")
    author_id: int = Field(alias="authorId")
    author_name: str = Field(alias="authorName")
    content: str
    review_status: str = Field(alias="reviewStatus")
    review_reason: str | None = Field(default=None, alias="reviewReason")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class ForumCommentReviewResponse(ForumCommentResponse):
    post_title: str = Field(alias="postTitle")


class ForumAttachmentResponse(BaseModel):
    id: int
    file_id: int = Field(alias="fileId")
    original_name: str = Field(alias="originalName")
    content_type: str = Field(alias="contentType")
    size: int
    download_url: str = Field(alias="downloadUrl")

    model_config = ConfigDict(populate_by_name=True)


class ForumPostItemResponse(BaseModel):
    id: int
    author_id: int = Field(alias="authorId")
    author_name: str = Field(alias="authorName")
    title: str
    content: str
    topic: str
    shared_block_id: int | None = Field(alias="sharedBlockId")
    related_type: ForumRelatedType | None = Field(default=None, alias="relatedType")
    related_id: int | None = Field(default=None, alias="relatedId")
    related_title: str | None = Field(default=None, alias="relatedTitle")
    related_summary: str | None = Field(default=None, alias="relatedSummary")
    review_status: str = Field(alias="reviewStatus")
    review_reason: str | None = Field(default=None, alias="reviewReason")
    attachments: list[ForumAttachmentResponse] = Field(default_factory=list)
    comment_count: int = Field(alias="commentCount")
    like_count: int = Field(alias="likeCount")
    favorite_count: int = Field(alias="favoriteCount")
    is_liked: bool = Field(default=False, alias="isLiked")
    is_favorited: bool = Field(default=False, alias="isFavorited")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class ForumPostDetailResponse(ForumPostItemResponse):
    comments: list[ForumCommentResponse]


class ForumPostListResponse(BaseModel):
    items: list[ForumPostItemResponse]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")

    model_config = ConfigDict(populate_by_name=True)


class ForumCommentReviewListResponse(BaseModel):
    items: list[ForumCommentReviewResponse]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")

    model_config = ConfigDict(populate_by_name=True)
