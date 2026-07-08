import hashlib
import hmac
import json
import tempfile
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.deps import get_current_admin, get_current_reviewer, get_db
from ..config import settings
from ..database import async_session
from ..models import Plugin, PluginVersion, User, WebhookEvent
from ..schemas.admin import (
    ArtifactFileResponse,
    ArtifactTreeResponse,
    LoginRequest,
    AdminStatsResponse,
    ConfigUpdate,
    PluginDetail,
    PluginCreateRequest,
    PluginListResponse,
    RepoInspectRequest,
    RepoInspectResponse,
    RepoResolveRequest,
    RepoResolveResponse,
    PublishVersionRequest,
    PluginStatusUpdate,
    PluginSubmitResponse,
    PluginSummary,
    SetLatestRequest,
    StatusResponse,
    TaskRetryResponse,
    TokenResponse,
    UserCreate,
    UserResponse,
    VersionCreate,
    VersionSubmitResponse,
    VersionSummary,
    VersionStatusUpdate,
    WorkerStatusResponse,
    WorkerTaskListResponse,
    WorkerTaskSummary,
)
from ..services.auth_service import authenticate_user, create_access_token, get_password_hash
from ..services.artifact_service import ArtifactError, list_artifact_tree, read_artifact_file
from ..services.build_service import build_from_repo
from ..services.config_service import list_config_response, update_config
from ..services.plugin_service import (
    create_plugin,
    create_version_from_upload,
    delete_plugin,
    delete_version,
    get_plugin,
    get_plugin_with_details,
    list_plugins,
    list_versions,
    publish_plugin_version,
    set_latest_version,
    set_plugin_status,
    set_version_status,
    update_plugin,
)
from ..services.registry_service import refresh_cache
from ..services.repo_inspection_service import inspect_git_repo, resolve_git_ref
from ..services.runtime_config import (
    runtime_git_allowed_hosts,
    runtime_git_http_proxy,
    runtime_git_preflight_timeout,
    runtime_scan_enabled_providers,
    runtime_upload_limits,
    runtime_webhook_auto_version,
    runtime_webhook_secret,
)
from ..services.scan_service import (
    mark_scan_pending,
    mark_scan_skipped,
    scan_version,
    version_scan_summary,
)
from ..services.scan_providers import get_scan_provider_registry
from ..services.security_service import login_rate_limit_keys, login_rate_limiter
from ..services.submit_service import submit_repo
from ..services.task_observability import (
    get_worker_task,
    list_worker_tasks,
    task_to_dict,
    worker_runtime_status,
)
from ..services.task_queue import enqueue_task
from ..utils.git_utils import GitError, parse_github_url
from ..utils.metadata_parser import parse_metadata_yaml
from ..utils.zip_utils import (
    ZipValidationError,
    find_metadata_yaml,
    inspect_zip,
    safe_unzip,
)

admin_router = APIRouter(prefix="/admin", tags=["admin"])


def _version_summary(version, required_scan_providers: list[str] | None = None) -> dict:
    scan = version_scan_summary(version)
    if scan is not None and required_scan_providers is not None:
        scan["required_providers"] = required_scan_providers
    return {
        "id": str(version.id),
        "version": version.version,
        "source_type": version.source_type,
        "source_ref": version.source_ref,
        "commit_sha": version.commit_sha,
        "changelog": version.changelog,
        "build_status": version.build_status,
        "build_log": version.build_log,
        "version_status": version.version_status,
        "is_latest": version.is_latest,
        "download_url": version.download_url,
        "file_size": version.file_size,
        "created_at": version.created_at,
        "updated_at": version.updated_at,
        "scan": scan,
    }


def _plugin_summary(plugin) -> dict:
    return {
        "id": str(plugin.id),
        "plugin_key": plugin.plugin_key,
        "display_name": plugin.display_name,
        "author": plugin.author,
        "status": plugin.status,
        "review_status": plugin.review_status,
        "category": plugin.category,
        "version_count": len(plugin.versions),
        "created_at": plugin.created_at,
        "updated_at": plugin.updated_at,
    }


