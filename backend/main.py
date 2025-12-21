from __future__ import annotations
from dotenv import load_dotenv

load_dotenv()

from typing import List, Optional, Literal, Callable, TypeVar, Type
from fastapi import FastAPI
from pydantic import BaseModel, Field
import os
import json
import sys
import time
import random
import re
import anyio
import uvicorn

# AI Clients
from google import genai
from openai import OpenAI

types = genai.types
app = FastAPI()

# ----------------------------
# Configuration & API Retries
# ----------------------------
RETRY_INITIAL_DELAY_SEC = float(os.getenv("GEMINI_RETRY_INITIAL_DELAY", "0.35"))
RETRY_MAX_DELAY_SEC = float(os.getenv("GEMINI_RETRY_MAX_DELAY", "2.0"))
RETRY_MAX_ATTEMPTS = int(os.getenv("GEMINI_RETRY_MAX_ATTEMPTS", "12"))
RETRY_JITTER_SEC = float(os.getenv("GEMINI_RETRY_JITTER_SEC", "0.10"))

# ----------------------------
# Data Models (Pydantic)
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
    user_login: Optional[str] = None

class ReviewPayload(BaseModel):
    kind: str

    review_body: Optional[str] = None
    review_state: Optional[str] = None
    comment_body: Optional[str] = None
    comment_path: Optional[str] = None
    comment_diff_hunk: Optional[str] = None
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

class BackendResponse(BaseModel):
    comment: str


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
# LLM Clients Initialization
# ----------------------------
def get_gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: raise RuntimeError("GEMINI_API_KEY not set")
    return genai.Client(api_key=api_key)

def get_perplexity_client() -> OpenAI:
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key: raise RuntimeError("PERPLEXITY_API_KEY not set")
    return OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")

# ----------------------------
# Centralized LLM Orchestrator
# ----------------------------
T = TypeVar("T")

async def call_llm_text(system_instructions: str, payload: ReviewPayload) -> str:
    """Orchestrates raw text generation"""
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    ctx = build_llm_context(payload)
    
    if provider == "perplexity":
        client = get_perplexity_client()
        resp = await anyio.to_thread.run_sync(
            lambda: client.chat.completions.create(
                model=os.getenv("PERPLEXITY_MODEL", "sonar-reasoning"),
                messages=[
                    {"role": "system", "content": system_instructions}, 
                    {"role": "user", "content": ctx}
                ]
            )
        )
        return resp.choices[0].message.content
    else:
        def _call():
            client = get_gemini_client()
            resp = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
                contents=[types.Content(role="user", parts=[types.Part(text=f"{system_instructions}\n\nCONTEXT:\n{ctx}")])]
            )
            return resp.text
        return gemini_call_with_retry("gemini_text", _call)

async def call_llm_structured(system_instructions: str, payload: ReviewPayload, response_model: Type[BaseModel]):
    """Orchestrates structured JSON generation with Pydantic validation"""
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    ctx = build_llm_context(payload)

    if provider == "perplexity":
        client = get_perplexity_client()
        schema = response_model.model_json_schema()
        
        # Format schema as readable text for prompt
        schema_str = json.dumps(schema, indent=2)
        
        prompt = f"""{system_instructions}

You MUST respond with ONLY a valid JSON object that matches this exact schema:

{schema_str}

Important:
- Return ONLY the JSON object, no markdown, no code blocks, no additional text
- All required fields must be present
- Follow the exact field names and types specified
"""
        
        resp = await anyio.to_thread.run_sync(
            lambda: client.chat.completions.create(
                model=os.getenv("PERPLEXITY_MODEL", "sonar-reasoning"),
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": ctx}
                ]
            )
        )
        
        # Clean the response - remove markdown code blocks if present
        content = resp.choices[0].message.content.strip()
        if content.startswith("```"):
            # Remove code fence
            content = re.sub(r'^```(?:json)?\s*\n', '', content)
            content = re.sub(r'\n```\s*$', '', content)
        
        try:
            return response_model.model_validate_json(content)
        except Exception as e:
            print(f"Failed to parse Perplexity response: {content[:200]}", file=sys.stderr)
            raise ValueError(f"Invalid JSON from Perplexity: {str(e)}")
    else:
        # Native Gemini structured output
        def _call():
            client = get_gemini_client()
            resp = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
                contents=[types.Part(text=f"{system_instructions}\n\nCONTEXT:\n{ctx}")],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_model,
                    temperature=0.2
                )
            )
            return response_model.model_validate(resp.parsed if resp.parsed else json.loads(resp.text))
        return gemini_call_with_retry(f"gemini_{response_model.__name__}", _call)

