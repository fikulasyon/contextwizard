# backend/main.py
from __future__ import annotations
from dotenv import load_dotenv

load_dotenv()

from typing import List, Optional, Literal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import sys
import time
import sqlite3
from contextlib import contextmanager

app = FastAPI()

# ----------------------------
# Database setup
# ----------------------------
DB_PATH = os.getenv("PENDING_COMMENTS_DB", "./pending_comments.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_comments (
            code TEXT PRIMARY KEY,
            comment_id INTEGER NOT NULL,
            comment_type TEXT NOT NULL,
            owner TEXT NOT NULL,
            repo TEXT NOT NULL,
            pr_number INTEGER NOT NULL,
            installation_id INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()
    print(f"[db] Initialized database at {DB_PATH}", file=sys.stderr)


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


init_db()

# ----------------------------
# Models
# ----------------------------
class PendingCommentCreate(BaseModel):
    code: str
    comment_id: int
    comment_type: Literal["inline", "thread"]
    owner: str
    repo: str
    pr_number: int
    installation_id: int
    expires_at: int


class PendingComment(PendingCommentCreate):
    pass


class ExpiredCommentsResponse(BaseModel):
    expired_comments: List[PendingComment]


# ----------------------------
# Helpers
# ----------------------------
def validate_expires_at(expires_at: int) -> None:
    """
    Prevent obviously wrong expiry values.
    - must be in the future
    - must not exceed 24 hours
    """
    now = int(time.time())

    if expires_at < now:
        raise HTTPException(status_code=400, detail="expires_at must be in the future")

    if expires_at > now + 24 * 60 * 60:
        raise HTTPException(
            status_code=400,
            detail="expires_at cannot be more than 24 hours in the future",
        )


# ----------------------------
# API
# ----------------------------
@app.post("/pending-comments", status_code=201)
async def create_pending_comment(data: PendingCommentCreate):
    validate_expires_at(data.expires_at)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO pending_comments
            (code, comment_id, comment_type, owner, repo, pr_number, installation_id, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.code,
                data.comment_id,
                data.comment_type,
                data.owner,
                data.repo,
                data.pr_number,
                data.installation_id,
                data.expires_at,
            ),
        )
        conn.commit()

    return {"status": "created", "code": data.code}


@app.get("/pending-comments/expired/list", response_model=ExpiredCommentsResponse)
async def get_expired_comments():
    now = int(time.time())

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM pending_comments WHERE expires_at <= ?",
            (now,),
        )
        rows = cursor.fetchall()

        expired = [PendingComment(**dict(row)) for row in rows]
        return ExpiredCommentsResponse(expired_comments=expired)
