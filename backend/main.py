# backend/main.py
from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()

from typing import List, Optional, Literal, Callable, TypeVar
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import os
import json
import sys
import time
import random
import re
import anyio
import sqlite3
from contextlib import contextmanager
from google import genai

types = genai.types

app = FastAPI()

# ---------------------------- 
# Database setup
# ----------------------------
DB_PATH = os.getenv("PENDING_COMMENTS_DB", "./pending_comments.db")

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

# Initialize on startup
init_db()

# ----------------------------
# Retry config
# ----------------------------
RETRY_INITIAL_DELAY_SEC = float(os.getenv("GEMINI_RETRY_INITIAL_DELAY", "0.35"))
RETRY_MAX_DELAY_SEC = float(os.getenv("GEMINI_RETRY_MAX_DELAY", "2.0"))
RETRY_MAX_ATTEMPTS = int(os.getenv("GEMINI_RETRY_MAX_ATTEMPTS", "12"))
RETRY_JITTER_SEC = float(os.getenv("GEMINI_RETRY_JITTER_SEC", "0.10"))

# ----------------------------
# Payload models
# ----------------------------
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

# ----------------------------
# Pending Comments Models
# ----------------------------
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

# ----------------------------
# Pending Comments CRUD
# ----------------------------
@app.post("/pending-comments", status_code=201)
async def create_pending_comment(data: PendingCommentCreate):
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

@app.get("/pending-comments/{code}", response_model=PendingComment)
async def get_pending_comment(code: str):
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

@app.delete("/pending-comments/{code}")
async def delete_pending_comment(code: str):
    """Remove a pending comment from storage."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pending_comments WHERE code = ?", (code,))
        conn.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Code not found")
        
        print(f"[db] Deleted pending comment: code={code}", file=sys.stderr)
        return {"status": "deleted", "code": code}

@app.get("/pending-comments/expired/list", response_model=ExpiredCommentsResponse)
async def get_expired_comments():
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
        return ExpiredCommentsResponse(expired_comments=expired)

# ----------------------------
# Gemini structured output models
# ----------------------------
Category = Literal[
    "PRAISE",
    "GOOD_CHANGE",
    "BAD_CHANGE",
    "GOOD_QUESTION",
    "BAD_QUESTION",
    "UNKNOWN",
]

class Classification(BaseModel):
    category: Category
    needs_reply: bool = Field(..., description="True only for GOOD_CHANGE, BAD_CHANGE, BAD_QUESTION.")
    needs_clarification: bool = Field(..., description="True only for BAD_CHANGE or BAD_QUESTION.")
    confidence: float = Field(..., ge=0.0, le=1.0)
    short_reason: str = Field(..., description="One short sentence. No chain-of-thought.")

class ClarifiedQuestion(BaseModel):
    clarified_question: str = Field(..., description="A rewritten, clarified version of the original question.")
    confidence: float = Field(..., ge=0.0, le=1.0)
    short_reason: str = Field(..., description="One short sentence on what was ambiguous / what you clarified.")

class ClarifiedChange(BaseModel):
    clarified_request: str = Field(
        ...,
        description="A rewritten, clarified change request. Must be actionable but may contain placeholders like <which function?>.",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    short_reason: str = Field(..., description="One short sentence on what was unclear / what you clarified.")

# ----------------------------
# Helpers
# ----------------------------
def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)

def clip(s: Optional[str], n: int) -> str:
    if not s:
        return ""
    return s if len(s) <= n else s[:n] + "\n…(truncated)…"

def build_llm_context(payload: ReviewPayload) -> str:
    pr_title = payload.pr_title or ""
    pr_body = clip(payload.pr_body, 1200)
    base = f"""
Repo: {payload.repo_full_name}
PR: #{payload.pr_number} — {pr_title}
PR author: {payload.pr_author_login}
PR description (truncated):
{pr_body}
""".strip()

    if payload.kind == "review_comment":
        comment_text = payload.comment_body or ""
        path = payload.comment_path or ""
        hunk = clip(payload.comment_diff_hunk, 1200)
        base += f"""

Event: inline review comment
Reviewer: {payload.reviewer_login}
File path: {path}
Original comment: {clip(comment_text, 1500)}
Diff hunk (truncated):
{hunk}
""".rstrip()
    
    elif payload.kind == "issue_comment":
        comment_text = payload.comment_body or ""
        base += f"""

