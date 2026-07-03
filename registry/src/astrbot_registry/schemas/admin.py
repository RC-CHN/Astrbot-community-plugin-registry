"""Admin-related Pydantic schemas."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str = Field(..., max_length=100)
    password: str
    role: str = "reviewer"


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
    status: str


class PluginStatusUpdate(BaseModel):
    status: str


class SetLatestRequest(BaseModel):
    is_latest: bool = True
