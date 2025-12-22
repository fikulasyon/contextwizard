"""
Main review analysis endpoint that orchestrates classification and response generation.
"""
import sys
import json
import anyio
from fastapi import APIRouter
from models.payloads import ReviewPayload, BackendResponse
from models.gemini_schemas import Classification
from services.classification import classify_with_gemini
from services.clarification import clarify_bad_question, clarify_bad_change
from services.code_generation import generate_code_suggestion, run_wizard_full_review
from utils.formatting import (
    format_debug_comment,
    format_clarification_question_comment,
    format_bad_change_with_suggestion_comment
)
from config import (
    GOOD_CHANGE_CONFIDENCE_THRESHOLD,
    BAD_QUESTION_CONFIDENCE_THRESHOLD,
    BAD_CHANGE_CONFIDENCE_THRESHOLD
)

router = APIRouter(tags=["analysis"])

@router.post("/analyze-review", response_model=BackendResponse)
async def analyze_review(payload: ReviewPayload):
    """
    Analyze a PR review comment and generate appropriate response.
    
    Handles different types of review events:
    - wizard_review_command: Autonomous full PR review
    - review_comment: Inline code comments
    - review: Submitted review summaries
    - issue_comment: PR conversation comments
    
    Returns appropriate response based on classification:
    - PRAISE: Debug info only
    - GOOD_CHANGE: Code suggestion
    - BAD_CHANGE: Clarified request + code suggestion
    - GOOD_QUESTION: Debug info only
    - BAD_QUESTION: Clarified question
    - UNKNOWN: Debug info
    """
    print(f"[DEBUG] Processing kind: {payload.kind} for PR #{payload.pr_number}", file=sys.stderr)

    # Handle wizard review command - full autonomous review
    if payload.kind == "wizard_review_command":
        print("[DEBUG] Running wizard autonomous review", file=sys.stderr)
        try:
            suggestions = await anyio.to_thread.run_sync(run_wizard_full_review, payload)
            
            wizard_output = f"""🧙‍♂️ **ContextWizard Autonomous Review**

{suggestions}

---
_This is an AI-generated code review. Please verify all suggestions before applying._"""
            
            return BackendResponse(comment=wizard_output)
        except Exception as e:
            error_msg = f"❌ **Wizard Review Error**\n\nFailed to complete autonomous review: {str(e)[:200]}"
            print(f"[ERROR] Wizard review failed: {str(e)}", file=sys.stderr)
            return BackendResponse(comment=error_msg)

    # Log incoming payload for debugging
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

    # Classify the comment
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

    # Handle PRAISE - just show debug info
    if cls.category == "PRAISE":
        return BackendResponse(comment=format_debug_comment(payload, cls))

    # Handle GOOD_CHANGE - generate code suggestion
    if cls.category == "GOOD_CHANGE" and cls.confidence >= GOOD_CHANGE_CONFIDENCE_THRESHOLD:
        try:
            suggestion_block = await anyio.to_thread.run_sync(
                generate_code_suggestion, payload, cls, None
            )
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

    # Handle BAD_QUESTION - clarify the question
    if cls.category == "BAD_QUESTION" and cls.confidence >= BAD_QUESTION_CONFIDENCE_THRESHOLD:
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

    # Handle BAD_CHANGE - clarify and generate suggestion
    if cls.category == "BAD_CHANGE" and cls.confidence >= BAD_CHANGE_CONFIDENCE_THRESHOLD:
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

    # Handle GOOD_QUESTION - just show debug info
    if cls.category == "GOOD_QUESTION":
        return BackendResponse(comment=format_debug_comment(payload, cls))

    # Default case - show debug info
    return BackendResponse(comment=format_debug_comment(payload, cls))