Event: PR conversation comment (from conversation tab)
Commenter: {payload.reviewer_login}
Comment text: {clip(comment_text, 1500)}

Context: This is a general comment on the PR, not tied to a specific line of code.
The commenter may be asking a question, requesting changes, or providing feedback about the PR as a whole.
""".rstrip()
    
    elif payload.kind == "review":
        review_text = payload.review_body or ""
        base += f"""

Event: review submitted
Reviewer: {payload.reviewer_login}
State: {payload.review_state}
Review body: {clip(review_text, 2000)}
""".rstrip()
    
    elif payload.kind == "wizard_review_command":
        base += f"""

Event: Autonomous wizard review requested
Requester: {payload.reviewer_login}
Task: Perform comprehensive code review of all changes
""".rstrip()
    
    else:
        comment_text = payload.comment_body or payload.review_body or ""
        if comment_text:
            base += f"""

Event: {payload.kind}
User: {payload.reviewer_login}
Comment: {clip(comment_text, 1500)}
""".rstrip()

    if payload.review_comments:
        base += "\n\nInline comments in this review (showing up to 5):\n"
        for c in payload.review_comments[:5]:
            base += (
                f"- id={c.id} file={c.path} line={c.line or c.position} "
                f"by {c.user_login}: {clip(c.body, 400)}\n"
            )

    files = payload.files or []
    if files:
        base += f"\n\nChanged files: {len(files)} (showing up to 6 patches, truncated)\n"
        for f in files[:6]:
            base += (
                f"\n---\nFILE: {f.filename}\nSTATUS: {f.status} "
                f"(+{f.additions}/-{f.deletions}, changes={f.changes})\n"
                f"PATCH:\n{clip(f.patch, 1200)}\n"
            )

    return base.strip()

def extract_first_fenced_code_block(text: str) -> str:
    if not text:
        return "```diff\n```"

    m = re.search(r"```[a-zA-Z0-9_-]*\n.*?\n```", text, flags=re.DOTALL)
    if m:
        return m.group(0).strip()

    if "```" in text:
        first = text.find("```")
        return text[first:].strip()

    return f"```\n{text.strip()}\n```"

# ----------------------------
# Gemini retry wrapper
# ----------------------------
T = TypeVar("T")

def _is_transient_gemini_error(exc: Exception) -> bool:
    msg = (str(exc) or "").lower()
    transient_markers = [
        "503", "overloaded", "unavailable", "resource exhausted", "rate limit",
        "quota", "429", "timeout", "timed out", "deadline exceeded",
        "connection reset", "connection aborted", "bad gateway", "502",
        "gateway timeout", "504", "internal error", "500", "temporarily", "try again",
    ]
    return any(m in msg for m in transient_markers)

def gemini_call_with_retry(
    call_name: str,
    fn: Callable[[], T],
    *,
    max_attempts: int = RETRY_MAX_ATTEMPTS,
    initial_delay: float = RETRY_INITIAL_DELAY_SEC,
    max_delay: float = RETRY_MAX_DELAY_SEC,
    jitter: float = RETRY_JITTER_SEC,
) -> T:
    attempt = 1
    delay = max(0.0, initial_delay)
    while True:
        try:
            print(f"[gemini] {call_name}: attempt {attempt}/{max_attempts}", file=sys.stderr)
            return fn()
        except Exception as e:
            transient = _is_transient_gemini_error(e)
            print(
                f"[gemini] {call_name}: attempt {attempt} failed "
                f"(transient={transient}) -> {type(e).__name__}: {str(e)[:220]}",
                file=sys.stderr,
            )
            if not transient:
                raise
            if attempt >= max_attempts:
                raise
            sleep_for = min(max_delay, delay) + random.uniform(0.0, max(0.0, jitter))
            print(f"[gemini] {call_name}: sleeping {sleep_for:.2f}s before retry", file=sys.stderr)
            time.sleep(sleep_for)
            delay = min(max_delay, max(delay, 0.05) * 1.5)
            attempt += 1

# ----------------------------
# Gemini calls
# ----------------------------
def classify_with_gemini(payload: ReviewPayload) -> Classification:
    client = get_client()
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    system_instructions = """
You are a code review assistant that classifies GitHub PR comments into exactly ONE category.

You will receive comments from THREE different contexts:
1. Inline review comments (tied to specific code lines)
2. PR conversation comments (general comments on the PR)
3. Review summaries (submitted reviews)

