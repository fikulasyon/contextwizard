"""
Functions for formatting bot responses and comments.
"""
from models.payloads import ReviewPayload
from models.gemini_schemas import Classification, ClarifiedQuestion

def format_debug_comment(payload: ReviewPayload, cls: Classification) -> str:
    """Format a debug comment showing classification details."""
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

def format_clarification_question_comment(
    payload: ReviewPayload, 
    cls: Classification, 
    cq: ClarifiedQuestion
) -> str:
    """Format a comment with a clarified question."""
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
    """Format a comment with clarified change request and code suggestion."""
    return "\n".join(
        [
            f"1- **clarified version:** {clarified_request}",
            "2- **suggested code change:**",
            suggestion_block.strip(),
        ]
    ).strip()