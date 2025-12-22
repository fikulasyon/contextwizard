"""
Code suggestion and wizard review generation service using Gemini.
"""
from typing import Optional
from google import genai
from models.payloads import ReviewPayload
from models.gemini_schemas import Classification
from services.gemini_client import get_client, gemini_call_with_retry
from utils.helpers import build_llm_context, extract_first_fenced_code_block
from config import GEMINI_CODE_MODEL, GEMINI_MODEL

types = genai.types

def generate_code_suggestion(
    payload: ReviewPayload,
    cls: Classification,
    reviewer_comment_override: Optional[str] = None,
) -> str:
    """
    Generate a code suggestion for a change request.
    
    Args:
        payload: Review payload containing context
        cls: Classification result (not currently used but kept for consistency)
        reviewer_comment_override: Optional override for the comment text
        
    Returns:
        Formatted code suggestion block
    """
    client = get_client()
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
            model=GEMINI_CODE_MODEL,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(temperature=0.2),
        )
        return extract_first_fenced_code_block((resp.text or "").strip())

    return gemini_call_with_retry("generate_code_suggestion", _call)

def run_wizard_full_review(payload: ReviewPayload) -> str:
    """
    Perform autonomous code review using Gemini (wizard mode).
    
    Args:
        payload: Review payload containing PR context
        
    Returns:
        Formatted markdown review with issues found
    """
    client = get_client()
    
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
            model=GEMINI_MODEL,
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