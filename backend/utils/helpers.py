"""
General utility functions for text processing and context building.
"""
from typing import Optional
import re
from models.payloads import ReviewPayload
from config import (
    MAX_PR_BODY_LENGTH,
    MAX_COMMENT_LENGTH,
    MAX_REVIEW_LENGTH,
    MAX_DIFF_HUNK_LENGTH,
    MAX_PATCH_LENGTH,
    MAX_INLINE_COMMENT_LENGTH
)

def clip(s: Optional[str], n: int) -> str:
    """Truncate string to n characters with ellipsis if needed."""
    if not s:
        return ""
    return s if len(s) <= n else s[:n] + "\n…(truncated)…"

def extract_first_fenced_code_block(text: str) -> str:
    """Extract the first fenced code block from text."""
    if not text:
        return "```diff\n```"

    m = re.search(r"```[a-zA-Z0-9_-]*\n.*?\n```", text, flags=re.DOTALL)
    if m:
        return m.group(0).strip()

    if "```" in text:
        first = text.find("```")
        return text[first:].strip()

    return f"```\n{text.strip()}\n```"

def build_llm_context(payload: ReviewPayload) -> str:
    """Build comprehensive context string for LLM from payload."""
    pr_title = payload.pr_title or ""
    pr_body = clip(payload.pr_body, MAX_PR_BODY_LENGTH)
    
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
        hunk = clip(payload.comment_diff_hunk, MAX_DIFF_HUNK_LENGTH)
        base += f"""

Event: inline review comment
Reviewer: {payload.reviewer_login}
File path: {path}
Original comment: {clip(comment_text, MAX_COMMENT_LENGTH)}
Diff hunk (truncated):
{hunk}
""".rstrip()
    
    elif payload.kind == "issue_comment":
        comment_text = payload.comment_body or ""
        base += f"""

Event: PR conversation comment (from conversation tab)
Commenter: {payload.reviewer_login}
Comment text: {clip(comment_text, MAX_COMMENT_LENGTH)}

Context: This is a general comment on the PR, not tied to a specific line of code.
The commenter may be asking a question, requesting changes, or providing feedback about the PR as a whole.
""".rstrip()
    
    elif payload.kind == "review":
        review_text = payload.review_body or ""
        base += f"""

Event: review submitted
Reviewer: {payload.reviewer_login}
State: {payload.review_state}
Review body: {clip(review_text, MAX_REVIEW_LENGTH)}
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
Comment: {clip(comment_text, MAX_COMMENT_LENGTH)}
""".rstrip()

    if payload.review_comments:
        base += "\n\nInline comments in this review (showing up to 5):\n"
        for c in payload.review_comments[:5]:
            base += (
                f"- id={c.id} file={c.path} line={c.line or c.position} "
                f"by {c.user_login}: {clip(c.body, MAX_INLINE_COMMENT_LENGTH)}\n"
            )

    files = payload.files or []
    if files:
        base += f"\n\nChanged files: {len(files)} (showing up to 6 patches, truncated)\n"
        for f in files[:6]:
            base += (
                f"\n---\nFILE: {f.filename}\nSTATUS: {f.status} "
                f"(+{f.additions}/-{f.deletions}, changes={f.changes})\n"
                f"PATCH:\n{clip(f.patch, MAX_PATCH_LENGTH)}\n"
            )

    return base.strip()