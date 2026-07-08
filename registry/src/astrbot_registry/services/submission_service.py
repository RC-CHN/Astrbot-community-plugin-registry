"""Plugin submission request service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PluginSubmissionRequest, User
from ..utils.git_utils import parse_github_url


class SubmissionError(ValueError):
    """Raised when a submission request cannot be processed."""


def submission_to_dict(submission: PluginSubmissionRequest, username: str | None = None) -> dict:
    return {
        "id": str(submission.id),
        "user_id": str(submission.user_id),
        "username": username,
        "repo_url": submission.repo_url,
        "provider": submission.provider,
        "ref_type": submission.ref_type,
        "ref": submission.ref,
        "status": submission.status,
        "resolved_commit_sha": submission.resolved_commit_sha,
        "accepted_plugin_id": str(submission.accepted_plugin_id) if submission.accepted_plugin_id else None,
        "accepted_version_id": str(submission.accepted_version_id) if submission.accepted_version_id else None,
        "user_message": submission.user_message,
        "admin_message": submission.admin_message,
        "accepted_by": str(submission.accepted_by) if submission.accepted_by else None,
        "accepted_at": submission.accepted_at,
        "created_at": submission.created_at,
        "updated_at": submission.updated_at,
    }


async def create_submission_request(
    db: AsyncSession,
    *,
    user: User,
    repo_url: str,
    ref_type: str,
    ref: str | None,
    user_message: str | None,
) -> PluginSubmissionRequest:
    try:
        parse_github_url(repo_url)
    except ValueError as exc:
        raise SubmissionError(str(exc)) from exc
    normalized_ref = ref.strip() if ref else None
    if ref_type == "default":
        normalized_ref = None
    if ref_type != "default" and not normalized_ref:
        raise SubmissionError("ref is required when ref_type is not default")
    submission = PluginSubmissionRequest(
        user_id=user.id,
        repo_url=repo_url.strip(),
        provider="github",
        ref_type=ref_type,
        ref=normalized_ref,
        user_message=user_message,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return submission


async def list_submission_requests(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    status: str | None = None,
) -> list[tuple[PluginSubmissionRequest, str | None]]:
    statement = (
        select(PluginSubmissionRequest, User.username)
        .join(User, User.id == PluginSubmissionRequest.user_id)
        .order_by(PluginSubmissionRequest.created_at.desc())
    )
    if user_id is not None:
        statement = statement.where(PluginSubmissionRequest.user_id == user_id)
    if status:
        statement = statement.where(PluginSubmissionRequest.status == status)
    result = await db.execute(statement)
    return [(row[0], row[1]) for row in result.all()]


async def get_submission_request(
    db: AsyncSession,
    submission_id: uuid.UUID,
    *,
    user_id: uuid.UUID | None = None,
) -> tuple[PluginSubmissionRequest, str | None] | None:
    statement = (
        select(PluginSubmissionRequest, User.username)
        .join(User, User.id == PluginSubmissionRequest.user_id)
        .where(PluginSubmissionRequest.id == submission_id)
    )
    if user_id is not None:
        statement = statement.where(PluginSubmissionRequest.user_id == user_id)
    result = await db.execute(statement)
    row = result.one_or_none()
    if row is None:
        return None
    return row[0], row[1]


async def mark_submission_decision(
    db: AsyncSession,
    submission: PluginSubmissionRequest,
    *,
    status: str,
    admin_message: str | None,
    accepted_by: uuid.UUID | None = None,
) -> PluginSubmissionRequest:
    if submission.status != "pending_review":
        raise SubmissionError("submission has already been processed")
    submission.status = status
    submission.admin_message = admin_message
    if status == "accepted":
        submission.accepted_by = accepted_by
        submission.accepted_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(submission)
    return submission
