# backend/database/pending_comments.py
"""
CRUD operations for pending comments.
"""
import sqlite3
import sys
import time
from typing import List
from fastapi import HTTPException
from database.connection import get_db
from models.payloads import PendingComment, PendingCommentCreate

def create_pending_comment(data: PendingCommentCreate) -> dict:
    """Store a new pending comment."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO pending_comments 
                (code, comment_id, comment_type, owner, repo, pr_number, installation_id, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.code,
                data.comment_id,
                data.comment_type,
                data.owner,
                data.repo,
                data.pr_number,
                data.installation_id,
                data.expires_at
            ))
            conn.commit()
            print(f"[db] Stored pending comment: code={data.code}, comment_id={data.comment_id}", file=sys.stderr)
            return {"status": "created", "code": data.code}
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Code already exists")

def get_pending_comment(code: str) -> PendingComment:
    """Lookup a pending comment by code."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pending_comments WHERE code = ?", (code,))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Code not found")
        
        return PendingComment(
            code=row["code"],
            comment_id=row["comment_id"],
            comment_type=row["comment_type"],
            owner=row["owner"],
            repo=row["repo"],
            pr_number=row["pr_number"],
            installation_id=row["installation_id"],
            expires_at=row["expires_at"]
        )

def delete_pending_comment(code: str) -> dict:
    """Remove a pending comment from storage."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pending_comments WHERE code = ?", (code,))
        conn.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Code not found")
        
        print(f"[db] Deleted pending comment: code={code}", file=sys.stderr)
        return {"status": "deleted", "code": code}

def get_expired_comments() -> List[PendingComment]:
    """Get all comments that have expired (past their expires_at timestamp)."""
    current_time = int(time.time())
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM pending_comments WHERE expires_at <= ?",
            (current_time,)
        )
        rows = cursor.fetchall()
        
        expired = [
            PendingComment(
                code=row["code"],
                comment_id=row["comment_id"],
                comment_type=row["comment_type"],
                owner=row["owner"],
                repo=row["repo"],
                pr_number=row["pr_number"],
                installation_id=row["installation_id"],
                expires_at=row["expires_at"]
            )
            for row in rows
        ]
        
        print(f"[db] Found {len(expired)} expired comments", file=sys.stderr)
        return expired