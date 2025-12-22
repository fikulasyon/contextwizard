# backend/database/connection.py
"""
Database connection management and initialization.
"""
import sqlite3
import sys
from contextlib import contextmanager
from config import DB_PATH

def init_db():
    """Initialize SQLite database with pending_comments table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
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
    """)
    conn.commit()
    conn.close()
    print(f"[db] Initialized database at {DB_PATH}", file=sys.stderr)

@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()