Decision priority:
1) Determine intent: praise / question / request change
2) Determine clarity: good / bad

Categories: PRAISE, GOOD_CHANGE, BAD_CHANGE, GOOD_QUESTION, BAD_QUESTION, UNKNOWN

Rules:
- PRAISE: positive feedback, appreciation, acknowledgment (e.g., "nice work", "LGTM", "looks good")
- GOOD_CHANGE: clear, actionable change request with sufficient context
- BAD_CHANGE: unclear/underspecified change request (missing details like which file, which function, what exactly to change)
- GOOD_QUESTION: clear question with enough context to understand what's being asked
- BAD_QUESTION: unclear question (vague, missing context, ambiguous)
- UNKNOWN: intent cannot be determined with confidence

Important:
- "bad" = unclear/underspecified (NOT rude or negative tone)
- needs_reply = true ONLY for: GOOD_CHANGE, BAD_CHANGE, BAD_QUESTION
- needs_clarification = true ONLY for: BAD_CHANGE, BAD_QUESTION
- For conversation comments without specific code context, be more lenient in classification
- Single word comments like "wow", "nice", "thanks" should be PRAISE
- Questions about "why", "how", "what" are questions, not change requests
- Requests with words like "can you", "please add", "should we" are change requests

Return ONLY valid JSON for the schema.
""".strip()

    ctx = build_llm_context(payload)

    def _call():
        resp = client.models.generate_content(
            model=model,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=f"{system_instructions}\n\nCONTEXT:\n{ctx}")],
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Classification,
                temperature=0.2,
            ),
        )
        data = getattr(resp, "parsed", None)
        if data is None:
            data = json.loads(resp.text)
        return Classification.model_validate(data)

    return gemini_call_with_retry("classify_with_gemini", _call)

def clarify_bad_question(payload: ReviewPayload, cls: Classification) -> ClarifiedQuestion:
    client = get_client()
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    system_instructions = """
Rewrite an unclear PR question into a clarified question.

Rules:
- Output must match the JSON schema.
- 1–2 short sentences max, end with "?".
- Do NOT answer. Do NOT invent facts.
- Use placeholders if missing: "<which file?>", "<which function?>", "<expected behavior?>"
""".strip()

    ctx = build_llm_context(payload)

    def _call():
        resp = client.models.generate_content(
            model=model,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=f"{system_instructions}\n\nCONTEXT:\n{ctx}")],
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ClarifiedQuestion,
                temperature=0.2,
            ),
        )
        data = getattr(resp, "parsed", None)
        if data is None:
            data = json.loads(resp.text)
        return ClarifiedQuestion.model_validate(data)

    return gemini_call_with_retry("clarify_bad_question", _call)

def clarify_bad_change(payload: ReviewPayload, cls: Classification) -> ClarifiedChange:
    client = get_client()
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    system_instructions = """
Rewrite an unclear PR change request into a clarified, actionable request.

Rules:
- Output must match the JSON schema.
- Do NOT propose code. Do NOT invent facts.
- "clarified_request" must be 1–2 short sentences max.
- Use placeholders if missing: "<which file?>", "<which function?>", "<acceptance criteria?>"
""".strip()

    ctx = build_llm_context(payload)

    def _call():
        resp = client.models.generate_content(
            model=model,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=f"{system_instructions}\n\nCONTEXT:\n{ctx}")],
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ClarifiedChange,
                temperature=0.2,
            ),
        )
        data = getattr(resp, "parsed", None)
        if data is None:
            data = json.loads(resp.text)
        return ClarifiedChange.model_validate(data)

    return gemini_call_with_retry("clarify_bad_change", _call)

def generate_code_suggestion(
    payload: ReviewPayload,
    cls: Classification,
    reviewer_comment_override: Optional[str] = None,
) -> str:
    client = get_client()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    reviewer_comment = (reviewer_comment_override or payload.comment_body or payload.review_body or "").strip()
    ctx = build_llm_context(payload)

    system_instructions = f"""
You are a GitHub code review assistant.
Goal: produce a SHORT, STRICT code suggestion for the requested change.

