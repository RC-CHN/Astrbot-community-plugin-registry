"""Registry output schemas matching the official AstrBot source format."""

from pydantic import BaseModel, Field


class ScanResult(BaseModel):
    pass_: bool = Field(..., alias="pass")
    msg: str


class RegistryEntry(BaseModel):
    name: str | None = None
    display_name: str | None = None
    desc: str
    short_desc: str = ""
    author: str
    repo: str | None = None
    tags: list[str]
    tag: list[str] = []
    social_link: str | None = None
    stars: int
    pinned: bool = False
    version: str
    updated_at: str
    logo: str
    commit_sha: str | None = None
    download_url: str
    sec_scan: dict[str, ScanResult]
    i18n: dict
    astrbot_version: str | None = None
    support_platforms: list[str]
    category: str | None = None