async def _build_version_task(
    plugin_id: str,
    version: str | None,
    ref: str | None,
    credential_id: str | None,
    temporary_token: str | None,
    changelog: str,
    user_id: str,
) -> None:
    async with async_session() as db:
        plugin = await get_plugin(db, uuid.UUID(plugin_id))
        if plugin is None:
            return
        await build_from_repo(
            db,
            plugin,
            version,
            ref=ref,
            credential_id=credential_id,
            temporary_token=temporary_token,
            changelog=changelog,
            created_by=user_id,
        )


async def _scan_version_task(version_id: str, providers: list[str] | None = None) -> None:
    async with async_session() as db:
        await scan_version(db, uuid.UUID(version_id), providers=providers)


async def _submit_repo_task(
    repo_url: str,
    version: str | None,
    ref: str | None,
    credential_id: str | None,
    temporary_token: str | None,
    changelog: str,
    user_id: str,
) -> None:
    async with async_session() as db:
        await submit_repo(
            db,
            repo_url=repo_url,
            version=version,
            ref=ref,
            credential_id=credential_id,
            temporary_token=temporary_token,
            changelog=changelog,
            user_id=user_id,
        )


async def _enqueue_or_fallback(
    background_tasks: BackgroundTasks,
    task_type: str,
    payload: dict,
    db: AsyncSession,
) -> None:
    queued = await enqueue_task(task_type, payload, db=db)
    if queued:
        return
    if task_type == "build":
        background_tasks.add_task(
            _build_version_task,
            payload["plugin_id"],
            payload["version"],
            payload.get("ref"),
            payload.get("credential_id"),
            payload.get("temporary_token"),
            payload.get("changelog", ""),
            payload.get("user_id", ""),
        )
    elif task_type == "scan":
        background_tasks.add_task(_scan_version_task, payload["version_id"], payload.get("providers"))
    elif task_type == "submit":
        background_tasks.add_task(
            _submit_repo_task,
            payload["repo_url"],
            payload.get("version"),
            payload.get("ref"),
            payload.get("credential_id"),
            payload.get("temporary_token"),
            payload.get("changelog", ""),
            payload.get("user_id", ""),
        )


async def _process_uploaded_zip(
    file: UploadFile,
    workdir: Path,
    db: AsyncSession,
) -> tuple:
    limits = await runtime_upload_limits(db)
    zip_path = workdir / "upload.zip"
    total = 0
    with open(zip_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > limits["max_upload_bytes"]:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Uploaded zip is too large",
                )
            f.write(chunk)

    try:
        inspect_zip(
            zip_path,
            max_total_uncompressed_bytes=limits["max_unzip_bytes"],
            max_file_count=limits["max_zip_entries"],
            max_single_file_bytes=limits["max_single_file_bytes"],
        )
    except ZipValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    extract_dir = workdir / "extracted"
    extract_dir.mkdir()
    try:
        safe_unzip(zip_path, extract_dir)
        metadata = parse_metadata_yaml(find_metadata_yaml(extract_dir))
    except ZipValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return metadata, zip_path


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    user = User(
        username=data.username,
        password_hash=get_password_hash(data.password),
        role=data.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@admin_router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    rate_limit_keys = login_rate_limit_keys(request, data.username)
    if settings.login_rate_limit_enabled:
        retry_after = max(login_rate_limiter.retry_after(key) for key in rate_limit_keys)
        if retry_after > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts",
                headers={"Retry-After": str(retry_after)},
            )

    user = await authenticate_user(db, data.username, data.password)
    if user is None:
        if settings.login_rate_limit_enabled:
            for key in rate_limit_keys:
                login_rate_limiter.record_failure(key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if settings.login_rate_limit_enabled:
        for key in rate_limit_keys:
            login_rate_limiter.record_success(key)
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}


