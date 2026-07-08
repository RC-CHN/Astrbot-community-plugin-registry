"""Plugin submission request schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SubmissionStatus = Literal["pending_review", "accepted", "rejected", "duplicate"]
SubmissionRefType = Literal["default", "branch", "tag", "commit"]


class SubmissionCreate(BaseModel):
    repo_url: str = Field(..., min_length=1, max_length=512)
    ref_type: SubmissionRefType = "default"
    ref: str | None = Field(default=None, max_length=255)
    user_message: str | None = Field(default=None, max_length=4000)


class SubmissionDecisionRequest(BaseModel):
    admin_message: str | None = Field(default=None, max_length=4000)


class SubmissionResponse(BaseModel):
    id: str
    user_id: str
    username: str | None = None
    repo_url: str
    provider: str
    ref_type: SubmissionRefType
    ref: str | None = None
    status: SubmissionStatus
    resolved_commit_sha: str | None = None
    accepted_plugin_id: str | None = None
    accepted_version_id: str | None = None
    user_message: str | None = None
    admin_message: str | None = None
    accepted_by: str | None = None
    accepted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SubmissionListResponse(BaseModel):
    items: list[SubmissionResponse]
    total: int
