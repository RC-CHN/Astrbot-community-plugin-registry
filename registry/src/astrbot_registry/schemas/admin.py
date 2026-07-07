"""Admin-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field
from typing import Literal


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=1024)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str = Field(..., max_length=100)
    password: str = Field(..., min_length=12, max_length=1024)
    role: Literal["admin", "reviewer"] = "reviewer"


class UserResponse(BaseModel):
    id: str
    username: str
    role: str


class PluginCreateRequest(BaseModel):
    repo_url: str
    version: str | None = None
    ref: str | None = None
    changelog: str = ""


class VersionCreate(BaseModel):
    version: str
    changelog: str = ""
    ref: str | None = None


class VersionStatusUpdate(BaseModel):
    status: Literal["draft", "active", "deprecated", "deleted"]


class PluginStatusUpdate(BaseModel):
    status: Literal["pending", "active", "disabled", "deleted"]
    review_status: Literal["pending", "approved", "skipped", "rejected"] | None = None


class SetLatestRequest(BaseModel):
    is_latest: bool = True


class PublishVersionRequest(BaseModel):
    review_status: Literal["approved", "skipped"] = "approved"


class ConfigUpdate(BaseModel):
    values: dict[str, str]


class StatusResponse(BaseModel):
    status: str


class PluginSubmitResponse(BaseModel):
    plugin_id: str | None = None
    version: str | None = None
    status: str


class VersionSubmitResponse(BaseModel):
    plugin_id: str | None = None
    version_id: str | None = None
    version: str | None = None
    status: str | None = None


class PluginSummary(BaseModel):
    id: str
    plugin_key: str
    display_name: str | None
    author: str
    status: str
    review_status: str = "pending"
    category: str | None = None
    version_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PluginListResponse(BaseModel):
    items: list[PluginSummary]
    total: int
    page: int
    page_size: int


class VersionSummary(BaseModel):
    id: str
    version: str
    source_type: str
    commit_sha: str | None = None
    build_status: str
    build_log: str | None = None
    version_status: str
    is_latest: bool
    download_url: str | None = None
    file_size: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    scan: dict | None = None


class ArtifactTreeEntry(BaseModel):
    path: str
    name: str
    kind: Literal["dir", "file"]
    size: int | None = None


class ArtifactTreeResponse(BaseModel):
    entries: list[ArtifactTreeEntry]


class ArtifactFileResponse(BaseModel):
    path: str
    name: str
    size: int
    language: str
    content: str | None = None
    truncated: bool = False
    binary: bool = False


class PluginDetail(PluginSummary):
    description: str
    repo_url: str | None = None
    social_link: str | None = None
    tags: list[str] = []
    support_platforms: list[str] = []
    astrbot_version: str | None = None
    versions: list[VersionSummary] = []


class AdminStatsResponse(BaseModel):
    total_plugins: int
    pending_plugins: int
