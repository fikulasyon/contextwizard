# backend/services/clarification.py
"""
Question and change request clarification service using Gemini.
"""
import json
from google import genai
from models.payloads import ReviewPayload
from models.gemini_schemas import Classification, ClarifiedQuestion, ClarifiedChange
from services.gemini_client import get_client, gemini_call_with_retry
from utils.helpers import build_llm_context
from config import GEMINI_MODEL

types = genai.types

CLARIFY_QUESTION_PROMPT = """
Rewrite an unclear PR question into a clarified question.

Rules:
- Output must match the JSON schema.
- 1-2 short sentences max, end with "?".
- Do NOT answer. Do NOT invent facts.
- Use placeholders if missing: "<which file?>", "<which function?>", "<expected behavior?>"
""".strip()

CLARIFY_CHANGE_PROMPT = """
Rewrite an unclear PR change request into a clarified, actionable request.

Rules:
- Output must match the JSON schema.
- Do NOT propose code. Do NOT invent facts.
- "clarified_request" must be 1-2 short sentences max.
- Use placeholders if missing: "<which file?>", "<which function?>", "<acceptance criteria?>"
""".strip()

def clarify_bad_question(payload: ReviewPayload, cls: Classification) -> ClarifiedQuestion:
    """
    Clarify an unclear question.
    
    Args:
        payload: Review payload containing the question
        cls: Classification result (not currently used but kept for consistency)
        
    Returns:
        Clarified question
    """
    client = get_client()
    ctx = build_llm_context(payload)

    def _call():
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=f"{CLARIFY_QUESTION_PROMPT}\n\nCONTEXT:\n{ctx}")],
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
    """
    Clarify an unclear change request.
    
    Args:
        payload: Review payload containing the change request
        cls: Classification result (not currently used but kept for consistency)
        
    Returns:
        Clarified change request
    """
    client = get_client()
    ctx = build_llm_context(payload)

    def _call():
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=f"{CLARIFY_CHANGE_PROMPT}\n\nCONTEXT:\n{ctx}")],
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