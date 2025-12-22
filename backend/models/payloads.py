"""
Pydantic models for API request and response payloads.
"""
from typing import List, Optional, Literal
from pydantic import BaseModel

class FileInfo(BaseModel):
    filename: str
    status: Optional[str] = None
    additions: Optional[int] = None
    deletions: Optional[int] = None
    changes: Optional[int] = None
    patch: Optional[str] = None

class ReviewCommentInfo(BaseModel):
    id: int
    body: str
    path: Optional[str] = None
    diff_hunk: Optional[str] = None
    position: Optional[int] = None
    line: Optional[int] = None
    original_line: Optional[int] = None
    user_login: Optional[str] = None

class ReviewPayload(BaseModel):
    kind: str
    review_body: Optional[str] = None
    review_state: Optional[str] = None
    comment_body: Optional[str] = None
    comment_path: Optional[str] = None
    comment_diff_hunk: Optional[str] = None
    comment_position: Optional[int] = None
    comment_id: Optional[int] = None
    reviewer_login: Optional[str] = None
    pr_number: int
    pr_title: Optional[str] = None
    pr_body: Optional[str] = None
    pr_author_login: Optional[str] = None
    repo_full_name: str
    repo_owner: Optional[str] = None
    repo_name: Optional[str] = None
    files: Optional[List[FileInfo]] = None
    review_comments: Optional[List[ReviewCommentInfo]] = None
    inline_comment_count: Optional[int] = 0

class BackendResponse(BaseModel):
    comment: str

class PendingComment(BaseModel):
    code: str
    comment_id: int
    comment_type: Literal["inline", "thread"]
    owner: str
    repo: str
    pr_number: int
    installation_id: int
    expires_at: int

class PendingCommentCreate(BaseModel):
    code: str
    comment_id: int
    comment_type: Literal["inline", "thread"]
    owner: str
    repo: str
    pr_number: int
    installation_id: int
    expires_at: int

class ExpiredCommentsResponse(BaseModel):
    expired_comments: List[PendingComment]