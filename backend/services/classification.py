"""
Comment classification service using Gemini.
"""
import json
from google import genai
from models.payloads import ReviewPayload
from models.gemini_schemas import Classification
from services.gemini_client import get_client, gemini_call_with_retry
from utils.helpers import build_llm_context
from config import GEMINI_MODEL

types = genai.types

CLASSIFICATION_SYSTEM_PROMPT = """
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

def classify_with_gemini(payload: ReviewPayload) -> Classification:
    """
    Classify a PR comment using Gemini.
    
    Args:
        payload: Review payload containing comment and context
        
    Returns:
        Classification result
    """
    client = get_client()
    ctx = build_llm_context(payload)

    def _call():
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=f"{CLASSIFICATION_SYSTEM_PROMPT}\n\nCONTEXT:\n{ctx}")],
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