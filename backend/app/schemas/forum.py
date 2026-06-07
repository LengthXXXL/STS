from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ForumPostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=3000)
    topic: str = Field(default="交流", min_length=1, max_length=40)
    shared_block_id: int | None = Field(default=None, alias="sharedBlockId")

    model_config = ConfigDict(populate_by_name=True)


class ForumCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1200)


class ForumCommentResponse(BaseModel):
    id: int
    post_id: int = Field(alias="postId")
    author_id: int = Field(alias="authorId")
    author_name: str = Field(alias="authorName")
    content: str
    review_status: str = Field(alias="reviewStatus")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class ForumPostItemResponse(BaseModel):
    id: int
    author_id: int = Field(alias="authorId")
    author_name: str = Field(alias="authorName")
    title: str
    content: str
    topic: str
    shared_block_id: int | None = Field(alias="sharedBlockId")
    review_status: str = Field(alias="reviewStatus")
    comment_count: int = Field(alias="commentCount")
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
