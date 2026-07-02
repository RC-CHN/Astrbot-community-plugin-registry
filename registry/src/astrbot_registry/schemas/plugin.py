"""Plugin-related Pydantic schemas."""

from pydantic import BaseModel, Field, HttpUrl


class PluginBase(BaseModel):
    plugin_key: str = Field(..., max_length=255)
    display_name: str | None = Field(None, max_length=255)
    description: str
    author: str = Field(..., max_length=255)
    repo_url: HttpUrl
    social_link: HttpUrl | None = None
    category: str | None = Field(None, max_length=100)
    tags: list[str] = []
    support_platforms: list[str] = []
    astrbot_version: str | None = Field(None, max_length=100)


class PluginCreate(PluginBase):
    pass


class PluginUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=255)
    description: str | None = None
    category: str | None = Field(None, max_length=100)
    tags: list[str] | None = None
    support_platforms: list[str] | None = None
    astrbot_version: str | None = Field(None, max_length=100)
