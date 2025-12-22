"""
Pydantic models for Gemini structured outputs.
"""
from typing import Literal
from pydantic import BaseModel, Field

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
    needs_reply: bool = Field(
        ..., 
        description="True only for GOOD_CHANGE, BAD_CHANGE, BAD_QUESTION."
    )
    needs_clarification: bool = Field(
        ..., 
        description="True only for BAD_CHANGE or BAD_QUESTION."
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    short_reason: str = Field(
        ..., 
        description="One short sentence. No chain-of-thought."
    )

class ClarifiedQuestion(BaseModel):
    clarified_question: str = Field(
        ..., 
        description="A rewritten, clarified version of the original question."
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    short_reason: str = Field(
        ..., 
        description="One short sentence on what was ambiguous / what you clarified."
    )

class ClarifiedChange(BaseModel):
    clarified_request: str = Field(
        ...,
        description="A rewritten, clarified change request. Must be actionable but may contain placeholders like <which function?>.",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    short_reason: str = Field(
        ..., 
        description="One short sentence on what was unclear / what you clarified."
    )