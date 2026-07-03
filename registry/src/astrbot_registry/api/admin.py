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
    Request,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.deps import get_current_admin, get_current_reviewer, get_db
from ..config import settings
from ..database import async_session
from ..models import Plugin, User, WebhookEvent
from ..schemas.admin import (
    LoginRequest,
    PluginCreateRequest,
    PluginStatusUpdate,
    SetLatestRequest,
    TokenResponse,
    UserCreate,
    VersionCreate,
    VersionStatusUpdate,
)
from ..services.auth_service import authenticate_user, create_access_token, get_password_hash
from ..services.build_service import build_from_repo
from ..services.plugin_service import (
    create_plugin,
    create_version_from_upload,
    delete_plugin,
    get_plugin,
    list_versions,
    set_latest_version,
    set_plugin_status,
    set_version_status,
    update_plugin,
)
from ..services.registry_service import refresh_cache
from ..services.scan_service import scan_version
from ..services.task_queue import enqueue_task
from ..utils.git_utils import clone_repo, get_metadata_path, temp_repo_dir
from ..utils.metadata_parser import parse_metadata_yaml
from ..utils.zip_utils import (
    ZipValidationError,
    find_metadata_yaml,
    inspect_zip,
    safe_unzip,
)

admin_router = APIRouter(prefix="/admin", tags=["admin"])


async def _build_version_task(
    plugin_id: str,
    version: str,
    ref: str | None,
    user_id: str,
) -> None:
    async with async_session() as db:
        plugin = await get_plugin(db, uuid.UUID(plugin_id))
        if plugin is None:
            return
        await build_from_repo(db, plugin, version, ref=ref, created_by=user_id)


async def _scan_version_task(version_id: str) -> None:
    async with async_session() as db:
        await scan_version(db, uuid.UUID(version_id))


async def _enqueue_or_fallback(
    background_tasks: BackgroundTasks,
    task_type: str,
    payload: dict,
) -> None:
    queued = await enqueue_task(task_type, payload)
    if queued:
        return
    if task_type == "build":
        background_tasks.add_task(
            _build_version_task,
            payload["plugin_id"],
            payload["version"],
            payload.get("ref"),
            payload.get("user_id", ""),
        )
    elif task_type == "scan":
        background_tasks.add_task(_scan_version_task, payload["version_id"])


async def _process_uploaded_zip(
    file: UploadFile,
    workdir: Path,
) -> tuple:
    zip_path = workdir / (file.filename or "upload.zip")
    total = 0
    with open(zip_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > settings.max_upload_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Uploaded zip is too large",
                )
            f.write(chunk)

    try:
        inspect_zip(
            zip_path,
            max_total_uncompressed_bytes=settings.max_unzip_bytes,
            max_file_count=settings.max_zip_entries,
            max_single_file_bytes=settings.max_single_file_bytes,
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
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await authenticate_user(db, data.username, data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}


@admin_router.post("/bootstrap")
async def bootstrap_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    count = await db.scalar(select(func.count(User.id)))
    if count and count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bootstrap already completed",
        )
    user = await create_user(db, data)
    return {"id": str(user.id), "username": user.username, "role": user.role}


@admin_router.post("/users")
async def create_user_endpoint(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    user = await create_user(db, data)
    return {"id": str(user.id), "username": user.username, "role": user.role}


@admin_router.post("/plugins")
async def submit_plugin(
    request: PluginCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    with temp_repo_dir() as repo_dir:
        clone_repo(request.repo_url, repo_dir, ref=request.ref, timeout=settings.git_clone_timeout)
        metadata = parse_metadata_yaml(get_metadata_path(repo_dir))

    plugin = await create_plugin(
        db,
        metadata,
        request.repo_url,
        created_by=current_user.id,
    )
    version = request.version or metadata.version

    await _enqueue_or_fallback(
        background_tasks,
        "build",
        {
            "plugin_id": str(plugin.id),
            "version": version,
            "ref": request.ref,
            "user_id": str(current_user.id),
        },
    )
    return {"plugin_id": str(plugin.id), "version": version, "status": "queued"}


@admin_router.post("/plugins/upload")
async def upload_plugin(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        metadata, zip_path = await _process_uploaded_zip(file, workdir)
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
        )
    return {"plugin_id": str(plugin.id), "version_id": str(version.id)}


@admin_router.put("/plugins/{plugin_id}")
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


@admin_router.delete("/plugins/{plugin_id}")
async def delete_plugin_endpoint(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    await delete_plugin(db, uuid.UUID(plugin_id))
    return {"status": "deleted"}


@admin_router.get("/plugins/{plugin_id}/versions")
async def list_versions_endpoint(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> list:
    versions = await list_versions(db, uuid.UUID(plugin_id))
    return [
        {
            "id": str(v.id),
            "version": v.version,
            "source_type": v.source_type,
            "commit_sha": v.commit_sha,
            "build_status": v.build_status,
            "version_status": v.version_status,
            "is_latest": v.is_latest,
            "download_url": v.download_url,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]


@admin_router.post("/plugins/{plugin_id}/versions")
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
            "user_id": str(current_user.id),
        },
    )
    return {"plugin_id": plugin_id, "version": request.version, "status": "queued"}


@admin_router.post("/plugins/{plugin_id}/versions/upload")
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
        metadata, zip_path = await _process_uploaded_zip(file, workdir)
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
        await _enqueue_or_fallback(background_tasks, "scan", {"version_id": str(pv.id)})
    return {"version_id": str(pv.id)}


@admin_router.put("/plugins/{plugin_id}/versions/{version_id}/latest")
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


@admin_router.put("/plugins/{plugin_id}/versions/{version_id}/status")
async def update_version_status(
    plugin_id: str,
    version_id: str,
    request: VersionStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    await set_version_status(db, uuid.UUID(version_id), request.status)
    return {"status": "updated"}


@admin_router.post("/plugins/{plugin_id}/build")
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
            "user_id": str(current_user.id),
        },
    )
    return {"status": "queued"}


@admin_router.post("/plugins/{plugin_id}/scan")
async def trigger_scan(
    plugin_id: str,
    version_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> dict:
    await _enqueue_or_fallback(background_tasks, "scan", {"version_id": version_id})
    return {"status": "queued"}


@admin_router.put("/plugins/{plugin_id}/status")
async def update_plugin_status(
    plugin_id: str,
    request: PluginStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    await set_plugin_status(db, uuid.UUID(plugin_id), request.status)
    return {"status": "updated"}


@admin_router.get("/plugins/pending")
async def pending_plugins(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_reviewer),
) -> list:
    result = await db.execute(select(Plugin).where(Plugin.status == "pending"))
    plugins = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "plugin_key": p.plugin_key,
            "display_name": p.display_name,
            "author": p.author,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in plugins
    ]


@admin_router.get("/stats")
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    total = await db.scalar(select(func.count(Plugin.id)))
    pending = await db.scalar(
        select(func.count(Plugin.id)).where(Plugin.status == "pending")
    )
    return {"total_plugins": total or 0, "pending_plugins": pending or 0}


@admin_router.post("/cache/refresh")
async def refresh_cache_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    await refresh_cache(db)
    return {"status": "refreshed"}


@admin_router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    body = await request.body()
    if settings.github_webhook_secret:
        signature = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(
            settings.github_webhook_secret.encode("utf-8"),
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
    await _enqueue_or_fallback(
        background_tasks,
        "build",
        {"plugin_id": str(plugin.id), "version": "auto", "ref": ref, "user_id": ""},
    )
    return {"status": "queued"}
