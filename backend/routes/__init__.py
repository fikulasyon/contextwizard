"""Routes package for ContextWizard backend."""
from .analyze import router as analyze_router
from .pending_comments import router as pending_comments_router

__all__ = [
    "analyze_router",
    "pending_comments_router",
]