Hard rules:
- Output MUST be ONLY ONE fenced code block and NOTHING else.
- The code block language MUST be either:
  1) ```diff  (preferred)
  2) ```suggestion (only if diff isn't possible)
- Keep it minimal: change ONLY the smallest relevant lines.
- Do NOT rewrite whole files. Do NOT include unrelated context.
- If unsure, output a SMALL diff that adds TODOs/placeholders rather than guessing.

Comment to satisfy (source of truth):
{reviewer_comment}
""".strip()

    prompt = f"""
{system_instructions}

CONTEXT (reference only):
---
{ctx}
---

Return ONLY the single fenced code block now.
""".strip()

    def _call():
        resp = client.models.generate_content(
            model=model,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(temperature=0.2),
        )
        return extract_first_fenced_code_block((resp.text or "").strip())

    return gemini_call_with_retry("generate_code_suggestion", _call)

def run_wizard_full_review(payload: ReviewPayload) -> str:
    """
    Autonomous code review using Gemini.
    Returns formatted markdown with issues found.
    """
    client = get_client()
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    
    system_instructions = """
You are the 'ContextWizard' AI Reviewer performing an autonomous code review.

Your task:
1. Analyze the provided PR diff hunks and changed files
2. Identify potential issues in these categories:
   - Bugs or logic errors
   - Security vulnerabilities
   - Performance problems
   - Code quality issues
   - Best practice violations

Output format (use markdown):
For each issue found, provide:

### [Issue Title]
**Severity**: High/Medium/Low
**Description**: Clear explanation of the problem and why it matters
**Suggestion**: Specific actionable fix

Rules:
- Be concise but thorough
- Focus on real issues, not style preferences
- Provide specific line references when possible
- If no issues found, say "No significant issues detected"
- Maximum 5 issues per review to stay focused
""".strip()

    ctx = build_llm_context(payload)

    def _call():
        resp = client.models.generate_content(
            model=model,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=f"{system_instructions}\n\n{ctx}")]
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=2048
            ),
        )
        result = (resp.text or "").strip()
        if not result:
            return "✅ No significant issues detected in this PR."
        return result

    return gemini_call_with_retry("wizard_review", _call)

# ----------------------------
# Formatting helpers
# ----------------------------
def format_debug_comment(payload: ReviewPayload, cls: Classification) -> str:
    where = "review" if payload.kind == "review" else "inline comment"
    original_text = payload.review_body if payload.kind == "review" else payload.comment_body
    original_text = (original_text or "").strip()

    lines = [
        "🧠 **ContextWizard (debug: classification only)**",
        f"- category: **{cls.category}**",
        f"- confidence: {cls.confidence:.2f}",
        "",
        "**Original text:**",
        f"> {(original_text[:500] + '…') if len(original_text) > 500 else original_text}".replace("\n", "\n> "),
        "",
        "_(classification only; no follow-up action taken)_",
    ]
    return "\n".join(lines).strip()

def format_clarification_question_comment(payload: ReviewPayload, cls: Classification, cq: ClarifiedQuestion) -> str:
    original_text = (payload.comment_body or payload.review_body or "").strip()

    lines = [
        "❓ **ContextWizard (clarified question)**",
        f"- category: **{cls.category}**",
        f"- classification_confidence: {cls.confidence:.2f}",
        f"- rewrite_confidence: {cq.confidence:.2f}",
        "",
        "**Original question:**",
        f"> {(original_text[:800] + '…') if len(original_text) > 800 else original_text}".replace("\n", "\n> "),
        "",
        "**Proposed clarified version:**",
        f"> {cq.clarified_question}".replace("\n", "\n> "),
    ]
    return "\n".join(lines).strip()

def format_bad_change_with_suggestion_comment(
    cls: Classification,
    clarified_request: str,
    suggestion_block: str,
) -> str:
    return "\n".join(
        [
            f"1- **clarified version:** {clarified_request}",
            "2- **suggested code change:**",
            suggestion_block.strip(),
        ]
    ).strip()

# ----------------------------
# FastAPI route
# ----------------------------
@app.post("/analyze-review", response_model=BackendResponse)
async def analyze_review(payload: ReviewPayload):
    print(f"[DEBUG] Processing kind: {payload.kind} for PR #{payload.pr_number}", file=sys.stderr)

    # Handle wizard review command - this gets full review
    if payload.kind == "wizard_review_command":
        print("[DEBUG] Running wizard autonomous review", file=sys.stderr)
        try:
            suggestions = await anyio.to_thread.run_sync(run_wizard_full_review, payload)
            
            # Format the wizard review nicely
            wizard_output = f"""🧙‍♂️ **ContextWizard Autonomous Review**

{suggestions}

---
_This is an AI-generated code review. Please verify all suggestions before applying._"""
            
            return BackendResponse(comment=wizard_output)
        except Exception as e:
            error_msg = f"❌ **Wizard Review Error**\n\nFailed to complete autonomous review: {str(e)[:200]}"
            print(f"[ERROR] Wizard review failed: {str(e)}", file=sys.stderr)
            return BackendResponse(comment=error_msg)

    print("==== Incoming payload ====", file=sys.stderr)
    try:
        print(json.dumps(payload.model_dump(), indent=2), file=sys.stderr)
    except Exception:
        print(json.dumps(payload.dict(), indent=2), file=sys.stderr)
    print("==========================", file=sys.stderr)

    # Skip reviews with inline comments (they'll be handled individually)
    if payload.kind == "review" and payload.inline_comment_count and payload.inline_comment_count > 0:
        print(f"[DEBUG] Skipping review with {payload.inline_comment_count} inline comments", file=sys.stderr)
        return BackendResponse(comment="")

    # Classification and processing for non-wizard reviews
    print("[DEBUG] Classifying with Gemini...", file=sys.stderr)
    try:
        cls = await anyio.to_thread.run_sync(classify_with_gemini, payload)
        print(f"[DEBUG] Classification: {cls.category} (confidence={cls.confidence})", file=sys.stderr)
    except Exception as e:
        print(f"[DEBUG] Classification failed: {str(e)[:200]}", file=sys.stderr)
        cls = Classification(
            category="UNKNOWN",
            needs_reply=True,
            needs_clarification=False,
            confidence=0.0,
            short_reason=f"Classification failed: {type(e).__name__}",
        )
        return BackendResponse(comment=format_debug_comment(payload, cls))

    # Validate payload kind
    if payload.kind not in ("review_comment", "review", "issue_comment"):
        print(f"[DEBUG] Invalid kind '{payload.kind}'", file=sys.stderr)
        return BackendResponse(comment=format_debug_comment(payload, cls))

    # Process based on classification
    if cls.category == "PRAISE":
        return BackendResponse(comment=format_debug_comment(payload, cls))

    if cls.category == "GOOD_CHANGE" and cls.confidence >= 0.7:
        try:
            suggestion_block = await anyio.to_thread.run_sync(generate_code_suggestion, payload, cls, None)
            return BackendResponse(comment=suggestion_block)
        except Exception as e:
            fallback = Classification(
                category="UNKNOWN",
                needs_reply=True,
                needs_clarification=False,
                confidence=0.0,
                short_reason=f"Suggestion generation failed: {str(e)[:160]}",
            )
            return BackendResponse(comment=format_debug_comment(payload, fallback))

    if cls.category == "BAD_QUESTION" and cls.confidence >= 0.55:
        try:
            cq = await anyio.to_thread.run_sync(clarify_bad_question, payload, cls)
            return BackendResponse(comment=format_clarification_question_comment(payload, cls, cq))
        except Exception as e:
            fallback = Classification(
                category="UNKNOWN",
                needs_reply=True,
                needs_clarification=False,
                confidence=0.0,
                short_reason=f"Question clarification failed: {str(e)[:160]}",
            )
            return BackendResponse(comment=format_debug_comment(payload, fallback))

    if cls.category == "BAD_CHANGE" and cls.confidence >= 0.55:
        try:
            cc = await anyio.to_thread.run_sync(clarify_bad_change, payload, cls)
            suggestion_block = await anyio.to_thread.run_sync(
                generate_code_suggestion, payload, cls, cc.clarified_request,
            )
            body = format_bad_change_with_suggestion_comment(cls, cc.clarified_request, suggestion_block)
            return BackendResponse(comment=body)
        except Exception as e:
            fallback = Classification(
                category="UNKNOWN",
                needs_reply=True,
                needs_clarification=False,
                confidence=0.0,
                short_reason=f"BAD_CHANGE processing failed: {str(e)[:160]}",
            )
            return BackendResponse(comment=format_debug_comment(payload, fallback))

    if cls.category == "GOOD_QUESTION":
        return BackendResponse(comment=format_debug_comment(payload, cls))

    return BackendResponse(comment=format_debug_comment(payload, cls))