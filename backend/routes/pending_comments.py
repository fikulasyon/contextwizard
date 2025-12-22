"""
API routes for pending comments CRUD operations.
"""
from fastapi import APIRouter
from models.payloads import (
    PendingComment, 
    PendingCommentCreate, 
    ExpiredCommentsResponse
)
from database.pending_comments import (
    create_pending_comment as db_create,
    get_pending_comment as db_get,
    delete_pending_comment as db_delete,
    get_expired_comments as db_get_expired
)

router = APIRouter(prefix="/pending-comments", tags=["pending_comments"])

@router.post("", status_code=201)
async def create_pending_comment(data: PendingCommentCreate):
    """Store a new pending comment."""
    return db_create(data)

@router.get("/{code}", response_model=PendingComment)
async def get_pending_comment(code: str):
    """Lookup a pending comment by code."""
    return db_get(code)

@router.delete("/{code}")
async def delete_pending_comment(code: str):
    """Remove a pending comment from storage."""
    return db_delete(code)

@router.get("/expired/list", response_model=ExpiredCommentsResponse)
async def get_expired_comments():
    """Get all comments that have expired (past their expires_at timestamp)."""
    expired = db_get_expired()
    return ExpiredCommentsResponse(expired_comments=expired)