@admin_router.post("/bootstrap", response_model=UserResponse)
async def bootstrap_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not settings.bootstrap_api_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bootstrap API is disabled",
        )
    count = await db.scalar(select(func.count(User.id)))
    if count and count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bootstrap already completed",
        )
    user = await create_user(db, data)
    return {"id": str(user.id), "username": user.username, "role": user.role}


@admin_router.post("/users", response_model=UserResponse)
async def create_user_endpoint(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    user = await create_user(db, data)
    return {"id": str(user.id), "username": user.username, "role": user.role}


@admin_router.get("/plugins", response_model=PluginListResponse)
async def list_plugins_endpoint(
    status: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    plugins, total = await list_plugins(db, status=status, q=q, page=page, page_size=page_size)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    return {
        "items": [_plugin_summary(plugin) for plugin in plugins],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@admin_router.post("/plugins/inspect-repo", response_model=RepoInspectResponse)
async def inspect_plugin_repo_endpoint(
    request: RepoInspectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    try:
        git_allowed_hosts = await runtime_git_allowed_hosts(db)
        git_http_proxy = await runtime_git_http_proxy(db)
        git_preflight_timeout = await runtime_git_preflight_timeout(db)
        return await inspect_git_repo(
            db,
            repo_url=request.repo_url,
            temporary_token=request.temporary_token,
            credential_id=request.credential_id,
            ref_type=request.ref_type,
            ref=request.ref,
            include_refs=request.include_refs,
            allowed_hosts=git_allowed_hosts,
            proxy_url=git_http_proxy,
            timeout=git_preflight_timeout,
        )
    except (ValueError, GitError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/plugins/resolve-ref", response_model=RepoResolveResponse)
async def resolve_plugin_ref_endpoint(
    request: RepoResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    try:
        git_allowed_hosts = await runtime_git_allowed_hosts(db)
        git_http_proxy = await runtime_git_http_proxy(db)
        git_preflight_timeout = await runtime_git_preflight_timeout(db)
        return await resolve_git_ref(
            db,
            repo_url=request.repo_url,
            temporary_token=request.temporary_token,
            credential_id=request.credential_id,
            ref_type=request.ref_type,
            ref=request.ref,
            allowed_hosts=git_allowed_hosts,
            proxy_url=git_http_proxy,
            timeout=git_preflight_timeout,
        )
    except (ValueError, GitError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.post("/plugins", response_model=PluginSubmitResponse)
async def submit_plugin(
    request: PluginCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    try:
        git_allowed_hosts = await runtime_git_allowed_hosts(db)
        parse_github_url(request.repo_url, allowed_hosts=git_allowed_hosts)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await _enqueue_or_fallback(
        background_tasks,
        "submit",
        {
            "repo_url": request.repo_url,
            "version": request.version,
            "ref": request.ref,
            "credential_id": request.credential_id,
            "temporary_token": request.temporary_token,
            "changelog": request.changelog,
            "user_id": str(current_user.id),
        },
        db,
    )
    return {"plugin_id": None, "version": request.version, "status": "queued"}


@admin_router.post("/plugins/upload", response_model=VersionSubmitResponse)
async def upload_plugin(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        metadata, zip_path = await _process_uploaded_zip(file, workdir, db)
        plugin = await create_plugin(
            db,
            metadata,
            repo_url=metadata.repo or "",
            created_by=current_user.id,
        )
        version = await create_version_from_upload(
            db,
            plugin,
            metadata,
            zip_path,
            metadata.version,
            created_by=current_user.id,
        )
        await _enqueue_or_fallback(
            background_tasks,
            "scan",
            {"version_id": str(version.id)},
            db,
        )
    return {"plugin_id": str(plugin.id), "version_id": str(version.id)}


@admin_router.get("/plugins/pending", response_model=list[PluginSummary])
async def pending_plugins(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> list:
    plugins, _ = await list_plugins(db, status="pending", page=1, page_size=100)
    return [_plugin_summary(plugin) for plugin in plugins]


@admin_router.get("/plugins/{plugin_id}", response_model=PluginDetail)
async def get_plugin_endpoint(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    plugin = await get_plugin_with_details(db, uuid.UUID(plugin_id))
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    required_scan_providers = await runtime_scan_enabled_providers(db)
    return {
        **_plugin_summary(plugin),
        "description": plugin.description,
        "repo_url": plugin.repo_url,
        "social_link": plugin.social_link,
        "tags": [tag.name for tag in plugin.tags],
        "support_platforms": plugin.support_platforms or [],
        "astrbot_version": plugin.astrbot_version,
        "versions": [_version_summary(version, required_scan_providers) for version in plugin.versions],
    }


@admin_router.put("/plugins/{plugin_id}", response_model=dict)
async def update_plugin_endpoint(
    plugin_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    from ..schemas.plugin import PluginUpdate

    plugin = await get_plugin(db, uuid.UUID(plugin_id))
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    updated = await update_plugin(db, plugin, PluginUpdate(**data))
    return {"plugin_id": str(updated.id), "plugin_key": updated.plugin_key}


@admin_router.delete("/plugins/{plugin_id}", response_model=StatusResponse)
async def delete_plugin_endpoint(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    await delete_plugin(db, uuid.UUID(plugin_id))
    return {"status": "deleted"}


@admin_router.get("/plugins/{plugin_id}/versions", response_model=list[VersionSummary])
async def list_versions_endpoint(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> list:
    versions = await list_versions(db, uuid.UUID(plugin_id))
    required_scan_providers = await runtime_scan_enabled_providers(db)
    return [_version_summary(v, required_scan_providers) for v in versions]


@admin_router.delete("/plugins/{plugin_id}/versions/{version_id}", response_model=StatusResponse)
async def delete_version_endpoint(
    plugin_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    await delete_version(db, uuid.UUID(plugin_id), uuid.UUID(version_id))
    return {"status": "deleted"}


@admin_router.post("/plugins/{plugin_id}/versions", response_model=VersionSubmitResponse)
async def create_version_from_repo(
    plugin_id: str,
    request: VersionCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    plugin = await get_plugin(db, uuid.UUID(plugin_id))
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    await _enqueue_or_fallback(
        background_tasks,
        "build",
        {
            "plugin_id": plugin_id,
            "version": request.version,
            "ref": request.ref,
            "credential_id": request.credential_id,
            "temporary_token": request.temporary_token,
            "changelog": request.changelog,
            "user_id": str(current_user.id),
        },
        db,
    )
    return {"plugin_id": plugin_id, "version": request.version, "status": "queued"}


@admin_router.post("/plugins/{plugin_id}/versions/upload", response_model=VersionSubmitResponse)
async def upload_version(
    plugin_id: str,
    background_tasks: BackgroundTasks,
    version: str = Form(...),
    changelog: str = Form(""),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    plugin = await get_plugin(db, uuid.UUID(plugin_id))
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        metadata, zip_path = await _process_uploaded_zip(file, workdir, db)
        version_str = version or metadata.version
        pv = await create_version_from_upload(
            db,
            plugin,
            metadata,
            zip_path,
            version_str,
            changelog,
            created_by=current_user.id,
        )
        await _enqueue_or_fallback(background_tasks, "scan", {"version_id": str(pv.id)}, db)
    return {"version_id": str(pv.id)}


@admin_router.put("/plugins/{plugin_id}/versions/{version_id}/latest", response_model=StatusResponse)
async def set_latest(
    plugin_id: str,
    version_id: str,
    request: SetLatestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    if not request.is_latest:
        raise HTTPException(status_code=400, detail="Setting is_latest=false is not supported")
    await set_latest_version(db, uuid.UUID(plugin_id), uuid.UUID(version_id))
    return {"status": "updated"}


@admin_router.post("/plugins/{plugin_id}/versions/{version_id}/publish", response_model=StatusResponse)
async def publish_version(
    plugin_id: str,
    version_id: str,
    request: PublishVersionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    await publish_plugin_version(
        db,
        uuid.UUID(plugin_id),
        uuid.UUID(version_id),
        review_status=request.review_status,
    )
    return {"status": "published"}


@admin_router.get(
    "/plugins/{plugin_id}/versions/{version_id}/artifact/tree",
    response_model=ArtifactTreeResponse,
)
async def artifact_tree(
    plugin_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    version = await _get_plugin_version(db, plugin_id, version_id)
    try:
        return await list_artifact_tree(version)
    except ArtifactError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@admin_router.get(
    "/plugins/{plugin_id}/versions/{version_id}/artifact/file",
    response_model=ArtifactFileResponse,
)
async def artifact_file(
    plugin_id: str,
    version_id: str,
    path: str = Query(..., min_length=1, max_length=512),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    version = await _get_plugin_version(db, plugin_id, version_id)
    try:
        return await read_artifact_file(version, path)
    except ArtifactError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _get_plugin_version(db: AsyncSession, plugin_id: str, version_id: str) -> PluginVersion:
    version = await db.scalar(
        select(PluginVersion).where(
            PluginVersion.id == uuid.UUID(version_id),
            PluginVersion.plugin_id == uuid.UUID(plugin_id),
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@admin_router.put("/plugins/{plugin_id}/versions/{version_id}/status", response_model=StatusResponse)
async def update_version_status(
    plugin_id: str,
    version_id: str,
    request: VersionStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    await set_version_status(db, uuid.UUID(version_id), request.status)
    return {"status": "updated"}


@admin_router.post("/plugins/{plugin_id}/build", response_model=StatusResponse)
async def trigger_build(
    plugin_id: str,
    request: VersionCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    plugin = await get_plugin(db, uuid.UUID(plugin_id))
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    await _enqueue_or_fallback(
        background_tasks,
        "build",
        {
            "plugin_id": plugin_id,
            "version": request.version,
            "ref": request.ref,
            "credential_id": request.credential_id,
            "temporary_token": request.temporary_token,
            "changelog": request.changelog,
            "user_id": str(current_user.id),
        },
        db,
    )
    return {"status": "queued"}


@admin_router.post("/plugins/{plugin_id}/scan", response_model=StatusResponse)
async def trigger_scan(
    plugin_id: str,
    version_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    providers = await runtime_scan_enabled_providers(db)
    await mark_scan_pending(db, uuid.UUID(version_id), providers=providers)
    await _enqueue_or_fallback(background_tasks, "scan", {"version_id": version_id, "providers": providers}, db)
    return {"status": "queued"}


@admin_router.post("/plugins/{plugin_id}/versions/{version_id}/scans/{provider}/run", response_model=StatusResponse)
async def trigger_scan_provider(
    plugin_id: str,
    version_id: str,
    provider: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    providers = await _scan_providers(db, provider)
    await mark_scan_pending(db, uuid.UUID(version_id), providers=providers)
    await _enqueue_or_fallback(background_tasks, "scan", {"version_id": version_id, "providers": providers}, db)
    return {"status": "queued"}


@admin_router.post("/plugins/{plugin_id}/versions/{version_id}/scans/{provider}/skip", response_model=StatusResponse)
async def skip_scan_provider(
    plugin_id: str,
    version_id: str,
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    await mark_scan_skipped(db, uuid.UUID(version_id), providers=await _scan_providers(db, provider))
    return {"status": "skipped"}


async def _scan_providers(db: AsyncSession, provider: str) -> list[str]:
    if provider == "all":
        return await runtime_scan_enabled_providers(db)
    if provider in get_scan_provider_registry().names:
        return [provider]
    raise HTTPException(status_code=400, detail="Invalid scan provider")


@admin_router.put("/plugins/{plugin_id}/status", response_model=StatusResponse)
async def update_plugin_status(
    plugin_id: str,
    request: PluginStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    await set_plugin_status(db, uuid.UUID(plugin_id), request.status, review_status=request.review_status)
    return {"status": "updated"}


@admin_router.get("/stats", response_model=AdminStatsResponse)
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    total = await db.scalar(select(func.count(Plugin.id)))
    pending = await db.scalar(
        select(func.count(Plugin.id)).where(Plugin.status == "pending")
    )
    return {"total_plugins": total or 0, "pending_plugins": pending or 0}


@admin_router.get("/tasks", response_model=WorkerTaskListResponse)
async def list_tasks_endpoint(
    status: str | None = None,
    task_type: str | None = Query(None, alias="type"),
    plugin_id: str | None = None,
    version_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    tasks, total = await list_worker_tasks(
        db,
        status=status,
        task_type=task_type,
        plugin_id=plugin_id,
        version_id=version_id,
        page=page,
        page_size=page_size,
    )
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    return {
        "items": [task_to_dict(task) for task in tasks],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@admin_router.get("/tasks/{task_id}", response_model=WorkerTaskSummary)
async def get_task_endpoint(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    task = await get_worker_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_to_dict(task)


@admin_router.post("/tasks/{task_id}/retry", response_model=TaskRetryResponse)
async def retry_task_endpoint(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    task = await get_worker_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status == "running":
        raise HTTPException(status_code=409, detail="Running tasks cannot be retried")
    new_task_id = await enqueue_task(task.task_type, task.payload or {}, db=db)
    if new_task_id is None:
        raise HTTPException(status_code=503, detail="Redis task queue is unavailable")
    return {"status": "queued", "task_id": new_task_id}


@admin_router.get("/worker/status", response_model=WorkerStatusResponse)
async def worker_status_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    return await worker_runtime_status(db)


@admin_router.get("/config")
async def get_config_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    return await list_config_response(db)


@admin_router.put("/config")
async def update_config_endpoint(
    request: ConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    return await update_config(db, request.values)


@admin_router.post("/cache/refresh", response_model=StatusResponse)
async def refresh_cache_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    await refresh_cache(db)
    return {"status": "refreshed"}


@admin_router.post("/webhooks/github", response_model=StatusResponse)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    body = await request.body()
    async with async_session() as db:
        webhook_secret = await runtime_webhook_secret(db)
        webhook_auto_version = await runtime_webhook_auto_version(db)

    if settings.github_webhook_require_secret and not webhook_secret:
        raise HTTPException(status_code=503, detail="GitHub webhook secret is not configured")

    if webhook_secret:
        signature = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(
            webhook_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook payload") from exc

    repo_url = payload.get("repository", {}).get("html_url")
    ref = payload.get("ref", "").replace("refs/heads/", "")
    if not repo_url or not ref:
        async with async_session() as db:
            db.add(
                WebhookEvent(
                    event_type="push",
                    payload=payload,
                    status="ignored",
                    error_message="missing repository html_url or ref",
                )
            )
            await db.commit()
        return {"status": "ignored"}

    async with async_session() as db:
        result = await db.execute(select(Plugin).where(Plugin.repo_url == repo_url))
        plugin = result.scalar_one_or_none()

    if plugin is None:
        async with async_session() as db:
            db.add(
                WebhookEvent(
                    event_type="push",
                    payload=payload,
                    status="ignored",
                    error_message=f"repository is not registered: {repo_url}",
                )
            )
            await db.commit()
        return {"status": "ignored"}

    async with async_session() as db:
        db.add(
            WebhookEvent(
                plugin_id=plugin.id,
                event_type="push",
                payload=payload,
                status="success",
            )
        )
        await db.commit()

    # We do not know the version from a push event; the build task will read metadata.yaml.
    async with async_session() as db:
        await _enqueue_or_fallback(
            background_tasks,
            "build",
            {
                "plugin_id": str(plugin.id),
                "version": webhook_auto_version,
                "ref": ref,
                "changelog": "",
                "user_id": "",
            },
            db,
        )
    return {"status": "queued"}