# ----------------------------
# Core Context Helpers
# ----------------------------
def clip(s: Optional[str], n: int) -> str:
    """Truncates long strings to manage context window limits"""
    if not s: return ""
    return s if len(s) <= n else s[:n] + "\n...(truncated)..."

def build_llm_context(payload: ReviewPayload) -> str:
    """Builds the prompt context from PR metadata and diffs"""
    pr_title = payload.pr_title or ""
    pr_body = clip(payload.pr_body, 1000)
    base = f"Repo: {payload.repo_full_name} | PR: #{payload.pr_number} - {pr_title}\nAuthor: {payload.pr_author_login}\n\nDescription:\n{pr_body}"

    if payload.kind == "review_comment":
        base += f"\n\nFile: {payload.comment_path}\nComment: {payload.comment_body}\n\nDiff Hunk:\n{clip(payload.comment_diff_hunk, 1000)}"
    
    if payload.files:
        base += "\n\nChanged Files Patches:"
        for f in payload.files[:3]:
            base += f"\n--- {f.filename} ---\n{clip(f.patch, 1000)}"
    
    return base

# ----------------------------
# Gemini Retry Wrapper
# ----------------------------
def gemini_call_with_retry(call_name: str, fn: Callable[[], T]) -> T:
    """Retries transient Gemini failures with exponential backoff"""
    attempt = 1
    delay = RETRY_INITIAL_DELAY_SEC
    while True:
        try:
            return fn()
        except Exception as e:
            if attempt >= RETRY_MAX_ATTEMPTS: raise e
            print(f"Retrying {call_name} (attempt {attempt})", file=sys.stderr)
            time.sleep(delay + random.uniform(0, RETRY_JITTER_SEC))
            delay = min(RETRY_MAX_DELAY_SEC, delay * 1.5)
            attempt += 1


