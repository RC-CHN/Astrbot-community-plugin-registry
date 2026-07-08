"""Public plugin submission request endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.deps import get_current_user, get_db
from ..models import User
from ..schemas.submission import SubmissionCreate, SubmissionListResponse, SubmissionResponse
from ..services.submission_service import (
    SubmissionError,
    create_submission_request,
    get_submission_request,
    list_submission_requests,
    submission_to_dict,
)

submissions_router = APIRouter(prefix="/submissions", tags=["submissions"])


@submissions_router.get("", response_model=SubmissionListResponse)
async def list_my_submissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    rows = await list_submission_requests(db, user_id=current_user.id)
    return {"items": [submission_to_dict(item, username) for item, username in rows], "total": len(rows)}


@submissions_router.post("", response_model=SubmissionResponse)
async def create_my_submission(
    request: SubmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        submission = await create_submission_request(
            db,
            user=current_user,
            repo_url=request.repo_url,
            ref_type=request.ref_type,
            ref=request.ref,
            user_message=request.user_message,
        )
    except SubmissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return submission_to_dict(submission, current_user.username)


@submissions_router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_my_submission(
    submission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    row = await get_submission_request(db, submission_id, user_id=current_user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Submission request not found")
    submission, username = row
    return submission_to_dict(submission, username)
