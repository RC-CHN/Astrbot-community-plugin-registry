"""Pydantic request/response schemas."""

from .admin import (
    LoginRequest,
    PluginCreateRequest,
    PluginStatusUpdate,
    SetLatestRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    VersionCreate,
    VersionStatusUpdate,
)
from .plugin import PluginCreate, PluginUpdate
from .registry import RegistryEntry, ScanResult

__all__ = [
    "LoginRequest",
    "PluginCreateRequest",
    "PluginStatusUpdate",
    "SetLatestRequest",
    "TokenResponse",
    "UserCreate",
    "UserResponse",
    "VersionCreate",
    "VersionStatusUpdate",
    "PluginCreate",
    "PluginUpdate",
    "RegistryEntry",
    "ScanResult",
]