# ----------------------------
# Formatting helpers
# ----------------------------
def format_debug_comment(payload: ReviewPayload, cls: Classification) -> str:
    where = "review" if payload.kind == "review" else "inline comment"
    original_text = payload.review_body if payload.kind == "review" else payload.comment_body
    original_text = (original_text or "").strip()

    lines = [
        f"🧠 **ContextWizard (debug: classification only - {os.getenv('LLM_PROVIDER', 'gemini')})**",
        f"- event: `{where}`",
        f"- category: **{cls.category}**",
        f"- confidence: `{cls.confidence:.2f}`",
        f"- needs_reply: `{cls.needs_reply}`",
        f"- needs_clarification: `{cls.needs_clarification}`",
        f"- reason: {cls.short_reason}",
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
        f"❓ **ContextWizard (clarified question - {os.getenv('LLM_PROVIDER', 'gemini')})**",
        f"- category: **{cls.category}**",
        f"- classification_confidence: `{cls.confidence:.2f}`",
        f"- rewrite_confidence: `{cq.confidence:.2f}`",
        f"- reason: {cls.short_reason}",
        f"- rewrite_note: {cq.short_reason}",
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
    provider = os.getenv('LLM_PROVIDER', 'gemini')
    return "\n".join(
        [
            f"🔧 **ContextWizard (change suggestion - {provider})**",
            f"1. **clarified version:** {clarified_request}",
            "2. **suggested code change:**",
            suggestion_block.strip(),
        ]
    ).strip()


def extract_first_fenced_code_block(text: str) -> str:
    """Extract the first code block from markdown"""
    pattern = r'```(?:\w+)?\s*\n(.*?)\n```'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return f"```\n{match.group(1)}\n```"
    return text


# ----------------------------
# FastAPI route
# ----------------------------
@app.post("/analyze-review", response_model=BackendResponse)
async def analyze_review(payload: ReviewPayload):
    provider = os.getenv("LLM_PROVIDER", "gemini")
    print(f"Processing kind: {payload.kind} for PR #{payload.pr_number} with provider: {provider}", file=sys.stderr)
    
    # Wizard Review Command
    if payload.kind == "wizard_review_command":
        try:
            sys_prompt = """You are ContextWizard, an AI code reviewer. 
Analyze the diff and identify bugs, security risks, or performance issues.
Format your response with:
- ### [TITLE] for each issue
- **Description** explaining the problem and how to fix it
Be concise and professional."""
            
            result = await call_llm_text(sys_prompt, payload)
            return BackendResponse(comment=f"🧙‍♂️ **Wizard Review ({provider})**\n\n{result}")
        except Exception as e:
            return BackendResponse(comment=f"❌ Error during Wizard Review: {str(e)[:200]}")

    # Classification
    print("Classifying comment...", file=sys.stderr)
    try:
        cls = await call_llm_structured(
            "Classify the intent and clarity of this GitHub PR comment into exactly ONE category: PRAISE, GOOD_CHANGE, BAD_CHANGE, GOOD_QUESTION, BAD_QUESTION, or UNKNOWN.",
            payload,
            Classification
        )
    except Exception as e:
        error_msg = str(e)[:200]
        print(f"Classification failed: {error_msg}", file=sys.stderr)
        cls = Classification(
            category="UNKNOWN",
            needs_reply=True,
            needs_clarification=False,
            confidence=0.0,
            short_reason=f"Classification failed: {error_msg}",
        )
        return BackendResponse(comment=format_debug_comment(payload, cls))

    # Only process inline comments
    if payload.kind != "review_comment":
        return BackendResponse(comment=format_debug_comment(payload, cls))

    # Handle GOOD_CHANGE
    if cls.category == "GOOD_CHANGE" and cls.confidence >= 0.7:
        print("Generating code suggestion...", file=sys.stderr)
        try:
            suggestion = await call_llm_text(
                f"""Generate a SHORT code diff for this change request.
Rules:
- Output ONLY a fenced code block (```diff or ```suggestion)
- Keep it minimal - change only relevant lines
- Do NOT rewrite whole files

Change requested: {payload.comment_body}""",
                payload
            )
            return BackendResponse(comment=extract_first_fenced_code_block(suggestion))
        except Exception as e:
            print(f"Code suggestion failed: {str(e)[:200]}", file=sys.stderr)
            return BackendResponse(comment=format_debug_comment(payload, cls))

    # Handle BAD_QUESTION
    if cls.category == "BAD_QUESTION" and cls.confidence >= 0.55:
        print("Clarifying question...", file=sys.stderr)
        try:
            cq = await call_llm_structured(
                """Rewrite this unclear question to be clear and actionable.
Rules:
- 1-2 short sentences max, end with "?"
- Do NOT answer the question
- Use placeholders if info is missing: <which file?>, <which function?>""",
                payload,
                ClarifiedQuestion
            )
            return BackendResponse(comment=format_clarification_question_comment(payload, cls, cq))
        except Exception as e:
            print(f"Question clarification failed: {str(e)[:200]}", file=sys.stderr)
            return BackendResponse(comment=format_debug_comment(payload, cls))

    # Handle BAD_CHANGE
    if cls.category == "BAD_CHANGE" and cls.confidence >= 0.55:
        print("Clarifying change request and generating suggestion...", file=sys.stderr)
        try:
            cc = await call_llm_structured(
                """Rewrite this unclear change request to be clear and actionable.
Rules:
- 1-2 short sentences max
- Use placeholders if info is missing: <which file?>, <acceptance criteria?>""",
                payload,
                ClarifiedChange
            )
            
            suggestion = await call_llm_text(
                f"""Generate a SHORT code diff for this change request.
Rules:
- Output ONLY a fenced code block (```diff or ```suggestion)
- Keep it minimal - change only relevant lines

Change requested: {cc.clarified_request}""",
                payload
            )
            
            body = format_bad_change_with_suggestion_comment(
                cls,
                cc.clarified_request,
                extract_first_fenced_code_block(suggestion)
            )
            return BackendResponse(comment=body)
        except Exception as e:
            print(f"BAD_CHANGE handling failed: {str(e)[:200]}", file=sys.stderr)
            return BackendResponse(comment=format_debug_comment(payload, cls))

    # Default: classification debug
    return BackendResponse(comment=format_debug_comment(payload, cls))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)