"""
Gemini API client initialization and retry logic.
"""
import sys
import time
import random
from typing import Callable, TypeVar
from google import genai
from config import (
    GEMINI_API_KEY,
    RETRY_INITIAL_DELAY_SEC,
    RETRY_MAX_DELAY_SEC,
    RETRY_MAX_ATTEMPTS,
    RETRY_JITTER_SEC
)

T = TypeVar("T")

def get_client() -> genai.Client:
    """Get initialized Gemini client."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=GEMINI_API_KEY)

def _is_transient_gemini_error(exc: Exception) -> bool:
    """Check if exception is a transient error that should be retried."""
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
    """
    Execute a Gemini API call with exponential backoff retry logic.
    
    Args:
        call_name: Name of the operation for logging
        fn: Function to execute
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        jitter: Random jitter to add to delays
        
    Returns:
        Result of the function call
        
    Raises:
        Exception: If all retry attempts fail or non-transient error occurs
    """
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